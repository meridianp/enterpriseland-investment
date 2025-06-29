"""
Advanced Features for CASA Due Diligence Platform - Phase 5.

Implements version control, regulatory compliance, performance monitoring,
and ESG assessment capabilities for enhanced due diligence workflows.
"""

from decimal import Decimal
from typing import Optional, Dict, List, Any
from datetime import datetime, date, timedelta
import json

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone

from .base_models import BaseAssessmentModel, RiskAssessmentMixin
from .enums import RiskLevel, AssessmentStatus
from .validation import validate_positive_decimal
from .partner_models import DevelopmentPartner
from .scheme_models import PBSAScheme
from .assessment_models import Assessment

User = get_user_model()


class VersionedEntity(models.Model):
    """
    Abstract base class for entities requiring version control and audit trails.
    
    Provides comprehensive versioning, change tracking, and audit capabilities
    for all critical business entities in the platform.
    """
    
    # Version information
    version_major = models.PositiveIntegerField(
        default=1,
        help_text="Major version number (breaking changes)"
    )
    
    version_minor = models.PositiveIntegerField(
        default=0,
        help_text="Minor version number (feature additions)"
    )
    
    version_patch = models.PositiveIntegerField(
        default=0,
        help_text="Patch version number (bug fixes)"
    )
    
    version_notes = models.TextField(
        blank=True,
        help_text="Version release notes and change description"
    )
    
    # Change tracking
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='%(class)s_modifications',
        null=True,
        blank=True,
        help_text="User who last modified this entity"
    )
    
    last_modified_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of last modification"
    )
    
    change_reason = models.CharField(
        max_length=500,
        blank=True,
        help_text="Reason for the change"
    )
    
    # Approval workflow
    requires_approval = models.BooleanField(
        default=True,
        help_text="Whether changes require approval"
    )
    
    approved_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='%(class)s_approvals',
        null=True,
        blank=True,
        help_text="User who approved this version"
    )
    
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of approval"
    )
    
    is_published = models.BooleanField(
        default=False,
        help_text="Whether this version is published/active"
    )
    
    class Meta:
        abstract = True
    
    @property
    def semver(self) -> str:
        """Get semantic version string."""
        return f"{self.version_major}.{self.version_minor}.{self.version_patch}"
    
    @property
    def is_approved(self) -> bool:
        """Check if this version is approved."""
        return bool(self.approved_by and self.approved_at)
    
    def increment_version(self, version_type: str = 'patch', reason: str = '') -> None:
        """Increment version number based on change type."""
        if version_type == 'major':
            self.version_major += 1
            self.version_minor = 0
            self.version_patch = 0
        elif version_type == 'minor':
            self.version_minor += 1
            self.version_patch = 0
        else:  # patch
            self.version_patch += 1
        
        self.change_reason = reason
        self.is_published = False
        self.approved_by = None
        self.approved_at = None
    
    def approve_version(self, user: User, notes: str = '') -> None:
        """Approve this version for publication."""
        self.approved_by = user
        self.approved_at = timezone.now()
        self.is_published = True
        if notes:
            self.version_notes = notes


