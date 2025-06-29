"""
Test data factories for market intelligence models.

Provides factory classes for creating test data using Django's testing framework.
Follows the factory pattern to create realistic test data consistently.
"""

import uuid
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model

from accounts.models import Group
from ..models import QueryTemplate, NewsArticle, TargetCompany

User = get_user_model()


class MarketIntelligenceFactoryMixin:
    """Mixin providing common factory methods for market intelligence tests."""
    
    @classmethod
    def create_test_group(cls, name="Test Group"):
        """Create a test group for multi-tenant testing."""
        return Group.objects.create(name=name, description="Test group for market intelligence")
    
    @classmethod
    def create_test_user(cls, role=User.Role.BUSINESS_ANALYST, email="test@example.com"):
        """Create a test user with specified role."""
        return User.objects.create_user(
            username=email.split('@')[0],
            email=email,
            password="testpass123",
            role=role
        )


class QueryTemplateFactory(MarketIntelligenceFactoryMixin):
    """Factory for creating QueryTemplate test instances."""
    
    @classmethod
    def create(cls, group=None, **kwargs):
        """Create a QueryTemplate with default values."""
        if group is None:
            group = cls.create_test_group()
        
        defaults = {
            'name': 'Test PBSA Discovery Template',
            'description': 'Template for discovering PBSA investment opportunities',
            'template_type': QueryTemplate.TemplateType.COMPANY_DISCOVERY,
            'query_pattern': 'student accommodation development {region}',
            'keywords': ['pbsa', 'student accommodation', 'student housing'],
            'excluded_keywords': ['dormitory'],
            'regions': ['UK', 'Ireland'],
            'languages': ['en'],
            'is_active': True,
            'schedule_frequency': 'daily'
        }
        defaults.update(kwargs)
        
        return QueryTemplate.objects.create(group=group, **defaults)
    
    @classmethod
    def create_batch(cls, size=3, group=None, **kwargs):
        """Create multiple QueryTemplate instances."""
        if group is None:
            group = cls.create_test_group()
        
        templates = []
        for i in range(size):
            template_kwargs = kwargs.copy()
            template_kwargs['name'] = f"Test Template {i+1}"
            templates.append(cls.create(group=group, **template_kwargs))
        return templates
    
    @classmethod
    def create_funding_template(cls, group=None):
        """Create a template specifically for funding announcements."""
        return cls.create(
            group=group,
            name='Funding Announcement Template',
            template_type=QueryTemplate.TemplateType.FUNDING_ANNOUNCEMENT,
            query_pattern='real estate funding series {round}',
            keywords=['funding', 'investment', 'series a', 'series b'],
            excluded_keywords=['cryptocurrency']
        )
    
    @classmethod
    def create_inactive_template(cls, group=None):
        """Create an inactive template for testing."""
        return cls.create(
            group=group,
            name='Inactive Template',
            is_active=False
        )


