"""
Market Intelligence ViewSets for API endpoints.

Provides RESTful API endpoints for market intelligence functionality
following Django REST Framework best practices with service layer integration.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db.models import Q
from django.utils import timezone

from accounts.permissions import GroupAccessPermission
from .models import QueryTemplate, NewsArticle, TargetCompany
from .serializers import (
    QueryTemplateSerializer,
    NewsArticleListSerializer, NewsArticleDetailSerializer,
    TargetCompanyListSerializer, TargetCompanyDetailSerializer, TargetCompanyCreateSerializer,
    ArticleAnalysisSerializer, TargetScoringSerializer, NewsScrapeSerializer,
    TargetPromotionSerializer, DashboardMetricsSerializer, ScoringInsightsSerializer,
    AnalysisInsightsSerializer, NewsArticleFilterSerializer, TargetCompanyFilterSerializer
)
from .services import MarketIntelligenceService, NewsAnalysisService, TargetScoringService


class BaseMarketIntelligenceViewSet(viewsets.ModelViewSet):
    """Base ViewSet with common market intelligence functionality."""
    
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    
    def get_service_kwargs(self):
        """Get service initialization kwargs."""
        return {
            'user': self.request.user,
            'group': getattr(self.request.user, 'current_group', None)
        }
    
    def get_queryset(self):
        """Filter queryset by user's group access."""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Admin users see all data
        if user.role == user.Role.ADMIN:
            return queryset
        
        # Filter by user's groups
        user_groups = user.groups.all()
        return queryset.filter(group__in=user_groups)
    
    def perform_create(self, serializer):
        """Set group context when creating objects."""
        # Get user's current group (you might need to implement group selection logic)
        current_group = getattr(self.request.user, 'current_group', None)
        if not current_group and self.request.user.groups.exists():
            current_group = self.request.user.groups.first()
        
        serializer.save(group=current_group)


