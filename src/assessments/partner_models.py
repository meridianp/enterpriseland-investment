"""
Enhanced partner information models for the CASA Due Diligence Platform.

These models implement the comprehensive partner assessment framework
from the original CASA data model specification.
"""

from decimal import Decimal
from typing import Optional, List, Dict
from datetime import datetime, date

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, URLValidator
from django.core.exceptions import ValidationError

from .base_models import BaseAssessmentModel, FinancialMixin, RiskAssessmentMixin
from .enums import Currency, DebtRatioCategory, RiskLevel, RelationshipType
from .validation import (
    CountryCodeValidator, 
    ShareholdingValidator,
    validate_positive_decimal,
    validate_year_range,
    get_country_code_validator
)


class OfficeLocation(BaseAssessmentModel):
    """
    Physical location of a company office with city and country.
    
    Used to track the geographic footprint of development partners.
    """
    
    partner = models.ForeignKey(
        'DevelopmentPartner',
        on_delete=models.CASCADE,
        related_name='office_locations',
        help_text="Development partner this office belongs to"
    )
    
    city = models.CharField(
        max_length=100,
        help_text="City name of the office location"
    )
    
    country = models.CharField(
        max_length=2,
        validators=[get_country_code_validator()],
        help_text="ISO 3166-1 alpha-2 country code"
    )
    
    is_headquarters = models.BooleanField(
        default=False,
        help_text="Whether this is the headquarters office"
    )
    
    employee_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of employees at this location"
    )
    
    class Meta:
        db_table = 'office_locations'
        unique_together = ['partner', 'city', 'country']
        verbose_name = 'Office Location'
        verbose_name_plural = 'Office Locations'
    
    def __str__(self) -> str:
        """Returns a formatted string like 'London, United Kingdom'"""
        # In a real implementation, you'd use pycountry to get the full name
        return f"{self.city}, {self.country}"
    
    @property
    def country_name(self) -> str:
        """Get the full country name from ISO code."""
        # This would use pycountry in implementation
        country_names = {
            'GB': 'United Kingdom',
            'US': 'United States',
            'DE': 'Germany',
            'FR': 'France',
            'AE': 'United Arab Emirates',
            'SA': 'Saudi Arabia'
        }
        return country_names.get(self.country, self.country)


class FinancialPartner(BaseAssessmentModel):
    """
    Financial partners and relationships for development partners.
    
    Tracks equity partners, debt providers, and joint venture participants.
    """
    
    partner = models.ForeignKey(
        'DevelopmentPartner',
        on_delete=models.CASCADE,
        related_name='financial_partners',
        help_text="Development partner this financial relationship belongs to"
    )
    
    name = models.CharField(
        max_length=255,
        help_text="Name of the financial partner"
    )
    
    relationship_type = models.CharField(
        max_length=20,
        choices=RelationshipType.choices,
        help_text="Type of financial relationship"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description of the relationship and terms"
    )
    
    commitment_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Financial commitment amount"
    )
    
    commitment_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of financial commitment"
    )
    
    relationship_start_date = models.DateField(
        null=True,
        blank=True,
        help_text="When the relationship began"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this relationship is currently active"
    )
    
    class Meta:
        db_table = 'financial_partners'
        unique_together = ['partner', 'name', 'relationship_type']
        verbose_name = 'Financial Partner'
        verbose_name_plural = 'Financial Partners'
    
    def __str__(self) -> str:
        return f"{self.name} ({self.get_relationship_type_display()})"
    
    @property
    def formatted_commitment(self) -> str:
        """Format the commitment amount with currency."""
        if self.commitment_amount and self.commitment_currency:
            symbol = Currency.get_symbol(self.commitment_currency)
            return f"{symbol}{self.commitment_amount:,.2f}"
        return "Not specified"


