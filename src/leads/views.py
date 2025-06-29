"""
Lead Management Views.

ViewSets for managing lead scoring models, leads, and lead activities
with comprehensive filtering, searching, and custom actions.
"""

from rest_framework import viewsets
from platform_core.core.views import PlatformViewSet, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters import rest_framework as filters
from django.db.models import Q

from platform_core.accounts.permissions import GroupAccessPermission
from .models import LeadScoringModel, Lead, LeadActivity
from .serializers import (
    LeadScoringModelSerializer, LeadSerializer, LeadActivitySerializer,
    LeadCreateSerializer, LeadUpdateSerializer
)
from .services import LeadScoringService, LeadWorkflowService
from .services.lead_recommendation_service import LeadRecommendationService
from .services.territory_analysis_service import TerritoryAnalysisService


class LeadScoringModelFilter(filters.FilterSet):
    """Filter for LeadScoringModel."""
    
    status = filters.CharFilter(field_name='status')
    scoring_method = filters.CharFilter(field_name='scoring_method')
    is_active = filters.BooleanFilter(method='filter_is_active')
    is_default = filters.BooleanFilter(field_name='is_default')
    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    class Meta:
        model = LeadScoringModel
        fields = ['status', 'scoring_method', 'is_active', 'is_default']
    
    def filter_is_active(self, queryset, name, value):
        if value:
            return queryset.filter(status=LeadScoringModel.ModelStatus.ACTIVE)
        return queryset.exclude(status=LeadScoringModel.ModelStatus.ACTIVE)


