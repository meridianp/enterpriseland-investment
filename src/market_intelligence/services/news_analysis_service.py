"""
News Analysis service for advanced NLP and content processing.

Handles article analysis, entity extraction, and relevance scoring
using NLP techniques and machine learning models.
"""

import logging
from typing import Dict, Any, Optional, List
from django.utils import timezone
from datetime import timedelta

from accounts.models import User, Group
from assessments.services.base import BaseService, ValidationServiceError, PermissionServiceError
from ..models import NewsArticle, QueryTemplate


class NewsAnalysisService(BaseService):
    """
    Service for advanced news analysis and NLP processing.
    
    Provides sophisticated content analysis capabilities for 
    investment opportunity identification.
    """
    
    def batch_analyze_articles(self, 
                              article_ids: List[str] = None,
                              days_back: int = 7) -> Dict[str, Any]:
        """
        Analyze multiple articles in batch for efficiency.
        
        Args:
            article_ids: Optional list of specific articles to analyze
            days_back: Number of days back to analyze if no IDs provided
            
        Returns:
            Analysis results and statistics
        """
        self._check_permission('analyze_articles')
        self._log_operation("batch_analyze_articles", {
            "article_count": len(article_ids) if article_ids else "recent",
            "days_back": days_back
        })
        
        # Get articles to analyze
        if article_ids:
            articles = NewsArticle.objects.filter(
                id__in=article_ids,
                group=self.group
            )
        else:
            cutoff_date = timezone.now() - timedelta(days=days_back)
            articles = NewsArticle.objects.filter(
                group=self.group,
                status=NewsArticle.ArticleStatus.PENDING,
                scraped_date__gte=cutoff_date
            )
        
        results = {
            'total_analyzed': 0,
            'relevant_found': 0,
            'entities_extracted': 0,
            'processing_errors': 0,
            'articles': []
        }
        
        for article in articles:
            try:
                analysis_result = self._analyze_single_article(article)
                results['articles'].append(analysis_result)
                results['total_analyzed'] += 1
                
                if article.relevance_score >= 0.7:
                    results['relevant_found'] += 1
                
                if article.entities_extracted:
                    results['entities_extracted'] += 1
                    
            except Exception as e:
                self.logger.error(f"Error analyzing article {article.id}: {str(e)}")
                results['processing_errors'] += 1
        
        return results
    
    def _analyze_single_article(self, article: NewsArticle) -> Dict[str, Any]:
        """Analyze a single article and update its fields."""
        # Calculate relevance score
        relevance_score = self._advanced_relevance_scoring(article)
        
        # Perform sentiment analysis
        sentiment_score = self._sentiment_analysis(article.content)
        
        # Extract entities
        entities = self._entity_extraction(article.content)
        
        # Identify topics
        topics = self._topic_modeling(article.content)
        
        # Generate summary
        summary = self._generate_summary(article.content)
        
        # Update article
        article.relevance_score = relevance_score
        article.sentiment_score = sentiment_score
        article.entities_extracted = entities
        article.topics = topics
        article.summary = summary
        article.status = (
            NewsArticle.ArticleStatus.RELEVANT if relevance_score >= 0.7
            else NewsArticle.ArticleStatus.IRRELEVANT
        )
        article.save()
        
        return {
            'article_id': str(article.id),
            'title': article.title,
            'relevance_score': relevance_score,
            'sentiment_score': sentiment_score,
            'topics': topics,
            'entity_count': sum(len(entities.get(key, [])) for key in entities),
            'status': article.status
        }
    
    def _advanced_relevance_scoring(self, article: NewsArticle) -> float:
        """
        Advanced relevance scoring using multiple factors.
        
        This is a more sophisticated version that considers:
        - Keyword density and positioning
        - Source credibility
        - Article recency
        - Content quality indicators
        """
        score = 0.0
        content_lower = article.content.lower()
        title_lower = article.title.lower()
        
        # Primary PBSA keywords (higher weight)
        primary_keywords = {
            'pbsa': 0.4,
            'purpose built student accommodation': 0.4,
            'student accommodation': 0.3,
            'student housing': 0.3,
            'student beds': 0.25,
            'student residence': 0.2,
            'university housing': 0.2
        }
        
        # Secondary real estate keywords
        secondary_keywords = {
            'property investment': 0.15,
            'real estate fund': 0.15,
            'property development': 0.1,
            'asset management': 0.1,
            'property acquisition': 0.1,
            'portfolio': 0.05
        }
        
        # Calculate keyword scores
        for keyword, weight in primary_keywords.items():
            if keyword in title_lower:
                score += weight * 1.5  # Title mentions get bonus
            elif keyword in content_lower:
                score += weight
        
        for keyword, weight in secondary_keywords.items():
            if keyword in title_lower:
                score += weight * 1.5
            elif keyword in content_lower:
                score += weight
        
        # Source credibility bonus
        credible_sources = {
            'property week': 0.2,
            'estates gazette': 0.2,
            'react news': 0.15,
            'propertyeu': 0.15,
            'place north west': 0.1,
            'financial times': 0.1
        }
        
        source_lower = article.source.lower()
        for source, bonus in credible_sources.items():
            if source in source_lower:
                score += bonus
                break
        
        # Recency bonus (newer articles get slight preference)
        days_old = (timezone.now() - article.published_date).days
        if days_old <= 1:
            score += 0.1
        elif days_old <= 7:
            score += 0.05
        
        # Content quality indicators
        if len(article.content) > 500:  # Substantial content
            score += 0.05
        
        if article.author:  # Has author attribution
            score += 0.02
        
        return min(score, 1.0)
    
    def _sentiment_analysis(self, content: str) -> float:
        """
        Perform sentiment analysis on article content.
        
        Returns sentiment score from -1 (negative) to 1 (positive).
        """
        # Enhanced sentiment analysis with more comprehensive word lists
        positive_indicators = [
            'growth', 'expansion', 'success', 'opportunity', 'investment',
            'development', 'construction', 'new', 'launch', 'opening',
            'partnership', 'collaboration', 'funding', 'acquisition',
            'innovative', 'breakthrough', 'excellent', 'strong',
            'increased', 'improved', 'rising', 'bull', 'optimistic'
        ]
        
        negative_indicators = [
            'decline', 'decrease', 'loss', 'problem', 'issue', 'crisis',
            'failure', 'bankruptcy', 'closure', 'downturn', 'recession',
            'weak', 'poor', 'disappointing', 'struggling', 'difficult',
            'challenging', 'uncertain', 'risk', 'concern', 'worry'
        ]
        
        content_words = content.lower().split()
        
        positive_count = sum(1 for word in content_words if any(pos in word for pos in positive_indicators))
        negative_count = sum(1 for word in content_words if any(neg in word for neg in negative_indicators))
        
        total_sentiment_words = positive_count + negative_count
        
        if total_sentiment_words == 0:
            return 0.0
        
        # Normalize to -1 to 1 range
        sentiment = (positive_count - negative_count) / total_sentiment_words
        return max(-1.0, min(1.0, sentiment))
    
    def _entity_extraction(self, content: str) -> Dict[str, List[str]]:
        """
        Extract named entities from content.
        
        In production, this would use proper NLP libraries like spaCy.
        """
        entities = {
            'companies': [],
            'people': [],
            'locations': [],
            'monetary_amounts': [],
            'universities': []
        }
        
        # Simple pattern-based extraction (replace with proper NLP)
        import re
        
        # Extract monetary amounts
        money_patterns = [
            r'£(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:million|m|billion|bn)',
            r'\$(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:million|m|billion|bn)',
            r'€(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:million|m|billion|bn)'
        ]
        
        for pattern in money_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            entities['monetary_amounts'].extend(matches)
        
        # Extract university names (common patterns)
        university_patterns = [
            r'(\w+\s+University)',
            r'(University\s+of\s+\w+)',
            r'(\w+\s+College)'
        ]
        
        for pattern in university_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            entities['universities'].extend([match.strip() for match in matches])
        
        # Extract potential company names (ending with Ltd, Plc, Inc, etc.)
        company_pattern = r'([A-Z][a-zA-Z\s&]+(?:Ltd|Plc|Inc|LLC|Group|Holdings|Development|Properties|Investments))'
        company_matches = re.findall(company_pattern, content)
        entities['companies'].extend([match.strip() for match in company_matches[:5]])  # Limit to top 5
        
        return entities
    
    def _topic_modeling(self, content: str) -> List[str]:
        """
        Identify key topics in the article content.
        
        Uses keyword-based topic identification with confidence scoring.
        """
        topics = []
        content_lower = content.lower()
        
        topic_definitions = {
            'funding_investment': {
                'keywords': ['funding', 'investment', 'series a', 'series b', 'venture capital', 
                           'private equity', 'fund', 'capital', 'financing', 'raised'],
                'threshold': 2
            },
            'property_development': {
                'keywords': ['development', 'construction', 'planning permission', 'building',
                           'developer', 'scheme', 'project', 'site', 'planning'],
                'threshold': 2
            },
            'acquisition_merger': {
                'keywords': ['acquisition', 'merger', 'takeover', 'bought', 'purchased',
                           'acquired', 'deal', 'transaction', 'sale'],
                'threshold': 1
            },
            'partnership_joint_venture': {
                'keywords': ['partnership', 'joint venture', 'collaboration', 'alliance',
                           'consortium', 'cooperation', 'tie-up'],
                'threshold': 1
            },
            'student_housing': {
                'keywords': ['student', 'accommodation', 'housing', 'residence', 'pbsa',
                           'university', 'college', 'campus', 'dormitory'],
                'threshold': 2
            },
            'proptech_technology': {
                'keywords': ['proptech', 'technology', 'digital', 'platform', 'software',
                           'app', 'ai', 'artificial intelligence', 'automation'],
                'threshold': 1
            },
            'market_trends': {
                'keywords': ['market', 'trend', 'demand', 'supply', 'growth', 'outlook',
                           'forecast', 'report', 'analysis', 'data'],
                'threshold': 2
            }
        }
        
        for topic, definition in topic_definitions.items():
            keyword_count = sum(1 for keyword in definition['keywords'] 
                              if keyword in content_lower)
            
            if keyword_count >= definition['threshold']:
                topics.append(topic)
        
        return topics
    
    def _generate_summary(self, content: str, max_sentences: int = 3) -> str:
        """
        Generate a concise summary of the article content.
        
        Uses simple extractive summarization based on sentence scoring.
        """
        if len(content) < 200:
            return content[:200] + "..." if len(content) > 200 else content
        
        # Split into sentences
        sentences = [s.strip() for s in content.split('.') if len(s.strip()) > 20]
        
        if len(sentences) <= max_sentences:
            return '. '.join(sentences) + '.'
        
        # Score sentences based on keyword presence and position
        sentence_scores = []
        
        important_keywords = [
            'student accommodation', 'pbsa', 'investment', 'development',
            'funding', 'acquisition', 'partnership', 'university'
        ]
        
        for i, sentence in enumerate(sentences):
            score = 0
            sentence_lower = sentence.lower()
            
            # Keyword presence
            for keyword in important_keywords:
                if keyword in sentence_lower:
                    score += 1
            
            # Position bonus (earlier sentences often more important)
            if i < 3:
                score += 0.5
            
            sentence_scores.append((score, sentence))
        
        # Select top scoring sentences
        top_sentences = sorted(sentence_scores, key=lambda x: x[0], reverse=True)[:max_sentences]
        
        # Maintain original order
        selected_sentences = []
        for sentence_score, sentence in top_sentences:
            original_index = sentences.index(sentence)
            selected_sentences.append((original_index, sentence))
        
        selected_sentences.sort(key=lambda x: x[0])
        
        return '. '.join([sentence for _, sentence in selected_sentences]) + '.'
    
    def get_analysis_insights(self, days_back: int = 30) -> Dict[str, Any]:
        """
        Get insights from recent article analysis.
        
        Args:
            days_back: Number of days to analyze
            
        Returns:
            Dict with analysis insights and trends
        """
        self._check_permission('view_insights')
        
        cutoff_date = timezone.now() - timedelta(days=days_back)
        articles = self._filter_by_group_access(
            NewsArticle.objects.filter(scraped_date__gte=cutoff_date)
        )
        
        # Topic frequency analysis
        all_topics = []
        for article in articles.exclude(topics=[]):
            all_topics.extend(article.topics)
        
        topic_counts = {}
        for topic in all_topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        # Sentiment trends
        sentiment_by_day = {}
        for article in articles.exclude(sentiment_score__isnull=True):
            day_key = article.published_date.date()
            if day_key not in sentiment_by_day:
                sentiment_by_day[day_key] = []
            sentiment_by_day[day_key].append(article.sentiment_score)
        
        # Calculate daily average sentiment
        daily_sentiment = {}
        for day, scores in sentiment_by_day.items():
            daily_sentiment[day.isoformat()] = sum(scores) / len(scores)
        
        return {
            'period_days': days_back,
            'total_articles': articles.count(),
            'relevant_articles': articles.filter(status=NewsArticle.ArticleStatus.RELEVANT).count(),
            'avg_relevance_score': articles.aggregate(avg_score=models.Avg('relevance_score'))['avg_score'] or 0,
            'top_topics': sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            'sentiment_trend': daily_sentiment,
            'top_sources': list(articles.values('source').annotate(count=models.Count('source')).order_by('-count')[:10])
        }