"""
Comprehensive tests for market intelligence serializers.

Tests all serializer functionality including validation, representation,
and business logic to ensure 90%+ code coverage.
"""

import uuid
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from accounts.models import Group
from ..models import QueryTemplate, NewsArticle, TargetCompany
from ..serializers import (
    QueryTemplateSerializer,
    NewsArticleListSerializer, NewsArticleDetailSerializer,
    TargetCompanyListSerializer, TargetCompanyDetailSerializer, TargetCompanyCreateSerializer,
    ArticleAnalysisSerializer, TargetScoringSerializer, NewsScrapeSerializer,
    TargetPromotionSerializer, DashboardMetricsSerializer, ScoringInsightsSerializer,
    AnalysisInsightsSerializer, NewsArticleFilterSerializer, TargetCompanyFilterSerializer
)
from .factories import (
    QueryTemplateFactory, NewsArticleFactory, TargetCompanyFactory, TestDataMixin
)

User = get_user_model()


class QueryTemplateSerializerTest(TestCase, TestDataMixin):
    """Test QueryTemplateSerializer functionality."""
    
    def setUp(self):
        super().setUp()
    
    def test_serialization_basic(self):
        """Test basic QueryTemplate serialization."""
        template = QueryTemplateFactory.create(group=self.group1)
        serializer = QueryTemplateSerializer(template)
        
        data = serializer.data
        
        self.assertEqual(data['id'], str(template.id))
        self.assertEqual(data['name'], template.name)
        self.assertEqual(data['description'], template.description)
        self.assertEqual(data['template_type'], template.template_type)
        self.assertEqual(data['is_active'], template.is_active)
        self.assertEqual(data['keywords'], template.keywords)
        self.assertEqual(data['regions'], template.regions)
    
    def test_serialization_with_last_executed(self):
        """Test serialization with last_executed field."""
        template = QueryTemplateFactory.create(group=self.group1)
        template.last_executed = timezone.now()
        template.save()
        
        serializer = QueryTemplateSerializer(template)
        data = serializer.data
        
        self.assertIsNotNone(data['last_executed'])
    
    def test_deserialization_valid_data(self):
        """Test QueryTemplate deserialization with valid data."""
        data = {
            'name': 'Test Template',
            'description': 'Test description',
            'template_type': QueryTemplate.TemplateType.COMPANY_DISCOVERY,
            'query_pattern': 'student accommodation {city}',
            'keywords': ['pbsa', 'student housing'],
            'excluded_keywords': ['dormitory'],
            'regions': ['UK', 'Ireland'],
            'schedule_frequency': 'daily'
        }
        
        serializer = QueryTemplateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        validated_data = serializer.validated_data
        self.assertEqual(validated_data['name'], 'Test Template')
        self.assertEqual(validated_data['keywords'], ['pbsa', 'student housing'])
    
    def test_deserialization_missing_required_fields(self):
        """Test deserialization with missing required fields."""
        data = {
            'description': 'Missing required fields'
        }
        
        serializer = QueryTemplateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)
        self.assertIn('template_type', serializer.errors)
        self.assertIn('query_pattern', serializer.errors)
    
    def test_deserialization_invalid_template_type(self):
        """Test deserialization with invalid template type."""
        data = {
            'name': 'Test Template',
            'template_type': 'invalid_type',
            'query_pattern': 'test pattern'
        }
        
        serializer = QueryTemplateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('template_type', serializer.errors)
    
    def test_deserialization_invalid_schedule_frequency(self):
        """Test deserialization with invalid schedule frequency."""
        data = {
            'name': 'Test Template',
            'template_type': QueryTemplate.TemplateType.COMPANY_DISCOVERY,
            'query_pattern': 'test pattern',
            'schedule_frequency': 'invalid_frequency'
        }
        
        serializer = QueryTemplateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('schedule_frequency', serializer.errors)


