"""
Investment Committee (IC) pack automation models.

Provides templates, automated generation, approval workflows, and distribution
for IC packs with version control and audit trails.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator, MaxValueValidator
from django_fsm import FSMField, transition

from assessments.base_models import GroupFilteredModel, TimestampedModel, UUIDModel
from accounts.models import User
from files.models import FileAttachment


class ICPackStatus(models.TextChoices):
    """Status options for IC pack lifecycle."""
    DRAFT = 'draft', 'Draft'
    READY_FOR_REVIEW = 'ready_for_review', 'Ready for Review'
    IN_REVIEW = 'in_review', 'In Review'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'
    DISTRIBUTED = 'distributed', 'Distributed'
    ARCHIVED = 'archived', 'Archived'


class ICPackTemplate(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Template for generating IC packs with predefined sections and data sources.
    
    Supports dynamic content generation based on deal data and custom sections.
    """
    
    name = models.CharField(
        max_length=255,
        help_text="Template name"
    )
    description = models.TextField(
        blank=True,
        help_text="Template description and use cases"
    )
    
    # Template configuration
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this template is available for use"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Default template for IC packs"
    )
    
    # Sections configuration
    sections = models.JSONField(
        default=list,
        help_text="""
        List of sections with configuration:
        [
            {
                "id": "executive_summary",
                "title": "Executive Summary",
                "order": 1,
                "required": true,
                "data_sources": ["deal", "partner", "assessment"],
                "template": "sections/executive_summary.html",
                "max_pages": 2
            }
        ]
        """
    )
    
    # Data requirements
    required_documents = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text="Document types required for this template"
    )
    
    # Approval configuration
    approval_stages = models.JSONField(
        default=list,
        help_text="""
        Approval workflow stages:
        [
            {
                "stage": "analyst_review",
                "name": "Analyst Review",
                "required_role": "ANALYST",
                "order": 1
            }
        ]
        """
    )
    
    # Output configuration
    output_format = models.CharField(
        max_length=20,
        choices=[
            ('pdf', 'PDF'),
            ('docx', 'Word Document'),
            ('pptx', 'PowerPoint')
        ],
        default='pdf'
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_ic_templates'
    )
    tags = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True
    )
    
    class Meta:
        db_table = 'ic_pack_templates'
        verbose_name = 'IC Pack Template'
        verbose_name_plural = 'IC Pack Templates'
        ordering = ['name']
        indexes = [
            models.Index(fields=['group', 'is_active']),
            models.Index(fields=['group', 'is_default']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'name'],
                name='unique_ic_template_name_per_group'
            ),
            models.UniqueConstraint(
                fields=['group', 'is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_ic_template_per_group'
            )
        ]
    
    def __str__(self):
        return f"{self.name} {'(Default)' if self.is_default else ''}"
    
    def validate_sections(self) -> List[str]:
        """Validate section configuration."""
        errors = []
        section_ids = set()
        
        for idx, section in enumerate(self.sections):
            if 'id' not in section:
                errors.append(f"Section {idx} missing 'id'")
            elif section['id'] in section_ids:
                errors.append(f"Duplicate section ID: {section['id']}")
            else:
                section_ids.add(section['id'])
            
            if 'title' not in section:
                errors.append(f"Section {idx} missing 'title'")
            if 'order' not in section:
                errors.append(f"Section {idx} missing 'order'")
        
        return errors


