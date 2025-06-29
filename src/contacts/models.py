"""
Contact management models for the EnterpriseLand Due-Diligence Platform.

This module provides comprehensive contact and relationship management capabilities
for marketing, outreach, and business development activities while maintaining
the existing multi-tenant architecture and role-based access control.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator, MaxValueValidator, EmailValidator
from django.core.exceptions import ValidationError
from django_fsm import FSMField, transition

from assessments.base_models import PlatformModel, TimestampedModel, UUIDModel
from platform_core.accounts.models import User
import pycountry


def validate_country_code(value):
    """Validate ISO 3166-1 alpha-2 country code."""
    if not isinstance(value, str):
        raise ValidationError("Country code must be a string")
    
    code = value.upper()
    if len(code) != 2:
        raise ValidationError("Country code must be exactly 2 characters")
    
    if pycountry.countries.get(alpha_2=code) is None:
        raise ValidationError(f"'{code}' is not a valid ISO 3166-1 alpha-2 country code")


class ContactStatus(models.TextChoices):
    """
    Contact lifecycle status using Finite State Machine pattern.
    
    Tracks the progression of a contact through marketing and sales funnel.
    """
    LEAD = 'lead', 'Lead'
    QUALIFIED = 'qualified', 'Qualified Lead'
    OPPORTUNITY = 'opportunity', 'Opportunity'
    CUSTOMER = 'customer', 'Customer'
    INACTIVE = 'inactive', 'Inactive'
    UNSUBSCRIBED = 'unsubscribed', 'Unsubscribed'


class ContactType(models.TextChoices):
    """Type of contact relationship."""
    INDIVIDUAL = 'individual', 'Individual Contact'
    COMPANY = 'company', 'Company Contact'


class RelationshipType(models.TextChoices):
    """Relationship between contact and development partner."""
    EMPLOYEE = 'employee', 'Employee'
    DIRECTOR = 'director', 'Director'
    ADVISOR = 'advisor', 'Advisor'
    CONSULTANT = 'consultant', 'Consultant'
    INVESTOR = 'investor', 'Investor'
    VENDOR = 'vendor', 'Vendor'
    CLIENT = 'client', 'Client'
    OTHER = 'other', 'Other'


class ActivityType(models.TextChoices):
    """Types of contact activities for tracking interactions."""
    EMAIL_SENT = 'email_sent', 'Email Sent'
    EMAIL_RECEIVED = 'email_received', 'Email Received'
    EMAIL_OPENED = 'email_opened', 'Email Opened'
    EMAIL_CLICKED = 'email_clicked', 'Email Link Clicked'
    CALL_MADE = 'call_made', 'Call Made'
    CALL_RECEIVED = 'call_received', 'Call Received'
    MEETING_SCHEDULED = 'meeting_scheduled', 'Meeting Scheduled'
    MEETING_COMPLETED = 'meeting_completed', 'Meeting Completed'
    NOTE_ADDED = 'note_added', 'Note Added'
    DOCUMENT_SHARED = 'document_shared', 'Document Shared'
    FORM_SUBMITTED = 'form_submitted', 'Form Submitted'
    CAMPAIGN_SENT = 'campaign_sent', 'Campaign Sent'
    WEBSITE_VISIT = 'website_visit', 'Website Visit'


class Contact(PlatformModel, TimestampedModel, UUIDModel):
    """
    Core contact model supporting both individual and company contacts.
    
    Implements FSM for status transitions, lead scoring, and comprehensive
    contact information management while respecting group-based multi-tenancy.
    """
    
    # Basic identification
    email = models.EmailField(
        validators=[EmailValidator()],
        help_text="Primary email address for the contact"
    )
    first_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="First name (for individual contacts)"
    )
    last_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Last name (for individual contacts)"
    )
    company_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Company name (for company contacts or individual's employer)"
    )
    
    # Contact type and status
    contact_type = models.CharField(
        max_length=20,
        choices=ContactType.choices,
        default=ContactType.INDIVIDUAL,
        help_text="Type of contact (individual or company)"
    )
    status = FSMField(
        default=ContactStatus.LEAD,
        choices=ContactStatus.choices,
        help_text="Current status in the contact lifecycle"
    )
    
    # Contact information
    phone_primary = models.CharField(
        max_length=20,
        blank=True,
        help_text="Primary phone number"
    )
    phone_secondary = models.CharField(
        max_length=20,
        blank=True,
        help_text="Secondary phone number"
    )
    website = models.URLField(
        blank=True,
        help_text="Website URL"
    )
    
    # Location information
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="City location"
    )
    country = models.CharField(
        max_length=2,
        validators=[validate_country_code],
        blank=True,
        help_text="Country (ISO 3166-1 alpha-2 code)"
    )
    
    # Professional information
    job_title = models.CharField(
        max_length=150,
        blank=True,
        help_text="Job title or position"
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        help_text="Department or division"
    )
    
    # Marketing and lead management
    current_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Current lead score (0-100, denormalized for performance)"
    )
    source = models.CharField(
        max_length=100,
        blank=True,
        help_text="Source of contact (referral, website, event, etc.)"
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Flexible tagging system for categorization"
    )
    
    # Preferences and consent
    email_opt_in = models.BooleanField(
        default=True,
        help_text="Consent to receive marketing emails"
    )
    sms_opt_in = models.BooleanField(
        default=False,
        help_text="Consent to receive SMS messages"
    )
    
    # Relationship tracking
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_contacts',
        help_text="User responsible for this contact"
    )
    
    # Activity tracking (denormalized for performance)
    last_activity_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last recorded activity"
    )
    last_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last email sent to this contact"
    )
    last_email_opened_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last email opened by this contact"
    )
    
    # Notes and additional information
    notes = models.TextField(
        blank=True,
        help_text="Private notes about the contact"
    )
    custom_fields = models.JSONField(
        default=dict,
        blank=True,
        help_text="Flexible custom fields for additional data"
    )
    
    class Meta:
        db_table = 'contacts'
        verbose_name = 'Contact'
        verbose_name_plural = 'Contacts'
        indexes = [
            models.Index(fields=['group', 'email']),
            models.Index(fields=['group', 'status']),
            models.Index(fields=['group', 'current_score']),
            models.Index(fields=['group', 'last_activity_at']),
            models.Index(fields=['group', 'assigned_to']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'email'],
                name='unique_contact_email_per_group'
            )
        ]
    
    def __str__(self) -> str:
        if self.contact_type == ContactType.INDIVIDUAL:
            name = f"{self.first_name} {self.last_name}".strip()
            if self.company_name:
                return f"{name} ({self.company_name})"
            return name or self.email
        return self.company_name or self.email
    
    @property
    def full_name(self) -> str:
        """Full name for individual contacts."""
        if self.contact_type == ContactType.INDIVIDUAL:
            return f"{self.first_name} {self.last_name}".strip()
        return self.company_name
    
    @property
    def display_name(self) -> str:
        """Display name for UI purposes."""
        return self.full_name or self.email
    
    # FSM transitions for contact status
    @transition(field=status, source=ContactStatus.LEAD, target=ContactStatus.QUALIFIED)
    def qualify(self):
        """Transition from lead to qualified lead."""
        pass
    
    @transition(field=status, source=ContactStatus.QUALIFIED, target=ContactStatus.OPPORTUNITY)
    def convert_to_opportunity(self):
        """Transition from qualified lead to opportunity."""
        pass
    
    @transition(field=status, source=ContactStatus.OPPORTUNITY, target=ContactStatus.CUSTOMER)
    def convert_to_customer(self):
        """Transition from opportunity to customer."""
        pass
    
    @transition(field=status, source='*', target=ContactStatus.INACTIVE)
    def mark_inactive(self):
        """Mark contact as inactive from any status."""
        pass
    
    @transition(field=status, source='*', target=ContactStatus.UNSUBSCRIBED)
    def unsubscribe(self):
        """Mark contact as unsubscribed from any status."""
        self.email_opt_in = False
        self.sms_opt_in = False
    
    def update_last_activity(self, activity_timestamp: datetime = None) -> None:
        """Update the last activity timestamp."""
        self.last_activity_at = activity_timestamp or datetime.now()
        self.save(update_fields=['last_activity_at'])
    
    def calculate_score(self) -> int:
        """
        Calculate lead score based on activities and attributes.
        
        This is a simplified scoring algorithm that can be enhanced
        with more sophisticated rules and machine learning.
        """
        score = 0
        
        # Basic information completeness
        if self.first_name and self.last_name:
            score += 10
        if self.company_name:
            score += 10
        if self.phone_primary:
            score += 5
        if self.job_title:
            score += 5
        
        # Engagement scoring
        activities = self.activities.all()
        email_opens = activities.filter(activity_type=ActivityType.EMAIL_OPENED).count()
        email_clicks = activities.filter(activity_type=ActivityType.EMAIL_CLICKED).count()
        meetings = activities.filter(activity_type=ActivityType.MEETING_COMPLETED).count()
        
        score += min(email_opens * 2, 20)  # Max 20 points for email engagement
        score += min(email_clicks * 5, 25)  # Max 25 points for click engagement
        score += min(meetings * 15, 30)     # Max 30 points for meetings
        
        # Recency boost
        if self.last_activity_at:
            days_since_activity = (datetime.now() - self.last_activity_at).days
            if days_since_activity < 7:
                score += 10
            elif days_since_activity < 30:
                score += 5
        
        return min(score, 100)  # Cap at 100


class ContactPartner(PlatformModel, TimestampedModel, UUIDModel):
    """
    Through model for many-to-many relationship between contacts and development partners.
    
    Allows tracking of relationship metadata and history.
    """
    
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name='partner_relationships',
        help_text="Contact in the relationship"
    )
    partner = models.ForeignKey(
        'assessments.DevelopmentPartner',
        on_delete=models.CASCADE,
        related_name='contact_relationships',
        help_text="Development partner in the relationship"
    )
    relationship_type = models.CharField(
        max_length=20,
        choices=RelationshipType.choices,
        default=RelationshipType.OTHER,
        help_text="Type of relationship between contact and partner"
    )
    start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Start date of the relationship"
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text="End date of the relationship (if applicable)"
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="Whether this is the primary contact for the partner"
    )
    notes = models.TextField(
        blank=True,
        help_text="Notes about this specific relationship"
    )
    
    class Meta:
        db_table = 'contact_partners'
        verbose_name = 'Contact-Partner Relationship'
        verbose_name_plural = 'Contact-Partner Relationships'
        indexes = [
            models.Index(fields=['group', 'contact']),
            models.Index(fields=['group', 'partner']),
            models.Index(fields=['group', 'relationship_type']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'contact', 'partner'],
                name='unique_contact_partner_per_group'
            )
        ]
    
    def __str__(self) -> str:
        return f"{self.contact} -> {self.partner} ({self.get_relationship_type_display()})"


class ContactActivity(PlatformModel, TimestampedModel, UUIDModel):
    """
    Activity log for tracking all interactions and events related to contacts.
    
    Uses generic foreign key to allow activities to be linked to contacts,
    partners, assessments, or any other model.
    """
    
    # Core activity information
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name='activities',
        help_text="Contact this activity relates to"
    )
    activity_type = models.CharField(
        max_length=20,
        choices=ActivityType.choices,
        help_text="Type of activity performed"
    )
    subject = models.CharField(
        max_length=255,
        blank=True,
        help_text="Subject or title of the activity"
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed description of the activity"
    )
    
    # Generic relationship to any model
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Type of the related object"
    )
    object_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of the related object"
    )
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Activity metadata
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contact_activities',
        help_text="User who performed the activity"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional activity metadata (email IDs, URLs, etc.)"
    )
    
    # Outcome tracking
    outcome = models.CharField(
        max_length=100,
        blank=True,
        help_text="Outcome or result of the activity"
    )
    follow_up_required = models.BooleanField(
        default=False,
        help_text="Whether this activity requires follow-up"
    )
    follow_up_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When follow-up is required"
    )
    
    class Meta:
        db_table = 'contact_activities'
        verbose_name = 'Contact Activity'
        verbose_name_plural = 'Contact Activities'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', 'contact', '-created_at']),
            models.Index(fields=['group', 'activity_type', '-created_at']),
            models.Index(fields=['group', 'actor', '-created_at']),
            models.Index(fields=['group', 'follow_up_required', 'follow_up_date']),
        ]
    
    def __str__(self) -> str:
        return f"{self.get_activity_type_display()} - {self.contact} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
    
    def save(self, *args, **kwargs):
        """Override save to update contact's last activity timestamp."""
        super().save(*args, **kwargs)
        
        # Update contact's last activity timestamp
        if self.contact:
            self.contact.update_last_activity(self.created_at)