class LeadScoringModelViewSet(PlatformViewSet):
    """
    ViewSet for managing lead scoring models.
    
    Provides CRUD operations and custom actions for model activation,
    performance tracking, and analytics.
    """
    
    serializer_class = LeadScoringModelSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filterset_class = LeadScoringModelFilter
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'version', 'accuracy_score']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return LeadScoringModel.objects.filter(
            group=self.request.user.current_group
        ).select_related('created_by')
    
    def perform_create(self, serializer):
        serializer.save(
            group=self.request.user.current_group,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a scoring model."""
        scoring_model = self.get_object()
        service = LeadScoringService(user=request.user, group=request.user.current_group)
        
        try:
            activated_model = service.activate_scoring_model(str(scoring_model.id))
            serializer = self.get_serializer(activated_model)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get performance metrics for a scoring model."""
        scoring_model = self.get_object()
        service = LeadScoringService(user=request.user, group=request.user.current_group)
        
        try:
            performance = service.evaluate_model_performance(str(scoring_model.id))
            return Response(performance)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get the currently active scoring model."""
        service = LeadScoringService(user=request.user, group=request.user.current_group)
        active_model = service.get_active_scoring_model()
        
        if active_model:
            serializer = self.get_serializer(active_model)
            return Response(serializer.data)
        return Response(
            {'message': 'No active scoring model found'},
            status=status.HTTP_404_NOT_FOUND
        )


class LeadFilter(filters.FilterSet):
    """Filter for Lead with geographic intelligence support."""
    
    # Basic filters
    status = filters.CharFilter(field_name='status')
    source = filters.CharFilter(field_name='source')
    priority = filters.CharFilter(field_name='priority')
    assigned_to = filters.CharFilter(field_name='assigned_to__id')
    identified_by = filters.CharFilter(field_name='identified_by__id')
    score_min = filters.NumberFilter(field_name='current_score', lookup_expr='gte')
    score_max = filters.NumberFilter(field_name='current_score', lookup_expr='lte')
    is_qualified = filters.BooleanFilter(method='filter_is_qualified')
    is_high_priority = filters.BooleanFilter(method='filter_is_high_priority')
    is_stale = filters.BooleanFilter(method='filter_is_stale')
    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    last_scored_after = filters.DateTimeFilter(field_name='last_scored_at', lookup_expr='gte')
    last_scored_before = filters.DateTimeFilter(field_name='last_scored_at', lookup_expr='lte')
    headquarters_country = filters.CharFilter(field_name='headquarters_country')
    
    # Geographic Intelligence Filters
    target_neighborhood = filters.CharFilter(field_name='target_neighborhood__id')
    neighborhood_name = filters.CharFilter(field_name='target_neighborhood__name', lookup_expr='icontains')
    target_universities = filters.CharFilter(field_name='target_universities__id')
    university_name = filters.CharFilter(field_name='target_universities__name', lookup_expr='icontains')
    has_geographic_data = filters.BooleanFilter(method='filter_has_geographic_data')
    
    # Geographic Score Filters
    geographic_score_min = filters.NumberFilter(field_name='geographic_score', lookup_expr='gte')
    geographic_score_max = filters.NumberFilter(field_name='geographic_score', lookup_expr='lte')
    accessibility_score_min = filters.NumberFilter(field_name='accessibility_score', lookup_expr='gte')
    accessibility_score_max = filters.NumberFilter(field_name='accessibility_score', lookup_expr='lte')
    university_proximity_score_min = filters.NumberFilter(field_name='university_proximity_score', lookup_expr='gte')
    university_proximity_score_max = filters.NumberFilter(field_name='university_proximity_score', lookup_expr='lte')
    market_demand_score_min = filters.NumberFilter(field_name='market_demand_score', lookup_expr='gte')
    market_demand_score_max = filters.NumberFilter(field_name='market_demand_score', lookup_expr='lte')
    competition_score_min = filters.NumberFilter(field_name='competition_score', lookup_expr='gte')
    competition_score_max = filters.NumberFilter(field_name='competition_score', lookup_expr='lte')
    
    # Location-based filters (proximity search)
    near_latitude = filters.NumberFilter(method='filter_near_location')
    near_longitude = filters.NumberFilter(method='filter_near_location')
    radius_km = filters.NumberFilter(method='filter_near_location')
    
    # Time-based geographic filters
    geographic_analysis_after = filters.DateTimeFilter(field_name='geographic_analysis_date', lookup_expr='gte')
    geographic_analysis_before = filters.DateTimeFilter(field_name='geographic_analysis_date', lookup_expr='lte')
    needs_geographic_update = filters.BooleanFilter(method='filter_needs_geographic_update')
    
    class Meta:
        model = Lead
        fields = [
            'status', 'source', 'priority', 'assigned_to', 'identified_by',
            'score_min', 'score_max', 'headquarters_country',
            'target_neighborhood', 'neighborhood_name', 'target_universities', 'university_name',
            'geographic_score_min', 'geographic_score_max',
            'accessibility_score_min', 'accessibility_score_max',
            'university_proximity_score_min', 'university_proximity_score_max',
            'market_demand_score_min', 'market_demand_score_max',
            'competition_score_min', 'competition_score_max'
        ]
    
    def filter_is_qualified(self, queryset, name, value):
        if value:
            return queryset.filter(current_score__gte=70)  # Default threshold
        return queryset.filter(current_score__lt=70)
    
    def filter_is_high_priority(self, queryset, name, value):
        if value:
            return queryset.filter(current_score__gte=85)  # Default threshold
        return queryset.filter(current_score__lt=85)
    
    def filter_is_stale(self, queryset, name, value):
        # This would implement stale lead logic
        # For now, return all leads
        return queryset
    
    # Geographic filter methods
    
    def filter_has_geographic_data(self, queryset, name, value):
        """Filter leads based on whether they have geographic analysis data."""
        if value:
            return queryset.filter(geographic_analysis_date__isnull=False)
        return queryset.filter(geographic_analysis_date__isnull=True)
    
    def filter_near_location(self, queryset, name, value):
        """Filter leads based on proximity to a geographic location."""
        # This method is called for any of the location parameters
        # We need to check if all required parameters are present
        params = self.request.GET
        
        try:
            latitude = float(params.get('near_latitude'))
            longitude = float(params.get('near_longitude'))
            radius_km = float(params.get('radius_km', 10.0))  # Default 10km
            
            # Use PostGIS distance query
            from django.contrib.gis.geos import Point
            from django.contrib.gis.measure import Distance
            
            location = Point(longitude, latitude, srid=4326)
            return queryset.filter(
                headquarters_location__distance_lte=(location, Distance(km=radius_km))
            )
            
        except (ValueError, TypeError):
            # If parameters are invalid, return original queryset
            return queryset
    
    def filter_needs_geographic_update(self, queryset, name, value):
        """Filter leads that need geographic score updates."""
        from django.utils import timezone
        from datetime import timedelta
        
        if value:
            # Leads with no geographic analysis or outdated analysis (>7 days)
            cutoff_date = timezone.now() - timedelta(days=7)
            return queryset.filter(
                Q(geographic_analysis_date__isnull=True) |
                Q(geographic_analysis_date__lt=cutoff_date)
            ).filter(headquarters_location__isnull=False)
        else:
            # Leads with recent geographic analysis
            cutoff_date = timezone.now() - timedelta(days=7)
            return queryset.filter(
                geographic_analysis_date__gte=cutoff_date
            )


class LeadViewSet(PlatformViewSet):
    """
    ViewSet for managing leads.
    
    Provides CRUD operations and custom actions for scoring,
    workflow management, and conversion tracking.
    """
    
    serializer_class = LeadSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filterset_class = LeadFilter
    search_fields = [
        'company_name', 'trading_name', 'primary_contact_name',
        'primary_contact_email', 'headquarters_city', 'qualification_notes',
        'target_neighborhood__name', 'target_universities__name'
    ]
    ordering_fields = [
        'company_name', 'current_score', 'created_at', 'last_scored_at',
        'status', 'priority', 'geographic_score', 'accessibility_score',
        'university_proximity_score', 'market_demand_score', 'competition_score'
    ]
    ordering = ['-current_score', '-created_at']
    
    def get_queryset(self):
        return Lead.objects.filter(
            group=self.request.user.current_group
        ).select_related(
            'assigned_to', 'identified_by', 'scoring_model',
            'market_intelligence_target', 'target_neighborhood',
            'target_neighborhood__metrics'
        ).prefetch_related('activities', 'target_universities')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return LeadCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return LeadUpdateSerializer
        return LeadSerializer
    
    def perform_create(self, serializer):
        # Use LeadWorkflowService to create lead with initial scoring
        service = LeadWorkflowService(user=self.request.user, group=self.request.user.current_group)
        lead_data = serializer.validated_data
        lead = service.create_lead(lead_data)
        serializer.instance = lead
    
    @action(detail=True, methods=['post'])
    def calculate_score(self, request, pk=None):
        """Calculate score for a specific lead."""
        lead = self.get_object()
        service = LeadScoringService(user=request.user, group=request.user.current_group)
        
        scoring_model_id = request.data.get('scoring_model_id')
        
        try:
            result = service.calculate_lead_score(str(lead.id), scoring_model_id)
            return Response(result)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update lead status with workflow validation."""
        lead = self.get_object()
        service = LeadWorkflowService(user=request.user, group=request.user.current_group)
        
        new_status = request.data.get('status')
        notes = request.data.get('notes')
        
        if not new_status:
            return Response(
                {'error': 'Status is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            updated_lead = service.update_lead_status(str(lead.id), new_status, notes)
            serializer = self.get_serializer(updated_lead)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign lead to a user."""
        lead = self.get_object()
        service = LeadWorkflowService(user=request.user, group=request.user.current_group)
        
        assigned_to_id = request.data.get('assigned_to_id')
        notes = request.data.get('notes')
        
        if not assigned_to_id:
            return Response(
                {'error': 'assigned_to_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            updated_lead = service.assign_lead(str(lead.id), assigned_to_id, notes)
            serializer = self.get_serializer(updated_lead)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        """Convert lead to development partner."""
        lead = self.get_object()
        service = LeadWorkflowService(user=request.user, group=request.user.current_group)
        
        conversion_data = request.data.get('conversion_data', {})
        
        try:
            result = service.convert_lead_to_partner(str(lead.id), conversion_data)
            return Response(result)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        """Get complete timeline of activities for a lead."""
        lead = self.get_object()
        service = LeadWorkflowService(user=request.user, group=request.user.current_group)
        
        try:
            timeline = service.get_lead_timeline(str(lead.id))
            return Response({'timeline': timeline})
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def batch_score(self, request):
        """Score multiple leads in batch."""
        service = LeadScoringService(user=request.user, group=request.user.current_group)
        
        lead_ids = request.data.get('lead_ids')
        filters = request.data.get('filters')
        scoring_model_id = request.data.get('scoring_model_id')
        
        try:
            result = service.batch_score_leads(lead_ids, filters, scoring_model_id)
            return Response(result)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get comprehensive lead analytics."""
        scoring_service = LeadScoringService(user=request.user, group=request.user.current_group)
        workflow_service = LeadWorkflowService(user=request.user, group=request.user.current_group)
        
        days_back = int(request.query_params.get('days_back', 30))
        
        try:
            scoring_analytics = scoring_service.get_scoring_analytics(days_back)
            workflow_analytics = workflow_service.get_workflow_analytics(days_back)
            
            return Response({
                'scoring': scoring_analytics,
                'workflow': workflow_analytics
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def overdue_actions(self, request):
        """Get leads with overdue actions."""
        service = LeadWorkflowService(user=request.user, group=request.user.current_group)
        
        assigned_user_id = request.query_params.get('assigned_user_id')
        
        try:
            overdue_actions = service.get_overdue_actions(assigned_user_id)
            return Response({'overdue_actions': overdue_actions})
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def update_geographic_scores(self, request, pk=None):
        """Update geographic intelligence scores for a specific lead."""
        lead = self.get_object()
        
        try:
            lead.update_geographic_scores()
            serializer = self.get_serializer(lead)
            return Response({
                'message': 'Geographic scores updated successfully',
                'lead': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def refresh_geographic_scores(self, request):
        """Refresh geographic intelligence scores for multiple leads."""
        service = LeadScoringService(user=request.user, group=request.user.current_group)
        
        lead_ids = request.data.get('lead_ids')
        
        try:
            result = service.refresh_geographic_scores(lead_ids)
            return Response(result)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def geographic_analytics(self, request):
        """Get geographic intelligence analytics for leads."""
        service = LeadScoringService(user=request.user, group=request.user.current_group)
        
        try:
            analytics = service.get_geographic_analytics()
            return Response(analytics)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def location_opportunities(self, request):
        """Find high-potential locations based on geographic intelligence."""
        service = LeadScoringService(user=request.user, group=request.user.current_group)
        
        min_score = float(request.query_params.get('min_score', 80.0))
        
        try:
            opportunities = service.find_location_opportunities(min_score)
            return Response(opportunities)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def by_location(self, request):
        """Get leads filtered by common geographic criteria."""
        queryset = self.get_queryset()
        
        # Common geographic filters with predefined logic
        filter_type = request.query_params.get('filter_type')
        
        if filter_type == 'high_geographic_score':
            # Leads with geographic score >= 80
            queryset = queryset.filter(geographic_score__gte=80)
            
        elif filter_type == 'excellent_accessibility':
            # Leads with excellent transport links
            queryset = queryset.filter(accessibility_score__gte=85)
            
        elif filter_type == 'university_proximity':
            # Leads very close to universities
            queryset = queryset.filter(university_proximity_score__gte=90)
            
        elif filter_type == 'high_demand_markets':
            # Leads in high student demand areas
            queryset = queryset.filter(market_demand_score__gte=80)
            
        elif filter_type == 'low_competition':
            # Leads in low competition areas
            queryset = queryset.filter(competition_score__gte=75)
            
        elif filter_type == 'needs_geo_update':
            # Leads that need geographic analysis updates
            from django.utils import timezone
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=7)
            queryset = queryset.filter(
                Q(geographic_analysis_date__isnull=True) |
                Q(geographic_analysis_date__lt=cutoff_date)
            ).filter(headquarters_location__isnull=False)
            
        elif filter_type == 'geo_complete':
            # Leads with complete geographic analysis
            queryset = queryset.filter(
                geographic_analysis_date__isnull=False,
                target_neighborhood__isnull=False
            )
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'filter_type': filter_type,
            'count': queryset.count(),
            'results': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def geographic_summary(self, request):
        """Get geographic distribution summary of leads."""
        queryset = self.get_queryset()
        
        # Get counts by geographic score ranges
        score_ranges = {
            'excellent_geo': queryset.filter(geographic_score__gte=90).count(),
            'good_geo': queryset.filter(geographic_score__gte=80, geographic_score__lt=90).count(),
            'fair_geo': queryset.filter(geographic_score__gte=70, geographic_score__lt=80).count(),
            'poor_geo': queryset.filter(geographic_score__lt=70, geographic_score__gt=0).count(),
            'no_geo_data': queryset.filter(geographic_score=0).count()
        }
        
        # Get top neighborhoods
        from django.db.models import Count, Avg
        top_neighborhoods = queryset.filter(
            target_neighborhood__isnull=False
        ).values(
            'target_neighborhood__name',
            'target_neighborhood__id'
        ).annotate(
            lead_count=Count('id'),
            avg_geographic_score=Avg('geographic_score')
        ).order_by('-lead_count')[:10]
        
        # Get top universities
        top_universities = queryset.filter(
            target_universities__isnull=False
        ).values(
            'target_universities__name',
            'target_universities__id'
        ).annotate(
            lead_count=Count('id'),
            avg_university_proximity=Avg('university_proximity_score')
        ).order_by('-lead_count')[:10]
        
        return Response({
            'total_leads': queryset.count(),
            'score_distribution': score_ranges,
            'top_neighborhoods': list(top_neighborhoods),
            'top_universities': list(top_universities),
            'coverage_stats': {
                'has_location': queryset.filter(headquarters_location__isnull=False).count(),
                'has_neighborhood': queryset.filter(target_neighborhood__isnull=False).count(),
                'has_universities': queryset.filter(target_universities__isnull=False).count(),
                'has_complete_analysis': queryset.filter(geographic_analysis_date__isnull=False).count()
            }
        })
    
    @action(detail=False, methods=['get'])
    def recommendations_by_location(self, request):
        """Get lead recommendations for a specific geographic location."""
        service = LeadRecommendationService(user=request.user, group=request.user.current_group)
        
        try:
            latitude = float(request.query_params.get('latitude'))
            longitude = float(request.query_params.get('longitude'))
            radius_km = float(request.query_params.get('radius_km', 10.0))
            limit = int(request.query_params.get('limit', 10))
            
            recommendations = service.get_recommendations_for_location(
                latitude=latitude,
                longitude=longitude,
                radius_km=radius_km,
                limit=limit
            )
            return Response(recommendations)
            
        except (ValueError, TypeError) as e:
            return Response(
                {'error': f'Invalid parameters: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def recommendations_by_neighborhood(self, request):
        """Get lead recommendations for a specific neighborhood."""
        service = LeadRecommendationService(user=request.user, group=request.user.current_group)
        
        neighborhood_id = request.query_params.get('neighborhood_id')
        limit = int(request.query_params.get('limit', 10))
        
        if not neighborhood_id:
            return Response(
                {'error': 'neighborhood_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            recommendations = service.get_recommendations_for_neighborhood(
                neighborhood_id=neighborhood_id,
                limit=limit
            )
            return Response(recommendations)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def strategic_recommendations(self, request):
        """Get lead recommendations based on strategic investment criteria."""
        service = LeadRecommendationService(user=request.user, group=request.user.current_group)
        
        strategy_type = request.query_params.get('strategy_type')
        limit = int(request.query_params.get('limit', 20))
        
        available_strategies = [
            'expansion', 'premium', 'value', 'university_focused', 
            'transport_hubs', 'emerging_markets', 'diversification'
        ]
        
        if not strategy_type:
            return Response({
                'error': 'strategy_type parameter is required',
                'available_strategies': available_strategies
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if strategy_type not in available_strategies:
            return Response({
                'error': f'Invalid strategy_type: {strategy_type}',
                'available_strategies': available_strategies
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            recommendations = service.get_strategic_recommendations(
                strategy_type=strategy_type,
                limit=limit
            )
            return Response(recommendations)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def portfolio_optimization(self, request):
        """Get lead recommendations for portfolio optimization."""
        service = LeadRecommendationService(user=request.user, group=request.user.current_group)
        
        constraints = request.data.get('constraints', {})
        limit = int(request.data.get('limit', 15))
        
        try:
            recommendations = service.get_portfolio_optimization_recommendations(
                portfolio_constraints=constraints,
                limit=limit
            )
            return Response(recommendations)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def recommendation_strategies(self, request):
        """Get available recommendation strategies and their descriptions."""
        strategies = {
            'expansion': {
                'name': 'Market Expansion',
                'description': 'Focus on leads with strong geographic fundamentals and transport connectivity',
                'criteria': 'Geographic score ≥70, Accessibility score ≥75',
                'best_for': 'Growing market presence in new areas'
            },
            'premium': {
                'name': 'Premium Investment',
                'description': 'Target high-quality leads near major universities',
                'criteria': 'Lead score ≥80, University proximity ≥85',
                'best_for': 'High-end student accommodation projects'
            },
            'value': {
                'name': 'Value Investment',
                'description': 'Identify undervalued opportunities with low competition',
                'criteria': 'Competition score ≥70, Geographic score ≥60',
                'best_for': 'Cost-effective market entry'
            },
            'university_focused': {
                'name': 'University-Centric',
                'description': 'Prioritize proximity to major universities and student populations',
                'criteria': 'University proximity ≥80, has target universities',
                'best_for': 'Purpose-built student accommodation'
            },
            'transport_hubs': {
                'name': 'Transport Accessibility',
                'description': 'Focus on areas with excellent transport connectivity',
                'criteria': 'Accessibility score ≥85',
                'best_for': 'Commuter-friendly developments'
            },
            'emerging_markets': {
                'name': 'Emerging Markets',
                'description': 'Target high-demand areas with growth potential',
                'criteria': 'Market demand ≥75, Competition score ≥65',
                'best_for': 'Early market entry opportunities'
            },
            'diversification': {
                'name': 'Portfolio Diversification',
                'description': 'Spread investments across different neighborhoods and markets',
                'criteria': 'Geographic score ≥65, avoid over-concentration',
                'best_for': 'Risk mitigation and balanced portfolio'
            }
        }
        
        return Response({
            'available_strategies': strategies,
            'usage': {
                'endpoint': '/api/leads/strategic_recommendations/',
                'parameters': {
                    'strategy_type': 'One of the strategy keys above',
                    'limit': 'Number of recommendations (default: 20)'
                }
            }
        })
    
    @action(detail=False, methods=['get'])
    def territory_analysis(self, request):
        """Get territory coverage analysis for a user or all users."""
        service = TerritoryAnalysisService(user=request.user, group=request.user.current_group)
        
        assigned_user_id = request.query_params.get('assigned_user_id')
        
        try:
            analysis = service.analyze_territory_coverage(assigned_user_id)
            return Response(analysis)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def optimize_assignments(self, request):
        """Get optimized lead assignment recommendations."""
        service = TerritoryAnalysisService(user=request.user, group=request.user.current_group)
        
        optimization_criteria = request.data.get('criteria', {})
        
        try:
            optimization = service.optimize_lead_assignments(optimization_criteria)
            return Response(optimization)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def execute_assignments(self, request):
        """Execute the recommended lead assignments."""
        service = TerritoryAnalysisService(user=request.user, group=request.user.current_group)
        
        assignments = request.data.get('assignments', [])
        create_activities = request.data.get('create_activities', True)
        
        if not assignments:
            return Response(
                {'error': 'assignments parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            result = service.execute_assignment_optimization(assignments, create_activities)
            return Response(result)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def territory_performance(self, request):
        """Get comprehensive territory performance analysis."""
        service = TerritoryAnalysisService(user=request.user, group=request.user.current_group)
        
        time_period_days = int(request.query_params.get('time_period_days', 30))
        
        try:
            performance = service.get_territory_performance_analysis(time_period_days)
            return Response(performance)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def workload_balancing(self, request):
        """Get workload balancing recommendations."""
        service = TerritoryAnalysisService(user=request.user, group=request.user.current_group)
        
        try:
            recommendations = service.get_workload_balancing_recommendations()
            return Response(recommendations)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class LeadActivityFilter(filters.FilterSet):
    """Filter for LeadActivity."""
    
    lead = filters.CharFilter(field_name='lead__id')
    activity_type = filters.CharFilter(field_name='activity_type')
    performed_by = filters.CharFilter(field_name='performed_by__id')
    is_milestone = filters.BooleanFilter(field_name='is_milestone')
    is_automated = filters.BooleanFilter(field_name='is_automated')
    is_overdue = filters.BooleanFilter(method='filter_is_overdue')
    activity_date_after = filters.DateTimeFilter(field_name='activity_date', lookup_expr='gte')
    activity_date_before = filters.DateTimeFilter(field_name='activity_date', lookup_expr='lte')
    next_action_date_after = filters.DateTimeFilter(field_name='next_action_date', lookup_expr='gte')
    next_action_date_before = filters.DateTimeFilter(field_name='next_action_date', lookup_expr='lte')
    
    class Meta:
        model = LeadActivity
        fields = [
            'lead', 'activity_type', 'performed_by', 'is_milestone',
            'is_automated'
        ]
    
    def filter_is_overdue(self, queryset, name, value):
        from django.utils import timezone
        if value:
            return queryset.filter(
                next_action_date__isnull=False,
                next_action_date__lt=timezone.now()
            )
        return queryset.filter(
            Q(next_action_date__isnull=True) |
            Q(next_action_date__gte=timezone.now())
        )


class LeadActivityViewSet(PlatformViewSet):
    """
    ViewSet for managing lead activities.
    
    Provides CRUD operations for activity tracking and
    workflow management.
    """
    
    serializer_class = LeadActivitySerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filterset_class = LeadActivityFilter
    search_fields = ['title', 'description', 'outcome', 'next_action']
    ordering_fields = ['activity_date', 'created_at', 'next_action_date']
    ordering = ['-activity_date', '-created_at']
    
    def get_queryset(self):
        return LeadActivity.objects.filter(
            group=self.request.user.current_group
        ).select_related('lead', 'performed_by')
    
    def perform_create(self, serializer):
        # Use LeadWorkflowService to create activity
        service = LeadWorkflowService(user=self.request.user, group=self.request.user.current_group)
        activity_data = serializer.validated_data
        activity = service.create_activity(activity_data)
        serializer.instance = activity