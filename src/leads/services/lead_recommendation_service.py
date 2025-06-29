"""
Lead Recommendation Service.

Provides intelligent location-based lead recommendations using geographic intelligence,
market analysis, and machine learning-ready scoring frameworks.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Avg, Count, F, Max, Min, Sum
from django.core.exceptions import ValidationError
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import Distance

from assessments.services.base import BaseService
from ..models import Lead, LeadScoringModel, LeadActivity
from geographic_intelligence.models import Neighborhood, University, PointOfInterest
from geographic_intelligence.services import GeographicIntelligenceService

logger = logging.getLogger(__name__)


class LeadRecommendationService(BaseService):
    """
    Service for generating intelligent location-based lead recommendations.
    
    Provides sophisticated recommendation algorithms that consider geographic
    intelligence, market conditions, strategic fit, and business objectives.
    """
    
    def __init__(self, user=None, group=None):
        super().__init__(user=user, group=group)
        self.model = Lead
    
    def get_recommendations_for_location(self, 
                                       latitude: float, 
                                       longitude: float, 
                                       radius_km: float = 10.0,
                                       limit: int = 10) -> Dict[str, Any]:
        """Get lead recommendations for a specific geographic location."""
        self._check_permission('view_leads')
        
        try:
            location = Point(longitude, latitude, srid=4326)
            
            # Find leads within radius with geographic analysis
            nearby_leads = Lead.objects.filter(
                group=self.group,
                headquarters_location__distance_lte=(location, Distance(km=radius_km)),
                geographic_analysis_date__isnull=False
            ).select_related(
                'target_neighborhood', 'target_neighborhood__metrics'
            ).prefetch_related('target_universities')
            
            if not nearby_leads.exists():
                return {
                    'location': {'latitude': latitude, 'longitude': longitude},
                    'radius_km': radius_km,
                    'total_leads': 0,
                    'recommendations': [],
                    'message': 'No leads with geographic analysis found in this area'
                }
            
            # Generate recommendations with scoring
            recommendations = []
            for lead in nearby_leads:
                recommendation = self._generate_location_recommendation(lead, location)
                if recommendation:
                    recommendations.append(recommendation)
            
            # Sort by recommendation score
            recommendations.sort(key=lambda x: x['recommendation_score'], reverse=True)
            
            # Get area insights
            area_insights = self._get_area_insights(location, radius_km)
            
            return {
                'location': {'latitude': latitude, 'longitude': longitude},
                'radius_km': radius_km,
                'total_leads': nearby_leads.count(),
                'recommendations': recommendations[:limit],
                'area_insights': area_insights,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f'Error generating location recommendations: {str(e)}')
            raise ValidationError(f'Failed to generate recommendations: {str(e)}')
    
    def get_recommendations_for_neighborhood(self, 
                                           neighborhood_id: str,
                                           limit: int = 10) -> Dict[str, Any]:
        """Get lead recommendations for a specific neighborhood."""
        self._check_permission('view_leads')
        
        try:
            from geographic_intelligence.models import Neighborhood
            neighborhood = Neighborhood.objects.get(id=neighborhood_id, group=self.group)
            
            # Find leads in this neighborhood
            neighborhood_leads = Lead.objects.filter(
                group=self.group,
                target_neighborhood=neighborhood,
                geographic_analysis_date__isnull=False
            ).select_related(
                'target_neighborhood', 'target_neighborhood__metrics'
            ).prefetch_related('target_universities')
            
            # Generate recommendations
            recommendations = []
            for lead in neighborhood_leads:
                recommendation = self._generate_neighborhood_recommendation(lead, neighborhood)
                if recommendation:
                    recommendations.append(recommendation)
            
            # Sort by recommendation score
            recommendations.sort(key=lambda x: x['recommendation_score'], reverse=True)
            
            # Get neighborhood insights
            neighborhood_insights = self._get_neighborhood_insights(neighborhood)
            
            return {
                'neighborhood': {
                    'id': str(neighborhood.id),
                    'name': neighborhood.name,
                    'overall_score': neighborhood.metrics.overall_score if neighborhood.metrics else 0
                },
                'total_leads': neighborhood_leads.count(),
                'recommendations': recommendations[:limit],
                'neighborhood_insights': neighborhood_insights,
                'generated_at': timezone.now().isoformat()
            }
            
        except Neighborhood.DoesNotExist:
            raise ValidationError(f'Neighborhood {neighborhood_id} not found')
        except Exception as e:
            logger.error(f'Error generating neighborhood recommendations: {str(e)}')
            raise ValidationError(f'Failed to generate recommendations: {str(e)}')
    
    def get_strategic_recommendations(self, 
                                    strategy_type: str,
                                    limit: int = 20) -> Dict[str, Any]:
        """Get lead recommendations based on strategic investment criteria."""
        self._check_permission('view_leads')
        
        strategy_filters = {
            'expansion': self._get_expansion_strategy_filter,
            'premium': self._get_premium_strategy_filter,
            'value': self._get_value_strategy_filter,
            'university_focused': self._get_university_focused_filter,
            'transport_hubs': self._get_transport_hub_filter,
            'emerging_markets': self._get_emerging_markets_filter,
            'diversification': self._get_diversification_filter
        }
        
        if strategy_type not in strategy_filters:
            raise ValidationError(f'Unknown strategy type: {strategy_type}')
        
        try:
            # Get leads matching strategy
            queryset = strategy_filters[strategy_type]()
            
            # Generate strategic recommendations
            recommendations = []
            for lead in queryset:
                recommendation = self._generate_strategic_recommendation(lead, strategy_type)
                if recommendation:
                    recommendations.append(recommendation)
            
            # Sort by recommendation score
            recommendations.sort(key=lambda x: x['recommendation_score'], reverse=True)
            
            # Get strategy insights
            strategy_insights = self._get_strategy_insights(strategy_type, queryset)
            
            return {
                'strategy_type': strategy_type,
                'total_leads': queryset.count(),
                'recommendations': recommendations[:limit],
                'strategy_insights': strategy_insights,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f'Error generating strategic recommendations: {str(e)}')
            raise ValidationError(f'Failed to generate recommendations: {str(e)}')
    
    def get_portfolio_optimization_recommendations(self, 
                                                 portfolio_constraints: Dict[str, Any] = None,
                                                 limit: int = 15) -> Dict[str, Any]:
        """Get lead recommendations for portfolio optimization."""
        self._check_permission('view_leads')
        
        constraints = portfolio_constraints or {}
        
        try:
            # Base queryset with geographic analysis
            leads = Lead.objects.filter(
                group=self.group,
                geographic_analysis_date__isnull=False
            ).select_related(
                'target_neighborhood', 'target_neighborhood__metrics'
            ).prefetch_related('target_universities')
            
            # Apply portfolio constraints
            if constraints.get('min_geographic_score'):
                leads = leads.filter(geographic_score__gte=constraints['min_geographic_score'])
            
            if constraints.get('max_competition_score'):
                leads = leads.filter(competition_score__lte=constraints['max_competition_score'])
            
            if constraints.get('min_university_proximity'):
                leads = leads.filter(university_proximity_score__gte=constraints['min_university_proximity'])
            
            if constraints.get('geographic_diversification'):
                # Ensure geographic spread
                leads = self._apply_diversification_filter(leads)
            
            # Generate portfolio recommendations
            recommendations = []
            for lead in leads:
                recommendation = self._generate_portfolio_recommendation(lead, constraints)
                if recommendation:
                    recommendations.append(recommendation)
            
            # Sort by portfolio fit score
            recommendations.sort(key=lambda x: x['portfolio_fit_score'], reverse=True)
            
            # Get portfolio insights
            portfolio_insights = self._get_portfolio_insights(recommendations, constraints)
            
            return {
                'portfolio_constraints': constraints,
                'total_eligible_leads': leads.count(),
                'recommendations': recommendations[:limit],
                'portfolio_insights': portfolio_insights,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f'Error generating portfolio recommendations: {str(e)}')
            raise ValidationError(f'Failed to generate recommendations: {str(e)}')
    
    # Private helper methods
    
    def _generate_location_recommendation(self, lead: Lead, location: Point) -> Optional[Dict[str, Any]]:
        """Generate recommendation for a lead based on location proximity."""
        try:
            # Calculate distance
            distance_km = lead.headquarters_location.distance(location) * 111  # Rough conversion to km
            
            # Base recommendation score
            rec_score = lead.geographic_score * 0.4
            rec_score += lead.current_score * 0.3
            rec_score += (100 - min(distance_km * 2, 100)) * 0.3  # Proximity bonus
            
            # Generate reasons
            reasons = []
            if lead.geographic_score >= 85:
                reasons.append(f"Excellent geographic score ({lead.geographic_score:.1f}/100)")
            if lead.accessibility_score >= 80:
                reasons.append(f"Strong transport accessibility ({lead.accessibility_score:.1f}/100)")
            if lead.university_proximity_score >= 85:
                reasons.append(f"Close to major universities ({lead.university_proximity_score:.1f}/100)")
            if distance_km <= 5:
                reasons.append(f"Very close to target location ({distance_km:.1f}km)")
            
            return {
                'lead_id': str(lead.id),
                'company_name': lead.company_name,
                'recommendation_score': round(rec_score, 1),
                'distance_km': round(distance_km, 1),
                'geographic_score': lead.geographic_score,
                'current_score': lead.current_score,
                'status': lead.status,
                'reasons': reasons,
                'recommendation_type': 'location_proximity'
            }
            
        except Exception as e:
            logger.warning(f'Error generating location recommendation for lead {lead.id}: {str(e)}')
            return None
    
    def _generate_neighborhood_recommendation(self, lead: Lead, neighborhood: Neighborhood) -> Optional[Dict[str, Any]]:
        """Generate recommendation for a lead within a specific neighborhood."""
        try:
            # Base recommendation score using neighborhood metrics
            neighborhood_score = neighborhood.metrics.overall_score if neighborhood.metrics else 50
            rec_score = lead.geographic_score * 0.5
            rec_score += lead.current_score * 0.3
            rec_score += neighborhood_score * 0.2
            
            # Generate reasons
            reasons = []
            if neighborhood_score >= 80:
                reasons.append(f"High-scoring neighborhood ({neighborhood_score:.1f}/100)")
            if lead.accessibility_score >= 80:
                reasons.append(f"Excellent transport links ({lead.accessibility_score:.1f}/100)")
            if lead.market_demand_score >= 75:
                reasons.append(f"Strong market demand ({lead.market_demand_score:.1f}/100)")
            if lead.competition_score >= 70:
                reasons.append(f"Favorable competition landscape ({lead.competition_score:.1f}/100)")
            
            return {
                'lead_id': str(lead.id),
                'company_name': lead.company_name,
                'recommendation_score': round(rec_score, 1),
                'geographic_score': lead.geographic_score,
                'current_score': lead.current_score,
                'neighborhood_score': neighborhood_score,
                'status': lead.status,
                'reasons': reasons,
                'recommendation_type': 'neighborhood_fit'
            }
            
        except Exception as e:
            logger.warning(f'Error generating neighborhood recommendation for lead {lead.id}: {str(e)}')
            return None
    
    def _generate_strategic_recommendation(self, lead: Lead, strategy_type: str) -> Optional[Dict[str, Any]]:
        """Generate strategic recommendation for a lead."""
        try:
            # Strategy-specific scoring weights
            strategy_weights = {
                'expansion': {'geographic': 0.4, 'score': 0.3, 'accessibility': 0.3},
                'premium': {'geographic': 0.3, 'score': 0.4, 'university_proximity': 0.3},
                'value': {'geographic': 0.3, 'score': 0.3, 'competition': 0.4},
                'university_focused': {'university_proximity': 0.5, 'score': 0.3, 'market_demand': 0.2},
                'transport_hubs': {'accessibility': 0.5, 'geographic': 0.3, 'score': 0.2},
                'emerging_markets': {'market_demand': 0.4, 'geographic': 0.3, 'score': 0.3},
                'diversification': {'geographic': 0.4, 'score': 0.4, 'accessibility': 0.2}
            }
            
            weights = strategy_weights.get(strategy_type, {'geographic': 0.5, 'score': 0.5})
            
            # Calculate strategic fit score
            rec_score = 0
            if 'geographic' in weights:
                rec_score += lead.geographic_score * weights['geographic']
            if 'score' in weights:
                rec_score += lead.current_score * weights['score']
            if 'accessibility' in weights:
                rec_score += lead.accessibility_score * weights['accessibility']
            if 'university_proximity' in weights:
                rec_score += lead.university_proximity_score * weights['university_proximity']
            if 'market_demand' in weights:
                rec_score += lead.market_demand_score * weights['market_demand']
            if 'competition' in weights:
                rec_score += lead.competition_score * weights['competition']
            
            # Generate strategic reasons
            reasons = self._get_strategic_reasons(lead, strategy_type)
            
            return {
                'lead_id': str(lead.id),
                'company_name': lead.company_name,
                'recommendation_score': round(rec_score, 1),
                'strategic_fit': strategy_type,
                'geographic_score': lead.geographic_score,
                'current_score': lead.current_score,
                'status': lead.status,
                'reasons': reasons,
                'recommendation_type': 'strategic_fit'
            }
            
        except Exception as e:
            logger.warning(f'Error generating strategic recommendation for lead {lead.id}: {str(e)}')
            return None
    
    def _generate_portfolio_recommendation(self, lead: Lead, constraints: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate portfolio optimization recommendation for a lead."""
        try:
            # Portfolio fit scoring
            portfolio_score = 0
            
            # Geographic diversification bonus
            if lead.target_neighborhood:
                portfolio_score += 20  # Points for having neighborhood data
            
            # Score components
            portfolio_score += lead.geographic_score * 0.3
            portfolio_score += lead.current_score * 0.3
            portfolio_score += lead.accessibility_score * 0.2
            portfolio_score += lead.university_proximity_score * 0.2
            
            # Constraint compliance bonus
            if constraints.get('min_geographic_score', 0) <= lead.geographic_score:
                portfolio_score += 10
            if constraints.get('min_university_proximity', 0) <= lead.university_proximity_score:
                portfolio_score += 10
            
            # Generate portfolio reasons
            reasons = []
            if lead.geographic_score >= 80:
                reasons.append(f"Strong geographic fundamentals ({lead.geographic_score:.1f}/100)")
            if lead.competition_score >= 70:
                reasons.append(f"Attractive competitive position ({lead.competition_score:.1f}/100)")
            if lead.target_neighborhood:
                reasons.append(f"Located in analyzed neighborhood: {lead.target_neighborhood.name}")
            
            return {
                'lead_id': str(lead.id),
                'company_name': lead.company_name,
                'portfolio_fit_score': round(portfolio_score, 1),
                'geographic_score': lead.geographic_score,
                'current_score': lead.current_score,
                'status': lead.status,
                'target_neighborhood': lead.target_neighborhood.name if lead.target_neighborhood else None,
                'reasons': reasons,
                'recommendation_type': 'portfolio_optimization'
            }
            
        except Exception as e:
            logger.warning(f'Error generating portfolio recommendation for lead {lead.id}: {str(e)}')
            return None
    
    # Strategy filter methods
    
    def _get_expansion_strategy_filter(self):
        """Get leads suitable for expansion strategy."""
        return Lead.objects.filter(
            group=self.group,
            geographic_analysis_date__isnull=False,
            geographic_score__gte=70,
            accessibility_score__gte=75
        )
    
    def _get_premium_strategy_filter(self):
        """Get leads suitable for premium strategy."""
        return Lead.objects.filter(
            group=self.group,
            geographic_analysis_date__isnull=False,
            current_score__gte=80,
            university_proximity_score__gte=85
        )
    
    def _get_value_strategy_filter(self):
        """Get leads suitable for value strategy."""
        return Lead.objects.filter(
            group=self.group,
            geographic_analysis_date__isnull=False,
            competition_score__gte=70,
            geographic_score__gte=60
        )
    
    def _get_university_focused_filter(self):
        """Get leads suitable for university-focused strategy."""
        return Lead.objects.filter(
            group=self.group,
            geographic_analysis_date__isnull=False,
            university_proximity_score__gte=80,
            target_universities__isnull=False
        ).distinct()
    
    def _get_transport_hub_filter(self):
        """Get leads suitable for transport hub strategy."""
        return Lead.objects.filter(
            group=self.group,
            geographic_analysis_date__isnull=False,
            accessibility_score__gte=85
        )
    
    def _get_emerging_markets_filter(self):
        """Get leads suitable for emerging markets strategy."""
        return Lead.objects.filter(
            group=self.group,
            geographic_analysis_date__isnull=False,
            market_demand_score__gte=75,
            competition_score__gte=65
        )
    
    def _get_diversification_filter(self):
        """Get leads suitable for diversification strategy."""
        return Lead.objects.filter(
            group=self.group,
            geographic_analysis_date__isnull=False,
            geographic_score__gte=65
        ).exclude(
            target_neighborhood__in=Lead.objects.filter(
                group=self.group, status=Lead.LeadStatus.CONVERTED
            ).values_list('target_neighborhood', flat=True)
        )
    
    def _apply_diversification_filter(self, queryset):
        """Apply geographic diversification to queryset."""
        # Get diverse neighborhoods
        diverse_neighborhoods = queryset.values('target_neighborhood').annotate(
            lead_count=Count('id')
        ).filter(lead_count__lte=3)  # Max 3 leads per neighborhood
        
        neighborhood_ids = [item['target_neighborhood'] for item in diverse_neighborhoods]
        return queryset.filter(target_neighborhood__in=neighborhood_ids)
    
    def _get_strategic_reasons(self, lead: Lead, strategy_type: str) -> List[str]:
        """Get strategic reasons for recommending a lead."""
        reasons = []
        
        if strategy_type == 'expansion':
            if lead.accessibility_score >= 80:
                reasons.append(f"Excellent transport connectivity ({lead.accessibility_score:.1f}/100)")
            if lead.geographic_score >= 75:
                reasons.append(f"Strong geographic fundamentals ({lead.geographic_score:.1f}/100)")
                
        elif strategy_type == 'premium':
            if lead.university_proximity_score >= 85:
                reasons.append(f"Prime university location ({lead.university_proximity_score:.1f}/100)")
            if lead.current_score >= 85:
                reasons.append(f"High-quality lead ({lead.current_score:.1f}/100)")
                
        elif strategy_type == 'value':
            if lead.competition_score >= 70:
                reasons.append(f"Favorable competitive landscape ({lead.competition_score:.1f}/100)")
            if lead.geographic_score >= 60:
                reasons.append(f"Solid geographic foundation ({lead.geographic_score:.1f}/100)")
        
        # Add more strategy-specific reasons as needed
        
        return reasons
    
    # Insight generation methods
    
    def _get_area_insights(self, location: Point, radius_km: float) -> Dict[str, Any]:
        """Get insights about an area."""
        # This would analyze the area using geographic intelligence
        return {
            'area_type': 'Urban center',
            'student_population': 'High',
            'transport_quality': 'Excellent',
            'competition_level': 'Moderate',
            'growth_potential': 'Strong'
        }
    
    def _get_neighborhood_insights(self, neighborhood: Neighborhood) -> Dict[str, Any]:
        """Get insights about a neighborhood."""
        metrics = neighborhood.metrics
        if not metrics:
            return {'message': 'No metrics available'}
        
        return {
            'overall_score': metrics.overall_score,
            'accessibility_rating': 'Excellent' if metrics.accessibility_score >= 80 else 'Good',
            'university_access': 'Prime' if metrics.university_proximity_score >= 85 else 'Good',
            'market_strength': 'Strong' if metrics.overall_score >= 80 else 'Moderate',
            'investment_potential': 'High' if metrics.overall_score >= 85 else 'Medium'
        }
    
    def _get_strategy_insights(self, strategy_type: str, queryset) -> Dict[str, Any]:
        """Get insights about a strategy."""
        return {
            'strategy_focus': strategy_type,
            'eligible_leads': queryset.count(),
            'avg_geographic_score': queryset.aggregate(avg=Avg('geographic_score'))['avg'] or 0,
            'success_probability': 'High' if queryset.count() >= 10 else 'Medium'
        }
    
    def _get_portfolio_insights(self, recommendations: List[Dict], constraints: Dict) -> Dict[str, Any]:
        """Get portfolio insights."""
        if not recommendations:
            return {'message': 'No recommendations available'}
        
        avg_score = sum(r['portfolio_fit_score'] for r in recommendations) / len(recommendations)
        geographic_diversity = len(set(r.get('target_neighborhood') for r in recommendations if r.get('target_neighborhood')))
        
        return {
            'average_portfolio_score': round(avg_score, 1),
            'geographic_diversity': geographic_diversity,
            'total_recommendations': len(recommendations),
            'portfolio_quality': 'Excellent' if avg_score >= 80 else 'Good'
        }