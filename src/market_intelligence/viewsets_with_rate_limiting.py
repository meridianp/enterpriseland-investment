"""
Example of Market Intelligence ViewSets with Rate Limiting applied.

This file demonstrates how to apply different rate limiting strategies
to various market intelligence endpoints.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from platform_core.core.mixins import (
    ScopedThrottleMixin,
    AIAgentThrottleMixin,
    BurstThrottleMixin
)
from .viewsets import BaseMarketIntelligenceViewSet
from .models import QueryTemplate, NewsArticle, TargetCompany


class RateLimitedQueryTemplateViewSet(ScopedThrottleMixin, BaseMarketIntelligenceViewSet):
    """
    Query template management with moderate rate limiting.
    
    Uses scoped rate limiting to allow reasonable usage for template management.
    """
    queryset = QueryTemplate.objects.all()
    serializer_class = QueryTemplateSerializer
    throttle_scope = 'api'  # Standard API rate limit
    
    @action(detail=False, methods=['post'])
    def execute_all(self, request):
        """Execute all active query templates - higher rate limit."""
        # This endpoint might trigger many operations, so we use burst throttling
        self.throttle_classes = [BurstThrottleMixin]
        return super().execute_all(request)


class RateLimitedNewsArticleViewSet(BaseMarketIntelligenceViewSet):
    """
    News article management with intelligent rate limiting.
    
    Different endpoints have different rate limits based on their resource usage.
    """
    queryset = NewsArticle.objects.all()
    
    def get_throttle_classes(self):
        """Dynamic throttle classes based on action."""
        if self.action in ['list', 'retrieve']:
            # Reading is less resource intensive
            return [ScopedThrottleMixin]
        elif self.action == 'analyze':
            # AI analysis needs stricter limits
            return [AIAgentThrottleMixin]
        else:
            # Default rate limiting
            return super().get_throttle_classes()
    
    def get_throttle_scope(self):
        """Different scopes for different actions."""
        if self.action == 'list':
            return 'search'  # Higher limit for searching
        elif self.action == 'analyze':
            return 'ai'  # AI-specific limits
        else:
            return 'api'  # Default API limits
    
    @action(detail=True, methods=['post'])
    def analyze(self, request, pk=None):
        """
        Analyze article with AI - uses AI agent throttling.
        
        This endpoint consumes AI tokens and is rate limited accordingly.
        """
        article = self.get_object()
        
        # Simulate AI analysis
        analysis_result = {
            'article_id': str(article.id),
            'companies_identified': ['Company A', 'Company B'],
            'sentiment': 'positive',
            'key_topics': ['market expansion', 'funding round'],
            'tokens_used': 850  # Track token usage for AI throttling
        }
        
        return Response(analysis_result)


class RateLimitedTargetCompanyViewSet(ScopedThrottleMixin, BaseMarketIntelligenceViewSet):
    """
    Target company management with scope-based rate limiting.
    
    Different operations have different computational costs and rate limits.
    """
    queryset = TargetCompany.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TargetCompanyCreateSerializer
        elif self.action in ['list']:
            return TargetCompanyListSerializer
        else:
            return TargetCompanyDetailSerializer
    
    def get_throttle_scope(self):
        """Set throttle scope based on action."""
        scope_map = {
            'list': 'search',      # Higher limit for searching
            'retrieve': 'api',     # Standard for single items
            'create': 'api',       # Standard for creation
            'update': 'api',       # Standard for updates
            'score': 'analytics',  # Lower limit for scoring
            'insights': 'ai',      # AI limits for insights
            'export': 'export'     # Export-specific limits
        }
        return scope_map.get(self.action, 'api')
    
    @action(detail=True, methods=['post'])
    def score(self, request, pk=None):
        """
        Score a target company - uses analytics rate limiting.
        
        This is computationally expensive, so has stricter limits.
        """
        # Scoring logic here
        return Response({'status': 'scored'})
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """
        Export target companies - uses export rate limiting.
        
        Exports can be large and resource-intensive.
        """
        # Export logic here
        return Response({'status': 'export_queued'})
    
    @action(detail=True, methods=['post'], throttle_classes=[AIAgentThrottleMixin])
    def generate_insights(self, request, pk=None):
        """
        Generate AI insights for a target company.
        
        This explicitly uses AI agent throttling regardless of viewset default.
        """
        target = self.get_object()
        
        # Simulate AI insight generation
        insights = {
            'target_id': str(target.id),
            'market_position': 'Strong growth trajectory...',
            'competitive_analysis': 'Leading position in...',
            'investment_thesis': 'Compelling opportunity due to...',
            'risk_factors': ['Market volatility', 'Regulatory changes'],
            'tokens_used': 1250  # Higher token usage for comprehensive insights
        }
        
        return Response(insights)


# Example usage in URLconf:
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets_with_rate_limiting import (
    RateLimitedQueryTemplateViewSet,
    RateLimitedNewsArticleViewSet,
    RateLimitedTargetCompanyViewSet
)

router = DefaultRouter()
router.register(r'query-templates', RateLimitedQueryTemplateViewSet)
router.register(r'news-articles', RateLimitedNewsArticleViewSet)
router.register(r'targets', RateLimitedTargetCompanyViewSet)

urlpatterns = [
    path('api/market-intelligence/', include(router.urls)),
]
"""