class RegulatoryCompliance(BaseAssessmentModel, VersionedEntity):
    """
    Regulatory compliance tracking and management.
    
    Manages regulatory requirements, compliance status, and jurisdictional
    considerations for international due diligence processes.
    """
    
    # Entity associations
    partner = models.ForeignKey(
        DevelopmentPartner,
        on_delete=models.CASCADE,
        related_name='regulatory_compliance',
        null=True,
        blank=True,
        help_text="Partner this compliance record applies to"
    )
    
    scheme = models.ForeignKey(
        PBSAScheme,
        on_delete=models.CASCADE,
        related_name='regulatory_compliance',
        null=True,
        blank=True,
        help_text="Scheme this compliance record applies to"
    )
    
    # Jurisdiction and regulatory framework
    jurisdiction = models.CharField(
        max_length=2,
        help_text="ISO country code for jurisdiction"
    )
    
    regulatory_framework = models.CharField(
        max_length=100,
        help_text="Name of applicable regulatory framework"
    )
    
    regulatory_body = models.CharField(
        max_length=200,
        help_text="Name of regulatory authority"
    )
    
    # Compliance requirements
    compliance_category = models.CharField(
        max_length=50,
        choices=[
            ('financial', 'Financial Regulation'),
            ('planning', 'Planning and Development'),
            ('building', 'Building Standards'),
            ('fire_safety', 'Fire Safety'),
            ('environmental', 'Environmental'),
            ('data_protection', 'Data Protection'),
            ('consumer', 'Consumer Protection'),
            ('employment', 'Employment Law'),
            ('tax', 'Tax and Revenue'),
            ('licensing', 'Licensing and Permits'),
        ],
        help_text="Category of compliance requirement"
    )
    
    requirement_title = models.CharField(
        max_length=200,
        help_text="Title of specific requirement"
    )
    
    requirement_description = models.TextField(
        help_text="Detailed description of compliance requirement"
    )
    
    # Compliance status
    compliance_status = models.CharField(
        max_length=20,
        choices=[
            ('compliant', 'Fully Compliant'),
            ('partial', 'Partially Compliant'),
            ('non_compliant', 'Non-Compliant'),
            ('pending', 'Compliance Pending'),
            ('exempt', 'Exempt'),
            ('not_applicable', 'Not Applicable'),
        ],
        default='pending',
        help_text="Current compliance status"
    )
    
    compliance_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date compliance was achieved"
    )
    
    expiry_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date compliance expires (if applicable)"
    )
    
    # Risk assessment
    compliance_risk_level = models.CharField(
        max_length=20,
        choices=RiskLevel.choices,
        default=RiskLevel.MEDIUM,
        help_text="Risk level if non-compliant"
    )
    
    financial_impact_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Potential financial impact of non-compliance"
    )
    
    # Evidence and documentation
    evidence_documents = models.JSONField(
        default=list,
        help_text="List of supporting documentation"
    )
    
    compliance_notes = models.TextField(
        blank=True,
        help_text="Additional compliance notes and observations"
    )
    
    # Review and monitoring
    next_review_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of next compliance review"
    )
    
    responsible_person = models.CharField(
        max_length=200,
        blank=True,
        help_text="Person responsible for maintaining compliance"
    )
    
    class Meta:
        db_table = 'regulatory_compliance'
        verbose_name = 'Regulatory Compliance'
        verbose_name_plural = 'Regulatory Compliance Records'
        unique_together = ['partner', 'scheme', 'regulatory_framework', 'requirement_title']
    
    def __str__(self) -> str:
        entity = self.partner or self.scheme
        return f"{self.requirement_title} - {entity} ({self.jurisdiction})"
    
    @property
    def is_expiring_soon(self) -> bool:
        """Check if compliance is expiring within 90 days."""
        if not self.expiry_date:
            return False
        return self.expiry_date <= date.today() + timedelta(days=90)
    
    @property
    def days_until_expiry(self) -> Optional[int]:
        """Calculate days until compliance expires."""
        if not self.expiry_date:
            return None
        return (self.expiry_date - date.today()).days
    
    @property
    def compliance_score(self) -> int:
        """Calculate compliance score (1-5)."""
        status_scores = {
            'compliant': 5,
            'partial': 3,
            'non_compliant': 1,
            'pending': 2,
            'exempt': 5,
            'not_applicable': 5
        }
        
        base_score = status_scores.get(self.compliance_status, 2)
        
        # Adjust for expiry risk
        if self.is_expiring_soon:
            base_score = max(1, base_score - 1)
        
        return base_score


