"""
Geographic Intelligence Service for PBSA investment analysis.

Provides comprehensive geographic scoring and analysis capabilities including
POI analysis, neighborhood evaluation, and market intelligence for investment decisions.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime

from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.measure import Distance
from django.db.models import QuerySet, Count, Avg, Max, Min
from django.utils import timezone

from accounts.models import Group, User
from ..models import (
    PointOfInterest, POIType, University, Neighborhood, 
    NeighborhoodMetrics, PBSAMarketAnalysis
)

logger = logging.getLogger(__name__)


class GeographicIntelligenceService:
    """
    Main service for geographic intelligence operations.
    
    Provides high-level geographic analysis and coordination between
    various geographic intelligence components.
    """
    
    def __init__(self, group: Group):
        """Initialize service for a specific group."""
        self.group = group
    
    def analyze_location(self, 
                        lat: float, 
                        lng: float, 
                        radius_km: float = 5.0) -> Dict[str, Any]:
        """
        Perform comprehensive location analysis for a given point.
        
        Args:
            lat: Latitude coordinate
            lng: Longitude coordinate  
            radius_km: Analysis radius in kilometers
            
        Returns:
            Dictionary containing comprehensive location analysis
        """
        point = Point(lng, lat, srid=4326)
        
        analysis = {
            'location': {'lat': lat, 'lng': lng},
            'radius_km': radius_km,
            'analysis_date': timezone.now().isoformat(),
            'universities': self._analyze_universities(point, radius_km),
            'pois': self._analyze_pois(point, radius_km),
            'neighborhoods': self._analyze_neighborhoods(point, radius_km),
            'accessibility_score': 0,
            'investment_potential': 'unknown'
        }
        
        # Calculate overall accessibility score
        analysis['accessibility_score'] = self._calculate_accessibility_score(analysis)
        
        # Determine investment potential
        analysis['investment_potential'] = self._assess_investment_potential(analysis)
        
        return analysis
    
    def _analyze_universities(self, point: Point, radius_km: float) -> Dict[str, Any]:
        """Analyze universities within radius of the point."""
        universities = University.objects.filter(
            group=self.group,
            main_campus__location__distance_lte=(point, Distance(km=radius_km))
        ).select_related('main_campus')
        
        university_data = []
        total_students = 0
        international_students = 0
        
        for uni in universities:
            distance = uni.main_campus.location.distance(point) * 100  # Convert to km
            uni_data = {
                'name': uni.name,
                'type': uni.university_type,
                'total_students': uni.total_students,
                'international_students': uni.international_students or 0,
                'international_percentage': uni.international_percentage,
                'accommodation_shortage': uni.accommodation_shortage,
                'distance_km': round(distance, 2),
                'ranking_national': uni.ranking_national,
                'website': uni.website
            }
            university_data.append(uni_data)
            total_students += uni.total_students
            international_students += uni.international_students or 0
        
        return {
            'count': len(university_data),
            'universities': university_data,
            'total_students_in_area': total_students,
            'total_international_students': international_students,
            'average_distance_km': round(
                sum(u['distance_km'] for u in university_data) / max(len(university_data), 1), 2
            ),
            'largest_university': max(university_data, key=lambda x: x['total_students'])['name'] 
            if university_data else None
        }
    
    def _analyze_pois(self, point: Point, radius_km: float) -> Dict[str, Any]:
        """Analyze points of interest within radius."""
        pois = PointOfInterest.objects.filter(
            group=self.group,
            location__distance_lte=(point, Distance(km=radius_km))
        )
        
        poi_analysis = {}
        
        # Group POIs by type
        for poi_type in POIType.choices:
            type_code = poi_type[0]
            type_pois = pois.filter(poi_type=type_code)
            
            poi_analysis[type_code] = {
                'count': type_pois.count(),
                'closest_distance_km': None,
                'average_distance_km': None,
                'pois': []
            }
            
            if type_pois.exists():
                poi_data = []
                distances = []
                
                for poi in type_pois[:10]:  # Limit to 10 closest
                    distance = poi.location.distance(point) * 100  # Convert to km
                    distances.append(distance)
                    poi_data.append({
                        'name': poi.name,
                        'address': poi.address,
                        'distance_km': round(distance, 2),
                        'verified': poi.verified
                    })
                
                poi_analysis[type_code].update({
                    'closest_distance_km': round(min(distances), 2),
                    'average_distance_km': round(sum(distances) / len(distances), 2),
                    'pois': poi_data
                })
        
        # Calculate convenience score based on POI availability
        convenience_score = self._calculate_convenience_score(poi_analysis)
        
        return {
            'by_type': poi_analysis,
            'total_pois': pois.count(),
            'convenience_score': convenience_score
        }
    
    def _analyze_neighborhoods(self, point: Point, radius_km: float) -> Dict[str, Any]:
        """Analyze neighborhoods that intersect with the search area."""
        # Find neighborhoods that contain the point or are within radius
        neighborhoods = Neighborhood.objects.filter(
            group=self.group,
            boundaries__distance_lte=(point, Distance(km=radius_km))
        ).select_related('metrics', 'primary_university')
        
        neighborhood_data = []
        
        for neighborhood in neighborhoods:
            # Calculate distance from point to neighborhood centroid
            centroid = neighborhood.boundaries.centroid
            distance = centroid.distance(point) * 100  # Convert to km
            
            neighborhood_data.append({
                'name': neighborhood.name,
                'description': neighborhood.description,
                'distance_km': round(distance, 2),
                'area_sqkm': neighborhood.area_sqkm,
                'metrics': {
                    'overall_score': neighborhood.metrics.overall_score,
                    'accessibility_score': neighborhood.metrics.accessibility_score,
                    'university_proximity_score': neighborhood.metrics.university_proximity_score,
                    'amenities_score': neighborhood.metrics.amenities_score,
                    'affordability_score': neighborhood.metrics.affordability_score,
                    'safety_score': neighborhood.metrics.safety_score,
                    'planning_feasibility_score': neighborhood.metrics.planning_feasibility_score
                },
                'investment_rationale': neighborhood.investment_rationale,
                'primary_university': neighborhood.primary_university.name if neighborhood.primary_university else None,
                'historic_district': neighborhood.historic_district,
                'planning_constraints': neighborhood.planning_constraints
            })
        
        # Sort by overall score
        neighborhood_data.sort(key=lambda x: x['metrics']['overall_score'], reverse=True)
        
        return {
            'count': len(neighborhood_data),
            'neighborhoods': neighborhood_data,
            'best_neighborhood': neighborhood_data[0] if neighborhood_data else None,
            'average_score': round(
                sum(n['metrics']['overall_score'] for n in neighborhood_data) / max(len(neighborhood_data), 1), 1
            )
        }
    
    def _calculate_accessibility_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate overall accessibility score based on analysis results."""
        score = 0.0
        
        # University proximity (40% weight)
        uni_data = analysis['universities']
        if uni_data['count'] > 0:
            # Higher score for closer universities and more students
            avg_distance = uni_data['average_distance_km']
            student_factor = min(uni_data['total_students_in_area'] / 10000, 1.0)
            proximity_score = max(0, (5.0 - avg_distance) / 5.0) * 40
            score += proximity_score * (0.7 + 0.3 * student_factor)
        
        # Transport accessibility (30% weight)
        transport_pois = analysis['pois']['by_type']
        transport_score = 0
        for poi_type in ['metro', 'train', 'bus', 'transport']:
            if transport_pois.get(poi_type, {}).get('count', 0) > 0:
                closest = transport_pois[poi_type]['closest_distance_km']
                transport_score += max(0, (2.0 - closest) / 2.0) * 10
        score += min(transport_score, 30)
        
        # Amenities (20% weight)
        amenity_types = ['shopping', 'grocery', 'restaurant', 'library', 'sports', 'healthcare']
        amenity_score = 0
        for poi_type in amenity_types:
            if transport_pois.get(poi_type, {}).get('count', 0) > 0:
                amenity_score += 3.33  # 20 / 6 types
        score += min(amenity_score, 20)
        
        # Neighborhood quality (10% weight)
        if analysis['neighborhoods']['count'] > 0:
            avg_neighborhood_score = analysis['neighborhoods']['average_score']
            score += (avg_neighborhood_score / 100) * 10
        
        return round(min(score, 100), 1)
    
    def _calculate_convenience_score(self, poi_analysis: Dict[str, Any]) -> float:
        """Calculate convenience score based on POI availability."""
        essential_pois = ['grocery', 'restaurant', 'transport', 'metro', 'bus']
        lifestyle_pois = ['shopping', 'nightlife', 'sports', 'park']
        
        essential_score = 0
        lifestyle_score = 0
        
        # Essential POIs (70% weight)
        for poi_type in essential_pois:
            if poi_analysis.get(poi_type, {}).get('count', 0) > 0:
                essential_score += 14  # 70 / 5 types
        
        # Lifestyle POIs (30% weight)
        for poi_type in lifestyle_pois:
            if poi_analysis.get(poi_type, {}).get('count', 0) > 0:
                lifestyle_score += 7.5  # 30 / 4 types
        
        return round(min(essential_score + lifestyle_score, 100), 1)
    
    def _assess_investment_potential(self, analysis: Dict[str, Any]) -> str:
        """Assess overall investment potential based on analysis."""
        score = analysis['accessibility_score']
        university_count = analysis['universities']['count']
        total_students = analysis['universities']['total_students_in_area']
        
        # High potential criteria
        if (score >= 80 and university_count >= 2 and total_students >= 15000):
            return 'high'
        elif (score >= 65 and university_count >= 1 and total_students >= 8000):
            return 'moderate'
        elif (score >= 50 and university_count >= 1):
            return 'low'
        else:
            return 'minimal'
    
    def find_optimal_locations(self, 
                              city: str,
                              max_results: int = 10,
                              min_students: int = 5000,
                              max_distance_from_uni: float = 3.0) -> List[Dict[str, Any]]:
        """
        Find optimal locations for PBSA development in a city.
        
        Args:
            city: City name to search in
            max_results: Maximum number of results to return
            min_students: Minimum student population requirement
            max_distance_from_uni: Maximum distance from university in km
            
        Returns:
            List of optimal location recommendations
        """
        # Find universities in the city
        universities = University.objects.filter(
            group=self.group,
            main_campus__address__icontains=city,
            total_students__gte=min_students
        ).select_related('main_campus')
        
        optimal_locations = []
        
        for university in universities:
            # Analyze area around university
            uni_location = university.main_campus.location
            analysis = self.analyze_location(
                uni_location.y, 
                uni_location.x, 
                max_distance_from_uni
            )
            
            # Find best neighborhoods near this university
            neighborhoods = analysis['neighborhoods']['neighborhoods']
            for neighborhood in neighborhoods[:3]:  # Top 3 per university
                optimal_locations.append({
                    'location': {
                        'lat': uni_location.y,
                        'lng': uni_location.x
                    },
                    'university': university.name,
                    'neighborhood': neighborhood['name'],
                    'overall_score': neighborhood['metrics']['overall_score'],
                    'accessibility_score': analysis['accessibility_score'],
                    'student_population': university.total_students,
                    'investment_potential': analysis['investment_potential'],
                    'key_factors': self._extract_key_factors(analysis, neighborhood)
                })
        
        # Sort by overall score and return top results
        optimal_locations.sort(key=lambda x: x['overall_score'], reverse=True)
        return optimal_locations[:max_results]
    
    def _extract_key_factors(self, analysis: Dict[str, Any], neighborhood: Dict[str, Any]) -> List[str]:
        """Extract key factors that make a location attractive."""
        factors = []
        
        if analysis['universities']['count'] > 1:
            factors.append(f"Multiple universities ({analysis['universities']['count']})")
        
        if analysis['accessibility_score'] >= 80:
            factors.append("Excellent accessibility")
        
        if neighborhood['metrics']['university_proximity_score'] >= 90:
            factors.append("Very close to university")
        
        if neighborhood['metrics']['amenities_score'] >= 80:
            factors.append("Rich amenities")
        
        if neighborhood['metrics']['planning_feasibility_score'] >= 80:
            factors.append("Development-friendly planning")
        
        if not neighborhood['historic_district']:
            factors.append("No historic restrictions")
        
        return factors