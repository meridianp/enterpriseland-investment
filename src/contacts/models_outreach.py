"""
Outreach sequence models for automated multi-step email campaigns.

This module provides sophisticated outreach automation with:
- Multi-step email sequences
- Conditional logic and branching
- A/B testing support
- Performance tracking
- Integration with CRM data
"""

import uuid
from datetime import timedelta
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator, MaxValueValidator
from django_fsm import FSMField, transition

from ..assessments.base_models import GroupFilteredModel, TimestampedModel, UUIDModel
from accounts.models import User
from .models import Contact, ContactList, EmailTemplate


class OutreachSequence(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Automated email sequence with multiple steps and conditional logic.
    
    Supports sophisticated outreach campaigns with:
    - Multiple email steps with delays
    - Conditional branching based on recipient behavior
    - A/B testing of content and timing
    - Integration with lead scoring
    """
    
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        COMPLETED = 'completed', 'Completed'
        ARCHIVED = 'archived', 'Archived'
    
    class TriggerType(models.TextChoices):
        MANUAL = 'manual', 'Manual Entry'
        LEAD_CREATED = 'lead_created', 'Lead Created'
        LEAD_SCORED = 'lead_scored', 'Lead Score Changed'
        TAG_ADDED = 'tag_added', 'Tag Added'
        FORM_SUBMITTED = 'form_submitted', 'Form Submitted'
        CUSTOM_EVENT = 'custom_event', 'Custom Event'
    
    # Basic info
    name = models.CharField(max_length=200, help_text="Internal name for the sequence")
    description = models.TextField(blank=True)
    
    # Configuration
    status = FSMField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        protected=True
    )
    trigger_type = models.CharField(
        max_length=20,
        choices=TriggerType.choices,
        default=TriggerType.MANUAL
    )
    trigger_conditions = models.JSONField(
        default=dict,
        blank=True,
        help_text="Conditions for automatic triggering"
    )
    
    # Settings
    skip_weekends = models.BooleanField(
        default=True,
        help_text="Skip sending emails on weekends"
    )
    timezone_optimized = models.BooleanField(
        default=True,
        help_text="Send emails at optimal time for recipient timezone"
    )
    optimal_send_hour = models.IntegerField(
        default=10,
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        help_text="Hour of day to send emails (in recipient timezone)"
    )
    
    # Exit conditions
    exit_on_reply = models.BooleanField(
        default=True,
        help_text="Stop sequence if recipient replies"
    )
    exit_on_click = models.BooleanField(
        default=False,
        help_text="Stop sequence if recipient clicks any link"
    )
    exit_on_conversion = models.BooleanField(
        default=True,
        help_text="Stop sequence if recipient converts"
    )
    exit_tags = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
        help_text="Exit sequence if contact has any of these tags"
    )
    
    # Goals and tracking
    goal_description = models.TextField(
        blank=True,
        help_text="What is this sequence trying to achieve?"
    )
    conversion_url_pattern = models.CharField(
        max_length=500,
        blank=True,
        help_text="URL pattern to track conversions (regex supported)"
    )
    
    # Ownership
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_sequences'
    )
    
    # Analytics
    total_enrolled = models.PositiveIntegerField(default=0)
    total_completed = models.PositiveIntegerField(default=0)
    total_converted = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'outreach_sequences'
        verbose_name = 'Outreach Sequence'
        verbose_name_plural = 'Outreach Sequences'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', 'status']),
            models.Index(fields=['group', 'trigger_type']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
    
    @transition(field=status, source=Status.DRAFT, target=Status.ACTIVE)
    def activate(self):
        """Activate the sequence."""
        pass
    
    @transition(field=status, source=Status.ACTIVE, target=Status.PAUSED)
    def pause(self):
        """Pause the sequence."""
        pass
    
    @transition(field=status, source=Status.PAUSED, target=Status.ACTIVE)
    def resume(self):
        """Resume the sequence."""
        pass
    
    @transition(field=status, source=[Status.ACTIVE, Status.PAUSED], target=Status.COMPLETED)
    def complete(self):
        """Mark sequence as completed."""
        pass
    
    @transition(field=status, source='*', target=Status.ARCHIVED)
    def archive(self):
        """Archive the sequence."""
        pass


class SequenceStep(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Individual step in an outreach sequence.
    
    Each step represents an email to be sent with conditions and timing.
    """
    
    class StepType(models.TextChoices):
        EMAIL = 'email', 'Send Email'
        WAIT = 'wait', 'Wait Period'
        CONDITION = 'condition', 'Check Condition'
        ACTION = 'action', 'Perform Action'
        AB_TEST = 'ab_test', 'A/B Test'
    
    class DayType(models.TextChoices):
        CALENDAR = 'calendar', 'Calendar Days'
        BUSINESS = 'business', 'Business Days'
    
    sequence = models.ForeignKey(
        OutreachSequence,
        on_delete=models.CASCADE,
        related_name='steps'
    )
    
    # Step configuration
    step_type = models.CharField(
        max_length=20,
        choices=StepType.choices,
        default=StepType.EMAIL
    )
    order = models.PositiveIntegerField(default=0)
    name = models.CharField(max_length=200)
    
    # Timing
    delay_days = models.PositiveIntegerField(
        default=0,
        help_text="Days to wait after previous step"
    )
    delay_hours = models.PositiveIntegerField(
        default=0,
        validators=[MaxValueValidator(23)],
        help_text="Additional hours to wait"
    )
    day_type = models.CharField(
        max_length=20,
        choices=DayType.choices,
        default=DayType.BUSINESS
    )
    
    # Email content (for EMAIL steps)
    email_template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sequence_steps'
    )
    email_subject = models.CharField(
        max_length=500,
        blank=True,
        help_text="Override template subject (supports variables)"
    )
    
    # Conditions
    condition_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Type of condition to check"
    )
    condition_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Condition configuration"
    )
    
    # Actions
    action_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Type of action to perform"
    )
    action_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Action configuration"
    )
    
    # A/B Testing
    is_variant = models.BooleanField(default=False)
    variant_group = models.CharField(
        max_length=50,
        blank=True,
        help_text="Group identifier for A/B test variants"
    )
    variant_percentage = models.IntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of recipients for this variant"
    )
    
    # Analytics
    total_sent = models.PositiveIntegerField(default=0)
    total_opened = models.PositiveIntegerField(default=0)
    total_clicked = models.PositiveIntegerField(default=0)
    total_replied = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'sequence_steps'
        verbose_name = 'Sequence Step'
        verbose_name_plural = 'Sequence Steps'
        ordering = ['sequence', 'order']
        unique_together = [['sequence', 'order']]
        indexes = [
            models.Index(fields=['group', 'sequence', 'order']),
        ]
    
    def __str__(self):
        return f"{self.sequence.name} - Step {self.order}: {self.name}"
    
    def get_total_delay_hours(self):
        """Calculate total delay in hours."""
        if self.day_type == self.DayType.BUSINESS:
            # Approximate business days (excluding weekends)
            total_days = self.delay_days * 7 / 5
        else:
            total_days = self.delay_days
        
        return (total_days * 24) + self.delay_hours


