"""
Geographic Intelligence models for PBSA investment analysis.

Provides comprehensive geographic scoring and analysis capabilities including
Points of Interest (POIs), neighborhood metrics, university data, and market analysis
for Purpose-Built Student Accommodation investments.
"""

import uuid
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Optional, Any

from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import Point, Polygon, MultiPolygon
from django.contrib.gis.measure import Distance
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

from platform_core.accounts.models import User, Group
from assessments.base_models import UUIDModel, TimestampedModel, PlatformModel


class POIType(models.TextChoices):
    """Types of Points of Interest relevant to PBSA investments."""
    UNIVERSITY = 'university', 'University/College'
    DORMITORY = 'dormitory', 'Existing Student Accommodation'
    TRANSPORT_HUB = 'transport', 'Transport Hub'
    METRO_STATION = 'metro', 'Metro/Subway Station'
    BUS_STOP = 'bus', 'Bus Stop'
    TRAIN_STATION = 'train', 'Train Station'
    SHOPPING = 'shopping', 'Shopping Center'
    GROCERY = 'grocery', 'Grocery Store'
    RESTAURANT = 'restaurant', 'Restaurant/Cafe'
    NIGHTLIFE = 'nightlife', 'Nightlife Venue'
    LIBRARY = 'library', 'Library'
    SPORTS = 'sports', 'Sports Facility'
    HEALTHCARE = 'healthcare', 'Healthcare Facility'
    PARK = 'park', 'Park/Recreation'


class UniversityType(models.TextChoices):
    """Types of universities for classification."""
    PUBLIC = 'public', 'Public University'
    PRIVATE = 'private', 'Private University'
    TECHNICAL = 'technical', 'Technical/Vocational'
    COMMUNITY = 'community', 'Community College'
    INTERNATIONAL = 'international', 'International Branch'


class PointOfInterest(UUIDModel, TimestampedModel, PlatformModel):
    """
    Point of Interest (POI) for geographic analysis.
    
    Represents locations relevant to PBSA investment decisions including
    universities, transport hubs, amenities, and competitive accommodations.
    """
    
    name = models.CharField(
        max_length=255,
        help_text="Name of the point of interest"
    )
    
    address = models.TextField(
        help_text="Physical address of the location"
    )
    
    location = gis_models.PointField(
        srid=4326,  # WGS84 coordinate system
        help_text="Geographic coordinates of the POI"
    )
    
    poi_type = models.CharField(
        max_length=20,
        choices=POIType.choices,
        db_index=True,
        help_text="Type of point of interest"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Brief description of the POI"
    )
    
    website = models.URLField(
        blank=True,
        help_text="Official website URL if available"
    )
    
    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Capacity if applicable (e.g., dormitory beds, university enrollment)"
    )
    
    # Additional metadata
    operating_hours = models.JSONField(
        default=dict,
        blank=True,
        help_text="Operating hours by day of week"
    )
    
    accessibility_features = models.JSONField(
        default=list,
        blank=True,
        help_text="List of accessibility features"
    )
    
    verified = models.BooleanField(
        default=False,
        help_text="Whether this POI has been verified"
    )
    
    data_source = models.CharField(
        max_length=100,
        blank=True,
        help_text="Source of the POI data"
    )
    
    class Meta:
        db_table = 'geographic_intelligence_pois'
        indexes = [
            models.Index(fields=['poi_type', 'verified']),
        ]
        verbose_name = "Point of Interest"
        verbose_name_plural = "Points of Interest"
    
    def __str__(self):
        return f"{self.name} ({self.get_poi_type_display()})"
    
    def get_nearby_pois(self, distance_km: float = 1.0, poi_types: List[str] = None):
        """Get nearby POIs within specified distance."""
        queryset = PointOfInterest.objects.filter(
            location__distance_lte=(self.location, Distance(km=distance_km))
        ).exclude(id=self.id)
        
        if poi_types:
            queryset = queryset.filter(poi_type__in=poi_types)
        
        return queryset.order_by('location')


