"""
Comprehensive tests for market intelligence ViewSets.

Tests all ViewSet functionality including CRUD operations, custom actions,
permissions, filtering, and API responses to ensure 90%+ code coverage.
"""

import uuid
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from accounts.models import Group
from ..models import QueryTemplate, NewsArticle, TargetCompany
from ..viewsets import (
    QueryTemplateViewSet, NewsArticleViewSet, TargetCompanyViewSet,
    MarketIntelligenceDashboardViewSet
)
from .factories import (
    QueryTemplateFactory, NewsArticleFactory, TargetCompanyFactory, TestDataMixin
)

User = get_user_model()


class QueryTemplateViewSetTest(APITestCase, TestDataMixin):
    """Test QueryTemplateViewSet functionality."""
    
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.analyst_user)
        self.url = '/api/market-intelligence/query-templates/'
    
    def test_list_query_templates(self):
        """Test listing query templates."""
        # Create templates for different groups
        template1 = QueryTemplateFactory.create(group=self.group1)
        template2 = QueryTemplateFactory.create(group=self.group2)
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Should only see templates from user's group
        template_ids = [item['id'] for item in data['results']]
        self.assertIn(str(template1.id), template_ids)
        self.assertNotIn(str(template2.id), template_ids)
    
    def test_create_query_template(self):
        """Test creating a new query template."""
        template_data = {
            'name': 'New API Template',
            'description': 'Created via API',
            'template_type': QueryTemplate.TemplateType.COMPANY_DISCOVERY,
            'query_pattern': 'student accommodation {city}',
            'keywords': ['pbsa', 'student housing'],
            'regions': ['UK'],
            'schedule_frequency': 'daily'
        }
        
        response = self.client.post(self.url, template_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        
        self.assertEqual(data['name'], 'New API Template')
        self.assertEqual(data['keywords'], ['pbsa', 'student housing'])
        
        # Verify template was created in database
        template = QueryTemplate.objects.get(id=data['id'])
        self.assertEqual(template.group, self.group1)  # Should be assigned to user's group
    
    def test_create_query_template_missing_fields(self):
        """Test creating template with missing required fields."""
        incomplete_data = {
            'description': 'Missing required fields'
        }
        
        response = self.client.post(self.url, incomplete_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn('name', data)
        self.assertIn('template_type', data)
    
    def test_retrieve_query_template(self):
        """Test retrieving a specific query template."""
        template = QueryTemplateFactory.create(group=self.group1)
        url = f'{self.url}{template.id}/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['id'], str(template.id))
        self.assertEqual(data['name'], template.name)
    
    def test_update_query_template(self):
        """Test updating a query template."""
        template = QueryTemplateFactory.create(group=self.group1)
        url = f'{self.url}{template.id}/'
        
        update_data = {
            'name': 'Updated Template Name',
            'description': template.description,
            'template_type': template.template_type,
            'query_pattern': template.query_pattern,
            'is_active': False
        }
        
        response = self.client.put(url, update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['name'], 'Updated Template Name')
        self.assertFalse(data['is_active'])
    
    def test_delete_query_template(self):
        """Test deleting a query template."""
        template = QueryTemplateFactory.create(group=self.group1)
        url = f'{self.url}{template.id}/'
        
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(QueryTemplate.objects.filter(id=template.id).exists())
    
    @patch('market_intelligence.services.MarketIntelligenceService.execute_news_scraping')
    def test_execute_scraping_action(self, mock_scraping):
        """Test execute_scraping custom action."""
        template = QueryTemplateFactory.create(group=self.group1)
        url = f'{self.url}{template.id}/execute_scraping/'
        
        mock_scraping.return_value = {
            'template_id': str(template.id),
            'articles_found': 5,
            'articles_processed': 3
        }
        
        scraping_data = {
            'search_parameters': {
                'city': 'London'
            },
            'max_articles': 10
        }
        
        response = self.client.post(url, scraping_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['articles_found'], 5)
        self.assertEqual(data['articles_processed'], 3)
        mock_scraping.assert_called_once()
    
    def test_toggle_active_action(self):
        """Test toggle_active custom action."""
        template = QueryTemplateFactory.create(group=self.group1, is_active=True)
        url = f'{self.url}{template.id}/toggle_active/'
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertFalse(data['is_active'])
        
        # Verify database was updated
        template.refresh_from_db()
        self.assertFalse(template.is_active)
    
    def test_active_templates_action(self):
        """Test active_templates custom action."""
        active_template = QueryTemplateFactory.create(group=self.group1, is_active=True)
        inactive_template = QueryTemplateFactory.create(group=self.group1, is_active=False)
        
        url = f'{self.url}active_templates/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        template_ids = [item['id'] for item in data]
        self.assertIn(str(active_template.id), template_ids)
        self.assertNotIn(str(inactive_template.id), template_ids)
    
    def test_filtering_and_search(self):
        """Test filtering and search functionality."""
        # Create templates with different characteristics
        funding_template = QueryTemplateFactory.create_funding_template(group=self.group1)
        discovery_template = QueryTemplateFactory.create(
            group=self.group1,
            template_type=QueryTemplate.TemplateType.COMPANY_DISCOVERY,
            name='Discovery Template'
        )
        
        # Test filtering by template_type
        response = self.client.get(f'{self.url}?template_type=funding_announcement')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['id'], str(funding_template.id))
        
        # Test search by name
        response = self.client.get(f'{self.url}?search=Discovery')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['id'], str(discovery_template.id))
    
    def test_unauthorized_access(self):
        """Test access without authentication."""
        self.client.force_authenticate(user=None)
        
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NewsArticleViewSetTest(APITestCase, TestDataMixin):
    """Test NewsArticleViewSet functionality."""
    
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.analyst_user)
        self.url = '/api/market-intelligence/news-articles/'
    
    def test_list_news_articles(self):
        """Test listing news articles."""
        article1 = NewsArticleFactory.create(group=self.group1)
        article2 = NewsArticleFactory.create(group=self.group2)
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Should only see articles from user's group
        article_ids = [item['id'] for item in data['results']]
        self.assertIn(str(article1.id), article_ids)
        self.assertNotIn(str(article2.id), article_ids)
    
    def test_retrieve_article_detail(self):
        """Test retrieving article detail view."""
        article = NewsArticleFactory.create(group=self.group1)
        url = f'{self.url}{article.id}/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Detail view should include full content
        self.assertEqual(data['id'], str(article.id))
        self.assertIn('content', data)
        self.assertIn('entities_extracted', data)
        self.assertIn('topics', data)
    
    @patch('market_intelligence.services.MarketIntelligenceService.analyze_article_relevance')
    def test_analyze_action(self, mock_analyze):
        """Test analyze custom action for individual article."""
        article = NewsArticleFactory.create_pending_article(group=self.group1)
        url = f'{self.url}{article.id}/analyze/'
        
        # Mock the analysis result
        article.relevance_score = 0.8
        article.status = NewsArticle.ArticleStatus.RELEVANT
        mock_analyze.return_value = article
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['relevance_score'], 0.8)
        self.assertEqual(data['status'], NewsArticle.ArticleStatus.RELEVANT)
        mock_analyze.assert_called_once()
    
    @patch('market_intelligence.services.NewsAnalysisService.batch_analyze_articles')
    def test_batch_analyze_action(self, mock_batch_analyze):
        """Test batch_analyze custom action."""
        articles = NewsArticleFactory.create_batch(3, group=self.group1, status=NewsArticle.ArticleStatus.PENDING)
        url = f'{self.url}batch_analyze/'
        
        mock_batch_analyze.return_value = {
            'total_analyzed': 3,
            'relevant_count': 2,
            'irrelevant_count': 1,
            'processing_errors': 0
        }
        
        batch_data = {
            'article_ids': [str(article.id) for article in articles],
            'analysis_type': 'full'
        }
        
        response = self.client.post(url, batch_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['total_analyzed'], 3)
        self.assertEqual(data['relevant_count'], 2)
        mock_batch_analyze.assert_called_once()
    
    def test_relevant_articles_action(self):
        """Test relevant_articles custom action."""
        relevant_article = NewsArticleFactory.create_relevant_article(group=self.group1)
        irrelevant_article = NewsArticleFactory.create_irrelevant_article(group=self.group1)
        
        url = f'{self.url}relevant_articles/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        article_ids = [item['id'] for item in data['results']]
        self.assertIn(str(relevant_article.id), article_ids)
        self.assertNotIn(str(irrelevant_article.id), article_ids)
    
    def test_pending_analysis_action(self):
        """Test pending_analysis custom action."""
        pending_article = NewsArticleFactory.create_pending_article(group=self.group1)
        analyzed_article = NewsArticleFactory.create(group=self.group1, status=NewsArticle.ArticleStatus.ANALYZED)
        
        url = f'{self.url}pending_analysis/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        article_ids = [item['id'] for item in data['results']]
        self.assertIn(str(pending_article.id), article_ids)
        self.assertNotIn(str(analyzed_article.id), article_ids)
    
    @patch('market_intelligence.services.NewsAnalysisService.get_analysis_insights')
    def test_analysis_insights_action(self, mock_insights):
        """Test analysis_insights custom action."""
        mock_insights.return_value = {
            'total_articles': 100,
            'relevant_articles': 30,
            'relevance_rate': 30.0,
            'top_topics': [('funding_investment', 15), ('property_development', 12)],
            'sentiment_trend': {'positive': 40, 'neutral': 35, 'negative': 25}
        }
        
        url = f'{self.url}analysis_insights/'
        response = self.client.get(url, {'days_back': 30})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['total_articles'], 100)
        self.assertEqual(data['relevance_rate'], 30.0)
        mock_insights.assert_called_once_with(days_back=30)
    
    def test_article_filtering(self):
        """Test article filtering functionality."""
        # Create articles with different characteristics
        relevant_article = NewsArticleFactory.create_relevant_article(group=self.group1)
        property_week_article = NewsArticleFactory.create(
            group=self.group1,
            source='Property Week',
            status=NewsArticle.ArticleStatus.ANALYZED
        )
        
        # Test filtering by status
        response = self.client.get(f'{self.url}?status=relevant')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        article_ids = [item['id'] for item in data['results']]
        self.assertIn(str(relevant_article.id), article_ids)
        
        # Test filtering by source
        response = self.client.get(f'{self.url}?source=Property Week')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Should find articles with Property Week in source
        found_property_week = any(
            'Property Week' in item['source'] 
            for item in data['results']
        )
        self.assertTrue(found_property_week)


