"""
Gold-Standard Assessment Framework for the CASA Due Diligence Platform.

This module implements the comprehensive assessment framework with weighted scoring,
decision thresholds, and automated recommendations as specified in the original
CASA data model.
"""

from decimal import Decimal
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime, date
from enum import Enum

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db.models import Avg, Sum, Max, Min, Count

from .base_models import BaseAssessmentModel, VersionedModel
from .enums import AssessmentStatus, AssessmentDecision, RiskLevel
from .validation import validate_positive_decimal, validate_year_range


class AssessmentType(models.TextChoices):
    """Types of assessments that can be performed."""
    PARTNER = 'PARTNER', 'Development Partner Assessment'
    SCHEME = 'SCHEME', 'PBSA Scheme Assessment'
    COMBINED = 'COMBINED', 'Combined Partner & Scheme Assessment'


class MetricCategory(models.TextChoices):
    """Categories for assessment metrics."""
    FINANCIAL = 'FINANCIAL', 'Financial Health'
    OPERATIONAL = 'OPERATIONAL', 'Operational Capability'
    TRACK_RECORD = 'TRACK_RECORD', 'Track Record & Experience'
    MARKET = 'MARKET', 'Market Position'
    RISK = 'RISK', 'Risk Assessment'
    ESG = 'ESG', 'Environmental, Social & Governance'
    LOCATION = 'LOCATION', 'Location & Site Factors'
    ECONOMIC = 'ECONOMIC', 'Economic Viability'


class DecisionBand(models.TextChoices):
    """Decision bands based on total weighted scores."""
    PREMIUM_PRIORITY = 'PREMIUM_PRIORITY', 'Premium/Priority (>165 points)'
    ACCEPTABLE = 'ACCEPTABLE', 'Acceptable (125-165 points)'
    REJECT = 'REJECT', 'Reject (<125 points)'