class University(UUIDModel, TimestampedModel, PlatformModel):
    """
    University information for PBSA market analysis.
    
    Comprehensive university data including campuses, student population,
    and expansion plans critical for investment decisions.
    """
    
    name = models.CharField(
        max_length=255,
        help_text="Name of the university"
    )
    
    university_type = models.CharField(
        max_length=20,
        choices=UniversityType.choices,
        default=UniversityType.PUBLIC,
        help_text="Type of university"
    )
    
    # Student population
    total_students = models.PositiveIntegerField(
        help_text="Total student enrollment"
    )
    
    international_students = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of international students"
    )
    
    postgraduate_students = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of postgraduate students"
    )
    
    # Campus information
    main_campus = models.OneToOneField(
        PointOfInterest,
        on_delete=models.PROTECT,
        related_name='main_university',
        help_text="Main campus location"
    )
    
    campus_boundaries = gis_models.MultiPolygonField(
        srid=4326,
        null=True,
        blank=True,
        help_text="Geographic boundaries of all campuses"
    )
    
    # Academic information
    programs = models.JSONField(
        default=list,
        blank=True,
        help_text="List of notable programs/faculties"
    )
    
    ranking_national = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="National ranking position"
    )
    
    ranking_global = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Global ranking position (e.g., QS, Times)"
    )
    
    # Growth and expansion
    expansion_plans = models.TextField(
        blank=True,
        help_text="Description of known expansion plans"
    )
    
    student_growth_rate = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-100), MaxValueValidator(100)],
        help_text="Annual student population growth rate (%)"
    )
    
    # Contact and reference
    website = models.URLField(
        help_text="Official university website"
    )
    
    accommodation_office_url = models.URLField(
        blank=True,
        help_text="Student accommodation office URL"
    )
    
    # Existing accommodation
    on_campus_beds = models.PositiveIntegerField(
        default=0,
        help_text="Number of on-campus accommodation beds"
    )
    
    accommodation_guarantee = models.BooleanField(
        default=False,
        help_text="Whether university guarantees accommodation for first-years"
    )
    
    class Meta:
        db_table = 'geographic_intelligence_universities'
        verbose_name_plural = "Universities"
        indexes = [
            models.Index(fields=['university_type', 'total_students']),
            models.Index(fields=['ranking_national']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.total_students:,} students)"
    
    @property
    def international_percentage(self) -> float:
        """Calculate percentage of international students."""
        if self.international_students and self.total_students > 0:
            return round((self.international_students / self.total_students) * 100, 1)
        return 0.0
    
    @property
    def accommodation_shortage(self) -> int:
        """Estimate accommodation shortage based on student numbers."""
        # Rough estimate: 30% of students need accommodation, minus on-campus beds
        estimated_need = int(self.total_students * 0.3)
        return max(0, estimated_need - self.on_campus_beds)
    
    def add_campus(self, poi: PointOfInterest):
        """Add a campus POI to this university."""
        UniversityCampus.objects.create(
            university=self,
            campus=poi,
            is_main=False
        )


class UniversityCampus(models.Model):
    """Many-to-many relationship between universities and campus POIs."""
    
    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name='campuses'
    )
    
    campus = models.ForeignKey(
        PointOfInterest,
        on_delete=models.CASCADE,
        related_name='universities'
    )
    
    is_main = models.BooleanField(
        default=False,
        help_text="Whether this is the main campus"
    )
    
    student_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of students at this campus"
    )
    
    class Meta:
        db_table = 'geographic_intelligence_university_campuses'
        unique_together = ['university', 'campus']


class NeighborhoodMetrics(UUIDModel, TimestampedModel):
    """
    Metrics for evaluating neighborhoods for PBSA investment.
    
    Comprehensive scoring across multiple dimensions relevant to
    student accommodation success.
    """
    
    # Individual metric scores (0-100)
    accessibility_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Score for transport accessibility (0-100)"
    )
    
    university_proximity_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Score for proximity to universities (0-100)"
    )
    
    amenities_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Score for student amenities availability (0-100)"
    )
    
    affordability_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Score for housing affordability (0-100)"
    )
    
    safety_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Score for neighborhood safety (0-100)"
    )
    
    cultural_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Score for cultural and leisure options (0-100)"
    )
    
    planning_feasibility_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Score for development feasibility (0-100)"
    )
    
    competition_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=50.0,
        help_text="Score based on competitive landscape (0-100, higher = less competition)"
    )
    
    # Calculated overall score
    overall_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Weighted overall investment score (0-100)"
    )
    
    # Score weights for calculation
    score_weights = models.JSONField(
        default=dict,
        help_text="Weights used for overall score calculation"
    )
    
    # Supporting metrics
    average_rent_psf = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Average rent per square foot in the area"
    )
    
    transport_links_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of public transport links"
    )
    
    amenities_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of relevant amenities"
    )
    
    crime_rate_percentile = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Crime rate percentile (0=lowest, 100=highest crime)"
    )
    
    # Metadata
    calculation_date = models.DateTimeField(
        default=timezone.now,
        help_text="When these metrics were calculated"
    )
    
    data_sources = models.JSONField(
        default=list,
        help_text="List of data sources used"
    )
    
    class Meta:
        db_table = 'geographic_intelligence_neighborhood_metrics'
        ordering = ['-overall_score']
    
    def calculate_overall_score(self, weights: Dict[str, float] = None):
        """Calculate weighted overall score."""
        if not weights:
            weights = {
                'accessibility': 0.20,
                'university_proximity': 0.25,
                'amenities': 0.15,
                'affordability': 0.10,
                'safety': 0.15,
                'cultural': 0.05,
                'planning_feasibility': 0.05,
                'competition': 0.05
            }
        
        self.score_weights = weights
        
        total_score = (
            self.accessibility_score * weights.get('accessibility', 0) +
            self.university_proximity_score * weights.get('university_proximity', 0) +
            self.amenities_score * weights.get('amenities', 0) +
            self.affordability_score * weights.get('affordability', 0) +
            self.safety_score * weights.get('safety', 0) +
            self.cultural_score * weights.get('cultural', 0) +
            self.planning_feasibility_score * weights.get('planning_feasibility', 0) +
            self.competition_score * weights.get('competition', 0)
        )
        
        self.overall_score = round(total_score, 1)
        return self.overall_score


