"""
Comprehensive tests for market intelligence models.

Tests all model functionality including validation, properties, methods,
and business logic to ensure 95%+ code coverage.
"""

import hashlib
from datetime import datetime, timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from django.contrib.auth import get_user_model

from accounts.models import Group
from ..models import QueryTemplate, NewsArticle, TargetCompany
from .factories import (
    QueryTemplateFactory, NewsArticleFactory, TargetCompanyFactory, TestDataMixin
)

User = get_user_model()


class QueryTemplateModelTest(TestCase, TestDataMixin):
    """Test QueryTemplate model functionality."""
    
    def setUp(self):
        super().setUp()
    
    def test_query_template_creation(self):
        """Test basic query template creation."""
        template = QueryTemplateFactory.create(group=self.group1)
        
        self.assertIsNotNone(template.id)
        self.assertEqual(template.group, self.group1)
        self.assertTrue(template.is_active)
        self.assertIsNotNone(template.created_at)
        self.assertIsNotNone(template.updated_at)
    
    def test_query_template_str_representation(self):
        """Test string representation of query template."""
        template = QueryTemplateFactory.create(
            group=self.group1,
            name="Test Template",
            template_type=QueryTemplate.TemplateType.COMPANY_DISCOVERY
        )
        
        expected = "Test Template (company_discovery)"
        self.assertEqual(str(template), expected)
    
    def test_unique_name_per_group(self):
        """Test that template names must be unique within a group."""
        QueryTemplateFactory.create(
            group=self.group1,
            name="Unique Template"
        )
        
        # Should raise IntegrityError for duplicate name in same group
        with self.assertRaises(IntegrityError):
            QueryTemplateFactory.create(
                group=self.group1,
                name="Unique Template"
            )
    
    def test_same_name_different_groups(self):
        """Test that same template name can exist in different groups."""
        template1 = QueryTemplateFactory.create(
            group=self.group1,
            name="Template Name"
        )
        template2 = QueryTemplateFactory.create(
            group=self.group2,
            name="Template Name"
        )
        
        self.assertEqual(template1.name, template2.name)
        self.assertNotEqual(template1.group, template2.group)
    
    def test_generate_search_query_basic(self):
        """Test basic search query generation."""
        template = QueryTemplateFactory.create(
            group=self.group1,
            query_pattern="student accommodation in {city}",
            keywords=["pbsa", "student housing"],
            excluded_keywords=["dormitory"]
        )
        
        query = template.generate_search_query(city="London")
        
        self.assertIn("student accommodation in London", query)
        self.assertIn('("pbsa" OR "student housing")', query)
        self.assertIn('-"dormitory"', query)
    
    def test_generate_search_query_no_parameters(self):
        """Test search query generation without parameters."""
        template = QueryTemplateFactory.create(
            group=self.group1,
            query_pattern="student accommodation development",
            keywords=["pbsa"],
            excluded_keywords=[]
        )
        
        query = template.generate_search_query()
        
        self.assertIn("student accommodation development", query)
        self.assertIn('"pbsa"', query)
        self.assertNotIn("-", query)  # No exclusions
    
    def test_generate_search_query_empty_keywords(self):
        """Test search query generation with empty keywords."""
        template = QueryTemplateFactory.create(
            group=self.group1,
            query_pattern="test query",
            keywords=[],
            excluded_keywords=[]
        )
        
        query = template.generate_search_query()
        
        self.assertEqual(query, "test query")
    
    def test_template_type_choices(self):
        """Test all template type choices are valid."""
        for choice_value, choice_label in QueryTemplate.TemplateType.choices:
            template = QueryTemplateFactory.create(
                group=self.group1,
                template_type=choice_value
            )
            self.assertEqual(template.template_type, choice_value)
    
    def test_schedule_frequency_choices(self):
        """Test schedule frequency validation."""
        valid_frequencies = ['daily', 'weekly', 'monthly']
        
        for frequency in valid_frequencies:
            template = QueryTemplateFactory.create(
                group=self.group1,
                schedule_frequency=frequency
            )
            self.assertEqual(template.schedule_frequency, frequency)
    
    def test_keywords_json_field(self):
        """Test keywords JSON field functionality."""
        keywords = ["pbsa", "student accommodation", "university housing"]
        template = QueryTemplateFactory.create(
            group=self.group1,
            keywords=keywords
        )
        
        self.assertEqual(template.keywords, keywords)
        self.assertIsInstance(template.keywords, list)
    
    def test_regions_json_field(self):
        """Test regions JSON field functionality."""
        regions = ["UK", "Ireland", "Netherlands"]
        template = QueryTemplateFactory.create(
            group=self.group1,
            regions=regions
        )
        
        self.assertEqual(template.regions, regions)
        self.assertIsInstance(template.regions, list)
    
    def test_last_executed_field(self):
        """Test last_executed field updates."""
        template = QueryTemplateFactory.create(group=self.group1)
        self.assertIsNone(template.last_executed)
        
        # Update last_executed
        now = timezone.now()
        template.last_executed = now
        template.save()
        
        template.refresh_from_db()
        self.assertEqual(template.last_executed, now)


