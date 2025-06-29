"""
Filters for root aggregate models - Phase 6.

Provides comprehensive filtering capabilities for due diligence cases,
checklists, and timeline events with business logic filters.
"""

from django_filters import rest_framework as filters
from django.db.models import Q, Count
from datetime import date, timedelta

from .root_aggregate import DueDiligenceCase, CaseChecklistItem, CaseTimeline
from .enums import RiskLevel


class DueDiligenceCaseFilter(filters.FilterSet):
    """Comprehensive filtering for due diligence cases."""
    
    # Case identification
    case_reference = filters.CharFilter(
        lookup_expr='icontains',
        help_text="Filter by case reference (partial match)"
    )
    
    case_name = filters.CharFilter(
        lookup_expr='icontains',
        help_text="Filter by case name (partial match)"
    )
    
    case_type = filters.ChoiceFilter(
        choices=[
            ('partner_only', 'Partner Assessment Only'),
            ('scheme_only', 'Scheme Assessment Only'),
            ('full_dd', 'Full Due Diligence'),
            ('portfolio', 'Portfolio Assessment'),
        ],
        help_text="Filter by case type"
    )
    
    # Entity filtering
    primary_partner = filters.UUIDFilter(
        field_name='primary_partner__id',
        help_text="Filter by primary partner ID"
    )
    
    partner_name = filters.CharFilter(
        field_name='primary_partner__company_name',
        lookup_expr='icontains',
        help_text="Filter by partner name (partial match)"
    )
    
    scheme = filters.UUIDFilter(
        field_name='schemes__id',
        help_text="Filter by scheme ID"
    )
    
    scheme_name = filters.CharFilter(
        field_name='schemes__scheme_name',
        lookup_expr='icontains',
        help_text="Filter by scheme name (partial match)"
    )
    
    # Status and priority
    case_status = filters.MultipleChoiceFilter(
        choices=[
            ('initiated', 'Initiated'),
            ('data_collection', 'Data Collection'),
            ('analysis', 'Analysis in Progress'),
            ('review', 'Under Review'),
            ('decision_pending', 'Decision Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('on_hold', 'On Hold'),
            ('completed', 'Completed'),
            ('archived', 'Archived'),
        ],
        help_text="Filter by case status (multiple allowed)"
    )
    
    priority = filters.ChoiceFilter(
        choices=[
            ('urgent', 'Urgent'),
            ('high', 'High'),
            ('medium', 'Medium'),
            ('low', 'Low'),
        ],
        help_text="Filter by priority level"
    )
    
    # Date filtering
    created_from = filters.DateFilter(
        field_name='created_at',
        lookup_expr='date__gte',
        help_text="Created from date (YYYY-MM-DD)"
    )
    
    created_to = filters.DateFilter(
        field_name='created_at',
        lookup_expr='date__lte',
        help_text="Created to date (YYYY-MM-DD)"
    )
    
    target_from = filters.DateFilter(
        field_name='target_completion_date',
        lookup_expr='gte',
        help_text="Target completion from date (YYYY-MM-DD)"
    )
    
    target_to = filters.DateFilter(
        field_name='target_completion_date',
        lookup_expr='lte',
        help_text="Target completion to date (YYYY-MM-DD)"
    )
    
    completed_from = filters.DateFilter(
        field_name='actual_completion_date',
        lookup_expr='gte',
        help_text="Actual completion from date (YYYY-MM-DD)"
    )
    
    completed_to = filters.DateFilter(
        field_name='actual_completion_date',
        lookup_expr='lte',
        help_text="Actual completion to date (YYYY-MM-DD)"
    )
    
    # Team filtering
    lead_assessor = filters.UUIDFilter(
        field_name='lead_assessor__id',
        help_text="Filter by lead assessor ID"
    )
    
    team_member = filters.UUIDFilter(
        field_name='assessment_team__id',
        help_text="Filter by team member ID"
    )
    
    decision_maker = filters.UUIDFilter(
        field_name='decision_maker__id',
        help_text="Filter by decision maker ID"
    )
    
    # Financial filtering
    min_investment = filters.NumberFilter(
        field_name='total_investment_amount',
        lookup_expr='gte',
        help_text="Minimum total investment amount"
    )
    
    max_investment = filters.NumberFilter(
        field_name='total_investment_amount',
        lookup_expr='lte',
        help_text="Maximum total investment amount"
    )
    
    investment_currency = filters.ChoiceFilter(
        field_name='total_investment_currency',
        choices=[
            ('GBP', 'British Pound'),
            ('EUR', 'Euro'),
            ('USD', 'US Dollar'),
        ],
        help_text="Filter by investment currency"
    )
    
    # Risk and decision filtering
    overall_risk_level = filters.ChoiceFilter(
        choices=RiskLevel.choices,
        help_text="Filter by overall risk level"
    )
    
    final_decision = filters.ChoiceFilter(
        choices=[
            ('proceed', 'Proceed with Investment'),
            ('conditional', 'Proceed with Conditions'),
            ('decline', 'Decline Investment'),
            ('defer', 'Defer Decision'),
        ],
        help_text="Filter by final decision"
    )
    
    # Special filters
    is_overdue = filters.BooleanFilter(
        method='filter_overdue',
        help_text="Filter for overdue cases"
    )
    
    due_soon = filters.BooleanFilter(
        method='filter_due_soon',
        help_text="Filter for cases due within 7 days"
    )
    
    active_only = filters.BooleanFilter(
        method='filter_active',
        help_text="Filter for active cases only"
    )
    
    has_high_risk = filters.BooleanFilter(
        method='filter_high_risk',
        help_text="Filter for cases with high or critical risk"
    )
    
    needs_decision = filters.BooleanFilter(
        method='filter_needs_decision',
        help_text="Filter for cases pending decision"
    )
    
    my_cases = filters.BooleanFilter(
        method='filter_my_cases',
        help_text="Filter for cases where user is lead or team member"
    )
    
    # Search across multiple fields
    search = filters.CharFilter(
        method='filter_search',
        help_text="Search in case reference, name, and executive summary"
    )
    
    class Meta:
        model = DueDiligenceCase
        fields = []
    
    def filter_overdue(self, queryset, name, value):
        """Filter for overdue cases."""
        if value:
            return queryset.filter(
                target_completion_date__lt=date.today(),
                case_status__in=[
                    'initiated', 'data_collection', 'analysis', 
                    'review', 'decision_pending'
                ]
            )
        return queryset
    
    def filter_due_soon(self, queryset, name, value):
        """Filter for cases due within 7 days."""
        if value:
            week_from_now = date.today() + timedelta(days=7)
            return queryset.filter(
                target_completion_date__lte=week_from_now,
                target_completion_date__gte=date.today(),
                case_status__in=[
                    'initiated', 'data_collection', 'analysis', 
                    'review', 'decision_pending'
                ]
            )
        return queryset
    
    def filter_active(self, queryset, name, value):
        """Filter for active cases only."""
        if value:
            return queryset.filter(
                case_status__in=[
                    'initiated', 'data_collection', 'analysis', 
                    'review', 'decision_pending', 'on_hold'
                ]
            )
        else:
            return queryset.filter(
                case_status__in=['approved', 'rejected', 'completed', 'archived']
            )
        return queryset
    
    def filter_high_risk(self, queryset, name, value):
        """Filter for high-risk cases."""
        if value:
            return queryset.filter(
                overall_risk_level__in=[RiskLevel.HIGH, RiskLevel.CRITICAL]
            )
        return queryset
    
    def filter_needs_decision(self, queryset, name, value):
        """Filter for cases needing decision."""
        if value:
            return queryset.filter(
                case_status='decision_pending',
                final_decision__isnull=True
            )
        return queryset
    
    def filter_my_cases(self, queryset, name, value):
        """Filter for user's cases."""
        if value and hasattr(self.request, 'user'):
            return queryset.filter(
                Q(lead_assessor=self.request.user) |
                Q(assessment_team=self.request.user)
            ).distinct()
        return queryset
    
    def filter_search(self, queryset, name, value):
        """Search across multiple fields."""
        if value:
            return queryset.filter(
                Q(case_reference__icontains=value) |
                Q(case_name__icontains=value) |
                Q(executive_summary__icontains=value) |
                Q(primary_partner__company_name__icontains=value) |
                Q(schemes__scheme_name__icontains=value)
            ).distinct()
        return queryset


class CaseChecklistItemFilter(filters.FilterSet):
    """Filtering for case checklist items."""
    
    # Case filtering
    case = filters.UUIDFilter(
        field_name='case__id',
        help_text="Filter by case ID"
    )
    
    case_reference = filters.CharFilter(
        field_name='case__case_reference',
        lookup_expr='icontains',
        help_text="Filter by case reference"
    )
    
    # Category and status
    category = filters.MultipleChoiceFilter(
        choices=[
            ('documentation', 'Documentation'),
            ('financial', 'Financial Analysis'),
            ('legal', 'Legal Review'),
            ('technical', 'Technical Assessment'),
            ('compliance', 'Compliance Check'),
            ('esg', 'ESG Assessment'),
            ('market', 'Market Analysis'),
            ('operational', 'Operational Review'),
        ],
        help_text="Filter by category (multiple allowed)"
    )
    
    is_required = filters.BooleanFilter(
        help_text="Filter for required items only"
    )
    
    is_completed = filters.BooleanFilter(
        help_text="Filter by completion status"
    )
    
    completed_by = filters.UUIDFilter(
        field_name='completed_by__id',
        help_text="Filter by user who completed"
    )
    
    # Date filtering
    due_from = filters.DateFilter(
        field_name='due_date',
        lookup_expr='gte',
        help_text="Due from date (YYYY-MM-DD)"
    )
    
    due_to = filters.DateFilter(
        field_name='due_date',
        lookup_expr='lte',
        help_text="Due to date (YYYY-MM-DD)"
    )
    
    completed_from = filters.DateTimeFilter(
        field_name='completed_at',
        lookup_expr='gte',
        help_text="Completed from date/time"
    )
    
    completed_to = filters.DateTimeFilter(
        field_name='completed_at',
        lookup_expr='lte',
        help_text="Completed to date/time"
    )
    
    # Special filters
    is_overdue = filters.BooleanFilter(
        method='filter_overdue',
        help_text="Filter for overdue items"
    )
    
    due_this_week = filters.BooleanFilter(
        method='filter_due_this_week',
        help_text="Filter for items due this week"
    )
    
    incomplete_required = filters.BooleanFilter(
        method='filter_incomplete_required',
        help_text="Filter for incomplete required items"
    )
    
    has_attachments = filters.BooleanFilter(
        method='filter_has_attachments',
        help_text="Filter for items with attachments"
    )
    
    # Search
    search = filters.CharFilter(
        method='filter_search',
        help_text="Search in item name and description"
    )
    
    class Meta:
        model = CaseChecklistItem
        fields = []
    
    def filter_overdue(self, queryset, name, value):
        """Filter for overdue items."""
        if value:
            return queryset.filter(
                is_completed=False,
                due_date__lt=date.today()
            )
        return queryset
    
    def filter_due_this_week(self, queryset, name, value):
        """Filter for items due this week."""
        if value:
            week_from_now = date.today() + timedelta(days=7)
            return queryset.filter(
                is_completed=False,
                due_date__lte=week_from_now,
                due_date__gte=date.today()
            )
        return queryset
    
    def filter_incomplete_required(self, queryset, name, value):
        """Filter for incomplete required items."""
        if value:
            return queryset.filter(
                is_required=True,
                is_completed=False
            )
        return queryset
    
    def filter_has_attachments(self, queryset, name, value):
        """Filter for items with attachments."""
        if value is not None:
            if value:
                return queryset.exclude(attachments=[])
            else:
                return queryset.filter(attachments=[])
        return queryset
    
    def filter_search(self, queryset, name, value):
        """Search in item name and description."""
        if value:
            return queryset.filter(
                Q(item_name__icontains=value) |
                Q(description__icontains=value) |
                Q(notes__icontains=value)
            )
        return queryset


class CaseTimelineFilter(filters.FilterSet):
    """Filtering for case timeline events."""
    
    # Case filtering
    case = filters.UUIDFilter(
        field_name='case__id',
        help_text="Filter by case ID"
    )
    
    case_reference = filters.CharFilter(
        field_name='case__case_reference',
        lookup_expr='icontains',
        help_text="Filter by case reference"
    )
    
    # Event filtering
    event_type = filters.MultipleChoiceFilter(
        choices=[
            ('created', 'Case Created'),
            ('status_change', 'Status Changed'),
            ('assessment_added', 'Assessment Added'),
            ('document_uploaded', 'Document Uploaded'),
            ('team_change', 'Team Changed'),
            ('milestone', 'Milestone Reached'),
            ('issue_raised', 'Issue Raised'),
            ('issue_resolved', 'Issue Resolved'),
            ('decision', 'Decision Made'),
            ('note', 'Note Added'),
        ],
        help_text="Filter by event type (multiple allowed)"
    )
    
    is_significant = filters.BooleanFilter(
        help_text="Filter for significant events only"
    )
    
    created_by = filters.UUIDFilter(
        field_name='created_by__id',
        help_text="Filter by user who created event"
    )
    
    # Date filtering
    event_date_from = filters.DateTimeFilter(
        field_name='event_date',
        lookup_expr='gte',
        help_text="Event from date/time"
    )
    
    event_date_to = filters.DateTimeFilter(
        field_name='event_date',
        lookup_expr='lte',
        help_text="Event to date/time"
    )
    
    # Special filters
    today_only = filters.BooleanFilter(
        method='filter_today',
        help_text="Filter for today's events only"
    )
    
    this_week = filters.BooleanFilter(
        method='filter_this_week',
        help_text="Filter for this week's events"
    )
    
    this_month = filters.BooleanFilter(
        method='filter_this_month',
        help_text="Filter for this month's events"
    )
    
    decision_events = filters.BooleanFilter(
        method='filter_decision_events',
        help_text="Filter for decision-related events"
    )
    
    # Search
    search = filters.CharFilter(
        method='filter_search',
        help_text="Search in event title and description"
    )
    
    class Meta:
        model = CaseTimeline
        fields = []
    
    def filter_today(self, queryset, name, value):
        """Filter for today's events."""
        if value:
            today = date.today()
            return queryset.filter(event_date__date=today)
        return queryset
    
    def filter_this_week(self, queryset, name, value):
        """Filter for this week's events."""
        if value:
            today = date.today()
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            return queryset.filter(
                event_date__date__gte=start_of_week,
                event_date__date__lte=end_of_week
            )
        return queryset
    
    def filter_this_month(self, queryset, name, value):
        """Filter for this month's events."""
        if value:
            today = date.today()
            return queryset.filter(
                event_date__year=today.year,
                event_date__month=today.month
            )
        return queryset
    
    def filter_decision_events(self, queryset, name, value):
        """Filter for decision-related events."""
        if value:
            return queryset.filter(
                Q(event_type='decision') |
                Q(event_type='status_change', metadata__to_status='decision_pending') |
                Q(event_type='status_change', metadata__to_status='approved') |
                Q(event_type='status_change', metadata__to_status='rejected')
            )
        return queryset
    
    def filter_search(self, queryset, name, value):
        """Search in event title and description."""
        if value:
            return queryset.filter(
                Q(event_title__icontains=value) |
                Q(event_description__icontains=value)
            )
        return queryset