"""
Email campaign serializers for the EnterpriseLand Due-Diligence Platform.

Provides comprehensive serializers for email templates, campaigns, messages,
and events with validation and nested relationships.
"""

from rest_framework import serializers
from django.utils import timezone
from django.template import Template, Context
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import (
    EmailTemplate, EmailCampaign, EmailMessage, EmailEvent,
    Contact, ContactList
)
from accounts.serializers import UserSerializer
from accounts.models import GroupMembership


def get_user_group(user):
    """Get the custom Group for a user via GroupMembership."""
    membership = GroupMembership.objects.filter(user=user).first()
    return membership.group if membership else None


class EmailTemplateSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for email templates with preview functionality.
    """
    
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
        read_only_fields = ['id', 'times_used', 'created_at', 'updated_at', 'created_by']
    
    def get_preview_html(self, obj):
        """Generate preview of HTML content with sample data."""
        try:
            preview_data = self.context.get('preview_data', obj.get_preview_data())
            template = Template(obj.html_content)
            context = Context(preview_data)
            return template.render(context)
        except Exception as e:
            return f"Template error: {str(e)}"
    
    def get_preview_text(self, obj):
        """Generate preview of text content with sample data."""
        try:
            preview_data = self.context.get('preview_data', obj.get_preview_data())
            template = Template(obj.text_content)
            context = Context(preview_data)
            return template.render(context)
        except Exception as e:
            return f"Template error: {str(e)}"
    
    def get_preview_subject(self, obj):
        """Generate preview of subject with sample data."""
        try:
            preview_data = self.context.get('preview_data', obj.get_preview_data())
            template = Template(obj.subject)
            context = Context(preview_data)
            return template.render(context)
        except Exception as e:
            return f"Template error: {str(e)}"
    
    def validate_subject(self, value):
        """Validate subject line length and content."""
        if len(value) > 150:
            raise serializers.ValidationError(
                "Subject line should be less than 150 characters for better deliverability."
            )
        return value
    
    def validate_html_content(self, value):
        """Validate HTML content is well-formed."""
        # Basic validation - in production you'd want more thorough HTML validation
        if not value.strip():
            raise serializers.ValidationError("HTML content cannot be empty.")
        
        # Check for required unsubscribe link placeholder
        if '{{ unsubscribe_url }}' not in value:
            raise serializers.ValidationError(
                "HTML content must include {{ unsubscribe_url }} for compliance."
            )
        
        return value
    
    def validate_text_content(self, value):
        """Validate text content."""
        if not value.strip():
            raise serializers.ValidationError("Text content cannot be empty.")
        
        # Check for required unsubscribe link placeholder
        if '{{ unsubscribe_url }}' not in value:
            raise serializers.ValidationError(
                "Text content must include {{ unsubscribe_url }} for compliance."
            )
        
        return value
    
    def validate(self, data):
        """Cross-field validation."""
        # Validate template variables are consistent
        if 'subject' in data and 'html_content' in data:
            # Extract variables from all fields
            import re
            variable_pattern = r'\{\{\s*(\w+)\s*\}\}'
            
            subject_vars = set(re.findall(variable_pattern, data.get('subject', '')))
            html_vars = set(re.findall(variable_pattern, data.get('html_content', '')))
            text_vars = set(re.findall(variable_pattern, data.get('text_content', '')))
            
            # All variables should be available in Contact model or custom
            all_vars = subject_vars | html_vars | text_vars
            
            # Update available_variables
            data['available_variables'] = list(all_vars)
        
        return data
    
    def create(self, validated_data):
        """Create template with current user as creator."""
        validated_data['created_by'] = self.context['request'].user
        validated_data['group'] = get_user_group(self.context['request'].user)
        return super().create(validated_data)


class EmailTemplateListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for template lists.
    """
    
    created_by = serializers.StringRelatedField()
    
    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'name', 'template_type', 'subject', 'is_active',
            'is_tested', 'times_used', 'created_by', 'created_at'
        ]
        read_only_fields = fields


class ContactListSummarySerializer(serializers.ModelSerializer):
    """
    Summary serializer for contact lists in campaigns.
    """
    
    contact_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ContactList
        fields = ['id', 'name', 'is_dynamic', 'contact_count']
        read_only_fields = fields
    
    def get_contact_count(self, obj):
        """Get contact count for the list."""
        return obj.get_contact_count()


class EmailCampaignSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for email campaigns with analytics.
    """
    
    template = EmailTemplateListSerializer(read_only=True)
    template_id = serializers.UUIDField(write_only=True)
    contact_lists = ContactListSummarySerializer(many=True, read_only=True)
    contact_list_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    excluded_contact_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    variant_template_ids = serializers.ListField(
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
    estimated_send_time = serializers.SerializerMethodField()
    
    class Meta:
        model = EmailCampaign
        fields = [
            'id', 'name', 'description', 'template', 'template_id',
            'status', 'contact_lists', 'contact_list_ids',
            'excluded_contact_ids', 'sending_strategy', 'scheduled_at',
            'send_rate_per_hour', 'track_opens', 'track_clicks',
            'include_unsubscribe_link', 'is_ab_test', 'ab_test_percentage',
            'variant_templates', 'variant_template_ids', 'total_recipients',
            'emails_sent', 'emails_delivered', 'emails_opened', 'emails_clicked',
            'emails_bounced', 'emails_unsubscribed', 'open_rate', 'click_rate',
            'bounce_rate', 'created_by', 'approved_by', 'started_at',
            'completed_at', 'created_at', 'updated_at', 'recipient_count',
            'can_send', 'estimated_send_time'
        ]
        read_only_fields = [
            'id', 'status', 'total_recipients', 'emails_sent', 'emails_delivered',
            'emails_opened', 'emails_clicked', 'emails_bounced',
            'emails_unsubscribed', 'started_at', 'completed_at',
            'created_at', 'updated_at', 'created_by', 'approved_by'
        ]
    
    def get_recipient_count(self, obj):
        """Calculate total unique recipients."""
        contact_ids = set()
        for contact_list in obj.contact_lists.all():
            contact_ids.update(contact_list.contacts.values_list('id', flat=True))
        
        # Remove excluded contacts
        excluded_ids = obj.excluded_contacts.values_list('id', flat=True)
        contact_ids -= set(excluded_ids)
        
        # Filter for opted-in, active contacts
        return Contact.objects.filter(
            id__in=contact_ids,
            email_opt_in=True,
            status__in=[Contact.ContactStatus.LEAD, Contact.ContactStatus.QUALIFIED,
                       Contact.ContactStatus.OPPORTUNITY, Contact.ContactStatus.CUSTOMER]
        ).count()
    
    def get_can_send(self, obj):
        """Check if campaign can be sent."""
        if obj.status not in [obj.CampaignStatus.DRAFT, obj.CampaignStatus.SCHEDULED]:
            return False
        
        if obj.sending_strategy == obj.SendingStrategy.SCHEDULED and not obj.scheduled_at:
            return False
        
        if not obj.template or not obj.template.is_active or not obj.template.is_tested:
            return False
        
        return self.get_recipient_count(obj) > 0
    
    def get_estimated_send_time(self, obj):
        """Calculate estimated time to send all emails."""
        recipient_count = self.get_recipient_count(obj)
        if recipient_count == 0 or obj.send_rate_per_hour == 0:
            return None
        
        hours = recipient_count / obj.send_rate_per_hour
        return {
            'hours': round(hours, 2),
            'formatted': f"{int(hours)}h {int((hours % 1) * 60)}m"
        }
    
    def validate_scheduled_at(self, value):
        """Ensure scheduled time is in the future."""
        if value and value <= timezone.now():
            raise serializers.ValidationError("Scheduled time must be in the future.")
        return value
    
    def validate_ab_test_percentage(self, value):
        """Validate A/B test percentage."""
        if value < 5 or value > 50:
            raise serializers.ValidationError(
                "A/B test percentage must be between 5% and 50%."
            )
        return value
    
    def validate(self, data):
        """Cross-field validation."""
        # Validate scheduling
        if data.get('sending_strategy') == EmailCampaign.SendingStrategy.SCHEDULED:
            if not data.get('scheduled_at'):
                raise serializers.ValidationError({
                    'scheduled_at': 'Scheduled time is required for scheduled campaigns.'
                })
        
        # Validate A/B testing
        if data.get('is_ab_test'):
            variant_ids = data.get('variant_template_ids', [])
            if len(variant_ids) < 1:
                raise serializers.ValidationError({
                    'variant_template_ids': 'At least one variant template is required for A/B tests.'
                })
        
        return data
    
    def create(self, validated_data):
        """Create campaign with M2M relationships."""
        contact_list_ids = validated_data.pop('contact_list_ids', [])
        excluded_contact_ids = validated_data.pop('excluded_contact_ids', [])
        variant_template_ids = validated_data.pop('variant_template_ids', [])
        
        validated_data['created_by'] = self.context['request'].user
        validated_data['group'] = get_user_group(self.context['request'].user)
        
        # Get template
        template_id = validated_data.pop('template_id')
        validated_data['template'] = EmailTemplate.objects.get(
            id=template_id,
            group=validated_data['group']
        )
        
        # Create campaign
        campaign = super().create(validated_data)
        
        # Set M2M relationships
        if contact_list_ids:
            lists = ContactList.objects.filter(
                id__in=contact_list_ids,
                group=campaign.group
            )
            campaign.contact_lists.set(lists)
        
        if excluded_contact_ids:
            contacts = Contact.objects.filter(
                id__in=excluded_contact_ids,
                group=campaign.group
            )
            campaign.excluded_contacts.set(contacts)
        
        if variant_template_ids:
            templates = EmailTemplate.objects.filter(
                id__in=variant_template_ids,
                group=campaign.group
            )
            campaign.variant_templates.set(templates)
        
        return campaign
    
    def update(self, instance, validated_data):
        """Update campaign with M2M relationships."""
        contact_list_ids = validated_data.pop('contact_list_ids', None)
        excluded_contact_ids = validated_data.pop('excluded_contact_ids', None)
        variant_template_ids = validated_data.pop('variant_template_ids', None)
        
        # Handle template update
        if 'template_id' in validated_data:
            template_id = validated_data.pop('template_id')
            validated_data['template'] = EmailTemplate.objects.get(
                id=template_id,
                group=instance.group
            )
        
        # Update instance
        instance = super().update(instance, validated_data)
        
        # Update M2M relationships if provided
        if contact_list_ids is not None:
            lists = ContactList.objects.filter(
                id__in=contact_list_ids,
                group=instance.group
            )
            instance.contact_lists.set(lists)
        
        if excluded_contact_ids is not None:
            contacts = Contact.objects.filter(
                id__in=excluded_contact_ids,
                group=instance.group
            )
            instance.excluded_contacts.set(contacts)
        
        if variant_template_ids is not None:
            templates = EmailTemplate.objects.filter(
                id__in=variant_template_ids,
                group=instance.group
            )
            instance.variant_templates.set(templates)
        
        return instance


class EmailCampaignListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for campaign lists.
    """
    
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
        read_only_fields = fields


class EmailMessageSerializer(serializers.ModelSerializer):
    """
    Serializer for individual email messages with event tracking.
    """
    
    contact_name = serializers.CharField(source='contact.display_name', read_only=True)
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    template_name = serializers.CharField(source='template_used.name', read_only=True)
    events = serializers.SerializerMethodField()
    
    class Meta:
        model = EmailMessage
        fields = [
            'id', 'campaign', 'campaign_name', 'contact', 'contact_name',
            'template_used', 'template_name', 'subject', 'from_email',
            'to_email', 'status', 'message_id', 'queued_at', 'sent_at',
            'delivered_at', 'first_opened_at', 'last_opened_at', 'open_count',
            'first_clicked_at', 'last_clicked_at', 'click_count',
            'bounce_type', 'bounce_reason', 'failed_reason', 'ip_address',
            'user_agent', 'created_at', 'events'
        ]
        read_only_fields = [
            'id', 'message_id', 'queued_at', 'sent_at', 'delivered_at',
            'first_opened_at', 'last_opened_at', 'open_count',
            'first_clicked_at', 'last_clicked_at', 'click_count',
            'bounce_type', 'bounce_reason', 'failed_reason',
            'ip_address', 'user_agent', 'created_at'
        ]
    
    def get_events(self, obj):
        """Get recent events for this message."""
        events = obj.events.order_by('-timestamp')[:5]
        return EmailEventSerializer(events, many=True).data


class EmailEventSerializer(serializers.ModelSerializer):
    """
    Serializer for email tracking events.
    """
    
    message_subject = serializers.CharField(source='message.subject', read_only=True)
    contact_email = serializers.CharField(source='message.to_email', read_only=True)
    campaign_name = serializers.CharField(source='message.campaign.name', read_only=True)
    
    class Meta:
        model = EmailEvent
        fields = [
            'id', 'message', 'message_subject', 'contact_email',
            'campaign_name', 'event_type', 'timestamp', 'ip_address',
            'user_agent', 'metadata', 'link_url', 'link_text'
        ]
        read_only_fields = ['id', 'timestamp']


class CampaignStatsSerializer(serializers.Serializer):
    """
    Serializer for overall campaign statistics.
    """
    
    total_campaigns = serializers.IntegerField()
    active_campaigns = serializers.IntegerField()
    total_emails_sent = serializers.IntegerField()
    average_open_rate = serializers.FloatField()
    average_click_rate = serializers.FloatField()
    recent_campaigns = EmailCampaignListSerializer(many=True)


class SendTestEmailSerializer(serializers.Serializer):
    """
    Serializer for sending test emails.
    """
    
    recipient_email = serializers.EmailField()
    test_data = serializers.DictField(
        required=False,
        default=dict,
        help_text="Optional data for template variable substitution"
    )
    
    def validate_recipient_email(self, value):
        """Ensure test emails go to verified addresses."""
        # In production, you might want to restrict test emails to
        # verified domains or specific addresses
        return value


class BulkEmailActionSerializer(serializers.Serializer):
    """
    Serializer for bulk email actions (pause, resume, cancel).
    """
    
    campaign_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=50
    )
    action = serializers.ChoiceField(
        choices=['pause', 'resume', 'cancel']
    )


class EmailAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for email analytics data.
    """
    
    period = serializers.ChoiceField(
        choices=['hour', 'day', 'week', 'month'],
        default='day'
    )
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    campaign_id = serializers.UUIDField(required=False)
    
    def validate(self, data):
        """Validate date range."""
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] >= data['end_date']:
                raise serializers.ValidationError(
                    "End date must be after start date."
                )
        return data