class NewsArticleModelTest(TestCase, TestDataMixin):
    """Test NewsArticle model functionality."""
    
    def setUp(self):
        super().setUp()
    
    def test_news_article_creation(self):
        """Test basic news article creation."""
        article = NewsArticleFactory.create(group=self.group1)
        
        self.assertIsNotNone(article.id)
        self.assertEqual(article.group, self.group1)
        self.assertIsNotNone(article.content_hash)
        self.assertIsNotNone(article.created_at)
        self.assertIsNotNone(article.updated_at)
    
    def test_news_article_str_representation(self):
        """Test string representation of news article."""
        article = NewsArticleFactory.create(
            group=self.group1,
            title="This is a very long title that should be truncated in the string representation",
            source="Test Source"
        )
        
        str_repr = str(article)
        self.assertIn("Test Source", str_repr)
        self.assertTrue(len(str_repr) <= 150)  # Should be truncated
    
    def test_content_hash_generation(self):
        """Test automatic content hash generation on save."""
        content = "This is test article content."
        article = NewsArticleFactory.create(
            group=self.group1,
            content=content
        )
        
        expected_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        self.assertEqual(article.content_hash, expected_hash)
    
    def test_content_hash_uniqueness(self):
        """Test that content hash enforces uniqueness."""
        content = "Duplicate content for testing."
        
        NewsArticleFactory.create(group=self.group1, content=content)
        
        # Should raise IntegrityError for duplicate content hash
        with self.assertRaises(IntegrityError):
            NewsArticleFactory.create(group=self.group1, content=content)
    
    def test_url_uniqueness(self):
        """Test that URL must be unique."""
        url = "https://example.com/unique-article"
        
        NewsArticleFactory.create(group=self.group1, url=url)
        
        # Should raise IntegrityError for duplicate URL
        with self.assertRaises(IntegrityError):
            NewsArticleFactory.create(group=self.group1, url=url)
    
    def test_is_relevant_property(self):
        """Test is_relevant property calculation."""
        # High relevance score
        relevant_article = NewsArticleFactory.create(
            group=self.group1,
            relevance_score=0.8
        )
        self.assertTrue(relevant_article.is_relevant)
        
        # Low relevance score
        irrelevant_article = NewsArticleFactory.create(
            group=self.group1,
            relevance_score=0.5
        )
        self.assertFalse(irrelevant_article.is_relevant)
        
        # Boundary case
        boundary_article = NewsArticleFactory.create(
            group=self.group1,
            relevance_score=0.7
        )
        self.assertTrue(boundary_article.is_relevant)
    
    def test_word_count_property(self):
        """Test word count calculation."""
        content = "This is a test article with exactly ten words here."
        article = NewsArticleFactory.create(
            group=self.group1,
            content=content
        )
        
        self.assertEqual(article.word_count, 10)
    
    def test_word_count_empty_content(self):
        """Test word count with empty content."""
        article = NewsArticleFactory.create(
            group=self.group1,
            content=""
        )
        
        self.assertEqual(article.word_count, 0)
    
    def test_article_status_choices(self):
        """Test all article status choices are valid."""
        for choice_value, choice_label in NewsArticle.ArticleStatus.choices:
            article = NewsArticleFactory.create(
                group=self.group1,
                status=choice_value
            )
            self.assertEqual(article.status, choice_value)
    
    def test_relevance_score_validation(self):
        """Test relevance score validation range."""
        # Valid scores
        for score in [0.0, 0.5, 1.0]:
            article = NewsArticleFactory.create(
                group=self.group1,
                relevance_score=score
            )
            self.assertEqual(article.relevance_score, score)
    
    def test_sentiment_score_validation(self):
        """Test sentiment score validation range."""
        # Valid scores
        for score in [-1.0, 0.0, 1.0]:
            article = NewsArticleFactory.create(
                group=self.group1,
                sentiment_score=score
            )
            self.assertEqual(article.sentiment_score, score)
    
    def test_entities_extracted_json_field(self):
        """Test entities_extracted JSON field."""
        entities = {
            'companies': ['Test Company Ltd'],
            'people': ['John Doe'],
            'locations': ['London'],
            'amounts': ['£10 million']
        }
        
        article = NewsArticleFactory.create(
            group=self.group1,
            entities_extracted=entities
        )
        
        self.assertEqual(article.entities_extracted, entities)
        self.assertIsInstance(article.entities_extracted, dict)
    
    def test_topics_json_field(self):
        """Test topics JSON field."""
        topics = ['property_development', 'funding', 'pbsa']
        
        article = NewsArticleFactory.create(
            group=self.group1,
            topics=topics
        )
        
        self.assertEqual(article.topics, topics)
        self.assertIsInstance(article.topics, list)
    
    def test_query_template_relationship(self):
        """Test relationship with QueryTemplate."""
        template = QueryTemplateFactory.create(group=self.group1)
        article = NewsArticleFactory.create(
            group=self.group1,
            query_template=template
        )
        
        self.assertEqual(article.query_template, template)
    
    def test_ordering(self):
        """Test default ordering by published_date descending."""
        # Create articles with different published dates
        old_article = NewsArticleFactory.create(
            group=self.group1,
            published_date=timezone.now() - timedelta(days=2)
        )
        new_article = NewsArticleFactory.create(
            group=self.group1,
            published_date=timezone.now()
        )
        
        articles = list(NewsArticle.objects.all())
        self.assertEqual(articles[0], new_article)  # Newest first
        self.assertEqual(articles[1], old_article)


