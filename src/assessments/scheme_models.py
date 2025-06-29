"""
PBSA Scheme Information Models for the CASA Due Diligence Platform.

These models implement comprehensive scheme assessment capabilities including
location analysis, site characteristics, economic viability, and operational
considerations for Purpose-Built Student Accommodation developments.
"""

from decimal import Decimal
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime, date

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import Point

from .base_models import BaseAssessmentModel, FinancialMixin, RiskAssessmentMixin
from .enums import Currency, RiskLevel, AreaUnit
from .validation import (
    CountryCodeValidator, 
    validate_positive_decimal, 
    validate_year_range,
    get_country_code_validator
)


class UniversityType(models.TextChoices):
    """Types of universities for PBSA scheme targeting."""
    RUSSELL_GROUP = 'RUSSELL_GROUP', 'Russell Group University'
    RED_BRICK = 'RED_BRICK', 'Red Brick University'
    CIVIC = 'CIVIC', 'Civic University'
    MODERN = 'MODERN', 'Modern University (Post-1992)'
    TECHNICAL = 'TECHNICAL', 'Technical/Specialist University'
    INTERNATIONAL = 'INTERNATIONAL', 'International Branch Campus'
    OTHER = 'OTHER', 'Other Institution'


class DevelopmentStage(models.TextChoices):
    """Development stages for PBSA schemes."""
    CONCEPT = 'CONCEPT', 'Concept Stage'
    FEASIBILITY = 'FEASIBILITY', 'Feasibility Study'
    PLANNING = 'PLANNING', 'Planning Application'
    PRE_CONSTRUCTION = 'PRE_CONSTRUCTION', 'Pre-Construction'
    CONSTRUCTION = 'CONSTRUCTION', 'Under Construction'
    OPERATIONAL = 'OPERATIONAL', 'Operational'
    DISPOSED = 'DISPOSED', 'Disposed'


class AccommodationType(models.TextChoices):
    """Types of student accommodation."""
    CLUSTER_FLAT = 'CLUSTER_FLAT', 'Cluster Flat'
    STUDIO = 'STUDIO', 'Studio Apartment'
    ONE_BED = 'ONE_BED', 'One Bedroom Apartment'
    TWO_BED = 'TWO_BED', 'Two Bedroom Apartment'
    TOWNHOUSE = 'TOWNHOUSE', 'Townhouse'
    ENSUITE = 'ENSUITE', 'En-suite Room'
    STANDARD = 'STANDARD', 'Standard Room'


class PlanningStatus(models.TextChoices):
    """Planning permission status."""
    PRE_APPLICATION = 'PRE_APPLICATION', 'Pre-Application'
    SUBMITTED = 'SUBMITTED', 'Application Submitted'
    UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
    APPROVED = 'APPROVED', 'Planning Approved'
    REFUSED = 'REFUSED', 'Planning Refused'
    APPEALED = 'APPEALED', 'Under Appeal'
    CONDITIONS = 'CONDITIONS', 'Approved with Conditions'