class Assessment(BaseAssessmentModel, VersionedModel):
    """
    Main assessment record implementing the gold-standard framework.
    
    Supports weighted scoring, automated decision making, and comprehensive
    assessment tracking across partner and scheme evaluations.
    """
    
    # Assessment identification
    assessment_type = models.CharField(
        max_length=20,
        choices=AssessmentType.choices,
        help_text="Type of assessment being performed"
    )
    
    assessment_name = models.CharField(
        max_length=255,
        help_text="Descriptive name for this assessment"
    )
    
    # Related entities
    partner = models.ForeignKey(
        'DevelopmentPartner',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='assessments',
        help_text="Development partner being assessed"
    )
    
    scheme = models.ForeignKey(
        'PBSAScheme',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='assessments',
        help_text="PBSA scheme being assessed"
    )
    
    # Assessment status and decision
    status = models.CharField(
        max_length=20,
        choices=AssessmentStatus.choices,
        default=AssessmentStatus.DRAFT,
        help_text="Current status of the assessment"
    )
    
    decision = models.CharField(
        max_length=20,
        choices=AssessmentDecision.choices,
        blank=True,
        help_text="Final assessment decision"
    )
    
    decision_band = models.CharField(
        max_length=20,
        choices=DecisionBand.choices,
        blank=True,
        help_text="Decision band based on scoring"
    )
    
    # Scoring summary
    total_weighted_score = models.IntegerField(
        null=True,
        blank=True,
        help_text="Total weighted score across all metrics"
    )
    
    max_possible_score = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum possible weighted score"
    )
    
    score_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Score as percentage of maximum possible"
    )
    
    # Assessment metadata
    assessment_date = models.DateField(
        default=date.today,
        help_text="Date when assessment was performed"
    )
    
    assessment_purpose = models.TextField(
        blank=True,
        help_text="Purpose and context of the assessment"
    )
    
    key_strengths = models.TextField(
        blank=True,
        help_text="Identified key strengths"
    )
    
    key_weaknesses = models.TextField(
        blank=True,
        help_text="Identified key weaknesses"
    )
    
    recommendations = models.TextField(
        blank=True,
        help_text="Assessment recommendations"
    )
    
    executive_summary = models.TextField(
        blank=True,
        help_text="Executive summary of assessment findings"
    )
    
    # Workflow tracking
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When assessment was submitted for review"
    )
    
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When assessment was reviewed"
    )
    
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When assessment was approved"
    )
    
    # Users involved
    assessor = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='conducted_assessments',
        help_text="User who conducted the assessment"
    )
    
    reviewer = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='reviewed_assessments',
        help_text="User who reviewed the assessment"
    )
    
    approver = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='approved_assessments',
        help_text="User who approved the assessment"
    )
    
    class Meta:
        db_table = 'assessments_enhanced'
        verbose_name = 'Assessment'
        verbose_name_plural = 'Assessments'
        ordering = ['-assessment_date', '-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['decision_band']),
            models.Index(fields=['assessment_date']),
            models.Index(fields=['total_weighted_score']),
        ]
    
    def __str__(self) -> str:
        return f"{self.assessment_name} ({self.get_assessment_type_display()})"
    
    def calculate_scores(self) -> Dict[str, Any]:
        """
        Calculate comprehensive assessment scores.
        
        Returns:
            Dictionary with total scores, category breakdowns, and analysis
        """
        metrics = self.assessment_metrics.all()
        
        if not metrics.exists():
            return {
                'total_weighted_score': 0,
                'max_possible_score': 0,
                'score_percentage': 0,
                'category_scores': {},
                'metric_count': 0
            }
        
        # Calculate totals
        total_weighted = sum(metric.weighted_score for metric in metrics)
        total_possible = sum(metric.max_weighted_score for metric in metrics)
        
        # Calculate category breakdowns
        category_scores = {}
        for category in MetricCategory.choices:
            category_metrics = metrics.filter(category=category[0])
            if category_metrics.exists():
                category_weighted = sum(m.weighted_score for m in category_metrics)
                category_possible = sum(m.max_weighted_score for m in category_metrics)
                category_scores[category[0]] = {
                    'weighted_score': category_weighted,
                    'max_possible': category_possible,
                    'percentage': round((category_weighted / category_possible * 100), 2) if category_possible > 0 else 0,
                    'metric_count': category_metrics.count()
                }
        
        # Calculate overall percentage
        score_pct = round((total_weighted / total_possible * 100), 2) if total_possible > 0 else 0
        
        return {
            'total_weighted_score': total_weighted,
            'max_possible_score': total_possible,
            'score_percentage': score_pct,
            'category_scores': category_scores,
            'metric_count': metrics.count()
        }
    
    def determine_decision_band(self) -> str:
        """
        Determine decision band based on total weighted score.
        
        Decision thresholds:
        - Premium/Priority: >165 points
        - Acceptable: 125-165 points  
        - Reject: <125 points
        """
        if self.total_weighted_score is None:
            return ''
        
        if self.total_weighted_score > 165:
            return DecisionBand.PREMIUM_PRIORITY
        elif self.total_weighted_score >= 125:
            return DecisionBand.ACCEPTABLE
        else:
            return DecisionBand.REJECT
    
    def get_strongest_categories(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Get the strongest performing assessment categories."""
        scores = self.calculate_scores()
        category_scores = scores.get('category_scores', {})
        
        # Sort by percentage score
        sorted_categories = sorted(
            [(cat, data) for cat, data in category_scores.items()],
            key=lambda x: x[1]['percentage'],
            reverse=True
        )
        
        return [
            {
                'category': cat,
                'category_display': dict(MetricCategory.choices)[cat],
                'percentage': data['percentage'],
                'weighted_score': data['weighted_score'],
                'max_possible': data['max_possible']
            }
            for cat, data in sorted_categories[:limit]
        ]
    
    def get_weakest_categories(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Get the weakest performing assessment categories."""
        scores = self.calculate_scores()
        category_scores = scores.get('category_scores', {})
        
        # Sort by percentage score (ascending)
        sorted_categories = sorted(
            [(cat, data) for cat, data in category_scores.items()],
            key=lambda x: x[1]['percentage']
        )
        
        return [
            {
                'category': cat,
                'category_display': dict(MetricCategory.choices)[cat],
                'percentage': data['percentage'],
                'weighted_score': data['weighted_score'],
                'max_possible': data['max_possible']
            }
            for cat, data in sorted_categories[:limit]
        ]
    
    def generate_automated_recommendations(self) -> List[str]:
        """
        Generate automated recommendations based on assessment results.
        """
        recommendations = []
        
        # Score-based recommendations
        if self.score_percentage is not None:
            if self.score_percentage < 60:
                recommendations.append(
                    "Overall performance is below acceptable thresholds. "
                    "Consider comprehensive improvement across multiple areas."
                )
            elif self.score_percentage > 85:
                recommendations.append(
                    "Excellent overall performance. This partner/scheme demonstrates "
                    "strong capabilities across assessed criteria."
                )
        
        # Category-specific recommendations
        weakest = self.get_weakest_categories(2)
        for weak_cat in weakest:
            if weak_cat['percentage'] < 50:
                category_name = weak_cat['category_display']
                if weak_cat['category'] == MetricCategory.FINANCIAL:
                    recommendations.append(
                        f"Financial health concerns identified. Review balance sheet "
                        f"strength, profitability, and debt management strategies."
                    )
                elif weak_cat['category'] == MetricCategory.OPERATIONAL:
                    recommendations.append(
                        f"Operational capability gaps detected. Assess team capacity, "
                        f"delivery track record, and process maturity."
                    )
                elif weak_cat['category'] == MetricCategory.RISK:
                    recommendations.append(
                        f"Risk profile requires attention. Review mitigation strategies "
                        f"and contingency planning."
                    )
                else:
                    recommendations.append(
                        f"{category_name} performance below expectations. "
                        f"Focused improvement required in this area."
                    )
        
        # Decision band recommendations
        if self.decision_band == DecisionBand.REJECT:
            recommendations.append(
                "Current assessment suggests rejection. Significant improvements "
                "required before re-assessment."
            )
        elif self.decision_band == DecisionBand.ACCEPTABLE:
            recommendations.append(
                "Assessment indicates acceptable performance. Monitor ongoing "
                "performance and consider targeted improvements."
            )
        elif self.decision_band == DecisionBand.PREMIUM_PRIORITY:
            recommendations.append(
                "Excellent candidate for premium/priority status. Strong performance "
                "across assessment criteria."
            )
        
        return recommendations
    
    def refresh_calculated_fields(self):
        """Refresh all calculated fields based on current metrics."""
        scores = self.calculate_scores()
        
        self.total_weighted_score = scores['total_weighted_score']
        self.max_possible_score = scores['max_possible_score']
        self.score_percentage = scores['score_percentage']
        self.decision_band = self.determine_decision_band()
        
        # Auto-generate recommendations if not manually set
        if not self.recommendations:
            auto_recommendations = self.generate_automated_recommendations()
            self.recommendations = '\n\n'.join(auto_recommendations)
        
        self.save(update_fields=[
            'total_weighted_score', 'max_possible_score', 'score_percentage',
            'decision_band', 'recommendations'
        ])
    
    def submit_for_review(self, user):
        """Submit assessment for review."""
        if self.status != AssessmentStatus.DRAFT:
            raise ValidationError("Only draft assessments can be submitted for review")
        
        self.refresh_calculated_fields()
        self.status = AssessmentStatus.IN_REVIEW
        self.submitted_at = datetime.now()
        self.save()
    
    def approve(self, user):
        """Approve the assessment."""
        if self.status != AssessmentStatus.IN_REVIEW:
            raise ValidationError("Only assessments in review can be approved")
        
        self.status = AssessmentStatus.APPROVED
        self.approver = user
        self.approved_at = datetime.now()
        self.increment_minor(user)  # Version increment for approval
        self.save()
    
    def reject(self, user, reason: str = ''):
        """Reject the assessment."""
        if self.status not in [AssessmentStatus.IN_REVIEW, AssessmentStatus.DRAFT]:
            raise ValidationError("Assessment cannot be rejected in current status")
        
        self.status = AssessmentStatus.REJECTED
        if reason:
            self.recommendations = f"REJECTION REASON: {reason}\n\n{self.recommendations}"
        self.save()


class AssessmentMetric(BaseAssessmentModel):
    """
    Individual assessment metrics with scores, weights, and justifications.
    
    Implements the weighted scoring system with 1-5 scores and 1-5 importance weights.
    """
    
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='assessment_metrics',
        help_text="Assessment this metric belongs to"
    )
    
    # Metric identification
    metric_name = models.CharField(
        max_length=100,
        help_text="Name of the assessment metric"
    )
    
    metric_description = models.TextField(
        blank=True,
        help_text="Detailed description of what this metric measures"
    )
    
    category = models.CharField(
        max_length=20,
        choices=MetricCategory.choices,
        help_text="Category this metric belongs to"
    )
    
    # Scoring
    score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Performance rating from 1 (poor) to 5 (excellent)"
    )
    
    weight = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Importance weighting from 1 (minor) to 5 (critical)"
    )
    
    # Documentation
    justification = models.TextField(
        help_text="Justification for the score given"
    )
    
    evidence_sources = models.TextField(
        blank=True,
        help_text="Sources of evidence supporting the score"
    )
    
    # Benchmarking
    industry_benchmark = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Industry benchmark score for comparison"
    )
    
    peer_comparison = models.TextField(
        blank=True,
        help_text="Comparison with peer companies/schemes"
    )
    
    # Additional metadata
    assessment_method = models.CharField(
        max_length=100,
        blank=True,
        choices=[
            ('FINANCIAL_ANALYSIS', 'Financial Statement Analysis'),
            ('SITE_VISIT', 'Site Visit'),
            ('INTERVIEW', 'Management Interview'),
            ('DOCUMENT_REVIEW', 'Document Review'),
            ('MARKET_RESEARCH', 'Market Research'),
            ('REFERENCE_CHECK', 'Reference Check'),
            ('TECHNICAL_REVIEW', 'Technical Review'),
            ('OTHER', 'Other Method'),
        ],
        help_text="Method used to assess this metric"
    )
    
    confidence_level = models.CharField(
        max_length=10,
        choices=[
            ('HIGH', 'High Confidence'),
            ('MEDIUM', 'Medium Confidence'),
            ('LOW', 'Low Confidence'),
        ],
        default='MEDIUM',
        help_text="Confidence level in the assessment"
    )
    
    class Meta:
        db_table = 'assessment_metrics_enhanced'
        verbose_name = 'Assessment Metric'
        verbose_name_plural = 'Assessment Metrics'
        unique_together = ['assessment', 'metric_name']
        ordering = ['category', 'metric_name']
    
    def __str__(self) -> str:
        return f"{self.metric_name}: {self.score}×{self.weight}={self.weighted_score}"
    
    @property
    def weighted_score(self) -> int:
        """Calculate weighted score (score × weight)."""
        return self.score * self.weight
    
    @property
    def max_weighted_score(self) -> int:
        """Maximum possible weighted score (5 × weight)."""
        return 5 * self.weight
    
    @property
    def score_percentage(self) -> float:
        """Score as percentage of maximum possible."""
        return round((self.weighted_score / self.max_weighted_score) * 100, 2)
    
    @property
    def performance_level(self) -> str:
        """Descriptive performance level based on score."""
        if self.score >= 5:
            return "Excellent"
        elif self.score >= 4:
            return "Good"
        elif self.score >= 3:
            return "Satisfactory"
        elif self.score >= 2:
            return "Needs Improvement"
        else:
            return "Poor"
    
    @property
    def importance_level(self) -> str:
        """Descriptive importance level based on weight."""
        if self.weight >= 5:
            return "Critical"
        elif self.weight >= 4:
            return "Very Important"
        elif self.weight >= 3:
            return "Important"
        elif self.weight >= 2:
            return "Moderate"
        else:
            return "Minor"
    
    def clean(self):
        """Validate assessment metric."""
        super().clean()
        
        # Ensure metric name is unique within assessment
        if self.assessment_id:
            existing = AssessmentMetric.objects.filter(
                assessment=self.assessment,
                metric_name=self.metric_name
            ).exclude(pk=self.pk)
            
            if existing.exists():
                raise ValidationError(
                    f"Metric '{self.metric_name}' already exists in this assessment"
                )


