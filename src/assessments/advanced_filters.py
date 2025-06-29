"""
Advanced filtering for the CASA Due Diligence Platform advanced features.

Provides comprehensive filtering capabilities for regulatory compliance,
performance metrics, ESG assessments, and audit trails with proper
validation and optimized queries.
"""

from django_filters import rest_framework as filters
from django.db.models import Q

from .advanced_models import (
    RegulatoryCompliance, PerformanceMetric, ESGAssessment, AuditTrail
)
from .enums import RiskLevel


class RegulatoryComplianceFilter(filters.FilterSet):
    """Comprehensive filtering for regulatory compliance records."""
    
    # Entity filtering
    partner = filters.UUIDFilter(
        field_name='partner__id',
        help_text="Filter by partner ID"
    )
    
    scheme = filters.UUIDFilter(
        field_name='scheme__id',
        help_text="Filter by scheme ID"
    )
    
    # Jurisdiction and framework
    jurisdiction = filters.CharFilter(
        field_name='jurisdiction',
        lookup_expr='iexact',
        help_text="Filter by jurisdiction (ISO country code)"
    )
    
    framework = filters.CharFilter(
        field_name='regulatory_framework',
        lookup_expr='icontains',
        help_text="Filter by regulatory framework (partial match)"
    )
    
    regulatory_body = filters.CharFilter(
        field_name='regulatory_body',
        lookup_expr='icontains',
        help_text="Filter by regulatory body name"
    )
    
    # Compliance status and risk
    status = filters.ChoiceFilter(
        field_name='compliance_status',
        choices=[
            ('compliant', 'Fully Compliant'),
            ('partial', 'Partially Compliant'),
            ('non_compliant', 'Non-Compliant'),
            ('pending', 'Compliance Pending'),
            ('exempt', 'Exempt'),
            ('not_applicable', 'Not Applicable'),
        ],
        help_text="Filter by compliance status"
    )
    
    category = filters.ChoiceFilter(
        field_name='compliance_category',
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
        help_text="Filter by compliance category"
    )
    
    risk_level = filters.ChoiceFilter(
        field_name='compliance_risk_level',
        choices=RiskLevel.choices,
        help_text="Filter by compliance risk level"
    )
    
    # Date filtering
    compliance_date_from = filters.DateFilter(
        field_name='compliance_date',
        lookup_expr='gte',
        help_text="Compliance achieved from date (YYYY-MM-DD)"
    )
    
    compliance_date_to = filters.DateFilter(
        field_name='compliance_date',
        lookup_expr='lte',
        help_text="Compliance achieved to date (YYYY-MM-DD)"
    )
    
    expiry_date_from = filters.DateFilter(
        field_name='expiry_date',
        lookup_expr='gte',
        help_text="Compliance expires from date (YYYY-MM-DD)"
    )
    
    expiry_date_to = filters.DateFilter(
        field_name='expiry_date',
        lookup_expr='lte',
        help_text="Compliance expires to date (YYYY-MM-DD)"
    )
    
    next_review_from = filters.DateFilter(
        field_name='next_review_date',
        lookup_expr='gte',
        help_text="Next review from date (YYYY-MM-DD)"
    )
    
    next_review_to = filters.DateFilter(
        field_name='next_review_date',
        lookup_expr='lte',
        help_text="Next review to date (YYYY-MM-DD)"
    )
    
    # Special filters
    expiring_soon = filters.BooleanFilter(
        method='filter_expiring_soon',
        help_text="Filter for compliance expiring within 90 days"
    )
    
    high_risk = filters.BooleanFilter(
        method='filter_high_risk',
        help_text="Filter for high-risk compliance items"
    )
    
    requires_action = filters.BooleanFilter(
        method='filter_requires_action',
        help_text="Filter for compliance requiring attention"
    )
    
    # Financial impact
    min_financial_impact = filters.NumberFilter(
        field_name='financial_impact_amount',
        lookup_expr='gte',
        help_text="Minimum financial impact amount"
    )
    
    max_financial_impact = filters.NumberFilter(
        field_name='financial_impact_amount',
        lookup_expr='lte',
        help_text="Maximum financial impact amount"
    )
    
    # Version control
    is_published = filters.BooleanFilter(
        help_text="Filter by publication status"
    )
    
    approved_by = filters.UUIDFilter(
        field_name='approved_by__id',
        help_text="Filter by approver user ID"
    )
    
    class Meta:
        model = RegulatoryCompliance
        fields = []
    
    def filter_expiring_soon(self, queryset, name, value):
        """Filter for compliance expiring within 90 days."""
        if value:
            from datetime import date, timedelta
            cutoff_date = date.today() + timedelta(days=90)
            return queryset.filter(
                expiry_date__lte=cutoff_date,
                expiry_date__isnull=False,
                compliance_status__in=['compliant', 'partial']
            )
        return queryset
    
    def filter_high_risk(self, queryset, name, value):
        """Filter for high-risk compliance items."""
        if value:
            return queryset.filter(
                Q(compliance_risk_level=RiskLevel.HIGH) |
                Q(compliance_status='non_compliant') |
                Q(financial_impact_amount__gte=100000)
            )
        return queryset
    
    def filter_requires_action(self, queryset, name, value):
        """Filter for compliance requiring immediate attention."""
        if value:
            from datetime import date, timedelta
            return queryset.filter(
                Q(compliance_status='non_compliant') |
                Q(compliance_status='pending') |
                Q(expiry_date__lte=date.today() + timedelta(days=30))
            )
        return queryset


