app_name = 'investment_leads'

"""
Lead Management URL Configuration.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for ViewSets
router = DefaultRouter()
router.register(r'scoring-models', views.LeadScoringModelViewSet, basename='lead-scoring-model')
router.register(r'leads', views.LeadViewSet, basename='lead')
router.register(r'activities', views.LeadActivityViewSet, basename='lead-activity')

urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # Additional custom endpoints can be added here
    # path('analytics/', views.LeadAnalyticsView.as_view(), name='lead-analytics'),
    # path('scoring/batch/', views.BatchScoringView.as_view(), name='batch-scoring'),
]