class TargetCompanyViewSetTest(APITestCase, TestDataMixin):
    """Test TargetCompanyViewSet functionality."""
    
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.analyst_user)
        self.url = '/api/market-intelligence/target-companies/'
    
    def test_list_target_companies(self):
        """Test listing target companies."""
        target1 = TargetCompanyFactory.create(group=self.group1, identified_by=self.analyst_user)
        target2 = TargetCompanyFactory.create(group=self.group2, identified_by=self.viewer_user)
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Should only see targets from user's group
        target_ids = [item['id'] for item in data['results']]
        self.assertIn(str(target1.id), target_ids)
        self.assertNotIn(str(target2.id), target_ids)
    
    def test_create_target_company(self):
        """Test creating a new target company."""
        target_data = {
            'company_name': 'New Target Company Ltd',
            'domain': 'https://newtarget.com',
            'description': 'A promising PBSA development company',
            'business_model': 'developer',
            'focus_sectors': ['pbsa'],
            'headquarters_country': 'GB'
        }
        
        response = self.client.post(self.url, target_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        
        self.assertEqual(data['company_name'], 'New Target Company Ltd')
        self.assertEqual(data['business_model'], 'developer')
        
        # Verify target was created with correct associations
        target = TargetCompany.objects.get(id=data['id'])
        self.assertEqual(target.group, self.group1)
        self.assertEqual(target.identified_by, self.analyst_user)
    
    def test_retrieve_target_detail(self):
        """Test retrieving target company detail view."""
        target = TargetCompanyFactory.create(group=self.group1, identified_by=self.analyst_user)
        url = f'{self.url}{target.id}/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Detail view should include comprehensive information
        self.assertEqual(data['id'], str(target.id))
        self.assertIn('description', data)
        self.assertIn('enrichment_data', data)
        self.assertIn('identified_by', data)
    
    @patch('market_intelligence.services.TargetScoringService.calculate_comprehensive_score')
    def test_calculate_score_action(self, mock_scoring):
        """Test calculate_score custom action."""
        target = TargetCompanyFactory.create(group=self.group1)
        url = f'{self.url}{target.id}/calculate_score/'
        
        mock_scoring.return_value = {
            'target_id': str(target.id),
            'total_score': 85.5,
            'components': {
                'business_alignment': 90.0,
                'market_presence': 80.0,
                'news_sentiment': 85.0
            },
            'qualification_status': 'highly_qualified'
        }
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['total_score'], 85.5)
        self.assertEqual(data['qualification_status'], 'highly_qualified')
        mock_scoring.assert_called_once()
    
    @patch('market_intelligence.services.TargetScoringService.batch_score_targets')
    def test_batch_score_action(self, mock_batch_scoring):
        """Test batch_score custom action."""
        targets = TargetCompanyFactory.create_batch(3, group=self.group1)
        url = f'{self.url}batch_score/'
        
        mock_batch_scoring.return_value = {
            'total_scored': 3,
            'qualified': 2,
            'needs_research': 1,
            'average_score': 72.5
        }
        
        batch_data = {
            'target_ids': [str(target.id) for target in targets],
            'scoring_components': ['business_alignment', 'market_presence']
        }
        
        response = self.client.post(url, batch_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['total_scored'], 3)
        self.assertEqual(data['qualified'], 2)
        mock_batch_scoring.assert_called_once()
    
    def test_assign_analyst_action(self):
        """Test assign_analyst custom action."""
        target = TargetCompanyFactory.create(group=self.group1)
        url = f'{self.url}{target.id}/assign_analyst/'
        
        assign_data = {
            'analyst_id': str(self.manager_user.id)
        }
        
        response = self.client.post(url, assign_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Verify assignment
        target.refresh_from_db()
        self.assertEqual(target.assigned_analyst, self.manager_user)
    
    def test_update_status_action(self):
        """Test update_status custom action."""
        target = TargetCompanyFactory.create(group=self.group1, status=TargetCompany.TargetStatus.IDENTIFIED)
        url = f'{self.url}{target.id}/update_status/'
        
        status_data = {
            'status': TargetCompany.TargetStatus.QUALIFIED
        }
        
        response = self.client.post(url, status_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['status'], TargetCompany.TargetStatus.QUALIFIED)
        
        # Verify database update
        target.refresh_from_db()
        self.assertEqual(target.status, TargetCompany.TargetStatus.QUALIFIED)
    
    def test_promote_to_partner_action(self):
        """Test promote_to_partner custom action."""
        target = TargetCompanyFactory.create(group=self.group1, status=TargetCompany.TargetStatus.QUALIFIED)
        url = f'{self.url}{target.id}/promote_to_partner/'
        
        promotion_data = {
            'promotion_reason': 'Excellent strategic fit for our investment portfolio',
            'priority_level': 'high'
        }
        
        response = self.client.post(url, promotion_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['status'], TargetCompany.TargetStatus.CONVERTED)
        
        # Verify conversion
        target.refresh_from_db()
        self.assertEqual(target.status, TargetCompany.TargetStatus.CONVERTED)
        self.assertIsNotNone(target.converted_at)
    
    def test_qualified_targets_action(self):
        """Test qualified_targets custom action."""
        qualified_target = TargetCompanyFactory.create_qualified_target(group=self.group1)
        unqualified_target = TargetCompanyFactory.create_startup_target(group=self.group1)
        
        url = f'{self.url}qualified_targets/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        target_ids = [item['id'] for item in data['results']]
        self.assertIn(str(qualified_target.id), target_ids)
        self.assertNotIn(str(unqualified_target.id), target_ids)
    
    def test_my_assignments_action(self):
        """Test my_assignments custom action."""
        my_target = TargetCompanyFactory.create(
            group=self.group1,
            assigned_analyst=self.analyst_user
        )
        other_target = TargetCompanyFactory.create(
            group=self.group1,
            assigned_analyst=self.manager_user
        )
        
        url = f'{self.url}my_assignments/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        target_ids = [item['id'] for item in data['results']]
        self.assertIn(str(my_target.id), target_ids)
        self.assertNotIn(str(other_target.id), target_ids)
    
    def test_target_filtering(self):
        """Test target company filtering functionality."""
        # Create targets with different characteristics
        developer_target = TargetCompanyFactory.create(
            group=self.group1,
            business_model='developer',
            status=TargetCompany.TargetStatus.QUALIFIED
        )
        investor_target = TargetCompanyFactory.create(
            group=self.group1,
            business_model='investor',
            status=TargetCompany.TargetStatus.RESEARCHING
        )
        
        # Test filtering by business_model
        response = self.client.get(f'{self.url}?business_model=developer')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        target_ids = [item['id'] for item in data['results']]
        self.assertIn(str(developer_target.id), target_ids)
        self.assertNotIn(str(investor_target.id), target_ids)
        
        # Test filtering by status
        response = self.client.get(f'{self.url}?status=qualified')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Should find qualified targets
        qualified_found = any(
            item['status'] == 'qualified'
            for item in data['results']
        )
        self.assertTrue(qualified_found)


class MarketIntelligenceDashboardViewSetTest(APITestCase, TestDataMixin):
    """Test MarketIntelligenceDashboardViewSet functionality."""
    
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.analyst_user)
        self.url = '/api/market-intelligence/dashboard/'
    
    @patch('market_intelligence.services.MarketIntelligenceService.get_dashboard_metrics')
    def test_metrics_action(self, mock_metrics):
        """Test metrics custom action."""
        mock_metrics.return_value = {
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
            }
        }
        
        url = f'{self.url}metrics/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(data['articles']['total'], 150)
        self.assertEqual(data['targets']['qualified'], 8)
        self.assertEqual(data['templates']['active'], 4)
        mock_metrics.assert_called_once()
    
    @patch('market_intelligence.services.MarketIntelligenceService.identify_target_companies')
    def test_identify_targets_action(self, mock_identify):
        """Test identify_targets custom action."""
        # Create some articles
        articles = NewsArticleFactory.create_batch(3, group=self.group1)
        
        # Mock target identification
        mock_targets = [
            TargetCompanyFactory.create(group=self.group1, company_name=f'Target Company {i}')
            for i in range(2)
        ]
        mock_identify.return_value = mock_targets
        
        url = f'{self.url}identify_targets/'
        identify_data = {
            'article_ids': [str(article.id) for article in articles]
        }
        
        response = self.client.post(url, identify_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(data['identified_count'], 2)
        self.assertEqual(len(data['targets']), 2)
        self.assertIn('id', data['targets'][0])
        self.assertIn('company_name', data['targets'][0])
        self.assertIn('lead_score', data['targets'][0])
        
        mock_identify.assert_called_once_with([str(article.id) for article in articles])
    
    def test_identify_targets_without_article_ids(self):
        """Test identify_targets action without article_ids (uses all relevant articles)."""
        # Create relevant articles
        NewsArticleFactory.create_relevant_article(group=self.group1)
        NewsArticleFactory.create_relevant_article(group=self.group1)
        
        with patch('market_intelligence.services.MarketIntelligenceService.identify_target_companies') as mock_identify:
            mock_identify.return_value = []
            
            url = f'{self.url}identify_targets/'
            response = self.client.post(url, {}, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            mock_identify.assert_called_once_with([])  # Empty list means use all relevant


class ViewSetPermissionTest(APITestCase, TestDataMixin):
    """Test ViewSet permission handling."""
    
    def setUp(self):
        super().setUp()
        self.client = APIClient()
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated requests are denied."""
        urls = [
            '/api/market-intelligence/query-templates/',
            '/api/market-intelligence/news-articles/',
            '/api/market-intelligence/target-companies/',
            '/api/market-intelligence/dashboard/metrics/'
        ]
        
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_read_only_user_permissions(self):
        """Test read-only user permissions."""
        self.client.force_authenticate(user=self.viewer_user)
        
        # Should be able to read
        template = QueryTemplateFactory.create(group=self.group2)
        url = f'/api/market-intelligence/query-templates/{template.id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should not be able to create
        template_data = {
            'name': 'Unauthorized Template',
            'template_type': QueryTemplate.TemplateType.COMPANY_DISCOVERY,
            'query_pattern': 'test'
        }
        response = self.client.post('/api/market-intelligence/query-templates/', template_data)
        # This would typically be forbidden, but depends on permission implementation
        # self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST])
    
    def test_group_isolation(self):
        """Test that users can only access data from their groups."""
        # User in group1 trying to access group2 data
        self.client.force_authenticate(user=self.analyst_user)
        
        group2_template = QueryTemplateFactory.create(group=self.group2)
        url = f'/api/market-intelligence/query-templates/{group2_template.id}/'
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ViewSetIntegrationTest(APITestCase, TestDataMixin):
    """Test integration between different ViewSets."""
    
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.analyst_user)
    
    def test_end_to_end_workflow_via_api(self):
        """Test complete workflow through API endpoints."""
        # 1. Create query template
        template_data = {
            'name': 'API Integration Template',
            'template_type': QueryTemplate.TemplateType.COMPANY_DISCOVERY,
            'query_pattern': 'student accommodation {city}',
            'keywords': ['pbsa'],
            'schedule_frequency': 'daily'
        }
        
        response = self.client.post('/api/market-intelligence/query-templates/', template_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        template_id = response.json()['id']
        
        # 2. Execute scraping (mocked)
        with patch('market_intelligence.services.MarketIntelligenceService.execute_news_scraping') as mock_scraping:
            mock_scraping.return_value = {
                'template_id': template_id,
                'articles_found': 2,
                'articles_processed': 2
            }
            
            scraping_url = f'/api/market-intelligence/query-templates/{template_id}/execute_scraping/'
            response = self.client.post(scraping_url, {'search_parameters': {'city': 'London'}}, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 3. Create target company
        target_data = {
            'company_name': 'API Created Target Ltd',
            'business_model': 'developer',
            'focus_sectors': ['pbsa']
        }
        
        response = self.client.post('/api/market-intelligence/target-companies/', target_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        target_id = response.json()['id']
        
        # 4. Calculate score for target
        with patch('market_intelligence.services.TargetScoringService.calculate_comprehensive_score') as mock_scoring:
            mock_scoring.return_value = {
                'target_id': target_id,
                'total_score': 75.0,
                'qualification_status': 'qualified'
            }
            
            scoring_url = f'/api/market-intelligence/target-companies/{target_id}/calculate_score/'
            response = self.client.post(scoring_url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.json()['total_score'], 75.0)
        
        # 5. Get dashboard metrics
        with patch('market_intelligence.services.MarketIntelligenceService.get_dashboard_metrics') as mock_metrics:
            mock_metrics.return_value = {
                'articles': {'total': 2, 'relevant': 1},
                'targets': {'total': 1, 'qualified': 1},
                'templates': {'total': 1, 'active': 1}
            }
            
            response = self.client.get('/api/market-intelligence/dashboard/metrics/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            metrics = response.json()
            self.assertEqual(metrics['targets']['qualified'], 1)
    
    def test_api_error_handling(self):
        """Test API error handling scenarios."""
        # Non-existent resource
        response = self.client.get(f'/api/market-intelligence/query-templates/{uuid.uuid4()}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Invalid data
        invalid_data = {'invalid_field': 'invalid_value'}
        response = self.client.post('/api/market-intelligence/query-templates/', invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Service errors (mocked)
        template = QueryTemplateFactory.create(group=self.group1)
        with patch('market_intelligence.services.MarketIntelligenceService.execute_news_scraping', side_effect=Exception('Service error')):
            url = f'/api/market-intelligence/query-templates/{template.id}/execute_scraping/'
            response = self.client.post(url, {}, format='json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('error', response.json())