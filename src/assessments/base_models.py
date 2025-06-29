"""
Base models and mixins for the CASA Due Diligence model.

Provides common functionality like versioning, audit trails, and computed properties.
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, Any
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from accounts.models import User, Group


class TimestampedModel(models.Model):
    """Provides created_at and updated_at timestamps."""
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """Provides UUID primary key."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    class Meta:
        abstract = True


class GroupFilteredModel(models.Model):
    """
    Provides group-based filtering for multi-tenancy.
    
    All models that inherit from this class will automatically:
    - Filter records by group for row-level security
    - Support bulk operations within group boundaries
    - Provide caching and performance optimizations
    - Include audit logging for all operations
    """
    
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        help_text="Group this record belongs to for multi-tenant access control",
        db_index=True  # Index for performance
    )
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['group']),  # Composite index for multi-tenant queries
        ]
    
    def __init_subclass__(cls, **kwargs):
        """
        Set up the custom manager when a model inherits from GroupFilteredModel.
        """
        super().__init_subclass__(**kwargs)
        
        # Only set up manager for concrete models (not abstract ones)
        if not cls._meta.abstract:
            from platform_core.core.managers import GroupFilteredManager
            cls.add_to_class('objects', GroupFilteredManager())
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure group is set and validate permissions.
        """
        # Validate that group is set
        if not self.group_id:
            raise ValidationError("Group must be set for all GroupFilteredModel instances")
        
        # Call parent save
        super().save(*args, **kwargs)
        
        # Invalidate related caches if using cached manager
        if hasattr(self.__class__.objects, '_invalidate_related_caches'):
            self.__class__.objects._invalidate_related_caches(self)
    
    def delete(self, *args, **kwargs):
        """
        Override delete to handle cache invalidation.
        """
        # Store values before deletion for cache invalidation
        group_id = self.group_id
        instance_id = self.id
        
        # Call parent delete
        result = super().delete(*args, **kwargs)
        
        # Invalidate related caches if using cached manager
        if hasattr(self.__class__.objects, '_invalidate_related_caches'):
            # Create a temporary object for cache invalidation
            temp_instance = self.__class__(id=instance_id, group_id=group_id)
            self.__class__.objects._invalidate_related_caches(temp_instance)
        
        return result
    
    @classmethod
    def get_for_user(cls, user, **filters):
        """
        Convenience method to get records accessible to a user.
        
        Args:
            user: User instance
            **filters: Additional filter parameters
            
        Returns:
            QuerySet filtered by user's accessible groups
        """
        return cls.objects.for_user(user).filter(**filters)
    
    @classmethod
    def create_for_user(cls, user, **kwargs):
        """
        Convenience method to create a record for a user.
        
        Args:
            user: User instance
            **kwargs: Model field values
            
        Returns:
            Created model instance
        """
        return cls.objects.create_for_user(user, **kwargs)


class VersionedModel(models.Model):
    """Provides semantic versioning functionality."""
    
    version_major = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    version_minor = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    version_patch = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='%(app_label)s_%(class)s_created',
        help_text="User who created this record"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='%(app_label)s_%(class)s_modified',
        null=True,
        blank=True,
        help_text="User who last modified this record"
    )
    last_modified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        abstract = True
    
    @property
    def semver(self) -> str:
        """Formatted semantic version string (MAJOR.MINOR.PATCH)."""
        return f"{self.version_major}.{self.version_minor}.{self.version_patch}"
    
    def increment_major(self, user: User) -> None:
        """Increment major version for significant changes."""
        self.version_major += 1
        self.version_minor = 0
        self.version_patch = 0
        self.last_modified_by = user
        self.last_modified_at = timezone.now()
        self.save()
    
    def increment_minor(self, user: User) -> None:
        """Increment minor version for non-breaking additions."""
        self.version_minor += 1
        self.version_patch = 0
        self.last_modified_by = user
        self.last_modified_at = timezone.now()
        self.save()
    
    def increment_patch(self, user: User) -> None:
        """Increment patch version for minor fixes."""
        self.version_patch += 1
        self.last_modified_by = user
        self.last_modified_at = timezone.now()
        self.save()


class BaseAssessmentModel(UUIDModel, GroupFilteredModel, VersionedModel):
    """
    Base class for all assessment-related models.
    
    Combines UUID, group filtering, and versioning functionality.
    """
    
    class Meta:
        abstract = True


# Utility mixins for specific functionality

class FinancialMixin:
    """Mixin providing common financial calculations."""
    
    def calculate_percentage(self, numerator: Optional[Decimal], denominator: Optional[Decimal]) -> Optional[float]:
        """Calculate percentage with null handling."""
        if numerator is None or denominator is None or denominator == 0:
            return None
        return round(float(numerator / denominator * 100), 2)
    
    def format_currency(self, amount: Optional[Decimal], currency: str) -> str:
        """Format currency amount with symbol."""
        if amount is None:
            return "N/A"
        
        currency_symbols = {
            'GBP': '£',
            'EUR': '€', 
            'USD': '$',
            'AED': 'AED ',
            'SAR': 'SAR '
        }
        symbol = currency_symbols.get(currency, f"{currency} ")
        return f"{symbol}{amount:,.2f}"


class RiskAssessmentMixin:
    """Mixin providing risk calculation utilities."""
    
    def categorize_risk_by_percentage(self, percentage: Optional[float]) -> Optional[str]:
        """Categorize risk based on percentage thresholds."""
        if percentage is None:
            return None
        
        if percentage <= 30:
            return 'LOW'
        elif percentage <= 60:
            return 'MODERATE'
        else:
            return 'HIGH'
    
    def calculate_overall_risk(self, risk_counts: Dict[str, int]) -> str:
        """Calculate overall risk profile from individual risk counts."""
        high_count = risk_counts.get('HIGH', 0)
        medium_count = risk_counts.get('MEDIUM', 0)
        
        if high_count >= 2:
            return 'HIGH'
        elif high_count == 1 or medium_count >= 3:
            return 'MEDIUM'
        else:
            return 'LOW'


class PerformanceMixin:
    """Mixin providing performance tracking utilities."""
    
    def calculate_variance_percentage(self, actual: Optional[Decimal], projected: Optional[Decimal]) -> Optional[float]:
        """Calculate variance between actual and projected values."""
        if actual is None or projected is None or projected == 0:
            return None
        
        variance = (actual - projected) / projected * 100
        return round(float(variance), 1)
    
    def categorize_performance(self, variance_pct: Optional[float]) -> str:
        """Categorize performance based on variance from projections."""
        if variance_pct is None:
            return "Unknown"
        
        if variance_pct >= 10:
            return "Significantly Above"
        elif variance_pct >= 5:
            return "Above"
        elif variance_pct >= -5:
            return "On Target"
        elif variance_pct >= -10:
            return "Below"
        else:
            return "Significantly Below"