class ContactList(PlatformModel, TimestampedModel, UUIDModel):
    """
    Contact list/segmentation model for organizing contacts into groups.
    
    Supports both static lists (explicit contact assignment) and dynamic lists
    (based on saved filter criteria).
    """
    
    name = models.CharField(
        max_length=255,
        help_text="Name of the contact list"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of the list purpose and criteria"
    )
    
    # List type and behavior
    is_dynamic = models.BooleanField(
        default=False,
        help_text="Whether this is a dynamic list based on criteria"
    )
    filter_criteria = models.JSONField(
        default=dict,
        blank=True,
        help_text="Saved filter criteria for dynamic lists"
    )
    
    # Static list members
    contacts = models.ManyToManyField(
        Contact,
        blank=True,
        related_name='contact_lists',
        help_text="Contacts in this list (for static lists)"
    )
    
    # List metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_contact_lists',
        help_text="User who created this list"
    )
    is_public = models.BooleanField(
        default=False,
        help_text="Whether this list is visible to other users in the group"
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Tags for organizing lists"
    )
    
    class Meta:
        db_table = 'contact_lists'
        verbose_name = 'Contact List'
        verbose_name_plural = 'Contact Lists'
        indexes = [
            models.Index(fields=['group', 'created_by']),
            models.Index(fields=['group', 'is_dynamic']),
            models.Index(fields=['group', 'is_public']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'name'],
                name='unique_contact_list_name_per_group'
            )
        ]
    
    def __str__(self) -> str:
        list_type = "Dynamic" if self.is_dynamic else "Static"
        return f"{self.name} ({list_type})"
    
    def get_contact_count(self) -> int:
        """Get the current number of contacts in this list."""
        if self.is_dynamic:
            # TODO: Implement dynamic query based on filter_criteria
            # For now, return 0 as placeholder
            return 0
        return self.contacts.count()
    
    def refresh_dynamic_list(self) -> None:
        """Refresh the dynamic list based on current filter criteria."""
        if not self.is_dynamic:
            return
        
        # TODO: Implement dynamic list refresh logic
        # This would query Contact model based on filter_criteria
        # and update the contacts relationship
        pass


