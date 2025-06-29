"""
Core value objects for the CASA Due Diligence model.

These classes represent fundamental data types that combine
multiple primitive values into meaningful business concepts.
"""

from decimal import Decimal
from typing import Optional
import pycountry
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class CountryISO:
    """
    Two-letter country code (ISO 3166-1 alpha-2) that is automatically validated.
    
    Examples: "GB" for United Kingdom, "DE" for Germany, "ES" for Spain
    """
    
    @classmethod
    def validate(cls, value: str) -> str:
        """Ensures the country code is valid according to ISO standards."""
        if not isinstance(value, str):
            raise ValidationError("Country code must be a string")
        
        code = value.upper()
        if pycountry.countries.get(alpha_2=code) is None:
            raise ValidationError(f"{code!r} is not a valid ISO 3166-1 alpha-2 country code")
        return code
    
    @classmethod
    def get_country_name(cls, code: str) -> Optional[str]:
        """Get the full country name from the ISO code."""
        try:
            country = pycountry.countries.get(alpha_2=code.upper())
            return country.name if country else None
        except:
            return None


class MoneyField(models.Model):
    """
    Precise monetary amount with currency specification.
    
    Combines amount and currency into a single coherent value object.
    """
    amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Non-negative monetary amount with decimal precision"
    )
    currency = models.CharField(
        max_length=3,
        choices=[
            ('AED', 'United Arab Emirates dirham'),
            ('EUR', 'Euro'),
            ('GBP', 'British pound sterling'),
            ('SAR', 'Saudi riyal'),
            ('USD', 'United States dollar'),
        ],
        help_text="ISO 4217 currency code"
    )
    
    class Meta:
        abstract = True
    
    def __str__(self) -> str:
        """Returns a formatted string like '£1,250,000.00'"""
        currency_symbols = {
            'GBP': '£',
            'EUR': '€', 
            'USD': '$',
            'AED': 'AED ',
            'SAR': 'SAR '
        }
        symbol = currency_symbols.get(self.currency, f"{self.currency} ")
        return f"{symbol}{self.amount:,.2f}"
    
    def to_decimal_string(self) -> str:
        """Returns amount as decimal string for calculations."""
        return str(self.amount)


class AreaField(models.Model):
    """
    Physical space measurement with explicit unit specification.
    
    Combines value and unit with conversion capabilities.
    """
    value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Positive area magnitude"
    )
    unit = models.CharField(
        max_length=10,
        choices=[
            ('SQ_FT', 'Square Feet'),
            ('SQ_M', 'Square Meters'),
        ],
        help_text="Unit of measure"
    )
    
    class Meta:
        abstract = True
    
    def to_sq_ft(self) -> Decimal:
        """Convert to square feet regardless of stored unit."""
        if self.unit == 'SQ_FT':
            return self.value
        # Convert from sq meters to sq feet (1 sq m = 10.764 sq ft)
        return self.value * Decimal("10.764")
    
    def to_sq_m(self) -> Decimal:
        """Convert to square meters regardless of stored unit."""
        if self.unit == 'SQ_M':
            return self.value
        # Convert from sq feet to sq meters (1 sq ft = 0.0929 sq m)
        return self.value * Decimal("0.0929")
    
    def __str__(self) -> str:
        """Returns a formatted string like '25,000 sq ft'"""
        unit_display = "sq ft" if self.unit == 'SQ_FT' else "sq m"
        return f"{self.value:,.0f} {unit_display}"


class MetricScore(models.Model):
    """
    Weighted scoring component used in Gold-Standard assessments.
    
    Each assessment criterion has both a performance score and importance weight.
    """
    score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Performance rating from 1 (poor) to 5 (excellent)"
    )
    weight = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Importance weighting from 1 (minor) to 5 (critical)"
    )
    justification = models.TextField(
        blank=True,
        help_text="Explanation for the assigned score"
    )
    
    class Meta:
        abstract = True
    
    @property
    def weighted_score(self) -> int:
        """
        Calculate weighted score (score × weight).
        
        Maximum possible value is 25 (score 5 × weight 5).
        """
        return self.score * self.weight
    
    def __str__(self) -> str:
        return f"Score: {self.score} × Weight: {self.weight} = {self.weighted_score}"


# Utility functions for working with value objects

def format_currency(amount: Decimal, currency: str) -> str:
    """Format a currency amount with appropriate symbol."""
    currency_symbols = {
        'GBP': '£',
        'EUR': '€', 
        'USD': '$',
        'AED': 'AED ',
        'SAR': 'SAR '
    }
    symbol = currency_symbols.get(currency, f"{currency} ")
    return f"{symbol}{amount:,.2f}"


def convert_area(value: Decimal, from_unit: str, to_unit: str) -> Decimal:
    """Convert area between square feet and square meters."""
    if from_unit == to_unit:
        return value
    
    if from_unit == 'SQ_FT' and to_unit == 'SQ_M':
        return value * Decimal("0.0929")
    elif from_unit == 'SQ_M' and to_unit == 'SQ_FT':
        return value * Decimal("10.764")
    else:
        raise ValueError(f"Unsupported unit conversion: {from_unit} to {to_unit}")


def validate_country_code(code: str) -> str:
    """Validate and normalize ISO country code."""
    return CountryISO.validate(code)