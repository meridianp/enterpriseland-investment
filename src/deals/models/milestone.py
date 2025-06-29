"""
Milestone models for tracking key deal events and deadlines.
"""

from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.utils import timezone
from assessments.base_models import GroupFilteredModel, TimestampedModel, UUIDModel
from accounts.models import User


class MilestoneTemplate(GroupFilteredModel, TimestampedModel):
    """
    Templates for common milestones that can be applied to deals.
    """
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    
    # Applicability
    deal_types = models.ManyToManyField(
        'DealType',
        blank=True,
        help_text="Deal types this template applies to"
    )
    stage = models.ForeignKey(
        'DealStage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Stage when this milestone typically occurs"
    )
    
    # Timing
    days_from_stage_start = models.IntegerField(
        null=True,
        blank=True,
        help_text="Days after stage start (negative for before)"
    )
    is_blocking = models.BooleanField(
        default=False,
        help_text="Must be completed before stage progression"
    )
    
    # Configuration
    required_documents = models.JSONField(
        default=list,
        blank=True,
        help_text="Documents required for milestone"
    )
    checklist_items = models.JSONField(
        default=list,
        blank=True,
        help_text="Checklist for milestone completion"
    )
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'milestone_templates'
        verbose_name = 'Milestone Template'
        verbose_name_plural = 'Milestone Templates'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class DealMilestone(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Key milestones and deadlines for a deal.
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        OVERDUE = 'overdue', 'Overdue'
        CANCELLED = 'cancelled', 'Cancelled'
    
    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        CRITICAL = 'critical', 'Critical'
    
    deal = models.ForeignKey(
        'Deal',
        on_delete=models.CASCADE,
        related_name='milestones'
    )
    template = models.ForeignKey(
        MilestoneTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Template this was created from"
    )
    
    # Basic information
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM
    )
    
    # Timing
    due_date = models.DateField()
    reminder_date = models.DateField(
        null=True,
        blank=True,
        help_text="When to send reminder"
    )
    completed_date = models.DateField(
        null=True,
        blank=True
    )
    
    # Assignment
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_milestones'
    )
    
    # Stage relationship
    stage = models.ForeignKey(
        'DealStage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Related deal stage"
    )
    is_blocking = models.BooleanField(
        default=False,
        help_text="Blocks stage progression if not completed"
    )
    
    # Progress tracking
    progress_percentage = models.PositiveIntegerField(
        default=0,
        validators=[MaxValueValidator(100)]
    )
    checklist_items = models.JSONField(
        default=list,
        blank=True,
        help_text="Checklist for completion"
    )
    completed_items = models.JSONField(
        default=list,
        blank=True,
        help_text="Completed checklist items"
    )
    
    # Documentation
    required_documents = models.JSONField(
        default=list,
        blank=True
    )
    attached_documents = models.ManyToManyField(
        'files.FileAttachment',
        blank=True,
        related_name='milestone_documents'
    )
    
    # Completion details
    completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_milestones'
    )
    completion_notes = models.TextField(blank=True)
    
    # Notifications
    reminder_sent = models.BooleanField(default=False)
    overdue_notification_sent = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'deal_milestones'
        verbose_name = 'Deal Milestone'
        verbose_name_plural = 'Deal Milestones'
        ordering = ['deal', 'due_date']
        indexes = [
            models.Index(fields=['deal', 'status']),
            models.Index(fields=['due_date', 'status']),
            models.Index(fields=['assigned_to', 'status']),
        ]
    
    def __str__(self):
        return f"{self.deal.code} - {self.name}"
    
    def clean(self):
        """Validate milestone dates"""
        if self.completed_date and self.status != self.Status.COMPLETED:
            raise ValidationError(
                "Completed date can only be set for completed milestones"
            )
        
        if self.reminder_date and self.reminder_date >= self.due_date:
            raise ValidationError(
                "Reminder date must be before due date"
            )
    
    @property
    def is_overdue(self):
        """Check if milestone is overdue"""
        if self.status in [self.Status.COMPLETED, self.Status.CANCELLED]:
            return False
        return timezone.now().date() > self.due_date
    
    @property
    def days_until_due(self):
        """Calculate days until due date"""
        if self.status == self.Status.COMPLETED:
            return None
        delta = self.due_date - timezone.now().date()
        return delta.days
    
    @property
    def checklist_progress(self):
        """Calculate checklist completion percentage"""
        if not self.checklist_items:
            return 100
        
        total = len(self.checklist_items)
        completed = len(self.completed_items)
        return int((completed / total) * 100)
    
    def complete(self, completed_by=None, notes=''):
        """Mark milestone as completed"""
        self.status = self.Status.COMPLETED
        self.completed_date = timezone.now().date()
        self.completed_by = completed_by
        self.completion_notes = notes
        self.progress_percentage = 100
        self.save()
        
        # Create activity
        from .activity import DealActivity, ActivityType
        DealActivity.objects.create(
            deal=self.deal,
            activity_type=ActivityType.MILESTONE_COMPLETED,
            performed_by=completed_by,
            description=f"Completed milestone: {self.name}",
            metadata={
                'milestone_id': str(self.id),
                'milestone_name': self.name,
                'days_to_complete': (self.completed_date - self.created_at.date()).days
            }
        )
    
    def update_status(self):
        """Update status based on current state"""
        if self.status in [self.Status.COMPLETED, self.Status.CANCELLED]:
            return
        
        if self.is_overdue:
            self.status = self.Status.OVERDUE
            # Send overdue notification if not already sent
            if not self.overdue_notification_sent:
                self._send_overdue_notification()
                self.overdue_notification_sent = True
        elif self.progress_percentage > 0:
            self.status = self.Status.IN_PROGRESS
        else:
            self.status = self.Status.PENDING
        
        self.save()
    
    def _send_overdue_notification(self):
        """Send overdue notification"""
        # This would integrate with the notification system
        pass