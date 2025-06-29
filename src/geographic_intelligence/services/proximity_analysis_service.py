"""
Proximity Analysis Service for geographic intelligence.

Provides distance calculations, travel time estimation, and accessibility analysis
for PBSA investment decisions.
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
    PointOfInterest, POIType, University, Neighborhood
)

logger = logging.getLogger(__name__)


class ProximityAnalysisService:
    """
    Service for analyzing proximity and accessibility between locations.
    
    Provides distance calculations, travel time estimates, and accessibility scoring
    for investment analysis.
    """
    
    def __init__(self, group: Group = None):
        """Initialize service for a specific group."""
        self.group = group
    
    def calculate_walking_distance(self, point1: Point, point2: Point) -> float:
        """
        Calculate estimated walking distance between two points.
        
        Args:
            point1: Starting point
            point2: Destination point
            
        Returns:
            Distance in kilometers (straight-line distance * walking factor)
        """
        straight_distance = point1.distance(point2) * 100  # Convert to km
        # Apply walking factor (streets aren't straight lines)
        walking_factor = 1.3
        return straight_distance * walking_factor
    
    def get_nearest_pois(self, 
                        location: Point, 
                        poi_type: str, 
                        max_distance_km: float = 5.0,
                        limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get nearest POIs of a specific type from a location.
        
        Args:
            location: Starting location
            poi_type: Type of POI to search for
            max_distance_km: Maximum search radius
            limit: Maximum number of results
            
        Returns:
            List of POI data with distances
        """
        pois = PointOfInterest.objects.filter(
            group=self.group,
            poi_type=poi_type,
            location__distance_lte=(location, Distance(km=max_distance_km))
        ).order_by('location')[:limit]
        
        results = []
        for poi in pois:
            distance_km = self.calculate_walking_distance(location, poi.location)
            walking_time_minutes = self._estimate_walking_time(distance_km)
            
            results.append({
                'poi': {
                    'id': str(poi.id),
                    'name': poi.name,
                    'address': poi.address,
                    'poi_type': poi.poi_type,
                    'verified': poi.verified
                },
                'distance_km': round(distance_km, 2),
                'walking_time_minutes': walking_time_minutes,
                'coordinates': {
                    'lat': poi.location.y,
                    'lng': poi.location.x
                }
            })
        
        return results
    
    def calculate_accessibility_score(self, 
                                    location: Point,
                                    weight_factors: Dict[str, float] = None) -> Dict[str, Any]:
        """
        Calculate comprehensive accessibility score for a location.
        
        Args:
            location: Location to analyze
            weight_factors: Custom weights for different POI types
            
        Returns:
            Accessibility analysis with scores and details
        """
        if not weight_factors:
            weight_factors = {
                'university': 0.30,
                'transport': 0.25,
                'metro': 0.25,
                'bus': 0.15,
                'grocery': 0.15,
                'restaurant': 0.10,
                'shopping': 0.10,
                'library': 0.05,
                'sports': 0.05,
                'healthcare': 0.10
            }
        
        accessibility_data = {
            'location': {'lat': location.y, 'lng': location.x},
            'analysis_date': timezone.now().isoformat(),
            'poi_analysis': {},
            'overall_score': 0.0,
            'transport_score': 0.0,
            'amenities_score': 0.0,
            'academic_score': 0.0
        }
        
        total_weighted_score = 0.0
        total_weights = 0.0
        
        # Analyze each POI type
        for poi_type, weight in weight_factors.items():
            nearest_pois = self.get_nearest_pois(location, poi_type, max_distance_km=3.0, limit=5)
            
            if nearest_pois:
                # Score based on proximity of closest POI
                closest_distance = nearest_pois[0]['distance_km']
                proximity_score = max(0, (3.0 - closest_distance) / 3.0) * 100
                
                # Bonus for multiple options
                count_bonus = min(len(nearest_pois) * 10, 30)
                type_score = min(proximity_score + count_bonus, 100)
                
                total_weighted_score += type_score * weight
                total_weights += weight
                
                accessibility_data['poi_analysis'][poi_type] = {
                    'count': len(nearest_pois),
                    'closest_distance_km': closest_distance,
                    'score': round(type_score, 1),
                    'nearest_pois': nearest_pois
                }
            else:
                accessibility_data['poi_analysis'][poi_type] = {
                    'count': 0,
                    'closest_distance_km': None,
                    'score': 0.0,
                    'nearest_pois': []
                }
        
        # Calculate component scores
        transport_types = ['transport', 'metro', 'bus']
        amenity_types = ['grocery', 'restaurant', 'shopping', 'sports', 'healthcare']
        academic_types = ['university', 'library']
        
        accessibility_data['transport_score'] = self._calculate_component_score(
            accessibility_data['poi_analysis'], transport_types
        )
        accessibility_data['amenities_score'] = self._calculate_component_score(
            accessibility_data['poi_analysis'], amenity_types
        )
        accessibility_data['academic_score'] = self._calculate_component_score(
            accessibility_data['poi_analysis'], academic_types
        )
        
        # Overall score
        if total_weights > 0:
            accessibility_data['overall_score'] = round(total_weighted_score / total_weights, 1)
        
        return accessibility_data
    
    def find_optimal_radius(self, 
                           location: Point, 
                           target_poi_counts: Dict[str, int],
                           max_radius_km: float = 10.0) -> Dict[str, Any]:
        """
        Find optimal radius that captures desired POI counts.
        
        Args:
            location: Center location
            target_poi_counts: Target counts for each POI type
            max_radius_km: Maximum search radius
            
        Returns:
            Analysis of optimal radius for different criteria
        """
        radius_analysis = {
            'location': {'lat': location.y, 'lng': location.x},
            'target_counts': target_poi_counts,
            'optimal_radius_km': 0.0,
            'radius_analysis': [],
            'recommendations': []
        }
        
        # Test different radii
        test_radii = [0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 7.5, 10.0]
        
        for radius in test_radii:
            if radius > max_radius_km:
                break
                
            radius_data = {
                'radius_km': radius,
                'poi_counts': {},
                'targets_met': 0,
                'total_targets': len(target_poi_counts),
                'coverage_percentage': 0.0
            }
            
            targets_met = 0
            for poi_type, target_count in target_poi_counts.items():
                actual_count = PointOfInterest.objects.filter(
                    group=self.group,
                    poi_type=poi_type,
                    location__distance_lte=(location, Distance(km=radius))
                ).count()
                
                radius_data['poi_counts'][poi_type] = actual_count
                if actual_count >= target_count:
                    targets_met += 1
            
            radius_data['targets_met'] = targets_met
            radius_data['coverage_percentage'] = (targets_met / len(target_poi_counts)) * 100
            
            radius_analysis['radius_analysis'].append(radius_data)
            
            # Update optimal radius if this is better
            if targets_met > radius_analysis.get('best_targets_met', 0):
                radius_analysis['optimal_radius_km'] = radius
                radius_analysis['best_targets_met'] = targets_met
        
        # Generate recommendations
        if radius_analysis['optimal_radius_km'] > 0:
            optimal_data = next(
                r for r in radius_analysis['radius_analysis'] 
                if r['radius_km'] == radius_analysis['optimal_radius_km']
            )
            
            if optimal_data['coverage_percentage'] >= 80:
                radius_analysis['recommendations'].append(
                    f"Excellent location: {optimal_data['coverage_percentage']:.0f}% targets met within {radius_analysis['optimal_radius_km']}km"
                )
            elif optimal_data['coverage_percentage'] >= 60:
                radius_analysis['recommendations'].append(
                    f"Good location: {optimal_data['coverage_percentage']:.0f}% targets met within {radius_analysis['optimal_radius_km']}km"
                )
            else:
                radius_analysis['recommendations'].append(
                    f"Limited accessibility: Only {optimal_data['coverage_percentage']:.0f}% targets met within {radius_analysis['optimal_radius_km']}km"
                )
        else:
            radius_analysis['recommendations'].append(
                "Poor accessibility: No targets met within maximum search radius"
            )
        
        return radius_analysis
    
    def calculate_catchment_area(self, 
                                university: University,
                                travel_time_minutes: int = 30) -> Dict[str, Any]:
        """
        Calculate catchment area around a university for PBSA analysis.
        
        Args:
            university: University to analyze
            travel_time_minutes: Maximum travel time in minutes
            
        Returns:
            Catchment area analysis with demographic and accessibility data
        """
        # Rough conversion: walking speed ~5km/h, cycling ~15km/h
        walking_radius_km = (travel_time_minutes / 60) * 5
        cycling_radius_km = (travel_time_minutes / 60) * 15
        
        uni_location = university.main_campus.location
        
        catchment_data = {
            'university': {
                'id': str(university.id),
                'name': university.name,
                'total_students': university.total_students,
                'location': {'lat': uni_location.y, 'lng': uni_location.x}
            },
            'travel_time_minutes': travel_time_minutes,
            'walking_radius_km': walking_radius_km,
            'cycling_radius_km': cycling_radius_km,
            'walking_catchment': {},
            'cycling_catchment': {},
            'competitive_analysis': {}
        }
        
        # Analyze walking catchment
        catchment_data['walking_catchment'] = self._analyze_catchment_area(
            uni_location, walking_radius_km
        )
        
        # Analyze cycling catchment
        catchment_data['cycling_catchment'] = self._analyze_catchment_area(
            uni_location, cycling_radius_km
        )
        
        # Competitive analysis - other universities in area
        competing_unis = University.objects.filter(
            group=self.group,
            main_campus__location__distance_lte=(uni_location, Distance(km=cycling_radius_km))
        ).exclude(id=university.id)
        
        catchment_data['competitive_analysis'] = {
            'competing_universities': competing_unis.count(),
            'total_competing_students': sum(uni.total_students for uni in competing_unis),
            'market_share_estimate': university.total_students / (
                university.total_students + sum(uni.total_students for uni in competing_unis)
            ) * 100 if competing_unis.exists() else 100.0
        }
        
        return catchment_data
    
    def _estimate_walking_time(self, distance_km: float) -> int:
        """Estimate walking time in minutes (assumes 5km/h walking speed)."""
        walking_speed_kmh = 5.0
        return int((distance_km / walking_speed_kmh) * 60)
    
    def _calculate_component_score(self, poi_analysis: Dict, poi_types: List[str]) -> float:
        """Calculate average score for a component (transport, amenities, etc.)."""
        relevant_scores = [
            poi_analysis.get(poi_type, {}).get('score', 0.0)
            for poi_type in poi_types
            if poi_type in poi_analysis
        ]
        return round(sum(relevant_scores) / len(relevant_scores), 1) if relevant_scores else 0.0
    
    def _analyze_catchment_area(self, location: Point, radius_km: float) -> Dict[str, Any]:
        """Analyze POIs and amenities within a catchment area."""
        catchment = {
            'radius_km': radius_km,
            'total_pois': 0,
            'poi_breakdown': {},
            'accessibility_indicators': {}
        }
        
        # Count POIs by type
        for poi_type in POIType.values:
            count = PointOfInterest.objects.filter(
                group=self.group,
                poi_type=poi_type,
                location__distance_lte=(location, Distance(km=radius_km))
            ).count()
            
            if count > 0:
                catchment['poi_breakdown'][poi_type] = count
                catchment['total_pois'] += count
        
        # Calculate accessibility indicators
        essential_pois = ['grocery', 'transport', 'metro', 'bus']
        essential_count = sum(
            catchment['poi_breakdown'].get(poi_type, 0)
            for poi_type in essential_pois
        )
        
        catchment['accessibility_indicators'] = {
            'essential_amenities': essential_count,
            'lifestyle_amenities': catchment['total_pois'] - essential_count,
            'amenity_density': round(catchment['total_pois'] / (3.14159 * radius_km ** 2), 2),
            'accessibility_rating': 'High' if essential_count >= 10 else 'Medium' if essential_count >= 5 else 'Low'
        }
        
        return catchment