class NewsArticleFactory(MarketIntelligenceFactoryMixin):
    """Factory for creating NewsArticle test instances."""
    
    @classmethod
    def create(cls, group=None, query_template=None, **kwargs):
        """Create a NewsArticle with default values."""
        if group is None:
            group = cls.create_test_group()
        
        if query_template is None:
            query_template = QueryTemplateFactory.create(group=group)
        
        defaults = {
            'title': 'Major PBSA Development Announced in London',
            'content': '''
            A significant purpose-built student accommodation development has been announced 
            in central London. The project will deliver 500 new student beds across a 
            10-story building. The development is being led by a major property developer 
            with extensive experience in the PBSA sector. The scheme is expected to open 
            in September 2025 and will target international students. The investment 
            represents a commitment of £50 million to the London student housing market.
            ''',
            'summary': 'Major 500-bed PBSA development announced in London with £50M investment.',
            'url': f'https://example.com/news/pbsa-london-{uuid.uuid4().hex[:8]}',
            'published_date': timezone.now() - timedelta(hours=2),
            'source': 'Property Week',
            'author': 'Jane Smith',
            'language': 'en',
            'status': NewsArticle.ArticleStatus.ANALYZED,
            'relevance_score': 0.85,
            'sentiment_score': 0.3,
            'entities_extracted': {
                'companies': ['London Student Properties Ltd'],
                'people': ['John Doe'],
                'locations': ['London', 'Central London'],
                'monetary_amounts': ['50 million'],
                'universities': []
            },
            'topics': ['property_development', 'student_housing', 'funding_investment'],
            'search_keywords': ['pbsa', 'student accommodation']
        }
        defaults.update(kwargs)
        
        return NewsArticle.objects.create(
            group=group,
            query_template=query_template,
            **defaults
        )
    
    @classmethod
    def create_batch(cls, size=5, group=None, **kwargs):
        """Create multiple NewsArticle instances."""
        if group is None:
            group = cls.create_test_group()
        
        articles = []
        for i in range(size):
            article_kwargs = kwargs.copy()
            article_kwargs['title'] = f"News Article {i+1}"
            article_kwargs['url'] = f"https://example.com/news/article-{i+1}-{uuid.uuid4().hex[:8]}"
            articles.append(cls.create(group=group, **article_kwargs))
        return articles
    
    @classmethod
    def create_relevant_article(cls, group=None):
        """Create a highly relevant article."""
        return cls.create(
            group=group,
            title='£100M PBSA Portfolio Acquisition Completed',
            content='''
            A major real estate investment fund has completed the acquisition of a 
            £100 million PBSA portfolio comprising 2,000 student beds across five 
            UK universities. The portfolio includes properties in Manchester, 
            Birmingham, and Leeds. This acquisition represents the fund's largest 
            investment in the student accommodation sector to date.
            ''',
            relevance_score=0.95,
            sentiment_score=0.7,
            status=NewsArticle.ArticleStatus.RELEVANT
        )
    
    @classmethod
    def create_irrelevant_article(cls, group=None):
        """Create an irrelevant article."""
        return cls.create(
            group=group,
            title='Local Restaurant Opens New Location',
            content='''
            A popular local restaurant chain has opened its fifth location in the 
            city center. The new restaurant features an expanded menu and modern 
            interior design. The opening is expected to create 20 new jobs.
            ''',
            relevance_score=0.1,
            sentiment_score=0.1,
            status=NewsArticle.ArticleStatus.IRRELEVANT,
            topics=['hospitality', 'local_business']
        )
    
    @classmethod
    def create_pending_article(cls, group=None):
        """Create an article pending analysis."""
        return cls.create(
            group=group,
            title='Pending Analysis Article',
            status=NewsArticle.ArticleStatus.PENDING,
            relevance_score=0.0,
            sentiment_score=None,
            entities_extracted={},
            topics=[]
        )


class TargetCompanyFactory(MarketIntelligenceFactoryMixin):
    """Factory for creating TargetCompany test instances."""
    
    @classmethod
    def create(cls, group=None, identified_by=None, **kwargs):
        """Create a TargetCompany with default values."""
        if group is None:
            group = cls.create_test_group()
        
        if identified_by is None:
            identified_by = cls.create_test_user()
        
        defaults = {
            'company_name': 'Urban Student Properties Ltd',
            'trading_name': 'Urban Student',
            'domain': 'https://urbanstudent.com',
            'linkedin_url': 'https://linkedin.com/company/urban-student',
            'description': '''
            Urban Student Properties is a leading UK developer and operator of 
            purpose-built student accommodation. With over 15 years of experience, 
            the company has delivered more than 10,000 student beds across major 
            university cities including London, Manchester, and Edinburgh.
            ''',
            'headquarters_city': 'London',
            'headquarters_country': 'GB',
            'company_size': TargetCompany.CompanySize.MEDIUM,
            'employee_count': 250,
            'business_model': 'developer',
            'focus_sectors': ['pbsa', 'residential'],
            'geographic_focus': ['UK', 'Ireland'],
            'status': TargetCompany.TargetStatus.IDENTIFIED,
            'lead_score': 75.0,
            'qualification_notes': 'Strong PBSA focus with proven track record in UK market.'
        }
        defaults.update(kwargs)
        
        return TargetCompany.objects.create(
            group=group,
            identified_by=identified_by,
            **defaults
        )
    
    @classmethod
    def create_batch(cls, size=3, group=None, **kwargs):
        """Create multiple TargetCompany instances."""
        if group is None:
            group = cls.create_test_group()
        
        companies = []
        for i in range(size):
            company_kwargs = kwargs.copy()
            company_kwargs['company_name'] = f"Test Company {i+1} Ltd"
            company_kwargs['domain'] = f"https://testcompany{i+1}.com"
            companies.append(cls.create(group=group, **company_kwargs))
        return companies
    
    @classmethod
    def create_qualified_target(cls, group=None):
        """Create a highly qualified target company."""
        return cls.create(
            group=group,
            company_name='Premier PBSA Developments Plc',
            business_model='developer',
            focus_sectors=['pbsa'],
            employee_count=500,
            company_size=TargetCompany.CompanySize.LARGE,
            lead_score=90.0,
            status=TargetCompany.TargetStatus.QUALIFIED
        )
    
    @classmethod
    def create_startup_target(cls, group=None):
        """Create a startup target company."""
        return cls.create(
            group=group,
            company_name='PropTech Student Solutions',
            business_model='platform',
            focus_sectors=['pbsa', 'proptech'],
            employee_count=25,
            company_size=TargetCompany.CompanySize.STARTUP,
            lead_score=45.0,
            status=TargetCompany.TargetStatus.RESEARCHING
        )
    
    @classmethod
    def create_converted_target(cls, group=None):
        """Create a target that has been converted to a development partner."""
        return cls.create(
            group=group,
            company_name='Converted PBSA Partner Ltd',
            status=TargetCompany.TargetStatus.CONVERTED,
            lead_score=85.0,
            converted_at=timezone.now() - timedelta(days=30)
        )
    
    @classmethod
    def create_with_articles(cls, group=None, article_count=3):
        """Create a target company with associated news articles."""
        target = cls.create(group=group)
        
        articles = []
        for i in range(article_count):
            article = NewsArticleFactory.create(
                group=group,
                title=f"News about {target.company_name} - Article {i+1}",
                content=f"This article mentions {target.company_name} in relation to student accommodation development."
            )
            articles.append(article)
        
        # Associate articles with target
        target.source_articles.set(articles)
        
        # Recalculate lead score based on articles
        target.lead_score = target.calculate_lead_score()
        target.save()
        
        return target