class Neighborhood(UUIDModel, TimestampedModel, PlatformModel):
    """
    Neighborhood definition for PBSA investment analysis.
    
    Represents geographic areas with boundaries, metrics, and
    investment potential for student accommodation.
    """
    
    name = models.CharField(
        max_length=255,
        help_text="Name of the neighborhood"
    )
    
    description = models.TextField(
        help_text="Brief description of the neighborhood"
    )
    
    # Geographic boundaries
    boundaries = gis_models.PolygonField(
        srid=4326,
        help_text="Geographic boundaries of the neighborhood"
    )
    
    area_sqkm = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Area in square kilometers"
    )
    
    # Metrics
    metrics = models.OneToOneField(
        NeighborhoodMetrics,
        on_delete=models.CASCADE,
        related_name='neighborhood',
        help_text="Evaluation metrics for the neighborhood"
    )
    
    # Planning and development
    historic_district = models.BooleanField(
        default=False,
        help_text="Whether the neighborhood is designated as a historic district"
    )
    
    planning_constraints = models.JSONField(
        default=list,
        blank=True,
        help_text="List of planning constraints if any"
    )
    
    zoning_classification = models.CharField(
        max_length=50,
        blank=True,
        help_text="Zoning classification code"
    )
    
    max_building_height_m = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Maximum allowed building height in meters"
    )
    
    # Investment analysis
    investment_rationale = models.TextField(
        help_text="Rationale for investment potential"
    )
    
    development_opportunities = models.PositiveIntegerField(
        default=0,
        help_text="Number of identified development opportunities"
    )
    
    average_land_price_psf = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Average land price per square foot"
    )
    
    # Relationships
    primary_university = models.ForeignKey(
        University,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='primary_neighborhoods',
        help_text="Primary university serving this neighborhood"
    )
    
    class Meta:
        db_table = 'geographic_intelligence_neighborhoods'
        indexes = [
            models.Index(fields=['name']),
        ]
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} (Score: {self.metrics.overall_score})"
    
    def calculate_area(self):
        """Calculate and store area of the neighborhood."""
        if self.boundaries:
            # Convert to appropriate projection for area calculation
            self.area_sqkm = self.boundaries.transform(3857, clone=True).area / 1000000
            return self.area_sqkm
        return None
    
    def get_pois_within(self, poi_types: List[str] = None):
        """Get all POIs within neighborhood boundaries."""
        queryset = PointOfInterest.objects.filter(
            group=self.group,
            location__within=self.boundaries
        )
        
        if poi_types:
            queryset = queryset.filter(poi_type__in=poi_types)
        
        return queryset
    
    def get_nearby_universities(self, max_distance_km: float = 5.0):
        """Get universities within specified distance of neighborhood."""
        return University.objects.filter(
            group=self.group,
            main_campus__location__distance_lte=(
                self.boundaries.centroid,
                Distance(km=max_distance_km)
            )
        ).order_by('main_campus__location')
    
    def update_metrics(self):
        """Update neighborhood metrics based on current data."""
        from .services import NeighborhoodScoringService
        
        service = NeighborhoodScoringService()
        service.calculate_neighborhood_scores(self)


