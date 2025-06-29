"""
ViewSets for root aggregate models - Phase 6.

Provides comprehensive API endpoints for due diligence case management,
workflow orchestration, and analytics with proper permissions and filtering.
"""

from typing import Any, Dict
from datetime import date, timedelta

from django.db.models import Q, Count, Sum, Avg, F, Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from accounts.permissions import GroupFilteredPermission
from .root_aggregate import (
    DueDiligenceCase, CaseChecklistItem, CaseTimeline, create_standard_checklist
)
from .root_aggregate_serializers import (
    DueDiligenceCaseSummarySerializer,
    DueDiligenceCaseDetailSerializer,
    DueDiligenceCaseCreateUpdateSerializer,
    CaseChecklistItemSerializer,
    CaseTimelineSerializer,
    CaseWorkflowSerializer,
    CaseDecisionSerializer,
    CaseAnalyticsSerializer,
    CaseComprehensiveSummarySerializer,
)
from .root_aggregate_filters import (
    DueDiligenceCaseFilter, CaseChecklistItemFilter, CaseTimelineFilter
)
from .advanced_models import AuditTrail
from .enums import RiskLevel


class DueDiligenceCaseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for due diligence case management.
    
    Provides comprehensive CRUD operations, workflow management,
    decision making, and analytics for due diligence cases.
    """
    
    permission_classes = [IsAuthenticated, GroupFilteredPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = DueDiligenceCaseFilter
    search_fields = [
        'case_reference', 'case_name', 'primary_partner__company_name',
        'schemes__scheme_name', 'executive_summary'
    ]
    ordering_fields = [
        'created_at', 'target_completion_date', 'priority',
        'case_status', 'overall_risk_level', 'total_investment_amount'
    ]
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get queryset with optimized prefetching."""
        queryset = DueDiligenceCase.objects.all()
        
        # Optimize queries with select_related and prefetch_related
        if self.action == 'list':
            queryset = queryset.select_related(
                'primary_partner', 'lead_assessor', 'decision_maker'
            ).prefetch_related('schemes', 'assessment_team')
        elif self.action in ['retrieve', 'comprehensive_summary']:
            queryset = queryset.select_related(
                'primary_partner', 'lead_assessor', 'decision_maker'
            ).prefetch_related(
                'schemes',
                'assessment_team',
                'checklist_items',
                'timeline_events',
                Prefetch('checklist_items', 
                    queryset=CaseChecklistItem.objects.select_related('completed_by')
                ),
                Prefetch('timeline_events',
                    queryset=CaseTimeline.objects.select_related('created_by').order_by('-event_date')[:10]
                )
            )
        
        return queryset
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action."""
        if self.action == 'list':
            return DueDiligenceCaseSummarySerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return DueDiligenceCaseCreateUpdateSerializer
        elif self.action == 'comprehensive_summary':
            return CaseComprehensiveSummarySerializer
        elif self.action == 'transition_status':
            return CaseWorkflowSerializer
        elif self.action == 'make_decision':
            return CaseDecisionSerializer
        elif self.action == 'analytics':
            return CaseAnalyticsSerializer
        else:
            return DueDiligenceCaseDetailSerializer
    
    @transaction.atomic
    def create(self, request):
        """Create new due diligence case with standard checklist."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create case
        case = serializer.save(
            group=request.user.group,
            lead_assessor=request.user  # Can be overridden in serializer
        )
        
        # Create standard checklist
        create_standard_checklist(case)
        
        # Create initial timeline event
        CaseTimeline.objects.create(
            case=case,
            group=case.group,
            event_type='created',
            event_title='Case Created',
            event_description=f'Due diligence case {case.case_reference} created',
            created_by=request.user,
            is_significant=True
        )
        
        # Create audit trail
        AuditTrail.objects.create(
            group=case.group,
            entity_type='DueDiligenceCase',
            entity_id=case.id,
            action_type='create',
            change_summary=f'Created due diligence case {case.case_reference}',
            user=request.user,
            risk_assessment=RiskLevel.LOW
        )
        
        # Return detailed view
        detail_serializer = DueDiligenceCaseDetailSerializer(case, context={'request': request})
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def transition_status(self, request, pk=None):
        """Transition case to new status."""
        case = self.get_object()
        serializer = CaseWorkflowSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        new_status = serializer.validated_data['new_status']
        notes = serializer.validated_data.get('notes', '')
        
        try:
            # Transition status
            case.transition_status(new_status, request.user, notes)
            
            # Create timeline event
            CaseTimeline.objects.create(
                case=case,
                group=case.group,
                event_type='status_change',
                event_title=f'Status changed to {case.get_case_status_display()}',
                event_description=f'Case transitioned from {case.case_status} to {new_status}. {notes}',
                created_by=request.user,
                is_significant=True,
                metadata={
                    'from_status': case.case_status,
                    'to_status': new_status,
                    'notes': notes
                }
            )
            
            return Response({
                'status': 'success',
                'new_status': new_status,
                'message': f'Case transitioned to {case.get_case_status_display()}'
            })
            
        except ValidationError as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def make_decision(self, request, pk=None):
        """Make final decision on the case."""
        case = self.get_object()
        serializer = CaseDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        decision = serializer.validated_data['decision']
        conditions = serializer.validated_data.get('conditions', [])
        notes = serializer.validated_data.get('notes', '')
        
        try:
            # Make decision
            case.make_decision(decision, request.user, conditions, notes)
            
            # Create timeline event
            CaseTimeline.objects.create(
                case=case,
                group=case.group,
                event_type='decision',
                event_title=f'Decision: {case.get_final_decision_display()}',
                event_description=f'Final decision made: {decision}. {notes}',
                created_by=request.user,
                is_significant=True,
                metadata={
                    'decision': decision,
                    'conditions': conditions,
                    'decision_maker': request.user.email
                }
            )
            
            return Response({
                'status': 'success',
                'decision': decision,
                'message': f'Decision recorded: {case.get_final_decision_display()}'
            })
            
        except ValidationError as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get dashboard summary for all cases."""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Calculate summary statistics
        total_cases = queryset.count()
        
        # Status distribution
        status_distribution = dict(
            queryset.values('case_status').annotate(
                count=Count('id')
            ).values_list('case_status', 'count')
        )
        
        # Priority distribution
        priority_distribution = dict(
            queryset.values('priority').annotate(
                count=Count('id')
            ).values_list('priority', 'count')
        )
        
        # Risk distribution
        risk_distribution = dict(
            queryset.exclude(overall_risk_level__isnull=True).values(
                'overall_risk_level'
            ).annotate(
                count=Count('id')
            ).values_list('overall_risk_level', 'count')
        )
        
        # Overdue cases
        overdue_cases = queryset.filter(
            target_completion_date__lt=date.today(),
            case_status__in=['initiated', 'data_collection', 'analysis', 'review', 'decision_pending']
        ).count()
        
        # Cases due this week
        week_from_now = date.today() + timedelta(days=7)
        due_this_week = queryset.filter(
            target_completion_date__lte=week_from_now,
            target_completion_date__gte=date.today(),
            case_status__in=['initiated', 'data_collection', 'analysis', 'review', 'decision_pending']
        ).count()
        
        # Recent decisions
        recent_decisions = queryset.exclude(
            final_decision__isnull=True
        ).order_by('-decision_date')[:5].values(
            'case_reference', 'case_name', 'final_decision', 'decision_date'
        )
        
        # Investment summary
        investment_by_currency = queryset.exclude(
            total_investment_amount__isnull=True
        ).values('total_investment_currency').annotate(
            total_amount=Sum('total_investment_amount'),
            count=Count('id')
        )
        
        return Response({
            'summary': {
                'total_cases': total_cases,
                'overdue_cases': overdue_cases,
                'due_this_week': due_this_week,
                'active_cases': queryset.filter(
                    case_status__in=['initiated', 'data_collection', 'analysis', 'review', 'decision_pending']
                ).count(),
                'completed_cases': queryset.filter(
                    case_status__in=['completed', 'archived']
                ).count(),
            },
            'distributions': {
                'by_status': status_distribution,
                'by_priority': priority_distribution,
                'by_risk': risk_distribution,
            },
            'recent_decisions': list(recent_decisions),
            'investment_summary': list(investment_by_currency),
        })
    
    @action(detail=True, methods=['get'])
    def comprehensive_summary(self, request, pk=None):
        """Get comprehensive summary of the case."""
        case = self.get_object()
        summary = case.get_comprehensive_summary()
        
        # Add timeline summary
        recent_events = CaseTimeline.objects.filter(
            case=case
        ).select_related('created_by').order_by('-event_date')[:10]
        
        summary['timeline'] = {
            'recent_events': CaseTimelineSerializer(recent_events, many=True).data,
            'total_events': case.timeline_events.count(),
            'significant_events': case.timeline_events.filter(is_significant=True).count()
        }
        
        # Add checklist summary
        checklist_summary = CaseChecklistItem.objects.filter(
            case=case
        ).values('category').annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(is_completed=True)),
            required=Count('id', filter=Q(is_required=True)),
            required_completed=Count('id', filter=Q(is_required=True, is_completed=True))
        )
        
        summary['checklist'] = {
            'by_category': list(checklist_summary),
            'overall_completion': self._calculate_checklist_completion(case),
            'overdue_items': CaseChecklistItem.objects.filter(
                case=case,
                is_completed=False,
                due_date__lt=date.today()
            ).count()
        }
        
        return Response(summary)
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get analytics data for reporting."""
        serializer = CaseAnalyticsSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        # Get filtered queryset
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply date filters
        date_from = serializer.validated_data.get('date_from')
        date_to = serializer.validated_data.get('date_to')
        
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        # Group by requested dimension
        group_by = serializer.validated_data.get('group_by', 'month')
        
        analytics_data = {
            'summary': self._get_analytics_summary(queryset),
            'trends': self._get_analytics_trends(queryset, group_by),
            'performance': self._get_analytics_performance(queryset),
            'risk_analysis': self._get_analytics_risk(queryset),
        }
        
        return Response(analytics_data)
    
    def _calculate_checklist_completion(self, case):
        """Calculate overall checklist completion percentage."""
        checklist_items = CaseChecklistItem.objects.filter(case=case, is_required=True)
        total = checklist_items.count()
        
        if total == 0:
            return 100
        
        completed = checklist_items.filter(is_completed=True).count()
        return round((completed / total) * 100, 1)
    
    def _get_analytics_summary(self, queryset):
        """Get summary analytics."""
        return {
            'total_cases': queryset.count(),
            'total_investment': queryset.aggregate(
                total=Sum('total_investment_amount')
            )['total'] or 0,
            'average_completion_days': self._calculate_average_completion_days(queryset),
            'decision_rates': self._calculate_decision_rates(queryset),
        }
    
    def _get_analytics_trends(self, queryset, group_by):
        """Get trend analytics."""
        # Implementation would vary based on group_by parameter
        # This is a simplified example
        if group_by == 'month':
            return queryset.extra(
                select={'month': "date_trunc('month', created_at)"}
            ).values('month').annotate(
                count=Count('id'),
                investment=Sum('total_investment_amount')
            ).order_by('month')
        
        return []
    
    def _get_analytics_performance(self, queryset):
        """Get performance analytics."""
        completed_cases = queryset.filter(case_status='completed')
        
        on_time = completed_cases.filter(
            actual_completion_date__lte=F('target_completion_date')
        ).count()
        
        total_completed = completed_cases.count()
        
        return {
            'on_time_completion_rate': round((on_time / total_completed) * 100, 1) if total_completed > 0 else 0,
            'average_team_size': queryset.annotate(
                team_size=Count('assessment_team')
            ).aggregate(avg=Avg('team_size'))['avg'] or 0,
        }
    
    def _get_analytics_risk(self, queryset):
        """Get risk analytics."""
        return {
            'high_risk_cases': queryset.filter(
                overall_risk_level__in=[RiskLevel.HIGH, RiskLevel.CRITICAL]
            ).count(),
            'risk_distribution': dict(
                queryset.exclude(overall_risk_level__isnull=True).values(
                    'overall_risk_level'
                ).annotate(
                    count=Count('id')
                ).values_list('overall_risk_level', 'count')
            ),
        }
    
    def _calculate_average_completion_days(self, queryset):
        """Calculate average days to complete cases."""
        completed = queryset.filter(
            case_status='completed',
            actual_completion_date__isnull=False
        ).annotate(
            days_to_complete=F('actual_completion_date') - F('created_at__date')
        ).aggregate(
            avg_days=Avg('days_to_complete')
        )['avg_days']
        
        return completed.days if completed else 0
    
    def _calculate_decision_rates(self, queryset):
        """Calculate decision rate breakdown."""
        total_decisions = queryset.exclude(final_decision__isnull=True).count()
        
        if total_decisions == 0:
            return {}
        
        decision_counts = dict(
            queryset.exclude(final_decision__isnull=True).values(
                'final_decision'
            ).annotate(
                count=Count('id')
            ).values_list('final_decision', 'count')
        )
        
        return {
            decision: round((count / total_decisions) * 100, 1)
            for decision, count in decision_counts.items()
        }


class CaseChecklistItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for case checklist management.
    
    Provides CRUD operations and completion tracking for
    due diligence checklist items.
    """
    
    serializer_class = CaseChecklistItemSerializer
    permission_classes = [IsAuthenticated, GroupFilteredPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = CaseChecklistItemFilter
    ordering_fields = ['category', 'due_date', 'is_completed', 'created_at']
    ordering = ['category', 'item_name']
    
    def get_queryset(self):
        """Get queryset with optimized queries."""
        return CaseChecklistItem.objects.select_related(
            'case', 'completed_by'
        ).all()
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark checklist item as complete."""
        item = self.get_object()
        
        notes = request.data.get('notes', '')
        attachments = request.data.get('attachments', [])
        
        # Mark complete
        item.mark_complete(request.user, notes)
        
        if attachments:
            item.attachments = attachments
            item.save()
        
        # Create timeline event
        CaseTimeline.objects.create(
            case=item.case,
            group=item.case.group,
            event_type='note',
            event_title='Checklist Item Completed',
            event_description=f'{item.category}: {item.item_name} completed',
            created_by=request.user,
            metadata={
                'checklist_item_id': str(item.id),
                'category': item.category,
                'item_name': item.item_name
            }
        )
        
        serializer = self.get_serializer(item)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_case(self, request):
        """Get checklist items grouped by case."""
        case_id = request.query_params.get('case_id')
        
        if not case_id:
            return Response({
                'error': 'case_id parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        case = get_object_or_404(DueDiligenceCase, id=case_id, group=request.user.group)
        
        checklist_items = self.filter_queryset(
            self.get_queryset().filter(case=case)
        )
        
        # Group by category
        by_category = {}
        for item in checklist_items:
            if item.category not in by_category:
                by_category[item.category] = {
                    'items': [],
                    'total': 0,
                    'completed': 0,
                    'required': 0,
                    'required_completed': 0
                }
            
            by_category[item.category]['items'].append(
                self.get_serializer(item).data
            )
            by_category[item.category]['total'] += 1
            
            if item.is_completed:
                by_category[item.category]['completed'] += 1
            
            if item.is_required:
                by_category[item.category]['required'] += 1
                if item.is_completed:
                    by_category[item.category]['required_completed'] += 1
        
        # Calculate completion percentages
        for category_data in by_category.values():
            if category_data['required'] > 0:
                category_data['completion_percentage'] = round(
                    (category_data['required_completed'] / category_data['required']) * 100, 1
                )
            else:
                category_data['completion_percentage'] = 100 if category_data['total'] == category_data['completed'] else 0
        
        return Response({
            'case': {
                'id': str(case.id),
                'reference': case.case_reference,
                'name': case.case_name
            },
            'checklist': by_category,
            'overall_completion': self._calculate_overall_completion(checklist_items)
        })
    
    def _calculate_overall_completion(self, checklist_items):
        """Calculate overall completion statistics."""
        total = checklist_items.count()
        completed = checklist_items.filter(is_completed=True).count()
        required = checklist_items.filter(is_required=True).count()
        required_completed = checklist_items.filter(
            is_required=True, is_completed=True
        ).count()
        
        return {
            'total_items': total,
            'completed_items': completed,
            'required_items': required,
            'required_completed': required_completed,
            'completion_percentage': round((completed / total) * 100, 1) if total > 0 else 0,
            'required_completion_percentage': round((required_completed / required) * 100, 1) if required > 0 else 0
        }


class CaseTimelineViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for case timeline viewing.
    
    Provides read-only access to case timeline events for
    audit and review purposes.
    """
    
    serializer_class = CaseTimelineSerializer
    permission_classes = [IsAuthenticated, GroupFilteredPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = CaseTimelineFilter
    ordering_fields = ['event_date', 'event_type', 'is_significant']
    ordering = ['-event_date']
    
    def get_queryset(self):
        """Get queryset with optimized queries."""
        return CaseTimeline.objects.select_related(
            'case', 'created_by'
        ).all()
    
    @action(detail=False, methods=['post'])
    def add_note(self, request):
        """Add a note to case timeline."""
        case_id = request.data.get('case_id')
        title = request.data.get('title')
        description = request.data.get('description')
        is_significant = request.data.get('is_significant', False)
        
        if not all([case_id, title, description]):
            return Response({
                'error': 'case_id, title, and description are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        case = get_object_or_404(DueDiligenceCase, id=case_id, group=request.user.group)
        
        timeline_event = CaseTimeline.objects.create(
            case=case,
            group=case.group,
            event_type='note',
            event_title=title,
            event_description=description,
            created_by=request.user,
            is_significant=is_significant
        )
        
        serializer = self.get_serializer(timeline_event)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def significant_events(self, request):
        """Get significant timeline events."""
        case_id = request.query_params.get('case_id')
        
        queryset = self.filter_queryset(self.get_queryset()).filter(
            is_significant=True
        )
        
        if case_id:
            queryset = queryset.filter(case_id=case_id)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)