"""
Enhanced enum classes for the CASA Due Diligence model.

Extends the basic Django TextChoices with validation and utility methods.
"""

from django.db import models
from typing import List, Dict


class Currency(models.TextChoices):
    """
    Officially recognized currencies for financial values used in assessments.
    
    Each currency follows the ISO 4217 standard with its three-letter code.
    """
    AED = 'AED', 'United Arab Emirates dirham'
    EUR = 'EUR', 'Euro'
    GBP = 'GBP', 'British pound sterling'
    SAR = 'SAR', 'Saudi riyal'
    USD = 'USD', 'United States dollar'
    
    @classmethod
    def get_symbol(cls, currency_code: str) -> str:
        """Get the currency symbol for a given currency code."""
        symbols = {
            cls.GBP: '£',
            cls.EUR: '€',
            cls.USD: '$',
            cls.AED: 'AED ',
            cls.SAR: 'SAR '
        }
        return symbols.get(currency_code, f"{currency_code} ")
    
    @classmethod
    def get_major_currencies(cls) -> List[str]:
        """Return list of major international currencies."""
        return [cls.USD, cls.EUR, cls.GBP]


class AssessmentStatus(models.TextChoices):
    """
    Workflow status tracking the progression of a due diligence assessment.
    
    Shows where in the approval process an assessment currently stands.
    """
    DRAFT = 'DRAFT', 'Draft'
    IN_REVIEW = 'IN_REVIEW', 'In Review'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'
    NEEDS_INFO = 'NEEDS_INFO', 'Needs Additional Info'
    ARCHIVED = 'ARCHIVED', 'Archived'
    
    @classmethod
    def get_active_statuses(cls) -> List[str]:
        """Return list of statuses considered 'active' (not archived)."""
        return [cls.DRAFT, cls.IN_REVIEW, cls.NEEDS_INFO]
    
    @classmethod
    def get_final_statuses(cls) -> List[str]:
        """Return list of statuses considered 'final' decisions."""
        return [cls.APPROVED, cls.REJECTED, cls.ARCHIVED]
    
    @classmethod
    def can_transition_to(cls, from_status: str, to_status: str) -> bool:
        """Check if transition between statuses is valid."""
        valid_transitions = {
            cls.DRAFT: [cls.IN_REVIEW, cls.ARCHIVED],
            cls.IN_REVIEW: [cls.APPROVED, cls.REJECTED, cls.NEEDS_INFO, cls.DRAFT],
            cls.NEEDS_INFO: [cls.IN_REVIEW, cls.DRAFT],
            cls.APPROVED: [cls.ARCHIVED],
            cls.REJECTED: [cls.ARCHIVED],
            cls.ARCHIVED: []  # No transitions from archived
        }
        return to_status in valid_transitions.get(from_status, [])


class AssessmentDecision(models.TextChoices):
    """
    Final recommendation outcomes from the Gold-Standard assessment.
    
    These categories determine whether to proceed with a partner or scheme.
    """
    PREMIUM_PRIORITY = 'Premium/Priority', 'Premium/Priority'
    ACCEPTABLE = 'Acceptable', 'Acceptable'
    REJECT = 'Reject', 'Reject'
    
    @classmethod
    def get_positive_decisions(cls) -> List[str]:
        """Return decisions that indicate proceeding with the opportunity."""
        return [cls.PREMIUM_PRIORITY, cls.ACCEPTABLE]
    
    @classmethod
    def get_priority_order(cls) -> Dict[str, int]:
        """Return priority order for decision ranking (higher = better)."""
        return {
            cls.REJECT: 0,
            cls.ACCEPTABLE: 1,
            cls.PREMIUM_PRIORITY: 2
        }


class RiskLevel(models.TextChoices):
    """
    Standardized risk assessment levels for various risk categories.
    
    Used for consistent risk classification across all assessment areas.
    """
    LOW = 'LOW', 'Low'
    MEDIUM = 'MEDIUM', 'Medium'
    HIGH = 'HIGH', 'High'
    
    @classmethod
    def get_color_code(cls, risk_level: str) -> str:
        """Get color code for UI display (traffic light system)."""
        colors = {
            cls.LOW: 'green',
            cls.MEDIUM: 'amber',
            cls.HIGH: 'red'
        }
        return colors.get(risk_level, 'gray')
    
    @classmethod
    def get_risk_score(cls, risk_level: str) -> int:
        """Get numeric score for risk aggregation."""
        scores = {
            cls.LOW: 1,
            cls.MEDIUM: 2,
            cls.HIGH: 3
        }
        return scores.get(risk_level, 0)