class NewsArticleSerializerTest(TestCase, TestDataMixin):
    """Test NewsArticle serializer functionality."""
    
    def setUp(self):
        super().setUp()
    
    def test_list_serializer_basic(self):
        """Test NewsArticleListSerializer basic functionality."""
        article = NewsArticleFactory.create(group=self.group1)
        serializer = NewsArticleListSerializer(article)
        
        data = serializer.data
        
        self.assertEqual(data['id'], str(article.id))
        self.assertEqual(data['title'], article.title)
        self.assertEqual(data['source'], article.source)
        self.assertEqual(data['relevance_score'], article.relevance_score)
        self.assertEqual(data['sentiment_score'], article.sentiment_score)
        self.assertIn('published_date', data)
        self.assertIn('word_count', data)
        self.assertIn('is_relevant', data)
    
    def test_detail_serializer_comprehensive(self):
        """Test NewsArticleDetailSerializer with full content."""
        article = NewsArticleFactory.create(group=self.group1)
        serializer = NewsArticleDetailSerializer(article)
        
        data = serializer.data
        
        # Check all fields are present
        expected_fields = [
            'id', 'title', 'content', 'summary', 'url', 'published_date',
            'source', 'author', 'language', 'status', 'relevance_score',
            'sentiment_score', 'entities_extracted', 'topics', 'word_count',
            'is_relevant', 'scraped_date', 'query_template'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
        
        self.assertEqual(data['content'], article.content)
        self.assertEqual(data['entities_extracted'], article.entities_extracted)
        self.assertEqual(data['topics'], article.topics)
    
    def test_query_template_nested_serialization(self):
        """Test nested QueryTemplate serialization in article detail."""
        template = QueryTemplateFactory.create(group=self.group1)
        article = NewsArticleFactory.create(group=self.group1, query_template=template)
        
        serializer = NewsArticleDetailSerializer(article)
        data = serializer.data
        
        self.assertIsNotNone(data['query_template'])
        self.assertEqual(data['query_template']['id'], str(template.id))
        self.assertEqual(data['query_template']['name'], template.name)
    
    def test_article_filter_serializer_validation(self):
        """Test NewsArticleFilterSerializer validation."""
        valid_data = {
            'status': NewsArticle.ArticleStatus.RELEVANT,
            'source': 'Property Week',
            'language': 'en',
            'relevance_min': 0.7,
            'published_after': timezone.now() - timedelta(days=30),
            'published_before': timezone.now(),
            'search': 'PBSA development'
        }
        
        serializer = NewsArticleFilterSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
        
        validated_data = serializer.validated_data
        self.assertEqual(validated_data['status'], NewsArticle.ArticleStatus.RELEVANT)
        self.assertEqual(validated_data['relevance_min'], 0.7)
    
    def test_article_filter_serializer_invalid_relevance(self):
        """Test filter serializer with invalid relevance score."""
        invalid_data = {
            'relevance_min': 1.5  # Should be <= 1.0
        }
        
        serializer = NewsArticleFilterSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('relevance_min', serializer.errors)
    
    def test_article_filter_serializer_invalid_date_range(self):
        """Test filter serializer with invalid date range."""
        invalid_data = {
            'published_after': timezone.now(),
            'published_before': timezone.now() - timedelta(days=1)  # Before should be after after
        }
        
        serializer = NewsArticleFilterSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)


