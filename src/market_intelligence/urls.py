"""
Market Intelligence URL Configuration.

Provides RESTful API endpoints for market intelligence functionality
including query templates, news articles, target companies, and dashboard analytics.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import (
    QueryTemplateViewSet,
    NewsArticleViewSet, 
    TargetCompanyViewSet,
    MarketIntelligenceDashboardViewSet
)

# Create router and register ViewSets
router = DefaultRouter()
router.register(r'query-templates', QueryTemplateViewSet)
router.register(r'news-articles', NewsArticleViewSet)
router.register(r'target-companies', TargetCompanyViewSet)
router.register(r'dashboard', MarketIntelligenceDashboardViewSet, basename='dashboard')

app_name = 'market_intelligence'

urlpatterns = [
    path('', include(router.urls)),
]