class DebtRatioCategory(models.TextChoices):
    """
    Classification of debt-to-asset ratios using traffic-light color coding.
    
    Used to quickly assess the financial risk level based on leverage.
    """
    LOW = 'LOW', 'Low (0-30%)'
    MODERATE = 'MODERATE', 'Moderate (30-60%)'
    HIGH = 'HIGH', 'High (>60%)'
    
    @classmethod
    def categorize_by_percentage(cls, debt_percentage: float) -> str:
        """Categorize debt ratio by percentage value."""
        if debt_percentage <= 30:
            return cls.LOW
        elif debt_percentage <= 60:
            return cls.MODERATE
        else:
            return cls.HIGH
    
    @classmethod
    def get_threshold_ranges(cls) -> Dict[str, tuple]:
        """Get the percentage ranges for each category."""
        return {
            cls.LOW: (0, 30),
            cls.MODERATE: (30, 60),
            cls.HIGH: (60, 100)
        }


class AreaUnit(models.TextChoices):
    """
    Units of measurement for site and building areas.
    
    All area calculations must specify their unit for clarity and conversion.
    """
    SQ_FT = 'SQ_FT', 'Square Feet'
    SQ_M = 'SQ_M', 'Square Meters'
    
    @classmethod
    def get_conversion_factor(cls, from_unit: str, to_unit: str) -> float:
        """Get conversion factor between units."""
        if from_unit == to_unit:
            return 1.0
        elif from_unit == cls.SQ_FT and to_unit == cls.SQ_M:
            return 0.0929  # 1 sq ft = 0.0929 sq m
        elif from_unit == cls.SQ_M and to_unit == cls.SQ_FT:
            return 10.764  # 1 sq m = 10.764 sq ft
        else:
            raise ValueError(f"Invalid unit conversion: {from_unit} to {to_unit}")


class AssessmentType(models.TextChoices):
    """Type of assessment being performed."""
    INITIAL = 'INITIAL', 'Initial Assessment'
    REVIEW = 'REVIEW', 'Review Assessment'
    ANNUAL_UPDATE = 'ANNUAL_UPDATE', 'Annual Update'
    
    @classmethod
    def get_periodic_types(cls) -> List[str]:
        """Return assessment types that are performed periodically."""
        return [cls.REVIEW, cls.ANNUAL_UPDATE]


class ESGRating(models.TextChoices):
    """ESG maturity levels based on certifications and performance."""
    INSUFFICIENT = 'INSUFFICIENT', 'Insufficient'
    BASIC = 'BASIC', 'Basic'
    DEVELOPING = 'DEVELOPING', 'Developing'
    ESTABLISHED = 'ESTABLISHED', 'Established'
    ADVANCED = 'ADVANCED', 'Advanced'
    
    @classmethod
    def get_minimum_acceptable(cls) -> str:
        """Return minimum acceptable ESG rating."""
        return cls.DEVELOPING
    
    @classmethod
    def get_rating_score(cls, rating: str) -> int:
        """Get numeric score for ESG rating comparison."""
        scores = {
            cls.INSUFFICIENT: 1,
            cls.BASIC: 2,
            cls.DEVELOPING: 3,
            cls.ESTABLISHED: 4,
            cls.ADVANCED: 5
        }
        return scores.get(rating, 0)


class MarketPenetrationCategory(models.TextChoices):
    """Market maturity based on PBSA provision rate."""
    EMERGING = 'EMERGING', 'Emerging (<20% provision)'
    DEVELOPING = 'DEVELOPING', 'Developing (20-40% provision)'
    MATURE = 'MATURE', 'Mature (40-60% provision)'
    SATURATED = 'SATURATED', 'Saturated (>60% provision)'
    
    @classmethod
    def categorize_by_provision_rate(cls, provision_rate: float) -> str:
        """Categorize market by PBSA provision rate percentage."""
        if provision_rate < 20:
            return cls.EMERGING
        elif provision_rate < 40:
            return cls.DEVELOPING
        elif provision_rate < 60:
            return cls.MATURE
        else:
            return cls.SATURATED
    
    @classmethod
    def get_opportunity_level(cls, category: str) -> str:
        """Get investment opportunity level for each market category."""
        opportunities = {
            cls.EMERGING: 'High Opportunity',
            cls.DEVELOPING: 'Good Opportunity',
            cls.MATURE: 'Moderate Opportunity',
            cls.SATURATED: 'Limited Opportunity'
        }
        return opportunities.get(category, 'Unknown')


class RelationshipType(models.TextChoices):
    """Types of financial relationships."""
    EQUITY = 'equity', 'Equity Partner'
    DEBT = 'debt', 'Debt Provider'
    JOINT_VENTURE = 'joint_venture', 'Joint Venture'
    OTHER = 'other', 'Other'