class TargetCompanySerializerTest(TestCase, TestDataMixin):
    """Test TargetCompany serializer functionality."""
    
    def setUp(self):
        super().setUp()
    
    def test_list_serializer_basic(self):
        """Test TargetCompanyListSerializer basic functionality."""
        target = TargetCompanyFactory.create(group=self.group1, identified_by=self.analyst_user)
        serializer = TargetCompanyListSerializer(target)
        
        data = serializer.data
        
        self.assertEqual(data['id'], str(target.id))
        self.assertEqual(data['company_name'], target.company_name)
        self.assertEqual(data['status'], target.status)
        self.assertEqual(data['lead_score'], target.lead_score)
        self.assertEqual(data['business_model'], target.business_model)
        self.assertIn('is_qualified', data)
        self.assertIn('days_since_identification', data)
    
    def test_detail_serializer_comprehensive(self):
        """Test TargetCompanyDetailSerializer with full content."""
        target = TargetCompanyFactory.create(group=self.group1, identified_by=self.analyst_user)
        # Add some source articles
        articles = NewsArticleFactory.create_batch(2, group=self.group1)
        target.source_articles.set(articles)
        
        serializer = TargetCompanyDetailSerializer(target)
        data = serializer.data
        
        # Check comprehensive fields
        expected_fields = [
            'id', 'company_name', 'trading_name', 'domain', 'linkedin_url',
            'description', 'headquarters_city', 'headquarters_country',
            'company_size', 'employee_count', 'business_model', 'focus_sectors',
            'geographic_focus', 'status', 'lead_score', 'qualification_notes',
            'enrichment_data', 'is_qualified', 'days_since_identification',
            'source_articles', 'identified_by', 'assigned_analyst'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
        
        # Check nested serializations
        self.assertEqual(len(data['source_articles']), 2)
        self.assertIsNotNone(data['identified_by'])
        self.assertEqual(data['identified_by']['username'], self.analyst_user.username)
    
    def test_create_serializer_validation(self):
        """Test TargetCompanyCreateSerializer validation."""
        valid_data = {
            'company_name': 'New Target Company Ltd',
            'domain': 'https://newtarget.com',
            'description': 'A promising PBSA development company',
            'business_model': 'developer',
            'focus_sectors': ['pbsa'],
            'headquarters_country': 'GB'
        }
        
        serializer = TargetCompanyCreateSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
        
        validated_data = serializer.validated_data
        self.assertEqual(validated_data['company_name'], 'New Target Company Ltd')
        self.assertEqual(validated_data['focus_sectors'], ['pbsa'])
    
    def test_create_serializer_missing_required_fields(self):
        """Test create serializer with missing required fields."""
        invalid_data = {
            'description': 'Missing company name'
        }
        
        serializer = TargetCompanyCreateSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('company_name', serializer.errors)
    
    def test_create_serializer_invalid_url(self):
        """Test create serializer with invalid URL format."""
        invalid_data = {
            'company_name': 'Test Company',
            'domain': 'not-a-valid-url'
        }
        
        serializer = TargetCompanyCreateSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('domain', serializer.errors)
    
    def test_target_filter_serializer_validation(self):
        """Test TargetCompanyFilterSerializer validation."""
        valid_data = {
            'status': TargetCompany.TargetStatus.QUALIFIED,
            'business_model': 'developer',
            'company_size': TargetCompany.CompanySize.LARGE,
            'headquarters_country': 'GB',
            'score_min': 70.0,
            'score_max': 100.0,
            'qualified_only': True,
            'search': 'PBSA'
        }
        
        serializer = TargetCompanyFilterSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
        
        validated_data = serializer.validated_data
        self.assertEqual(validated_data['status'], TargetCompany.TargetStatus.QUALIFIED)
        self.assertTrue(validated_data['qualified_only'])
    
    def test_target_filter_serializer_invalid_score_range(self):
        """Test filter serializer with invalid score range."""
        invalid_data = {
            'score_min': 80.0,
            'score_max': 70.0  # Max should be >= min
        }
        
        serializer = TargetCompanyFilterSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)