class KeyShareholder(BaseAssessmentModel):
    """
    Key shareholders and ownership percentages for development partners.
    
    Tracks major shareholders and their ownership stakes.
    """
    
    partner = models.ForeignKey(
        'DevelopmentPartner',
        on_delete=models.CASCADE,
        related_name='key_shareholders',
        help_text="Development partner this shareholding relates to"
    )
    
    name = models.CharField(
        max_length=255,
        help_text="Name of the shareholder"
    )
    
    ownership_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Ownership percentage (0-100)"
    )
    
    shareholder_type = models.CharField(
        max_length=50,
        choices=[
            ('individual', 'Individual'),
            ('corporation', 'Corporation'),
            ('fund', 'Investment Fund'),
            ('institution', 'Financial Institution'),
            ('government', 'Government Entity'),
            ('other', 'Other'),
        ],
        help_text="Type of shareholder entity"
    )
    
    is_controlling = models.BooleanField(
        default=False,
        help_text="Whether this shareholder has controlling interest"
    )
    
    class Meta:
        db_table = 'key_shareholders'
        unique_together = ['partner', 'name']
        verbose_name = 'Key Shareholder'
        verbose_name_plural = 'Key Shareholders'
    
    def __str__(self) -> str:
        return f"{self.name} ({self.ownership_percentage}%)"


class GeneralInformation(BaseAssessmentModel):
    """
    Basic information about the development partner organization.
    
    Covers identity, branding, and geographic presence of the company.
    """
    
    partner = models.OneToOneField(
        'DevelopmentPartner',
        on_delete=models.CASCADE,
        related_name='general_info',
        help_text="Development partner this information belongs to"
    )
    
    # Core identification
    trading_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Operating or brand name if different from registered name"
    )
    
    legal_structure = models.CharField(
        max_length=100,
        choices=[
            ('ltd', 'Private Limited Company'),
            ('plc', 'Public Limited Company'),
            ('llp', 'Limited Liability Partnership'),
            ('partnership', 'Partnership'),
            ('sole_trader', 'Sole Trader'),
            ('other', 'Other'),
        ],
        blank=True,
        help_text="Legal structure of the organization"
    )
    
    registration_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Company registration number"
    )
    
    # Geographic information
    headquarter_city = models.CharField(
        max_length=100,
        blank=True,
        help_text="City location of headquarters"
    )
    
    headquarter_country = models.CharField(
        max_length=2,
        validators=[get_country_code_validator()],
        blank=True,
        help_text="Country of headquarters (ISO code)"
    )
    
    # Timeline information
    year_established = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[validate_year_range],
        help_text="Year the company was founded"
    )
    
    # Contact information
    website_url = models.URLField(
        blank=True,
        validators=[URLValidator()],
        help_text="Company's primary website address"
    )
    
    primary_contact_email = models.EmailField(
        blank=True,
        help_text="Primary business contact email"
    )
    
    primary_contact_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Primary business contact phone"
    )
    
    # Additional information
    business_description = models.TextField(
        blank=True,
        help_text="Description of the company's business activities"
    )
    
    class Meta:
        db_table = 'general_information'
        verbose_name = 'General Information'
    
    def __str__(self) -> str:
        return f"General Info for {self.partner.company_name}"
    
    @property
    def company_age(self) -> Optional[int]:
        """Calculate company age in years."""
        if self.year_established:
            return datetime.now().year - self.year_established
        return None
    
    @property
    def has_international_presence(self) -> bool:
        """Check if company has offices in multiple countries."""
        if not self.headquarter_country:
            return False
        
        office_countries = set(
            self.partner.office_locations.values_list('country', flat=True)
        )
        office_countries.add(self.headquarter_country)
        
        return len(office_countries) > 1


