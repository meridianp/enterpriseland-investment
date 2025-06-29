"""
Enhanced financial information models for the CASA Due Diligence Platform.

These models implement comprehensive financial assessment capabilities
that integrate with the partner information structure.
"""

from decimal import Decimal
from typing import Optional, Dict, List, Tuple
from datetime import datetime, date

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

from .base_models import BaseAssessmentModel, FinancialMixin, RiskAssessmentMixin
from .enums import Currency, DebtRatioCategory, RiskLevel
from .validation import validate_positive_decimal, validate_year_range


class FinancialInformation(BaseAssessmentModel, FinancialMixin):
    """
    Enhanced financial information model with comprehensive metrics.
    
    Tracks balance sheet, P&L, and calculated financial ratios for assessment.
    """
    
    partner = models.OneToOneField(
        'DevelopmentPartner',
        on_delete=models.CASCADE,
        related_name='financial_info',
        help_text="Development partner this financial information belongs to"
    )
    
    # Financial year information
    financial_year_end_date = models.DateField(
        null=True,
        blank=True,
        help_text="End date of the financial year"
    )
    
    accounting_standards = models.CharField(
        max_length=20,
        choices=[
            ('IFRS', 'International Financial Reporting Standards'),
            ('GAAP_US', 'US Generally Accepted Accounting Principles'),
            ('GAAP_UK', 'UK Generally Accepted Accounting Principles'),
            ('LOCAL', 'Local Accounting Standards'),
        ],
        blank=True,
        help_text="Accounting standards used for financial statements"
    )
    
    auditor_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name of external auditor"
    )
    
    is_audited = models.BooleanField(
        null=True,
        blank=True,
        help_text="Whether financial statements are externally audited"
    )
    
    # Balance Sheet Information
    total_assets_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Total assets value"
    )
    
    total_assets_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of total assets"
    )
    
    net_assets_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Net assets (shareholders' equity)"
    )
    
    net_assets_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of net assets"
    )
    
    current_assets_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Current assets value"
    )
    
    current_assets_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of current assets"
    )
    
    current_liabilities_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Current liabilities value"
    )
    
    current_liabilities_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of current liabilities"
    )
    
    # P&L Information
    latest_annual_revenue_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Latest annual revenue"
    )
    
    latest_annual_revenue_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of latest annual revenue"
    )
    
    gross_profit_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Gross profit (can be negative)"
    )
    
    gross_profit_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of gross profit"
    )
    
    ebitda_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Earnings Before Interest, Tax, Depreciation, and Amortization"
    )
    
    ebitda_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of EBITDA"
    )
    
    net_profit_before_tax_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Net profit before tax (can be negative)"
    )
    
    net_profit_before_tax_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of net profit before tax"
    )
    
    # Cash flow information
    operating_cash_flow_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Operating cash flow (can be negative)"
    )
    
    operating_cash_flow_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of operating cash flow"
    )
    
    free_cash_flow_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Free cash flow (can be negative)"
    )
    
    free_cash_flow_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of free cash flow"
    )
    
    class Meta:
        db_table = 'financial_information_enhanced'
        verbose_name = 'Financial Information'
    
    def __str__(self) -> str:
        return f"Financial Info for {self.partner.company_name}"
    
    @property
    def profit_margin_pct(self) -> Optional[float]:
        """
        Net profit margin percentage.
        
        Formula: (Net Profit Before Tax / Revenue) × 100
        """
        if (self.net_profit_before_tax_amount is None or 
            self.latest_annual_revenue_amount is None or
            self.latest_annual_revenue_amount == 0):
            return None
        
        margin = (self.net_profit_before_tax_amount / self.latest_annual_revenue_amount) * 100
        return round(float(margin), 2)
    
    @property
    def gross_margin_pct(self) -> Optional[float]:
        """
        Gross profit margin percentage.
        
        Formula: (Gross Profit / Revenue) × 100
        """
        if (self.gross_profit_amount is None or 
            self.latest_annual_revenue_amount is None or
            self.latest_annual_revenue_amount == 0):
            return None
        
        margin = (self.gross_profit_amount / self.latest_annual_revenue_amount) * 100
        return round(float(margin), 2)
    
    @property
    def ebitda_margin_pct(self) -> Optional[float]:
        """
        EBITDA margin percentage.
        
        Formula: (EBITDA / Revenue) × 100
        """
        if (self.ebitda_amount is None or 
            self.latest_annual_revenue_amount is None or
            self.latest_annual_revenue_amount == 0):
            return None
        
        margin = (self.ebitda_amount / self.latest_annual_revenue_amount) * 100
        return round(float(margin), 2)
    
    @property
    def current_ratio(self) -> Optional[float]:
        """
        Current ratio for liquidity assessment.
        
        Formula: Current Assets / Current Liabilities
        Higher values indicate better short-term liquidity.
        """
        if (self.current_assets_amount is None or 
            self.current_liabilities_amount is None or
            self.current_liabilities_amount == 0):
            return None
        
        ratio = self.current_assets_amount / self.current_liabilities_amount
        return round(float(ratio), 2)
    
    @property
    def working_capital_amount(self) -> Optional[Decimal]:
        """
        Working capital amount.
        
        Formula: Current Assets - Current Liabilities
        """
        if (self.current_assets_amount is None or 
            self.current_liabilities_amount is None):
            return None
        
        return self.current_assets_amount - self.current_liabilities_amount
    
    @property
    def return_on_assets_pct(self) -> Optional[float]:
        """
        Return on Assets percentage.
        
        Formula: (Net Profit Before Tax / Total Assets) × 100
        """
        if (self.net_profit_before_tax_amount is None or 
            self.total_assets_amount is None or
            self.total_assets_amount == 0):
            return None
        
        roa = (self.net_profit_before_tax_amount / self.total_assets_amount) * 100
        return round(float(roa), 2)
    
    @property
    def return_on_equity_pct(self) -> Optional[float]:
        """
        Return on Equity percentage.
        
        Formula: (Net Profit Before Tax / Net Assets) × 100
        """
        if (self.net_profit_before_tax_amount is None or 
            self.net_assets_amount is None or
            self.net_assets_amount == 0):
            return None
        
        roe = (self.net_profit_before_tax_amount / self.net_assets_amount) * 100
        return round(float(roe), 2)
    
    @property
    def financial_health_score(self) -> Dict[str, any]:
        """
        Comprehensive financial health assessment.
        
        Returns a score from 1 (poor) to 5 (excellent) with supporting metrics.
        """
        score = 3  # Start with neutral
        factors = []
        
        # Profitability assessment
        if self.profit_margin_pct is not None:
            if self.profit_margin_pct > 15:
                score += 1
                factors.append("Strong profit margins")
            elif self.profit_margin_pct < 0:
                score -= 1
                factors.append("Negative profitability")
        
        # Liquidity assessment
        if self.current_ratio is not None:
            if self.current_ratio > 2.0:
                score += 0.5
                factors.append("Strong liquidity position")
            elif self.current_ratio < 1.0:
                score -= 1
                factors.append("Poor liquidity position")
        
        # Growth indicators
        if self.ebitda_margin_pct is not None:
            if self.ebitda_margin_pct > 20:
                score += 0.5
                factors.append("Strong operational efficiency")
            elif self.ebitda_margin_pct < 5:
                score -= 0.5
                factors.append("Low operational efficiency")
        
        # Bound the score
        final_score = max(1, min(5, round(score)))
        
        return {
            'score': final_score,
            'factors': factors,
            'profit_margin': self.profit_margin_pct,
            'current_ratio': self.current_ratio,
            'ebitda_margin': self.ebitda_margin_pct
        }
    
    def clean(self):
        """Validate financial information."""
        super().clean()
        
        # Validate currency consistency
        currencies = set()
        currency_fields = [
            self.total_assets_currency,
            self.net_assets_currency,
            self.current_assets_currency,
            self.current_liabilities_currency,
            self.latest_annual_revenue_currency,
            self.gross_profit_currency,
            self.ebitda_currency,
            self.net_profit_before_tax_currency,
            self.operating_cash_flow_currency,
            self.free_cash_flow_currency
        ]
        
        for currency in currency_fields:
            if currency:
                currencies.add(currency)
        
        if len(currencies) > 1:
            raise ValidationError(
                f"Multiple currencies detected: {', '.join(currencies)}. "
                f"All financial figures should be in the same currency."
            )


