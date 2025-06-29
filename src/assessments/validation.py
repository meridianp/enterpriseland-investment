"""
Validation utilities for the CASA Due Diligence model.

Provides custom validators, validation mixins, and business rule validation.
"""

import re
from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
import pycountry


class CountryCodeValidator:
    """Validator for ISO 3166-1 alpha-2 country codes."""
    
    def __call__(self, value: str):
        """Validate that the country code is a valid ISO code."""
        if not isinstance(value, str):
            raise ValidationError("Country code must be a string")
        
        code = value.upper()
        if len(code) != 2:
            raise ValidationError("Country code must be exactly 2 characters")
        
        if pycountry.countries.get(alpha_2=code) is None:
            raise ValidationError(f"'{code}' is not a valid ISO 3166-1 alpha-2 country code")


class PercentageValidator:
    """Validator for percentage values."""
    
    def __init__(self, min_value: float = 0.0, max_value: float = 100.0):
        self.min_value = min_value
        self.max_value = max_value
    
    def __call__(self, value: float):
        """Validate percentage is within acceptable range."""
        if value < self.min_value or value > self.max_value:
            raise ValidationError(
                f"Percentage must be between {self.min_value}% and {self.max_value}%"
            )


class ShareholdingValidator:
    """Validator for shareholding percentages that ensures they don't exceed 100%."""
    
    def __call__(self, shareholdings: Dict[str, float]):
        """Validate that total shareholding doesn't exceed 100%."""
        if not isinstance(shareholdings, dict):
            raise ValidationError("Shareholdings must be a dictionary")
        
        total = sum(shareholdings.values())
        if total > 100.0:
            raise ValidationError(
                f"Total shareholding percentage ({total:.2f}%) cannot exceed 100%"
            )
        
        # Validate individual percentages
        for shareholder, percentage in shareholdings.items():
            if percentage < 0 or percentage > 100:
                raise ValidationError(
                    f"Individual shareholding for '{shareholder}' ({percentage:.2f}%) "
                    f"must be between 0% and 100%"
                )


class MetricScoreValidator:
    """Validator for metric scores and weights."""
    
    def __call__(self, score_data: Dict[str, int]):
        """Validate metric score and weight are within acceptable ranges."""
        score = score_data.get('score')
        weight = score_data.get('weight')
        
        if score is not None and (score < 1 or score > 5):
            raise ValidationError("Score must be between 1 and 5")
        
        if weight is not None and (weight < 1 or weight > 5):
            raise ValidationError("Weight must be between 1 and 5")


