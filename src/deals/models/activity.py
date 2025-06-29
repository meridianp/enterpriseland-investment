"""
Activity tracking models for deal timeline and audit trail.
"""

from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from assessments.base_models import GroupFilteredModel, TimestampedModel, UUIDModel
from accounts.models import User


class ActivityType(models.TextChoices):
    """Types of activities that can occur on a deal"""
    # Deal lifecycle
    DEAL_CREATED = 'deal_created', 'Deal Created'
    STAGE_CHANGED = 'stage_changed', 'Stage Changed'
    STATUS_UPDATED = 'status_updated', 'Status Updated'
    DEAL_COMPLETED = 'deal_completed', 'Deal Completed'
    DEAL_REJECTED = 'deal_rejected', 'Deal Rejected'
    
    # Team activities
    TEAM_MEMBER_ADDED = 'team_member_added', 'Team Member Added'
    TEAM_MEMBER_REMOVED = 'team_member_removed', 'Team Member Removed'
    ROLE_CHANGED = 'role_changed', 'Role Changed'
    TEAM_CHANGE = 'team_change', 'Team Change'
    
    # Milestone activities
    MILESTONE_CREATED = 'milestone_created', 'Milestone Created'
    MILESTONE_UPDATED = 'milestone_updated', 'Milestone Updated'
    MILESTONE_COMPLETED = 'milestone_completed', 'Milestone Completed'
    MILESTONE_OVERDUE = 'milestone_overdue', 'Milestone Overdue'
    
    # Document activities
    DOCUMENT_UPLOADED = 'document_uploaded', 'Document Uploaded'
    DOCUMENT_REVIEWED = 'document_reviewed', 'Document Reviewed'
    DOCUMENT_APPROVED = 'document_approved', 'Document Approved'
    DOCUMENT_REJECTED = 'document_rejected', 'Document Rejected'
    
    # Financial activities
    VALUATION_UPDATED = 'valuation_updated', 'Valuation Updated'
    TERMS_UPDATED = 'terms_updated', 'Terms Updated'
    FINANCIAL_MODEL_UPDATED = 'financial_model_updated', 'Financial Model Updated'
    
    # Communication
    NOTE_ADDED = 'note_added', 'Note Added'
    EMAIL_SENT = 'email_sent', 'Email Sent'
    MEETING_SCHEDULED = 'meeting_scheduled', 'Meeting Scheduled'
    MEETING_COMPLETED = 'meeting_completed', 'Meeting Completed'
    CALL_LOGGED = 'call_logged', 'Call Logged'
    
    # Review and approval
    REVIEW_REQUESTED = 'review_requested', 'Review Requested'
    REVIEW_COMPLETED = 'review_completed', 'Review Completed'
    APPROVAL_REQUESTED = 'approval_requested', 'Approval Requested'
    APPROVAL_GRANTED = 'approval_granted', 'Approval Granted'
    APPROVAL_DENIED = 'approval_denied', 'Approval Denied'
    
    # Other
    CUSTOM = 'custom', 'Custom Activity'
    SYSTEM = 'system', 'System Activity'


class DealActivity(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Comprehensive activity log for all deal-related actions.
    """
    deal = models.ForeignKey(
        'Deal',
        on_delete=models.CASCADE,
        related_name='activities'
    )
    activity_type = models.CharField(
        max_length=50,
        choices=ActivityType.choices
    )
    
    # Who performed the activity
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deal_activities'
    )
    
    # What happened
    title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Activity title (auto-generated if blank)"
    )
    description = models.TextField()
    
    # Related object (generic relation)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    object_id = models.UUIDField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Additional context
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional activity data"
    )
    
    # Importance
    is_important = models.BooleanField(
        default=False,
        help_text="Mark important activities"
    )
    is_private = models.BooleanField(
        default=False,
        help_text="Only visible to specific roles"
    )
    
    # Notifications
    notify_team = models.BooleanField(
        default=True,
        help_text="Notify deal team members"
    )
    notified_users = models.ManyToManyField(
        User,
        blank=True,
        related_name='activity_notifications'
    )
    
    class Meta:
        db_table = 'deal_activities'
        verbose_name = 'Deal Activity'
        verbose_name_plural = 'Deal Activities'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['deal', '-created_at']),
            models.Index(fields=['activity_type', '-created_at']),
            models.Index(fields=['performed_by', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.deal.code} - {self.get_activity_type_display()}"
    
    def save(self, *args, **kwargs):
        # Auto-generate title if not provided
        if not self.title:
            self.title = self._generate_title()
        
        # Set is_important for certain activity types
        if self.activity_type in [
            ActivityType.DEAL_COMPLETED,
            ActivityType.DEAL_REJECTED,
            ActivityType.STAGE_CHANGED,
            ActivityType.APPROVAL_GRANTED,
            ActivityType.APPROVAL_DENIED
        ]:
            self.is_important = True
        
        super().save(*args, **kwargs)
        
        # Send notifications after save
        if self.notify_team and self.pk:
            self._notify_team_members()
    
    def _generate_title(self):
        """Generate title based on activity type"""
        titles = {
            ActivityType.DEAL_CREATED: "Deal created",
            ActivityType.STAGE_CHANGED: f"Stage changed to {self.metadata.get('to_stage', 'unknown')}",
            ActivityType.TEAM_MEMBER_ADDED: f"Added {self.metadata.get('member_name', 'team member')}",
            ActivityType.MILESTONE_COMPLETED: f"Completed: {self.metadata.get('milestone_name', 'milestone')}",
            ActivityType.DOCUMENT_UPLOADED: f"Uploaded: {self.metadata.get('document_name', 'document')}",
            ActivityType.VALUATION_UPDATED: "Valuation updated",
            ActivityType.NOTE_ADDED: "Note added",
            ActivityType.MEETING_SCHEDULED: f"Meeting scheduled for {self.metadata.get('meeting_date', 'TBD')}",
        }
        return titles.get(self.activity_type, self.get_activity_type_display())
    
    def _notify_team_members(self):
        """Send notifications to relevant team members"""
        from ..services.notifications import send_deal_activity_notification
        
        # Get active team members
        team_members = self.deal.team_members.filter(
            removed_at__isnull=True,
            notify_on_updates=True
        ).exclude(user=self.performed_by)
        
        # Send notifications based on activity type
        if self.activity_type == ActivityType.STAGE_CHANGED:
            # Notify all team members for stage changes
            recipients = team_members.values_list('user', flat=True)
        elif self.is_important:
            # Notify core team and leads for important activities
            recipients = team_members.filter(
                involvement_level__in=['lead', 'core']
            ).values_list('user', flat=True)
        else:
            # Notify only assigned team members for regular activities
            recipients = team_members.filter(
                user=self.metadata.get('assigned_to')
            ).values_list('user', flat=True) if self.metadata.get('assigned_to') else []
        
        for user_id in recipients:
            send_deal_activity_notification.delay(
                activity_id=str(self.id),
                user_id=str(user_id)
            )
            self.notified_users.add(user_id)