"""
Serializers for the contacts app.

Provides DRF serializers for Contact, ContactActivity, ContactList, and related models
with proper multi-tenant support and nested relationships.
"""

from rest_framework import serializers
from platform_core.core.serializers import PlatformSerializer
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from .models import (
    Contact, ContactPartner, ContactActivity, ContactList,
    ContactStatus, ContactType, RelationshipType, ActivityType,
    EmailTemplate, EmailCampaign, EmailMessage, EmailEvent
)
from assessments.models import DevelopmentPartner
from platform_core.accounts.serializers import UserSerializer
from accounts.models import GroupMembership


def get_user_group(user):
    """Get the custom Group for a user via GroupMembership."""
    membership = GroupMembership.objects.filter(user=user).first()
    return membership.group if membership else None


class ContactListSerializer(serializers.ModelSerializer):
    """Basic serializer for contact lists."""
    
    created_by = UserSerializer(read_only=True)
    contact_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ContactList
        fields = [
            'id', 'name', 'description', 'is_dynamic', 'filter_criteria',
            'is_public', 'tags', 'created_by', 'created_at', 'updated_at',
            'contact_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']
    
    def get_contact_count(self, obj):
        """Get the number of contacts in this list."""
        return obj.get_contact_count()
    
    def create(self, validated_data):
        """Create a new contact list with the current user as creator."""
        validated_data['created_by'] = self.context['request'].user
        validated_data['group'] = get_user_group(self.context['request'].user)
        return super().create(validated_data)


