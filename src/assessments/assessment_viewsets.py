"""
API viewsets for the CASA Gold-Standard Assessment Framework.

Provides comprehensive API endpoints for assessments, metrics, templates,
and workflow management with proper permissions and filtering.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any

from django.db.models import Q, Count, Avg, Sum
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view

from accounts.permissions import IsAuthenticated, GroupFilteredPermission
from .assessment_models import (
    Assessment, AssessmentMetric, AssessmentTemplate, MetricTemplate,
    AssessmentType, MetricCategory, DecisionBand
)
from .assessment_serializers import (
    AssessmentSummarySerializer, AssessmentDetailSerializer,
    AssessmentCreateUpdateSerializer, AssessmentMetricEnhancedSerializer,
    AssessmentTemplateSerializer, MetricTemplateSerializer,
    AssessmentWorkflowSerializer, AssessmentMetricBulkCreateSerializer,
    AssessmentAnalyticsSerializer
)
from .enums import AssessmentStatus
from .filters import AssessmentFilter, AssessmentMetricFilter


@extend_schema_view(
    list=extend_schema(
        summary="List assessments",
        description="Get paginated list of assessments with filtering and search capabilities"
    ),
    retrieve=extend_schema(
        summary="Get assessment details",
        description="Get detailed assessment information including metrics and calculations"
    ),
    create=extend_schema(
        summary="Create assessment",
        description="Create a new assessment with basic information"
    ),
    update=extend_schema(
        summary="Update assessment",
        description="Update assessment information"
    ),
    partial_update=extend_schema(
        summary="Partially update assessment",
        description="Partially update assessment fields"
    ),
    destroy=extend_schema(
        summary="Delete assessment",
        description="Delete an assessment (only if in draft status)"
    )
)
class AssessmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing assessments with comprehensive functionality.
    
    Provides CRUD operations, workflow management, scoring calculations,
    and analytics for the CASA assessment framework.
    """
    
    permission_classes = [IsAuthenticated, GroupFilteredPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = AssessmentFilter
    search_fields = ['assessment_name', 'partner__company_name', 'scheme__scheme_name']
    ordering_fields = ['assessment_date', 'total_weighted_score', 'score_percentage', 'created_at']
    ordering = ['-assessment_date', '-created_at']
    
    def get_queryset(self):
        """Get assessments filtered by user's group."""
        return Assessment.objects.filter(
            group__in=self.request.user.groups.all()
        ).select_related(
            'partner', 'scheme', 'assessor', 'reviewer', 'approver',
            'partner__general_info', 'partner__operational_info'
        ).prefetch_related(
            'assessment_metrics'
        )
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return AssessmentSummarySerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return AssessmentCreateUpdateSerializer
        else:
            return AssessmentDetailSerializer
    
    def perform_create(self, serializer):
        """Create assessment with user and group context."""
        user = self.request.user
        group = user.groups.first()
        
        serializer.save(
            group=group,
            assessor=user
        )
    
    def perform_destroy(self, instance):
        """Only allow deletion of draft assessments."""
        if instance.status != AssessmentStatus.DRAFT:
            raise PermissionError("Only draft assessments can be deleted")
        
        super().perform_destroy(instance)
    
    @extend_schema(
        summary="Submit assessment for review",
        description="Submit a draft assessment for review, triggering score calculations",
        request=AssessmentWorkflowSerializer,
        responses={200: AssessmentDetailSerializer}
    )
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit assessment for review."""
        assessment = self.get_object()
        serializer = AssessmentWorkflowSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                assessment.submit_for_review(request.user)
                return Response(
                    AssessmentDetailSerializer(assessment, context={'request': request}).data,
                    status=status.HTTP_200_OK
                )
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Approve assessment",
        description="Approve an assessment in review, finalizing the evaluation",
        request=AssessmentWorkflowSerializer,
        responses={200: AssessmentDetailSerializer}
    )
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve assessment."""
        assessment = self.get_object()
        serializer = AssessmentWorkflowSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                assessment.approve(request.user)
                return Response(
                    AssessmentDetailSerializer(assessment, context={'request': request}).data,
                    status=status.HTTP_200_OK
                )
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Reject assessment",
        description="Reject an assessment with reason, returning it to draft status",
        request=AssessmentWorkflowSerializer,
        responses={200: AssessmentDetailSerializer}
    )
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject assessment."""
        assessment = self.get_object()
        serializer = AssessmentWorkflowSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                reason = serializer.validated_data.get('reason', '')
                assessment.reject(request.user, reason)
                return Response(
                    AssessmentDetailSerializer(assessment, context={'request': request}).data,
                    status=status.HTTP_200_OK
                )
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Refresh calculated fields",
        description="Recalculate all assessment scores and decision bands",
        responses={200: AssessmentDetailSerializer}
    )
    @action(detail=True, methods=['post'])
    def refresh_scores(self, request, pk=None):
        """Refresh all calculated fields."""
        assessment = self.get_object()
        assessment.refresh_calculated_fields()
        
        return Response(
            AssessmentDetailSerializer(assessment, context={'request': request}).data,
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Create metrics from template",
        description="Bulk create assessment metrics from a template",
        request=AssessmentMetricBulkCreateSerializer,
        responses={201: AssessmentDetailSerializer}
    )
    @action(detail=True, methods=['post'])
    def create_metrics_from_template(self, request, pk=None):
        """Create metrics from template."""
        assessment = self.get_object()
        serializer = AssessmentMetricBulkCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            template_id = serializer.validated_data['template_id']
            overrides = serializer.validated_data.get('metric_overrides', {})
            
            try:
                template = AssessmentTemplate.objects.get(
                    id=template_id,
                    group__in=request.user.groups.all()
                )
                
                # Validate assessment type matches template
                if assessment.assessment_type != template.assessment_type:
                    return Response(
                        {'error': 'Assessment type does not match template type'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                with transaction.atomic():
                    # Create metrics from template
                    metrics_created = 0
                    for metric_template in template.metric_templates.all():
                        # Check if metric already exists
                        if not assessment.assessment_metrics.filter(
                            metric_name=metric_template.metric_name
                        ).exists():
                            
                            # Apply overrides if specified
                            override_data = overrides.get(metric_template.metric_name, {})
                            weight = override_data.get('weight', metric_template.default_weight)
                            score = override_data.get('score', None)
                            
                            AssessmentMetric.objects.create(
                                group=assessment.group,
                                assessment=assessment,
                                metric_name=metric_template.metric_name,
                                metric_description=metric_template.metric_description,
                                category=metric_template.category,
                                score=score or 3,  # Default to neutral score
                                weight=weight,
                                justification=override_data.get('justification', 'Created from template'),
                                assessment_method='TEMPLATE',
                                confidence_level='MEDIUM'
                            )
                            metrics_created += 1
                    
                    # Refresh calculated fields
                    assessment.refresh_calculated_fields()
                
                return Response(
                    {
                        'message': f'Created {metrics_created} metrics from template',
                        'assessment': AssessmentDetailSerializer(assessment, context={'request': request}).data
                    },
                    status=status.HTTP_201_CREATED
                )
                
            except AssessmentTemplate.DoesNotExist:
                return Response(
                    {'error': 'Template not found or not accessible'},
                    status=status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Get assessment analytics",
        description="Get comprehensive analytics and reporting for assessments",
        parameters=[AssessmentAnalyticsSerializer],
        responses={200: dict}
    )
    @action(detail=False, methods=['get'])
    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    def analytics(self, request):
        """Get assessment analytics."""
        serializer = AssessmentAnalyticsSerializer(data=request.query_params)
        
        if serializer.is_valid():
            filters = Q(group__in=request.user.groups.all())
            
            # Apply date filters
            if serializer.validated_data.get('date_from'):
                filters &= Q(assessment_date__gte=serializer.validated_data['date_from'])
            
            if serializer.validated_data.get('date_to'):
                filters &= Q(assessment_date__lte=serializer.validated_data['date_to'])
            
            # Apply type filter
            if serializer.validated_data.get('assessment_type'):
                filters &= Q(assessment_type=serializer.validated_data['assessment_type'])
            
            queryset = Assessment.objects.filter(filters)
            
            # Basic statistics
            total_assessments = queryset.count()
            avg_score = queryset.aggregate(avg_score=Avg('score_percentage'))['avg_score'] or 0
            
            # Status breakdown
            status_counts = queryset.values('status').annotate(
                count=Count('id')
            ).order_by('status')
            
            # Decision band breakdown
            decision_counts = queryset.exclude(decision_band='').values('decision_band').annotate(
                count=Count('id')
            ).order_by('decision_band')
            
            # Assessment type breakdown
            type_counts = queryset.values('assessment_type').annotate(
                count=Count('id')
            ).order_by('assessment_type')
            
            # Category performance (for completed assessments)
            completed_assessments = queryset.filter(status=AssessmentStatus.APPROVED)
            category_performance = {}
            
            if completed_assessments.exists():
                for category in MetricCategory.choices:
                    metrics = AssessmentMetric.objects.filter(
                        assessment__in=completed_assessments,
                        category=category[0]
                    )
                    
                    if metrics.exists():
                        avg_score = metrics.aggregate(
                            avg_score=Avg('score')
                        )['avg_score']
                        avg_weight = metrics.aggregate(
                            avg_weight=Avg('weight')
                        )['avg_weight']
                        
                        category_performance[category[0]] = {
                            'name': category[1],
                            'avg_score': round(avg_score, 2) if avg_score else 0,
                            'avg_weight': round(avg_weight, 2) if avg_weight else 0,
                            'metric_count': metrics.count()
                        }
            
            # Time-based grouping if requested
            time_series = {}
            group_by = serializer.validated_data.get('group_by')
            
            if group_by in ['month', 'quarter']:
                if group_by == 'month':
                    time_series = queryset.extra(
                        select={'period': 'DATE_TRUNC(\'month\', assessment_date)'}
                    ).values('period').annotate(
                        count=Count('id'),
                        avg_score=Avg('score_percentage')
                    ).order_by('period')
                elif group_by == 'quarter':
                    time_series = queryset.extra(
                        select={'period': 'DATE_TRUNC(\'quarter\', assessment_date)'}
                    ).values('period').annotate(
                        count=Count('id'),
                        avg_score=Avg('score_percentage')
                    ).order_by('period')
            
            return Response({
                'summary': {
                    'total_assessments': total_assessments,
                    'average_score_percentage': round(avg_score, 2),
                    'completed_assessments': completed_assessments.count(),
                    'pending_assessments': queryset.filter(
                        status__in=[AssessmentStatus.DRAFT, AssessmentStatus.IN_REVIEW]
                    ).count()
                },
                'status_breakdown': list(status_counts),
                'decision_breakdown': list(decision_counts),
                'type_breakdown': list(type_counts),
                'category_performance': category_performance,
                'time_series': list(time_series) if time_series else None,
                'generated_at': datetime.now().isoformat()
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema_view(
    list=extend_schema(
        summary="List assessment metrics",
        description="Get paginated list of assessment metrics with filtering"
    ),
    retrieve=extend_schema(
        summary="Get metric details",
        description="Get detailed metric information with calculations"
    ),
    create=extend_schema(
        summary="Create metric",
        description="Create a new assessment metric"
    ),
    update=extend_schema(
        summary="Update metric",
        description="Update metric information and automatically refresh assessment scores"
    ),
    destroy=extend_schema(
        summary="Delete metric",
        description="Delete a metric and refresh assessment scores"
    )
)
class AssessmentMetricViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing assessment metrics.
    
    Provides CRUD operations for individual metrics with automatic
    score recalculation when metrics are modified.
    """
    
    serializer_class = AssessmentMetricEnhancedSerializer
    permission_classes = [IsAuthenticated, GroupFilteredPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = AssessmentMetricFilter
    search_fields = ['metric_name', 'justification']
    ordering_fields = ['category', 'metric_name', 'score', 'weight', 'weighted_score']
    ordering = ['category', 'metric_name']
    
    def get_queryset(self):
        """Get metrics filtered by user's group."""
        return AssessmentMetric.objects.filter(
            group__in=self.request.user.groups.all()
        ).select_related('assessment')
    
    def perform_create(self, serializer):
        """Create metric with group context and refresh scores."""
        group = self.request.user.groups.first()
        metric = serializer.save(group=group)
        
        # Refresh assessment calculated fields
        metric.assessment.refresh_calculated_fields()
    
    def perform_update(self, serializer):
        """Update metric and refresh assessment scores."""
        metric = serializer.save()
        
        # Refresh assessment calculated fields
        metric.assessment.refresh_calculated_fields()
    
    def perform_destroy(self, instance):
        """Delete metric and refresh assessment scores."""
        assessment = instance.assessment
        super().perform_destroy(instance)
        
        # Refresh assessment calculated fields
        assessment.refresh_calculated_fields()


@extend_schema_view(
    list=extend_schema(
        summary="List assessment templates",
        description="Get available assessment templates with metric definitions"
    ),
    retrieve=extend_schema(
        summary="Get template details",
        description="Get detailed template information including all metric templates"
    )
)
class AssessmentTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for assessment templates.
    
    Provides access to standard assessment templates and their
    metric definitions for creating consistent assessments.
    """
    
    serializer_class = AssessmentTemplateSerializer
    permission_classes = [IsAuthenticated, GroupFilteredPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['template_name', 'description']
    ordering_fields = ['template_name', 'assessment_type', 'version']
    ordering = ['assessment_type', 'template_name']
    
    def get_queryset(self):
        """Get templates filtered by user's group and active status."""
        return AssessmentTemplate.objects.filter(
            group__in=self.request.user.groups.all(),
            is_active=True
        ).prefetch_related('metric_templates')
    
    def filter_queryset(self, queryset):
        """Add additional filtering by assessment type."""
        queryset = super().filter_queryset(queryset)
        
        assessment_type = self.request.query_params.get('assessment_type')
        if assessment_type:
            queryset = queryset.filter(assessment_type=assessment_type)
        
        return queryset


@extend_schema_view(
    list=extend_schema(
        summary="List metric templates",
        description="Get metric template definitions for building assessments"
    ),
    retrieve=extend_schema(
        summary="Get metric template details",
        description="Get detailed metric template with scoring criteria"
    )
)
class MetricTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for metric templates.
    
    Provides access to standard metric definitions including
    scoring criteria and assessment guidelines.
    """
    
    serializer_class = MetricTemplateSerializer
    permission_classes = [IsAuthenticated, GroupFilteredPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['metric_name', 'metric_description']
    ordering_fields = ['category', 'metric_name', 'default_weight', 'display_order']
    ordering = ['category', 'display_order', 'metric_name']
    
    def get_queryset(self):
        """Get metric templates filtered by user's group."""
        return MetricTemplate.objects.filter(
            template__group__in=self.request.user.groups.all(),
            template__is_active=True
        ).select_related('template')
    
    def filter_queryset(self, queryset):
        """Add additional filtering options."""
        queryset = super().filter_queryset(queryset)
        
        # Filter by template
        template_id = self.request.query_params.get('template')
        if template_id:
            queryset = queryset.filter(template_id=template_id)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by mandatory status
        mandatory = self.request.query_params.get('mandatory')
        if mandatory is not None:
            queryset = queryset.filter(is_mandatory=mandatory.lower() == 'true')
        
        return queryset