class TargetCompanyModelTest(TestCase, TestDataMixin):
    """Test TargetCompany model functionality."""
    
    def setUp(self):
        super().setUp()
    
    def test_target_company_creation(self):
        """Test basic target company creation."""
        target = TargetCompanyFactory.create(
            group=self.group1,
            identified_by=self.analyst_user
        )
        
        self.assertIsNotNone(target.id)
        self.assertEqual(target.group, self.group1)
        self.assertEqual(target.identified_by, self.analyst_user)
        self.assertIsNotNone(target.created_at)
        self.assertIsNotNone(target.updated_at)
    
    def test_target_company_str_representation(self):
        """Test string representation of target company."""
        target = TargetCompanyFactory.create(
            group=self.group1,
            company_name="Test Company Ltd",
            status=TargetCompany.TargetStatus.QUALIFIED
        )
        
        expected = "Test Company Ltd (qualified)"
        self.assertEqual(str(target), expected)
    
    def test_unique_company_name_per_group(self):
        """Test that company names must be unique within a group."""
        TargetCompanyFactory.create(
            group=self.group1,
            company_name="Unique Company Ltd"
        )
        
        # Should raise IntegrityError for duplicate name in same group
        with self.assertRaises(IntegrityError):
            TargetCompanyFactory.create(
                group=self.group1,
                company_name="Unique Company Ltd"
            )
    
    def test_same_company_name_different_groups(self):
        """Test that same company name can exist in different groups."""
        target1 = TargetCompanyFactory.create(
            group=self.group1,
            company_name="Company Name Ltd"
        )
        target2 = TargetCompanyFactory.create(
            group=self.group2,
            company_name="Company Name Ltd"
        )
        
        self.assertEqual(target1.company_name, target2.company_name)
        self.assertNotEqual(target1.group, target2.group)
    
    def test_is_qualified_property(self):
        """Test is_qualified property calculation."""
        # High scoring target
        qualified_target = TargetCompanyFactory.create(
            group=self.group1,
            lead_score=75.0
        )
        self.assertTrue(qualified_target.is_qualified)
        
        # Low scoring target
        unqualified_target = TargetCompanyFactory.create(
            group=self.group1,
            lead_score=65.0
        )
        self.assertFalse(unqualified_target.is_qualified)
        
        # Boundary case
        boundary_target = TargetCompanyFactory.create(
            group=self.group1,
            lead_score=70.0
        )
        self.assertTrue(boundary_target.is_qualified)
    
    def test_days_since_identification_property(self):
        """Test days_since_identification calculation."""
        # Create target with specific creation date
        past_date = timezone.now() - timedelta(days=5)
        target = TargetCompanyFactory.create(group=self.group1)
        target.created_at = past_date
        target.save()
        
        self.assertEqual(target.days_since_identification, 5)
    
    def test_calculate_lead_score_basic(self):
        """Test basic lead score calculation."""
        target = TargetCompanyFactory.create(
            group=self.group1,
            domain="https://example.com",
            linkedin_url="https://linkedin.com/company/example",
            description="A PBSA development company",
            business_model="developer",
            focus_sectors=["pbsa"]
        )
        
        score = target.calculate_lead_score()
        
        # Should get points for domain (10), linkedin (10), description (10),
        # developer business model (20), and PBSA focus (30)
        expected_minimum = 80.0
        self.assertGreaterEqual(score, expected_minimum)
        self.assertLessEqual(score, 100.0)
    
    def test_calculate_lead_score_with_articles(self):
        """Test lead score calculation with news articles."""
        target = TargetCompanyFactory.create_with_articles(
            group=self.group1,
            article_count=5
        )
        
        score = target.calculate_lead_score()
        
        # Should get bonus points for recent articles (up to 20 points)
        # 5 articles × 5 points = 20 points (capped at 20)
        self.assertGreater(score, 0)
    
    def test_calculate_lead_score_minimum_data(self):
        """Test lead score calculation with minimal data."""
        target = TargetCompanyFactory.create(
            group=self.group1,
            domain="",
            linkedin_url="",
            description="",
            business_model="other",
            focus_sectors=[]
        )
        
        score = target.calculate_lead_score()
        
        # Should get minimal score (5 points for 'other' business model)
        self.assertEqual(score, 5.0)
    
    def test_target_status_choices(self):
        """Test all target status choices are valid."""
        for choice_value, choice_label in TargetCompany.TargetStatus.choices:
            target = TargetCompanyFactory.create(
                group=self.group1,
                status=choice_value
            )
            self.assertEqual(target.status, choice_value)
    
    def test_company_size_choices(self):
        """Test all company size choices are valid."""
        for choice_value, choice_label in TargetCompany.CompanySize.choices:
            target = TargetCompanyFactory.create(
                group=self.group1,
                company_size=choice_value
            )
            self.assertEqual(target.company_size, choice_value)
    
    def test_business_model_choices(self):
        """Test business model choices."""
        valid_models = ['developer', 'investor', 'operator', 'platform', 'service', 'other']
        
        for model in valid_models:
            target = TargetCompanyFactory.create(
                group=self.group1,
                business_model=model
            )
            self.assertEqual(target.business_model, model)
    
    def test_lead_score_validation(self):
        """Test lead score validation range."""
        # Valid scores
        for score in [0.0, 50.0, 100.0]:
            target = TargetCompanyFactory.create(
                group=self.group1,
                lead_score=score
            )
            self.assertEqual(target.lead_score, score)
    
    def test_employee_count_validation(self):
        """Test employee count validation."""
        # Valid employee counts
        target = TargetCompanyFactory.create(
            group=self.group1,
            employee_count=100
        )
        self.assertEqual(target.employee_count, 100)
        
        # None should be allowed
        target_none = TargetCompanyFactory.create(
            group=self.group1,
            employee_count=None
        )
        self.assertIsNone(target_none.employee_count)
    
    def test_focus_sectors_json_field(self):
        """Test focus_sectors JSON field."""
        sectors = ['pbsa', 'residential', 'commercial']
        target = TargetCompanyFactory.create(
            group=self.group1,
            focus_sectors=sectors
        )
        
        self.assertEqual(target.focus_sectors, sectors)
        self.assertIsInstance(target.focus_sectors, list)
    
    def test_geographic_focus_json_field(self):
        """Test geographic_focus JSON field."""
        regions = ['UK', 'Ireland', 'Netherlands']
        target = TargetCompanyFactory.create(
            group=self.group1,
            geographic_focus=regions
        )
        
        self.assertEqual(target.geographic_focus, regions)
        self.assertIsInstance(target.geographic_focus, list)
    
    def test_enrichment_data_json_field(self):
        """Test enrichment_data JSON field."""
        enrichment = {
            'linkedin_followers': 1000,
            'company_funding': '£10M Series A',
            'key_personnel': ['CEO: John Doe', 'CTO: Jane Smith']
        }
        
        target = TargetCompanyFactory.create(
            group=self.group1,
            enrichment_data=enrichment
        )
        
        self.assertEqual(target.enrichment_data, enrichment)
        self.assertIsInstance(target.enrichment_data, dict)
    
    def test_source_articles_relationship(self):
        """Test many-to-many relationship with NewsArticle."""
        target = TargetCompanyFactory.create(group=self.group1)
        articles = NewsArticleFactory.create_batch(3, group=self.group1)
        
        target.source_articles.set(articles)
        
        self.assertEqual(target.source_articles.count(), 3)
        for article in articles:
            self.assertIn(article, target.source_articles.all())
    
    def test_identified_by_relationship(self):
        """Test relationship with identifying user."""
        target = TargetCompanyFactory.create(
            group=self.group1,
            identified_by=self.analyst_user
        )
        
        self.assertEqual(target.identified_by, self.analyst_user)
    
    def test_assigned_analyst_relationship(self):
        """Test relationship with assigned analyst."""
        target = TargetCompanyFactory.create(
            group=self.group1,
            assigned_analyst=self.analyst_user
        )
        
        self.assertEqual(target.assigned_analyst, self.analyst_user)
    
    def test_ordering(self):
        """Test default ordering by lead_score descending, then created_at descending."""
        # Create targets with different scores
        low_score_target = TargetCompanyFactory.create(
            group=self.group1,
            lead_score=30.0
        )
        high_score_target = TargetCompanyFactory.create(
            group=self.group1,
            lead_score=90.0
        )
        
        targets = list(TargetCompany.objects.all())
        self.assertEqual(targets[0], high_score_target)  # Highest score first
        
    def test_conversion_tracking(self):
        """Test conversion tracking fields."""
        converted_target = TargetCompanyFactory.create_converted_target(
            group=self.group1
        )
        
        self.assertEqual(converted_target.status, TargetCompany.TargetStatus.CONVERTED)
        self.assertIsNotNone(converted_target.converted_at)