class PerformanceMetric(BaseAssessmentModel, VersionedEntity):
    """
    Performance monitoring and historical tracking.
    
    Captures performance metrics over time for partners, schemes, and assessments
    to enable trend analysis and performance optimization.
    """
    
    # Entity associations
    partner = models.ForeignKey(
        DevelopmentPartner,
        on_delete=models.CASCADE,
        related_name='performance_metrics',
        null=True,
        blank=True,
        help_text="Partner this metric applies to"
    )
    
    scheme = models.ForeignKey(
        PBSAScheme,
        on_delete=models.CASCADE,
        related_name='performance_metrics',
        null=True,
        blank=True,
        help_text="Scheme this metric applies to"
    )
    
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='performance_metrics',
        null=True,
        blank=True,
        help_text="Assessment this metric applies to"
    )
    
    # Metric definition
    metric_name = models.CharField(
        max_length=100,
        help_text="Name of the performance metric"
    )
    
    metric_category = models.CharField(
        max_length=50,
        choices=[
            ('financial', 'Financial Performance'),
            ('operational', 'Operational Performance'),
            ('market', 'Market Performance'),
            ('development', 'Development Performance'),
            ('compliance', 'Compliance Performance'),
            ('satisfaction', 'Customer Satisfaction'),
            ('efficiency', 'Operational Efficiency'),
            ('sustainability', 'ESG Performance'),
        ],
        help_text="Category of performance metric"
    )
    
    metric_description = models.TextField(
        blank=True,
        help_text="Description of what this metric measures"
    )
    
    # Metric value and measurement
    measurement_date = models.DateField(
        help_text="Date this measurement was taken"
    )
    
    metric_value = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        help_text="Measured value of the metric"
    )
    
    metric_unit = models.CharField(
        max_length=50,
        blank=True,
        help_text="Unit of measurement (%, £, ratio, etc.)"
    )
    
    # Benchmarking and targets
    target_value = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Target value for this metric"
    )
    
    benchmark_value = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Industry/market benchmark value"
    )
    
    # Performance analysis
    trend_direction = models.CharField(
        max_length=20,
        choices=[
            ('improving', 'Improving'),
            ('stable', 'Stable'),
            ('declining', 'Declining'),
            ('volatile', 'Volatile'),
        ],
        null=True,
        blank=True,
        help_text="Overall trend direction"
    )
    
    variance_from_target_pct = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Percentage variance from target"
    )
    
    variance_from_benchmark_pct = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Percentage variance from benchmark"
    )
    
    # Data quality and validation
    data_source = models.CharField(
        max_length=200,
        help_text="Source of the metric data"
    )
    
    data_quality_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=3,
        help_text="Quality/reliability of data (1-5)"
    )
    
    measurement_frequency = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('annually', 'Annually'),
            ('ad_hoc', 'Ad Hoc'),
        ],
        help_text="Frequency of measurement"
    )
    
    # Analysis and insights
    performance_notes = models.TextField(
        blank=True,
        help_text="Analysis and insights about this measurement"
    )
    
    action_required = models.BooleanField(
        default=False,
        help_text="Whether this metric indicates action is required"
    )
    
    class Meta:
        db_table = 'performance_metrics'
        verbose_name = 'Performance Metric'
        verbose_name_plural = 'Performance Metrics'
        ordering = ['-measurement_date', 'metric_name']
        indexes = [
            models.Index(fields=['metric_name', 'measurement_date']),
            models.Index(fields=['metric_category', '-measurement_date']),
        ]
    
    def __str__(self) -> str:
        entity = self.partner or self.scheme or self.assessment
        return f"{self.metric_name}: {self.metric_value} ({self.measurement_date})"
    
    @property
    def performance_rating(self) -> str:
        """Get performance rating based on target achievement."""
        if not self.target_value or not self.variance_from_target_pct:
            return "Not Available"
        
        variance = abs(self.variance_from_target_pct)
        
        if variance <= 5:
            return "Excellent"
        elif variance <= 10:
            return "Good"
        elif variance <= 20:
            return "Acceptable"
        elif variance <= 30:
            return "Poor"
        else:
            return "Unacceptable"
    
    @property
    def is_meeting_target(self) -> Optional[bool]:
        """Check if metric is meeting target."""
        if not self.target_value:
            return None
        
        # For metrics where higher is better
        if self.metric_name in ['occupancy_rate', 'satisfaction_score', 'yield']:
            return self.metric_value >= self.target_value
        # For metrics where lower is better
        elif self.metric_name in ['cost_overrun', 'delay_months', 'complaints']:
            return self.metric_value <= self.target_value
        # For metrics where close to target is better
        else:
            if self.variance_from_target_pct:
                return abs(self.variance_from_target_pct) <= 10
        
        return None