class SequenceEnrollment(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Track contact enrollment in sequences.
    
    Manages the state of each contact's progress through a sequence.
    """
    
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        COMPLETED = 'completed', 'Completed'
        EXITED = 'exited', 'Exited'
        FAILED = 'failed', 'Failed'
    
    class ExitReason(models.TextChoices):
        COMPLETED = 'completed', 'Sequence Completed'
        REPLIED = 'replied', 'Contact Replied'
        CLICKED = 'clicked', 'Contact Clicked'
        CONVERTED = 'converted', 'Contact Converted'
        UNSUBSCRIBED = 'unsubscribed', 'Contact Unsubscribed'
        MANUAL = 'manual', 'Manually Removed'
        CONDITION_MET = 'condition_met', 'Exit Condition Met'
        ERROR = 'error', 'Error Occurred'
    
    sequence = models.ForeignKey(
        OutreachSequence,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name='sequence_enrollments'
    )
    
    # Status tracking
    status = FSMField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        protected=True
    )
    current_step = models.ForeignKey(
        SequenceStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='current_enrollments'
    )
    current_step_index = models.IntegerField(default=0)
    
    # Scheduling
    next_step_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When to execute next step"
    )
    
    # Exit tracking
    exited_at = models.DateTimeField(null=True, blank=True)
    exit_reason = models.CharField(
        max_length=20,
        choices=ExitReason.choices,
        blank=True
    )
    exit_details = models.TextField(blank=True)
    
    # Conversion tracking
    converted = models.BooleanField(default=False)
    converted_at = models.DateTimeField(null=True, blank=True)
    conversion_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Metadata
    enrollment_context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Context data at time of enrollment"
    )
    custom_variables = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom variables for this enrollment"
    )
    
    # A/B Test assignment
    variant_assignments = models.JSONField(
        default=dict,
        blank=True,
        help_text="A/B test variant assignments"
    )
    
    class Meta:
        db_table = 'sequence_enrollments'
        verbose_name = 'Sequence Enrollment'
        verbose_name_plural = 'Sequence Enrollments'
        ordering = ['-created_at']
        unique_together = [['sequence', 'contact']]
        indexes = [
            models.Index(fields=['group', 'status', 'next_step_at']),
            models.Index(fields=['group', 'sequence', 'status']),
            models.Index(fields=['group', 'contact', 'status']),
        ]
    
    def __str__(self):
        return f"{self.contact.email} in {self.sequence.name} ({self.get_status_display()})"
    
    @transition(field=status, source=Status.ACTIVE, target=Status.PAUSED)
    def pause(self):
        """Pause enrollment."""
        pass
    
    @transition(field=status, source=Status.PAUSED, target=Status.ACTIVE)
    def resume(self):
        """Resume enrollment."""
        pass
    
    @transition(field=status, source=[Status.ACTIVE, Status.PAUSED], target=Status.COMPLETED)
    def complete(self):
        """Mark enrollment as completed."""
        self.exit_reason = self.ExitReason.COMPLETED
        from django.utils import timezone
        self.exited_at = timezone.now()
    
    @transition(field=status, source=[Status.ACTIVE, Status.PAUSED], target=Status.EXITED)
    def exit(self, reason, details=''):
        """Exit enrollment with reason."""
        self.exit_reason = reason
        self.exit_details = details
        from django.utils import timezone
        self.exited_at = timezone.now()


class SequenceStepExecution(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Track execution of individual sequence steps.
    
    Records what happened when each step was executed for each enrollment.
    """
    
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        EXECUTING = 'executing', 'Executing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        SKIPPED = 'skipped', 'Skipped'
    
    enrollment = models.ForeignKey(
        SequenceEnrollment,
        on_delete=models.CASCADE,
        related_name='step_executions'
    )
    step = models.ForeignKey(
        SequenceStep,
        on_delete=models.CASCADE,
        related_name='executions'
    )
    
    # Execution tracking
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED
    )
    scheduled_at = models.DateTimeField()
    executed_at = models.DateTimeField(null=True, blank=True)
    
    # Results
    result = models.JSONField(
        default=dict,
        blank=True,
        help_text="Execution results"
    )
    error_message = models.TextField(blank=True)
    
    # For email steps
    email_message_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of EmailMessage if email was sent"
    )
    
    class Meta:
        db_table = 'sequence_step_executions'
        verbose_name = 'Step Execution'
        verbose_name_plural = 'Step Executions'
        ordering = ['enrollment', 'step__order']
        indexes = [
            models.Index(fields=['group', 'status', 'scheduled_at']),
            models.Index(fields=['enrollment', 'step']),
        ]
    
    def __str__(self):
        return f"{self.enrollment} - {self.step.name} ({self.get_status_display()})"


