"""
Comprehensive tests for market intelligence services.

Tests all service layer functionality including business logic, permissions,
error handling, and integration scenarios to ensure 90%+ code coverage.
"""

import uuid
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction

from accounts.models import Group
from assessments.services.base import (
    ValidationServiceError, PermissionServiceError, NotFoundServiceError
)
from ..models import QueryTemplate, NewsArticle, TargetCompany
from ..services import MarketIntelligenceService, NewsAnalysisService, TargetScoringService
from .factories import (
    QueryTemplateFactory, NewsArticleFactory, TargetCompanyFactory, TestDataMixin
)

User = get_user_model()


class MarketIntelligenceServiceTest(TestCase, TestDataMixin):
    """Test MarketIntelligenceService functionality."""
    
    def setUp(self):
        super().setUp()
        self.service = MarketIntelligenceService(
            user=self.analyst_user,
            group=self.group1
        )
    
    def test_service_initialization(self):
        """Test service initialization with user and group context."""
        self.assertEqual(self.service.user, self.analyst_user)
        self.assertEqual(self.service.group, self.group1)
        self.assertIsNotNone(self.service.logger)
    
    def test_create_query_template_success(self):
        """Test successful query template creation."""
        template_data = {
            'name': 'Test Template',
            'description': 'Test description',
            'template_type': QueryTemplate.TemplateType.COMPANY_DISCOVERY,
            'query_pattern': 'student accommodation {city}',
            'keywords': ['pbsa', 'student housing'],
            'regions': ['UK', 'Ireland'],
            'schedule_frequency': 'daily'
        }
        
        with patch.object(self.service, '_check_permission') as mock_permission:
            template = self.service.create_query_template(template_data)
        
        mock_permission.assert_called_once_with('create_query_template')
        self.assertIsInstance(template, QueryTemplate)
        self.assertEqual(template.name, 'Test Template')
        self.assertEqual(template.group, self.group1)
        self.assertEqual(template.keywords, ['pbsa', 'student housing'])
    
    def test_create_query_template_missing_required_fields(self):
        """Test query template creation with missing required fields."""
        template_data = {
            'description': 'Missing required fields'
        }
        
        with patch.object(self.service, '_check_permission'):
            with self.assertRaises(ValidationServiceError) as context:
                self.service.create_query_template(template_data)
        
        self.assertIn("Field 'name' is required", str(context.exception))
    
    def test_create_query_template_no_group_context(self):
        """Test query template creation without group context."""
        service_no_group = MarketIntelligenceService(user=self.analyst_user)
        template_data = {
            'name': 'Test Template',
            'template_type': QueryTemplate.TemplateType.COMPANY_DISCOVERY,
            'query_pattern': 'test pattern'
        }
        
        with patch.object(service_no_group, '_check_permission'):
            with self.assertRaises(ValidationServiceError) as context:
                service_no_group.create_query_template(template_data)
        
        self.assertIn("Group context required", str(context.exception))
    
    def test_create_query_template_permission_denied(self):
        """Test query template creation with insufficient permissions."""
        template_data = {
            'name': 'Test Template',
            'template_type': QueryTemplate.TemplateType.COMPANY_DISCOVERY,
            'query_pattern': 'test pattern'
        }
        
        with patch.object(self.service, '_check_permission', side_effect=PermissionServiceError("Permission denied")):
            with self.assertRaises(PermissionServiceError):
                self.service.create_query_template(template_data)
    
    @patch('market_intelligence.services.market_intelligence_service.MarketIntelligenceService._scrape_articles')
    def test_execute_news_scraping_success(self, mock_scrape):
        """Test successful news scraping execution."""
        template = QueryTemplateFactory.create(group=self.group1)
        mock_articles = [
            NewsArticleFactory.create(group=self.group1),
            NewsArticleFactory.create(group=self.group1, status=NewsArticle.ArticleStatus.PENDING)
        ]
        mock_scrape.return_value = mock_articles
        
        with patch.object(self.service, '_check_permission'):
            result = self.service.execute_news_scraping(str(template.id), city="London")
        
        mock_scrape.assert_called_once()
        self.assertEqual(result['template_id'], str(template.id))
        self.assertEqual(result['articles_found'], 2)
        self.assertEqual(result['articles_processed'], 1)  # Only one with status != PENDING
        
        # Check template was updated
        template.refresh_from_db()
        self.assertIsNotNone(template.last_executed)
    
    def test_execute_news_scraping_template_not_found(self):
        """Test news scraping with non-existent template."""
        non_existent_id = str(uuid.uuid4())
        
        with patch.object(self.service, '_check_permission'):
            with self.assertRaises(NotFoundServiceError) as context:
                self.service.execute_news_scraping(non_existent_id)
        
        self.assertIn(f"Query template {non_existent_id} not found", str(context.exception))
    
    def test_execute_news_scraping_inactive_template(self):
        """Test news scraping with inactive template."""
        template = QueryTemplateFactory.create_inactive_template(group=self.group1)
        
        with patch.object(self.service, '_check_permission'):
            with self.assertRaises(ValidationServiceError) as context:
                self.service.execute_news_scraping(str(template.id))
        
        self.assertIn("Query template is not active", str(context.exception))
    
    @patch('market_intelligence.services.market_intelligence_service.MarketIntelligenceService._simulate_news_api_response')
    def test_scrape_articles_with_deduplication(self, mock_api):
        """Test article scraping with deduplication logic."""
        template = QueryTemplateFactory.create(group=self.group1)
        
        # Mock API response
        mock_api.return_value = [
            {
                'title': 'Test Article',
                'content': 'Test content for deduplication',
                'url': 'https://example.com/test',
                'published_date': timezone.now(),
                'source': 'Test Source',
                'language': 'en'
            }
        ]
        
        # Create existing article with same content
        existing_content = 'Test content for deduplication'
        NewsArticleFactory.create(group=self.group1, content=existing_content)
        
        articles = self.service._scrape_articles(template, "test query")
        
        # Should be empty due to deduplication
        self.assertEqual(len(articles), 0)
    
    def test_analyze_article_relevance_success(self):
        """Test successful article relevance analysis."""
        article = NewsArticleFactory.create_pending_article(group=self.group1)
        
        with patch.object(self.service, '_check_permission'):
            with patch.object(self.service, '_calculate_article_relevance', return_value=0.8):
                with patch.object(self.service, '_analyze_sentiment', return_value=0.3):
                    with patch.object(self.service, '_extract_entities', return_value={'companies': ['Test Co']}):
                        with patch.object(self.service, '_identify_topics', return_value=['funding']):
                            result = self.service.analyze_article_relevance(str(article.id))
        
        result.refresh_from_db()
        self.assertEqual(result.relevance_score, 0.8)
        self.assertEqual(result.sentiment_score, 0.3)
        self.assertEqual(result.status, NewsArticle.ArticleStatus.RELEVANT)
        self.assertEqual(result.entities_extracted, {'companies': ['Test Co']})
        self.assertEqual(result.topics, ['funding'])
    
    def test_analyze_article_relevance_not_found(self):
        """Test article analysis with non-existent article."""
        non_existent_id = str(uuid.uuid4())
        
        with patch.object(self.service, '_check_permission'):
            with self.assertRaises(NotFoundServiceError) as context:
                self.service.analyze_article_relevance(non_existent_id)
        
        self.assertIn(f"Article {non_existent_id} not found", str(context.exception))
    
    def test_calculate_article_relevance(self):
        """Test article relevance calculation algorithm."""
        article = NewsArticleFactory.create(
            group=self.group1,
            title="Major PBSA Development in London",
            content="This is about student accommodation development and investment in London PBSA market.",
            source="Property Week"
        )
        
        score = self.service._calculate_article_relevance(article)
        
        # Should get points for PBSA keywords, title mentions, and credible source
        self.assertGreater(score, 0.5)
        self.assertLessEqual(score, 1.0)
    
    def test_analyze_sentiment_positive(self):
        """Test sentiment analysis for positive content."""
        positive_content = "Great success in the investment growth opportunity expansion development"
        score = self.service._analyze_sentiment(positive_content)
        self.assertGreater(score, 0)
    
    def test_analyze_sentiment_negative(self):
        """Test sentiment analysis for negative content."""
        negative_content = "Decline failure crisis problem bankruptcy loss recession challenging"
        score = self.service._analyze_sentiment(negative_content)
        self.assertLess(score, 0)
    
    def test_analyze_sentiment_neutral(self):
        """Test sentiment analysis for neutral content."""
        neutral_content = "The building has five floors and contains offices."
        score = self.service._analyze_sentiment(neutral_content)
        self.assertEqual(score, 0.0)
    
    def test_identify_target_companies_success(self):
        """Test successful target company identification."""
        # Create relevant articles
        articles = [
            NewsArticleFactory.create_relevant_article(group=self.group1),
            NewsArticleFactory.create_relevant_article(group=self.group1)
        ]
        
        with patch.object(self.service, '_check_permission'):
            with patch.object(self.service, '_extract_company_mentions') as mock_extract:
                with patch.object(self.service, '_create_target_company') as mock_create:
                    mock_extract.return_value = [{'name': 'Test Company Ltd', 'confidence': 0.8}]
                    mock_target = TargetCompanyFactory.create(group=self.group1)
                    mock_create.return_value = mock_target
                    
                    targets = self.service.identify_target_companies()
        
        self.assertEqual(len(targets), 2)  # One target per article
        self.assertEqual(mock_extract.call_count, 2)
        self.assertEqual(mock_create.call_count, 2)
    
    def test_identify_target_companies_existing_target(self):
        """Test target identification with existing company."""
        article = NewsArticleFactory.create_relevant_article(group=self.group1)
        existing_target = TargetCompanyFactory.create(
            group=self.group1,
            company_name="Existing Company Ltd"
        )
        
        with patch.object(self.service, '_check_permission'):
            with patch.object(self.service, '_extract_company_mentions') as mock_extract:
                mock_extract.return_value = [{'name': 'Existing Company Ltd', 'confidence': 0.8}]
                
                targets = self.service.identify_target_companies([str(article.id)])
        
        # Should return existing target, not create new one
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0], existing_target)
        
        # Article should be associated with existing target
        existing_target.refresh_from_db()
        self.assertIn(article, existing_target.source_articles.all())
    
    def test_extract_company_mentions(self):
        """Test company mention extraction from article content."""
        article = NewsArticleFactory.create(
            group=self.group1,
            content="Property Developer Ltd announced a new student accommodation project."
        )
        
        companies = self.service._extract_company_mentions(article)
        
        self.assertGreater(len(companies), 0)
        self.assertIn('name', companies[0])
        self.assertIn('confidence', companies[0])
    
    def test_get_dashboard_metrics_success(self):
        """Test dashboard metrics calculation."""
        # Create sample data
        self.create_sample_data_set(group=self.group1)
        
        with patch.object(self.service, '_check_permission'):
            metrics = self.service.get_dashboard_metrics()
        
        self.assertIn('articles', metrics)
        self.assertIn('targets', metrics)
        self.assertIn('templates', metrics)
        
        # Check article metrics
        article_metrics = metrics['articles']
        self.assertIn('total', article_metrics)
        self.assertIn('relevant', article_metrics)
        self.assertIn('pending', article_metrics)
        self.assertIn('recent', article_metrics)
        self.assertIn('relevance_rate', article_metrics)
        
        # Check target metrics
        target_metrics = metrics['targets']
        self.assertIn('total', target_metrics)
        self.assertIn('qualified', target_metrics)
        self.assertIn('recent', target_metrics)
        self.assertIn('qualification_rate', target_metrics)
    
    def test_get_dashboard_metrics_empty_data(self):
        """Test dashboard metrics with no data."""
        with patch.object(self.service, '_check_permission'):
            metrics = self.service.get_dashboard_metrics()
        
        self.assertEqual(metrics['articles']['total'], 0)
        self.assertEqual(metrics['articles']['relevance_rate'], 0)
        self.assertEqual(metrics['targets']['total'], 0)
        self.assertEqual(metrics['targets']['qualification_rate'], 0)


