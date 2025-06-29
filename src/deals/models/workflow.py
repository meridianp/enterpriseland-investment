"""
Workflow models for deal progression and stage management.
"""

from django.db import models
from django.contrib.postgres.fields import ArrayField
from assessments.base_models import GroupFilteredModel, TimestampedModel, UUIDModel
from accounts.models import User


class WorkflowTemplate(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Template for deal workflows that can be customized per deal type.
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    deal_type = models.ForeignKey(
        'DealType',
        on_delete=models.CASCADE,
        related_name='workflow_templates'
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Default template for this deal type"
    )
    is_active = models.BooleanField(default=True)
    
    # Configuration
    configuration = models.JSONField(
        default=dict,
        help_text="Workflow configuration and rules"
    )
    
    class Meta:
        db_table = 'workflow_templates'
        verbose_name = 'Workflow Template'
        verbose_name_plural = 'Workflow Templates'
        ordering = ['name']
        unique_together = [['group', 'deal_type', 'is_default']]
    
    def __str__(self):
        return f"{self.name} ({self.deal_type.name})"


class DealStage(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Configurable stages in a deal workflow.
    """
    
    class StageType(models.TextChoices):
        ORIGINATION = 'origination', 'Origination'
        SCREENING = 'screening', 'Screening'
        ANALYSIS = 'analysis', 'Analysis'
        APPROVAL = 'approval', 'Approval'
        EXECUTION = 'execution', 'Execution'
        CLOSING = 'closing', 'Closing'
        POST_CLOSING = 'post_closing', 'Post-Closing'
    
    workflow_template = models.ForeignKey(
        WorkflowTemplate,
        on_delete=models.CASCADE,
        related_name='stages'
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    stage_type = models.CharField(
        max_length=20,
        choices=StageType.choices
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Order in workflow"
    )
    description = models.TextField(blank=True)
    
    # Requirements
    required_documents = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text="Required document types"
    )
    required_approvals = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
        help_text="Required approval roles"
    )
    required_tasks = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text="Tasks that must be completed"
    )
    
    # Timing
    target_duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Target days to complete stage"
    )
    max_duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum days before escalation"
    )
    
    # Permissions
    allowed_roles = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
        help_text="Roles that can work in this stage"
    )
    approval_roles = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
        help_text="Roles that can approve progression"
    )
    
    # Configuration
    entry_criteria = models.JSONField(
        default=dict,
        blank=True,
        help_text="Conditions to enter stage"
    )
    exit_criteria = models.JSONField(
        default=dict,
        blank=True,
        help_text="Conditions to exit stage"
    )
    automation_rules = models.JSONField(
        default=dict,
        blank=True,
        help_text="Automation configuration"
    )
    
    class Meta:
        db_table = 'deal_stages'
        verbose_name = 'Deal Stage'
        verbose_name_plural = 'Deal Stages'
        ordering = ['workflow_template', 'order']
        unique_together = [['workflow_template', 'code']]
    
    def __str__(self):
        return f"{self.workflow_template.name} - {self.name}"


class DealTransition(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Records transitions between deal stages.
    """
    deal = models.ForeignKey(
        'Deal',
        on_delete=models.CASCADE,
        related_name='transitions'
    )
    from_stage = models.ForeignKey(
        DealStage,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='transitions_from'
    )
    to_stage = models.ForeignKey(
        DealStage,
        on_delete=models.PROTECT,
        related_name='transitions_to'
    )
    from_status = models.CharField(
        max_length=20,
        help_text="Deal status before transition"
    )
    to_status = models.CharField(
        max_length=20,
        help_text="Deal status after transition"
    )
    
    # Who and when
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='deal_transitions'
    )
    performed_at = models.DateTimeField(auto_now_add=True)
    
    # Transition details
    reason = models.TextField(
        blank=True,
        help_text="Reason for transition"
    )
    notes = models.TextField(blank=True)
    
    # Validation
    criteria_met = models.JSONField(
        default=dict,
        help_text="Which criteria were met"
    )
    overrides = models.JSONField(
        default=dict,
        blank=True,
        help_text="Any overridden requirements"
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_transitions'
    )
    
    # Duration tracking
    stage_duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Days spent in previous stage"
    )
    
    class Meta:
        db_table = 'deal_transitions'
        verbose_name = 'Deal Transition'
        verbose_name_plural = 'Deal Transitions'
        ordering = ['-performed_at']
        indexes = [
            models.Index(fields=['deal', '-performed_at']),
        ]
    
    def __str__(self):
        return f"{self.deal.code}: {self.from_status} → {self.to_status}"
    
    def save(self, *args, **kwargs):
        # Calculate stage duration if from_stage exists
        if self.from_stage and self.deal.stage_entered_at:
            duration = self.performed_at - self.deal.stage_entered_at
            self.stage_duration_days = duration.days
        
        super().save(*args, **kwargs)