class PBSAScheme(BaseAssessmentModel, FinancialMixin):
    """
    Enhanced PBSA scheme model with comprehensive information structure.
    
    This is the main entity for Purpose-Built Student Accommodation schemes,
    aggregating all scheme-related information for assessment purposes.
    """
    
    # Basic scheme identification
    scheme_name = models.CharField(
        max_length=255,
        help_text="Name of the PBSA scheme"
    )
    
    scheme_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Internal reference code for the scheme"
    )
    
    development_stage = models.CharField(
        max_length=20,
        choices=DevelopmentStage.choices,
        default=DevelopmentStage.CONCEPT,
        help_text="Current development stage"
    )
    
    # Developer relationship
    developer = models.ForeignKey(
        'DevelopmentPartner',
        on_delete=models.CASCADE,
        related_name='pbsa_schemes',
        help_text="Development partner responsible for this scheme"
    )
    
    # Basic scheme metrics
    total_beds = models.PositiveIntegerField(
        help_text="Total number of student beds"
    )
    
    total_units = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total number of accommodation units"
    )
    
    # Scheme timeline
    expected_completion_date = models.DateField(
        null=True,
        blank=True,
        help_text="Expected scheme completion date"
    )
    
    construction_start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Actual or planned construction start date"
    )
    
    operational_start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Expected operational start date"
    )
    
    # High-level financial information
    total_development_cost_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Total development cost"
    )
    
    total_development_cost_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of total development cost"
    )
    
    estimated_gcd_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Estimated Gross Development Cost"
    )
    
    estimated_gcd_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of estimated GDC"
    )
    
    # Status and priority
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this scheme is currently active"
    )
    
    assessment_priority = models.CharField(
        max_length=20,
        choices=[
            ('high', 'High Priority'),
            ('medium', 'Medium Priority'),
            ('low', 'Low Priority'),
        ],
        default='medium',
        help_text="Assessment priority level"
    )
    
    # Quick access fields (denormalized for performance)
    _university_count = models.PositiveIntegerField(
        default=0,
        help_text="Cached count of target universities"
    )
    
    _average_rent_per_bed = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cached average rent per bed per week"
    )
    
    class Meta:
        db_table = 'pbsa_schemes_enhanced'
        verbose_name = 'PBSA Scheme'
        verbose_name_plural = 'PBSA Schemes'
        ordering = ['scheme_name']
        indexes = [
            models.Index(fields=['development_stage']),
            models.Index(fields=['total_beds']),
            models.Index(fields=['expected_completion_date']),
        ]
    
    def __str__(self) -> str:
        return f"{self.scheme_name} ({self.total_beds} beds)"
    
    @property
    def cost_per_bed(self) -> Optional[Decimal]:
        """Calculate development cost per bed."""
        if (self.total_development_cost_amount and 
            self.total_beds and self.total_beds > 0):
            return round(self.total_development_cost_amount / self.total_beds, 2)
        return None
    
    @property
    def development_timeline_months(self) -> Optional[int]:
        """Calculate development timeline in months."""
        if (self.construction_start_date and 
            self.expected_completion_date and
            self.expected_completion_date > self.construction_start_date):
            
            delta = self.expected_completion_date - self.construction_start_date
            return round(delta.days / 30.44)  # Average days per month
        return None
    
    @property
    def beds_per_unit(self) -> Optional[float]:
        """Average beds per unit ratio."""
        if self.total_units and self.total_units > 0:
            return round(self.total_beds / self.total_units, 2)
        return None
    
    def get_scheme_summary(self) -> Dict[str, Any]:
        """Get comprehensive scheme summary."""
        summary = {
            'scheme_name': self.scheme_name,
            'developer': self.developer.company_name,
            'total_beds': self.total_beds,
            'development_stage': self.get_development_stage_display(),
            'cost_per_bed': self.cost_per_bed,
            'timeline_months': self.development_timeline_months,
        }
        
        # Add location information
        if hasattr(self, 'location_info'):
            loc_info = self.location_info
            summary.update({
                'city': loc_info.city,
                'country': loc_info.country,
                'university_count': loc_info.target_universities.count(),
            })
        
        # Add economic information
        if hasattr(self, 'economic_info'):
            econ_info = self.economic_info
            summary.update({
                'estimated_yield': econ_info.estimated_gross_yield_pct,
                'estimated_irr': econ_info.projected_irr_pct,
            })
        
        return summary
    
    def update_cached_fields(self):
        """Update denormalized fields for performance."""
        if hasattr(self, 'location_info'):
            self._university_count = self.location_info.target_universities.count()
        
        if hasattr(self, 'economic_info') and self.economic_info.avg_rent_per_bed_per_week:
            self._average_rent_per_bed = self.economic_info.avg_rent_per_bed_per_week
        
        self.save(update_fields=['_university_count', '_average_rent_per_bed'])