class PerformanceMetricFilter(filters.FilterSet):
    """Comprehensive filtering for performance metrics."""
    
    # Entity filtering
    partner = filters.UUIDFilter(
        field_name='partner__id',
        help_text="Filter by partner ID"
    )
    
    scheme = filters.UUIDFilter(
        field_name='scheme__id',
        help_text="Filter by scheme ID"
    )
    
    assessment = filters.UUIDFilter(
        field_name='assessment__id',
        help_text="Filter by assessment ID"
    )
    
    # Metric identification
    metric_name = filters.CharFilter(
        lookup_expr='icontains',
        help_text="Filter by metric name (partial match)"
    )
    
    metric_category = filters.ChoiceFilter(
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
        help_text="Filter by metric category"
    )
    
    data_source = filters.CharFilter(
        lookup_expr='icontains',
        help_text="Filter by data source"
    )
    
    # Date and frequency filtering
    measurement_date_from = filters.DateFilter(
        field_name='measurement_date',
        lookup_expr='gte',
        help_text="Measurements from date (YYYY-MM-DD)"
    )
    
    measurement_date_to = filters.DateFilter(
        field_name='measurement_date',
        lookup_expr='lte',
        help_text="Measurements to date (YYYY-MM-DD)"
    )
    
    frequency = filters.ChoiceFilter(
        field_name='measurement_frequency',
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('annually', 'Annually'),
            ('ad_hoc', 'Ad Hoc'),
        ],
        help_text="Filter by measurement frequency"
    )
    
    # Performance analysis
    trend = filters.ChoiceFilter(
        field_name='trend_direction',
        choices=[
            ('improving', 'Improving'),
            ('stable', 'Stable'),
            ('declining', 'Declining'),
            ('volatile', 'Volatile'),
        ],
        help_text="Filter by trend direction"
    )
    
    meeting_target = filters.BooleanFilter(
        method='filter_meeting_target',
        help_text="Filter metrics meeting their targets"
    )
    
    exceeding_benchmark = filters.BooleanFilter(
        method='filter_exceeding_benchmark',
        help_text="Filter metrics exceeding industry benchmark"
    )
    
    action_required = filters.BooleanFilter(
        help_text="Filter metrics requiring action"
    )
    
    # Value and variance filtering
    min_value = filters.NumberFilter(
        field_name='metric_value',
        lookup_expr='gte',
        help_text="Minimum metric value"
    )
    
    max_value = filters.NumberFilter(
        field_name='metric_value',
        lookup_expr='lte',
        help_text="Maximum metric value"
    )
    
    target_variance_threshold = filters.NumberFilter(
        method='filter_target_variance',
        help_text="Filter by absolute variance from target (%)"
    )
    
    # Data quality
    min_quality_score = filters.NumberFilter(
        field_name='data_quality_score',
        lookup_expr='gte',
        help_text="Minimum data quality score (1-5)"
    )
    
    # Version control
    is_published = filters.BooleanFilter(
        help_text="Filter by publication status"
    )
    
    class Meta:
        model = PerformanceMetric
        fields = []
    
    def filter_meeting_target(self, queryset, name, value):
        """Filter metrics that are meeting their targets."""
        if value is not None:
            if value:
                return queryset.filter(
                    target_value__isnull=False,
                    variance_from_target_pct__isnull=False,
                    variance_from_target_pct__gte=-10,
                    variance_from_target_pct__lte=10
                )
            else:
                return queryset.filter(
                    Q(target_value__isnull=True) |
                    Q(variance_from_target_pct__isnull=True) |
                    Q(variance_from_target_pct__lt=-10) |
                    Q(variance_from_target_pct__gt=10)
                )
        return queryset
    
    def filter_exceeding_benchmark(self, queryset, name, value):
        """Filter metrics exceeding industry benchmark."""
        if value is not None:
            if value:
                return queryset.filter(
                    benchmark_value__isnull=False,
                    variance_from_benchmark_pct__gt=0
                )
            else:
                return queryset.filter(
                    Q(benchmark_value__isnull=True) |
                    Q(variance_from_benchmark_pct__lte=0)
                )
        return queryset
    
    def filter_target_variance(self, queryset, name, value):
        """Filter by absolute variance from target."""
        if value is not None:
            return queryset.filter(
                variance_from_target_pct__isnull=False
            ).extra(
                where=['ABS(variance_from_target_pct) >= %s'],
                params=[value]
            )
        return queryset