class OperationalInformation(BaseAssessmentModel):
    """
    Operating scale and track record of the development partner.
    
    Quantifies development experience, team size, and pipeline strength.
    """
    
    partner = models.OneToOneField(
        'DevelopmentPartner',
        on_delete=models.CASCADE,
        related_name='operational_info',
        help_text="Development partner this information belongs to"
    )
    
    # Team and workforce
    size_of_development_team = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of dedicated development professionals"
    )
    
    number_of_employees = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total employee headcount across all departments"
    )
    
    # PBSA experience
    completed_pbsa_schemes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of PBSA projects completed to date"
    )
    
    years_of_pbsa_experience = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Years of experience developing PBSA properties"
    )
    
    total_pbsa_beds_delivered = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total number of PBSA beds completed to date"
    )
    
    # Current pipeline
    schemes_in_development = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total number of schemes currently in development"
    )
    
    pbsa_schemes_in_development = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of PBSA schemes currently in development"
    )
    
    beds_in_development = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of PBSA beds currently in development"
    )
    
    # Location-specific experience
    completed_schemes_in_target_location = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of completed schemes in current target location"
    )
    
    class Meta:
        db_table = 'operational_information'
        verbose_name = 'Operational Information'
    
    def __str__(self) -> str:
        return f"Operational Info for {self.partner.company_name}"
    
    @property
    def pbsa_specialization_pct(self) -> Optional[float]:
        """
        Percentage of current pipeline that is PBSA.
        
        Measures focus/specialization in student accommodation.
        """
        if (self.schemes_in_development is None or 
            self.schemes_in_development == 0 or
            self.pbsa_schemes_in_development is None):
            return None
            
        return round(
            (self.pbsa_schemes_in_development / self.schemes_in_development) * 100,
            1
        )
    
    @property
    def avg_pbsa_scheme_size(self) -> Optional[int]:
        """
        Average number of beds per completed PBSA scheme.
        
        Indicates typical project scale.
        """
        if (self.completed_pbsa_schemes is None or
            self.completed_pbsa_schemes == 0 or
            self.total_pbsa_beds_delivered is None):
            return None
            
        return round(self.total_pbsa_beds_delivered / self.completed_pbsa_schemes)
    
    @property
    def development_team_ratio(self) -> Optional[float]:
        """Ratio of development team to total employees."""
        if (self.size_of_development_team is None or
            self.number_of_employees is None or
            self.number_of_employees == 0):
            return None
            
        return round(
            (self.size_of_development_team / self.number_of_employees) * 100,
            1
        )


class StakeholderInformation(BaseAssessmentModel):
    """
    Ownership structure and key financial relationships.
    
    Identifies principal owners and financial partners for risk assessment.
    """
    
    partner = models.OneToOneField(
        'DevelopmentPartner',
        on_delete=models.CASCADE,
        related_name='stakeholder_info',
        help_text="Development partner this information belongs to"
    )
    
    # Ownership structure
    shareholding_structure = models.TextField(
        blank=True,
        help_text="Narrative description of ownership and shareholding breakdown"
    )
    
    ultimate_parent_company = models.CharField(
        max_length=255,
        blank=True,
        help_text="Ultimate controlling entity, if applicable"
    )
    
    # Public listing information
    publicly_listed = models.BooleanField(
        null=True,
        blank=True,
        help_text="Whether the company is publicly traded on a stock exchange"
    )
    
    stock_exchange = models.CharField(
        max_length=100,
        blank=True,
        help_text="Stock exchange where shares are listed, if applicable"
    )
    
    ticker_symbol = models.CharField(
        max_length=10,
        blank=True,
        help_text="Stock ticker symbol if publicly listed"
    )
    
    class Meta:
        db_table = 'stakeholder_information'
        verbose_name = 'Stakeholder Information'
    
    def __str__(self) -> str:
        return f"Stakeholder Info for {self.partner.company_name}"
    
    @property
    def has_institutional_backing(self) -> bool:
        """
        Whether the partner has institutional financial backing.
        
        Institutional backing can indicate financial stability.
        """
        institutional_keywords = [
            'fund', 'capital', 'investment', 'asset', 'management',
            'bank', 'insurance', 'pension', 'partners', 'group'
        ]
        
        # Check financial partners
        for partner in self.partner.financial_partners.all():
            for keyword in institutional_keywords:
                if keyword.lower() in partner.name.lower():
                    return True
        
        # Check key shareholders
        for shareholder in self.partner.key_shareholders.all():
            if shareholder.shareholder_type in ['fund', 'institution']:
                return True
            for keyword in institutional_keywords:
                if keyword.lower() in shareholder.name.lower():
                    return True
        
        return False
    
    @property
    def total_tracked_ownership(self) -> float:
        """Sum of all tracked shareholding percentages."""
        return sum(
            self.partner.key_shareholders.values_list('ownership_percentage', flat=True)
        ) or 0.0
    
    @property
    def ownership_concentration(self) -> str:
        """Categorize ownership concentration."""
        max_ownership = self.partner.key_shareholders.aggregate(
            models.Max('ownership_percentage')
        )['ownership_percentage__max'] or 0
        
        if max_ownership >= 75:
            return 'Highly Concentrated'
        elif max_ownership >= 50:
            return 'Concentrated'
        elif max_ownership >= 25:
            return 'Moderately Concentrated'
        else:
            return 'Dispersed'
    
    def clean(self):
        """Validate stakeholder information."""
        super().clean()
        
        # Validate shareholding doesn't exceed 100%
        if self.total_tracked_ownership > 100:
            raise ValidationError(
                f"Total tracked ownership ({self.total_tracked_ownership:.1f}%) "
                f"cannot exceed 100%"
            )


