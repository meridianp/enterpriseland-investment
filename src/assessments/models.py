
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import uuid
from datetime import datetime

class Currency(models.TextChoices):
    AED = 'AED', 'United Arab Emirates dirham'
    EUR = 'EUR', 'Euro'
    GBP = 'GBP', 'British pound sterling'
    SAR = 'SAR', 'Saudi riyal'
    USD = 'USD', 'United States dollar'


class AssessmentStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    IN_REVIEW = 'IN_REVIEW', 'In Review'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'
    NEEDS_INFO = 'NEEDS_INFO', 'Needs Additional Info'
    ARCHIVED = 'ARCHIVED', 'Archived'


class AssessmentDecision(models.TextChoices):
    PREMIUM_PRIORITY = 'Premium/Priority', 'Premium/Priority'
    ACCEPTABLE = 'Acceptable', 'Acceptable'
    REJECT = 'Reject', 'Reject'


class RiskLevel(models.TextChoices):
    LOW = 'LOW', 'Low'
    MEDIUM = 'MEDIUM', 'Medium'
    HIGH = 'HIGH', 'High'


class DebtRatioCategory(models.TextChoices):
    LOW = 'LOW', 'Low (0-30%)'
    MODERATE = 'MODERATE', 'Moderate (30-60%)'
    HIGH = 'HIGH', 'High (>60%)'


class AreaUnit(models.TextChoices):
    SQ_FT = 'SQ_FT', 'Square Feet'
    SQ_M = 'SQ_M', 'Square Meters'


class DevelopmentPartner(models.Model):
    """Development partner company information"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey('accounts.Group', on_delete=models.CASCADE, related_name='development_partners')
    
    # General Information
    company_name = models.CharField(max_length=255)
    trading_name = models.CharField(max_length=255, blank=True)
    headquarter_city = models.CharField(max_length=100, blank=True)
    headquarter_country = models.CharField(max_length=2, blank=True)  # ISO 3166-1 alpha-2
    year_established = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1800), MaxValueValidator(datetime.now().year)]
    )
    website_url = models.URLField(blank=True)
    
    # Operational Information
    size_of_development_team = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    number_of_employees = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    completed_pbsa_schemes = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    schemes_in_development = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    pbsa_schemes_in_development = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    completed_schemes_in_target_location = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    years_of_pbsa_experience = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    total_pbsa_beds_delivered = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    beds_in_development = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    
    # Stakeholder Information
    shareholding_structure = models.TextField(blank=True)
    ultimate_parent_company = models.CharField(max_length=255, blank=True)
    publicly_listed = models.BooleanField(null=True, blank=True)
    stock_exchange = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'development_partners'
        
    def __str__(self):
        return self.company_name
    
    @property
    def pbsa_specialization_pct(self):
        """Percentage of current pipeline that is PBSA"""
        if not self.schemes_in_development or not self.pbsa_schemes_in_development:
            return None
        return round((self.pbsa_schemes_in_development / self.schemes_in_development) * 100, 1)
    
    @property
    def avg_pbsa_scheme_size(self):
        """Average number of beds per completed PBSA scheme"""
        if not self.completed_pbsa_schemes or not self.total_pbsa_beds_delivered:
            return None
        return round(self.total_pbsa_beds_delivered / self.completed_pbsa_schemes)


class OfficeLocation(models.Model):
    """Office locations for development partners"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    partner = models.ForeignKey(DevelopmentPartner, on_delete=models.CASCADE, related_name='office_locations')
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=2)  # ISO 3166-1 alpha-2
    
    class Meta:
        db_table = 'office_locations'
        
    def __str__(self):
        return f"{self.city}, {self.country}"


class FinancialPartner(models.Model):
    """Financial partners and relationships"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    partner = models.ForeignKey(DevelopmentPartner, on_delete=models.CASCADE, related_name='financial_partners')
    name = models.CharField(max_length=255)
    relationship_type = models.CharField(max_length=50, choices=[
        ('equity', 'Equity Partner'),
        ('debt', 'Debt Provider'),
        ('joint_venture', 'Joint Venture'),
        ('other', 'Other')
    ])
    
    class Meta:
        db_table = 'financial_partners'
        
    def __str__(self):
        return f"{self.name} ({self.get_relationship_type_display()})"


class KeyShareholder(models.Model):
    """Key shareholders and ownership percentages"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    partner = models.ForeignKey(DevelopmentPartner, on_delete=models.CASCADE, related_name='key_shareholders')
    name = models.CharField(max_length=255)
    ownership_percentage = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    class Meta:
        db_table = 'key_shareholders'
        
    def __str__(self):
        return f"{self.name} ({self.ownership_percentage}%)"


