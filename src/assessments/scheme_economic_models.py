"""
Economic and Operational Models for PBSA Schemes.

These models implement comprehensive economic viability analysis, revenue
modeling, cost management, and operational considerations for Purpose-Built
Student Accommodation developments.
"""

from decimal import Decimal
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime, date
import json

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

from .base_models import BaseAssessmentModel, FinancialMixin, RiskAssessmentMixin
from .enums import Currency, RiskLevel
from .validation import validate_positive_decimal
from .scheme_models import PBSAScheme, AccommodationType


class SchemeEconomicInformation(BaseAssessmentModel, FinancialMixin):
    """
    Economic viability and financial modeling for PBSA schemes.
    
    Captures development costs, revenue projections, investment returns,
    and comprehensive financial analysis for scheme evaluation.
    """
    
    scheme = models.OneToOneField(
        PBSAScheme,
        on_delete=models.CASCADE,
        related_name='economic_info',
        help_text="PBSA scheme this economic information belongs to"
    )
    
    # Development costs
    land_cost_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Land acquisition cost"
    )
    
    land_cost_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of land cost"
    )
    
    construction_cost_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Total construction cost"
    )
    
    construction_cost_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of construction cost"
    )
    
    professional_fees_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Professional fees (architects, consultants, etc.)"
    )
    
    professional_fees_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of professional fees"
    )
    
    finance_costs_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Development finance costs"
    )
    
    finance_costs_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of finance costs"
    )
    
    contingency_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Contingency allowance"
    )
    
    contingency_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of contingency"
    )
    
    # Revenue projections
    avg_rent_per_bed_per_week = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Average rent per bed per week"
    )
    
    rent_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of rental income"
    )
    
    occupancy_rate_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
        help_text="Expected occupancy rate percentage"
    )
    
    rental_growth_rate_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Annual rental growth rate percentage"
    )
    
    ancillary_income_per_bed_per_year = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Ancillary income per bed per year (parking, services, etc.)"
    )
    
    # Operating costs
    operating_cost_per_bed_per_year = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Operating cost per bed per year"
    )
    
    management_fee_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Management fee as percentage of gross rental income"
    )
    
    maintenance_cost_per_bed_per_year = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Maintenance and repairs cost per bed per year"
    )
    
    # Investment returns
    target_gross_yield_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Target gross rental yield percentage"
    )
    
    target_net_yield_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Target net rental yield percentage"
    )
    
    projected_irr_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Projected Internal Rate of Return percentage"
    )
    
    exit_cap_rate_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Exit capitalization rate percentage"
    )
    
    # Market analysis
    market_rent_per_bed_per_week = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Market average rent per bed per week"
    )
    
    rent_premium_discount_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Rent premium (+) or discount (-) vs market average"
    )
    
    # Financial year information
    financial_year_end_month = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        null=True,
        blank=True,
        help_text="Financial year end month (1-12)"
    )
    
    class Meta:
        db_table = 'scheme_economic_information'
        verbose_name = 'Scheme Economic Information'
    
    def __str__(self) -> str:
        return f"Economic Info for {self.scheme.scheme_name}"
    
    @property
    def total_development_cost(self) -> Optional[Decimal]:
        """Calculate total development cost."""
        costs = [
            self.land_cost_amount,
            self.construction_cost_amount,
            self.professional_fees_amount,
            self.finance_costs_amount,
            self.contingency_amount
        ]
        
        total = Decimal('0')
        for cost in costs:
            if cost:
                total += cost
        
        return total if total > 0 else None
    
    @property
    def cost_per_bed(self) -> Optional[Decimal]:
        """Calculate development cost per bed."""
        total_cost = self.total_development_cost
        if total_cost and self.scheme.total_beds > 0:
            return round(total_cost / self.scheme.total_beds, 2)
        return None
    
    @property
    def gross_annual_rental_income(self) -> Optional[Decimal]:
        """Calculate gross annual rental income."""
        if (self.avg_rent_per_bed_per_week and 
            self.occupancy_rate_pct and 
            self.scheme.total_beds > 0):
            
            weekly_income = (self.avg_rent_per_bed_per_week * 
                           self.scheme.total_beds * 
                           (self.occupancy_rate_pct / 100))
            
            return round(weekly_income * 52, 2)  # 52 weeks per year
        return None
    
    @property
    def total_annual_income(self) -> Optional[Decimal]:
        """Calculate total annual income including ancillary."""
        gross_rental = self.gross_annual_rental_income
        if not gross_rental:
            return None
        
        total = gross_rental
        
        if self.ancillary_income_per_bed_per_year:
            ancillary_total = (self.ancillary_income_per_bed_per_year * 
                             self.scheme.total_beds)
            total += ancillary_total
        
        return round(total, 2)
    
    @property
    def total_annual_operating_costs(self) -> Optional[Decimal]:
        """Calculate total annual operating costs."""
        if not self.scheme.total_beds:
            return None
        
        total_costs = Decimal('0')
        
        # Operating costs per bed
        if self.operating_cost_per_bed_per_year:
            total_costs += (self.operating_cost_per_bed_per_year * 
                          self.scheme.total_beds)
        
        # Management fee
        if self.management_fee_pct and self.gross_annual_rental_income:
            management_fee = (self.gross_annual_rental_income * 
                            self.management_fee_pct / 100)
            total_costs += management_fee
        
        # Maintenance costs
        if self.maintenance_cost_per_bed_per_year:
            total_costs += (self.maintenance_cost_per_bed_per_year * 
                          self.scheme.total_beds)
        
        return round(total_costs, 2) if total_costs > 0 else None
    
    @property
    def net_annual_income(self) -> Optional[Decimal]:
        """Calculate net annual income after operating costs."""
        total_income = self.total_annual_income
        operating_costs = self.total_annual_operating_costs
        
        if total_income and operating_costs:
            return round(total_income - operating_costs, 2)
        return None
    
    @property
    def estimated_gross_yield_pct(self) -> Optional[Decimal]:
        """Calculate estimated gross rental yield."""
        total_cost = self.total_development_cost
        gross_income = self.gross_annual_rental_income
        
        if total_cost and gross_income and total_cost > 0:
            yield_pct = (gross_income / total_cost) * 100
            return round(yield_pct, 2)
        return None
    
    @property
    def estimated_net_yield_pct(self) -> Optional[Decimal]:
        """Calculate estimated net rental yield."""
        total_cost = self.total_development_cost
        net_income = self.net_annual_income
        
        if total_cost and net_income and total_cost > 0:
            yield_pct = (net_income / total_cost) * 100
            return round(yield_pct, 2)
        return None
    
    @property
    def rent_vs_market_analysis(self) -> Dict[str, Any]:
        """Analyze rent positioning vs market."""
        if not (self.avg_rent_per_bed_per_week and self.market_rent_per_bed_per_week):
            return {}
        
        variance = self.avg_rent_per_bed_per_week - self.market_rent_per_bed_per_week
        variance_pct = (variance / self.market_rent_per_bed_per_week) * 100
        
        if variance_pct > 10:
            positioning = "Premium"
        elif variance_pct > 0:
            positioning = "Above Market"
        elif variance_pct > -5:
            positioning = "Market Rate"
        else:
            positioning = "Below Market"
        
        return {
            'scheme_rent': self.avg_rent_per_bed_per_week,
            'market_rent': self.market_rent_per_bed_per_week,
            'variance_amount': round(variance, 2),
            'variance_percentage': round(variance_pct, 2),
            'positioning': positioning
        }
    
    @property
    def investment_viability_score(self) -> Optional[int]:
        """Calculate investment viability score (1-5)."""
        score = 3  # Start with neutral
        factors = []
        
        # Yield analysis
        gross_yield = self.estimated_gross_yield_pct
        if gross_yield:
            if gross_yield >= 8:
                score += 1
                factors.append("Strong gross yield (≥8%)")
            elif gross_yield >= 6:
                score += 0.5
                factors.append("Good gross yield (6-8%)")
            elif gross_yield < 4:
                score -= 1
                factors.append("Poor gross yield (<4%)")
        
        # IRR analysis
        if self.projected_irr_pct:
            if self.projected_irr_pct >= 15:
                score += 1
                factors.append("Excellent IRR (≥15%)")
            elif self.projected_irr_pct >= 12:
                score += 0.5
                factors.append("Good IRR (12-15%)")
            elif self.projected_irr_pct < 8:
                score -= 1
                factors.append("Poor IRR (<8%)")
        
        # Rent positioning
        rent_analysis = self.rent_vs_market_analysis
        if rent_analysis:
            variance_pct = rent_analysis.get('variance_percentage', 0)
            if -5 <= variance_pct <= 10:
                score += 0.5
                factors.append("Appropriate rent positioning")
            elif variance_pct > 20:
                score -= 0.5
                factors.append("Potentially overpriced")
        
        # Cost efficiency
        cost_per_bed = self.cost_per_bed
        if cost_per_bed:
            # These are example thresholds - would be market-specific
            if cost_per_bed <= 40000:
                score += 0.5
                factors.append("Cost-efficient development")
            elif cost_per_bed >= 70000:
                score -= 0.5
                factors.append("High development cost")
        
        # Bound the score
        final_score = max(1, min(5, round(score)))
        
        return {
            'score': final_score,
            'factors': factors,
            'gross_yield': gross_yield,
            'projected_irr': self.projected_irr_pct,
            'cost_per_bed': cost_per_bed
        }