class ESGAssessmentFilter(filters.FilterSet):
    """Comprehensive filtering for ESG assessments."""
    
    # Entity filtering
    partner = filters.UUIDFilter(
        field_name='partner__id',
        help_text="Filter by partner ID"
    )
    
    scheme = filters.UUIDFilter(
        field_name='scheme__id',
        help_text="Filter by scheme ID"
    )
    
    # Assessment framework and period
    framework = filters.ChoiceFilter(
        field_name='assessment_framework',
        choices=[
            ('gri', 'Global Reporting Initiative (GRI)'),
            ('sasb', 'Sustainability Accounting Standards Board (SASB)'),
            ('tcfd', 'Task Force on Climate-related Financial Disclosures'),
            ('un_sdg', 'UN Sustainable Development Goals'),
            ('breeam', 'BREEAM Building Assessment'),
            ('leed', 'LEED Green Building'),
            ('custom', 'Custom Framework'),
        ],
        help_text="Filter by ESG framework"
    )
    
    period_start_from = filters.DateFilter(
        field_name='assessment_period_start',
        lookup_expr='gte',
        help_text="Assessment period start from date (YYYY-MM-DD)"
    )
    
    period_start_to = filters.DateFilter(
        field_name='assessment_period_start',
        lookup_expr='lte',
        help_text="Assessment period start to date (YYYY-MM-DD)"
    )
    
    period_end_from = filters.DateFilter(
        field_name='assessment_period_end',
        lookup_expr='gte',
        help_text="Assessment period end from date (YYYY-MM-DD)"
    )
    
    period_end_to = filters.DateFilter(
        field_name='assessment_period_end',
        lookup_expr='lte',
        help_text="Assessment period end to date (YYYY-MM-DD)"
    )
    
    # ESG Scores
    min_environmental_score = filters.NumberFilter(
        field_name='environmental_score',
        lookup_expr='gte',
        help_text="Minimum environmental score (1-5)"
    )
    
    max_environmental_score = filters.NumberFilter(
        field_name='environmental_score',
        lookup_expr='lte',
        help_text="Maximum environmental score (1-5)"
    )
    
    min_social_score = filters.NumberFilter(
        field_name='social_score',
        lookup_expr='gte',
        help_text="Minimum social score (1-5)"
    )
    
    max_social_score = filters.NumberFilter(
        field_name='social_score',
        lookup_expr='lte',
        help_text="Maximum social score (1-5)"
    )
    
    min_governance_score = filters.NumberFilter(
        field_name='governance_score',
        lookup_expr='gte',
        help_text="Minimum governance score (1-5)"
    )
    
    max_governance_score = filters.NumberFilter(
        field_name='governance_score',
        lookup_expr='lte',
        help_text="Maximum governance score (1-5)"
    )
    
    min_overall_score = filters.NumberFilter(
        field_name='overall_esg_score',
        lookup_expr='gte',
        help_text="Minimum overall ESG score"
    )
    
    max_overall_score = filters.NumberFilter(
        field_name='overall_esg_score',
        lookup_expr='lte',
        help_text="Maximum overall ESG score"
    )
    
    # ESG Rating
    esg_rating = filters.ChoiceFilter(
        choices=[
            ('AAA', 'AAA (Leader)'),
            ('AA', 'AA (Leader)'),
            ('A', 'A (Average)'),
            ('BBB', 'BBB (Average)'),
            ('BB', 'BB (Average)'),
            ('B', 'B (Laggard)'),
            ('CCC', 'CCC (Laggard)'),
        ],
        help_text="Filter by ESG rating"
    )
    
    # Environmental metrics
    energy_efficiency = filters.ChoiceFilter(
        field_name='energy_efficiency_rating',
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
        help_text="Filter by energy efficiency rating"
    )
    
    min_renewable_energy = filters.NumberFilter(
        field_name='renewable_energy_pct',
        lookup_expr='gte',
        help_text="Minimum renewable energy percentage"
    )
    
    max_carbon_footprint = filters.NumberFilter(
        field_name='carbon_footprint_tonnes',
        lookup_expr='lte',
        help_text="Maximum carbon footprint (tonnes CO2)"
    )
    
    min_waste_diversion = filters.NumberFilter(
        field_name='waste_diversion_rate_pct',
        lookup_expr='gte',
        help_text="Minimum waste diversion rate (%)"
    )
    
    # Social metrics
    min_student_satisfaction = filters.NumberFilter(
        field_name='student_satisfaction_score',
        lookup_expr='gte',
        help_text="Minimum student satisfaction score"
    )
    
    min_local_employment = filters.NumberFilter(
        field_name='local_employment_pct',
        lookup_expr='gte',
        help_text="Minimum local employment percentage"
    )
    
    max_safety_incidents = filters.NumberFilter(
        field_name='health_safety_incidents',
        lookup_expr='lte',
        help_text="Maximum health and safety incidents"
    )
    
    # Governance metrics
    min_board_diversity = filters.NumberFilter(
        field_name='board_diversity_pct',
        lookup_expr='gte',
        help_text="Minimum board diversity percentage"
    )
    
    anti_corruption = filters.BooleanFilter(
        field_name='anti_corruption_policies',
        help_text="Filter by anti-corruption policy presence"
    )
    
    min_transparency_score = filters.NumberFilter(
        field_name='transparency_score',
        lookup_expr='gte',
        help_text="Minimum transparency score (1-5)"
    )
    
    # Special filters
    high_performers = filters.BooleanFilter(
        method='filter_high_performers',
        help_text="Filter for high ESG performers (AA+ rating)"
    )
    
    needs_improvement = filters.BooleanFilter(
        method='filter_needs_improvement',
        help_text="Filter assessments with improvement opportunities"
    )
    
    latest_only = filters.BooleanFilter(
        method='filter_latest_only',
        help_text="Filter for latest assessment per entity"
    )
    
    # Version control
    is_published = filters.BooleanFilter(
        help_text="Filter by publication status"
    )
    
    approved_by = filters.UUIDFilter(
        field_name='approved_by__id',
        help_text="Filter by approver user ID"
    )
    
    class Meta:
        model = ESGAssessment
        fields = []
    
    def filter_high_performers(self, queryset, name, value):
        """Filter for high ESG performers."""
        if value:
            return queryset.filter(
                esg_rating__in=['AAA', 'AA'],
                overall_esg_score__gte=4.0
            )
        return queryset
    
    def filter_needs_improvement(self, queryset, name, value):
        """Filter assessments with improvement opportunities."""
        if value:
            return queryset.filter(
                Q(environmental_score__lte=3) |
                Q(social_score__lte=3) |
                Q(governance_score__lte=3) |
                Q(esg_rating__in=['B', 'CCC'])
            )
        return queryset
    
    def filter_latest_only(self, queryset, name, value):
        """Filter for latest assessment per entity."""
        if value:
            # This is a complex filter that would need subquery optimization
            # For now, we'll return the queryset ordered by date
            return queryset.order_by(
                'partner', 'scheme', '-assessment_period_end'
            ).distinct('partner', 'scheme')
        return queryset