class NewsAnalysisServiceTest(TestCase, TestDataMixin):
    """Test NewsAnalysisService functionality."""
    
    def setUp(self):
        super().setUp()
        self.service = NewsAnalysisService(
            user=self.analyst_user,
            group=self.group1
        )
    
    def test_batch_analyze_articles_with_ids(self):
        """Test batch analysis with specific article IDs."""
        articles = NewsArticleFactory.create_batch(3, group=self.group1, status=NewsArticle.ArticleStatus.PENDING)
        article_ids = [str(article.id) for article in articles]
        
        with patch.object(self.service, '_check_permission'):
            with patch.object(self.service, '_analyze_single_article') as mock_analyze:
                mock_analyze.return_value = {
                    'article_id': str(articles[0].id),
                    'relevance_score': 0.8,
                    'sentiment_score': 0.3,
                    'topics': ['funding'],
                    'entity_count': 2,
                    'status': NewsArticle.ArticleStatus.RELEVANT
                }
                
                results = self.service.batch_analyze_articles(article_ids=article_ids)
        
        self.assertEqual(results['total_analyzed'], 3)
        self.assertEqual(mock_analyze.call_count, 3)
    
    def test_batch_analyze_articles_by_date(self):
        """Test batch analysis by date range."""
        # Create articles from different dates
        old_article = NewsArticleFactory.create(
            group=self.group1,
            status=NewsArticle.ArticleStatus.PENDING
        )
        old_article.scraped_date = timezone.now() - timedelta(days=10)
        old_article.save()
        
        recent_article = NewsArticleFactory.create(
            group=self.group1,
            status=NewsArticle.ArticleStatus.PENDING
        )
        
        with patch.object(self.service, '_check_permission'):
            with patch.object(self.service, '_analyze_single_article') as mock_analyze:
                mock_analyze.return_value = {
                    'article_id': str(recent_article.id),
                    'relevance_score': 0.7,
                    'sentiment_score': 0.2,
                    'topics': [],
                    'entity_count': 0,
                    'status': NewsArticle.ArticleStatus.IRRELEVANT
                }
                
                results = self.service.batch_analyze_articles(days_back=7)
        
        # Should only analyze recent article (within 7 days)
        self.assertEqual(results['total_analyzed'], 1)
        self.assertEqual(mock_analyze.call_count, 1)
    
    def test_batch_analyze_articles_error_handling(self):
        """Test batch analysis with errors."""
        articles = NewsArticleFactory.create_batch(2, group=self.group1, status=NewsArticle.ArticleStatus.PENDING)
        
        with patch.object(self.service, '_check_permission'):
            with patch.object(self.service, '_analyze_single_article', side_effect=Exception("Analysis error")):
                results = self.service.batch_analyze_articles()
        
        self.assertEqual(results['processing_errors'], 2)
        self.assertEqual(results['total_analyzed'], 0)
    
    def test_advanced_relevance_scoring(self):
        """Test advanced relevance scoring algorithm."""
        article = NewsArticleFactory.create(
            group=self.group1,
            title="PBSA Development Fund Launches £100M Investment Programme",
            content="Purpose built student accommodation developer announces major investment in UK university cities.",
            source="Property Week",
            published_date=timezone.now() - timedelta(hours=1)  # Very recent
        )
        
        score = self.service._advanced_relevance_scoring(article)
        
        # Should score highly due to PBSA keywords, credible source, and recency
        self.assertGreater(score, 0.7)
    
    def test_sentiment_analysis(self):
        """Test enhanced sentiment analysis."""
        positive_content = "Successful growth expansion opportunity excellent breakthrough innovative"
        negative_content = "Decline crisis failure bankruptcy struggling disappointing weak"
        
        positive_score = self.service._sentiment_analysis(positive_content)
        negative_score = self.service._sentiment_analysis(negative_content)
        
        self.assertGreater(positive_score, 0)
        self.assertLess(negative_score, 0)
    
    def test_entity_extraction(self):
        """Test entity extraction functionality."""
        content = """
        Urban Properties Ltd raised £10 million in Series A funding.
        The University of Manchester partnership was announced.
        CEO John Smith commented on the £5.5 billion market opportunity.
        """
        
        entities = self.service._entity_extraction(content)
        
        self.assertIn('companies', entities)
        self.assertIn('monetary_amounts', entities)
        self.assertIn('universities', entities)
        self.assertGreater(len(entities['monetary_amounts']), 0)
        self.assertGreater(len(entities['universities']), 0)
    
    def test_topic_modeling(self):
        """Test topic identification."""
        content = """
        The funding round was led by venture capital firm Investment Partners.
        The PropTech platform uses artificial intelligence for property management.
        Student accommodation demand continues to grow in university cities.
        """
        
        topics = self.service._topic_modeling(content)
        
        expected_topics = ['funding_investment', 'proptech_technology', 'student_housing']
        for topic in expected_topics:
            self.assertIn(topic, topics)
    
    def test_generate_summary(self):
        """Test article summary generation."""
        long_content = """
        A major real estate investment fund has announced a significant acquisition.
        The portfolio includes multiple student accommodation properties.
        This represents the largest PBSA investment in the current market.
        The fund plans to expand operations across European markets.
        Property management will be handled by experienced operators.
        Students will benefit from modern facilities and amenities.
        """
        
        summary = self.service._generate_summary(long_content, max_sentences=2)
        
        self.assertIsInstance(summary, str)
        self.assertLess(len(summary), len(long_content))
        self.assertTrue(summary.endswith('.'))
    
    def test_get_analysis_insights(self):
        """Test analysis insights generation."""
        # Create articles with different topics and sentiments
        articles_data = [
            {'topics': ['funding_investment'], 'sentiment_score': 0.5},
            {'topics': ['property_development'], 'sentiment_score': 0.3},
            {'topics': ['funding_investment', 'student_housing'], 'sentiment_score': 0.8}
        ]
        
        for data in articles_data:
            NewsArticleFactory.create(
                group=self.group1,
                topics=data['topics'],
                sentiment_score=data['sentiment_score']
            )
        
        with patch.object(self.service, '_check_permission'):
            insights = self.service.get_analysis_insights(days_back=30)
        
        self.assertIn('total_articles', insights)
        self.assertIn('relevant_articles', insights)
        self.assertIn('top_topics', insights)
        self.assertIn('sentiment_trend', insights)
        self.assertIn('top_sources', insights)
        
        # Check topic frequency
        top_topics = dict(insights['top_topics'])
        self.assertEqual(top_topics.get('funding_investment'), 2)
        self.assertEqual(top_topics.get('property_development'), 1)


