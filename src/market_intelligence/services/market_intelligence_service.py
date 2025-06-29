"""
Market Intelligence service for news scraping and target identification.

Handles the complete workflow from query template execution through
target company identification and lead scoring.
"""

import logging
import hashlib
import requests
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from django.db import transaction
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.core.exceptions import ValidationError

from accounts.models import User, Group
from assessments.services.base import BaseService, ValidationServiceError, PermissionServiceError, NotFoundServiceError
from ..models import QueryTemplate, NewsArticle, TargetCompany


class MarketIntelligenceService(BaseService):
    """
    Core service for market intelligence operations.
    
    Handles news scraping, article analysis, and target identification
    following the established service layer architecture.
    """
    
    def __init__(self, user: Optional[User] = None, group: Optional[Group] = None):
        """Initialize with user context for permissions and logging."""
        super().__init__(user, group)
        self.logger = logging.getLogger(__name__)
    
    def create_query_template(self, template_data: Dict[str, Any]) -> QueryTemplate:
        """
        Create a new query template for news scraping.
        
        Args:
            template_data: Template configuration data
            
        Returns:
            Created QueryTemplate instance
            
        Raises:
            ValidationServiceError: If template data is invalid
            PermissionServiceError: If user lacks permission
        """
        self._check_permission('create_query_template')
        self._log_operation("create_query_template", {"name": template_data.get('name')})
        
        if not self.group:
            raise ValidationServiceError("Group context required")
        
        # Validate required fields
        required_fields = ['name', 'query_pattern', 'template_type']
        for field in required_fields:
            if not template_data.get(field):
                raise ValidationServiceError(f"Field '{field}' is required")
        
        def _create_template():
            template = QueryTemplate(
                group=self.group,
                name=template_data['name'],
                description=template_data.get('description', ''),
                template_type=template_data['template_type'],
                query_pattern=template_data['query_pattern'],
                keywords=template_data.get('keywords', []),
                excluded_keywords=template_data.get('excluded_keywords', []),
                regions=template_data.get('regions', []),
                languages=template_data.get('languages', ['en']),
                schedule_frequency=template_data.get('schedule_frequency', 'daily')
            )
            template.save()
            return template
        
        return self._execute_with_transaction(_create_template)
    
    def execute_news_scraping(self, template_id: str, **kwargs) -> Dict[str, Any]:
        """
        Execute news scraping using a query template.
        
        Args:
            template_id: ID of the query template to use
            **kwargs: Additional parameters for query generation
            
        Returns:
            Dict with scraping results and statistics
            
        Raises:
            NotFoundServiceError: If template not found
            PermissionServiceError: If user lacks permission
        """
        self._check_permission('execute_news_scraping')
        self._log_operation("execute_news_scraping", {"template_id": template_id})
        
        try:
            template = QueryTemplate.objects.get(id=template_id, group=self.group)
        except QueryTemplate.DoesNotExist:
            raise NotFoundServiceError(f"Query template {template_id} not found")
        
        if not template.is_active:
            raise ValidationServiceError("Query template is not active")
        
        # Generate search query from template
        search_query = template.generate_search_query(**kwargs)
        
        # Execute scraping (this would integrate with external APIs)
        articles_found = self._scrape_articles(template, search_query)
        
        # Update template execution time
        template.last_executed = timezone.now()
        template.save()
        
        return {
            'template_id': template_id,
            'search_query': search_query,
            'articles_found': len(articles_found),
            'articles_processed': len([a for a in articles_found if a.status != NewsArticle.ArticleStatus.PENDING]),
            'execution_time': timezone.now().isoformat()
        }
    
    def _scrape_articles(self, template: QueryTemplate, search_query: str) -> List[NewsArticle]:
        """
        Internal method to scrape articles using external search APIs.
        
        This is a simplified implementation - in production this would
        integrate with services like Serper, Exa, or Bing Search API.
        """
        articles = []
        
        # Simulate API call (replace with actual implementation)
        mock_articles = self._simulate_news_api_response(search_query, template.regions)
        
        for article_data in mock_articles:
            try:
                # Check for duplicates using content hash
                content_hash = hashlib.sha256(
                    article_data['content'].encode('utf-8')
                ).hexdigest()
                
                if NewsArticle.objects.filter(content_hash=content_hash).exists():
                    continue
                
                article = NewsArticle(
                    group=self.group,
                    title=article_data['title'],
                    content=article_data['content'],
                    url=article_data['url'],
                    published_date=article_data['published_date'],
                    source=article_data['source'],
                    author=article_data.get('author', ''),
                    language=article_data.get('language', 'en'),
                    content_hash=content_hash,
                    query_template=template,
                    search_keywords=template.keywords
                )
                article.save()
                articles.append(article)
                
            except Exception as e:
                self.logger.error(f"Error processing article: {str(e)}")
                continue
        
        return articles
    
    def _simulate_news_api_response(self, query: str, regions: List[str]) -> List[Dict[str, Any]]:
        """
        Simulate news API response for testing purposes.
        
        In production, this would be replaced with actual API integration.
        """
        return [
            {
                'title': f'PBSA Development Announcement in {regions[0] if regions else "London"}',
                'content': f'A major student accommodation development has been announced. The project will deliver 500 new beds for students. This represents a significant investment in the {regions[0] if regions else "London"} student housing market.',
                'url': f'https://example.com/news/pbsa-development-{timezone.now().timestamp()}',
                'published_date': timezone.now() - timedelta(hours=2),
                'source': 'Property Week',
                'author': 'Jane Smith',
                'language': 'en'
            },
            {
                'title': 'PropTech Company Raises Series A Funding',
                'content': 'A property technology startup focused on student accommodation has raised £10M in Series A funding. The company plans to expand its platform for managing student housing operations.',
                'url': f'https://example.com/news/proptech-funding-{timezone.now().timestamp()}',
                'published_date': timezone.now() - timedelta(hours=5),
                'source': 'TechCrunch',
                'author': 'John Doe',
                'language': 'en'
            }
        ]
    
    def analyze_article_relevance(self, article_id: str) -> NewsArticle:
        """
        Analyze article relevance using NLP and scoring algorithms.
        
        Args:
            article_id: ID of the article to analyze
            
        Returns:
            Updated NewsArticle instance
            
        Raises:
            NotFoundServiceError: If article not found
            PermissionServiceError: If user lacks permission
        """
        self._check_permission('analyze_articles')
        self._log_operation("analyze_article_relevance", {"article_id": article_id})
        
        try:
            article = NewsArticle.objects.get(id=article_id, group=self.group)
        except NewsArticle.DoesNotExist:
            raise NotFoundServiceError(f"Article {article_id} not found")
        
        # Simplified relevance scoring (replace with actual NLP analysis)
        relevance_score = self._calculate_article_relevance(article)
        sentiment_score = self._analyze_sentiment(article.content)
        entities = self._extract_entities(article.content)
        topics = self._identify_topics(article.content)
        
        # Update article with analysis results
        article.relevance_score = relevance_score
        article.sentiment_score = sentiment_score
        article.entities_extracted = entities
        article.topics = topics
        article.status = (
            NewsArticle.ArticleStatus.RELEVANT if relevance_score >= 0.7
            else NewsArticle.ArticleStatus.IRRELEVANT
        )
        article.save()
        
        return article
    
    def _calculate_article_relevance(self, article: NewsArticle) -> float:
        """Calculate relevance score based on content analysis."""
        score = 0.0
        content_lower = article.content.lower()
        title_lower = article.title.lower()
        
        # PBSA-specific keywords
        pbsa_keywords = [
            'student accommodation', 'student housing', 'pbsa', 
            'purpose built student accommodation', 'student beds',
            'university housing', 'student residence'
        ]
        
        # Real estate investment keywords
        investment_keywords = [
            'investment', 'funding', 'acquisition', 'development',
            'portfolio', 'asset management', 'property fund'
        ]
        
        # Score based on keyword presence
        for keyword in pbsa_keywords:
            if keyword in content_lower:
                score += 0.3
            if keyword in title_lower:
                score += 0.2
        
        for keyword in investment_keywords:
            if keyword in content_lower:
                score += 0.1
            if keyword in title_lower:
                score += 0.1
        
        # Bonus for specific sources
        high_value_sources = ['property week', 'estates gazette', 'react news']
        if article.source.lower() in high_value_sources:
            score += 0.2
        
        return min(score, 1.0)
    
    def _analyze_sentiment(self, content: str) -> float:
        """Analyze sentiment of article content."""
        # Simplified sentiment analysis (replace with actual NLP)
        positive_words = ['growth', 'success', 'investment', 'expansion', 'opportunity']
        negative_words = ['decline', 'loss', 'problem', 'crisis', 'failure']
        
        content_lower = content.lower()
        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)
        
        if positive_count + negative_count == 0:
            return 0.0
        
        return (positive_count - negative_count) / (positive_count + negative_count)
    
    def _extract_entities(self, content: str) -> Dict[str, List[str]]:
        """Extract named entities from article content."""
        # Simplified entity extraction (replace with actual NLP)
        return {
            'companies': [],
            'people': [],
            'locations': [],
            'amounts': []
        }
    
    def _identify_topics(self, content: str) -> List[str]:
        """Identify key topics in article content."""
        # Simplified topic identification (replace with actual NLP)
        topics = []
        content_lower = content.lower()
        
        topic_keywords = {
            'funding': ['funding', 'investment', 'series a', 'series b', 'venture capital'],
            'development': ['development', 'construction', 'planning', 'building'],
            'acquisition': ['acquisition', 'merger', 'takeover', 'bought'],
            'partnership': ['partnership', 'joint venture', 'collaboration']
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                topics.append(topic)
        
        return topics
    
    def identify_target_companies(self, article_ids: List[str] = None) -> List[TargetCompany]:
        """
        Identify potential target companies from analyzed articles.
        
        Args:
            article_ids: Optional list of specific article IDs to analyze
            
        Returns:
            List of identified TargetCompany instances
            
        Raises:
            PermissionServiceError: If user lacks permission
        """
        self._check_permission('identify_targets')
        self._log_operation("identify_target_companies", {"article_count": len(article_ids) if article_ids else "all"})
        
        # Get relevant articles
        articles_query = NewsArticle.objects.filter(
            group=self.group,
            status=NewsArticle.ArticleStatus.RELEVANT
        )
        
        if article_ids:
            articles_query = articles_query.filter(id__in=article_ids)
        
        articles = articles_query.select_related('query_template')
        
        identified_targets = []
        
        for article in articles:
            # Extract company mentions from article
            companies = self._extract_company_mentions(article)
            
            for company_data in companies:
                # Check if company already exists
                existing_target = TargetCompany.objects.filter(
                    group=self.group,
                    company_name__iexact=company_data['name']
                ).first()
                
                if existing_target:
                    # Add article to existing target
                    existing_target.source_articles.add(article)
                    # Recalculate lead score
                    existing_target.lead_score = existing_target.calculate_lead_score()
                    existing_target.save()
                    identified_targets.append(existing_target)
                else:
                    # Create new target company
                    target = self._create_target_company(company_data, article)
                    identified_targets.append(target)
        
        return identified_targets
    
    def _extract_company_mentions(self, article: NewsArticle) -> List[Dict[str, Any]]:
        """Extract company mentions from article content."""
        # Simplified company extraction (replace with actual NLP)
        companies = []
        
        # Look for patterns like "Company Name announced" or "Company Name has"
        content = article.content
        
        # This is a very simplified implementation
        # In practice, you'd use proper NLP libraries like spaCy or NLTK
        if 'announced' in content.lower():
            # Extract potential company name before "announced"
            import re
            pattern = r'(\w+(?:\s+\w+)*)\s+announced'
            matches = re.findall(pattern, content, re.IGNORECASE)
            
            for match in matches[:3]:  # Limit to first 3 matches
                if len(match.split()) <= 3:  # Reasonable company name length
                    companies.append({
                        'name': match.strip(),
                        'confidence': 0.8,
                        'context': 'announcement'
                    })
        
        return companies
    
    def _create_target_company(self, company_data: Dict[str, Any], source_article: NewsArticle) -> TargetCompany:
        """Create a new target company from extracted data."""
        target = TargetCompany(
            group=self.group,
            company_name=company_data['name'],
            status=TargetCompany.TargetStatus.IDENTIFIED,
            identified_by=self.user,
            qualification_notes=f"Identified from article: {source_article.title}"
        )
        target.save()
        
        # Add source article
        target.source_articles.add(source_article)
        
        # Calculate initial lead score
        target.lead_score = target.calculate_lead_score()
        target.save()
        
        return target
    
    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """
        Get market intelligence dashboard metrics.
        
        Returns:
            Dict with various metrics and statistics
        """
        self._check_permission('view_dashboard')
        
        # Filter by user's group access
        articles = self._filter_by_group_access(NewsArticle.objects.all())
        targets = self._filter_by_group_access(TargetCompany.objects.all())
        templates = self._filter_by_group_access(QueryTemplate.objects.all())
        
        # Calculate metrics
        total_articles = articles.count()
        relevant_articles = articles.filter(status=NewsArticle.ArticleStatus.RELEVANT).count()
        pending_articles = articles.filter(status=NewsArticle.ArticleStatus.PENDING).count()
        
        total_targets = targets.count()
        qualified_targets = targets.filter(is_qualified=True).count()
        
        # Recent activity (last 7 days)
        recent_date = timezone.now() - timedelta(days=7)
        recent_articles = articles.filter(scraped_date__gte=recent_date).count()
        recent_targets = targets.filter(created_at__gte=recent_date).count()
        
        return {
            'articles': {
                'total': total_articles,
                'relevant': relevant_articles,
                'pending': pending_articles,
                'recent': recent_articles,
                'relevance_rate': (relevant_articles / total_articles * 100) if total_articles > 0 else 0
            },
            'targets': {
                'total': total_targets,
                'qualified': qualified_targets,
                'recent': recent_targets,
                'qualification_rate': (qualified_targets / total_targets * 100) if total_targets > 0 else 0
            },
            'templates': {
                'total': templates.count(),
                'active': templates.filter(is_active=True).count()
            }
        }