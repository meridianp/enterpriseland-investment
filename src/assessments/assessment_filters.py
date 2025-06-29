"""
Django filters for the CASA Assessment Framework.

Provides comprehensive filtering capabilities for assessments, metrics,
and related models with proper field validation and query optimization.
"""

import django_filters
from django.db.models import Q, Count
from datetime import date, datetime, timedelta

from .assessment_models import (
    Assessment, AssessmentMetric, AssessmentTemplate, MetricTemplate,
    AssessmentType, MetricCategory, DecisionBand
)
from .enums import AssessmentStatus, RiskLevel
from .partner_models import DevelopmentPartner


class AssessmentFilter(django_filters.FilterSet):
    """
    Comprehensive filter set for Assessment model.
    
    Provides filtering by status, type, dates, scores, partners,
    and various assessment characteristics.
    """
    
    # Basic filters
    assessment_type = django_filters.ChoiceFilter(
        choices=AssessmentType.choices,
        help_text="Filter by assessment type"
    )
    
    status = django_filters.MultipleChoiceFilter(
        choices=AssessmentStatus.choices,
        help_text="Filter by assessment status (multiple values allowed)"
    )
    
    decision_band = django_filters.ChoiceFilter(
        choices=DecisionBand.choices,
        help_text="Filter by decision band"
    )
    
    # Date filters
    assessment_date = django_filters.DateFilter(
        help_text="Filter by exact assessment date"
    )
    
    assessment_date_from = django_filters.DateFilter(
        field_name='assessment_date',
        lookup_expr='gte',
        help_text="Filter assessments from this date onwards"
    )
    
    assessment_date_to = django_filters.DateFilter(
        field_name='assessment_date',
        lookup_expr='lte',
        help_text="Filter assessments up to this date"
    )
    
    created_from = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte',
        help_text="Filter assessments created from this datetime"
    )
    
    created_to = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte',
        help_text="Filter assessments created up to this datetime"
    )
    
    # Score filters
    score_min = django_filters.NumberFilter(
        field_name='score_percentage',
        lookup_expr='gte',
        help_text="Minimum score percentage"
    )
    
    score_max = django_filters.NumberFilter(
        field_name='score_percentage',
        lookup_expr='lte',
        help_text="Maximum score percentage"
    )
    
    total_score_min = django_filters.NumberFilter(
        field_name='total_weighted_score',
        lookup_expr='gte',
        help_text="Minimum total weighted score"
    )
    
    total_score_max = django_filters.NumberFilter(
        field_name='total_weighted_score',
        lookup_expr='lte',
        help_text="Maximum total weighted score"
    )
    
    # Partner filters
    partner = django_filters.ModelChoiceFilter(
        queryset=DevelopmentPartner.objects.all(),
        help_text="Filter by specific partner"
    )
    
    partner_name = django_filters.CharFilter(
        field_name='partner__company_name',
        lookup_expr='icontains',
        help_text="Filter by partner company name (case insensitive)"
    )
    
    # Complex filters
    has_metrics = django_filters.BooleanFilter(
        method='filter_has_metrics',
        help_text="Filter assessments that have/don't have metrics"
    )
    
    recent_days = django_filters.NumberFilter(
        method='filter_recent_days',
        help_text="Filter assessments created in the last N days"
    )
    
    high_priority = django_filters.BooleanFilter(
        method='filter_high_priority',
        help_text="Filter high priority assessments (score < 125 or high risk)"
    )
    
    class Meta:
        model = Assessment
        fields = []
    
    def filter_has_metrics(self, queryset, name, value):
        """Filter assessments that have or don't have metrics."""
        if value is True:
            return queryset.filter(assessment_metrics__isnull=False).distinct()
        elif value is False:
            return queryset.filter(assessment_metrics__isnull=True)
        return queryset
    
    def filter_recent_days(self, queryset, name, value):
        """Filter assessments created in the last N days."""
        if value and value > 0:
            cutoff_date = datetime.now() - timedelta(days=value)
            return queryset.filter(created_at__gte=cutoff_date)
        return queryset
    
    def filter_high_priority(self, queryset, name, value):
        """Filter high priority assessments needing immediate attention."""
        if value is True:
            return queryset.filter(
                Q(total_weighted_score__lt=125) |  # Reject band
                Q(decision_band=DecisionBand.REJECT) |
                Q(status=AssessmentStatus.REJECTED)
            )
        return queryset


class AssessmentMetricFilter(django_filters.FilterSet):
    """
    Filter set for AssessmentMetric model.
    
    Provides filtering by assessment, category, scores, weights,
    and performance characteristics.
    """
    
    # Basic filters
    assessment = django_filters.UUIDFilter(
        field_name='assessment__id',
        help_text="Filter by assessment ID"
    )
    
    category = django_filters.MultipleChoiceFilter(
        choices=MetricCategory.choices,
        help_text="Filter by metric category (multiple values allowed)"
    )
    
    # Score filters
    score = django_filters.NumberFilter(
        help_text="Filter by exact score"
    )
    
    score_min = django_filters.NumberFilter(
        field_name='score',
        lookup_expr='gte',
        help_text="Minimum score (1-5)"
    )
    
    score_max = django_filters.NumberFilter(
        field_name='score',
        lookup_expr='lte',
        help_text="Maximum score (1-5)"
    )
    
    # Weight filters
    weight = django_filters.NumberFilter(
        help_text="Filter by exact weight"
    )
    
    weight_min = django_filters.NumberFilter(
        field_name='weight',
        lookup_expr='gte',
        help_text="Minimum weight (1-5)"
    )
    
    weight_max = django_filters.NumberFilter(
        field_name='weight',
        lookup_expr='lte',
        help_text="Maximum weight (1-5)"
    )
    
    class Meta:
        model = AssessmentMetric
        fields = []