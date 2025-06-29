"""
URL configuration for Geographic Intelligence API endpoints.

Provides REST API routes for geographic data, analysis, and visualization
supporting PBSA investment decisions.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PointOfInterestViewSet, UniversityViewSet, NeighborhoodViewSet,
    PBSAMarketAnalysisViewSet, GeographicAnalysisViewSet
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'pois', PointOfInterestViewSet, basename='pointofinterest')
router.register(r'universities', UniversityViewSet, basename='university')
router.register(r'neighborhoods', NeighborhoodViewSet, basename='neighborhood')
router.register(r'market-analyses', PBSAMarketAnalysisViewSet, basename='pbsamarketanalysis')
router.register(r'analysis', GeographicAnalysisViewSet, basename='geographicanalysis')

app_name = 'geographic_intelligence'

urlpatterns = [
    path('', include(router.urls)),
]