# Email Campaign Models

class EmailTemplate(PlatformModel, TimestampedModel, UUIDModel):
    """
    Email template for campaigns.
    
    Supports Jinja2 templating with variable substitution.
    """
    
    class TemplateType(models.TextChoices):
        MARKETING = 'marketing', 'Marketing'
        TRANSACTIONAL = 'transactional', 'Transactional'
        NEWSLETTER = 'newsletter', 'Newsletter'
        ANNOUNCEMENT = 'announcement', 'Announcement'
        FOLLOW_UP = 'follow_up', 'Follow-up'
    
    name = models.CharField(max_length=200, help_text="Internal template name")
    slug = models.SlugField(
        max_length=200,
        unique=True,
        null=True,
        blank=True,
        help_text="Unique identifier for template (used in code)"
    )
    template_type = models.CharField(
        max_length=20,
        choices=TemplateType.choices,
        default=TemplateType.MARKETING
    )
    
    # Email content
    subject = models.CharField(
        max_length=200,
        help_text="Email subject line. Supports Jinja2 variables like {{ first_name }}"
    )
    preheader = models.CharField(
        max_length=200,
        blank=True,
        help_text="Preview text shown in email clients"
    )
    html_content = models.TextField(
        help_text="HTML email content with Jinja2 templating"
    )
    text_content = models.TextField(
        help_text="Plain text version of the email"
    )
    
    # Metadata
    from_name = models.CharField(max_length=100, default="EnterpriseLand")
    from_email = models.EmailField(default="noreply@enterpriseland.com")
    reply_to_email = models.EmailField(blank=True)
    
    # Template variables
    available_variables = models.JSONField(
        default=list,
        blank=True,
        help_text="List of available template variables"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_tested = models.BooleanField(default=False)
    
    # Analytics
    times_used = models.PositiveIntegerField(default=0)
    
    # Tracking
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='created_email_templates'
    )
    
    class Meta:
        db_table = 'email_templates'
        verbose_name = 'Email Template'
        verbose_name_plural = 'Email Templates'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', 'template_type', 'is_active']),
            models.Index(fields=['group', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.template_type})"
    
    def get_preview_data(self):
        """Get sample data for template preview."""
        return {
            'first_name': 'John',
            'last_name': 'Doe',
            'company_name': 'Example Corp',
            'email': 'john.doe@example.com',
            'unsubscribe_url': 'https://example.com/unsubscribe',
            'preferences_url': 'https://example.com/preferences',
            'current_year': datetime.now().year,
        }


