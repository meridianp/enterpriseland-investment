"""
Deal collaboration models for team communication and discussion.
"""

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from assessments.base_models import GroupFilteredModel, TimestampedModel, UUIDModel
from accounts.models import User


class DealComment(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Comments on deals or deal-related objects.
    
    Supports threaded discussions and @mentions.
    """
    
    class CommentType(models.TextChoices):
        GENERAL = 'general', 'General Comment'
        QUESTION = 'question', 'Question'
        CONCERN = 'concern', 'Concern'
        APPROVAL = 'approval', 'Approval'
        REJECTION = 'rejection', 'Rejection'
        UPDATE = 'update', 'Status Update'
    
    deal = models.ForeignKey(
        'Deal',
        on_delete=models.CASCADE,
        related_name='comments'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='deal_comments'
    )
    
    # Generic relation to allow comments on any deal object
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Type of object this comment is attached to"
    )
    object_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of the object this comment is attached to"
    )
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Comment content
    comment_type = models.CharField(
        max_length=20,
        choices=CommentType.choices,
        default=CommentType.GENERAL
    )
    content = models.TextField(help_text="Comment content with markdown support")
    
    # Threading support
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )
    
    # Status and visibility
    is_private = models.BooleanField(
        default=False,
        help_text="Only visible to specific team members"
    )
    is_resolved = models.BooleanField(
        default=False,
        help_text="For questions/concerns - marked as resolved"
    )
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_comments'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Mentions and notifications
    mentioned_users = models.ManyToManyField(
        User,
        blank=True,
        related_name='mentioned_in_comments',
        help_text="Users mentioned in this comment"
    )
    
    # Metadata
    edited_at = models.DateTimeField(null=True, blank=True)
    edit_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'deal_comments'
        verbose_name = 'Deal Comment'
        verbose_name_plural = 'Deal Comments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['deal', '-created_at']),
            models.Index(fields=['author', '-created_at']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['parent', '-created_at']),
        ]
    
    def __str__(self):
        return f"Comment by {self.author.get_full_name()} on {self.deal.code}"
    
    @property
    def is_thread_starter(self):
        """Check if this is a top-level comment"""
        return self.parent is None
    
    @property
    def reply_count(self):
        """Count of replies to this comment"""
        return self.replies.count()
    
    def get_thread_root(self):
        """Get the root comment of this thread"""
        if self.parent:
            return self.parent.get_thread_root()
        return self
    
    def extract_mentions(self):
        """Extract @mentions from comment content"""
        import re
        mention_pattern = r'@(\w+(?:\.\w+)*)'
        mentions = re.findall(mention_pattern, self.content)
        
        # Find users by username or email
        mentioned_users = []
        for mention in mentions:
            try:
                user = User.objects.get(
                    models.Q(username__iexact=mention) |
                    models.Q(email__iexact=mention)
                )
                mentioned_users.append(user)
            except User.DoesNotExist:
                continue
        
        return mentioned_users
    
    def resolve(self, resolved_by):
        """Mark comment as resolved"""
        from django.utils import timezone
        
        self.is_resolved = True
        self.resolved_by = resolved_by
        self.resolved_at = timezone.now()
        self.save(update_fields=['is_resolved', 'resolved_by', 'resolved_at'])
    
    def save(self, *args, **kwargs):
        """Override save to handle mentions and notifications"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            # Extract and save mentions
            mentioned_users = self.extract_mentions()
            self.mentioned_users.set(mentioned_users)
            
            # Create notifications
            self._create_notifications(mentioned_users)
    
    def _create_notifications(self, mentioned_users):
        """Create notifications for mentions and deal team"""
        from .activity import DealActivity
        
        # Create activity for the comment
        DealActivity.objects.create(
            deal=self.deal,
            activity_type='comment_added',
            performed_by=self.author,
            description=f"Added comment: {self.content[:100]}...",
            object_id=self.id,
            content_type=ContentType.objects.get_for_model(self),
            metadata={
                'comment_type': self.comment_type,
                'mentioned_count': len(mentioned_users),
                'is_reply': self.parent is not None
            },
            group=self.group
        )


class DealDiscussion(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Structured discussions around specific deal topics.
    
    Groups related comments into focused discussions.
    """
    
    class DiscussionStatus(models.TextChoices):
        ACTIVE = 'active', 'Active'
        RESOLVED = 'resolved', 'Resolved'
        ARCHIVED = 'archived', 'Archived'
        ESCALATED = 'escalated', 'Escalated'
    
    class DiscussionType(models.TextChoices):
        GENERAL = 'general', 'General Discussion'
        VALUATION = 'valuation', 'Valuation Discussion'
        TERMS = 'terms', 'Terms Discussion'
        DILIGENCE = 'diligence', 'Due Diligence'
        RISK = 'risk', 'Risk Assessment'
        DECISION = 'decision', 'Decision Required'
    
    deal = models.ForeignKey(
        'Deal',
        on_delete=models.CASCADE,
        related_name='discussions'
    )
    
    # Discussion details
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    discussion_type = models.CharField(
        max_length=20,
        choices=DiscussionType.choices,
        default=DiscussionType.GENERAL
    )
    status = models.CharField(
        max_length=20,
        choices=DiscussionStatus.choices,
        default=DiscussionStatus.ACTIVE
    )
    
    # Ownership and participants
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_discussions'
    )
    participants = models.ManyToManyField(
        User,
        blank=True,
        related_name='deal_discussions',
        help_text="Users participating in this discussion"
    )
    
    # Lifecycle tracking
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_discussions'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_summary = models.TextField(blank=True)
    
    # Related objects
    related_stage = models.ForeignKey(
        'DealStage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='discussions'
    )
    related_milestone = models.ForeignKey(
        'DealMilestone',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='discussions'
    )
    
    # Metadata
    priority = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('urgent', 'Urgent'),
        ],
        default='medium'
    )
    due_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this discussion needs resolution"
    )
    
    class Meta:
        db_table = 'deal_discussions'
        verbose_name = 'Deal Discussion'
        verbose_name_plural = 'Deal Discussions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['deal', 'status']),
            models.Index(fields=['deal', '-created_at']),
            models.Index(fields=['discussion_type', 'status']),
            models.Index(fields=['due_date']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.deal.code}"
    
    @property
    def comment_count(self):
        """Total comments in this discussion"""
        return DealComment.objects.filter(
            deal=self.deal,
            content_type=ContentType.objects.get_for_model(self),
            object_id=self.id
        ).count()
    
    @property
    def is_overdue(self):
        """Check if discussion is past due date"""
        if not self.due_date:
            return False
        from django.utils import timezone
        return timezone.now() > self.due_date and self.status == self.DiscussionStatus.ACTIVE
    
    def add_participant(self, user):
        """Add a user to the discussion"""
        self.participants.add(user)
        
        # Create activity
        from .activity import DealActivity
        DealActivity.objects.create(
            deal=self.deal,
            activity_type='discussion_participant_added',
            performed_by=user,
            description=f"Joined discussion: {self.title}",
            metadata={'discussion_id': str(self.id)},
            group=self.group
        )
    
    def resolve(self, resolved_by, summary=""):
        """Mark discussion as resolved"""
        from django.utils import timezone
        
        self.status = self.DiscussionStatus.RESOLVED
        self.resolved_by = resolved_by
        self.resolved_at = timezone.now()
        self.resolution_summary = summary
        self.save()
        
        # Create activity
        from .activity import DealActivity
        DealActivity.objects.create(
            deal=self.deal,
            activity_type='discussion_resolved',
            performed_by=resolved_by,
            description=f"Resolved discussion: {self.title}",
            metadata={
                'discussion_id': str(self.id),
                'summary': summary
            },
            group=self.group
        )


class DealNotification(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Real-time notifications for deal team members.
    """
    
    class NotificationType(models.TextChoices):
        COMMENT_MENTION = 'comment_mention', 'Mentioned in Comment'
        COMMENT_REPLY = 'comment_reply', 'Reply to Comment'
        DISCUSSION_INVITE = 'discussion_invite', 'Discussion Invitation'
        MILESTONE_DUE = 'milestone_due', 'Milestone Due'
        MILESTONE_OVERDUE = 'milestone_overdue', 'Milestone Overdue'
        STAGE_CHANGE = 'stage_change', 'Stage Changed'
        TEAM_ASSIGNMENT = 'team_assignment', 'Team Assignment'
        APPROVAL_REQUEST = 'approval_request', 'Approval Required'
        DEAL_UPDATE = 'deal_update', 'Deal Updated'
    
    deal = models.ForeignKey(
        'Deal',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='deal_notifications'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sent_deal_notifications'
    )
    
    # Notification content
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Related object
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.UUIDField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Status tracking
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_dismissed = models.BooleanField(default=False)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    
    # Action tracking
    action_url = models.CharField(max_length=500, blank=True)
    action_text = models.CharField(max_length=100, blank=True)
    
    class Meta:
        db_table = 'deal_notifications'
        verbose_name = 'Deal Notification'
        verbose_name_plural = 'Deal Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
            models.Index(fields=['deal', '-created_at']),
            models.Index(fields=['notification_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.recipient.get_full_name()}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            from django.utils import timezone
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def dismiss(self):
        """Dismiss notification"""
        if not self.is_dismissed:
            from django.utils import timezone
            self.is_dismissed = True
            self.dismissed_at = timezone.now()
            self.save(update_fields=['is_dismissed', 'dismissed_at'])
    
    @classmethod
    def create_mention_notification(cls, comment, mentioned_user):
        """Create notification for @mention in comment"""
        return cls.objects.create(
            deal=comment.deal,
            recipient=mentioned_user,
            sender=comment.author,
            notification_type=cls.NotificationType.COMMENT_MENTION,
            title=f"You were mentioned in a comment",
            message=f"{comment.author.get_full_name()} mentioned you: {comment.content[:100]}...",
            content_object=comment,
            action_url=f"/deals/{comment.deal.id}/comments/{comment.id}",
            action_text="View Comment",
            group=comment.group
        )
    
    @classmethod
    def create_stage_change_notification(cls, deal, new_stage, changed_by, team_members):
        """Create notifications for stage changes"""
        notifications = []
        for member in team_members:
            if member.user != changed_by and member.notify_on_stage_change:
                notification = cls.objects.create(
                    deal=deal,
                    recipient=member.user,
                    sender=changed_by,
                    notification_type=cls.NotificationType.STAGE_CHANGE,
                    title=f"Deal moved to {new_stage.name}",
                    message=f"{changed_by.get_full_name()} moved {deal.name} to {new_stage.name}",
                    action_url=f"/deals/{deal.id}",
                    action_text="View Deal",
                    group=deal.group
                )
                notifications.append(notification)
        return notifications