class PBSAScheme(models.Model):
    """PBSA scheme information"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey('accounts.Group', on_delete=models.CASCADE, related_name='pbsa_schemes')
    
    scheme_name = models.CharField(max_length=255)
    location_city = models.CharField(max_length=100)
    location_country = models.CharField(max_length=2)  # ISO 3166-1 alpha-2
    total_beds = models.IntegerField(validators=[MinValueValidator(1)])
    site_area_value = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    site_area_unit = models.CharField(max_length=10, choices=AreaUnit.choices)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'pbsa_schemes'
        
    def __str__(self):
        return self.scheme_name


class Assessment(models.Model):
    """Main assessment record"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey('accounts.Group', on_delete=models.CASCADE, related_name='assessments')
    
    # Assessment type and relationships
    assessment_type = models.CharField(max_length=20, choices=[
        ('PARTNER', 'Development Partner'),
        ('SCHEME', 'PBSA Scheme'),
        ('COMBINED', 'Combined Assessment')
    ])
    partner = models.ForeignKey(DevelopmentPartner, on_delete=models.CASCADE, null=True, blank=True, related_name='assessments')
    scheme = models.ForeignKey(PBSAScheme, on_delete=models.CASCADE, null=True, blank=True, related_name='assessments')
    
    # Assessment metadata
    status = models.CharField(max_length=20, choices=AssessmentStatus.choices, default=AssessmentStatus.DRAFT)
    decision = models.CharField(max_length=20, choices=AssessmentDecision.choices, blank=True)
    total_score = models.IntegerField(null=True, blank=True)
    
    # Version control
    version_major = models.IntegerField(default=1)
    version_minor = models.IntegerField(default=0)
    version_patch = models.IntegerField(default=0)
    
    # Audit trail
    created_by = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='created_assessments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='updated_assessments', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_by = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='approved_assessments', null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'assessments'
        
    def __str__(self):
        if self.partner:
            return f"Assessment of {self.partner.company_name}"
        elif self.scheme:
            return f"Assessment of {self.scheme.scheme_name}"
        return f"Assessment {self.id}"
    
    @property
    def semver(self):
        """Semantic version string"""
        return f"{self.version_major}.{self.version_minor}.{self.version_patch}"
    
    def increment_major(self, user):
        """Increment major version for significant changes"""
        self.version_major += 1
        self.version_minor = 0
        self.version_patch = 0
        self.updated_by = user
        self.save()
    
    def increment_minor(self, user):
        """Increment minor version for non-breaking additions"""
        self.version_minor += 1
        self.version_patch = 0
        self.updated_by = user
        self.save()
    
    def increment_patch(self, user):
        """Increment patch version for minor fixes"""
        self.version_patch += 1
        self.updated_by = user
        self.save()