class CreditInformation(BaseAssessmentModel, RiskAssessmentMixin):
    """
    Enhanced credit information model with comprehensive debt analysis.
    
    Tracks debt profile, banking relationships, and credit risk metrics.
    """
    
    partner = models.OneToOneField(
        'DevelopmentPartner',
        on_delete=models.CASCADE,
        related_name='credit_info',
        help_text="Development partner this credit information belongs to"
    )
    
    # Banking relationships
    main_banking_relationship = models.CharField(
        max_length=255,
        blank=True,
        help_text="Primary banking partner"
    )
    
    number_of_banking_relationships = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total number of banking relationships"
    )
    
    banking_relationship_duration_years = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duration of primary banking relationship in years"
    )
    
    # Debt structure
    total_debt_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Total outstanding debt"
    )
    
    total_debt_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of total debt"
    )
    
    short_term_debt_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Short-term debt (due within 1 year)"
    )
    
    short_term_debt_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of short-term debt"
    )
    
    long_term_debt_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Long-term debt (due after 1 year)"
    )
    
    long_term_debt_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of long-term debt"
    )
    
    # Credit metrics
    interest_coverage_ratio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="EBITDA / Interest Expense - ability to service debt"
    )
    
    debt_service_coverage_ratio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Operating Cash Flow / Total Debt Service"
    )
    
    debt_to_equity_ratio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total Debt / Shareholders' Equity"
    )
    
    # Credit rating and external assessment
    credit_rating = models.CharField(
        max_length=10,
        blank=True,
        help_text="External credit rating (e.g., AAA, BB+)"
    )
    
    credit_rating_agency = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('SP', "Standard & Poor's"),
            ('MOODY', "Moody's"),
            ('FITCH', "Fitch Ratings"),
            ('LOCAL', "Local Rating Agency"),
            ('INTERNAL', "Internal Assessment"),
        ],
        help_text="Credit rating agency"
    )
    
    credit_rating_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of credit rating"
    )
    
    # Default and covenant information
    any_defaults_last_5_years = models.BooleanField(
        null=True,
        blank=True,
        help_text="Any loan defaults in the last 5 years"
    )
    
    covenant_breaches_last_2_years = models.BooleanField(
        null=True,
        blank=True,
        help_text="Any covenant breaches in the last 2 years"
    )
    
    bankruptcy_history = models.BooleanField(
        null=True,
        blank=True,
        help_text="Any bankruptcy history"
    )
    
    # Facilities and credit lines
    total_credit_facilities_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Total available credit facilities"
    )
    
    total_credit_facilities_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of credit facilities"
    )
    
    utilized_credit_facilities_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_positive_decimal],
        help_text="Currently utilized credit facilities"
    )
    
    utilized_credit_facilities_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of utilized credit facilities"
    )
    
    class Meta:
        db_table = 'credit_information_enhanced'
        verbose_name = 'Credit Information'
    
    def __str__(self) -> str:
        return f"Credit Info for {self.partner.company_name}"
    
    @property
    def debt_to_total_assets_pct(self) -> Optional[float]:
        """
        Debt-to-total assets ratio as percentage.
        
        Formula: (Total Debt / Total Assets) × 100
        """
        if (self.total_debt_amount is None or 
            not hasattr(self.partner, 'financial_info') or
            self.partner.financial_info.total_assets_amount is None or
            self.partner.financial_info.total_assets_amount == 0):
            return None
        
        ratio = (self.total_debt_amount / self.partner.financial_info.total_assets_amount) * 100
        return round(float(ratio), 2)
    
    @property
    def short_term_debt_pct(self) -> Optional[float]:
        """
        Short-term debt as percentage of total debt.
        
        Formula: (Short-term Debt / Total Debt) × 100
        """
        if (self.short_term_debt_amount is None or 
            self.total_debt_amount is None or
            self.total_debt_amount == 0):
            return None
        
        pct = (self.short_term_debt_amount / self.total_debt_amount) * 100
        return round(float(pct), 2)
    
    @property
    def credit_utilization_pct(self) -> Optional[float]:
        """
        Credit facility utilization percentage.
        
        Formula: (Utilized Facilities / Total Facilities) × 100
        """
        if (self.utilized_credit_facilities_amount is None or 
            self.total_credit_facilities_amount is None or
            self.total_credit_facilities_amount == 0):
            return None
        
        utilization = (self.utilized_credit_facilities_amount / self.total_credit_facilities_amount) * 100
        return round(float(utilization), 2)
    
    @property
    def available_credit_amount(self) -> Optional[Decimal]:
        """
        Available unused credit facilities.
        
        Formula: Total Facilities - Utilized Facilities
        """
        if (self.total_credit_facilities_amount is None or 
            self.utilized_credit_facilities_amount is None):
            return None
        
        return self.total_credit_facilities_amount - self.utilized_credit_facilities_amount
    
    @property
    def leverage_band(self) -> Optional[str]:
        """
        Categorizes debt level into risk bands.
        
        Returns:
            LOW: 0-30% debt-to-assets
            MODERATE: 30-60% debt-to-assets  
            HIGH: >60% debt-to-assets
        """
        debt_ratio = self.debt_to_total_assets_pct
        if debt_ratio is None:
            return None
        
        if debt_ratio <= 30:
            return DebtRatioCategory.LOW
        elif debt_ratio <= 60:
            return DebtRatioCategory.MODERATE
        else:
            return DebtRatioCategory.HIGH
    
    @property
    def liquidity_risk(self) -> Optional[str]:
        """
        Comprehensive liquidity risk assessment.
        
        Considers short-term debt ratio, coverage ratios, and credit utilization.
        """
        if self.short_term_debt_pct is None:
            return None
        
        # Base assessment from short-term debt percentage
        if self.short_term_debt_pct > 60:
            base_risk = RiskLevel.HIGH
        elif self.short_term_debt_pct > 30:
            base_risk = RiskLevel.MEDIUM
        else:
            base_risk = RiskLevel.LOW
        
        # Adjust based on interest coverage ratio
        if self.interest_coverage_ratio is not None:
            if self.interest_coverage_ratio < 1.5:
                # Poor coverage increases risk
                if base_risk == RiskLevel.LOW:
                    base_risk = RiskLevel.MEDIUM
                elif base_risk == RiskLevel.MEDIUM:
                    base_risk = RiskLevel.HIGH
            elif self.interest_coverage_ratio > 3.0:
                # Strong coverage reduces risk
                if base_risk == RiskLevel.HIGH:
                    base_risk = RiskLevel.MEDIUM
                elif base_risk == RiskLevel.MEDIUM:
                    base_risk = RiskLevel.LOW
        
        # Adjust based on credit utilization
        if self.credit_utilization_pct is not None:
            if self.credit_utilization_pct > 80:
                # High utilization increases risk
                if base_risk == RiskLevel.LOW:
                    base_risk = RiskLevel.MEDIUM
            elif self.credit_utilization_pct < 50:
                # Low utilization reduces risk
                if base_risk == RiskLevel.HIGH:
                    base_risk = RiskLevel.MEDIUM
        
        return base_risk
    
    @property
    def credit_risk_score(self) -> Dict[str, any]:
        """
        Comprehensive credit risk assessment.
        
        Returns a score from 1 (high risk) to 5 (low risk) with supporting factors.
        """
        score = 3  # Start with neutral
        factors = []
        
        # Leverage assessment
        leverage = self.leverage_band
        if leverage == DebtRatioCategory.LOW:
            score += 1
            factors.append("Low leverage")
        elif leverage == DebtRatioCategory.HIGH:
            score -= 1
            factors.append("High leverage")
        
        # Liquidity assessment
        liquidity = self.liquidity_risk
        if liquidity == RiskLevel.LOW:
            score += 1
            factors.append("Strong liquidity")
        elif liquidity == RiskLevel.HIGH:
            score -= 1
            factors.append("Poor liquidity")
        
        # Coverage ratios
        if self.interest_coverage_ratio is not None:
            if self.interest_coverage_ratio > 3.0:
                score += 0.5
                factors.append("Strong interest coverage")
            elif self.interest_coverage_ratio < 1.5:
                score -= 1
                factors.append("Weak interest coverage")
        
        # Default/breach history
        if self.any_defaults_last_5_years:
            score -= 1
            factors.append("Recent default history")
        
        if self.covenant_breaches_last_2_years:
            score -= 0.5
            factors.append("Recent covenant breaches")
        
        if self.bankruptcy_history:
            score -= 1.5
            factors.append("Bankruptcy history")
        
        # Banking relationship stability
        if self.banking_relationship_duration_years is not None:
            if self.banking_relationship_duration_years > 5:
                score += 0.5
                factors.append("Stable banking relationships")
        
        # Bound the score
        final_score = max(1, min(5, round(score)))
        
        return {
            'score': final_score,
            'factors': factors,
            'leverage_band': leverage,
            'liquidity_risk': liquidity,
            'interest_coverage': self.interest_coverage_ratio
        }
    
    def clean(self):
        """Validate credit information."""
        super().clean()
        
        # Validate debt components sum to total
        if (self.total_debt_amount is not None and 
            self.short_term_debt_amount is not None and 
            self.long_term_debt_amount is not None):
            
            calculated_total = self.short_term_debt_amount + self.long_term_debt_amount
            tolerance = Decimal('0.01')  # Allow small rounding differences
            
            if abs(calculated_total - self.total_debt_amount) > tolerance:
                raise ValidationError(
                    f"Short-term debt ({self.short_term_debt_amount}) + "
                    f"Long-term debt ({self.long_term_debt_amount}) = "
                    f"{calculated_total} does not equal total debt ({self.total_debt_amount})"
                )
        
        # Validate credit utilization doesn't exceed facilities
        if (self.utilized_credit_facilities_amount is not None and 
            self.total_credit_facilities_amount is not None):
            
            if self.utilized_credit_facilities_amount > self.total_credit_facilities_amount:
                raise ValidationError(
                    f"Utilized credit facilities ({self.utilized_credit_facilities_amount}) "
                    f"cannot exceed total facilities ({self.total_credit_facilities_amount})"
                )