class AccommodationUnit(BaseAssessmentModel):
    """
    Individual accommodation units within a PBSA scheme.
    
    Tracks unit types, specifications, and pricing for detailed
    revenue modeling and market positioning analysis.
    """
    
    scheme = models.ForeignKey(
        PBSAScheme,
        on_delete=models.CASCADE,
        related_name='accommodation_units',
        help_text="PBSA scheme this unit belongs to"
    )
    
    # Unit specification
    unit_type = models.CharField(
        max_length=20,
        choices=AccommodationType.choices,
        help_text="Type of accommodation unit"
    )
    
    unit_name = models.CharField(
        max_length=100,
        help_text="Name or designation of this unit type"
    )
    
    bed_count = models.PositiveIntegerField(
        help_text="Number of beds in this unit type"
    )
    
    bathroom_count = models.PositiveIntegerField(
        default=1,
        help_text="Number of bathrooms in this unit type"
    )
    
    # Unit size and specifications
    gross_floor_area_sqm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Gross floor area in square meters"
    )
    
    bedroom_size_sqm = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Average bedroom size in square meters"
    )
    
    # Features and amenities
    has_kitchen = models.BooleanField(
        default=True,
        help_text="Whether unit has kitchen facilities"
    )
    
    kitchen_type = models.CharField(
        max_length=20,
        choices=[
            ('private', 'Private Kitchen'),
            ('shared', 'Shared Kitchen'),
            ('kitchenette', 'Kitchenette'),
            ('none', 'No Kitchen'),
        ],
        default='shared',
        help_text="Type of kitchen provision"
    )
    
    has_study_space = models.BooleanField(
        default=True,
        help_text="Whether unit has dedicated study space"
    )
    
    has_storage = models.BooleanField(
        default=True,
        help_text="Whether unit has storage space"
    )
    
    furnishing_level = models.CharField(
        max_length=20,
        choices=[
            ('unfurnished', 'Unfurnished'),
            ('part_furnished', 'Part Furnished'),
            ('fully_furnished', 'Fully Furnished'),
            ('premium_furnished', 'Premium Furnished'),
        ],
        default='fully_furnished',
        help_text="Level of furnishing provided"
    )
    
    # Pricing and availability
    number_of_units = models.PositiveIntegerField(
        help_text="Number of units of this type in the scheme"
    )
    
    rent_per_bed_per_week = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Rent per bed per week for this unit type"
    )
    
    rent_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of rental pricing"
    )
    
    # Market positioning
    target_market_segment = models.CharField(
        max_length=100,
        blank=True,
        help_text="Target market segment for this unit type"
    )
    
    competitive_rent_per_week = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Competitive market rent for similar units"
    )
    
    class Meta:
        db_table = 'accommodation_units'
        verbose_name = 'Accommodation Unit'
        verbose_name_plural = 'Accommodation Units'
        unique_together = ['scheme', 'unit_name']
        ordering = ['unit_type', 'unit_name']
    
    def __str__(self) -> str:
        return f"{self.unit_name} ({self.bed_count} bed, {self.number_of_units} units)"
    
    @property
    def total_beds_for_unit_type(self) -> int:
        """Total beds for this unit type."""
        return self.bed_count * self.number_of_units
    
    @property
    def area_per_bed_sqm(self) -> Optional[Decimal]:
        """Calculate area per bed."""
        if self.gross_floor_area_sqm and self.bed_count > 0:
            return round(self.gross_floor_area_sqm / self.bed_count, 2)
        return None
    
    @property
    def annual_revenue_per_unit(self) -> Optional[Decimal]:
        """Calculate annual revenue per unit (assuming 95% occupancy)."""
        if self.rent_per_bed_per_week:
            weekly_revenue = self.rent_per_bed_per_week * self.bed_count
            annual_revenue = weekly_revenue * 52 * Decimal('0.95')  # 95% occupancy
            return round(annual_revenue, 2)
        return None
    
    @property
    def total_annual_revenue_for_unit_type(self) -> Optional[Decimal]:
        """Calculate total annual revenue for all units of this type."""
        unit_revenue = self.annual_revenue_per_unit
        if unit_revenue:
            return round(unit_revenue * self.number_of_units, 2)
        return None
    
    @property
    def rent_premium_vs_competition_pct(self) -> Optional[Decimal]:
        """Calculate rent premium vs competitive market."""
        if (self.rent_per_bed_per_week and 
            self.competitive_rent_per_week and 
            self.competitive_rent_per_week > 0):
            
            premium = ((self.rent_per_bed_per_week - self.competitive_rent_per_week) /
                      self.competitive_rent_per_week) * 100
            return round(premium, 2)
        return None
    
    @property
    def unit_efficiency_score(self) -> Optional[int]:
        """Calculate unit efficiency score (1-5)."""
        score = 3  # Start with neutral
        
        # Area efficiency
        area_per_bed = self.area_per_bed_sqm
        if area_per_bed:
            if area_per_bed >= 25:  # Very spacious
                score += 1
            elif area_per_bed >= 20:  # Good size
                score += 0.5
            elif area_per_bed < 15:  # Cramped
                score -= 1
        
        # Feature completeness
        feature_score = 0
        if self.has_kitchen:
            feature_score += 1
        if self.has_study_space:
            feature_score += 1
        if self.has_storage:
            feature_score += 0.5
        if self.furnishing_level in ['fully_furnished', 'premium_furnished']:
            feature_score += 0.5
        
        if feature_score >= 3:
            score += 1
        elif feature_score <= 1:
            score -= 1
        
        # Rent competitiveness
        rent_premium = self.rent_premium_vs_competition_pct
        if rent_premium is not None:
            if -5 <= rent_premium <= 10:  # Reasonable positioning
                score += 0.5
            elif rent_premium > 20:  # Potentially overpriced
                score -= 1
        
        return max(1, min(5, round(score)))


