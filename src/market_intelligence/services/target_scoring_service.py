"""
Target Scoring service for lead qualification and company analysis.

Provides sophisticated lead scoring algorithms and target company
evaluation using multiple data sources and machine learning techniques.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from django.db import models
from django.utils import timezone

from accounts.models import User, Group
from assessments.services.base import BaseService, ValidationServiceError, PermissionServiceError
from ..models import TargetCompany, NewsArticle


class TargetScoringService(BaseService):
    """
    Service for advanced target company scoring and qualification.
    
    Implements ML-based lead scoring algorithms and provides
    comprehensive company evaluation capabilities.
    """
    
    def calculate_comprehensive_score(self, target_id: str) -> Dict[str, Any]:
        """
        Calculate comprehensive lead score using multiple factors.
        
        Args:
            target_id: ID of the target company to score
            
        Returns:
            Dict with detailed scoring breakdown
            
        Raises:
            NotFoundServiceError: If target not found
        """
        self._check_permission('score_targets')
        self._log_operation("calculate_comprehensive_score", {"target_id": target_id})
        
        try:
            target = TargetCompany.objects.get(id=target_id, group=self.group)
        except TargetCompany.DoesNotExist:
            raise NotFoundServiceError(f"Target company {target_id} not found")
        
        # Calculate individual score components
        scoring_components = {
            'business_alignment': self._score_business_alignment(target),
            'market_presence': self._score_market_presence(target),
            'news_sentiment': self._score_news_sentiment(target),
            'company_maturity': self._score_company_maturity(target),
            'geographic_fit': self._score_geographic_fit(target),
            'engagement_potential': self._score_engagement_potential(target),
            'data_completeness': self._score_data_completeness(target)
        }
        
        # Weight the components
        weights = {
            'business_alignment': 0.25,
            'market_presence': 0.20,
            'news_sentiment': 0.15,
            'company_maturity': 0.15,
            'geographic_fit': 0.10,
            'engagement_potential': 0.10,
            'data_completeness': 0.05
        }
        
        # Calculate weighted total
        total_score = sum(
            scoring_components[component] * weights[component]
            for component in scoring_components
        )
        
        # Update target with new score
        target.lead_score = min(total_score, 100.0)
        target.save()
        
        return {
            'target_id': str(target.id),
            'company_name': target.company_name,
            'total_score': total_score,
            'components': scoring_components,
            'weights': weights,
            'qualification_status': self._determine_qualification_status(total_score),
            'recommendations': self._generate_scoring_recommendations(scoring_components)
        }
    
    def _score_business_alignment(self, target: TargetCompany) -> float:
        """Score how well the company aligns with our investment focus."""
        score = 0.0
        
        # Business model alignment (max 40 points)
        business_model_scores = {
            'developer': 40,
            'investor': 35,
            'operator': 25,
            'platform': 20,
            'service': 10,
            'other': 5
        }
        score += business_model_scores.get(target.business_model, 0)
        
        # Sector focus alignment (max 35 points)
        if target.focus_sectors:
            if 'pbsa' in target.focus_sectors:
                score += 35
            elif any(sector in target.focus_sectors for sector in ['residential', 'commercial']):
                score += 20
            elif 'real estate' in str(target.focus_sectors).lower():
                score += 15
            else:
                score += 5
        
        # Company description alignment (max 25 points)
        if target.description:
            description_lower = target.description.lower()
            alignment_keywords = {
                'student accommodation': 15,
                'pbsa': 15,
                'student housing': 12,
                'real estate development': 10,
                'property investment': 8,
                'accommodation': 5
            }
            
            for keyword, points in alignment_keywords.items():
                if keyword in description_lower:
                    score += points
                    break  # Only award points for best match
        
        return min(score, 100.0)
    
    def _score_market_presence(self, target: TargetCompany) -> float:
        """Score the company's market presence and visibility."""
        score = 0.0
        
        # Company size (max 25 points)
        size_scores = {
            'large': 25,
            'medium': 20,
            'small': 15,
            'startup': 10,
            'unknown': 5
        }
        score += size_scores.get(target.company_size, 0)
        
        # Employee count (max 20 points)
        if target.employee_count:
            if target.employee_count >= 1000:
                score += 20
            elif target.employee_count >= 200:
                score += 15
            elif target.employee_count >= 50:
                score += 10
            else:
                score += 5
        
        # Digital presence (max 30 points)
        if target.domain:
            score += 15
        if target.linkedin_url:
            score += 15
        
        # News mentions (max 25 points)
        recent_articles = target.source_articles.filter(
            published_date__gte=timezone.now() - timedelta(days=90)
        ).count()
        
        if recent_articles >= 5:
            score += 25
        elif recent_articles >= 3:
            score += 20
        elif recent_articles >= 1:
            score += 15
        else:
            score += 5
        
        return min(score, 100.0)
    
    def _score_news_sentiment(self, target: TargetCompany) -> float:
        """Score based on sentiment analysis of related news articles."""
        articles = target.source_articles.exclude(sentiment_score__isnull=True)
        
        if not articles.exists():
            return 50.0  # Neutral score if no sentiment data
        
        # Calculate average sentiment
        avg_sentiment = articles.aggregate(
            avg_sentiment=models.Avg('sentiment_score')
        )['avg_sentiment']
        
        # Convert sentiment (-1 to 1) to score (0 to 100)
        # Neutral (0) maps to 50, positive (1) to 100, negative (-1) to 0
        score = (avg_sentiment + 1) * 50
        
        # Bonus for positive sentiment in recent articles
        recent_positive = articles.filter(
            published_date__gte=timezone.now() - timedelta(days=30),
            sentiment_score__gt=0.3
        ).count()
        
        if recent_positive >= 2:
            score += 10
        elif recent_positive >= 1:
            score += 5
        
        return min(score, 100.0)
    
    def _score_company_maturity(self, target: TargetCompany) -> float:
        """Score the company's maturity and stability."""
        score = 40.0  # Base score
        
        # Geographic diversification (max 20 points)
        if target.geographic_focus:
            geographic_count = len(target.geographic_focus)
            if geographic_count >= 5:
                score += 20
            elif geographic_count >= 3:
                score += 15
            elif geographic_count >= 2:
                score += 10
            else:
                score += 5
        
        # Business model sophistication (max 20 points)
        if target.description:
            sophistication_indicators = [
                'portfolio', 'fund', 'platform', 'technology',
                'analytics', 'management', 'strategy', 'international'
            ]
            description_lower = target.description.lower()
            sophistication_count = sum(
                1 for indicator in sophistication_indicators
                if indicator in description_lower
            )
            score += min(sophistication_count * 3, 20)
        
        # Data richness (max 20 points)
        data_points = [
            target.domain, target.linkedin_url, target.description,
            target.headquarters_city, target.headquarters_country,
            target.employee_count, target.focus_sectors, target.geographic_focus
        ]
        
        filled_data_points = sum(1 for point in data_points if point)
        score += (filled_data_points / len(data_points)) * 20
        
        return min(score, 100.0)
    
    def _score_geographic_fit(self, target: TargetCompany) -> float:
        """Score geographic alignment with our investment focus."""
        score = 50.0  # Neutral base
        
        # Preferred markets (higher scores)
        preferred_countries = ['GB', 'IE', 'NL', 'DE', 'FR']  # UK, Ireland, Netherlands, Germany, France
        emerging_markets = ['ES', 'IT', 'PL', 'CZ']  # Spain, Italy, Poland, Czech Republic
        
        if target.headquarters_country:
            if target.headquarters_country in preferred_countries:
                score += 30
            elif target.headquarters_country in emerging_markets:
                score += 20
            else:
                score += 10  # Any other European market
        
        # Geographic focus alignment
        if target.geographic_focus:
            european_markets = sum(
                1 for market in target.geographic_focus
                if any(country in str(market).upper() for country in preferred_countries + emerging_markets)
            )
            
            if european_markets >= 3:
                score += 20
            elif european_markets >= 1:
                score += 10
        
        return min(score, 100.0)
    
    def _score_engagement_potential(self, target: TargetCompany) -> float:
        """Score the potential for successful engagement."""
        score = 30.0  # Base score
        
        # Company status and approachability
        status_scores = {
            'identified': 10,
            'researching': 20,
            'qualified': 30,
            'contacted': 25,  # Lower because already contacted
            'engaged': 40,
            'converted': 0,   # Already converted
            'rejected': 0,    # Rejected
            'archived': 0     # Archived
        }
        score += status_scores.get(target.status, 0)
        
        # Time since identification (fresher leads often better)
        days_since_identification = target.days_since_identification
        if days_since_identification <= 7:
            score += 20
        elif days_since_identification <= 30:
            score += 15
        elif days_since_identification <= 90:
            score += 10
        else:
            score += 5
        
        # Recent news activity (indicates active company)
        recent_news = target.source_articles.filter(
            published_date__gte=timezone.now() - timedelta(days=60)
        ).count()
        
        if recent_news >= 3:
            score += 20
        elif recent_news >= 1:
            score += 10
        
        # Has contact information
        if hasattr(target, 'contacts') and target.contacts.exists():
            score += 20
        
        return min(score, 100.0)
    
    def _score_data_completeness(self, target: TargetCompany) -> float:
        """Score how complete the target's data profile is."""
        data_fields = [
            'company_name', 'domain', 'linkedin_url', 'description',
            'headquarters_city', 'headquarters_country', 'company_size',
            'employee_count', 'business_model', 'focus_sectors',
            'geographic_focus'
        ]
        
        filled_fields = 0
        for field in data_fields:
            value = getattr(target, field, None)
            if value:
                filled_fields += 1
        
        base_score = (filled_fields / len(data_fields)) * 70
        
        # Bonus for enrichment data
        if target.enrichment_data:
            base_score += 20
        
        # Bonus for recent enrichment
        if target.last_enriched and target.last_enriched >= timezone.now() - timedelta(days=30):
            base_score += 10
        
        return min(base_score, 100.0)
    
    def _determine_qualification_status(self, score: float) -> str:
        """Determine qualification status based on score."""
        if score >= 80:
            return 'highly_qualified'
        elif score >= 65:
            return 'qualified'
        elif score >= 50:
            return 'potential'
        elif score >= 30:
            return 'needs_research'
        else:
            return 'poor_fit'
    
    def _generate_scoring_recommendations(self, components: Dict[str, float]) -> List[str]:
        """Generate recommendations based on scoring components."""
        recommendations = []
        
        # Business alignment recommendations
        if components['business_alignment'] < 60:
            recommendations.append("Research company's PBSA focus and real estate activities")
        
        # Market presence recommendations
        if components['market_presence'] < 50:
            recommendations.append("Gather more information about company size and market position")
        
        # News sentiment recommendations
        if components['news_sentiment'] < 40:
            recommendations.append("Monitor for positive news developments before outreach")
        
        # Company maturity recommendations
        if components['company_maturity'] < 60:
            recommendations.append("Assess company's track record and portfolio")
        
        # Geographic fit recommendations
        if components['geographic_fit'] < 50:
            recommendations.append("Evaluate geographic market alignment")
        
        # Engagement potential recommendations
        if components['engagement_potential'] < 50:
            recommendations.append("Develop engagement strategy and identify key contacts")
        
        # Data completeness recommendations
        if components['data_completeness'] < 70:
            recommendations.append("Enrich company data through external sources")
        
        return recommendations
    
    def batch_score_targets(self, target_ids: List[str] = None) -> Dict[str, Any]:
        """
        Score multiple targets in batch for efficiency.
        
        Args:
            target_ids: Optional list of specific targets to score
            
        Returns:
            Batch scoring results and statistics
        """
        self._check_permission('score_targets')
        self._log_operation("batch_score_targets", {
            "target_count": len(target_ids) if target_ids else "all"
        })
        
        # Get targets to score
        if target_ids:
            targets = TargetCompany.objects.filter(
                id__in=target_ids,
                group=self.group
            )
        else:
            targets = self._filter_by_group_access(TargetCompany.objects.all())
        
        results = {
            'total_scored': 0,
            'highly_qualified': 0,
            'qualified': 0,
            'potential': 0,
            'needs_research': 0,
            'poor_fit': 0,
            'targets': []
        }
        
        for target in targets:
            try:
                scoring_result = self.calculate_comprehensive_score(str(target.id))
                results['targets'].append(scoring_result)
                results['total_scored'] += 1
                
                # Count by qualification status
                status = scoring_result['qualification_status']
                if status in results:
                    results[status] += 1
                    
            except Exception as e:
                self.logger.error(f"Error scoring target {target.id}: {str(e)}")
        
        return results
    
    def get_scoring_insights(self) -> Dict[str, Any]:
        """
        Get insights about target scoring across the pipeline.
        
        Returns:
            Dict with scoring insights and trends
        """
        self._check_permission('view_insights')
        
        targets = self._filter_by_group_access(TargetCompany.objects.all())
        
        # Score distribution
        score_ranges = {
            '80-100': targets.filter(lead_score__gte=80).count(),
            '65-79': targets.filter(lead_score__gte=65, lead_score__lt=80).count(),
            '50-64': targets.filter(lead_score__gte=50, lead_score__lt=65).count(),
            '30-49': targets.filter(lead_score__gte=30, lead_score__lt=50).count(),
            '0-29': targets.filter(lead_score__lt=30).count()
        }
        
        # Business model breakdown
        business_model_scores = targets.values('business_model').annotate(
            avg_score=models.Avg('lead_score'),
            count=models.Count('id')
        ).order_by('-avg_score')
        
        # Geographic performance
        geographic_scores = targets.exclude(headquarters_country='').values('headquarters_country').annotate(
            avg_score=models.Avg('lead_score'),
            count=models.Count('id')
        ).order_by('-avg_score')
        
        # Status progression
        status_scores = targets.values('status').annotate(
            avg_score=models.Avg('lead_score'),
            count=models.Count('id')
        ).order_by('-avg_score')
        
        return {
            'total_targets': targets.count(),
            'average_score': targets.aggregate(avg=models.Avg('lead_score'))['avg'] or 0,
            'score_distribution': score_ranges,
            'business_model_performance': list(business_model_scores),
            'geographic_performance': list(geographic_scores),
            'status_performance': list(status_scores),
            'top_targets': list(
                targets.filter(lead_score__gte=70)
                .order_by('-lead_score')
                .values('id', 'company_name', 'lead_score', 'status')[:10]
            )
        }