class FinancialRatio(BaseAssessmentModel):
    """
    Calculated financial ratios for benchmarking and trend analysis.
    
    Stores computed ratios with timestamps for historical tracking.
    """
    
    partner = models.ForeignKey(
        'DevelopmentPartner',
        on_delete=models.CASCADE,
        related_name='financial_ratios',
        help_text="Development partner these ratios belong to"
    )
    
    calculation_date = models.DateField(
        default=date.today,
        help_text="Date when ratios were calculated"
    )
    
    # Profitability ratios
    gross_margin_pct = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Gross profit margin percentage"
    )
    
    net_margin_pct = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Net profit margin percentage"
    )
    
    ebitda_margin_pct = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="EBITDA margin percentage"
    )
    
    return_on_assets_pct = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Return on assets percentage"
    )
    
    return_on_equity_pct = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Return on equity percentage"
    )
    
    # Liquidity ratios
    current_ratio = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Current assets / Current liabilities"
    )
    
    quick_ratio = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="(Current assets - Inventory) / Current liabilities"
    )
    
    # Leverage ratios
    debt_to_assets_pct = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Total debt / Total assets percentage"
    )
    
    debt_to_equity_ratio = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Total debt / Shareholders' equity"
    )
    
    interest_coverage_ratio = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="EBITDA / Interest expense"
    )
    
    # Efficiency ratios
    asset_turnover_ratio = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Revenue / Total assets"
    )
    
    working_capital_ratio = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Working capital / Revenue"
    )
    
    class Meta:
        db_table = 'financial_ratios'
        unique_together = ['partner', 'calculation_date']
        verbose_name = 'Financial Ratio'
        verbose_name_plural = 'Financial Ratios'
        ordering = ['-calculation_date']
    
    def __str__(self) -> str:
        return f"Ratios for {self.partner.company_name} ({self.calculation_date})"
    
    @classmethod
    def calculate_for_partner(cls, partner: 'DevelopmentPartner') -> 'FinancialRatio':
        """
        Calculate all financial ratios for a partner based on their financial info.
        
        Args:
            partner: DevelopmentPartner instance
            
        Returns:
            FinancialRatio instance with calculated values
        """
        ratio_obj, created = cls.objects.get_or_create(
            partner=partner,
            calculation_date=date.today(),
            defaults={'group': partner.group}
        )
        
        # Get financial and credit info
        if hasattr(partner, 'financial_info'):
            financial = partner.financial_info
            
            # Profitability ratios
            ratio_obj.gross_margin_pct = financial.gross_margin_pct
            ratio_obj.net_margin_pct = financial.profit_margin_pct
            ratio_obj.ebitda_margin_pct = financial.ebitda_margin_pct
            ratio_obj.return_on_assets_pct = financial.return_on_assets_pct
            ratio_obj.return_on_equity_pct = financial.return_on_equity_pct
            
            # Liquidity ratios
            ratio_obj.current_ratio = financial.current_ratio
            
            # Efficiency ratios
            if (financial.latest_annual_revenue_amount and 
                financial.total_assets_amount and 
                financial.total_assets_amount > 0):
                ratio_obj.asset_turnover_ratio = round(
                    float(financial.latest_annual_revenue_amount / financial.total_assets_amount), 3
                )
            
            if (financial.working_capital_amount and 
                financial.latest_annual_revenue_amount and 
                financial.latest_annual_revenue_amount > 0):
                ratio_obj.working_capital_ratio = round(
                    float(financial.working_capital_amount / financial.latest_annual_revenue_amount), 3
                )
        
        # Get credit info for leverage ratios
        if hasattr(partner, 'credit_info'):
            credit = partner.credit_info
            
            ratio_obj.debt_to_assets_pct = credit.debt_to_total_assets_pct
            ratio_obj.debt_to_equity_ratio = credit.debt_to_equity_ratio
            ratio_obj.interest_coverage_ratio = credit.interest_coverage_ratio
        
        ratio_obj.save()
        return ratio_obj