class SchemeLocationInformation(BaseAssessmentModel):
    """
    Location and market information for PBSA schemes.
    
    Captures location characteristics, university proximity, market dynamics,
    and transport connectivity essential for student accommodation viability.
    """
    
    scheme = models.OneToOneField(
        PBSAScheme,
        on_delete=models.CASCADE,
        related_name='location_info',
        help_text="PBSA scheme this location information belongs to"
    )
    
    # Geographic location
    address = models.TextField(
        help_text="Full address of the scheme"
    )
    
    city = models.CharField(
        max_length=100,
        help_text="City where the scheme is located"
    )
    
    region = models.CharField(
        max_length=100,
        blank=True,
        help_text="Region or state/province"
    )
    
    country = models.CharField(
        max_length=2,
        validators=[get_country_code_validator()],
        help_text="Country (ISO 3166-1 alpha-2)"
    )
    
    postcode = models.CharField(
        max_length=20,
        blank=True,
        help_text="Postal/ZIP code"
    )
    
    # Geospatial information
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Latitude coordinate"
    )
    
    longitude = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Longitude coordinate"
    )
    
    # Location characteristics
    location_type = models.CharField(
        max_length=20,
        choices=[
            ('city_centre', 'City Centre'),
            ('campus_adjacent', 'Campus Adjacent'),
            ('suburban', 'Suburban'),
            ('edge_of_town', 'Edge of Town'),
            ('out_of_town', 'Out of Town'),
        ],
        help_text="Type of location relative to city/university"
    )
    
    # Transport and connectivity
    nearest_train_station = models.CharField(
        max_length=100,
        blank=True,
        help_text="Nearest railway station"
    )
    
    train_station_distance_km = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Distance to nearest train station in km"
    )
    
    airport_proximity = models.CharField(
        max_length=100,
        blank=True,
        help_text="Nearest airport and approximate distance"
    )
    
    public_transport_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
        help_text="Public transport quality rating (1-5)"
    )
    
    # Market characteristics
    local_market_description = models.TextField(
        blank=True,
        help_text="Description of local student accommodation market"
    )
    
    competitive_schemes_nearby = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of competing PBSA schemes in area"
    )
    
    total_student_population = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total student population in the area"
    )
    
    class Meta:
        db_table = 'scheme_location_information'
        verbose_name = 'Scheme Location Information'
    
    def __str__(self) -> str:
        return f"Location Info for {self.scheme.scheme_name}"
    
    @property
    def coordinates(self) -> Optional[Point]:
        """Get location coordinates as a Point object."""
        if self.latitude is not None and self.longitude is not None:
            return Point(float(self.longitude), float(self.latitude))
        return None
    
    @property
    def transport_accessibility_score(self) -> Optional[int]:
        """Calculate transport accessibility score."""
        score = 0
        max_score = 0
        
        # Public transport rating (weight: 40%)
        if self.public_transport_rating:
            score += self.public_transport_rating * 40
            max_score += 5 * 40
        
        # Train station proximity (weight: 35%)
        if self.train_station_distance_km is not None:
            if self.train_station_distance_km <= 0.5:
                score += 5 * 35
            elif self.train_station_distance_km <= 1.0:
                score += 4 * 35
            elif self.train_station_distance_km <= 2.0:
                score += 3 * 35
            elif self.train_station_distance_km <= 5.0:
                score += 2 * 35
            else:
                score += 1 * 35
            max_score += 5 * 35
        
        # Location type bonus (weight: 25%)
        location_scores = {
            'city_centre': 5,
            'campus_adjacent': 4,
            'suburban': 3,
            'edge_of_town': 2,
            'out_of_town': 1
        }
        if self.location_type in location_scores:
            score += location_scores[self.location_type] * 25
            max_score += 5 * 25
        
        if max_score > 0:
            return round((score / max_score) * 5)
        return None


class TargetUniversity(BaseAssessmentModel):
    """
    Target universities for PBSA scheme marketing and demand analysis.
    
    Tracks universities within catchment area with student numbers,
    accommodation provision, and market analysis.
    """
    
    location_info = models.ForeignKey(
        SchemeLocationInformation,
        on_delete=models.CASCADE,
        related_name='target_universities',
        help_text="Location information this university relates to"
    )
    
    # University identification
    university_name = models.CharField(
        max_length=255,
        help_text="Name of the university"
    )
    
    university_type = models.CharField(
        max_length=20,
        choices=UniversityType.choices,
        help_text="Type/category of university"
    )
    
    # Location and proximity
    distance_to_campus_km = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Distance from scheme to main campus in km"
    )
    
    walking_time_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Walking time to campus in minutes"
    )
    
    cycling_time_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Cycling time to campus in minutes"
    )
    
    public_transport_time_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Public transport time to campus in minutes"
    )
    
    # University characteristics
    total_student_population = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total number of students at university"
    )
    
    international_student_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of international students"
    )
    
    postgraduate_student_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of postgraduate students"
    )
    
    # Accommodation provision
    university_provided_beds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of beds provided by university"
    )
    
    accommodation_satisfaction_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
        help_text="University accommodation satisfaction rating"
    )
    
    # Market potential
    target_student_segment = models.CharField(
        max_length=100,
        blank=True,
        help_text="Primary target student segment for this university"
    )
    
    estimated_demand_capture_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Estimated demand capture percentage"
    )
    
    class Meta:
        db_table = 'target_universities'
        verbose_name = 'Target University'
        verbose_name_plural = 'Target Universities'
        unique_together = ['location_info', 'university_name']
        ordering = ['distance_to_campus_km']
    
    def __str__(self) -> str:
        return f"{self.university_name} ({self.distance_to_campus_km}km)"
    
    @property
    def proximity_score(self) -> int:
        """Calculate proximity score based on distance and transport."""
        if self.distance_to_campus_km <= 0.5:
            base_score = 5
        elif self.distance_to_campus_km <= 1.0:
            base_score = 4
        elif self.distance_to_campus_km <= 2.0:
            base_score = 3
        elif self.distance_to_campus_km <= 5.0:
            base_score = 2
        else:
            base_score = 1
        
        # Adjust for walking time if available
        if self.walking_time_minutes:
            if self.walking_time_minutes <= 10:
                base_score = min(5, base_score + 1)
            elif self.walking_time_minutes <= 20:
                pass  # No adjustment
            else:
                base_score = max(1, base_score - 1)
        
        return base_score
    
    @property
    def market_attractiveness(self) -> Optional[float]:
        """Calculate market attractiveness score."""
        if not self.total_student_population:
            return None
        
        score = 0
        weights = 0
        
        # University size (weight: 30%)
        if self.total_student_population >= 30000:
            score += 5 * 30
        elif self.total_student_population >= 20000:
            score += 4 * 30
        elif self.total_student_population >= 15000:
            score += 3 * 30
        elif self.total_student_population >= 10000:
            score += 2 * 30
        else:
            score += 1 * 30
        weights += 30
        
        # International student percentage (weight: 25%)
        if self.international_student_pct:
            if self.international_student_pct >= 25:
                score += 5 * 25
            elif self.international_student_pct >= 20:
                score += 4 * 25
            elif self.international_student_pct >= 15:
                score += 3 * 25
            elif self.international_student_pct >= 10:
                score += 2 * 25
            else:
                score += 1 * 25
            weights += 25
        
        # Proximity (weight: 25%)
        score += self.proximity_score * 25
        weights += 25
        
        # University accommodation satisfaction (weight: 20%)
        if self.accommodation_satisfaction_rating:
            # Lower satisfaction = higher opportunity for private provision
            reverse_rating = 6 - self.accommodation_satisfaction_rating
            score += reverse_rating * 20
            weights += 20
        
        if weights > 0:
            return round((score / weights), 2)
        return None


