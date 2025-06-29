"""
Advanced features viewsets for the CASA Due Diligence Platform.

Provides comprehensive API endpoints for regulatory compliance, performance metrics,
ESG assessments, and audit trails with analytics, filtering, and reporting capabilities.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional

from django.db.models import Q, Count, Avg, Sum, Max, Min, F, Case, When, Value
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.shortcuts import get_object_or_404

from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from rest_framework.permissions import IsAuthenticated
from accounts.permissions import GroupAccessPermission, RoleBasedPermission
from .advanced_models import (
    RegulatoryCompliance, PerformanceMetric, ESGAssessment, AuditTrail
)
from .advanced_serializers import (
    # Regulatory Compliance
    RegulatoryComplianceSummarySerializer, RegulatoryComplianceDetailSerializer,
    RegulatoryComplianceCreateUpdateSerializer,
    # Performance Metrics
    PerformanceMetricSummarySerializer, PerformanceMetricDetailSerializer,
    PerformanceMetricCreateUpdateSerializer,
    # ESG Assessments
    ESGAssessmentSummarySerializer, ESGAssessmentDetailSerializer,
    ESGAssessmentCreateUpdateSerializer,
    # Audit Trail
    AuditTrailSerializer, AuditTrailCreateSerializer,
    # Analytics
    ComplianceAnalyticsSerializer, PerformanceAnalyticsSerializer,
    ESGComparisonSerializer
)
from .enums import RiskLevel


class RegulatoryComplianceFilter(DjangoFilterBackend):
    """Custom filter for regulatory compliance records."""
    
    class Meta:
        model = RegulatoryCompliance
        fields = {
            'jurisdiction': ['exact', 'in'],
            'regulatory_framework': ['exact', 'icontains'],
            'regulatory_body': ['exact', 'icontains'],
            'compliance_category': ['exact', 'in'],
            'compliance_status': ['exact', 'in'],
            'compliance_risk_level': ['exact', 'in'],
            'compliance_date': ['exact', 'gte', 'lte'],
            'expiry_date': ['exact', 'gte', 'lte'],
            'next_review_date': ['exact', 'gte', 'lte'],
            'partner': ['exact'],
            'scheme': ['exact'],
            'is_published': ['exact'],
            'financial_impact_amount': ['gte', 'lte']
        }


class PerformanceMetricFilter(DjangoFilterBackend):
    """Custom filter for performance metrics."""
    
    class Meta:
        model = PerformanceMetric
        fields = {
            'metric_name': ['exact', 'icontains'],
            'metric_category': ['exact', 'in'],
            'measurement_date': ['exact', 'gte', 'lte'],
            'trend_direction': ['exact', 'in'],
            'measurement_frequency': ['exact', 'in'],
            'data_quality_score': ['exact', 'gte', 'lte'],
            'action_required': ['exact'],
            'partner': ['exact'],
            'scheme': ['exact'],
            'assessment': ['exact'],
            'is_published': ['exact']
        }


class ESGAssessmentFilter(DjangoFilterBackend):
    """Custom filter for ESG assessments."""
    
    class Meta:
        model = ESGAssessment
        fields = {
            'assessment_framework': ['exact', 'in'],
            'assessment_period_start': ['exact', 'gte', 'lte'],
            'assessment_period_end': ['exact', 'gte', 'lte'],
            'environmental_score': ['exact', 'gte', 'lte'],
            'social_score': ['exact', 'gte', 'lte'],
            'governance_score': ['exact', 'gte', 'lte'],
            'overall_esg_score': ['gte', 'lte'],
            'esg_rating': ['exact', 'in'],
            'energy_efficiency_rating': ['exact', 'in'],
            'partner': ['exact'],
            'scheme': ['exact'],
            'is_published': ['exact'],
            'next_assessment_date': ['exact', 'gte', 'lte']
        }


@extend_schema_view(
    list=extend_schema(
        summary="List regulatory compliance records",
        description="Get paginated list of compliance records with filtering and search"
    ),
    retrieve=extend_schema(
        summary="Get compliance details",
        description="Get detailed regulatory compliance information including version history"
    ),
    create=extend_schema(
        summary="Create compliance record",
        description="Create a new regulatory compliance record"
    ),
    update=extend_schema(
        summary="Update compliance record",
        description="Update regulatory compliance information with version tracking"
    ),
    partial_update=extend_schema(
        summary="Partially update compliance",
        description="Partially update compliance fields"
    ),
    destroy=extend_schema(
        summary="Delete compliance record",
        description="Delete a compliance record (only drafts can be deleted)"
    )
)
class RegulatoryComplianceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing regulatory compliance records.
    
    Provides CRUD operations, compliance analytics, expiry monitoring,
    and jurisdictional filtering for regulatory requirements.
    """
    
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = RegulatoryComplianceFilter
    search_fields = [
        'requirement_title', 'requirement_description', 'regulatory_framework',
        'regulatory_body', 'responsible_person', 'compliance_notes'
    ]
    ordering_fields = [
        'compliance_date', 'expiry_date', 'next_review_date',
        'compliance_score', 'financial_impact_amount', 'created_at'
    ]
    ordering = ['-next_review_date', '-expiry_date']
    
    def get_queryset(self):
        """Get compliance records filtered by user's group."""
        queryset = RegulatoryCompliance.objects.filter(
            group__in=self.request.user.groups.all()
        ).select_related(
            'partner', 'scheme', 'last_modified_by', 'approved_by'
        )
        
        # Add custom filters
        expiring_soon = self.request.query_params.get('expiring_soon')
        if expiring_soon and expiring_soon.lower() == 'true':
            cutoff_date = date.today() + timedelta(days=90)
            queryset = queryset.filter(
                expiry_date__isnull=False,
                expiry_date__lte=cutoff_date
            )
        
        high_risk_only = self.request.query_params.get('high_risk_only')
        if high_risk_only and high_risk_only.lower() == 'true':
            queryset = queryset.filter(
                Q(compliance_risk_level__in=[RiskLevel.HIGH, RiskLevel.CRITICAL]) |
                Q(compliance_status='non_compliant')
            )
        
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return RegulatoryComplianceSummarySerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return RegulatoryComplianceCreateUpdateSerializer
        else:
            return RegulatoryComplianceDetailSerializer
    
    def perform_create(self, serializer):
        """Create compliance record with group context."""
        user = self.request.user
        group = user.groups.first()
        
        serializer.save(
            group=group,
            last_modified_by=user
        )
    
    def perform_destroy(self, instance):
        """Only allow deletion of unpublished compliance records."""
        if instance.is_published:
            raise PermissionDenied("Cannot delete published compliance records")
        
        # Create audit trail entry
        AuditTrail.objects.create(
            group=instance.group,
            entity_type='RegulatoryCompliance',
            entity_id=instance.id,
            action_type='delete',
            change_summary=f"Deleted compliance record: {instance.requirement_title}",
            user=self.request.user,
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
            risk_assessment=RiskLevel.MEDIUM
        )
        
        super().perform_destroy(instance)
    
    @extend_schema(
        summary="Approve compliance record",
        description="Approve a compliance record for publication",
        request=None,
        responses={200: RegulatoryComplianceDetailSerializer}
    )
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve compliance record for publication."""
        compliance = self.get_object()
        
        if compliance.is_approved:
            return Response(
                {'error': 'Compliance record is already approved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        compliance.approve_version(request.user, request.data.get('notes', ''))
        compliance.save()
        
        # Create audit trail
        AuditTrail.objects.create(
            group=compliance.group,
            entity_type='RegulatoryCompliance',
            entity_id=compliance.id,
            action_type='approve',
            change_summary=f"Approved compliance record: {compliance.requirement_title}",
            user=request.user,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            risk_assessment=RiskLevel.LOW
        )
        
        serializer = self.get_serializer(compliance)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get compliance analytics",
        description="Get comprehensive compliance analytics and statistics",
        parameters=[ComplianceAnalyticsSerializer],
        responses={200: dict}
    )
    @action(detail=False, methods=['get'])
    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    def analytics(self, request):
        """Get compliance analytics and reporting."""
        serializer = ComplianceAnalyticsSerializer(data=request.query_params)
        
        if serializer.is_valid():
            filters = Q(group__in=request.user.groups.all())
            
            # Apply filters
            if serializer.validated_data.get('date_from'):
                filters &= Q(compliance_date__gte=serializer.validated_data['date_from'])
            
            if serializer.validated_data.get('date_to'):
                filters &= Q(compliance_date__lte=serializer.validated_data['date_to'])
            
            if serializer.validated_data.get('jurisdiction'):
                filters &= Q(jurisdiction=serializer.validated_data['jurisdiction'])
            
            if serializer.validated_data.get('compliance_category'):
                filters &= Q(compliance_category=serializer.validated_data['compliance_category'])
            
            if serializer.validated_data.get('compliance_status'):
                filters &= Q(compliance_status=serializer.validated_data['compliance_status'])
            
            if serializer.validated_data.get('risk_level'):
                filters &= Q(compliance_risk_level=serializer.validated_data['risk_level'])
            
            if serializer.validated_data.get('include_expiring'):
                cutoff_date = date.today() + timedelta(days=90)
                filters &= Q(expiry_date__lte=cutoff_date)
            
            queryset = RegulatoryCompliance.objects.filter(filters)
            
            # Basic statistics
            total_records = queryset.count()
            
            # Compliance status breakdown
            status_breakdown = queryset.values('compliance_status').annotate(
                count=Count('id'),
                avg_score=Avg('compliance_score'),
                total_impact=Sum('financial_impact_amount')
            ).order_by('compliance_status')
            
            # Risk level breakdown
            risk_breakdown = queryset.values('compliance_risk_level').annotate(
                count=Count('id'),
                total_impact=Sum('financial_impact_amount')
            ).order_by('compliance_risk_level')
            
            # Category breakdown
            category_breakdown = queryset.values('compliance_category').annotate(
                count=Count('id'),
                compliant_count=Count('id', filter=Q(compliance_status='compliant')),
                avg_score=Avg('compliance_score')
            ).order_by('compliance_category')
            
            # Jurisdiction analysis
            jurisdiction_breakdown = queryset.values('jurisdiction').annotate(
                count=Count('id'),
                compliant_count=Count('id', filter=Q(compliance_status='compliant')),
                non_compliant_count=Count('id', filter=Q(compliance_status='non_compliant'))
            ).order_by('-count')[:10]
            
            # Expiry analysis
            expiring_soon = queryset.filter(
                expiry_date__isnull=False,
                expiry_date__lte=date.today() + timedelta(days=90)
            ).count()
            
            expired = queryset.filter(
                expiry_date__isnull=False,
                expiry_date__lt=date.today()
            ).count()
            
            # Financial impact
            total_impact = queryset.aggregate(
                total=Sum('financial_impact_amount')
            )['total'] or 0
            
            high_risk_impact = queryset.filter(
                compliance_risk_level__in=[RiskLevel.HIGH, RiskLevel.CRITICAL]
            ).aggregate(
                total=Sum('financial_impact_amount')
            )['total'] or 0
            
            # Grouping if requested
            grouped_data = {}
            group_by = serializer.validated_data.get('group_by')
            if group_by:
                if group_by == 'jurisdiction':
                    grouped_data = list(jurisdiction_breakdown)
                elif group_by == 'category':
                    grouped_data = list(category_breakdown)
                elif group_by == 'status':
                    grouped_data = list(status_breakdown)
                elif group_by == 'entity_type':
                    entity_breakdown = queryset.annotate(
                        entity_type=Case(
                            When(partner__isnull=False, then=Value('partner')),
                            When(scheme__isnull=False, then=Value('scheme')),
                            default=Value('unknown')
                        )
                    ).values('entity_type').annotate(
                        count=Count('id')
                    )
                    grouped_data = list(entity_breakdown)
            
            return Response({
                'summary': {
                    'total_records': total_records,
                    'compliant_count': queryset.filter(compliance_status='compliant').count(),
                    'non_compliant_count': queryset.filter(compliance_status='non_compliant').count(),
                    'compliance_rate': round(
                        queryset.filter(compliance_status='compliant').count() / total_records * 100
                        if total_records > 0 else 0, 2
                    ),
                    'expiring_soon': expiring_soon,
                    'expired': expired,
                    'total_financial_impact': float(total_impact),
                    'high_risk_impact': float(high_risk_impact)
                },
                'status_breakdown': list(status_breakdown),
                'risk_breakdown': list(risk_breakdown),
                'category_breakdown': list(category_breakdown),
                'jurisdiction_breakdown': list(jurisdiction_breakdown),
                'grouped_data': grouped_data,
                'generated_at': datetime.now().isoformat()
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Get expiring compliance",
        description="Get compliance records expiring within specified days",
        parameters=[
            OpenApiParameter(
                name='days',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                default=90,
                description='Number of days to look ahead'
            )
        ],
        responses={200: RegulatoryComplianceSummarySerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def expiring(self, request):
        """Get compliance records expiring soon."""
        days = int(request.query_params.get('days', 90))
        cutoff_date = date.today() + timedelta(days=days)
        
        queryset = self.get_queryset().filter(
            expiry_date__isnull=False,
            expiry_date__lte=cutoff_date,
            expiry_date__gte=date.today()
        ).order_by('expiry_date')
        
        serializer = RegulatoryComplianceSummarySerializer(
            queryset, many=True, context={'request': request}
        )
        
        return Response({
            'count': queryset.count(),
            'cutoff_date': cutoff_date.isoformat(),
            'results': serializer.data
        })


@extend_schema_view(
    list=extend_schema(
        summary="List performance metrics",
        description="Get paginated list of performance metrics with filtering"
    ),
    retrieve=extend_schema(
        summary="Get metric details",
        description="Get detailed performance metric information with trend data"
    ),
    create=extend_schema(
        summary="Create metric",
        description="Create a new performance metric measurement"
    ),
    update=extend_schema(
        summary="Update metric",
        description="Update performance metric information"
    ),
    destroy=extend_schema(
        summary="Delete metric",
        description="Delete a performance metric (only unpublished)"
    )
)
class PerformanceMetricViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing performance metrics.
    
    Provides CRUD operations, trend analysis, benchmarking,
    and performance reporting capabilities.
    """
    
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PerformanceMetricFilter
    search_fields = [
        'metric_name', 'metric_description', 'performance_notes',
        'data_source'
    ]
    ordering_fields = [
        'measurement_date', 'metric_value', 'variance_from_target_pct',
        'variance_from_benchmark_pct', 'data_quality_score', 'created_at'
    ]
    ordering = ['-measurement_date', 'metric_name']
    
    def get_queryset(self):
        """Get metrics filtered by user's group."""
        queryset = PerformanceMetric.objects.filter(
            group__in=self.request.user.groups.all()
        ).select_related(
            'partner', 'scheme', 'assessment', 'last_modified_by', 'approved_by'
        )
        
        # Add custom filters
        action_required_only = self.request.query_params.get('action_required_only')
        if action_required_only and action_required_only.lower() == 'true':
            queryset = queryset.filter(action_required=True)
        
        below_target_only = self.request.query_params.get('below_target_only')
        if below_target_only and below_target_only.lower() == 'true':
            queryset = queryset.filter(
                variance_from_target_pct__lt=-10
            )
        
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return PerformanceMetricSummarySerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return PerformanceMetricCreateUpdateSerializer
        else:
            return PerformanceMetricDetailSerializer
    
    def perform_create(self, serializer):
        """Create metric with group context."""
        user = self.request.user
        group = user.groups.first()
        
        serializer.save(
            group=group,
            last_modified_by=user
        )
    
    @extend_schema(
        summary="Get trend analysis",
        description="Get trend analysis for performance metrics",
        parameters=[PerformanceAnalyticsSerializer],
        responses={200: dict}
    )
    @action(detail=False, methods=['get'])
    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    def trends(self, request):
        """Get performance trend analysis."""
        serializer = PerformanceAnalyticsSerializer(data=request.query_params)
        
        if serializer.is_valid():
            filters = Q(group__in=request.user.groups.all())
            
            # Apply filters
            if serializer.validated_data.get('metric_names'):
                filters &= Q(metric_name__in=serializer.validated_data['metric_names'])
            
            if serializer.validated_data.get('metric_category'):
                filters &= Q(metric_category=serializer.validated_data['metric_category'])
            
            if serializer.validated_data.get('date_from'):
                filters &= Q(measurement_date__gte=serializer.validated_data['date_from'])
            
            if serializer.validated_data.get('date_to'):
                filters &= Q(measurement_date__lte=serializer.validated_data['date_to'])
            
            if serializer.validated_data.get('entity_type') and serializer.validated_data.get('entity_id'):
                entity_type = serializer.validated_data['entity_type']
                entity_id = serializer.validated_data['entity_id']
                
                if entity_type == 'partner':
                    filters &= Q(partner_id=entity_id)
                elif entity_type == 'scheme':
                    filters &= Q(scheme_id=entity_id)
                elif entity_type == 'assessment':
                    filters &= Q(assessment_id=entity_id)
            
            queryset = PerformanceMetric.objects.filter(filters)
            
            # Get unique metrics
            metrics = queryset.values('metric_name', 'metric_category').distinct()
            
            trend_data = []
            for metric in metrics:
                metric_data = queryset.filter(
                    metric_name=metric['metric_name'],
                    metric_category=metric['metric_category']
                ).order_by('measurement_date')
                
                # Calculate trend statistics
                values = list(metric_data.values_list('metric_value', flat=True))
                if len(values) >= 2:
                    # Simple linear trend
                    first_half_avg = sum(values[:len(values)//2]) / (len(values)//2)
                    second_half_avg = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
                    trend_direction = 'improving' if second_half_avg > first_half_avg else 'declining'
                else:
                    trend_direction = 'stable'
                
                # Time series data
                time_series = []
                aggregation = serializer.validated_data.get('aggregation', 'monthly')
                
                if aggregation == 'daily':
                    grouped_data = metric_data.values('measurement_date').annotate(
                        avg_value=Avg('metric_value'),
                        min_value=Min('metric_value'),
                        max_value=Max('metric_value'),
                        avg_target=Avg('target_value'),
                        avg_benchmark=Avg('benchmark_value')
                    ).order_by('measurement_date')
                else:
                    # For other aggregations, we'd need to use database-specific functions
                    # Simplified version here
                    grouped_data = metric_data.values('measurement_date').annotate(
                        avg_value=Avg('metric_value'),
                        min_value=Min('metric_value'),
                        max_value=Max('metric_value'),
                        avg_target=Avg('target_value'),
                        avg_benchmark=Avg('benchmark_value')
                    ).order_by('measurement_date')
                
                for data_point in grouped_data:
                    point = {
                        'date': data_point['measurement_date'],
                        'value': float(data_point['avg_value']),
                        'min': float(data_point['min_value']),
                        'max': float(data_point['max_value'])
                    }
                    
                    if serializer.validated_data.get('include_targets'):
                        point['target'] = float(data_point['avg_target']) if data_point['avg_target'] else None
                    
                    if serializer.validated_data.get('include_benchmarks'):
                        point['benchmark'] = float(data_point['avg_benchmark']) if data_point['avg_benchmark'] else None
                    
                    time_series.append(point)
                
                # Performance statistics
                latest_metric = metric_data.last()
                
                trend_data.append({
                    'metric_name': metric['metric_name'],
                    'metric_category': metric['metric_category'],
                    'measurement_count': metric_data.count(),
                    'trend_direction': trend_direction,
                    'latest_value': float(latest_metric.metric_value) if latest_metric else None,
                    'latest_date': latest_metric.measurement_date if latest_metric else None,
                    'average_value': float(metric_data.aggregate(avg=Avg('metric_value'))['avg'] or 0),
                    'min_value': float(metric_data.aggregate(min=Min('metric_value'))['min'] or 0),
                    'max_value': float(metric_data.aggregate(max=Max('metric_value'))['max'] or 0),
                    'time_series': time_series
                })
            
            return Response({
                'metrics_analyzed': len(trend_data),
                'date_range': {
                    'from': serializer.validated_data.get('date_from'),
                    'to': serializer.validated_data.get('date_to')
                },
                'aggregation': serializer.validated_data.get('aggregation', 'monthly'),
                'trends': trend_data,
                'generated_at': datetime.now().isoformat()
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Get performance report",
        description="Generate comprehensive performance report",
        parameters=[
            OpenApiParameter(
                name='entity_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=['partner', 'scheme', 'assessment'],
                description='Entity type for report'
            ),
            OpenApiParameter(
                name='entity_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description='Entity ID for report'
            ),
            OpenApiParameter(
                name='period',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=['month', 'quarter', 'year'],
                default='quarter',
                description='Reporting period'
            )
        ],
        responses={200: dict}
    )
    @action(detail=False, methods=['get'])
    def report(self, request):
        """Generate performance report for an entity."""
        entity_type = request.query_params.get('entity_type')
        entity_id = request.query_params.get('entity_id')
        period = request.query_params.get('period', 'quarter')
        
        if not entity_type or not entity_id:
            return Response(
                {'error': 'Both entity_type and entity_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determine date range based on period
        end_date = date.today()
        if period == 'month':
            start_date = end_date - timedelta(days=30)
        elif period == 'quarter':
            start_date = end_date - timedelta(days=90)
        else:  # year
            start_date = end_date - timedelta(days=365)
        
        # Build filter
        filters = Q(
            group__in=request.user.groups.all(),
            measurement_date__gte=start_date,
            measurement_date__lte=end_date
        )
        
        if entity_type == 'partner':
            filters &= Q(partner_id=entity_id)
        elif entity_type == 'scheme':
            filters &= Q(scheme_id=entity_id)
        elif entity_type == 'assessment':
            filters &= Q(assessment_id=entity_id)
        
        metrics = PerformanceMetric.objects.filter(filters).select_related(
            'partner', 'scheme', 'assessment'
        )
        
        # Category analysis
        category_analysis = metrics.values('metric_category').annotate(
            metric_count=Count('id'),
            avg_score=Avg('data_quality_score'),
            meeting_target_count=Count(
                'id',
                filter=Q(variance_from_target_pct__gte=-5, variance_from_target_pct__lte=5)
            ),
            action_required_count=Count('id', filter=Q(action_required=True))
        )
        
        # Key metrics summary
        key_metrics = []
        for metric_name in metrics.values_list('metric_name', flat=True).distinct()[:10]:
            metric_series = metrics.filter(metric_name=metric_name).order_by('measurement_date')
            latest = metric_series.last()
            
            if latest:
                previous = metric_series.exclude(id=latest.id).last()
                
                change_pct = None
                if previous and previous.metric_value != 0:
                    change_pct = ((latest.metric_value - previous.metric_value) / 
                                 previous.metric_value * 100)
                
                key_metrics.append({
                    'metric_name': metric_name,
                    'latest_value': float(latest.metric_value),
                    'unit': latest.metric_unit,
                    'target': float(latest.target_value) if latest.target_value else None,
                    'variance_from_target': float(latest.variance_from_target_pct) if latest.variance_from_target_pct else None,
                    'trend': latest.trend_direction,
                    'change_pct': float(change_pct) if change_pct else None,
                    'performance_rating': latest.performance_rating,
                    'action_required': latest.action_required
                })
        
        # Overall performance score
        meeting_target = metrics.filter(
            variance_from_target_pct__gte=-5,
            variance_from_target_pct__lte=5
        ).count()
        total_with_targets = metrics.exclude(target_value__isnull=True).count()
        performance_score = (meeting_target / total_with_targets * 100) if total_with_targets > 0 else 0
        
        return Response({
            'entity': {
                'type': entity_type,
                'id': entity_id
            },
            'reporting_period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'period': period
            },
            'summary': {
                'total_metrics': metrics.count(),
                'unique_metrics': metrics.values('metric_name').distinct().count(),
                'measurements': metrics.count(),
                'overall_performance_score': round(performance_score, 2),
                'metrics_meeting_target': meeting_target,
                'metrics_with_targets': total_with_targets,
                'action_items': metrics.filter(action_required=True).count()
            },
            'category_analysis': list(category_analysis),
            'key_metrics': key_metrics,
            'data_quality': {
                'average_score': metrics.aggregate(avg=Avg('data_quality_score'))['avg'] or 0,
                'high_quality_count': metrics.filter(data_quality_score__gte=4).count(),
                'low_quality_count': metrics.filter(data_quality_score__lte=2).count()
            },
            'generated_at': datetime.now().isoformat()
        })


@extend_schema_view(
    list=extend_schema(
        summary="List ESG assessments",
        description="Get paginated list of ESG assessments with filtering"
    ),
    retrieve=extend_schema(
        summary="Get ESG assessment details",
        description="Get detailed ESG assessment with score breakdown"
    ),
    create=extend_schema(
        summary="Create ESG assessment",
        description="Create a new ESG assessment"
    ),
    update=extend_schema(
        summary="Update ESG assessment",
        description="Update ESG assessment information"
    ),
    destroy=extend_schema(
        summary="Delete ESG assessment",
        description="Delete an ESG assessment (only unpublished)"
    )
)
class ESGAssessmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ESG assessments.
    
    Provides CRUD operations, ESG scoring, comparisons,
    and sustainability reporting capabilities.
    """
    
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ESGAssessmentFilter
    search_fields = [
        'assessment_name', 'improvement_areas', 'action_plan',
        'environmental_certifications'
    ]
    ordering_fields = [
        'assessment_period_end', 'overall_esg_score', 'environmental_score',
        'social_score', 'governance_score', 'created_at'
    ]
    ordering = ['-assessment_period_end', '-overall_esg_score']
    
    def get_queryset(self):
        """Get ESG assessments filtered by user's group."""
        queryset = ESGAssessment.objects.filter(
            group__in=self.request.user.groups.all()
        ).select_related(
            'partner', 'scheme', 'last_modified_by', 'approved_by'
        )
        
        # Add custom filters
        latest_only = self.request.query_params.get('latest_only')
        if latest_only and latest_only.lower() == 'true':
            # Get latest assessment for each entity
            # This is simplified - in production, use window functions
            queryset = queryset.order_by('partner', 'scheme', '-assessment_period_end').distinct('partner', 'scheme')
        
        min_rating = self.request.query_params.get('min_rating')
        if min_rating:
            rating_map = {'AAA': 4.5, 'AA': 4.0, 'A': 3.5, 'BBB': 3.0, 'BB': 2.5, 'B': 2.0, 'CCC': 1.5}
            min_score = rating_map.get(min_rating, 0)
            queryset = queryset.filter(overall_esg_score__gte=min_score)
        
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return ESGAssessmentSummarySerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ESGAssessmentCreateUpdateSerializer
        else:
            return ESGAssessmentDetailSerializer
    
    def perform_create(self, serializer):
        """Create ESG assessment with group context."""
        user = self.request.user
        group = user.groups.first()
        
        serializer.save(
            group=group,
            last_modified_by=user
        )
    
    @extend_schema(
        summary="Compare ESG assessments",
        description="Compare ESG assessments across multiple entities",
        request=ESGComparisonSerializer,
        responses={200: dict}
    )
    @action(detail=False, methods=['post'])
    def compare(self, request):
        """Compare ESG assessments across entities."""
        serializer = ESGComparisonSerializer(data=request.data)
        
        if serializer.is_valid():
            entity_ids = serializer.validated_data['entity_ids']
            entity_type = serializer.validated_data['entity_type']
            date_range = serializer.validated_data.get('date_range', 'latest')
            comparison_metrics = serializer.validated_data.get('comparison_metrics')
            
            # Build base filter
            filters = Q(group__in=request.user.groups.all())
            
            if entity_type == 'partner':
                filters &= Q(partner_id__in=entity_ids)
            else:  # scheme
                filters &= Q(scheme_id__in=entity_ids)
            
            # Apply date range filter
            if date_range == 'latest':
                # Get latest assessment for each entity
                assessments = []
                for entity_id in entity_ids:
                    if entity_type == 'partner':
                        latest = ESGAssessment.objects.filter(
                            filters,
                            partner_id=entity_id
                        ).order_by('-assessment_period_end').first()
                    else:
                        latest = ESGAssessment.objects.filter(
                            filters,
                            scheme_id=entity_id
                        ).order_by('-assessment_period_end').first()
                    
                    if latest:
                        assessments.append(latest)
            else:
                # Get all assessments in date range
                if date_range == 'last_year':
                    start_date = date.today() - timedelta(days=365)
                elif date_range == 'last_2_years':
                    start_date = date.today() - timedelta(days=730)
                else:  # all
                    start_date = None
                
                if start_date:
                    filters &= Q(assessment_period_end__gte=start_date)
                
                assessments = ESGAssessment.objects.filter(filters)
            
            # Build comparison data
            comparison_data = []
            
            for assessment in assessments:
                entity = assessment.partner or assessment.scheme
                entity_name = entity.company_name if hasattr(entity, 'company_name') else entity.scheme_name
                
                data = {
                    'entity_id': str(entity.id),
                    'entity_name': entity_name,
                    'assessment_date': assessment.assessment_period_end,
                    'framework': assessment.assessment_framework
                }
                
                # Add requested metrics
                if 'overall_score' in comparison_metrics:
                    data['overall_esg_score'] = float(assessment.overall_esg_score) if assessment.overall_esg_score else None
                    data['esg_rating'] = assessment.esg_rating
                
                if 'environmental' in comparison_metrics:
                    data['environmental_score'] = assessment.environmental_score
                    data['carbon_footprint'] = float(assessment.carbon_footprint_tonnes) if assessment.carbon_footprint_tonnes else None
                    data['renewable_energy_pct'] = float(assessment.renewable_energy_pct) if assessment.renewable_energy_pct else None
                
                if 'social' in comparison_metrics:
                    data['social_score'] = assessment.social_score
                    data['student_satisfaction'] = float(assessment.student_satisfaction_score) if assessment.student_satisfaction_score else None
                    data['local_employment_pct'] = float(assessment.local_employment_pct) if assessment.local_employment_pct else None
                
                if 'governance' in comparison_metrics:
                    data['governance_score'] = assessment.governance_score
                    data['board_diversity_pct'] = float(assessment.board_diversity_pct) if assessment.board_diversity_pct else None
                    data['transparency_score'] = assessment.transparency_score
                
                if 'carbon_footprint' in comparison_metrics:
                    data['carbon_intensity'] = float(assessment.carbon_intensity) if assessment.carbon_intensity else None
                
                if 'energy_efficiency' in comparison_metrics:
                    data['energy_efficiency_rating'] = assessment.energy_efficiency_rating
                
                if 'certifications' in comparison_metrics:
                    data['environmental_certifications'] = assessment.environmental_certifications
                
                comparison_data.append(data)
            
            # Calculate averages and rankings
            metrics_to_average = [
                'overall_esg_score', 'environmental_score', 'social_score',
                'governance_score', 'carbon_footprint', 'renewable_energy_pct',
                'student_satisfaction', 'local_employment_pct', 'board_diversity_pct',
                'transparency_score', 'carbon_intensity'
            ]
            
            averages = {}
            for metric in metrics_to_average:
                values = [d.get(metric) for d in comparison_data if d.get(metric) is not None]
                if values:
                    averages[metric] = sum(values) / len(values)
            
            return Response({
                'entity_type': entity_type,
                'entities_compared': len(entity_ids),
                'assessments_included': len(comparison_data),
                'date_range': date_range,
                'comparison_metrics': comparison_metrics,
                'comparison_data': comparison_data,
                'averages': averages,
                'generated_at': datetime.now().isoformat()
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Get ESG improvement recommendations",
        description="Get AI-generated improvement recommendations based on ESG scores",
        responses={200: dict}
    )
    @action(detail=True, methods=['get'])
    def recommendations(self, request, pk=None):
        """Get improvement recommendations for ESG assessment."""
        assessment = self.get_object()
        
        recommendations = []
        
        # Environmental recommendations
        if assessment.environmental_score < 4:
            if assessment.renewable_energy_pct and assessment.renewable_energy_pct < 50:
                recommendations.append({
                    'category': 'Environmental',
                    'priority': 'High' if assessment.renewable_energy_pct < 20 else 'Medium',
                    'recommendation': 'Increase renewable energy usage',
                    'target': 'Achieve 50% renewable energy within 2 years',
                    'impact': 'Could improve environmental score by up to 1 point'
                })
            
            if assessment.waste_diversion_rate_pct and assessment.waste_diversion_rate_pct < 70:
                recommendations.append({
                    'category': 'Environmental',
                    'priority': 'Medium',
                    'recommendation': 'Improve waste management and recycling',
                    'target': 'Achieve 70% waste diversion rate',
                    'impact': 'Reduces landfill impact and improves sustainability metrics'
                })
        
        # Social recommendations
        if assessment.social_score < 4:
            if assessment.student_satisfaction_score and assessment.student_satisfaction_score < 4:
                recommendations.append({
                    'category': 'Social',
                    'priority': 'High',
                    'recommendation': 'Enhance student experience and satisfaction',
                    'target': 'Achieve 4.0+ student satisfaction score',
                    'impact': 'Directly impacts social score and reputation'
                })
            
            if assessment.local_employment_pct and assessment.local_employment_pct < 60:
                recommendations.append({
                    'category': 'Social',
                    'priority': 'Medium',
                    'recommendation': 'Increase local employment opportunities',
                    'target': 'Achieve 60% local employment',
                    'impact': 'Strengthens community relations and social impact'
                })
        
        # Governance recommendations
        if assessment.governance_score < 4:
            if assessment.board_diversity_pct and assessment.board_diversity_pct < 30:
                recommendations.append({
                    'category': 'Governance',
                    'priority': 'High',
                    'recommendation': 'Improve board diversity',
                    'target': 'Achieve 30% board diversity',
                    'impact': 'Enhances decision-making and governance score'
                })
            
            if not assessment.anti_corruption_policies:
                recommendations.append({
                    'category': 'Governance',
                    'priority': 'Critical',
                    'recommendation': 'Implement anti-corruption policies',
                    'target': 'Complete within 3 months',
                    'impact': 'Essential for governance compliance and risk management'
                })
        
        # Sort by priority
        priority_order = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 999))
        
        return Response({
            'assessment_id': str(assessment.id),
            'current_rating': assessment.esg_rating,
            'overall_score': float(assessment.overall_esg_score) if assessment.overall_esg_score else None,
            'recommendations_count': len(recommendations),
            'recommendations': recommendations,
            'potential_rating_improvement': self._calculate_potential_improvement(assessment, recommendations),
            'generated_at': datetime.now().isoformat()
        })
    
    def _calculate_potential_improvement(self, assessment, recommendations):
        """Calculate potential ESG rating improvement."""
        # Simplified calculation - each high priority recommendation could improve score by 0.2
        high_priority_count = sum(1 for r in recommendations if r['priority'] in ['Critical', 'High'])
        potential_score_increase = high_priority_count * 0.2
        
        new_score = float(assessment.overall_esg_score or 0) + potential_score_increase
        
        # Determine new rating
        if new_score >= 4.5:
            new_rating = 'AAA'
        elif new_score >= 4.0:
            new_rating = 'AA'
        elif new_score >= 3.5:
            new_rating = 'A'
        elif new_score >= 3.0:
            new_rating = 'BBB'
        elif new_score >= 2.5:
            new_rating = 'BB'
        elif new_score >= 2.0:
            new_rating = 'B'
        else:
            new_rating = 'CCC'
        
        return {
            'current_rating': assessment.esg_rating,
            'potential_rating': new_rating,
            'score_increase': round(potential_score_increase, 2)
        }


@extend_schema_view(
    list=extend_schema(
        summary="List audit trail entries",
        description="Get paginated list of audit trail entries (read-only)"
    ),
    retrieve=extend_schema(
        summary="Get audit trail details",
        description="Get detailed audit trail information"
    )
)
class AuditTrailViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for audit trail entries.
    
    Provides access to system audit logs for compliance
    and security monitoring purposes.
    """
    
    serializer_class = AuditTrailSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['change_summary', 'business_justification', 'user__email']
    ordering_fields = ['created_at', 'risk_assessment']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get audit logs based on user role."""
        user = self.request.user
        
        # Only auditors and admins can view audit logs
        if not hasattr(user, 'role') or user.role not in ['AUDITOR', 'ADMIN']:
            return AuditTrail.objects.none()
        
        queryset = AuditTrail.objects.all().select_related('user')
        
        # Add filters
        entity_type = self.request.query_params.get('entity_type')
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        
        entity_id = self.request.query_params.get('entity_id')
        if entity_id:
            queryset = queryset.filter(entity_id=entity_id)
        
        action_type = self.request.query_params.get('action_type')
        if action_type:
            queryset = queryset.filter(action_type=action_type)
        
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        risk_level = self.request.query_params.get('risk_level')
        if risk_level:
            queryset = queryset.filter(risk_assessment=risk_level)
        
        # Date range
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        return queryset
    
    @extend_schema(
        summary="Get audit statistics",
        description="Get audit trail statistics and activity summary",
        parameters=[
            OpenApiParameter(
                name='days',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                default=30,
                description='Number of days to analyze'
            )
        ],
        responses={200: dict}
    )
    @action(detail=False, methods=['get'])
    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    def statistics(self, request):
        """Get audit trail statistics."""
        days = int(request.query_params.get('days', 30))
        start_date = datetime.now() - timedelta(days=days)
        
        queryset = self.get_queryset().filter(created_at__gte=start_date)
        
        # Activity by action type
        action_breakdown = queryset.values('action_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Activity by entity type
        entity_breakdown = queryset.values('entity_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Activity by risk level
        risk_breakdown = queryset.values('risk_assessment').annotate(
            count=Count('id')
        ).order_by('risk_assessment')
        
        # Most active users
        user_activity = queryset.values(
            'user__id', 'user__email', 'user__first_name', 'user__last_name'
        ).annotate(
            action_count=Count('id')
        ).order_by('-action_count')[:10]
        
        # Daily activity trend
        daily_activity = queryset.extra(
            select={'date': 'DATE(created_at)'}
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        # High risk activities
        high_risk_count = queryset.filter(
            risk_assessment__in=[RiskLevel.HIGH, RiskLevel.CRITICAL]
        ).count()
        
        return Response({
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': datetime.now().isoformat()
            },
            'summary': {
                'total_activities': queryset.count(),
                'unique_users': queryset.values('user').distinct().count(),
                'unique_entities': queryset.values('entity_type', 'entity_id').distinct().count(),
                'high_risk_activities': high_risk_count,
                'average_daily_activities': queryset.count() / days if days > 0 else 0
            },
            'breakdown': {
                'by_action': list(action_breakdown),
                'by_entity_type': list(entity_breakdown),
                'by_risk_level': list(risk_breakdown)
            },
            'top_users': [
                {
                    'user_id': user['user__id'],
                    'email': user['user__email'],
                    'name': f"{user['user__first_name']} {user['user__last_name']}".strip(),
                    'action_count': user['action_count']
                }
                for user in user_activity
            ],
            'daily_trend': list(daily_activity),
            'generated_at': datetime.now().isoformat()
        })