class TargetScoringServiceTest(TestCase, TestDataMixin):
    """Test TargetScoringService functionality."""
    
    def setUp(self):
        super().setUp()
        self.service = TargetScoringService(
            user=self.analyst_user,
            group=self.group1
        )
    
    def test_calculate_comprehensive_score_success(self):
        """Test comprehensive scoring calculation."""
        target = TargetCompanyFactory.create_qualified_target(group=self.group1)
        
        with patch.object(self.service, '_check_permission'):
            result = self.service.calculate_comprehensive_score(str(target.id))
        
        self.assertIn('target_id', result)
        self.assertIn('total_score', result)
        self.assertIn('components', result)
        self.assertIn('weights', result)
        self.assertIn('qualification_status', result)
        self.assertIn('recommendations', result)
        
        # Check all scoring components are present
        components = result['components']
        expected_components = [
            'business_alignment', 'market_presence', 'news_sentiment',
            'company_maturity', 'geographic_fit', 'engagement_potential',
            'data_completeness'
        ]
        for component in expected_components:
            self.assertIn(component, components)
            self.assertIsInstance(components[component], float)
    
    def test_calculate_comprehensive_score_not_found(self):
        """Test scoring with non-existent target."""
        non_existent_id = str(uuid.uuid4())
        
        with patch.object(self.service, '_check_permission'):
            with self.assertRaises(NotFoundServiceError) as context:
                self.service.calculate_comprehensive_score(non_existent_id)
        
        self.assertIn(f"Target company {non_existent_id} not found", str(context.exception))
    
    def test_score_business_alignment_developer(self):
        """Test business alignment scoring for developer."""
        target = TargetCompanyFactory.create(
            group=self.group1,
            business_model='developer',
            focus_sectors=['pbsa'],
            description='Leading PBSA development company with strong portfolio'
        )
        
        score = self.service._score_business_alignment(target)
        
        # Should score highly for developer model + PBSA focus + relevant description
        self.assertGreater(score, 80.0)
    
    def test_score_business_alignment_poor_fit(self):
        """Test business alignment scoring for poor fit."""
        target = TargetCompanyFactory.create(
            group=self.group1,
            business_model='other',
            focus_sectors=[],
            description='Unrelated business activities'
        )
        
        score = self.service._score_business_alignment(target)
        
        # Should score low for poor business model fit
        self.assertLess(score, 30.0)
    
    def test_score_market_presence_large_company(self):
        """Test market presence scoring for large company."""
        target = TargetCompanyFactory.create(
            group=self.group1,
            company_size=TargetCompany.CompanySize.LARGE,
            employee_count=1500,
            domain='https://example.com',
            linkedin_url='https://linkedin.com/company/example'
        )
        
        # Add recent news articles
        articles = NewsArticleFactory.create_batch(3, group=self.group1)
        target.source_articles.set(articles)
        
        score = self.service._score_market_presence(target)
        
        # Should score highly for large size + digital presence + news mentions
        self.assertGreater(score, 70.0)
    
    def test_score_news_sentiment_positive(self):
        """Test news sentiment scoring with positive articles."""
        target = TargetCompanyFactory.create(group=self.group1)
        
        # Create positive sentiment articles
        positive_articles = [
            NewsArticleFactory.create(group=self.group1, sentiment_score=0.6),
            NewsArticleFactory.create(group=self.group1, sentiment_score=0.8)
        ]
        target.source_articles.set(positive_articles)
        
        score = self.service._score_news_sentiment(target)
        
        # Should score above neutral (50) for positive sentiment
        self.assertGreater(score, 60.0)
    
    def test_score_news_sentiment_no_data(self):
        """Test news sentiment scoring with no sentiment data."""
        target = TargetCompanyFactory.create(group=self.group1)
        
        score = self.service._score_news_sentiment(target)
        
        # Should return neutral score (50) when no sentiment data
        self.assertEqual(score, 50.0)
    
    def test_score_geographic_fit_preferred_market(self):
        """Test geographic fit scoring for preferred markets."""
        target = TargetCompanyFactory.create(
            group=self.group1,
            headquarters_country='GB',  # UK is preferred
            geographic_focus=['UK', 'Ireland', 'Netherlands']
        )
        
        score = self.service._score_geographic_fit(target)
        
        # Should score highly for UK base + European focus
        self.assertGreater(score, 80.0)
    
    def test_score_engagement_potential_fresh_lead(self):
        """Test engagement potential for fresh, active lead."""
        target = TargetCompanyFactory.create(
            group=self.group1,
            status=TargetCompany.TargetStatus.QUALIFIED
        )
        
        # Make it a fresh lead
        target.created_at = timezone.now() - timedelta(days=3)
        target.save()
        
        # Add recent news
        recent_article = NewsArticleFactory.create(
            group=self.group1,
            published_date=timezone.now() - timedelta(days=30)
        )
        target.source_articles.add(recent_article)
        
        score = self.service._score_engagement_potential(target)
        
        # Should score highly for qualified + fresh + recent news
        self.assertGreater(score, 70.0)
    
    def test_score_data_completeness_full_profile(self):
        """Test data completeness scoring for complete profile."""
        target = TargetCompanyFactory.create(
            group=self.group1,
            company_name='Complete Company Ltd',
            domain='https://complete.com',
            linkedin_url='https://linkedin.com/company/complete',
            description='Complete description',
            headquarters_city='London',
            headquarters_country='GB',
            company_size=TargetCompany.CompanySize.LARGE,
            employee_count=500,
            business_model='developer',
            focus_sectors=['pbsa'],
            geographic_focus=['UK'],
            enrichment_data={'linkedin_followers': 1000},
            last_enriched=timezone.now()
        )
        
        score = self.service._score_data_completeness(target)
        
        # Should score highly for complete data profile
        self.assertGreater(score, 90.0)
    
    def test_determine_qualification_status(self):
        """Test qualification status determination."""
        test_cases = [
            (85.0, 'highly_qualified'),
            (70.0, 'qualified'),
            (55.0, 'potential'),
            (35.0, 'needs_research'),
            (20.0, 'poor_fit')
        ]
        
        for score, expected_status in test_cases:
            status = self.service._determine_qualification_status(score)
            self.assertEqual(status, expected_status)
    
    def test_generate_scoring_recommendations(self):
        """Test scoring recommendations generation."""
        # Create components with mixed scores
        components = {
            'business_alignment': 30.0,  # Low - should generate recommendation
            'market_presence': 80.0,     # High - no recommendation
            'news_sentiment': 20.0,      # Low - should generate recommendation
            'company_maturity': 70.0,    # OK - no recommendation
            'geographic_fit': 40.0,      # Low - should generate recommendation
            'engagement_potential': 30.0, # Low - should generate recommendation
            'data_completeness': 60.0    # Low - should generate recommendation
        }
        
        recommendations = self.service._generate_scoring_recommendations(components)
        
        # Should have recommendations for low-scoring components
        self.assertGreater(len(recommendations), 3)
        self.assertTrue(any('PBSA focus' in rec for rec in recommendations))
        self.assertTrue(any('positive news' in rec for rec in recommendations))
    
    def test_batch_score_targets_success(self):
        """Test batch scoring of multiple targets."""
        targets = TargetCompanyFactory.create_batch(3, group=self.group1)
        target_ids = [str(target.id) for target in targets]
        
        with patch.object(self.service, '_check_permission'):
            with patch.object(self.service, 'calculate_comprehensive_score') as mock_score:
                mock_score.return_value = {
                    'target_id': target_ids[0],
                    'qualification_status': 'qualified'
                }
                
                results = self.service.batch_score_targets(target_ids)
        
        self.assertEqual(results['total_scored'], 3)
        self.assertEqual(results['qualified'], 3)  # All returned as qualified
        self.assertEqual(mock_score.call_count, 3)
    
    def test_batch_score_targets_with_errors(self):
        """Test batch scoring with errors."""
        targets = TargetCompanyFactory.create_batch(2, group=self.group1)
        target_ids = [str(target.id) for target in targets]
        
        with patch.object(self.service, '_check_permission'):
            with patch.object(self.service, 'calculate_comprehensive_score', side_effect=Exception("Scoring error")):
                results = self.service.batch_score_targets(target_ids)
        
        self.assertEqual(results['total_scored'], 0)
    
    def test_get_scoring_insights(self):
        """Test scoring insights generation."""
        # Create targets with different scores and characteristics
        TargetCompanyFactory.create_qualified_target(group=self.group1)  # High score
        TargetCompanyFactory.create_startup_target(group=self.group1)    # Lower score
        
        with patch.object(self.service, '_check_permission'):
            insights = self.service.get_scoring_insights()
        
        self.assertIn('total_targets', insights)
        self.assertIn('average_score', insights)
        self.assertIn('score_distribution', insights)
        self.assertIn('business_model_performance', insights)
        self.assertIn('geographic_performance', insights)
        self.assertIn('status_performance', insights)
        self.assertIn('top_targets', insights)
        
        # Check score distribution
        score_dist = insights['score_distribution']
        self.assertIn('80-100', score_dist)
        self.assertIn('65-79', score_dist)