class ICPack(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Investment Committee pack instance for a specific deal.
    
    Manages the lifecycle from creation through approval to distribution.
    """
    
    # Core relationships
    deal = models.ForeignKey(
        'deals.Deal',
        on_delete=models.CASCADE,
        related_name='ic_packs'
    )
    template = models.ForeignKey(
        ICPackTemplate,
        on_delete=models.PROTECT,
        related_name='packs'
    )
    
    # Pack metadata
    title = models.CharField(
        max_length=255,
        help_text="IC pack title"
    )
    meeting_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Scheduled IC meeting date"
    )
    version = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Pack version number"
    )
    
    # Status tracking
    status = FSMField(
        default=ICPackStatus.DRAFT,
        choices=ICPackStatus.choices
    )
    
    # Content and sections
    sections_data = models.JSONField(
        default=dict,
        help_text="Generated content for each section"
    )
    custom_content = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional custom content"
    )
    
    # Generated documents
    generated_document = models.ForeignKey(
        FileAttachment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ic_pack_documents'
    )
    
    # Team and ownership
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_ic_packs'
    )
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='modified_ic_packs'
    )
    
    # Approval tracking
    current_approval_stage = models.CharField(
        max_length=50,
        blank=True,
        help_text="Current stage in approval workflow"
    )
    approval_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Deadline for approval"
    )
    
    # Distribution
    distribution_list = ArrayField(
        models.EmailField(),
        default=list,
        blank=True,
        help_text="Email addresses for distribution"
    )
    distributed_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Analytics
    generation_time_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text="Time taken to generate the pack"
    )
    times_viewed = models.IntegerField(
        default=0
    )
    
    class Meta:
        db_table = 'ic_packs'
        verbose_name = 'IC Pack'
        verbose_name_plural = 'IC Packs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', 'deal']),
            models.Index(fields=['group', 'status']),
            models.Index(fields=['group', 'meeting_date']),
            models.Index(fields=['group', 'created_by']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['deal', 'version'],
                name='unique_ic_pack_version_per_deal'
            )
        ]
    
    def __str__(self):
        return f"{self.title} v{self.version} - {self.get_status_display()}"
    
    # FSM transitions
    @transition(field=status, source=ICPackStatus.DRAFT, target=ICPackStatus.READY_FOR_REVIEW)
    def submit_for_review(self):
        """Submit pack for review."""
        self.last_modified_by = self.created_by
        self.save()
    
    @transition(field=status, source=ICPackStatus.READY_FOR_REVIEW, target=ICPackStatus.IN_REVIEW)
    def start_review(self):
        """Start the review process."""
        # Set first approval stage
        if self.template.approval_stages:
            self.current_approval_stage = self.template.approval_stages[0]['stage']
    
    @transition(field=status, source=ICPackStatus.IN_REVIEW, target=ICPackStatus.APPROVED)
    def approve(self):
        """Approve the IC pack."""
        pass
    
    @transition(field=status, source=ICPackStatus.IN_REVIEW, target=ICPackStatus.REJECTED)
    def reject(self):
        """Reject the IC pack."""
        pass
    
    @transition(field=status, source=[ICPackStatus.IN_REVIEW, ICPackStatus.REJECTED], target=ICPackStatus.DRAFT)
    def send_back_to_draft(self):
        """Send pack back to draft for revisions."""
        self.version += 1
    
    @transition(field=status, source=ICPackStatus.APPROVED, target=ICPackStatus.DISTRIBUTED)
    def distribute(self):
        """Distribute the approved pack."""
        self.distributed_at = datetime.now()
    
    @transition(field=status, source='*', target=ICPackStatus.ARCHIVED)
    def archive(self):
        """Archive the pack."""
        pass
    
    def create_new_version(self) -> 'ICPack':
        """Create a new version of this pack."""
        new_pack = ICPack.objects.create(
            group=self.group,
            deal=self.deal,
            template=self.template,
            title=self.title,
            meeting_date=self.meeting_date,
            version=self.version + 1,
            sections_data=self.sections_data.copy(),
            custom_content=self.custom_content.copy(),
            created_by=self.created_by,
            distribution_list=self.distribution_list.copy()
        )
        return new_pack
    
    def get_next_approval_stage(self) -> Optional[Dict[str, Any]]:
        """Get the next approval stage if any."""
        if not self.current_approval_stage:
            return None
        
        stages = self.template.approval_stages
        current_idx = next(
            (i for i, s in enumerate(stages) if s['stage'] == self.current_approval_stage),
            -1
        )
        
        if current_idx >= 0 and current_idx < len(stages) - 1:
            return stages[current_idx + 1]
        
        return None


class ICPackApproval(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Approval record for IC pack review workflow.
    
    Tracks each approval/rejection with comments and conditions.
    """
    
    class ApprovalDecision(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        CONDITIONAL = 'conditional', 'Conditionally Approved'
    
    ic_pack = models.ForeignKey(
        ICPack,
        on_delete=models.CASCADE,
        related_name='approvals'
    )
    
    # Approval details
    stage = models.CharField(
        max_length=50,
        help_text="Approval stage identifier"
    )
    stage_name = models.CharField(
        max_length=100,
        help_text="Human-readable stage name"
    )
    
    # Decision
    decision = models.CharField(
        max_length=20,
        choices=ApprovalDecision.choices,
        default=ApprovalDecision.PENDING
    )
    decided_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ic_pack_decisions'
    )
    decided_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Feedback
    comments = models.TextField(
        blank=True,
        help_text="Approval comments or feedback"
    )
    conditions = models.JSONField(
        default=list,
        blank=True,
        help_text="Conditions for approval if conditional"
    )
    
    # Delegation
    delegated_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='delegated_ic_approvals'
    )
    delegated_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    class Meta:
        db_table = 'ic_pack_approvals'
        verbose_name = 'IC Pack Approval'
        verbose_name_plural = 'IC Pack Approvals'
        ordering = ['ic_pack', 'created_at']
        indexes = [
            models.Index(fields=['group', 'ic_pack']),
            models.Index(fields=['group', 'decision']),
            models.Index(fields=['group', 'decided_by']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['ic_pack', 'stage'],
                name='unique_approval_per_stage'
            )
        ]
    
    def __str__(self):
        return f"{self.ic_pack} - {self.stage_name}: {self.get_decision_display()}"
    
    def make_decision(self, user: User, decision: str, comments: str = '', conditions: List[str] = None):
        """Record an approval decision."""
        self.decided_by = user
        self.decided_at = datetime.now()
        self.decision = decision
        self.comments = comments
        if conditions:
            self.conditions = conditions
        self.save()
        
        # Update IC pack status based on decision
        if decision == self.ApprovalDecision.APPROVED:
            next_stage = self.ic_pack.get_next_approval_stage()
            if next_stage:
                # Create next approval stage
                ICPackApproval.objects.create(
                    group=self.group,
                    ic_pack=self.ic_pack,
                    stage=next_stage['stage'],
                    stage_name=next_stage['name']
                )
                self.ic_pack.current_approval_stage = next_stage['stage']
                self.ic_pack.save()
            else:
                # All stages approved
                self.ic_pack.approve()
                self.ic_pack.save()
        elif decision == self.ApprovalDecision.REJECTED:
            self.ic_pack.reject()
            self.ic_pack.save()