class ESGAssessment(BaseAssessmentModel, VersionedEntity, RiskAssessmentMixin):
    """
    Environmental, Social, and Governance (ESG) assessment framework.
    
    Comprehensive ESG evaluation for partners and schemes to support
    sustainable investment decisions and regulatory compliance.
    """
    
    # Entity associations
    partner = models.ForeignKey(
        DevelopmentPartner,
        on_delete=models.CASCADE,
        related_name='esg_assessments',
        null=True,
        blank=True,
        help_text="Partner this ESG assessment applies to"
    )
    
    scheme = models.ForeignKey(
        PBSAScheme,
        on_delete=models.CASCADE,
        related_name='esg_assessments',
        null=True,
        blank=True,
        help_text="Scheme this ESG assessment applies to"
    )
    
    # Assessment metadata
    assessment_name = models.CharField(
        max_length=200,
        help_text="Name of this ESG assessment"
    )
    
    assessment_framework = models.CharField(
        max_length=100,
        choices=[
            ('gri', 'Global Reporting Initiative (GRI)'),
            ('sasb', 'Sustainability Accounting Standards Board (SASB)'),
            ('tcfd', 'Task Force on Climate-related Financial Disclosures'),
            ('un_sdg', 'UN Sustainable Development Goals'),
            ('breeam', 'BREEAM Building Assessment'),
            ('leed', 'LEED Green Building'),
            ('custom', 'Custom Framework'),
        ],
        default='gri',
        help_text="ESG assessment framework used"
    )
    
    assessment_period_start = models.DateField(
        help_text="Start date of assessment period"
    )
    
    assessment_period_end = models.DateField(
        help_text="End date of assessment period"
    )
    
    # Environmental (E) Factors
    environmental_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Environmental performance score (1-5)"
    )
    
    carbon_footprint_tonnes = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Carbon footprint in tonnes CO2 equivalent"
    )
    
    energy_efficiency_rating = models.CharField(
        max_length=2,
        choices=[
            ('A+', 'A+ (Highest)'),
            ('A', 'A'),
            ('B', 'B'),
            ('C', 'C'),
            ('D', 'D'),
            ('E', 'E'),
            ('F', 'F'),
            ('G', 'G (Lowest)'),
        ],
        null=True,
        blank=True,
        help_text="Energy efficiency rating"
    )
    
    renewable_energy_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
        help_text="Percentage of energy from renewable sources"
    )
    
    water_efficiency_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
        help_text="Water efficiency score (1-5)"
    )
    
    waste_diversion_rate_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
        help_text="Percentage of waste diverted from landfill"
    )
    
    environmental_certifications = models.JSONField(
        default=list,
        help_text="List of environmental certifications"
    )
    
    # Social (S) Factors
    social_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Social performance score (1-5)"
    )
    
    community_investment_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Community investment amount"
    )
    
    local_employment_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
        help_text="Percentage of local workforce"
    )
    
    health_safety_incidents = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of health and safety incidents"
    )
    
    student_satisfaction_score = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
        help_text="Student satisfaction score (1-5)"
    )
    
    accessibility_compliance_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
        help_text="Accessibility compliance score (1-5)"
    )
    
    # Governance (G) Factors
    governance_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Governance performance score (1-5)"
    )
    
    board_diversity_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
        help_text="Board diversity percentage"
    )
    
    ethics_training_completion_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
        help_text="Ethics training completion rate"
    )
    
    transparency_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
        help_text="Transparency and disclosure score (1-5)"
    )
    
    anti_corruption_policies = models.BooleanField(
        default=False,
        help_text="Whether anti-corruption policies are in place"
    )
    
    # Overall ESG Assessment
    overall_esg_score = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Overall weighted ESG score"
    )
    
    esg_rating = models.CharField(
        max_length=3,
        choices=[
            ('AAA', 'AAA (Leader)'),
            ('AA', 'AA (Leader)'),
            ('A', 'A (Average)'),
            ('BBB', 'BBB (Average)'),
            ('BB', 'BB (Average)'),
            ('B', 'B (Laggard)'),
            ('CCC', 'CCC (Laggard)'),
        ],
        null=True,
        blank=True,
        help_text="ESG rating classification"
    )
    
    # Improvement and action plans
    improvement_areas = models.JSONField(
        default=list,
        help_text="Areas identified for improvement"
    )
    
    action_plan = models.TextField(
        blank=True,
        help_text="Action plan for ESG improvements"
    )
    
    next_assessment_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of next ESG assessment"
    )
    
    class Meta:
        db_table = 'esg_assessments'
        verbose_name = 'ESG Assessment'
        verbose_name_plural = 'ESG Assessments'
        ordering = ['-assessment_period_end']
    
    def __str__(self) -> str:
        entity = self.partner or self.scheme
        return f"ESG Assessment: {entity} ({self.assessment_period_end})"
    
    def calculate_overall_score(self) -> Decimal:
        """Calculate weighted overall ESG score."""
        # Standard weighting: E=40%, S=30%, G=30%
        e_weight = Decimal('0.40')
        s_weight = Decimal('0.30')
        g_weight = Decimal('0.30')
        
        overall = (
            (self.environmental_score * e_weight) +
            (self.social_score * s_weight) +
            (self.governance_score * g_weight)
        )
        
        return round(overall, 2)
    
    def determine_esg_rating(self) -> str:
        """Determine ESG rating based on overall score."""
        score = self.calculate_overall_score()
        
        if score >= 4.5:
            return 'AAA'
        elif score >= 4.0:
            return 'AA'
        elif score >= 3.5:
            return 'A'
        elif score >= 3.0:
            return 'BBB'
        elif score >= 2.5:
            return 'BB'
        elif score >= 2.0:
            return 'B'
        else:
            return 'CCC'
    
    @property
    def carbon_intensity(self) -> Optional[Decimal]:
        """Calculate carbon intensity per bed (for schemes)."""
        if self.scheme and self.carbon_footprint_tonnes and self.scheme.total_beds:
            return round(self.carbon_footprint_tonnes / self.scheme.total_beds, 2)
        return None
    
    def save(self, *args, **kwargs):
        """Auto-calculate overall score and rating on save."""
        self.overall_esg_score = self.calculate_overall_score()
        self.esg_rating = self.determine_esg_rating()
        super().save(*args, **kwargs)