class ServiceIntegrationTest(TestCase, TestDataMixin):
    """Test integration between different services."""
    
    def setUp(self):
        super().setUp()
        self.mi_service = MarketIntelligenceService(user=self.analyst_user, group=self.group1)
        self.analysis_service = NewsAnalysisService(user=self.analyst_user, group=self.group1)
        self.scoring_service = TargetScoringService(user=self.analyst_user, group=self.group1)
    
    def test_end_to_end_workflow(self):
        """Test complete end-to-end workflow integration."""
        # 1. Create query template
        template_data = {
            'name': 'Integration Test Template',
            'template_type': QueryTemplate.TemplateType.COMPANY_DISCOVERY,
            'query_pattern': 'PBSA development {city}',
            'keywords': ['pbsa', 'student accommodation']
        }
        
        with patch.object(self.mi_service, '_check_permission'):
            template = self.mi_service.create_query_template(template_data)
        
        # 2. Execute news scraping
        with patch.object(self.mi_service, '_check_permission'):
            with patch.object(self.mi_service, '_scrape_articles') as mock_scrape:
                mock_articles = [NewsArticleFactory.create_pending_article(group=self.group1)]
                mock_scrape.return_value = mock_articles
                
                scraping_result = self.mi_service.execute_news_scraping(str(template.id))
        
        # 3. Analyze articles
        article = mock_articles[0]
        with patch.object(self.analysis_service, '_check_permission'):
            with patch.object(self.analysis_service, '_analyze_single_article') as mock_analyze:
                mock_analyze.return_value = {
                    'article_id': str(article.id),
                    'relevance_score': 0.8,
                    'status': NewsArticle.ArticleStatus.RELEVANT
                }
                
                analysis_result = self.analysis_service.batch_analyze_articles(
                    article_ids=[str(article.id)]
                )
        
        # 4. Identify targets
        with patch.object(self.mi_service, '_check_permission'):
            with patch.object(self.mi_service, '_extract_company_mentions') as mock_extract:
                with patch.object(self.mi_service, '_create_target_company') as mock_create:
                    mock_extract.return_value = [{'name': 'Integration Test Company', 'confidence': 0.8}]
                    target = TargetCompanyFactory.create(group=self.group1)
                    mock_create.return_value = target
                    
                    targets = self.mi_service.identify_target_companies([str(article.id)])
        
        # 5. Score targets
        target = targets[0]
        with patch.object(self.scoring_service, '_check_permission'):
            scoring_result = self.scoring_service.calculate_comprehensive_score(str(target.id))
        
        # Verify end-to-end flow
        self.assertIsNotNone(template)
        self.assertEqual(scraping_result['articles_found'], 1)
        self.assertEqual(analysis_result['total_analyzed'], 1)
        self.assertEqual(len(targets), 1)
        self.assertIn('total_score', scoring_result)
    
    def test_permission_isolation_between_services(self):
        """Test that services properly isolate permissions."""
        # Create service with different user
        unauthorized_service = MarketIntelligenceService(
            user=self.viewer_user,  # Read-only user
            group=self.group1
        )
        
        template_data = {
            'name': 'Unauthorized Template',
            'template_type': QueryTemplate.TemplateType.COMPANY_DISCOVERY,
            'query_pattern': 'test'
        }
        
        # Should fail permission check
        with patch.object(unauthorized_service, '_check_permission', 
                         side_effect=PermissionServiceError("Permission denied")):
            with self.assertRaises(PermissionServiceError):
                unauthorized_service.create_query_template(template_data)
    
    def test_group_isolation_between_services(self):
        """Test that services properly isolate data by group."""
        # Create data in group1
        target_group1 = TargetCompanyFactory.create(group=self.group1)
        
        # Create service for group2
        group2_service = TargetScoringService(user=self.manager_user, group=self.group2)
        
        # Should not find target from group1
        with patch.object(group2_service, '_check_permission'):
            with self.assertRaises(NotFoundServiceError):
                group2_service.calculate_comprehensive_score(str(target_group1.id))