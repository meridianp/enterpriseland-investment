"""
Geographic Intelligence serializers for API endpoints.

Provides comprehensive serialization for POIs, universities, neighborhoods,
and market analysis data for the PBSA investment platform.
"""

from rest_framework import serializers
from platform_core.core.serializers import PlatformSerializer
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from django.contrib.gis.geos import Point, Polygon

from .models import (
    PointOfInterest, University, UniversityCampus, NeighborhoodMetrics,
    Neighborhood, PBSAMarketAnalysis, MarketAnalysisNeighborhood,
    MarketAnalysisUniversity, POIType, UniversityType
)


class PointOfInterestSerializer(GeoFeatureModelSerializer):
    """Serializer for Point of Interest with GeoJSON support."""
    
    poi_type_display = serializers.CharField(source='get_poi_type_display', read_only=True)
    
    class Meta:
        model = PointOfInterest
        geo_field = 'location'
        fields = [
            'id', 'name', 'address', 'poi_type', 'poi_type_display', 'description',
            'website', 'capacity', 'operating_hours', 'accessibility_features',
            'verified', 'data_source', 'created_at', 'updated_at'
        ]


class PointOfInterestCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating POIs with latitude/longitude."""
    
    latitude = serializers.FloatField(write_only=True)
    longitude = serializers.FloatField(write_only=True)
    
    class Meta:
        model = PointOfInterest
        fields = [
            'name', 'address', 'latitude', 'longitude', 'poi_type', 'description',
            'website', 'capacity', 'operating_hours', 'accessibility_features',
            'verified', 'data_source'
        ]
    
    def create(self, validated_data):
        lat = validated_data.pop('latitude')
        lng = validated_data.pop('longitude')
        validated_data['location'] = Point(lng, lat, srid=4326)
        return super().create(validated_data)


class UniversityCampusSerializer(serializers.ModelSerializer):
    """Serializer for university campus relationships."""
    
    campus = PointOfInterestSerializer(read_only=True)
    
    class Meta:
        model = UniversityCampus
        fields = ['campus', 'is_main', 'student_count']


class UniversitySerializer(serializers.ModelSerializer):
    """Serializer for University data."""
    
    university_type_display = serializers.CharField(source='get_university_type_display', read_only=True)
    main_campus = PointOfInterestSerializer(read_only=True)
    campuses = UniversityCampusSerializer(many=True, read_only=True)
    international_percentage = serializers.FloatField(read_only=True)
    accommodation_shortage = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = University
        fields = [
            'id', 'name', 'university_type', 'university_type_display',
            'total_students', 'international_students', 'postgraduate_students',
            'main_campus', 'campuses', 'campus_boundaries', 'programs',
            'ranking_national', 'ranking_global', 'expansion_plans',
            'student_growth_rate', 'website', 'accommodation_office_url',
            'on_campus_beds', 'accommodation_guarantee', 'international_percentage',
            'accommodation_shortage', 'created_at', 'updated_at'
        ]


class NeighborhoodMetricsSerializer(serializers.ModelSerializer):
    """Serializer for neighborhood metrics."""
    
    class Meta:
        model = NeighborhoodMetrics
        fields = [
            'id', 'accessibility_score', 'university_proximity_score',
            'amenities_score', 'affordability_score', 'safety_score',
            'cultural_score', 'planning_feasibility_score', 'competition_score',
            'overall_score', 'score_weights', 'average_rent_psf',
            'transport_links_count', 'amenities_count', 'crime_rate_percentile',
            'calculation_date', 'data_sources'
        ]


class NeighborhoodSerializer(GeoFeatureModelSerializer):
    """Serializer for Neighborhood with GeoJSON support."""
    
    metrics = NeighborhoodMetricsSerializer(read_only=True)
    primary_university = UniversitySerializer(read_only=True)
    
    class Meta:
        model = Neighborhood
        geo_field = 'boundaries'
        fields = [
            'id', 'name', 'description', 'area_sqkm', 'metrics',
            'historic_district', 'planning_constraints', 'zoning_classification',
            'max_building_height_m', 'investment_rationale',
            'development_opportunities', 'average_land_price_psf',
            'primary_university', 'created_at', 'updated_at'
        ]


class NeighborhoodListSerializer(serializers.ModelSerializer):
    """Simplified serializer for neighborhood lists without geometry."""
    
    overall_score = serializers.FloatField(source='metrics.overall_score', read_only=True)
    accessibility_score = serializers.FloatField(source='metrics.accessibility_score', read_only=True)
    university_proximity_score = serializers.FloatField(source='metrics.university_proximity_score', read_only=True)
    primary_university_name = serializers.CharField(source='primary_university.name', read_only=True)
    
    class Meta:
        model = Neighborhood
        fields = [
            'id', 'name', 'description', 'area_sqkm', 'overall_score',
            'accessibility_score', 'university_proximity_score',
            'historic_district', 'investment_rationale', 'primary_university_name'
        ]


class MarketAnalysisNeighborhoodSerializer(serializers.ModelSerializer):
    """Serializer for market analysis neighborhood relationships."""
    
    neighborhood = NeighborhoodListSerializer(read_only=True)
    
    class Meta:
        model = MarketAnalysisNeighborhood
        fields = ['neighborhood', 'rank']


class MarketAnalysisUniversitySerializer(serializers.ModelSerializer):
    """Serializer for market analysis university relationships."""
    
    university = UniversitySerializer(read_only=True)
    
    class Meta:
        model = MarketAnalysisUniversity
        fields = ['university']


class PBSAMarketAnalysisSerializer(serializers.ModelSerializer):
    """Serializer for PBSA market analysis."""
    
    neighborhoods = MarketAnalysisNeighborhoodSerializer(many=True, read_only=True)
    universities = MarketAnalysisUniversitySerializer(many=True, read_only=True)
    market_maturity = serializers.CharField(read_only=True)
    supply_shortage = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = PBSAMarketAnalysis
        fields = [
            'id', 'city', 'country', 'analysis_date', 'total_student_population',
            'international_student_percentage', 'existing_pbsa_beds', 'pipeline_beds',
            'estimated_demand', 'supply_demand_ratio', 'average_occupancy_rate',
            'average_rent_per_week', 'rent_growth_rate', 'market_summary',
            'key_trends', 'opportunities', 'risks', 'top_neighborhoods',
            'neighborhood_count', 'methodology', 'data_sources', 'version',
            'is_published', 'market_maturity', 'supply_shortage',
            'neighborhoods', 'universities', 'created_at', 'updated_at'
        ]


class LocationAnalysisInputSerializer(serializers.Serializer):
    """Serializer for location analysis input parameters."""
    
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    radius_km = serializers.FloatField(default=5.0, min_value=0.1, max_value=50.0)


class LocationAnalysisResultSerializer(serializers.Serializer):
    """Serializer for location analysis results."""
    
    location = serializers.DictField()
    radius_km = serializers.FloatField()
    analysis_date = serializers.CharField()
    universities = serializers.DictField()
    pois = serializers.DictField()
    neighborhoods = serializers.DictField()
    accessibility_score = serializers.FloatField()
    investment_potential = serializers.CharField()


class OptimalLocationInputSerializer(serializers.Serializer):
    """Serializer for optimal location finder input."""
    
    city = serializers.CharField(max_length=100)
    max_results = serializers.IntegerField(default=10, min_value=1, max_value=50)
    min_students = serializers.IntegerField(default=5000, min_value=1000)
    max_distance_from_uni = serializers.FloatField(default=3.0, min_value=0.5, max_value=10.0)


class OptimalLocationResultSerializer(serializers.Serializer):
    """Serializer for optimal location results."""
    
    location = serializers.DictField()
    university = serializers.CharField()
    neighborhood = serializers.CharField()
    overall_score = serializers.FloatField()
    accessibility_score = serializers.FloatField()
    student_population = serializers.IntegerField()
    investment_potential = serializers.CharField()
    key_factors = serializers.ListField(child=serializers.CharField())


class NeighborhoodScoringInputSerializer(serializers.Serializer):
    """Serializer for neighborhood scoring input."""
    
    neighborhood_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=True,
        required=False,
        help_text="List of neighborhood IDs to score. If empty, scores all neighborhoods."
    )
    
    force_recalculation = serializers.BooleanField(
        default=False,
        help_text="Whether to force recalculation even if scores are recent"
    )


class SimplePOISerializer(serializers.Serializer):
    """Simple POI serializer for clustering without GeoJSON."""
    id = serializers.CharField()
    name = serializers.CharField()
    poi_type = serializers.CharField()
    location = serializers.ListField(child=serializers.FloatField(), min_length=2, max_length=2)


class POIClusterSerializer(serializers.Serializer):
    """Serializer for POI clustering data."""
    
    cluster_id = serializers.CharField()
    center = serializers.ListField(child=serializers.FloatField(), min_length=2, max_length=2)
    count = serializers.IntegerField()
    poi_types = serializers.ListField(child=serializers.CharField())
    pois = SimplePOISerializer(many=True, required=False)


class HeatMapDataSerializer(serializers.Serializer):
    """Serializer for heat map data points."""
    
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    intensity = serializers.FloatField()
    score_type = serializers.CharField()
    value = serializers.FloatField()
    metadata = serializers.DictField(required=False)