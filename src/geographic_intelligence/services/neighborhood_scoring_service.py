"""
Neighborhood Scoring Service for PBSA investment analysis.

Provides comprehensive neighborhood evaluation and scoring based on multiple
criteria relevant to student accommodation investments.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime

from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.measure import Distance
from django.db.models import QuerySet, Count, Avg, Q
from django.utils import timezone

from accounts.models import Group
from ..models import (
    PointOfInterest, POIType, University, Neighborhood, 
    NeighborhoodMetrics
)

logger = logging.getLogger(__name__)


class NeighborhoodScoringService:
    """
    Service for calculating neighborhood scores for PBSA investment.
    
    Evaluates neighborhoods across multiple dimensions including accessibility,
    university proximity, amenities, affordability, safety, and development feasibility.
    """
    
    def __init__(self, group: Group = None):
        """Initialize service for a specific group."""
        self.group = group
    
    def calculate_neighborhood_scores(self, neighborhood: Neighborhood) -> NeighborhoodMetrics:
        """
        Calculate comprehensive scores for a neighborhood.
        
        Args:
            neighborhood: Neighborhood instance to score
            
        Returns:
            Updated NeighborhoodMetrics instance
        """
        metrics = neighborhood.metrics
        
        # Calculate individual scores
        metrics.accessibility_score = self._calculate_accessibility_score(neighborhood)
        metrics.university_proximity_score = self._calculate_university_proximity_score(neighborhood)
        metrics.amenities_score = self._calculate_amenities_score(neighborhood)
        metrics.affordability_score = self._calculate_affordability_score(neighborhood)
        metrics.safety_score = self._calculate_safety_score(neighborhood)
        metrics.cultural_score = self._calculate_cultural_score(neighborhood)
        metrics.planning_feasibility_score = self._calculate_planning_feasibility_score(neighborhood)
        metrics.competition_score = self._calculate_competition_score(neighborhood)
        
        # Update supporting metrics
        metrics.transport_links_count = self._count_transport_links(neighborhood)
        metrics.amenities_count = self._count_amenities(neighborhood)
        
        # Calculate overall score
        metrics.calculate_overall_score()
        
        # Update calculation metadata
        metrics.calculation_date = timezone.now()
        metrics.data_sources = self._get_data_sources()
        
        metrics.save()
        return metrics
    
    def _calculate_accessibility_score(self, neighborhood: Neighborhood) -> float:
        """Calculate transport accessibility score (0-100)."""
        centroid = neighborhood.boundaries.centroid
        score = 0.0
        
        # Find transport POIs within neighborhood and nearby
        transport_pois = PointOfInterest.objects.filter(
            group=neighborhood.group,
            poi_type__in=['metro', 'train', 'bus', 'transport'],
            location__distance_lte=(centroid, Distance(km=2.0))
        )
        
        # Score based on transport type and proximity
        metro_count = transport_pois.filter(poi_type='metro').count()
        train_count = transport_pois.filter(poi_type='train').count()
        bus_count = transport_pois.filter(poi_type='bus').count()
        
        # Metro stations (highest value)
        score += min(metro_count * 30, 60)  # Max 60 points for metro
        
        # Train stations
        score += min(train_count * 20, 40)  # Max 40 points for train
        
        # Bus stops
        score += min(bus_count * 2, 20)  # Max 20 points for buses
        
        # Distance penalty for closest transport
        if transport_pois.exists():
            closest_transport = min(
                poi.location.distance(centroid) * 100  # Convert to km
                for poi in transport_pois
            )
            distance_bonus = max(0, (1.0 - closest_transport) / 1.0) * 20
            score += distance_bonus
        
        return min(score, 100.0)
    
    def _calculate_university_proximity_score(self, neighborhood: Neighborhood) -> float:
        """Calculate proximity to universities score (0-100)."""
        centroid = neighborhood.boundaries.centroid
        
        # Find universities within reasonable distance
        universities = University.objects.filter(
            group=neighborhood.group,
            main_campus__location__distance_lte=(centroid, Distance(km=10.0))
        ).select_related('main_campus')
        
        if not universities.exists():
            return 0.0
        
        score = 0.0
        total_students = 0
        
        for university in universities:
            distance_km = university.main_campus.location.distance(centroid) * 100
            student_count = university.total_students
            total_students += student_count
            
            # Distance scoring (closer is better)
            if distance_km <= 1.0:
                distance_score = 40
            elif distance_km <= 2.0:
                distance_score = 35
            elif distance_km <= 3.0:
                distance_score = 25
            elif distance_km <= 5.0:
                distance_score = 15
            else:
                distance_score = 5
            
            # Student population factor (more students = higher demand)
            student_factor = min(student_count / 10000, 1.0)
            university_score = distance_score * (0.7 + 0.3 * student_factor)
            
            score += university_score
        
        # Bonus for multiple universities
        if universities.count() > 1:
            score *= 1.2
        
        # Bonus for large total student population
        if total_students > 20000:
            score *= 1.1
        
        return min(score, 100.0)
    
    def _calculate_amenities_score(self, neighborhood: Neighborhood) -> float:
        """Calculate student amenities availability score (0-100)."""
        centroid = neighborhood.boundaries.centroid
        
        # Define amenity types and their weights
        amenity_weights = {
            'grocery': 15,      # Essential
            'restaurant': 15,   # Essential
            'shopping': 12,     # Important
            'library': 10,      # Academic support
            'sports': 10,       # Recreation
            'healthcare': 8,    # Safety
            'nightlife': 8,     # Social
            'park': 7,          # Recreation
        }
        
        score = 0.0
        
        for poi_type, weight in amenity_weights.items():
            pois = PointOfInterest.objects.filter(
                group=neighborhood.group,
                poi_type=poi_type,
                location__distance_lte=(centroid, Distance(km=1.5))
            )
            
            count = pois.count()
            if count > 0:
                # Base score for having any of this type
                type_score = weight * 0.6
                
                # Bonus for multiple options
                if count > 1:
                    type_score += weight * 0.3 * min(count - 1, 3) / 3
                
                # Proximity bonus
                closest_distance = min(
                    poi.location.distance(centroid) * 100 for poi in pois
                )
                if closest_distance <= 0.5:
                    type_score += weight * 0.1
                
                score += type_score
        
        return min(score, 100.0)
    
    def _calculate_affordability_score(self, neighborhood: Neighborhood) -> float:
        """Calculate housing affordability score (0-100)."""
        # This would typically use real estate data
        # For now, use placeholder logic based on location characteristics
        
        score = 50.0  # Base score
        
        # Adjust based on location type
        if hasattr(neighborhood, 'location_type'):
            if neighborhood.location_type == 'city_centre':
                score -= 20  # City center typically more expensive
            elif neighborhood.location_type == 'suburban':
                score += 15  # Suburban typically more affordable
            elif neighborhood.location_type == 'edge_of_town':
                score += 25  # Edge of town typically most affordable
        
        # Adjust based on planning constraints
        if neighborhood.historic_district:
            score -= 15  # Historic districts typically more expensive
        
        # Adjust based on average land price if available
        if neighborhood.average_land_price_psf:
            if neighborhood.average_land_price_psf > 100:
                score -= 20
            elif neighborhood.average_land_price_psf < 50:
                score += 20
        
        return max(0, min(score, 100.0))
    
    def _calculate_safety_score(self, neighborhood: Neighborhood) -> float:
        """Calculate neighborhood safety score (0-100)."""
        score = 50.0  # Base safety score
        
        # Check for safety-related POIs
        centroid = neighborhood.boundaries.centroid
        
        # Healthcare facilities nearby (positive factor)
        healthcare_count = PointOfInterest.objects.filter(
            group=neighborhood.group,
            poi_type='healthcare',
            location__distance_lte=(centroid, Distance(km=2.0))
        ).count()
        score += min(healthcare_count * 10, 20)
        
        # Well-lit areas (parks, shopping centers indicate activity)
        activity_pois = PointOfInterest.objects.filter(
            group=neighborhood.group,
            poi_type__in=['shopping', 'restaurant', 'sports'],
            location__distance_lte=(centroid, Distance(km=1.0))
        ).count()
        score += min(activity_pois * 3, 15)
        
        # Use crime rate if available
        if hasattr(neighborhood.metrics, 'crime_rate_percentile') and neighborhood.metrics.crime_rate_percentile:
            # Lower crime rate percentile = safer = higher score
            crime_factor = (100 - neighborhood.metrics.crime_rate_percentile) / 100
            score = score * 0.3 + crime_factor * 70
        
        return min(score, 100.0)
    
    def _calculate_cultural_score(self, neighborhood: Neighborhood) -> float:
        """Calculate cultural and leisure options score (0-100)."""
        centroid = neighborhood.boundaries.centroid
        
        cultural_pois = PointOfInterest.objects.filter(
            group=neighborhood.group,
            poi_type__in=['restaurant', 'nightlife', 'sports', 'park', 'library'],
            location__distance_lte=(centroid, Distance(km=2.0))
        )
        
        score = 0.0
        
        # Score by type diversity and quantity
        poi_types = cultural_pois.values('poi_type').distinct().count()
        total_count = cultural_pois.count()
        
        # Diversity bonus
        score += poi_types * 15  # Up to 75 points for all 5 types
        
        # Quantity bonus
        score += min(total_count * 2, 25)  # Up to 25 points for quantity
        
        return min(score, 100.0)
    
    def _calculate_planning_feasibility_score(self, neighborhood: Neighborhood) -> float:
        """Calculate development feasibility score (0-100)."""
        score = 70.0  # Base score assuming generally feasible
        
        # Historic district restrictions
        if neighborhood.historic_district:
            score -= 30
        
        # Planning constraints
        constraint_count = len(neighborhood.planning_constraints)
        score -= min(constraint_count * 10, 30)
        
        # Maximum building height
        if neighborhood.max_building_height_m:
            if neighborhood.max_building_height_m >= 50:
                score += 15  # High-rise allowed
            elif neighborhood.max_building_height_m >= 30:
                score += 10  # Mid-rise allowed
            elif neighborhood.max_building_height_m < 15:
                score -= 20  # Low height restrictions
        
        # Zoning classification
        if neighborhood.zoning_classification:
            if 'residential' in neighborhood.zoning_classification.lower():
                score += 10
            elif 'commercial' in neighborhood.zoning_classification.lower():
                score -= 5
        
        return max(0, min(score, 100.0))
    
    def _calculate_competition_score(self, neighborhood: Neighborhood) -> float:
        """Calculate competition score (0-100, higher = less competition)."""
        centroid = neighborhood.boundaries.centroid
        
        # Count existing student accommodation within area
        competing_pois = PointOfInterest.objects.filter(
            group=neighborhood.group,
            poi_type='dormitory',
            location__distance_lte=(centroid, Distance(km=2.0))
        )
        
        competition_count = competing_pois.count()
        
        # Calculate total competing beds if capacity data available
        total_competing_beds = sum(
            poi.capacity for poi in competing_pois 
            if poi.capacity
        )
        
        # Base score (assumes moderate competition)
        score = 60.0
        
        # Adjust based on number of competitors
        score -= min(competition_count * 15, 45)
        
        # Adjust based on total bed capacity
        if total_competing_beds > 0:
            if total_competing_beds > 2000:
                score -= 20
            elif total_competing_beds > 1000:
                score -= 10
            elif total_competing_beds < 300:
                score += 15
        
        return max(0, min(score, 100.0))
    
    def _count_transport_links(self, neighborhood: Neighborhood) -> int:
        """Count transport links in and around neighborhood."""
        centroid = neighborhood.boundaries.centroid
        return PointOfInterest.objects.filter(
            group=neighborhood.group,
            poi_type__in=['metro', 'train', 'bus', 'transport'],
            location__distance_lte=(centroid, Distance(km=1.5))
        ).count()
    
    def _count_amenities(self, neighborhood: Neighborhood) -> int:
        """Count relevant amenities in neighborhood."""
        centroid = neighborhood.boundaries.centroid
        amenity_types = ['grocery', 'restaurant', 'shopping', 'library', 'sports', 'healthcare']
        return PointOfInterest.objects.filter(
            group=neighborhood.group,
            poi_type__in=amenity_types,
            location__distance_lte=(centroid, Distance(km=1.0))
        ).count()
    
    def _get_data_sources(self) -> List[str]:
        """Get list of data sources used in calculations."""
        return [
            'POI Database',
            'University Database', 
            'Planning Database',
            'Geographic Analysis',
            f'Calculated: {timezone.now().strftime("%Y-%m-%d")}'
        ]
    
    def batch_calculate_scores(self, neighborhoods: QuerySet[Neighborhood]) -> Dict[str, Any]:
        """
        Calculate scores for multiple neighborhoods in batch.
        
        Args:
            neighborhoods: QuerySet of neighborhoods to score
            
        Returns:
            Summary statistics of the scoring operation
        """
        results = {
            'processed': 0,
            'updated': 0,
            'errors': [],
            'score_distribution': {
                'high': 0,    # 80+
                'moderate': 0, # 60-79
                'low': 0,     # 40-59
                'poor': 0     # <40
            }
        }
        
        for neighborhood in neighborhoods:
            try:
                self.calculate_neighborhood_scores(neighborhood)
                results['processed'] += 1
                results['updated'] += 1
                
                # Update distribution
                score = neighborhood.metrics.overall_score
                if score >= 80:
                    results['score_distribution']['high'] += 1
                elif score >= 60:
                    results['score_distribution']['moderate'] += 1
                elif score >= 40:
                    results['score_distribution']['low'] += 1
                else:
                    results['score_distribution']['poor'] += 1
                    
            except Exception as e:
                error_msg = f"Error processing neighborhood {neighborhood.name}: {str(e)}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
                results['processed'] += 1
        
        return results