class ICPackDistribution(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Distribution record for IC packs.
    
    Tracks who received the pack and their engagement.
    """
    
    ic_pack = models.ForeignKey(
        ICPack,
        on_delete=models.CASCADE,
        related_name='distributions'
    )
    
    # Recipient
    recipient_email = models.EmailField()
    recipient_name = models.CharField(
        max_length=255,
        blank=True
    )
    recipient_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_ic_packs'
    )
    
    # Distribution details
    sent_at = models.DateTimeField(
        auto_now_add=True
    )
    sent_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='distributed_ic_packs'
    )
    
    # Engagement tracking
    first_viewed_at = models.DateTimeField(
        null=True,
        blank=True
    )
    last_viewed_at = models.DateTimeField(
        null=True,
        blank=True
    )
    view_count = models.IntegerField(
        default=0
    )
    download_count = models.IntegerField(
        default=0
    )
    
    # Access control
    access_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        help_text="Unique token for accessing the pack"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional expiration for access"
    )
    
    class Meta:
        db_table = 'ic_pack_distributions'
        verbose_name = 'IC Pack Distribution'
        verbose_name_plural = 'IC Pack Distributions'
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['group', 'ic_pack']),
            models.Index(fields=['access_token']),
            models.Index(fields=['recipient_email']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['ic_pack', 'recipient_email'],
                name='unique_distribution_per_recipient'
            )
        ]
    
    def __str__(self):
        return f"{self.ic_pack} -> {self.recipient_email}"
    
    def record_view(self):
        """Record a view of the distributed pack."""
        from django.utils import timezone
        
        now = timezone.now()
        if not self.first_viewed_at:
            self.first_viewed_at = now
        self.last_viewed_at = now
        self.view_count += 1
        self.save(update_fields=['first_viewed_at', 'last_viewed_at', 'view_count'])
        
        # Update pack view count
        self.ic_pack.times_viewed += 1
        self.ic_pack.save(update_fields=['times_viewed'])
    
    def is_expired(self) -> bool:
        """Check if access has expired."""
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at


class ICPackAuditLog(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Audit trail for all IC pack activities.
    
    Provides complete traceability of pack lifecycle.
    """
    
    class ActionType(models.TextChoices):
        CREATED = 'created', 'Created'
        MODIFIED = 'modified', 'Modified'
        SUBMITTED = 'submitted', 'Submitted for Review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        DISTRIBUTED = 'distributed', 'Distributed'
        VIEWED = 'viewed', 'Viewed'
        DOWNLOADED = 'downloaded', 'Downloaded'
        ARCHIVED = 'archived', 'Archived'
        VERSION_CREATED = 'version_created', 'New Version Created'
    
    ic_pack = models.ForeignKey(
        ICPack,
        on_delete=models.CASCADE,
        related_name='audit_logs'
    )
    
    # Action details
    action = models.CharField(
        max_length=30,
        choices=ActionType.choices
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='ic_pack_actions'
    )
    
    # Context
    description = models.TextField(
        blank=True,
        help_text="Detailed description of the action"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional action metadata"
    )
    
    # Change tracking
    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Field changes for modifications"
    )
    
    # Access details
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True
    )
    user_agent = models.TextField(
        blank=True
    )
    
    class Meta:
        db_table = 'ic_pack_audit_logs'
        verbose_name = 'IC Pack Audit Log'
        verbose_name_plural = 'IC Pack Audit Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', 'ic_pack', '-created_at']),
            models.Index(fields=['group', 'action', '-created_at']),
            models.Index(fields=['group', 'actor', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.ic_pack} - {self.get_action_display()} by {self.actor}"
    
    @classmethod
    def log_action(cls, ic_pack: ICPack, action: str, actor: User, 
                   description: str = '', metadata: Dict = None, 
                   changes: Dict = None, ip_address: str = None, 
                   user_agent: str = None):
        """Create an audit log entry."""
        return cls.objects.create(
            group=ic_pack.group,
            ic_pack=ic_pack,
            action=action,
            actor=actor,
            description=description,
            metadata=metadata or {},
            changes=changes or {},
            ip_address=ip_address,
            user_agent=user_agent or ''
        )