class AssessmentTemplate(BaseAssessmentModel):
    """
    Templates for standardized assessments.
    
    Defines standard metric sets for consistent assessment across partners/schemes.
    """
    
    template_name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Name of the assessment template"
    )
    
    description = models.TextField(
        help_text="Description of the template and its purpose"
    )
    
    assessment_type = models.CharField(
        max_length=20,
        choices=AssessmentType.choices,
        help_text="Type of assessment this template is for"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this template is currently active"
    )
    
    version = models.CharField(
        max_length=20,
        default='1.0',
        help_text="Template version"
    )
    
    class Meta:
        db_table = 'assessment_templates'
        verbose_name = 'Assessment Template'
        verbose_name_plural = 'Assessment Templates'
        ordering = ['template_name']
    
    def __str__(self) -> str:
        return f"{self.template_name} v{self.version}"


class MetricTemplate(BaseAssessmentModel):
    """
    Standard metric definitions for assessment templates.
    """
    
    template = models.ForeignKey(
        AssessmentTemplate,
        on_delete=models.CASCADE,
        related_name='metric_templates',
        help_text="Assessment template this metric belongs to"
    )
    
    metric_name = models.CharField(
        max_length=100,
        help_text="Standard name for this metric"
    )
    
    metric_description = models.TextField(
        help_text="Standard description of what this metric measures"
    )
    
    category = models.CharField(
        max_length=20,
        choices=MetricCategory.choices,
        help_text="Category this metric belongs to"
    )
    
    default_weight = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Default importance weighting"
    )
    
    assessment_guidelines = models.TextField(
        help_text="Guidelines for assessing this metric"
    )
    
    scoring_criteria = models.JSONField(
        default=dict,
        help_text="Detailed scoring criteria for each score level (1-5)"
    )
    
    is_mandatory = models.BooleanField(
        default=True,
        help_text="Whether this metric is mandatory in assessments"
    )
    
    display_order = models.PositiveIntegerField(
        default=0,
        help_text="Display order within category"
    )
    
    class Meta:
        db_table = 'metric_templates'
        verbose_name = 'Metric Template'
        verbose_name_plural = 'Metric Templates'
        unique_together = ['template', 'metric_name']
        ordering = ['category', 'display_order', 'metric_name']
    
    def __str__(self) -> str:
        return f"{self.metric_name} (Weight: {self.default_weight})"