"""
Core deal model for investment opportunity tracking.
"""

import uuid
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django_fsm import FSMField, transition
from django.utils import timezone

from assessments.base_models import GroupFilteredModel, TimestampedModel, UUIDModel
from accounts.models import User


class DealType(GroupFilteredModel, TimestampedModel):
    """Types of deals (e.g., Equity, Debt, JV, etc.)"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    configuration = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'deal_types'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class DealSource(GroupFilteredModel, TimestampedModel):
    """Sources of deal flow"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'deal_sources'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Deal(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Central deal entity representing an investment opportunity.
    
    Tracks the complete lifecycle of a deal from origination to close.
    """
    
    class Status(models.TextChoices):
        PIPELINE = 'pipeline', 'Pipeline'
        INITIAL_REVIEW = 'initial_review', 'Initial Review'
        DUE_DILIGENCE = 'due_diligence', 'Due Diligence'
        NEGOTIATION = 'negotiation', 'Negotiation'
        DOCUMENTATION = 'documentation', 'Documentation'
        CLOSING = 'closing', 'Closing'
        COMPLETED = 'completed', 'Completed'
        REJECTED = 'rejected', 'Rejected'
        ON_HOLD = 'on_hold', 'On Hold'
        WITHDRAWN = 'withdrawn', 'Withdrawn'
    
    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        CRITICAL = 'critical', 'Critical'
    
    # Basic Information
    name = models.CharField(
        max_length=200,
        help_text="Deal name or project name"
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique deal code (e.g., 2024-EQ-001)"
    )
    description = models.TextField(
        blank=True,
        help_text="Deal overview and investment thesis"
    )
    
    # Deal Classification
    deal_type = models.ForeignKey(
        DealType,
        on_delete=models.PROTECT,
        related_name='deals'
    )
    deal_source = models.ForeignKey(
        DealSource,
        on_delete=models.PROTECT,
        related_name='deals'
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM
    )
    
    # Status and Workflow
    status = FSMField(
        max_length=20,
        choices=Status.choices,
        default=Status.PIPELINE,
        protected=True
    )
    current_stage = models.ForeignKey(
        'DealStage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='current_deals'
    )
    stage_entered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the deal entered current stage"
    )
    
    # Relationships
    target_company = models.ForeignKey(
        'market_intelligence.TargetCompany',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deals'
    )
    lead = models.ForeignKey(
        'leads.Lead',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deals'
    )
    assessment = models.ForeignKey(
        'assessments.Assessment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deals'
    )
    primary_contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        null=True,
        related_name='primary_deals'
    )
    
    # Financial Information
    deal_size = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total deal size in base currency"
    )
    investment_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Our investment amount"
    )
    pre_money_valuation = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    post_money_valuation = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    ownership_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00'))
        ]
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="ISO 4217 currency code"
    )
    
    # Dates
    origination_date = models.DateField(
        default=timezone.now,
        help_text="When the deal was originated"
    )
    expected_close_date = models.DateField(
        null=True,
        blank=True,
        help_text="Expected closing date"
    )
    actual_close_date = models.DateField(
        null=True,
        blank=True,
        help_text="Actual closing date"
    )
    
    # Team
    deal_lead = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='led_deals'
    )
    originator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='originated_deals'
    )
    
    # Additional Information
    sector = models.CharField(max_length=100, blank=True)
    geography = models.CharField(max_length=100, blank=True)
    investment_thesis = models.TextField(blank=True)
    key_risks = models.TextField(blank=True)
    exit_strategy = models.TextField(blank=True)
    
    # Metadata
    tags = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    
    # Metrics
    irr_target = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Target IRR percentage"
    )
    multiple_target = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Target multiple (e.g., 2.5x)"
    )
    
    class Meta:
        db_table = 'deals'
        verbose_name = 'Deal'
        verbose_name_plural = 'Deals'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', 'status']),
            models.Index(fields=['group', 'deal_lead']),
            models.Index(fields=['group', 'expected_close_date']),
            models.Index(fields=['code']),
        ]
        permissions = [
            ('view_all_deals', 'Can view all deals in group'),
            ('approve_deals', 'Can approve deal progression'),
            ('export_deals', 'Can export deal data'),
        ]
    
    def save(self, *args, **kwargs):
        """Override save to generate code if not provided"""
        if not self.code:
            # Generate code based on deal type and year
            year = timezone.now().year
            deal_type_code = self.deal_type.code.upper()[:3] if self.deal_type else 'DEL'
            
            # Find next sequence number for this type and year
            prefix = f"{deal_type_code}-{year}"
            existing_codes = Deal.objects.filter(
                code__startswith=prefix,
                group=self.group
            ).values_list('code', flat=True)
            
            # Extract sequence numbers and find next
            sequence_numbers = []
            for code in existing_codes:
                try:
                    seq = int(code.split('-')[-1])
                    sequence_numbers.append(seq)
                except (ValueError, IndexError):
                    continue
            
            next_seq = max(sequence_numbers, default=0) + 1
            self.code = f"{prefix}-{next_seq:03d}"
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.code}: {self.name}"
    
    @property
    def days_in_current_stage(self):
        """Calculate days in current stage"""
        if self.stage_entered_at:
            return (timezone.now() - self.stage_entered_at).days
        return 0
    
    @property
    def is_active(self):
        """Check if deal is in active status"""
        return self.status not in [
            self.Status.COMPLETED,
            self.Status.REJECTED,
            self.Status.WITHDRAWN
        ]
    
    # State transitions
    @transition(field=status, source=Status.PIPELINE, target=Status.INITIAL_REVIEW)
    def start_review(self):
        """Move deal to initial review"""
        self.stage_entered_at = timezone.now()
    
    @transition(field=status, source=Status.INITIAL_REVIEW, target=Status.DUE_DILIGENCE)
    def start_due_diligence(self):
        """Move deal to due diligence"""
        self.stage_entered_at = timezone.now()
    
    @transition(field=status, source=Status.DUE_DILIGENCE, target=Status.NEGOTIATION)
    def start_negotiation(self):
        """Move deal to negotiation"""
        self.stage_entered_at = timezone.now()
    
    @transition(field=status, source=Status.NEGOTIATION, target=Status.DOCUMENTATION)
    def start_documentation(self):
        """Move deal to documentation"""
        self.stage_entered_at = timezone.now()
    
    @transition(field=status, source=Status.DOCUMENTATION, target=Status.CLOSING)
    def start_closing(self):
        """Move deal to closing"""
        self.stage_entered_at = timezone.now()
    
    @transition(field=status, source=Status.CLOSING, target=Status.COMPLETED)
    def complete_deal(self):
        """Complete the deal"""
        self.stage_entered_at = timezone.now()
        self.actual_close_date = timezone.now().date()
    
    @transition(field=status, source=[
        Status.PIPELINE,
        Status.INITIAL_REVIEW,
        Status.DUE_DILIGENCE,
        Status.NEGOTIATION,
        Status.DOCUMENTATION
    ], target=Status.REJECTED)
    def reject_deal(self):
        """Reject the deal"""
        self.stage_entered_at = timezone.now()
    
    @transition(field=status, source=[
        Status.INITIAL_REVIEW,
        Status.DUE_DILIGENCE,
        Status.NEGOTIATION,
        Status.DOCUMENTATION
    ], target=Status.ON_HOLD)
    def put_on_hold(self):
        """Put deal on hold"""
        self.stage_entered_at = timezone.now()
    
    @transition(field=status, source=Status.ON_HOLD, target=[Status.PIPELINE, Status.INITIAL_REVIEW, Status.DUE_DILIGENCE, Status.NEGOTIATION, Status.DOCUMENTATION, Status.CLOSING])
    def resume_deal(self):
        """Resume deal from hold"""
        self.stage_entered_at = timezone.now()
    
    def can_transition_to(self, target_status):
        """Check if transition to target status is allowed"""
        # Get available transitions for current status
        transitions = {
            self.Status.PIPELINE: [self.Status.INITIAL_REVIEW, self.Status.REJECTED],
            self.Status.INITIAL_REVIEW: [
                self.Status.DUE_DILIGENCE,
                self.Status.REJECTED,
                self.Status.ON_HOLD
            ],
            self.Status.DUE_DILIGENCE: [
                self.Status.NEGOTIATION,
                self.Status.REJECTED,
                self.Status.ON_HOLD
            ],
            self.Status.NEGOTIATION: [
                self.Status.DOCUMENTATION,
                self.Status.REJECTED,
                self.Status.ON_HOLD
            ],
            self.Status.DOCUMENTATION: [
                self.Status.CLOSING,
                self.Status.REJECTED,
                self.Status.ON_HOLD
            ],
            self.Status.CLOSING: [self.Status.COMPLETED],
            self.Status.ON_HOLD: [
                self.Status.INITIAL_REVIEW,
                self.Status.DUE_DILIGENCE,
                self.Status.NEGOTIATION,
                self.Status.DOCUMENTATION
            ],
        }
        
        return target_status in transitions.get(self.status, [])