class PBSAMarketAnalysis(UUIDModel, TimestampedModel, PlatformModel):
    """
    Complete PBSA market analysis for a city or region.
    
    Aggregates neighborhood and university data to provide
    comprehensive market insights for investment decisions.
    """
    
    # Basic information
    city = models.CharField(
        max_length=100,
        help_text="Target city name"
    )
    
    country = models.CharField(
        max_length=2,
        help_text="Country code (ISO 3166-1 alpha-2)"
    )
    
    analysis_date = models.DateField(
        default=timezone.now,
        help_text="Date when the analysis was generated"
    )
    
    # Market overview
    total_student_population = models.PositiveIntegerField(
        help_text="Total student population in the city"
    )
    
    international_student_percentage = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of international students"
    )
    
    existing_pbsa_beds = models.PositiveIntegerField(
        default=0,
        help_text="Total existing PBSA beds in the market"
    )
    
    pipeline_beds = models.PositiveIntegerField(
        default=0,
        help_text="PBSA beds in development pipeline"
    )
    
    # Supply and demand
    estimated_demand = models.PositiveIntegerField(
        help_text="Estimated total bed demand"
    )
    
    supply_demand_ratio = models.FloatField(
        help_text="Ratio of supply to demand (1.0 = balanced)"
    )
    
    average_occupancy_rate = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Average occupancy rate across PBSA (%)"
    )
    
    # Market dynamics
    average_rent_per_week = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Average rent per bed per week"
    )
    
    rent_growth_rate = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-100), MaxValueValidator(100)],
        help_text="Annual rent growth rate (%)"
    )
    
    # Analysis content
    market_summary = models.TextField(
        help_text="Executive summary of the market"
    )
    
    key_trends = models.JSONField(
        default=list,
        help_text="List of key market trends"
    )
    
    opportunities = models.JSONField(
        default=list,
        help_text="List of investment opportunities"
    )
    
    risks = models.JSONField(
        default=list,
        help_text="List of market risks"
    )
    
    # Rankings
    top_neighborhoods = models.JSONField(
        default=list,
        help_text="Ranked list of top neighborhoods for investment"
    )
    
    neighborhood_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of neighborhoods analyzed"
    )
    
    # Methodology and sources
    methodology = models.TextField(
        help_text="Description of research methodology"
    )
    
    data_sources = models.JSONField(
        default=list,
        help_text="List of data sources and references"
    )
    
    # Versioning
    version = models.CharField(
        max_length=10,
        default="1.0",
        help_text="Version of the analysis"
    )
    
    is_published = models.BooleanField(
        default=False,
        help_text="Whether this analysis is published"
    )
    
    class Meta:
        db_table = 'geographic_intelligence_market_analyses'
        unique_together = ['group', 'city', 'country', 'version']
        indexes = [
            models.Index(fields=['city', 'country', 'is_published']),
            models.Index(fields=['analysis_date']),
        ]
        ordering = ['-analysis_date', '-version']
    
    def __str__(self):
        return f"{self.city}, {self.country} - PBSA Market Analysis ({self.analysis_date})"
    
    @property
    def supply_shortage(self) -> int:
        """Calculate supply shortage/surplus."""
        return self.estimated_demand - (self.existing_pbsa_beds + self.pipeline_beds)
    
    @property
    def market_maturity(self) -> str:
        """Classify market maturity based on supply/demand."""
        ratio = self.supply_demand_ratio
        if ratio < 0.5:
            return "Emerging"
        elif ratio < 0.8:
            return "Growing"
        elif ratio < 1.2:
            return "Mature"
        else:
            return "Oversupplied"
    
    def add_neighborhood(self, neighborhood: 'Neighborhood'):
        """Add a neighborhood to this analysis."""
        MarketAnalysisNeighborhood.objects.create(
            market_analysis=self,
            neighborhood=neighborhood
        )
        self.neighborhood_count = self.neighborhoods.count()
        self.save(update_fields=['neighborhood_count'])
    
    def add_university(self, university: 'University'):
        """Add a university to this analysis."""
        MarketAnalysisUniversity.objects.create(
            market_analysis=self,
            university=university
        )
    
    def calculate_top_neighborhoods(self, limit: int = 20):
        """Calculate and store top neighborhoods by score."""
        neighborhoods = list(
            self.neighborhoods.select_related('neighborhood__metrics')
            .order_by('-neighborhood__metrics__overall_score')[:limit]
            .values_list('neighborhood__name', flat=True)
        )
        self.top_neighborhoods = neighborhoods
        self.save(update_fields=['top_neighborhoods'])


class MarketAnalysisNeighborhood(models.Model):
    """Many-to-many relationship for market analysis neighborhoods."""
    
    market_analysis = models.ForeignKey(
        PBSAMarketAnalysis,
        on_delete=models.CASCADE,
        related_name='neighborhoods'
    )
    
    neighborhood = models.ForeignKey(
        Neighborhood,
        on_delete=models.CASCADE,
        related_name='market_analyses'
    )
    
    rank = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Rank within this market analysis"
    )
    
    class Meta:
        db_table = 'geographic_intelligence_market_neighborhoods'
        unique_together = ['market_analysis', 'neighborhood']
        ordering = ['rank']


class MarketAnalysisUniversity(models.Model):
    """Many-to-many relationship for market analysis universities."""
    
    market_analysis = models.ForeignKey(
        PBSAMarketAnalysis,
        on_delete=models.CASCADE,
        related_name='universities'
    )
    
    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name='market_analyses'
    )
    
    class Meta:
        db_table = 'geographic_intelligence_market_universities'
        unique_together = ['market_analysis', 'university']