class AuditTrail(BaseAssessmentModel):
    """
    Comprehensive audit trail for all system changes.
    
    Tracks all significant changes across the platform for compliance,
    debugging, and historical analysis purposes.
    """
    
    # Change identification
    entity_type = models.CharField(
        max_length=100,
        help_text="Type of entity that was changed"
    )
    
    entity_id = models.UUIDField(
        help_text="ID of the entity that was changed"
    )
    
    action_type = models.CharField(
        max_length=20,
        choices=[
            ('create', 'Created'),
            ('update', 'Updated'),
            ('delete', 'Deleted'),
            ('approve', 'Approved'),
            ('reject', 'Rejected'),
            ('publish', 'Published'),
            ('archive', 'Archived'),
        ],
        help_text="Type of action performed"
    )
    
    # Change details
    changed_fields = models.JSONField(
        default=dict,
        help_text="Fields that were changed and their old/new values"
    )
    
    change_summary = models.CharField(
        max_length=500,
        help_text="Brief summary of the change"
    )
    
    # User and context
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        help_text="User who made the change"
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the user"
    )
    
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string"
    )
    
    # Additional context
    business_justification = models.TextField(
        blank=True,
        help_text="Business justification for the change"
    )
    
    risk_assessment = models.CharField(
        max_length=20,
        choices=RiskLevel.choices,
        default=RiskLevel.LOW,
        help_text="Risk level of this change"
    )
    
    class Meta:
        db_table = 'audit_trail'
        verbose_name = 'Audit Trail Entry'
        verbose_name_plural = 'Audit Trail'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action_type', '-created_at']),
        ]
    
    def __str__(self) -> str:
        return f"{self.action_type} {self.entity_type} by {self.user} at {self.created_at}"