class SchemeOperationalInformation(BaseAssessmentModel):
    """
    Operational considerations and management for PBSA schemes.
    
    Captures operational planning, management approach, service provision,
    and performance optimization strategies.
    """
    
    scheme = models.OneToOneField(
        PBSAScheme,
        on_delete=models.CASCADE,
        related_name='operational_info',
        help_text="PBSA scheme this operational information belongs to"
    )
    
    # Management approach
    management_model = models.CharField(
        max_length=20,
        choices=[
            ('self_managed', 'Self Managed'),
            ('third_party', 'Third Party Management'),
            ('hybrid', 'Hybrid Model'),
            ('franchise', 'Franchise Operation'),
        ],
        help_text="Operational management model"
    )
    
    management_company = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name of management company (if third party)"
    )
    
    # Staffing and operations
    on_site_staff_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of on-site staff members"
    )
    
    has_24_7_reception = models.BooleanField(
        default=False,
        help_text="Whether scheme has 24/7 reception"
    )
    
    has_security = models.BooleanField(
        default=True,
        help_text="Whether scheme has security provision"
    )
    
    security_type = models.CharField(
        max_length=20,
        choices=[
            ('cctv_only', 'CCTV Only'),
            ('access_control', 'Access Control Systems'),
            ('security_guard', 'Security Guard'),
            ('full_security', 'Comprehensive Security'),
        ],
        blank=True,
        help_text="Type of security provision"
    )
    
    # Services and amenities
    cleaning_service = models.CharField(
        max_length=20,
        choices=[
            ('none', 'No Cleaning Service'),
            ('common_areas', 'Common Areas Only'),
            ('weekly_rooms', 'Weekly Room Cleaning'),
            ('full_service', 'Full Cleaning Service'),
        ],
        default='common_areas',
        help_text="Level of cleaning service provided"
    )
    
    laundry_facilities = models.CharField(
        max_length=20,
        choices=[
            ('none', 'No Laundry'),
            ('shared_coin', 'Shared Coin-Operated'),
            ('shared_card', 'Shared Card/App Payment'),
            ('in_unit', 'In-Unit Laundry'),
        ],
        default='shared_card',
        help_text="Type of laundry facilities"
    )
    
    internet_provision = models.CharField(
        max_length=20,
        choices=[
            ('basic', 'Basic Internet'),
            ('high_speed', 'High Speed Broadband'),
            ('premium', 'Premium/Gaming Speed'),
            ('enterprise', 'Enterprise Grade'),
        ],
        default='high_speed',
        help_text="Level of internet provision"
    )
    
    # Common areas and facilities
    has_gym = models.BooleanField(
        default=False,
        help_text="Whether scheme has gym facilities"
    )
    
    has_study_rooms = models.BooleanField(
        default=True,
        help_text="Whether scheme has dedicated study rooms"
    )
    
    has_social_spaces = models.BooleanField(
        default=True,
        help_text="Whether scheme has social/common spaces"
    )
    
    has_cinema_room = models.BooleanField(
        default=False,
        help_text="Whether scheme has cinema/media room"
    )
    
    has_outdoor_space = models.BooleanField(
        default=False,
        help_text="Whether scheme has outdoor/garden space"
    )
    
    # Technology and innovation
    smart_building_features = models.JSONField(
        default=list,
        help_text="Smart building and technology features"
    )
    
    mobile_app_features = models.JSONField(
        default=list,
        help_text="Mobile app features for residents"
    )
    
    sustainability_features = models.JSONField(
        default=list,
        help_text="Sustainability and environmental features"
    )
    
    # Performance metrics
    target_occupancy_rate_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(50), MaxValueValidator(100)],
        null=True,
        blank=True,
        help_text="Target occupancy rate percentage"
    )
    
    average_lease_length_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Average lease length in months"
    )
    
    student_satisfaction_target = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
        help_text="Target student satisfaction rating (1-5)"
    )
    
    # Cost considerations
    estimated_operating_cost_per_bed = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Estimated annual operating cost per bed"
    )
    
    utilities_included_in_rent = models.BooleanField(
        default=True,
        help_text="Whether utilities are included in rent"
    )
    
    class Meta:
        db_table = 'scheme_operational_information'
        verbose_name = 'Scheme Operational Information'
    
    def __str__(self) -> str:
        return f"Operational Info for {self.scheme.scheme_name}"
    
    @property
    def amenity_score(self) -> int:
        """Calculate amenity provision score (1-5)."""
        score = 0
        max_score = 0
        
        # Essential amenities (weight: 40%)
        essential_weight = 40
        essential_score = 0
        essential_max = 0
        
        if self.has_study_rooms:
            essential_score += 20
        essential_max += 20
        
        if self.has_social_spaces:
            essential_score += 20
        essential_max += 20
        
        if essential_max > 0:
            score += (essential_score / essential_max) * essential_weight
            max_score += essential_weight
        
        # Premium amenities (weight: 30%)
        premium_weight = 30
        premium_score = 0
        premium_max = 0
        
        if self.has_gym:
            premium_score += 15
        premium_max += 15
        
        if self.has_cinema_room:
            premium_score += 10
        premium_max += 10
        
        if self.has_outdoor_space:
            premium_score += 5
        premium_max += 5
        
        if premium_max > 0:
            score += (premium_score / premium_max) * premium_weight
            max_score += premium_weight
        
        # Service quality (weight: 30%)
        service_weight = 30
        service_score = 0
        service_max = 0
        
        # Internet quality
        internet_scores = {
            'basic': 5,
            'high_speed': 10,
            'premium': 15,
            'enterprise': 20
        }
        if self.internet_provision in internet_scores:
            service_score += internet_scores[self.internet_provision]
        service_max += 20
        
        # Security provision
        if self.has_security:
            service_score += 10
        service_max += 10
        
        if service_max > 0:
            score += (service_score / service_max) * service_weight
            max_score += service_weight
        
        if max_score > 0:
            return round((score / max_score) * 5)
        return 3  # Default neutral score
    
    @property
    def operational_efficiency_score(self) -> int:
        """Calculate operational efficiency score (1-5)."""
        score = 3  # Start with neutral
        
        # Management model efficiency
        if self.management_model == 'self_managed':
            score += 0.5  # Better control
        elif self.management_model == 'third_party':
            score += 1  # Professional management
        
        # Technology integration
        tech_features = len(self.smart_building_features) if self.smart_building_features else 0
        app_features = len(self.mobile_app_features) if self.mobile_app_features else 0
        
        if tech_features + app_features >= 5:
            score += 1
        elif tech_features + app_features >= 3:
            score += 0.5
        
        # Staffing efficiency
        if self.on_site_staff_count and self.scheme.total_beds:
            staff_ratio = self.on_site_staff_count / self.scheme.total_beds * 100
            if 2 <= staff_ratio <= 5:  # Optimal staffing
                score += 0.5
            elif staff_ratio > 8:  # Overstaffed
                score -= 0.5
        
        # Service automation
        if self.laundry_facilities in ['shared_card', 'in_unit']:
            score += 0.5
        
        return max(1, min(5, round(score)))
    
    def get_operational_summary(self) -> Dict[str, Any]:
        """Get comprehensive operational summary."""
        return {
            'management_model': self.get_management_model_display(),
            'management_company': self.management_company or 'Self-managed',
            'amenity_score': self.amenity_score,
            'efficiency_score': self.operational_efficiency_score,
            'target_occupancy': self.target_occupancy_rate_pct,
            'security_level': self.get_security_type_display() if self.security_type else 'Basic',
            'technology_features': len(self.smart_building_features) if self.smart_building_features else 0,
            'sustainability_features': len(self.sustainability_features) if self.sustainability_features else 0
        }