class BusinessRuleValidator:
    """
    Validates complex business rules that span multiple fields.
    
    Used for cross-field validation in assessment models.
    """
    
    @staticmethod
    def validate_assessment_consistency(assessment_data: Dict[str, Any]) -> List[str]:
        """
        Validate consistency across assessment fields.
        
        Returns list of validation errors found.
        """
        errors = []
        
        # Check that scheme assessments have scheme data
        if (assessment_data.get('assessment_type') in ['SCHEME', 'COMBINED'] and
            not assessment_data.get('scheme')):
            errors.append("Scheme assessments must have associated scheme data")
        
        # Check that partner assessments have partner data
        if (assessment_data.get('assessment_type') in ['PARTNER', 'COMBINED'] and
            not assessment_data.get('partner')):
            errors.append("Partner assessments must have associated partner data")
        
        # Check financial data consistency
        if assessment_data.get('financials'):
            financials = assessment_data['financials']
            if (financials.get('net_assets_amount') and 
                financials.get('net_current_assets_amount')):
                net_assets = financials['net_assets_amount']
                net_current = financials['net_current_assets_amount']
                if net_current > net_assets:
                    errors.append(
                        "Net current assets cannot exceed total net assets"
                    )
        
        return errors
    
    @staticmethod
    def validate_site_metrics(site_data: Dict[str, Any]) -> List[str]:
        """
        Validate site and scheme metrics for consistency.
        
        Returns list of validation errors found.
        """
        errors = []
        
        site_area = site_data.get('site_area_value')
        internal_area = site_data.get('net_internal_area_value')
        total_beds = site_data.get('total_pbsa_beds')
        
        # Check that internal area isn't larger than site area (considering height)
        if (site_area and internal_area and 
            internal_area > site_area * 10):  # Allow up to 10 stories
            errors.append(
                "Net internal area seems unusually large compared to site area"
            )
        
        # Check reasonable beds per area ratio
        if internal_area and total_beds:
            area_per_bed = internal_area / total_beds
            if area_per_bed < 150:  # sq ft minimum
                errors.append(
                    f"Area per bed ({area_per_bed:.0f} sq ft) is below minimum standards"
                )
            elif area_per_bed > 1000:  # sq ft maximum
                errors.append(
                    f"Area per bed ({area_per_bed:.0f} sq ft) seems unusually large"
                )
        
        return errors
    
    @staticmethod
    def validate_financial_ratios(financial_data: Dict[str, Any]) -> List[str]:
        """
        Validate financial ratios for reasonableness.
        
        Returns list of validation errors found.
        """
        errors = []
        
        # Check debt ratios
        debt_ratio = financial_data.get('debt_to_total_assets_pct')
        if debt_ratio and debt_ratio > 95:
            errors.append(
                f"Debt ratio ({debt_ratio:.1f}%) is extremely high and may indicate distress"
            )
        
        # Check profit margins
        revenue = financial_data.get('latest_annual_revenue_amount')
        profit = financial_data.get('net_profit_before_tax_amount')
        if revenue and profit and revenue > 0:
            margin = (profit / revenue) * 100
            if margin < -50:
                errors.append(
                    f"Profit margin ({margin:.1f}%) indicates significant losses"
                )
            elif margin > 50:
                errors.append(
                    f"Profit margin ({margin:.1f}%) seems unusually high"
                )
        
        return errors


# Regex validators for common formats

email_validator = RegexValidator(
    regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    message="Enter a valid email address"
)

phone_validator = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message="Phone number must be between 9-15 digits and may start with +"
)

website_validator = RegexValidator(
    regex=r'^https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?$',
    message="Enter a valid website URL"
)

postcode_uk_validator = RegexValidator(
    regex=r'^[A-Z]{1,2}[0-9R][0-9A-Z]? [0-9][ABD-HJLNP-UW-Z]{2}$',
    message="Enter a valid UK postcode (e.g., SW1A 1AA)"
)


def validate_positive_decimal(value: Decimal) -> None:
    """Validate that a decimal value is positive."""
    if value is not None and value < 0:
        raise ValidationError("Value must be positive")


def validate_assessment_score_range(value: int) -> None:
    """Validate assessment scores are within 1-5 range."""
    if value < 1 or value > 5:
        raise ValidationError("Assessment scores must be between 1 and 5")


def validate_year_range(value: int) -> None:
    """Validate year is within reasonable range."""
    current_year = datetime.now().year
    if value < 1800 or value > current_year:
        raise ValidationError(
            f"Year must be between 1800 and {current_year}"
        )


def validate_future_date(value: date) -> None:
    """Validate that a date is in the future."""
    if value <= date.today():
        raise ValidationError("Date must be in the future")


def validate_past_date(value: date) -> None:
    """Validate that a date is in the past."""
    if value >= date.today():
        raise ValidationError("Date must be in the past")


# Custom field validators for Django models

def get_country_code_validator():
    """Get instance of country code validator for use in model fields."""
    return CountryCodeValidator()


def get_percentage_validator(min_val: float = 0.0, max_val: float = 100.0):
    """Get instance of percentage validator with custom range."""
    return PercentageValidator(min_val, max_val)


def get_shareholding_validator():
    """Get instance of shareholding validator for use in model fields."""
    return ShareholdingValidator()