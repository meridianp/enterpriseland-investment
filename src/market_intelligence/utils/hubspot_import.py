"""
Utilities for importing HubSpot data.

Provides functions for converting Excel dates, mapping country codes,
and transforming HubSpot data to Django models.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def convert_excel_date(excel_date: Any) -> Optional[datetime]:
    """
    Convert Excel decimal date to Python datetime.
    
    Excel stores dates as decimal numbers where:
    - The integer part represents days since December 30, 1899
    - The decimal part represents the fraction of a day (time)
    
    Args:
        excel_date: Excel date as float or string
        
    Returns:
        datetime object or None if conversion fails
    """
    if not excel_date:
        return None
    
    try:
        # Handle both float and string inputs
        if isinstance(excel_date, str):
            # Skip if it's not a numeric string
            if not excel_date.replace('.', '').replace('-', '').isdigit():
                return None
            excel_date = float(excel_date)
        elif not isinstance(excel_date, (int, float)):
            return None
        
        # Excel base date (December 30, 1899)
        # Note: Excel has a leap year bug for 1900, but we handle dates after that
        base_date = datetime(1899, 12, 30)
        
        # Calculate the date
        days = int(excel_date)
        time_fraction = excel_date - days
        
        # Add days to base date
        result = base_date + timedelta(days=days)
        
        # Add time component if present
        if time_fraction > 0:
            total_seconds = time_fraction * 24 * 60 * 60
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = int(total_seconds % 60)
            
            # Ensure hours, minutes, seconds are within valid ranges
            hours = min(hours, 23)
            minutes = min(minutes, 59)
            seconds = min(seconds, 59)
            
            result = result.replace(hour=hours, minute=minutes, second=seconds)
        
        return result
        
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Failed to convert Excel date {excel_date}: {str(e)}")
        return None


# Country name to ISO 3166-1 alpha-2 code mapping
COUNTRY_MAPPINGS = {
    # United Kingdom variants
    'United Kingdom': 'GB',
    'UK': 'GB',
    'England': 'GB',
    'Scotland': 'GB',
    'Wales': 'GB',
    'Northern Ireland': 'GB',
    'Great Britain': 'GB',
    
    # United States variants
    'United States': 'US',
    'USA': 'US',
    'United States of America': 'US',
    'U.S.A.': 'US',
    'U.S.': 'US',
    'America': 'US',
    
    # Other English-speaking countries
    'Canada': 'CA',
    'Australia': 'AU',
    'New Zealand': 'NZ',
    'Ireland': 'IE',
    'Republic of Ireland': 'IE',
    
    # European countries
    'Germany': 'DE',
    'France': 'FR',
    'Spain': 'ES',
    'Italy': 'IT',
    'Netherlands': 'NL',
    'The Netherlands': 'NL',
    'Belgium': 'BE',
    'Switzerland': 'CH',
    'Austria': 'AT',
    'Sweden': 'SE',
    'Norway': 'NO',
    'Denmark': 'DK',
    'Finland': 'FI',
    'Poland': 'PL',
    'Portugal': 'PT',
    'Greece': 'GR',
    'Czech Republic': 'CZ',
    'Hungary': 'HU',
    'Romania': 'RO',
    'Bulgaria': 'BG',
    'Croatia': 'HR',
    'Slovakia': 'SK',
    'Slovenia': 'SI',
    'Luxembourg': 'LU',
    'Estonia': 'EE',
    'Latvia': 'LV',
    'Lithuania': 'LT',
    'Malta': 'MT',
    'Cyprus': 'CY',
    
    # Asian countries
    'China': 'CN',
    'Japan': 'JP',
    'India': 'IN',
    'South Korea': 'KR',
    'Singapore': 'SG',
    'Hong Kong': 'HK',
    'Taiwan': 'TW',
    'Malaysia': 'MY',
    'Thailand': 'TH',
    'Indonesia': 'ID',
    'Philippines': 'PH',
    'Vietnam': 'VN',
    'Pakistan': 'PK',
    'Bangladesh': 'BD',
    'Sri Lanka': 'LK',
    'Nepal': 'NP',
    
    # Middle East
    'United Arab Emirates': 'AE',
    'UAE': 'AE',
    'Saudi Arabia': 'SA',
    'Israel': 'IL',
    'Turkey': 'TR',
    'Qatar': 'QA',
    'Kuwait': 'KW',
    'Bahrain': 'BH',
    'Oman': 'OM',
    'Jordan': 'JO',
    'Lebanon': 'LB',
    'Iraq': 'IQ',
    'Iran': 'IR',
    
    # Africa
    'South Africa': 'ZA',
    'Egypt': 'EG',
    'Nigeria': 'NG',
    'Kenya': 'KE',
    'Morocco': 'MA',
    'Tunisia': 'TN',
    'Algeria': 'DZ',
    'Ghana': 'GH',
    'Ethiopia': 'ET',
    'Uganda': 'UG',
    'Tanzania': 'TZ',
    'Zimbabwe': 'ZW',
    
    # Americas
    'Mexico': 'MX',
    'Brazil': 'BR',
    'Argentina': 'AR',
    'Chile': 'CL',
    'Colombia': 'CO',
    'Peru': 'PE',
    'Venezuela': 'VE',
    'Ecuador': 'EC',
    'Uruguay': 'UY',
    'Paraguay': 'PY',
    'Bolivia': 'BO',
    'Costa Rica': 'CR',
    'Panama': 'PA',
    'Guatemala': 'GT',
    'Honduras': 'HN',
    'El Salvador': 'SV',
    'Nicaragua': 'NI',
    'Dominican Republic': 'DO',
    'Cuba': 'CU',
    'Jamaica': 'JM',
    'Haiti': 'HT',
    'Trinidad and Tobago': 'TT',
    'Barbados': 'BB',
    
    # Oceania
    'Fiji': 'FJ',
    'Papua New Guinea': 'PG',
    
    # Special cases and regions
    'Conwy': 'GB',  # Welsh county
}


def map_country_to_iso(country_name: Optional[str]) -> str:
    """
    Map country name to ISO 3166-1 alpha-2 code.
    
    Args:
        country_name: Country name string
        
    Returns:
        ISO 3166-1 alpha-2 code or empty string if not found
    """
    if not country_name:
        return ''
    
    # Clean the country name
    country_name = country_name.strip()
    
    # Direct lookup
    if country_name in COUNTRY_MAPPINGS:
        return COUNTRY_MAPPINGS[country_name]
    
    # Try case-insensitive lookup
    country_lower = country_name.lower()
    for name, code in COUNTRY_MAPPINGS.items():
        if name.lower() == country_lower:
            return code
    
    # If it's already a 2-letter code, return it
    if len(country_name) == 2 and country_name.isalpha():
        return country_name.upper()
    
    logger.warning(f"Unknown country name: {country_name}")
    return ''


def map_industry_to_business_model(industry: Optional[str]) -> str:
    """
    Map HubSpot industry to business model categories.
    
    Args:
        industry: Industry string from HubSpot
        
    Returns:
        Business model string suitable for TargetCompany
    """
    if not industry:
        return 'other'
    
    industry_lower = industry.lower()
    
    # Education and student housing
    if any(term in industry_lower for term in ['education', 'university', 'college', 'student']):
        return 'operator'
    
    # Real estate and development
    if any(term in industry_lower for term in ['real estate', 'property', 'development', 'construction']):
        return 'developer'
    
    # Technology
    if any(term in industry_lower for term in ['technology', 'software', 'tech', 'it', 'computer']):
        return 'technology'
    
    # Investment and finance
    if any(term in industry_lower for term in ['investment', 'finance', 'capital', 'fund', 'equity']):
        return 'investor'
    
    # Hospitality (relevant for student accommodation)
    if any(term in industry_lower for term in ['hospitality', 'accommodation', 'hotel', 'housing']):
        return 'operator'
    
    # Telecommunications (from the data)
    if 'telecom' in industry_lower:
        return 'technology'
    
    # Manufacturing and goods
    if any(term in industry_lower for term in ['manufacturing', 'goods', 'retail', 'sporting']):
        return 'other'
    
    return 'other'


def clean_phone_number(phone: Optional[str]) -> str:
    """
    Clean and standardize phone number format.
    
    Args:
        phone: Phone number string
        
    Returns:
        Cleaned phone number or empty string
    """
    if not phone:
        return ''
    
    # Remove common formatting and whitespace
    phone = phone.strip()
    
    # Keep the original format but clean obvious issues
    if phone.startswith(' '):
        phone = phone.strip()
    
    # Limit length to field maximum (20 characters)
    return phone[:20]


def parse_company_size(size_str: Optional[str]) -> str:
    """
    Parse company size string to TargetCompany.CompanySize choices.
    
    Args:
        size_str: Company size string from HubSpot
        
    Returns:
        CompanySize choice value
    """
    if not size_str:
        return 'unknown'
    
    size_lower = size_str.lower()
    
    # Check for employee count patterns
    if any(term in size_lower for term in ['<50', 'small', 'startup']):
        return 'startup'
    elif any(term in size_lower for term in ['50-200', 'medium']):
        return 'small'
    elif any(term in size_lower for term in ['200-1000']):
        return 'medium'
    elif any(term in size_lower for term in ['>1000', 'large', 'enterprise']):
        return 'large'
    
    return 'unknown'