class ActionSerializerTest(TestCase, TestDataMixin):
    """Test action-specific serializers."""
    
    def setUp(self):
        super().setUp()
    
    def test_article_analysis_serializer(self):
        """Test ArticleAnalysisSerializer validation."""
        valid_data = {
            'article_ids': [str(uuid.uuid4()) for _ in range(3)],
            'analysis_type': 'full',
            'force_reanalysis': True
        }
        
        serializer = ArticleAnalysisSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
        
        validated_data = serializer.validated_data
        self.assertEqual(len(validated_data['article_ids']), 3)
        self.assertTrue(validated_data['force_reanalysis'])
    
    def test_article_analysis_serializer_invalid_ids(self):
        """Test analysis serializer with invalid UUIDs."""
        invalid_data = {
            'article_ids': ['not-a-uuid', 'also-not-uuid']
        }
        
        serializer = ArticleAnalysisSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('article_ids', serializer.errors)
    
    def test_target_scoring_serializer(self):
        """Test TargetScoringSerializer validation."""
        valid_data = {
            'target_ids': [str(uuid.uuid4()) for _ in range(2)],
            'scoring_components': ['business_alignment', 'market_presence'],
            'update_scores': True
        }
        
        serializer = TargetScoringSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
        
        validated_data = serializer.validated_data
        self.assertEqual(len(validated_data['target_ids']), 2)
        self.assertIn('business_alignment', validated_data['scoring_components'])
    
    def test_news_scrape_serializer(self):
        """Test NewsScrapeSerializer validation."""
        valid_data = {
            'search_parameters': {
                'city': 'London',
                'region': 'UK'
            },
            'max_articles': 50,
            'date_range_days': 30
        }
        
        serializer = NewsScrapeSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
        
        validated_data = serializer.validated_data
        self.assertEqual(validated_data['max_articles'], 50)
        self.assertEqual(validated_data['search_parameters']['city'], 'London')
    
    def test_news_scrape_serializer_invalid_max_articles(self):
        """Test scrape serializer with invalid max_articles."""
        invalid_data = {
            'max_articles': 1001  # Should be <= 1000
        }
        
        serializer = NewsScrapeSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('max_articles', serializer.errors)
    
    def test_target_promotion_serializer(self):
        """Test TargetPromotionSerializer validation."""
        valid_data = {
            'promotion_reason': 'Excellent fit for our PBSA investment strategy',
            'assigned_analyst': str(self.analyst_user.id),
            'priority_level': 'high'
        }
        
        serializer = TargetPromotionSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
        
        validated_data = serializer.validated_data
        self.assertIn('Excellent fit', validated_data['promotion_reason'])
        self.assertEqual(validated_data['priority_level'], 'high')


class MetricsSerializerTest(TestCase, TestDataMixin):
    """Test metrics and insights serializers."""
    
    def setUp(self):
        super().setUp()
    
    def test_dashboard_metrics_serializer(self):
        """Test DashboardMetricsSerializer representation."""
        metrics_data = {
            'articles': {
                'total': 150,
                'relevant': 45,
                'pending': 12,
                'recent': 8,
                'relevance_rate': 30.0
            },
            'targets': {
                'total': 25,
                'qualified': 8,
                'recent': 3,
                'qualification_rate': 32.0
            },
            'templates': {
                'total': 5,
                'active': 4
            },
            'trends': {
                'articles_last_7_days': [2, 3, 1, 4, 2, 3, 5],
                'targets_last_7_days': [0, 1, 0, 2, 1, 0, 1]
            }
        }
        
        serializer = DashboardMetricsSerializer(metrics_data)
        data = serializer.data
        
        self.assertEqual(data['articles']['total'], 150)
        self.assertEqual(data['targets']['qualified'], 8)
        self.assertEqual(len(data['trends']['articles_last_7_days']), 7)
    
    def test_scoring_insights_serializer(self):
        """Test ScoringInsightsSerializer representation."""
        insights_data = {
            'total_targets': 50,
            'average_score': 65.5,
            'score_distribution': {
                '80-100': 8,
                '65-79': 15,
                '50-64': 18,
                '35-49': 7,
                '0-34': 2
            },
            'business_model_performance': {
                'developer': 75.2,
                'investor': 68.1,
                'operator': 62.8
            },
            'geographic_performance': {
                'UK': 72.3,
                'Ireland': 68.9,
                'Netherlands': 64.2
            },
            'top_targets': [
                {
                    'id': str(uuid.uuid4()),
                    'company_name': 'Top Performer Ltd',
                    'score': 92.5
                }
            ]
        }
        
        serializer = ScoringInsightsSerializer(insights_data)
        data = serializer.data
        
        self.assertEqual(data['total_targets'], 50)
        self.assertEqual(data['average_score'], 65.5)
        self.assertEqual(data['score_distribution']['80-100'], 8)
        self.assertEqual(data['business_model_performance']['developer'], 75.2)
        self.assertEqual(len(data['top_targets']), 1)
    
    def test_analysis_insights_serializer(self):
        """Test AnalysisInsightsSerializer representation."""
        insights_data = {
            'total_articles': 200,
            'relevant_articles': 60,
            'relevance_rate': 30.0,
            'top_topics': [
                ('funding_investment', 25),
                ('property_development', 20),
                ('student_housing', 15)
            ],
            'sentiment_trend': {
                'positive': 45,
                'neutral': 35,
                'negative': 20
            },
            'top_sources': [
                ('Property Week', 30),
                ('Real Estate Weekly', 25),
                ('PropTech News', 20)
            ],
            'language_distribution': {
                'en': 180,
                'es': 15,
                'fr': 5
            }
        }
        
        serializer = AnalysisInsightsSerializer(insights_data)
        data = serializer.data
        
        self.assertEqual(data['total_articles'], 200)
        self.assertEqual(data['relevance_rate'], 30.0)
        self.assertEqual(len(data['top_topics']), 3)
        self.assertEqual(data['top_topics'][0][0], 'funding_investment')
        self.assertEqual(data['sentiment_trend']['positive'], 45)