class TestDataMixin:
    """Mixin providing comprehensive test data setup for test cases."""
    
    def setUp(self):
        """Set up comprehensive test data."""
        # Create groups
        self.group1 = Group.objects.create(name="Test Group 1")
        self.group2 = Group.objects.create(name="Test Group 2")
        
        # Create users with different roles
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role=User.Role.ADMIN
        )
        
        self.analyst_user = User.objects.create_user(
            username="analyst",
            email="analyst@example.com",
            password="testpass123",
            role=User.Role.BUSINESS_ANALYST
        )
        
        self.manager_user = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="testpass123",
            role=User.Role.PORTFOLIO_MANAGER
        )
        
        self.viewer_user = User.objects.create_user(
            username="viewer",
            email="viewer@example.com",
            password="testpass123",
            role=User.Role.READ_ONLY
        )
        
        # Add users to groups
        self.group1.members.add(self.admin_user, self.analyst_user, self.manager_user)
        self.group2.members.add(self.viewer_user)
        
        # Create test data
        self.query_template = QueryTemplateFactory.create(group=self.group1)
        self.news_article = NewsArticleFactory.create(
            group=self.group1,
            query_template=self.query_template
        )
        self.target_company = TargetCompanyFactory.create(
            group=self.group1,
            identified_by=self.analyst_user
        )
        
        # Associate article with target
        self.target_company.source_articles.add(self.news_article)
    
    def create_sample_data_set(self, group=None):
        """Create a comprehensive sample data set for testing."""
        if group is None:
            group = self.group1
        
        # Create multiple templates
        templates = QueryTemplateFactory.create_batch(3, group=group)
        
        # Create articles with different statuses
        relevant_articles = [
            NewsArticleFactory.create_relevant_article(group=group)
            for _ in range(3)
        ]
        irrelevant_articles = [
            NewsArticleFactory.create_irrelevant_article(group=group)
            for _ in range(2)
        ]
        pending_articles = [
            NewsArticleFactory.create_pending_article(group=group)
            for _ in range(2)
        ]
        
        # Create target companies with different profiles
        qualified_targets = [
            TargetCompanyFactory.create_qualified_target(group=group)
            for _ in range(2)
        ]
        startup_targets = [
            TargetCompanyFactory.create_startup_target(group=group)
            for _ in range(2)
        ]
        
        return {
            'templates': templates,
            'articles': {
                'relevant': relevant_articles,
                'irrelevant': irrelevant_articles,
                'pending': pending_articles
            },
            'targets': {
                'qualified': qualified_targets,
                'startups': startup_targets
            }
        }