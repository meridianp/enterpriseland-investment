
import django_filters
from .models import Assessment, DevelopmentPartner, AssessmentStatus, AssessmentDecision

class AssessmentFilter(django_filters.FilterSet):
    """Filter for assessments"""
    status = django_filters.ChoiceFilter(choices=AssessmentStatus.choices)
    decision = django_filters.ChoiceFilter(choices=AssessmentDecision.choices)
    assessment_type = django_filters.ChoiceFilter(choices=[
        ('PARTNER', 'Development Partner'),
        ('SCHEME', 'PBSA Scheme'),
        ('COMBINED', 'Combined Assessment')
    ])
    created_after = django_filters.DateFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateFilter(field_name='created_at', lookup_expr='lte')
    total_score_min = django_filters.NumberFilter(field_name='total_score', lookup_expr='gte')
    total_score_max = django_filters.NumberFilter(field_name='total_score', lookup_expr='lte')
    partner_name = django_filters.CharFilter(field_name='partner__company_name', lookup_expr='icontains')
    scheme_name = django_filters.CharFilter(field_name='scheme__scheme_name', lookup_expr='icontains')
    
    class Meta:
        model = Assessment
        fields = [
            'status', 'decision', 'assessment_type', 'created_after',
            'created_before', 'total_score_min', 'total_score_max',
            'partner_name', 'scheme_name'
        ]

class DevelopmentPartnerFilter(django_filters.FilterSet):
    """Filter for development partners"""
    country = django_filters.CharFilter(field_name='headquarter_country')
    year_established_min = django_filters.NumberFilter(field_name='year_established', lookup_expr='gte')
    year_established_max = django_filters.NumberFilter(field_name='year_established', lookup_expr='lte')
    min_employees = django_filters.NumberFilter(field_name='number_of_employees', lookup_expr='gte')
    max_employees = django_filters.NumberFilter(field_name='number_of_employees', lookup_expr='lte')
    has_pbsa_experience = django_filters.BooleanFilter(method='filter_pbsa_experience')
    
    class Meta:
        model = DevelopmentPartner
        fields = [
            'country', 'year_established_min', 'year_established_max',
            'min_employees', 'max_employees', 'has_pbsa_experience'
        ]
    
    def filter_pbsa_experience(self, queryset, name, value):
        if value:
            return queryset.filter(completed_pbsa_schemes__gt=0)
        return queryset.filter(completed_pbsa_schemes__isnull=True)
