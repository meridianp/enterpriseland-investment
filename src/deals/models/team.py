"""
Deal team models for managing deal participants and roles.
"""

from django.db import models
from django.core.exceptions import ValidationError
from assessments.base_models import GroupFilteredModel, TimestampedModel, UUIDModel
from accounts.models import User


class DealRole(GroupFilteredModel, TimestampedModel):
    """
    Predefined roles for deal team members.
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    
    # Permissions for this role
    permissions = models.JSONField(
        default=list,
        help_text="List of permission codes"
    )
    
    # Role configuration
    is_required = models.BooleanField(
        default=False,
        help_text="Is this role required for all deals?"
    )
    max_members = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum members with this role per deal"
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'deal_roles'
        verbose_name = 'Deal Role'
        verbose_name_plural = 'Deal Roles'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class DealTeamMember(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Team members assigned to a deal with specific roles.
    """
    
    class InvolvementLevel(models.TextChoices):
        LEAD = 'lead', 'Lead'
        CORE = 'core', 'Core Team'
        SUPPORT = 'support', 'Support'
        REVIEWER = 'reviewer', 'Reviewer'
        OBSERVER = 'observer', 'Observer'
    
    deal = models.ForeignKey(
        'Deal',
        on_delete=models.CASCADE,
        related_name='team_members'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='deal_assignments'
    )
    role = models.ForeignKey(
        DealRole,
        on_delete=models.PROTECT,
        related_name='assignments'
    )
    involvement_level = models.CharField(
        max_length=20,
        choices=InvolvementLevel.choices,
        default=InvolvementLevel.CORE
    )
    
    # Assignment details
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='deal_assignments_made'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When member was removed from deal"
    )
    
    # Responsibilities
    responsibilities = models.TextField(
        blank=True,
        help_text="Specific responsibilities for this deal"
    )
    
    # Time allocation
    allocation_percentage = models.PositiveIntegerField(
        default=100,
        help_text="Percentage of time allocated to this deal"
    )
    
    # Access control
    can_edit = models.BooleanField(
        default=True,
        help_text="Can edit deal information"
    )
    can_approve = models.BooleanField(
        default=False,
        help_text="Can approve stage transitions"
    )
    can_view_confidential = models.BooleanField(
        default=True,
        help_text="Can view confidential information"
    )
    
    # Notifications
    notify_on_updates = models.BooleanField(
        default=True,
        help_text="Receive notifications for deal updates"
    )
    notify_on_stage_change = models.BooleanField(
        default=True,
        help_text="Receive notifications for stage changes"
    )
    
    # Performance tracking
    tasks_assigned = models.PositiveIntegerField(default=0)
    tasks_completed = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'deal_team_members'
        verbose_name = 'Deal Team Member'
        verbose_name_plural = 'Deal Team Members'
        ordering = ['deal', 'involvement_level', 'role']
        unique_together = [['deal', 'user', 'role']]
        indexes = [
            models.Index(fields=['deal', 'user']),
            models.Index(fields=['user', 'removed_at']),
        ]
    
    def __str__(self):
        return f"{self.deal.code} - {self.user.get_full_name()} ({self.role.name})"
    
    def clean(self):
        """Validate team member assignment"""
        # Check if role has max members limit
        if self.role.max_members:
            existing_count = DealTeamMember.objects.filter(
                deal=self.deal,
                role=self.role,
                removed_at__isnull=True
            ).exclude(pk=self.pk).count()
            
            if existing_count >= self.role.max_members:
                raise ValidationError(
                    f"Maximum {self.role.max_members} {self.role.name}(s) "
                    f"allowed per deal"
                )
        
        # Validate allocation percentage
        if self.allocation_percentage > 100:
            raise ValidationError("Allocation percentage cannot exceed 100%")
    
    @property
    def is_active(self):
        """Check if member is currently active on the deal"""
        return self.removed_at is None
    
    @property
    def days_on_deal(self):
        """Calculate days member has been on the deal"""
        if self.removed_at:
            duration = self.removed_at - self.assigned_at
        else:
            from django.utils import timezone
            duration = timezone.now() - self.assigned_at
        return duration.days
    
    def has_permission(self, permission_code):
        """Check if team member has specific permission"""
        # Check role permissions
        if permission_code in self.role.permissions:
            return True
        
        # Check individual access flags
        permission_map = {
            'edit_deal': self.can_edit,
            'approve_documents': self.can_approve,
            'view_deal': True,  # All team members can view
            'view_confidential': self.can_view_confidential,
        }
        
        return permission_map.get(permission_code, False)
    
    def remove_from_deal(self, removed_by=None):
        """Remove member from deal team"""
        from django.utils import timezone
        self.removed_at = timezone.now()
        self.save()
        
        # Create activity log
        from .activity import DealActivity
        DealActivity.objects.create(
            deal=self.deal,
            activity_type='team_change',
            performed_by=removed_by,
            description=f"Removed {self.user.get_full_name()} from deal team",
            metadata={
                'member_id': str(self.id),
                'user_id': str(self.user.id),
                'role': self.role.code
            },
            group=self.group
        )