# Enhanced DevelopmentPartner model that ties everything together
class DevelopmentPartner(BaseAssessmentModel, FinancialMixin):
    """
    Enhanced development partner model with comprehensive information structure.
    
    This is the main entity that aggregates all partner-related information.
    """
    
    # Core identification (kept for backward compatibility)
    company_name = models.CharField(
        max_length=255,
        help_text="Legal registered name of the company"
    )
    
    # Status tracking
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this partner is currently active"
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
    _total_countries = models.PositiveIntegerField(
        default=0,
        help_text="Cached count of countries with offices"
    )
    
    _has_pbsa_experience = models.BooleanField(
        default=False,
        help_text="Cached flag for PBSA experience"
    )
    
    class Meta:
        db_table = 'development_partners'
        verbose_name = 'Development Partner'
        verbose_name_plural = 'Development Partners'
        ordering = ['company_name']
    
    def __str__(self) -> str:
        return self.company_name
    
    @property
    def total_countries(self) -> int:
        """Count of unique countries where the company has offices."""
        countries = set()
        
        # Add headquarters country
        if hasattr(self, 'general_info') and self.general_info.headquarter_country:
            countries.add(self.general_info.headquarter_country)
        
        # Add office countries
        for office in self.office_locations.all():
            countries.add(office.country)
        
        return len(countries)
    
    @property
    def has_offices_in_target_location(self) -> bool:
        """
        Determine if the partner has offices in target location.
        
        This would need to be customized based on specific assessment context.
        """
        # Placeholder - would be implemented based on assessment requirements
        return False
    
    @property
    def financial_summary(self) -> Dict[str, any]:
        """Get summary of financial information."""
        if not hasattr(self, 'financial_info'):
            return {}
        
        financial_info = self.financial_info
        return {
            'net_assets': financial_info.net_assets_amount,
            'currency': financial_info.net_assets_currency,
            'profit_margin': financial_info.profit_margin_pct,
            'current_ratio': financial_info.current_ratio,
            'ebitda_margin': financial_info.ebitda_margin_pct,
            'financial_health_score': financial_info.financial_health_score.get('score'),
            'last_updated': financial_info.updated_at
        }
    
    def update_cached_fields(self):
        """Update denormalized fields for performance."""
        self._total_countries = self.total_countries
        
        if hasattr(self, 'operational_info'):
            self._has_pbsa_experience = (
                self.operational_info.completed_pbsa_schemes is not None and
                self.operational_info.completed_pbsa_schemes > 0
            )
        
        self.save(update_fields=['_total_countries', '_has_pbsa_experience'])
    
    def get_assessment_summary(self) -> Dict[str, any]:
        """Get comprehensive assessment summary."""
        summary = {
            'company_name': self.company_name,
            'countries_present': self.total_countries,
            'has_pbsa_experience': self._has_pbsa_experience,
        }
        
        # Add operational metrics
        if hasattr(self, 'operational_info'):
            op_info = self.operational_info
            summary.update({
                'pbsa_schemes_completed': op_info.completed_pbsa_schemes,
                'total_beds_delivered': op_info.total_pbsa_beds_delivered,
                'pbsa_specialization': op_info.pbsa_specialization_pct,
                'avg_scheme_size': op_info.avg_pbsa_scheme_size,
            })
        
        # Add financial health indicators
        if hasattr(self, 'credit_info'):
            credit_info = self.credit_info
            summary.update({
                'leverage_band': credit_info.leverage_band,
                'liquidity_risk': credit_info.liquidity_risk,
                'credit_risk_score': credit_info.credit_risk_score.get('score'),
                'interest_coverage': credit_info.interest_coverage_ratio,
            })
        
        return summary