class FinancialInformation(models.Model):
    """Financial information for assessments"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.OneToOneField(Assessment, on_delete=models.CASCADE, related_name='financial_info')
    
    # Balance sheet information
    net_assets_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    net_assets_currency = models.CharField(max_length=3, choices=Currency.choices, null=True, blank=True)
    net_current_assets_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    net_current_assets_currency = models.CharField(max_length=3, choices=Currency.choices, null=True, blank=True)
    
    # Profit and loss information
    net_profit_before_tax_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    net_profit_before_tax_currency = models.CharField(max_length=3, choices=Currency.choices, null=True, blank=True)
    latest_annual_revenue_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    latest_annual_revenue_currency = models.CharField(max_length=3, choices=Currency.choices, null=True, blank=True)
    ebitda_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    ebitda_currency = models.CharField(max_length=3, choices=Currency.choices, null=True, blank=True)
    
    financial_year_end_date = models.DateField(null=True, blank=True)
    
    class Meta:
        db_table = 'financial_information'
        
    @property
    def profit_margin_pct(self):
        """Profitability measure: (profit before tax / revenue) × 100"""
        if not self.net_profit_before_tax_amount or not self.latest_annual_revenue_amount:
            return None
        if self.latest_annual_revenue_amount == 0:
            return None
        return round(float(self.net_profit_before_tax_amount / self.latest_annual_revenue_amount * 100), 1)


class CreditInformation(models.Model):
    """Credit and debt information for assessments"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.OneToOneField(Assessment, on_delete=models.CASCADE, related_name='credit_info')
    
    main_banking_relationship = models.CharField(max_length=255, blank=True)
    amount_of_debt_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    amount_of_debt_currency = models.CharField(max_length=3, choices=Currency.choices, null=True, blank=True)
    debt_to_total_assets_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    short_term_debt_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    interest_coverage_ratio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    debt_service_coverage_ratio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    credit_rating = models.CharField(max_length=10, blank=True)
    
    class Meta:
        db_table = 'credit_information'
        
    @property
    def leverage_band(self):
        """Categorizes debt level into LOW/MODERATE/HIGH risk bands"""
        if self.debt_to_total_assets_pct is None:
            return None
        
        pct = float(self.debt_to_total_assets_pct)
        if pct <= 30:
            return DebtRatioCategory.LOW
        elif pct <= 60:
            return DebtRatioCategory.MODERATE
        else:
            return DebtRatioCategory.HIGH
    
    @property
    def liquidity_risk(self):
        """Assesses short-term liquidity risk based on debt profile"""
        if self.short_term_debt_pct is None:
            return None
        
        pct = float(self.short_term_debt_pct)
        if pct > 50:
            base_risk = RiskLevel.HIGH
        elif pct > 25:
            base_risk = RiskLevel.MEDIUM
        else:
            base_risk = RiskLevel.LOW
        
        # Adjust based on coverage ratios if available
        if self.interest_coverage_ratio is not None:
            ratio = float(self.interest_coverage_ratio)
            if ratio < 1.5:
                if base_risk == RiskLevel.LOW:
                    base_risk = RiskLevel.MEDIUM
                elif base_risk == RiskLevel.MEDIUM:
                    base_risk = RiskLevel.HIGH
            elif ratio > 3.0:
                if base_risk == RiskLevel.HIGH:
                    base_risk = RiskLevel.MEDIUM
                elif base_risk == RiskLevel.MEDIUM:
                    base_risk = RiskLevel.LOW
        
        return base_risk


class AssessmentMetric(models.Model):
    """Individual assessment metrics with scores and weights"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='metrics')
    
    metric_name = models.CharField(max_length=100)
    score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    weight = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    justification = models.TextField(blank=True)
    
    class Meta:
        db_table = 'assessment_metrics'
        unique_together = ['assessment', 'metric_name']
        
    @property
    def weighted_score(self):
        """Calculate weighted score (score × weight)"""
        return self.score * self.weight
    
    def __str__(self):
        return f"{self.metric_name}: {self.score}×{self.weight}={self.weighted_score}"


class FXRate(models.Model):
    """Foreign exchange rates for currency conversion"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    base_currency = models.CharField(max_length=3, choices=Currency.choices)
    target_currency = models.CharField(max_length=3, choices=Currency.choices)
    rate = models.DecimalField(max_digits=10, decimal_places=6)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'fx_rates'
        unique_together = ['base_currency', 'target_currency', 'date']
        
    def __str__(self):
        return f"{self.base_currency}/{self.target_currency}: {self.rate} ({self.date})"


class AssessmentAuditLog_Legacy(models.Model):
    """Legacy audit trail for assessment-specific data changes - TO BE MIGRATED"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='assessment_audit_entries')
    table_name = models.CharField(max_length=100)
    record_id = models.UUIDField()
    action = models.CharField(max_length=10, choices=[
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete')
    ])
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        db_table = 'assessment_audit_log_legacy'
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['table_name', 'record_id']),
            models.Index(fields=['user']),
        ]
        
    def __str__(self):
        return f"{self.action} {self.table_name} by {self.user.email} at {self.timestamp}"