class ContactPartnerSerializer(serializers.ModelSerializer):
    """Serializer for contact-partner relationships."""
    
    partner_name = serializers.CharField(source='partner.company_name', read_only=True)
    
    class Meta:
        model = ContactPartner
        fields = [
            'id', 'partner', 'partner_name', 'relationship_type',
            'start_date', 'end_date', 'is_primary', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ContactActivitySerializer(serializers.ModelSerializer):
    """Serializer for contact activities with generic relation support."""
    
    actor = UserSerializer(read_only=True)
    related_object_type = serializers.SerializerMethodField()
    related_object_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ContactActivity
        fields = [
            'id', 'activity_type', 'subject', 'description', 'actor',
            'metadata', 'outcome', 'follow_up_required', 'follow_up_date',
            'related_object_type', 'related_object_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'actor']
    
    def get_related_object_type(self, obj):
        """Get the type of the related object."""
        if obj.content_type:
            return obj.content_type.model
        return None
    
    def get_related_object_name(self, obj):
        """Get a display name for the related object."""
        if obj.related_object:
            return str(obj.related_object)
        return None
    
    def create(self, validated_data):
        """Create activity with current user as actor."""
        validated_data['actor'] = self.context['request'].user
        validated_data['group'] = get_user_group(self.context['request'].user)
        validated_data['contact'] = self.context['contact']
        return super().create(validated_data)


class ContactSerializer(serializers.ModelSerializer):
    """
    Main contact serializer with nested relationships and computed fields.
    
    Supports both list and detail views with optimized queries.
    """
    
    full_name = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    partner_relationships = ContactPartnerSerializer(many=True, read_only=True)
    assigned_to = UserSerializer(read_only=True)
    assigned_to_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    recent_activities = serializers.SerializerMethodField()
    
    class Meta:
        model = Contact
        fields = [
            'id', 'email', 'first_name', 'last_name', 'company_name',
            'contact_type', 'status', 'phone_primary', 'phone_secondary',
            'website', 'city', 'country', 'job_title', 'department',
            'current_score', 'source', 'tags', 'email_opt_in', 'sms_opt_in',
            'assigned_to', 'assigned_to_id', 'last_activity_at',
            'last_email_sent_at', 'last_email_opened_at', 'notes',
            'custom_fields', 'full_name', 'display_name',
            'partner_relationships', 'recent_activities',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'current_score', 'last_activity_at', 'last_email_sent_at',
            'last_email_opened_at', 'created_at', 'updated_at'
        ]
    
    def get_recent_activities(self, obj):
        """Get the 5 most recent activities for this contact."""
        if self.context.get('exclude_activities'):
            return []
        
        activities = obj.activities.select_related('actor').order_by('-created_at')[:5]
        return ContactActivitySerializer(activities, many=True).data
    
    def validate_email(self, value):
        """Ensure email is unique within the group."""
        group = get_user_group(self.context['request'].user)
        qs = Contact.objects.filter(group=group, email=value)
        
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise serializers.ValidationError(
                "A contact with this email already exists in your organization."
            )
        return value
    
    def validate_contact_type(self, value):
        """Validate contact type and ensure required fields."""
        if value == ContactType.INDIVIDUAL:
            if not self.initial_data.get('first_name') and not self.initial_data.get('last_name'):
                raise serializers.ValidationError(
                    "Individual contacts must have at least a first or last name."
                )
        elif value == ContactType.COMPANY:
            if not self.initial_data.get('company_name'):
                raise serializers.ValidationError(
                    "Company contacts must have a company name."
                )
        return value
    
    def create(self, validated_data):
        """Create a new contact with group assignment."""
        validated_data['group'] = get_user_group(self.context['request'].user)
        
        # Handle assigned_to_id
        assigned_to_id = validated_data.pop('assigned_to_id', None)
        if assigned_to_id:
            validated_data['assigned_to_id'] = assigned_to_id
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update contact with status transition support."""
        # Handle assigned_to_id
        assigned_to_id = validated_data.pop('assigned_to_id', None)
        if assigned_to_id is not None:
            validated_data['assigned_to_id'] = assigned_to_id
        
        # Handle status transitions
        new_status = validated_data.get('status')
        if new_status and new_status != instance.status:
            # Validate FSM transition
            if new_status == ContactStatus.QUALIFIED and instance.status == ContactStatus.LEAD:
                instance.qualify()
            elif new_status == ContactStatus.OPPORTUNITY and instance.status == ContactStatus.QUALIFIED:
                instance.convert_to_opportunity()
            elif new_status == ContactStatus.CUSTOMER and instance.status == ContactStatus.OPPORTUNITY:
                instance.convert_to_customer()
            elif new_status == ContactStatus.INACTIVE:
                instance.mark_inactive()
            elif new_status == ContactStatus.UNSUBSCRIBED:
                instance.unsubscribe()
            else:
                raise serializers.ValidationError({
                    'status': f'Invalid status transition from {instance.status} to {new_status}'
                })
            
            # Remove status from validated_data since FSM handles it
            validated_data.pop('status')
        
        return super().update(instance, validated_data)


class ContactDetailSerializer(ContactSerializer):
    """Detailed contact serializer with additional computed fields."""
    
    partner_count = serializers.SerializerMethodField()
    
    class Meta(ContactSerializer.Meta):
        fields = ContactSerializer.Meta.fields + ['partner_count']
    
    def get_partner_count(self, obj):
        """Get the number of partner relationships for this contact."""
        return obj.partner_relationships.count()


class ContactListDetailSerializer(ContactListSerializer):
    """Detailed serializer for contact lists including member contacts."""
    
    contacts = ContactSerializer(many=True, read_only=True)
    
    class Meta(ContactListSerializer.Meta):
        fields = ContactListSerializer.Meta.fields + ['contacts']


class ContactImportSerializer(serializers.Serializer):
    """Serializer for bulk contact import."""
    
    contacts = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=1000
    )
    list_id = serializers.UUIDField(required=False, help_text="Optional list to add contacts to")
    update_existing = serializers.BooleanField(
        default=False,
        help_text="Update existing contacts instead of skipping"
    )
    
    def validate_contacts(self, value):
        """Validate each contact in the import list."""
        required_fields = ['email']
        errors = []
        
        for idx, contact in enumerate(value):
            contact_errors = {}
            
            # Check required fields
            for field in required_fields:
                if not contact.get(field):
                    contact_errors[field] = "This field is required."
            
            # Validate contact type specific fields
            contact_type = contact.get('contact_type', ContactType.INDIVIDUAL)
            if contact_type == ContactType.INDIVIDUAL:
                if not contact.get('first_name') and not contact.get('last_name'):
                    contact_errors['name'] = "Individual contacts need first or last name."
            elif contact_type == ContactType.COMPANY:
                if not contact.get('company_name'):
                    contact_errors['company_name'] = "Company contacts need company name."
            
            if contact_errors:
                errors.append({f"contact_{idx}": contact_errors})
        
        if errors:
            raise serializers.ValidationError(errors)
        
        return value
    
    def create(self, validated_data):
        """Bulk create or update contacts."""
        contacts_data = validated_data['contacts']
        list_id = validated_data.get('list_id')
        update_existing = validated_data['update_existing']
        
        group = get_user_group(self.context['request'].user)
        created_contacts = []
        updated_contacts = []
        skipped_contacts = []
        
        with transaction.atomic():
            for contact_data in contacts_data:
                email = contact_data['email']
                
                try:
                    existing_contact = Contact.objects.get(group=group, email=email)
                    
                    if update_existing:
                        # Update existing contact
                        for key, value in contact_data.items():
                            if key != 'email' and value is not None:
                                setattr(existing_contact, key, value)
                        existing_contact.save()
                        updated_contacts.append(existing_contact)
                    else:
                        skipped_contacts.append(email)
                    
                except Contact.DoesNotExist:
                    # Create new contact
                    contact_data['group'] = group
                    contact = Contact.objects.create(**contact_data)
                    created_contacts.append(contact)
            
            # Add to list if specified
            if list_id and (created_contacts or updated_contacts):
                try:
                    contact_list = ContactList.objects.get(
                        id=list_id,
                        group=group
                    )
                    contact_list.contacts.add(*(created_contacts + updated_contacts))
                except ContactList.DoesNotExist:
                    pass
        
        return {
            'created': len(created_contacts),
            'updated': len(updated_contacts),
            'skipped': len(skipped_contacts),
            'skipped_emails': skipped_contacts
        }


class ContactExportSerializer(serializers.Serializer):
    """Serializer for contact export parameters."""
    
    format = serializers.ChoiceField(choices=['csv', 'excel'], default='csv')
    fields = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Specific fields to export. If not provided, exports all fields."
    )
    list_id = serializers.UUIDField(
        required=False,
        help_text="Export only contacts from a specific list"
    )
    filters = serializers.DictField(
        required=False,
        help_text="Additional filters to apply"
    )


# Email Campaign Serializers

class EmailTemplateSerializer(serializers.ModelSerializer):
    """Serializer for email templates."""
    
    created_by = UserSerializer(read_only=True)
    preview_html = serializers.SerializerMethodField()
    preview_text = serializers.SerializerMethodField()
    preview_subject = serializers.SerializerMethodField()
    
    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'name', 'template_type', 'subject', 'preheader',
            'html_content', 'text_content', 'from_name', 'from_email',
            'reply_to_email', 'available_variables', 'is_active',
            'is_tested', 'times_used', 'created_by', 'created_at',
            'updated_at', 'preview_html', 'preview_text', 'preview_subject'
        ]
        read_only_fields = ['id', 'times_used', 'created_at', 'updated_at']
    
    def get_preview_html(self, obj):
        """Generate preview of HTML content with sample data."""
        try:
            from django.template import Template, Context
            template = Template(obj.html_content)
            context = Context(obj.get_preview_data())
            return template.render(context)
        except Exception:
            return obj.html_content
    
    def get_preview_text(self, obj):
        """Generate preview of text content with sample data."""
        try:
            from django.template import Template, Context
            template = Template(obj.text_content)
            context = Context(obj.get_preview_data())
            return template.render(context)
        except Exception:
            return obj.text_content
    
    def get_preview_subject(self, obj):
        """Generate preview of subject with sample data."""
        try:
            from django.template import Template, Context
            template = Template(obj.subject)
            context = Context(obj.get_preview_data())
            return template.render(context)
        except Exception:
            return obj.subject
    
    def create(self, validated_data):
        """Create template with current user as creator."""
        validated_data['created_by'] = self.context['request'].user
        validated_data['group'] = get_user_group(self.context['request'].user)
        return super().create(validated_data)


class EmailTemplateListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for template lists."""
    
    created_by = serializers.StringRelatedField()
    
    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'name', 'template_type', 'subject', 'is_active',
            'times_used', 'created_by', 'created_at'
        ]


class ContactListSummarySerializer(serializers.ModelSerializer):
    """Summary serializer for contact lists in campaigns."""
    
    contact_count = serializers.IntegerField(source='get_contact_count', read_only=True)
    
    class Meta:
        model = ContactList
        fields = ['id', 'name', 'contact_count']


class EmailCampaignSerializer(serializers.ModelSerializer):
    """Serializer for email campaigns."""
    
    template = EmailTemplateListSerializer(read_only=True)
    template_id = serializers.UUIDField(write_only=True)
    contact_lists = ContactListSummarySerializer(many=True, read_only=True)
    contact_list_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    created_by = UserSerializer(read_only=True)
    approved_by = UserSerializer(read_only=True)
    
    # Analytics fields
    open_rate = serializers.ReadOnlyField()
    click_rate = serializers.ReadOnlyField()
    bounce_rate = serializers.ReadOnlyField()
    
    # Computed fields
    recipient_count = serializers.SerializerMethodField()
    can_send = serializers.SerializerMethodField()
    
    class Meta:
        model = EmailCampaign
        fields = [
            'id', 'name', 'description', 'template', 'template_id',
            'status', 'contact_lists', 'contact_list_ids',
            'sending_strategy', 'scheduled_at', 'send_rate_per_hour',
            'track_opens', 'track_clicks', 'include_unsubscribe_link',
            'is_ab_test', 'ab_test_percentage', 'variant_templates',
            'total_recipients', 'emails_sent', 'emails_delivered',
            'emails_opened', 'emails_clicked', 'emails_bounced',
            'emails_unsubscribed', 'open_rate', 'click_rate',
            'bounce_rate', 'created_by', 'approved_by', 'started_at',
            'completed_at', 'created_at', 'updated_at',
            'recipient_count', 'can_send'
        ]
        read_only_fields = [
            'id', 'total_recipients', 'emails_sent', 'emails_delivered',
            'emails_opened', 'emails_clicked', 'emails_bounced',
            'emails_unsubscribed', 'started_at', 'completed_at',
            'created_at', 'updated_at'
        ]
    
    def get_recipient_count(self, obj):
        """Calculate total unique recipients."""
        contact_ids = set()
        for contact_list in obj.contact_lists.all():
            contact_ids.update(contact_list.contacts.values_list('id', flat=True))
        
        # Remove excluded contacts
        excluded_ids = obj.excluded_contacts.values_list('id', flat=True)
        contact_ids -= set(excluded_ids)
        
        return len(contact_ids)
    
    def get_can_send(self, obj):
        """Check if campaign can be sent."""
        if obj.status not in [obj.CampaignStatus.DRAFT, obj.CampaignStatus.SCHEDULED]:
            return False
        
        if obj.sending_strategy == obj.SendingStrategy.SCHEDULED and not obj.scheduled_at:
            return False
        
        return self.get_recipient_count(obj) > 0
    
    def validate_scheduled_at(self, value):
        """Ensure scheduled time is in the future."""
        if value and value <= timezone.now():
            raise serializers.ValidationError("Scheduled time must be in the future")
        return value
    
    def create(self, validated_data):
        """Create campaign with M2M relationships."""
        contact_list_ids = validated_data.pop('contact_list_ids', [])
        validated_data['created_by'] = self.context['request'].user
        validated_data['group'] = get_user_group(self.context['request'].user)
        
        # Convert template_id to template object
        template_id = validated_data.pop('template_id')
        validated_data['template'] = EmailTemplate.objects.get(id=template_id)
        
        campaign = super().create(validated_data)
        
        # Add contact lists
        if contact_list_ids:
            lists = ContactList.objects.filter(
                id__in=contact_list_ids,
                group=campaign.group
            )
            campaign.contact_lists.set(lists)
        
        return campaign
    
    def update(self, instance, validated_data):
        """Update campaign with M2M relationships."""
        contact_list_ids = validated_data.pop('contact_list_ids', None)
        
        # Handle template update
        if 'template_id' in validated_data:
            template_id = validated_data.pop('template_id')
            validated_data['template'] = EmailTemplate.objects.get(id=template_id)
        
        instance = super().update(instance, validated_data)
        
        # Update contact lists if provided
        if contact_list_ids is not None:
            lists = ContactList.objects.filter(
                id__in=contact_list_ids,
                group=instance.group
            )
            instance.contact_lists.set(lists)
        
        return instance


class EmailCampaignListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for campaign lists."""
    
    template_name = serializers.CharField(source='template.name', read_only=True)
    created_by = serializers.StringRelatedField()
    open_rate = serializers.ReadOnlyField()
    click_rate = serializers.ReadOnlyField()
    
    class Meta:
        model = EmailCampaign
        fields = [
            'id', 'name', 'template_name', 'status', 'scheduled_at',
            'total_recipients', 'emails_sent', 'open_rate', 'click_rate',
            'created_by', 'created_at'
        ]


class EmailMessageSerializer(serializers.ModelSerializer):
    """Serializer for email messages."""
    
    contact = serializers.StringRelatedField()
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    events = serializers.SerializerMethodField()
    
    class Meta:
        model = EmailMessage
        fields = [
            'id', 'campaign', 'campaign_name', 'contact', 'template_used',
            'subject', 'from_email', 'to_email', 'status', 'message_id',
            'queued_at', 'sent_at', 'delivered_at', 'first_opened_at',
            'last_opened_at', 'open_count', 'first_clicked_at',
            'last_clicked_at', 'click_count', 'bounce_type',
            'bounce_reason', 'failed_reason', 'created_at', 'events'
        ]
        read_only_fields = [
            'id', 'message_id', 'queued_at', 'sent_at', 'delivered_at',
            'first_opened_at', 'last_opened_at', 'open_count',
            'first_clicked_at', 'last_clicked_at', 'click_count',
            'bounce_type', 'bounce_reason', 'failed_reason', 'created_at'
        ]
    
    def get_events(self, obj):
        """Get recent events for this message."""
        events = obj.events.order_by('-timestamp')[:10]
        return EmailEventSerializer(events, many=True).data


class EmailEventSerializer(serializers.ModelSerializer):
    """Serializer for email events."""
    
    class Meta:
        model = EmailEvent
        fields = [
            'id', 'message', 'event_type', 'timestamp', 'ip_address',
            'user_agent', 'metadata', 'link_url', 'link_text'
        ]
        read_only_fields = ['id', 'timestamp']


class CampaignStatsSerializer(serializers.Serializer):
    """Serializer for campaign statistics."""
    
    total_campaigns = serializers.IntegerField()
    active_campaigns = serializers.IntegerField()
    total_emails_sent = serializers.IntegerField()
    average_open_rate = serializers.FloatField()
    average_click_rate = serializers.FloatField()
    recent_campaigns = EmailCampaignListSerializer(many=True)


class SendTestEmailSerializer(serializers.Serializer):
    """Serializer for sending test emails."""
    
    template_id = serializers.UUIDField()
    recipient_email = serializers.EmailField()
    test_data = serializers.DictField(required=False, default=dict)