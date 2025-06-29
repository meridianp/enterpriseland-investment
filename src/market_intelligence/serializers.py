"""
Market Intelligence serializers for API responses.

Follows Django REST Framework best practices with proper validation,
nested relationships, and optimized queries.
"""

from rest_framework import serializers
from platform_core.core.serializers import PlatformSerializer
from django.contrib.auth import get_user_model

from accounts.models import Group
from .models import QueryTemplate, NewsArticle, TargetCompany

User = get_user_model()


class QueryTemplateSerializer(serializers.ModelSerializer):
    """Serializer for query templates with validation."""
    
    group_name = serializers.CharField(source='group.name', read_only=True)
    execution_status = serializers.SerializerMethodField()
    
    class Meta:
        model = QueryTemplate
        fields = [
            'id', 'group', 'group_name', 'name', 'description', 
            'template_type', 'query_pattern', 'keywords', 'excluded_keywords',
            'regions', 'languages', 'is_active', 'schedule_frequency',
            'last_executed', 'created_at', 'updated_at', 'execution_status'
        ]
        read_only_fields = ['id', 'group', 'created_at', 'updated_at']
    
    def get_execution_status(self, obj):
        """Get execution status information."""
        if not obj.last_executed:
            return 'never_executed'
        
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        if obj.schedule_frequency == 'daily' and obj.last_executed < now - timedelta(days=1):
            return 'overdue'
        elif obj.schedule_frequency == 'weekly' and obj.last_executed < now - timedelta(days=7):
            return 'overdue'
        elif obj.schedule_frequency == 'monthly' and obj.last_executed < now - timedelta(days=30):
            return 'overdue'
        else:
            return 'up_to_date'
    
    def validate_keywords(self, value):
        """Validate keywords list."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Keywords must be a list")
        
        if len(value) > 20:
            raise serializers.ValidationError("Maximum 20 keywords allowed")
        
        return [keyword.strip().lower() for keyword in value if keyword.strip()]
    
    def validate_regions(self, value):
        """Validate regions list."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Regions must be a list")
        
        return [region.strip() for region in value if region.strip()]


class NewsArticleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for article lists."""
    
    source_template = serializers.CharField(source='query_template.name', read_only=True)
    word_count = serializers.ReadOnlyField()
    is_relevant = serializers.ReadOnlyField()
    
    class Meta:
        model = NewsArticle
        fields = [
            'id', 'title', 'url', 'source', 'published_date', 'scraped_date',
            'status', 'relevance_score', 'sentiment_score', 'language',
            'source_template', 'word_count', 'is_relevant'
        ]


class NewsArticleDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for individual articles."""
    
    query_template_name = serializers.CharField(source='query_template.name', read_only=True)
    word_count = serializers.ReadOnlyField()
    is_relevant = serializers.ReadOnlyField()
    related_targets = serializers.SerializerMethodField()
    
    class Meta:
        model = NewsArticle
        fields = [
            'id', 'title', 'content', 'summary', 'url', 'published_date', 
            'scraped_date', 'source', 'author', 'language', 'content_hash',
            'status', 'relevance_score', 'sentiment_score', 'entities_extracted',
            'topics', 'query_template', 'query_template_name', 'search_keywords',
            'word_count', 'is_relevant', 'related_targets', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'content_hash', 'scraped_date', 'query_template', 
            'search_keywords', 'created_at', 'updated_at'
        ]
    
    def get_related_targets(self, obj):
        """Get target companies mentioned in this article."""
        targets = TargetCompany.objects.filter(source_articles=obj)
        return TargetCompanyListSerializer(targets, many=True).data


class TargetCompanyListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for target company lists."""
    
    identified_by_name = serializers.CharField(source='identified_by.email', read_only=True)
    assigned_analyst_name = serializers.CharField(source='assigned_analyst.email', read_only=True)
    is_qualified = serializers.ReadOnlyField()
    days_since_identification = serializers.ReadOnlyField()
    article_count = serializers.SerializerMethodField()
    
    class Meta:
        model = TargetCompany
        fields = [
            'id', 'company_name', 'domain', 'headquarters_city', 
            'headquarters_country', 'business_model', 'status', 'lead_score',
            'identified_by_name', 'assigned_analyst_name', 'is_qualified',
            'days_since_identification', 'article_count', 'created_at'
        ]
    
    def get_article_count(self, obj):
        """Get count of related articles."""
        return obj.source_articles.count()


class TargetCompanyDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for individual target companies."""
    
    identified_by_name = serializers.CharField(source='identified_by.email', read_only=True)
    assigned_analyst_name = serializers.CharField(source='assigned_analyst.email', read_only=True)
    is_qualified = serializers.ReadOnlyField()
    days_since_identification = serializers.ReadOnlyField()
    source_articles_data = NewsArticleListSerializer(source='source_articles', many=True, read_only=True)
    development_partner_name = serializers.CharField(source='development_partner.company_name', read_only=True)
    
    class Meta:
        model = TargetCompany
        fields = [
            'id', 'company_name', 'trading_name', 'domain', 'linkedin_url',
            'description', 'headquarters_city', 'headquarters_country',
            'company_size', 'employee_count', 'business_model', 'focus_sectors',
            'geographic_focus', 'status', 'lead_score', 'qualification_notes',
            'identified_by', 'identified_by_name', 'assigned_analyst', 
            'assigned_analyst_name', 'development_partner', 'development_partner_name',
            'converted_at', 'enrichment_data', 'last_enriched', 'is_qualified',
            'days_since_identification', 'source_articles_data', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'identified_by', 'development_partner', 'converted_at',
            'created_at', 'updated_at'
        ]
    
    def validate_focus_sectors(self, value):
        """Validate focus sectors."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Focus sectors must be a list")
        
        valid_sectors = [
            'pbsa', 'residential', 'commercial', 'office', 'retail', 
            'industrial', 'hospitality', 'healthcare', 'mixed_use'
        ]
        
        for sector in value:
            if sector not in valid_sectors:
                raise serializers.ValidationError(f"Invalid sector: {sector}")
        
        return value
    
    def validate_lead_score(self, value):
        """Validate lead score range."""
        if not 0 <= value <= 100:
            raise serializers.ValidationError("Lead score must be between 0 and 100")
        return value


class TargetCompanyCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new target companies."""
    
    class Meta:
        model = TargetCompany
        fields = [
            'company_name', 'trading_name', 'domain', 'linkedin_url',
            'description', 'headquarters_city', 'headquarters_country',
            'company_size', 'employee_count', 'business_model', 'focus_sectors',
            'geographic_focus', 'qualification_notes'
        ]
    
    def create(self, validated_data):
        """Create target company with user context."""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['identified_by'] = request.user
            
        # Calculate initial lead score
        target = TargetCompany(**validated_data)
        target.lead_score = target.calculate_lead_score()
        target.save()
        
        return target