class EmailCampaign(PlatformModel, TimestampedModel, UUIDModel):
    """
    Email marketing campaign targeting a list of contacts.
    """
    
    class CampaignStatus(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SCHEDULED = 'scheduled', 'Scheduled'
        SENDING = 'sending', 'Sending'
        SENT = 'sent', 'Sent'
        PAUSED = 'paused', 'Paused'
        CANCELLED = 'cancelled', 'Cancelled'
    
    class SendingStrategy(models.TextChoices):
        IMMEDIATE = 'immediate', 'Send Immediately'
        SCHEDULED = 'scheduled', 'Scheduled'
        DRIP = 'drip', 'Drip Campaign'
        TIMEZONE_OPTIMIZED = 'timezone', 'Timezone Optimized'
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Campaign configuration
    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.PROTECT,
        related_name='campaigns'
    )
    status = models.CharField(
        max_length=20,
        choices=CampaignStatus.choices,
        default=CampaignStatus.DRAFT
    )
    
    # Recipients
    contact_lists = models.ManyToManyField(
        ContactList,
        related_name='email_campaigns',
        blank=True
    )
    excluded_contacts = models.ManyToManyField(
        Contact,
        related_name='excluded_from_campaigns',
        blank=True
    )
    
    # Scheduling
    sending_strategy = models.CharField(
        max_length=20,
        choices=SendingStrategy.choices,
        default=SendingStrategy.IMMEDIATE
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    send_rate_per_hour = models.PositiveIntegerField(
        default=1000,
        help_text="Maximum emails to send per hour"
    )
    
    # Campaign settings
    track_opens = models.BooleanField(default=True)
    track_clicks = models.BooleanField(default=True)
    include_unsubscribe_link = models.BooleanField(default=True)
    
    # A/B Testing
    is_ab_test = models.BooleanField(default=False)
    ab_test_percentage = models.PositiveSmallIntegerField(
        default=10,
        help_text="Percentage of recipients for A/B test"
    )
    variant_templates = models.ManyToManyField(
        EmailTemplate,
        related_name='ab_test_campaigns',
        blank=True
    )
    
    # Analytics (updated by Celery tasks)
    total_recipients = models.PositiveIntegerField(default=0)
    emails_sent = models.PositiveIntegerField(default=0)
    emails_delivered = models.PositiveIntegerField(default=0)
    emails_opened = models.PositiveIntegerField(default=0)
    emails_clicked = models.PositiveIntegerField(default=0)
    emails_bounced = models.PositiveIntegerField(default=0)
    emails_unsubscribed = models.PositiveIntegerField(default=0)
    
    # Tracking
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_campaigns'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_campaigns'
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'email_campaigns'
        verbose_name = 'Email Campaign'
        verbose_name_plural = 'Email Campaigns'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', 'status', 'scheduled_at']),
            models.Index(fields=['group', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
    
    @property
    def open_rate(self):
        """Calculate email open rate."""
        if self.emails_delivered == 0:
            return 0
        return round((self.emails_opened / self.emails_delivered) * 100, 2)
    
    @property
    def click_rate(self):
        """Calculate email click rate."""
        if self.emails_delivered == 0:
            return 0
        return round((self.emails_clicked / self.emails_delivered) * 100, 2)
    
    @property
    def bounce_rate(self):
        """Calculate email bounce rate."""
        if self.emails_sent == 0:
            return 0
        return round((self.emails_bounced / self.emails_sent) * 100, 2)


class EmailMessage(PlatformModel, TimestampedModel, UUIDModel):
    """
    Individual email message sent to a contact as part of a campaign.
    
    Tracks delivery status and engagement metrics.
    """
    
    class MessageStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        QUEUED = 'queued', 'Queued'
        SENT = 'sent', 'Sent'
        DELIVERED = 'delivered', 'Delivered'
        OPENED = 'opened', 'Opened'
        CLICKED = 'clicked', 'Clicked'
        BOUNCED = 'bounced', 'Bounced'
        FAILED = 'failed', 'Failed'
        UNSUBSCRIBED = 'unsubscribed', 'Unsubscribed'
        COMPLAINED = 'complained', 'Complained'
    
    campaign = models.ForeignKey(
        EmailCampaign,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name='email_messages'
    )
    
    # Message details
    template_used = models.ForeignKey(
        EmailTemplate,
        on_delete=models.SET_NULL,
        null=True
    )
    subject = models.CharField(max_length=200)
    from_email = models.EmailField()
    to_email = models.EmailField()
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=MessageStatus.choices,
        default=MessageStatus.PENDING
    )
    
    # Delivery information
    message_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Email service provider message ID"
    )
    queued_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Engagement tracking
    first_opened_at = models.DateTimeField(null=True, blank=True)
    last_opened_at = models.DateTimeField(null=True, blank=True)
    open_count = models.PositiveIntegerField(default=0)
    
    first_clicked_at = models.DateTimeField(null=True, blank=True)
    last_clicked_at = models.DateTimeField(null=True, blank=True)
    click_count = models.PositiveIntegerField(default=0)
    
    # Error tracking
    bounce_type = models.CharField(max_length=50, blank=True)
    bounce_reason = models.TextField(blank=True)
    failed_reason = models.TextField(blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        db_table = 'email_messages'
        verbose_name = 'Email Message'
        verbose_name_plural = 'Email Messages'
        ordering = ['-created_at']
        unique_together = [['campaign', 'contact']]
        indexes = [
            models.Index(fields=['group', 'campaign', 'status']),
            models.Index(fields=['group', 'contact', 'sent_at']),
            models.Index(fields=['group', 'status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Email to {self.to_email} - {self.get_status_display()}"


class EmailEvent(TimestampedModel, UUIDModel):
    """
    Track email events for analytics and debugging.
    
    Records all interactions with email messages.
    Note: Not group-filtered as events are system-wide tracking.
    """
    
    class EventType(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        SENT = 'sent', 'Sent'
        DELIVERED = 'delivered', 'Delivered'
        OPENED = 'opened', 'Opened'
        CLICKED = 'clicked', 'Clicked'
        BOUNCED = 'bounced', 'Bounced'
        FAILED = 'failed', 'Failed'
        UNSUBSCRIBED = 'unsubscribed', 'Unsubscribed'
        COMPLAINED = 'complained', 'Spam Complaint'
    
    message = models.ForeignKey(
        EmailMessage,
        on_delete=models.CASCADE,
        related_name='events'
    )
    event_type = models.CharField(
        max_length=20,
        choices=EventType.choices
    )
    
    # Event details
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Additional data (JSON)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional event-specific data"
    )
    
    # For click events
    link_url = models.URLField(blank=True)
    link_text = models.CharField(max_length=200, blank=True)
    
    class Meta:
        db_table = 'email_events'
        verbose_name = 'Email Event'
        verbose_name_plural = 'Email Events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['message', 'event_type']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.get_event_type_display()} - {self.message.to_email} at {self.timestamp}"


# Import outreach sequence models
from .models_outreach import (
    OutreachSequence,
    SequenceStep,
    SequenceEnrollment,
    SequenceStepExecution,
    SequenceTemplate
)