class AuditTrailFilter(filters.FilterSet):
    """Comprehensive filtering for audit trail entries."""
    
    # Entity identification
    entity_type = filters.CharFilter(
        lookup_expr='iexact',
        help_text="Filter by entity type"
    )
    
    entity_id = filters.UUIDFilter(
        help_text="Filter by specific entity ID"
    )
    
    # Action and user filtering
    action_type = filters.ChoiceFilter(
        choices=[
            ('create', 'Created'),
            ('update', 'Updated'),
            ('delete', 'Deleted'),
            ('approve', 'Approved'),
            ('reject', 'Rejected'),
            ('publish', 'Published'),
            ('archive', 'Archived'),
        ],
        help_text="Filter by action type"
    )
    
    user = filters.UUIDFilter(
        field_name='user__id',
        help_text="Filter by user ID"
    )
    
    user_email = filters.CharFilter(
        field_name='user__email',
        lookup_expr='icontains',
        help_text="Filter by user email (partial match)"
    )
    
    user_role = filters.ChoiceFilter(
        field_name='user__role',
        choices=[
            ('admin', 'Administrator'),
            ('manager', 'Manager'),
            ('analyst', 'Analyst'),
            ('assessor', 'Assessor'),
            ('viewer', 'Viewer'),
            ('partner', 'Partner'),
        ],
        help_text="Filter by user role"
    )
    
    # Date filtering
    date_from = filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte',
        help_text="Filter from date/time (YYYY-MM-DD HH:MM:SS)"
    )
    
    date_to = filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte',
        help_text="Filter to date/time (YYYY-MM-DD HH:MM:SS)"
    )
    
    today_only = filters.BooleanFilter(
        method='filter_today_only',
        help_text="Filter for today's activities only"
    )
    
    last_week = filters.BooleanFilter(
        method='filter_last_week',
        help_text="Filter for last 7 days of activities"
    )
    
    # Risk and impact filtering
    risk_level = filters.ChoiceFilter(
        field_name='risk_assessment',
        choices=RiskLevel.choices,
        help_text="Filter by risk assessment level"
    )
    
    high_risk_only = filters.BooleanFilter(
        method='filter_high_risk_only',
        help_text="Filter for high-risk activities only"
    )
    
    # Network and context
    ip_address = filters.CharFilter(
        help_text="Filter by IP address"
    )
    
    has_justification = filters.BooleanFilter(
        method='filter_has_justification',
        help_text="Filter for entries with business justification"
    )
    
    # Search functionality
    search = filters.CharFilter(
        method='filter_search',
        help_text="Search in summary, justification, and changed fields"
    )
    
    class Meta:
        model = AuditTrail
        fields = []
    
    def filter_today_only(self, queryset, name, value):
        """Filter for today's activities."""
        if value:
            from django.utils import timezone
            today = timezone.now().date()
            return queryset.filter(created_at__date=today)
        return queryset
    
    def filter_last_week(self, queryset, name, value):
        """Filter for last 7 days of activities."""
        if value:
            from django.utils import timezone
            from datetime import timedelta
            week_ago = timezone.now() - timedelta(days=7)
            return queryset.filter(created_at__gte=week_ago)
        return queryset
    
    def filter_high_risk_only(self, queryset, name, value):
        """Filter for high-risk activities."""
        if value:
            return queryset.filter(
                Q(risk_assessment=RiskLevel.HIGH) |
                Q(action_type='delete') |
                Q(action_type='archive')
            )
        return queryset
    
    def filter_has_justification(self, queryset, name, value):
        """Filter for entries with business justification."""
        if value is not None:
            if value:
                return queryset.exclude(
                    Q(business_justification='') |
                    Q(business_justification__isnull=True)
                )
            else:
                return queryset.filter(
                    Q(business_justification='') |
                    Q(business_justification__isnull=True)
                )
        return queryset
    
    def filter_search(self, queryset, name, value):
        """Search across summary, justification, and changed fields."""
        if value:
            return queryset.filter(
                Q(change_summary__icontains=value) |
                Q(business_justification__icontains=value) |
                Q(changed_fields__icontains=value)
            )
        return queryset