# Action serializers for specific operations

class ArticleAnalysisSerializer(serializers.Serializer):
    """Serializer for article analysis requests."""
    
    article_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        help_text="Optional list of article IDs to analyze"
    )
    days_back = serializers.IntegerField(
        default=7,
        min_value=1,
        max_value=365,
        help_text="Days back to analyze if no IDs provided"
    )


class TargetScoringSerializer(serializers.Serializer):
    """Serializer for target scoring requests."""
    
    target_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        help_text="Optional list of target IDs to score"
    )


class NewsScrapeSerializer(serializers.Serializer):
    """Serializer for news scraping requests."""
    
    template_id = serializers.UUIDField(help_text="Query template ID to use")
    search_parameters = serializers.DictField(
        required=False,
        help_text="Additional parameters for query generation"
    )


class TargetPromotionSerializer(serializers.Serializer):
    """Serializer for promoting targets to development partners."""
    
    target_id = serializers.UUIDField(help_text="Target company ID to promote")
    additional_data = serializers.DictField(
        required=False,
        help_text="Additional data for the development partner"
    )


# Dashboard serializers

class DashboardMetricsSerializer(serializers.Serializer):
    """Serializer for dashboard metrics response."""
    
    articles = serializers.DictField(help_text="Article metrics")
    targets = serializers.DictField(help_text="Target company metrics")
    templates = serializers.DictField(help_text="Query template metrics")


class ScoringInsightsSerializer(serializers.Serializer):
    """Serializer for scoring insights response."""
    
    total_targets = serializers.IntegerField()
    average_score = serializers.FloatField()
    score_distribution = serializers.DictField()
    business_model_performance = serializers.ListField()
    geographic_performance = serializers.ListField()
    status_performance = serializers.ListField()
    top_targets = serializers.ListField()


class AnalysisInsightsSerializer(serializers.Serializer):
    """Serializer for analysis insights response."""
    
    period_days = serializers.IntegerField()
    total_articles = serializers.IntegerField()
    relevant_articles = serializers.IntegerField()
    avg_relevance_score = serializers.FloatField()
    top_topics = serializers.ListField()
    sentiment_trend = serializers.DictField()
    top_sources = serializers.ListField()


# Filter serializers

class NewsArticleFilterSerializer(serializers.Serializer):
    """Serializer for news article filtering."""
    
    status = serializers.ChoiceField(
        choices=NewsArticle.ArticleStatus.choices,
        required=False
    )
    source = serializers.CharField(required=False)
    language = serializers.CharField(required=False)
    relevance_min = serializers.FloatField(min_value=0, max_value=1, required=False)
    published_after = serializers.DateTimeField(required=False)
    published_before = serializers.DateTimeField(required=False)
    template = serializers.UUIDField(required=False)
    search = serializers.CharField(required=False, help_text="Search in title and content")


class TargetCompanyFilterSerializer(serializers.Serializer):
    """Serializer for target company filtering."""
    
    status = serializers.ChoiceField(
        choices=TargetCompany.TargetStatus.choices,
        required=False
    )
    business_model = serializers.ChoiceField(
        choices=[
            ('developer', 'Property Developer'),
            ('investor', 'Real Estate Investor'),
            ('operator', 'Property Operator'),
            ('platform', 'PropTech Platform'),
            ('service', 'Real Estate Services'),
            ('other', 'Other'),
        ],
        required=False
    )
    company_size = serializers.ChoiceField(
        choices=TargetCompany.CompanySize.choices,
        required=False
    )
    headquarters_country = serializers.CharField(required=False)
    assigned_analyst = serializers.UUIDField(required=False)
    score_min = serializers.FloatField(min_value=0, max_value=100, required=False)
    score_max = serializers.FloatField(min_value=0, max_value=100, required=False)
    qualified_only = serializers.BooleanField(required=False)
    search = serializers.CharField(required=False, help_text="Search in company name and description")