class ModelIntegrationTest(TestCase, TestDataMixin):
    """Test integration between different models."""
    
    def setUp(self):
        super().setUp()
    
    def test_complete_workflow_integration(self):
        """Test complete workflow from template to target identification."""
        # Create query template
        template = QueryTemplateFactory.create(group=self.group1)
        
        # Create news article from template
        article = NewsArticleFactory.create(
            group=self.group1,
            query_template=template
        )
        
        # Create target company
        target = TargetCompanyFactory.create(
            group=self.group1,
            identified_by=self.analyst_user
        )
        
        # Link article to target
        target.source_articles.add(article)
        
        # Test relationships
        self.assertEqual(article.query_template, template)
        self.assertIn(article, target.source_articles.all())
        self.assertEqual(target.identified_by, self.analyst_user)
    
    def test_group_isolation(self):
        """Test that group-based isolation works correctly."""
        # Create data in group1
        template1 = QueryTemplateFactory.create(group=self.group1)
        article1 = NewsArticleFactory.create(group=self.group1)
        target1 = TargetCompanyFactory.create(group=self.group1)
        
        # Create data in group2
        template2 = QueryTemplateFactory.create(group=self.group2)
        article2 = NewsArticleFactory.create(group=self.group2)
        target2 = TargetCompanyFactory.create(group=self.group2)
        
        # Test group1 only sees its data
        group1_templates = QueryTemplate.objects.filter(group=self.group1)
        self.assertIn(template1, group1_templates)
        self.assertNotIn(template2, group1_templates)
        
        group1_articles = NewsArticle.objects.filter(group=self.group1)
        self.assertIn(article1, group1_articles)
        self.assertNotIn(article2, group1_articles)
        
        group1_targets = TargetCompany.objects.filter(group=self.group1)
        self.assertIn(target1, group1_targets)
        self.assertNotIn(target2, group1_targets)
    
    def test_cascade_deletion(self):
        """Test cascade deletion behavior."""
        template = QueryTemplateFactory.create(group=self.group1)
        article = NewsArticleFactory.create(
            group=self.group1,
            query_template=template
        )
        
        # Delete template - article should still exist but template reference should be None
        template.delete()
        article.refresh_from_db()
        self.assertIsNone(article.query_template)
        
        # Target should still exist when related user is deleted
        target = TargetCompanyFactory.create(
            group=self.group1,
            identified_by=self.analyst_user
        )
        user_id = self.analyst_user.id
        self.analyst_user.delete()
        
        target.refresh_from_db()
        # Should still exist but identified_by should be None due to SET_NULL
        self.assertIsNone(target.identified_by)