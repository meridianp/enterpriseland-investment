"""
Geographic Intelligence API views for PBSA investment analysis.

Provides comprehensive REST API endpoints for geographic data, analysis,
and visualization supporting the investment decision platform.
"""

import logging
from typing import Dict, List, Any

from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.measure import Distance
from django.db.models import Q, Count, Avg, Max, Min, Sum
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from platform_core.core.views import PlatformViewSet, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from platform_core.accounts.permissions import RoleBasedPermission
from .models import (
    PointOfInterest, University, Neighborhood, NeighborhoodMetrics,
    PBSAMarketAnalysis, POIType, UniversityType
)
from .serializers import (
    PointOfInterestSerializer, PointOfInterestCreateSerializer,
    UniversitySerializer, NeighborhoodSerializer, NeighborhoodListSerializer,
    NeighborhoodMetricsSerializer, PBSAMarketAnalysisSerializer,
    LocationAnalysisInputSerializer, LocationAnalysisResultSerializer,
    OptimalLocationInputSerializer, OptimalLocationResultSerializer,
    NeighborhoodScoringInputSerializer, POIClusterSerializer,
    HeatMapDataSerializer
)
from .services import (
    GeographicIntelligenceService, NeighborhoodScoringService
)

logger = logging.getLogger(__name__)