class SequenceTemplate(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Pre-built sequence templates for common use cases.
    
    Allows sharing and reusing successful sequences.
    """
    
    class Category(models.TextChoices):
        COLD_OUTREACH = 'cold_outreach', 'Cold Outreach'
        LEAD_NURTURE = 'lead_nurture', 'Lead Nurturing'
        ONBOARDING = 'onboarding', 'Onboarding'
        RE_ENGAGEMENT = 're_engagement', 'Re-engagement'
        EVENT_INVITE = 'event_invite', 'Event Invitation'
        FOLLOW_UP = 'follow_up', 'Follow-up'
        CUSTOM = 'custom', 'Custom'
    
    name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.CUSTOM
    )
    
    # Template configuration
    configuration = models.JSONField(
        help_text="Complete sequence configuration"
    )
    
    # Metadata
    is_public = models.BooleanField(
        default=False,
        help_text="Available to all groups"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sequence_templates'
    )
    
    # Usage tracking
    times_used = models.PositiveIntegerField(default=0)
    average_conversion_rate = models.FloatField(
        null=True,
        blank=True,
        help_text="Average conversion rate across all uses"
    )
    
    class Meta:
        db_table = 'sequence_templates'
        verbose_name = 'Sequence Template'
        verbose_name_plural = 'Sequence Templates'
        ordering = ['-times_used', 'name']
        indexes = [
            models.Index(fields=['group', 'category']),
            models.Index(fields=['is_public', 'category']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"