class SchemeSiteInformation(BaseAssessmentModel):
    """
    Site characteristics and development constraints for PBSA schemes.
    
    Captures physical site attributes, planning status, development constraints,
    and opportunities that impact scheme viability and design.
    """
    
    scheme = models.OneToOneField(
        PBSAScheme,
        on_delete=models.CASCADE,
        related_name='site_info',
        help_text="PBSA scheme this site information belongs to"
    )
    
    # Site characteristics
    site_area_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[validate_positive_decimal],
        help_text="Total site area"
    )
    
    site_area_unit = models.CharField(
        max_length=10,
        choices=AreaUnit.choices,
        help_text="Unit of measurement for site area"
    )
    
    site_configuration = models.CharField(
        max_length=20,
        choices=[
            ('regular', 'Regular Shape'),
            ('irregular', 'Irregular Shape'),
            ('corner', 'Corner Plot'),
            ('linear', 'Linear Site'),
            ('island', 'Island Site'),
        ],
        help_text="General configuration of the site"
    )
    
    # Development capacity
    plot_ratio = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Plot ratio (floor area / site area)"
    )
    
    building_coverage_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of site covered by buildings"
    )
    
    max_height_stories = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum permitted building height in stories"
    )
    
    # Site conditions
    topography = models.CharField(
        max_length=20,
        choices=[
            ('flat', 'Flat'),
            ('gentle_slope', 'Gentle Slope'),
            ('steep_slope', 'Steep Slope'),
            ('undulating', 'Undulating'),
            ('valley', 'Valley'),
        ],
        blank=True,
        help_text="Site topography"
    )
    
    ground_conditions = models.CharField(
        max_length=20,
        choices=[
            ('excellent', 'Excellent'),
            ('good', 'Good'),
            ('average', 'Average'),
            ('poor', 'Poor'),
            ('very_poor', 'Very Poor'),
        ],
        blank=True,
        help_text="Ground conditions for construction"
    )
    
    contamination_risk = models.CharField(
        max_length=10,
        choices=RiskLevel.choices,
        blank=True,
        help_text="Contamination risk level"
    )
    
    flood_risk = models.CharField(
        max_length=10,
        choices=RiskLevel.choices,
        blank=True,
        help_text="Flood risk level"
    )
    
    # Planning status
    planning_status = models.CharField(
        max_length=20,
        choices=PlanningStatus.choices,
        default=PlanningStatus.PRE_APPLICATION,
        help_text="Current planning permission status"
    )
    
    planning_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Planning application reference number"
    )
    
    planning_submission_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date planning application was submitted"
    )
    
    planning_decision_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of planning decision"
    )
    
    planning_conditions = models.TextField(
        blank=True,
        help_text="Planning conditions or requirements"
    )
    
    # Infrastructure and services
    utilities_available = models.JSONField(
        default=dict,
        help_text="Available utilities (electricity, gas, water, etc.)"
    )
    
    infrastructure_upgrades_required = models.TextField(
        blank=True,
        help_text="Infrastructure upgrades required for development"
    )
    
    # Constraints and opportunities
    development_constraints = models.TextField(
        blank=True,
        help_text="Key development constraints and challenges"
    )
    
    design_opportunities = models.TextField(
        blank=True,
        help_text="Design opportunities and advantages"
    )
    
    environmental_considerations = models.TextField(
        blank=True,
        help_text="Environmental factors and requirements"
    )
    
    class Meta:
        db_table = 'scheme_site_information'
        verbose_name = 'Scheme Site Information'
    
    def __str__(self) -> str:
        return f"Site Info for {self.scheme.scheme_name}"
    
    @property
    def site_area_sq_m(self) -> Decimal:
        """Convert site area to square meters."""
        if self.site_area_unit == AreaUnit.SQ_M:
            return self.site_area_value
        elif self.site_area_unit == AreaUnit.SQ_FT:
            return round(self.site_area_value * Decimal('0.092903'), 2)
        return self.site_area_value
    
    @property
    def beds_per_hectare(self) -> Optional[Decimal]:
        """Calculate bed density per hectare."""
        area_hectares = self.site_area_sq_m / Decimal('10000')
        if area_hectares > 0:
            return round(self.scheme.total_beds / area_hectares, 1)
        return None
    
    @property
    def development_feasibility_score(self) -> int:
        """Calculate development feasibility score (1-5)."""
        score = 3  # Start with neutral
        
        # Planning status impact
        planning_scores = {
            PlanningStatus.APPROVED: 2,
            PlanningStatus.CONDITIONS: 1,
            PlanningStatus.UNDER_REVIEW: 0,
            PlanningStatus.SUBMITTED: 0,
            PlanningStatus.PRE_APPLICATION: -1,
            PlanningStatus.REFUSED: -2,
            PlanningStatus.APPEALED: -1,
        }
        score += planning_scores.get(self.planning_status, 0)
        
        # Ground conditions impact
        ground_scores = {
            'excellent': 1,
            'good': 0.5,
            'average': 0,
            'poor': -0.5,
            'very_poor': -1,
        }
        if self.ground_conditions:
            score += ground_scores.get(self.ground_conditions, 0)
        
        # Risk factors impact
        if self.contamination_risk == RiskLevel.HIGH:
            score -= 1
        elif self.contamination_risk == RiskLevel.LOW:
            score += 0.5
        
        if self.flood_risk == RiskLevel.HIGH:
            score -= 1
        elif self.flood_risk == RiskLevel.LOW:
            score += 0.5
        
        # Site configuration impact
        config_scores = {
            'regular': 0.5,
            'corner': 0.5,
            'irregular': -0.5,
            'linear': 0,
            'island': 0,
        }
        if self.site_configuration:
            score += config_scores.get(self.site_configuration, 0)
        
        # Bound the score
        return max(1, min(5, round(score)))
    
    @property
    def planning_risk_assessment(self) -> Dict[str, Any]:
        """Assess planning risks and timeline."""
        risk_level = RiskLevel.MEDIUM
        timeline_estimate = None
        risk_factors = []
        
        if self.planning_status == PlanningStatus.APPROVED:
            risk_level = RiskLevel.LOW
            timeline_estimate = "0-3 months (conditions discharge)"
        elif self.planning_status == PlanningStatus.CONDITIONS:
            risk_level = RiskLevel.LOW
            timeline_estimate = "1-6 months (conditions discharge)"
        elif self.planning_status in [PlanningStatus.SUBMITTED, PlanningStatus.UNDER_REVIEW]:
            risk_level = RiskLevel.MEDIUM
            timeline_estimate = "3-12 months (decision pending)"
        elif self.planning_status == PlanningStatus.PRE_APPLICATION:
            risk_level = RiskLevel.HIGH
            timeline_estimate = "6-18 months (application + decision)"
            risk_factors.append("No formal application submitted")
        elif self.planning_status == PlanningStatus.REFUSED:
            risk_level = RiskLevel.HIGH
            timeline_estimate = "12+ months (appeal or resubmission)"
            risk_factors.append("Previous refusal")
        elif self.planning_status == PlanningStatus.APPEALED:
            risk_level = RiskLevel.HIGH
            timeline_estimate = "6-12 months (appeal process)"
            risk_factors.append("Currently under appeal")
        
        return {
            'risk_level': risk_level,
            'timeline_estimate': timeline_estimate,
            'risk_factors': risk_factors,
            'planning_status': self.get_planning_status_display()
        }