"""
Filters for the contacts app.

Provides Django-filter classes for advanced filtering of contacts,
activities, and lists with multi-tenant support.
"""

import django_filters
from django.db.models import Q
from django.contrib.postgres.search import SearchVector

from .models import Contact, ContactActivity, ContactList, ContactStatus, ContactType, ActivityType


class ContactFilter(django_filters.FilterSet):
    """
    Advanced filtering for contacts with search, status, scoring, and date ranges.
    
    Supports both simple and complex queries for the contact list view.
    """
    
    # Search filter
    search = django_filters.CharFilter(method='filter_search', label='Search')
    
    # Status and type filters
    status = django_filters.MultipleChoiceFilter(
        choices=ContactStatus.choices,
        label='Status'
    )
    contact_type = django_filters.ChoiceFilter(
        choices=ContactType.choices,
        label='Contact Type'
    )
    
    # Score range filter
    score_min = django_filters.NumberFilter(
        field_name='current_score',
        lookup_expr='gte',
        label='Minimum Score'
    )
    score_max = django_filters.NumberFilter(
        field_name='current_score',
        lookup_expr='lte',
        label='Maximum Score'
    )
    
    # Location filters
    city = django_filters.CharFilter(lookup_expr='icontains', label='City')
    country = django_filters.CharFilter(label='Country')
    
    # Assignment filter
    assigned_to = django_filters.UUIDFilter(field_name='assigned_to__id', label='Assigned To')
    unassigned = django_filters.BooleanFilter(
        method='filter_unassigned',
        label='Unassigned Only'
    )
    
    # Activity filters
    has_activity = django_filters.BooleanFilter(
        method='filter_has_activity',
        label='Has Activity'
    )
    last_activity_days = django_filters.NumberFilter(
        method='filter_last_activity_days',
        label='Last Activity (days ago)'
    )
    
    # Date range filters
    created_after = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte',
        label='Created After'
    )
    created_before = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte',
        label='Created Before'
    )
    
    # Opt-in filters
    email_opt_in = django_filters.BooleanFilter(label='Email Opt-in')
    sms_opt_in = django_filters.BooleanFilter(label='SMS Opt-in')
    
    # Tag filter
    tags = django_filters.CharFilter(method='filter_tags', label='Tags')
    
    # Partner relationship filter
    partner = django_filters.UUIDFilter(
        method='filter_partner',
        label='Related Partner'
    )
    
    class Meta:
        model = Contact
        fields = [
            'status', 'contact_type', 'city', 'country', 'assigned_to',
            'email_opt_in', 'sms_opt_in', 'source'
        ]
    
    def filter_search(self, queryset, name, value):
        """
        Full-text search across multiple fields.
        
        Searches in: email, first_name, last_name, company_name, notes
        """
        if not value:
            return queryset
        
        # Use PostgreSQL full-text search if available
        try:
            search_vector = SearchVector(
                'email', 'first_name', 'last_name', 'company_name', 'notes'
            )
            return queryset.annotate(search=search_vector).filter(search=value)
        except:
            # Fallback to basic search
            return queryset.filter(
                Q(email__icontains=value) |
                Q(first_name__icontains=value) |
                Q(last_name__icontains=value) |
                Q(company_name__icontains=value) |
                Q(notes__icontains=value)
            )
    
    def filter_unassigned(self, queryset, name, value):
        """Filter for unassigned contacts."""
        if value:
            return queryset.filter(assigned_to__isnull=True)
        return queryset
    
    def filter_has_activity(self, queryset, name, value):
        """Filter contacts based on whether they have any activities."""
        if value is True:
            return queryset.filter(last_activity_at__isnull=False)
        elif value is False:
            return queryset.filter(last_activity_at__isnull=True)
        return queryset
    
    def filter_last_activity_days(self, queryset, name, value):
        """Filter contacts by last activity within N days."""
        if value:
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=value)
            return queryset.filter(last_activity_at__gte=cutoff_date)
        return queryset
    
    def filter_tags(self, queryset, name, value):
        """Filter contacts by tags (comma-separated)."""
        if not value:
            return queryset
        
        tags = [tag.strip() for tag in value.split(',')]
        # Use JSONField contains lookup
        for tag in tags:
            queryset = queryset.filter(tags__contains=tag)
        
        return queryset
    
    def filter_partner(self, queryset, name, value):
        """Filter contacts related to a specific partner."""
        if value:
            return queryset.filter(partner_relationships__partner_id=value).distinct()
        return queryset


class ContactActivityFilter(django_filters.FilterSet):
    """Filtering for contact activities."""
    
    activity_type = django_filters.MultipleChoiceFilter(
        choices=ActivityType.choices,
        label='Activity Type'
    )
    
    actor = django_filters.UUIDFilter(field_name='actor__id', label='Actor')
    
    follow_up_required = django_filters.BooleanFilter(label='Follow-up Required')
    
    created_after = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte',
        label='Created After'
    )
    created_before = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte',
        label='Created Before'
    )
    
    has_outcome = django_filters.BooleanFilter(
        method='filter_has_outcome',
        label='Has Outcome'
    )
    
    class Meta:
        model = ContactActivity
        fields = ['activity_type', 'actor', 'follow_up_required']
    
    def filter_has_outcome(self, queryset, name, value):
        """Filter activities based on whether they have an outcome."""
        if value is True:
            return queryset.exclude(outcome='')
        elif value is False:
            return queryset.filter(outcome='')
        return queryset


class ContactListFilter(django_filters.FilterSet):
    """Filtering for contact lists."""
    
    search = django_filters.CharFilter(
        method='filter_search',
        label='Search'
    )
    
    is_dynamic = django_filters.BooleanFilter(label='Dynamic Lists Only')
    is_public = django_filters.BooleanFilter(label='Public Lists Only')
    
    created_by = django_filters.UUIDFilter(
        field_name='created_by__id',
        label='Created By'
    )
    
    my_lists = django_filters.BooleanFilter(
        method='filter_my_lists',
        label='My Lists Only'
    )
    
    tags = django_filters.CharFilter(method='filter_tags', label='Tags')
    
    class Meta:
        model = ContactList
        fields = ['is_dynamic', 'is_public', 'created_by']
    
    def filter_search(self, queryset, name, value):
        """Search in list name and description."""
        if value:
            return queryset.filter(
                Q(name__icontains=value) |
                Q(description__icontains=value)
            )
        return queryset
    
    def filter_my_lists(self, queryset, name, value):
        """Filter for lists created by the current user."""
        if value:
            user = self.request.user
            return queryset.filter(created_by=user)
        return queryset
    
    def filter_tags(self, queryset, name, value):
        """Filter lists by tags."""
        if not value:
            return queryset
        
        tags = [tag.strip() for tag in value.split(',')]
        for tag in tags:
            queryset = queryset.filter(tags__contains=tag)
        
        return queryset