class SerializerIntegrationTest(TestCase, TestDataMixin):
    """Test integration between different serializers."""
    
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
    
    def test_nested_serialization_consistency(self):
        """Test consistency between nested and standalone serializations."""
        # Create related objects
        template = QueryTemplateFactory.create(group=self.group1)
        article = NewsArticleFactory.create(group=self.group1, query_template=template)
        target = TargetCompanyFactory.create(group=self.group1, identified_by=self.analyst_user)
        target.source_articles.add(article)
        
        # Test nested serialization in target detail
        target_serializer = TargetCompanyDetailSerializer(target)
        target_data = target_serializer.data
        
        # Test standalone article serialization
        article_serializer = NewsArticleDetailSerializer(article)
        article_data = article_serializer.data
        
        # Nested article should match standalone
        nested_article = target_data['source_articles'][0]
        self.assertEqual(nested_article['id'], article_data['id'])
        self.assertEqual(nested_article['title'], article_data['title'])
    
    def test_filter_serializer_integration(self):
        """Test filter serializers work with actual querysets."""
        # Create test data
        NewsArticleFactory.create_relevant_article(group=self.group1)
        NewsArticleFactory.create_irrelevant_article(group=self.group1)
        TargetCompanyFactory.create_qualified_target(group=self.group1)
        TargetCompanyFactory.create_startup_target(group=self.group1)
        
        # Test article filtering
        article_filter_data = {
            'status': NewsArticle.ArticleStatus.RELEVANT,
            'relevance_min': 0.7
        }
        article_filter_serializer = NewsArticleFilterSerializer(data=article_filter_data)
        self.assertTrue(article_filter_serializer.is_valid())
        
        # Test target filtering
        target_filter_data = {
            'qualified_only': True,
            'business_model': 'developer'
        }
        target_filter_serializer = TargetCompanyFilterSerializer(data=target_filter_data)
        self.assertTrue(target_filter_serializer.is_valid())
    
    def test_serializer_validation_with_request_context(self):
        """Test serializers with request context."""
        request = self.factory.get('/')
        request.user = self.analyst_user
        
        # Test serializer with context
        target = TargetCompanyFactory.create(group=self.group1)
        serializer = TargetCompanyDetailSerializer(
            target, 
            context={'request': request}
        )
        
        data = serializer.data
        self.assertIsNotNone(data)
        # Context should be available for custom field processing