class PointOfInterestViewSet(PlatformViewSet):
    """
    ViewSet for managing Points of Interest.
    
    Provides CRUD operations for POIs with spatial filtering and clustering.
    """
    
    queryset = PointOfInterest.objects.all()
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'address', 'description']
    ordering_fields = ['name', 'poi_type', 'verified', 'created_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        """Use different serializers for different actions."""
        if self.action == 'create':
            return PointOfInterestCreateSerializer
        return PointOfInterestSerializer
    
    @action(detail=False, methods=['get'])
    def types(self, request):
        """Get available POI types."""
        types = [{'value': choice[0], 'label': choice[1]} for choice in POIType.choices]
        return Response(types)
    
    @action(detail=False, methods=['post'])
    def within_radius(self, request):
        """Get POIs within radius of a point."""
        try:
            lat = float(request.data.get('latitude'))
            lng = float(request.data.get('longitude'))
            radius_km = float(request.data.get('radius_km', 5.0))
            poi_types = request.data.get('poi_types', [])
            
            point = Point(lng, lat, srid=4326)
            queryset = self.get_queryset().filter(
                location__distance_lte=(point, Distance(km=radius_km))
            )
            
            if poi_types:
                queryset = queryset.filter(poi_type__in=poi_types)
            
            serializer = self.get_serializer(queryset, many=True)
            return Response({
                'center': {'lat': lat, 'lng': lng},
                'radius_km': radius_km,
                'count': queryset.count(),
                'pois': serializer.data
            })
            
        except (ValueError, TypeError) as e:
            return Response(
                {'error': f'Invalid parameters: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    def clusters(self, request):
        """Get POI clusters for map visualization with performance optimization."""
        try:
            # Extract parameters
            bounds = request.data.get('bounds', {})
            zoom_level = int(request.data.get('zoom', 10))
            poi_types = request.data.get('poi_types', [])
            min_cluster_size = int(request.data.get('min_cluster_size', 3))
            
            # Validate bounds
            if not all(k in bounds for k in ['north', 'south', 'east', 'west']):
                return Response(
                    {'error': 'Invalid bounds. Must include north, south, east, west'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create bounding box polygon
            bbox = Polygon.from_bbox((
                bounds['west'], bounds['south'],
                bounds['east'], bounds['north']
            ))
            
            # Filter POIs within bounds
            queryset = self.get_queryset().filter(location__within=bbox)
            if poi_types:
                queryset = queryset.filter(poi_type__in=poi_types)
            
            # Determine grid size based on zoom level
            # Higher zoom = smaller grid cells = more detailed clusters
            grid_size = max(0.001, 0.5 / (2 ** (zoom_level - 10)))
            
            # Perform server-side clustering using grid aggregation
            clusters = []
            cluster_data = {}
            
            # For performance, only fetch necessary fields
            pois = queryset.values('id', 'name', 'poi_type', 'location')
            
            for poi in pois:
                # Calculate grid cell
                grid_x = int(poi['location'].x / grid_size)
                grid_y = int(poi['location'].y / grid_size)
                cluster_key = f"{grid_x},{grid_y}"
                
                if cluster_key not in cluster_data:
                    cluster_data[cluster_key] = {
                        'cluster_id': cluster_key,
                        'center': [0, 0],
                        'count': 0,
                        'poi_types': set(),
                        'pois': []
                    }
                
                cluster = cluster_data[cluster_key]
                cluster['count'] += 1
                cluster['poi_types'].add(poi['poi_type'])
                cluster['center'][0] += poi['location'].x
                cluster['center'][1] += poi['location'].y
                
                # Only include individual POIs at high zoom levels
                if zoom_level >= 15 and cluster['count'] <= 10:
                    cluster['pois'].append({
                        'id': str(poi['id']),
                        'name': poi['name'],
                        'poi_type': poi['poi_type'],
                        'location': [poi['location'].x, poi['location'].y]
                    })
            
            # Process clusters
            for cluster_key, cluster in cluster_data.items():
                # Calculate cluster center
                cluster['center'][0] /= cluster['count']
                cluster['center'][1] /= cluster['count']
                cluster['poi_types'] = list(cluster['poi_types'])
                
                # Only return clusters above minimum size or individual POIs
                if cluster['count'] >= min_cluster_size or zoom_level >= 15:
                    clusters.append(cluster)
            
            # For very high zoom levels, return individual POIs
            if zoom_level >= 17:
                individual_pois = []
                for poi in queryset[:1000]:  # Limit to prevent overload
                    individual_pois.append({
                        'cluster_id': f"poi_{poi.id}",
                        'center': [poi.location.x, poi.location.y],
                        'count': 1,
                        'poi_types': [poi.poi_type],
                        'pois': [{
                            'id': str(poi.id),
                            'name': poi.name,
                            'poi_type': poi.poi_type,
                            'location': [poi.location.x, poi.location.y]
                        }]
                    })
                clusters = individual_pois
            
            serializer = POIClusterSerializer(clusters, many=True)
            return Response({
                'bounds': bounds,
                'zoom': zoom_level,
                'cluster_count': len(clusters),
                'total_pois': sum(c['count'] for c in clusters),
                'clusters': serializer.data
            })
            
        except Exception as e:
            logger.error(f'POI clustering error: {str(e)}')
            return Response(
                {'error': f'Clustering failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UniversityViewSet(PlatformViewSet):
    """
    ViewSet for managing Universities.
    
    Provides CRUD operations for universities with campus and student data.
    """
    
    queryset = University.objects.select_related('main_campus').prefetch_related('campuses__campus')
    serializer_class = UniversitySerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'programs']
    ordering_fields = ['name', 'total_students', 'ranking_national', 'created_at']
    ordering = ['name']


class NeighborhoodViewSet(PlatformViewSet):
    """
    ViewSet for managing Neighborhoods.
    
    Provides CRUD operations for neighborhoods with scoring and analysis.
    """
    
    queryset = Neighborhood.objects.select_related('metrics', 'primary_university')
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'investment_rationale']
    ordering_fields = ['name', 'metrics__overall_score', 'area_sqkm', 'created_at']
    ordering = ['-metrics__overall_score']
    
    def get_serializer_class(self):
        """Use simplified serializer for list view."""
        if self.action == 'list':
            return NeighborhoodListSerializer
        return NeighborhoodSerializer


class PBSAMarketAnalysisViewSet(PlatformViewSet):
    """
    ViewSet for managing PBSA Market Analysis.
    
    Provides CRUD operations for comprehensive market analysis reports.
    """
    
    queryset = PBSAMarketAnalysis.objects.prefetch_related(
        'neighborhoods__neighborhood__metrics',
        'universities__university__main_campus'
    )
    serializer_class = PBSAMarketAnalysisSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['city', 'market_summary']
    ordering_fields = ['city', 'analysis_date', 'total_student_population', 'supply_demand_ratio']
    ordering = ['-analysis_date']


class GeographicAnalysisViewSet(viewsets.ViewSet):
    """
    ViewSet for geographic analysis operations.
    
    Provides location analysis, optimal location finding, and market intelligence.
    """
    
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    
    @action(detail=False, methods=['post'])
    def analyze_location(self, request):
        """Perform comprehensive location analysis."""
        serializer = LocationAnalysisInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        service = GeographicIntelligenceService(group=request.user.groups.first())
        
        try:
            analysis = service.analyze_location(
                lat=data['latitude'],
                lng=data['longitude'],
                radius_km=data['radius_km']
            )
            
            result_serializer = LocationAnalysisResultSerializer(analysis)
            return Response(result_serializer.data)
            
        except Exception as e:
            logger.error(f'Location analysis error: {str(e)}')
            return Response(
                {'error': f'Analysis failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