class QueryTemplateViewSet(BaseMarketIntelligenceViewSet):
    """ViewSet for managing query templates."""
    
    queryset = QueryTemplate.objects.all()
    serializer_class = QueryTemplateSerializer
    filterset_fields = ['template_type', 'is_active', 'schedule_frequency']
    ordering_fields = ['created_at', 'last_executed', 'name']
    search_fields = ['name', 'description']
    ordering = ['-created_at']
    
    @action(detail=True, methods=['post'])
    def execute_scraping(self, request, pk=None):
        """Execute news scraping using this template."""
        template = self.get_object()
        serializer = NewsScrapeSerializer(data=request.data)
        
        if serializer.is_valid():
            service = MarketIntelligenceService(**self.get_service_kwargs())
            
            try:
                result = service.execute_news_scraping(
                    template_id=str(template.id),
                    **serializer.validated_data.get('search_parameters', {})
                )
                return Response(result, status=status.HTTP_200_OK)
            except Exception as e:
                return Response(
                    {'error': f'Scraping failed: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle template active status."""
        template = self.get_object()
        template.is_active = not template.is_active
        template.save()
        
        serializer = self.get_serializer(template)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def active_templates(self, request):
        """Get only active templates."""
        queryset = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class NewsArticleViewSet(BaseMarketIntelligenceViewSet):
    """ViewSet for managing news articles."""
    
    queryset = NewsArticle.objects.all()
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    ordering_fields = ['published_date', 'scraped_date', 'relevance_score', 'sentiment_score']
    search_fields = ['title', 'content', 'source']
    ordering = ['-published_date']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'retrieve':
            return NewsArticleDetailSerializer
        return NewsArticleListSerializer
    
    def get_queryset(self):
        """Apply custom filtering."""
        queryset = super().get_queryset()
        
        # Apply custom filters from query params
        filter_serializer = NewsArticleFilterSerializer(data=self.request.query_params)
        if filter_serializer.is_valid():
            filters = filter_serializer.validated_data
            
            if filters.get('status'):
                queryset = queryset.filter(status=filters['status'])
            
            if filters.get('source'):
                queryset = queryset.filter(source__icontains=filters['source'])
            
            if filters.get('language'):
                queryset = queryset.filter(language=filters['language'])
            
            if filters.get('relevance_min'):
                queryset = queryset.filter(relevance_score__gte=filters['relevance_min'])
            
            if filters.get('published_after'):
                queryset = queryset.filter(published_date__gte=filters['published_after'])
            
            if filters.get('published_before'):
                queryset = queryset.filter(published_date__lte=filters['published_before'])
            
            if filters.get('template'):
                queryset = queryset.filter(query_template_id=filters['template'])
            
            if filters.get('search'):
                search_term = filters['search']
                queryset = queryset.filter(
                    Q(title__icontains=search_term) | Q(content__icontains=search_term)
                )
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def analyze(self, request, pk=None):
        """Analyze individual article for relevance and sentiment."""
        article = self.get_object()
        service = MarketIntelligenceService(**self.get_service_kwargs())
        
        try:
            result = service.analyze_article_relevance(str(article.id))
            serializer = NewsArticleDetailSerializer(result)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': f'Analysis failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def batch_analyze(self, request):
        """Analyze multiple articles in batch."""
        serializer = ArticleAnalysisSerializer(data=request.data)
        
        if serializer.is_valid():
            service = NewsAnalysisService(**self.get_service_kwargs())
            
            try:
                result = service.batch_analyze_articles(**serializer.validated_data)
                return Response(result, status=status.HTTP_200_OK)
            except Exception as e:
                return Response(
                    {'error': f'Batch analysis failed: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def relevant_articles(self, request):
        """Get only relevant articles."""
        queryset = self.get_queryset().filter(status=NewsArticle.ArticleStatus.RELEVANT)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending_analysis(self, request):
        """Get articles pending analysis."""
        queryset = self.get_queryset().filter(status=NewsArticle.ArticleStatus.PENDING)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def analysis_insights(self, request):
        """Get insights from article analysis."""
        days_back = int(request.query_params.get('days_back', 30))
        service = NewsAnalysisService(**self.get_service_kwargs())
        
        try:
            insights = service.get_analysis_insights(days_back=days_back)
            serializer = AnalysisInsightsSerializer(insights)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': f'Failed to get insights: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


class TargetCompanyViewSet(BaseMarketIntelligenceViewSet):
    """ViewSet for managing target companies."""
    
    queryset = TargetCompany.objects.all()
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    ordering_fields = ['created_at', 'lead_score', 'company_name']
    search_fields = ['company_name', 'trading_name', 'description']
    ordering = ['-lead_score', '-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return TargetCompanyCreateSerializer
        elif self.action == 'retrieve':
            return TargetCompanyDetailSerializer
        return TargetCompanyListSerializer
    
    def get_queryset(self):
        """Apply custom filtering."""
        queryset = super().get_queryset()
        
        # Apply custom filters from query params
        filter_serializer = TargetCompanyFilterSerializer(data=self.request.query_params)
        if filter_serializer.is_valid():
            filters = filter_serializer.validated_data
            
            if filters.get('status'):
                queryset = queryset.filter(status=filters['status'])
            
            if filters.get('business_model'):
                queryset = queryset.filter(business_model=filters['business_model'])
            
            if filters.get('company_size'):
                queryset = queryset.filter(company_size=filters['company_size'])
            
            if filters.get('headquarters_country'):
                queryset = queryset.filter(headquarters_country=filters['headquarters_country'])
            
            if filters.get('assigned_analyst'):
                queryset = queryset.filter(assigned_analyst_id=filters['assigned_analyst'])
            
            if filters.get('score_min'):
                queryset = queryset.filter(lead_score__gte=filters['score_min'])
            
            if filters.get('score_max'):
                queryset = queryset.filter(lead_score__lte=filters['score_max'])
            
            if filters.get('qualified_only'):
                queryset = queryset.filter(lead_score__gte=70.0)  # Qualification threshold
            
            if filters.get('search'):
                search_term = filters['search']
                queryset = queryset.filter(
                    Q(company_name__icontains=search_term) | 
                    Q(description__icontains=search_term)
                )
        
        return queryset
    
    def perform_create(self, serializer):
        """Set additional fields when creating target."""
        super().perform_create(serializer)
        
        # Set the identifying user
        target = serializer.instance
        target.identified_by = self.request.user
        target.save()
    
    @action(detail=True, methods=['post'])
    def calculate_score(self, request, pk=None):
        """Calculate comprehensive lead score for target."""
        target = self.get_object()
        service = TargetScoringService(**self.get_service_kwargs())
        
        try:
            result = service.calculate_comprehensive_score(str(target.id))
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': f'Scoring failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def batch_score(self, request):
        """Calculate scores for multiple targets in batch."""
        serializer = TargetScoringSerializer(data=request.data)
        
        if serializer.is_valid():
            service = TargetScoringService(**self.get_service_kwargs())
            
            try:
                result = service.batch_score_targets(**serializer.validated_data)
                return Response(result, status=status.HTTP_200_OK)
            except Exception as e:
                return Response(
                    {'error': f'Batch scoring failed: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def assign_analyst(self, request, pk=None):
        """Assign an analyst to this target."""
        target = self.get_object()
        analyst_id = request.data.get('analyst_id')
        
        if not analyst_id:
            return Response(
                {'error': 'analyst_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            analyst = User.objects.get(id=analyst_id)
            
            target.assigned_analyst = analyst
            target.save()
            
            serializer = self.get_serializer(target)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response(
                {'error': 'Analyst not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update target status."""
        target = self.get_object()
        new_status = request.data.get('status')
        
        if not new_status:
            return Response(
                {'error': 'status is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if new_status not in [choice[0] for choice in TargetCompany.TargetStatus.choices]:
            return Response(
                {'error': 'Invalid status value'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        target.status = new_status
        if new_status == TargetCompany.TargetStatus.CONVERTED:
            target.converted_at = timezone.now()
        target.save()
        
        serializer = self.get_serializer(target)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def promote_to_partner(self, request, pk=None):
        """Promote target to development partner."""
        target = self.get_object()
        serializer = TargetPromotionSerializer(data=request.data)
        
        if serializer.is_valid():
            # This would integrate with the assessments app to create a DevelopmentPartner
            # For now, just mark as converted
            target.status = TargetCompany.TargetStatus.CONVERTED
            target.converted_at = timezone.now()
            target.save()
            
            return Response({
                'message': 'Target promoted to development partner',
                'target_id': str(target.id),
                'status': target.status
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def qualified_targets(self, request):
        """Get only qualified targets (score >= 70)."""
        queryset = self.get_queryset().filter(lead_score__gte=70.0)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_assignments(self, request):
        """Get targets assigned to current user."""
        queryset = self.get_queryset().filter(assigned_analyst=request.user)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def scoring_insights(self, request):
        """Get insights about target scoring."""
        service = TargetScoringService(**self.get_service_kwargs())
        
        try:
            insights = service.get_scoring_insights()
            serializer = ScoringInsightsSerializer(insights)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': f'Failed to get insights: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


class MarketIntelligenceDashboardViewSet(viewsets.ViewSet):
    """ViewSet for market intelligence dashboard functionality."""
    
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    
    def get_service_kwargs(self):
        """Get service initialization kwargs."""
        return {
            'user': self.request.user,
            'group': getattr(self.request.user, 'current_group', None)
        }
    
    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """Get dashboard metrics overview."""
        service = MarketIntelligenceService(**self.get_service_kwargs())
        
        try:
            metrics = service.get_dashboard_metrics()
            serializer = DashboardMetricsSerializer(metrics)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': f'Failed to get metrics: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def identify_targets(self, request):
        """Identify target companies from articles."""
        article_ids = request.data.get('article_ids', [])
        
        service = MarketIntelligenceService(**self.get_service_kwargs())
        
        try:
            targets = service.identify_target_companies(article_ids)
            
            # Return summary of identified targets
            result = {
                'identified_count': len(targets),
                'targets': [
                    {
                        'id': str(target.id),
                        'company_name': target.company_name,
                        'lead_score': target.lead_score,
                        'status': target.status
                    }
                    for target in targets
                ]
            }
            
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': f'Target identification failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )