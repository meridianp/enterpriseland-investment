"""
Unit tests for the CASA Due Diligence Platform legacy models.

Tests the models available in the main models.py file.
"""

from decimal import Decimal
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Group
from assessments.models import (
    DevelopmentPartner, OfficeLocation, FinancialPartner, KeyShareholder,
    PBSAScheme, LegacyAssessment, FinancialInformation, CreditInformation,
    LegacyAssessmentMetric, FXRate, AssessmentAuditLog_Legacy,
    Currency, AssessmentStatus, AssessmentDecision, RiskLevel, 
    DebtRatioCategory, AreaUnit
)

User = get_user_model()


class DevelopmentPartnerModelTest(TestCase):
    """Test the DevelopmentPartner model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            role='ANALYST'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.user.groups.add(self.group)
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd',
            trading_name='Test Dev',
            headquarters_city='London',
            headquarters_country='GB',
            year_established=2010,
            number_of_employees=150,
            size_of_development_team=25
        )
    
    def test_partner_creation(self):
        """Test basic partner creation."""
        self.assertEqual(self.partner.company_name, 'Test Developer Ltd')
        self.assertEqual(self.partner.trading_name, 'Test Dev')
        self.assertEqual(self.partner.headquarters_city, 'London')
        self.assertEqual(self.partner.year_established, 2010)
        self.assertEqual(str(self.partner), 'Test Developer Ltd')
    
    def test_partner_offices(self):
        """Test partner office relationships."""
        office = OfficeLocation.objects.create(
            partner=self.partner,
            city='Berlin',
            country='DE'
        )
        
        self.assertEqual(self.partner.office_locations.count(), 1)
        self.assertEqual(self.partner.office_locations.first(), office)
    
    def test_partner_financial_partners(self):
        """Test financial partner relationships."""
        financial_partner = FinancialPartner.objects.create(
            partner=self.partner,
            name='Investment Fund XYZ',
            relationship_type='equity_partner',
            description='Strategic equity partner'
        )
        
        self.assertEqual(self.partner.financial_partners.count(), 1)
        self.assertEqual(self.partner.financial_partners.first(), financial_partner)


class OfficeLocationModelTest(TestCase):
    """Test the OfficeLocation model."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.office = OfficeLocation.objects.create(
            partner=self.partner,
            city='London',
            country='GB'
        )
    
    def test_office_creation(self):
        """Test office location creation."""
        self.assertEqual(self.office.city, 'London')
        self.assertEqual(self.office.country, 'GB')
        self.assertEqual(str(self.office), 'London, GB')
    
    def test_office_partner_relationship(self):
        """Test relationship with partner."""
        self.assertEqual(self.office.partner, self.partner)


class FinancialPartnerModelTest(TestCase):
    """Test the FinancialPartner model."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.financial_partner = FinancialPartner.objects.create(
            partner=self.partner,
            name='Blackstone Capital',
            relationship_type='equity_partner',
            description='Primary equity investor'
        )
    
    def test_financial_partner_creation(self):
        """Test financial partner creation."""
        self.assertEqual(self.financial_partner.name, 'Blackstone Capital')
        self.assertEqual(self.financial_partner.relationship_type, 'equity_partner')
        self.assertEqual(self.financial_partner.description, 'Primary equity investor')
        self.assertEqual(str(self.financial_partner), 'Blackstone Capital (equity_partner)')


class KeyShareholderModelTest(TestCase):
    """Test the KeyShareholder model."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.shareholder = KeyShareholder.objects.create(
            partner=self.partner,
            name='John Smith',
            ownership_percentage=Decimal('35.5')
        )
    
    def test_shareholder_creation(self):
        """Test shareholder creation."""
        self.assertEqual(self.shareholder.name, 'John Smith')
        self.assertEqual(self.shareholder.ownership_percentage, Decimal('35.5'))
        self.assertEqual(str(self.shareholder), 'John Smith (35.5%)')
    
    def test_ownership_percentage_validation(self):
        """Test ownership percentage validation."""
        # Test valid percentage
        shareholder = KeyShareholder(
            partner=self.partner,
            name='Valid Shareholder',
            ownership_percentage=Decimal('50')
        )
        shareholder.full_clean()  # Should not raise
        
        # Test > 100%
        with self.assertRaises(ValidationError):
            shareholder = KeyShareholder(
                partner=self.partner,
                name='Invalid Shareholder',
                ownership_percentage=Decimal('101')
            )
            shareholder.full_clean()
        
        # Test < 0%
        with self.assertRaises(ValidationError):
            shareholder = KeyShareholder(
                partner=self.partner,
                name='Invalid Shareholder',
                ownership_percentage=Decimal('-1')
            )
            shareholder.full_clean()


class PBSASchemeModelTest(TestCase):
    """Test the PBSAScheme model."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.developer = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.scheme = PBSAScheme.objects.create(
            group=self.group,
            scheme_name='University Heights',
            developer=self.developer,
            scheme_address='123 University Road',
            scheme_city='Oxford',
            scheme_country='GB',
            total_beds=600,
            total_development_cost_gbp=Decimal('30000000'),
            expected_completion_date=date(2025, 9, 1)
        )
    
    def test_scheme_creation(self):
        """Test scheme creation."""
        self.assertEqual(self.scheme.scheme_name, 'University Heights')
        self.assertEqual(self.scheme.total_beds, 600)
        self.assertEqual(self.scheme.scheme_city, 'Oxford')
        self.assertEqual(self.scheme.total_development_cost_gbp, Decimal('30000000'))
        self.assertEqual(str(self.scheme), 'University Heights')
    
    def test_cost_per_bed_calculation(self):
        """Test cost per bed calculation."""
        expected_cost_per_bed = Decimal('30000000') / 600
        self.assertAlmostEqual(
            self.scheme.cost_per_bed_gbp,
            expected_cost_per_bed,
            places=2
        )


class FinancialInformationModelTest(TestCase):
    """Test the FinancialInformation model."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.financial_info = FinancialInformation.objects.create(
            partner=self.partner,
            financial_year_end=date(2023, 12, 31),
            total_assets_gbp=Decimal('50000000'),
            net_assets_gbp=Decimal('25000000'),
            annual_revenue_gbp=Decimal('35000000'),
            net_profit_gbp=Decimal('5000000'),
            current_assets_gbp=Decimal('15000000'),
            current_liabilities_gbp=Decimal('8000000')
        )
    
    def test_financial_info_creation(self):
        """Test financial information creation."""
        self.assertEqual(self.financial_info.total_assets_gbp, Decimal('50000000'))
        self.assertEqual(self.financial_info.net_assets_gbp, Decimal('25000000'))
        self.assertEqual(self.financial_info.annual_revenue_gbp, Decimal('35000000'))
        self.assertEqual(str(self.financial_info), 'Financial info for Test Developer Ltd')
    
    def test_calculated_ratios(self):
        """Test calculated financial ratios."""
        # Test profit margin
        expected_profit_margin = (Decimal('5000000') / Decimal('35000000')) * 100
        self.assertAlmostEqual(
            self.financial_info.profit_margin_percentage,
            expected_profit_margin,
            places=2
        )
        
        # Test current ratio
        expected_current_ratio = Decimal('15000000') / Decimal('8000000')
        self.assertAlmostEqual(
            self.financial_info.current_ratio,
            expected_current_ratio,
            places=2
        )
        
        # Test working capital
        expected_working_capital = Decimal('15000000') - Decimal('8000000')
        self.assertEqual(
            self.financial_info.working_capital_gbp,
            expected_working_capital
        )


class CreditInformationModelTest(TestCase):
    """Test the CreditInformation model."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.credit_info = CreditInformation.objects.create(
            partner=self.partner,
            credit_rating='BBB+',
            credit_score=720,
            total_debt_gbp=Decimal('20000000'),
            short_term_debt_gbp=Decimal('5000000')
        )
    
    def test_credit_info_creation(self):
        """Test credit information creation."""
        self.assertEqual(self.credit_info.credit_rating, 'BBB+')
        self.assertEqual(self.credit_info.credit_score, 720)
        self.assertEqual(self.credit_info.total_debt_gbp, Decimal('20000000'))
        self.assertEqual(str(self.credit_info), 'Credit info for Test Developer Ltd')
    
    def test_credit_score_validation(self):
        """Test credit score validation."""
        # Valid score
        credit_info = CreditInformation(
            partner=self.partner,
            credit_score=650
        )
        credit_info.full_clean()  # Should not raise
        
        # Score too low
        with self.assertRaises(ValidationError):
            credit_info = CreditInformation(
                partner=self.partner,
                credit_score=299
            )
            credit_info.full_clean()
        
        # Score too high
        with self.assertRaises(ValidationError):
            credit_info = CreditInformation(
                partner=self.partner,
                credit_score=851
            )
            credit_info.full_clean()


class LegacyAssessmentModelTest(TestCase):
    """Test the LegacyAssessment model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='assessor@example.com',
            password='testpass123',
            role='ANALYST'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.user.groups.add(self.group)
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.assessment = LegacyAssessment.objects.create(
            group=self.group,
            partner=self.partner,
            assessment_name='Q1 2024 Assessment',
            assessor=self.user,
            status=AssessmentStatus.DRAFT
        )
    
    def test_assessment_creation(self):
        """Test assessment creation."""
        self.assertEqual(self.assessment.assessment_name, 'Q1 2024 Assessment')
        self.assertEqual(self.assessment.partner, self.partner)
        self.assertEqual(self.assessment.assessor, self.user)
        self.assertEqual(self.assessment.status, AssessmentStatus.DRAFT)
        self.assertEqual(str(self.assessment), 'Q1 2024 Assessment')
    
    def test_assessment_decision_update(self):
        """Test updating assessment decision."""
        self.assessment.assessment_decision = AssessmentDecision.ACCEPTABLE
        self.assessment.save()
        
        self.assertEqual(self.assessment.assessment_decision, AssessmentDecision.ACCEPTABLE)


class LegacyAssessmentMetricModelTest(TestCase):
    """Test the LegacyAssessmentMetric model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='assessor@example.com',
            password='testpass123',
            role='ANALYST'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.assessment = LegacyAssessment.objects.create(
            group=self.group,
            partner=self.partner,
            assessment_name='Test Assessment',
            assessor=self.user
        )
        
        self.metric = LegacyAssessmentMetric.objects.create(
            assessment=self.assessment,
            metric_name='Financial Strength',
            metric_score=4,
            metric_weight=5,
            metric_rationale='Strong balance sheet and profitability'
        )
    
    def test_metric_creation(self):
        """Test metric creation."""
        self.assertEqual(self.metric.metric_name, 'Financial Strength')
        self.assertEqual(self.metric.metric_score, 4)
        self.assertEqual(self.metric.metric_weight, 5)
        self.assertEqual(self.metric.metric_rationale, 'Strong balance sheet and profitability')
        self.assertEqual(str(self.metric), 'Financial Strength')
    
    def test_metric_score_validation(self):
        """Test metric score validation."""
        # Valid score
        metric = LegacyAssessmentMetric(
            assessment=self.assessment,
            metric_name='Test Metric',
            metric_score=3,
            metric_weight=4
        )
        metric.full_clean()  # Should not raise
        
        # Score too low
        with self.assertRaises(ValidationError):
            metric = LegacyAssessmentMetric(
                assessment=self.assessment,
                metric_name='Test Metric',
                metric_score=0,
                metric_weight=4
            )
            metric.full_clean()
        
        # Score too high
        with self.assertRaises(ValidationError):
            metric = LegacyAssessmentMetric(
                assessment=self.assessment,
                metric_name='Test Metric',
                metric_score=6,
                metric_weight=4
            )
            metric.full_clean()
    
    def test_metric_weight_validation(self):
        """Test metric weight validation."""
        # Valid weight
        metric = LegacyAssessmentMetric(
            assessment=self.assessment,
            metric_name='Test Metric',
            metric_score=3,
            metric_weight=3
        )
        metric.full_clean()  # Should not raise
        
        # Weight too low
        with self.assertRaises(ValidationError):
            metric = LegacyAssessmentMetric(
                assessment=self.assessment,
                metric_name='Test Metric',
                metric_score=3,
                metric_weight=0
            )
            metric.full_clean()
        
        # Weight too high
        with self.assertRaises(ValidationError):
            metric = LegacyAssessmentMetric(
                assessment=self.assessment,
                metric_name='Test Metric',
                metric_score=3,
                metric_weight=6
            )
            metric.full_clean()


class FXRateModelTest(TestCase):
    """Test the FXRate model."""
    
    def setUp(self):
        """Set up test data."""
        self.fx_rate = FXRate.objects.create(
            from_currency=Currency.GBP,
            to_currency=Currency.USD,
            rate=Decimal('1.2750'),
            rate_date=date.today()
        )
    
    def test_fx_rate_creation(self):
        """Test FX rate creation."""
        self.assertEqual(self.fx_rate.from_currency, Currency.GBP)
        self.assertEqual(self.fx_rate.to_currency, Currency.USD)
        self.assertEqual(self.fx_rate.rate, Decimal('1.2750'))
        self.assertEqual(self.fx_rate.rate_date, date.today())
        
        expected_str = f'GBP to USD: 1.2750 ({date.today()})'
        self.assertEqual(str(self.fx_rate), expected_str)
    
    def test_unique_constraint(self):
        """Test unique constraint on currency pair and date."""
        # Try to create duplicate
        with self.assertRaises(Exception):
            FXRate.objects.create(
                from_currency=Currency.GBP,
                to_currency=Currency.USD,
                rate=Decimal('1.2800'),
                rate_date=date.today()
            )


class AuditLogModelTest(TestCase):
    """Test the Legacy AuditLog model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='auditor@example.com',
            password='testpass123',
            role='MANAGER'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.audit = AssessmentAuditLog_Legacy.objects.create(
            user=self.user,
            action='UPDATE',
            model_name='DevelopmentPartner',
            object_id='123e4567-e89b-12d3-a456-426614174000',
            changes={'company_name': {'old': 'Old Name', 'new': 'New Name'}}
        )
    
    def test_audit_log_creation(self):
        """Test audit log creation."""
        self.assertEqual(self.audit.user, self.user)
        self.assertEqual(self.audit.action, 'UPDATE')
        self.assertEqual(self.audit.model_name, 'DevelopmentPartner')
        self.assertEqual(self.audit.object_id, '123e4567-e89b-12d3-a456-426614174000')
        self.assertIn('company_name', self.audit.changes)
        
        expected_str = f'{self.user.email} - UPDATE - DevelopmentPartner'
        self.assertEqual(str(self.audit), expected_str)


class IntegrationTest(TestCase):
    """Integration tests for model interactions."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='integration@example.com',
            password='testpass123',
            role='MANAGER'
        )
        
        self.group = Group.objects.create(
            name='Integration Test Group',
            group_type='COMPANY'
        )
        
        self.user.groups.add(self.group)
    
    def test_complete_partner_setup(self):
        """Test creating a complete partner with all related data."""
        # Create partner
        partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Complete Developer Ltd',
            trading_name='Complete Dev',
            headquarters_city='London',
            headquarters_country='GB',
            year_established=2015,
            number_of_employees=200,
            size_of_development_team=40,
            schemes_completed=15,
            schemes_in_development=5
        )
        
        # Add office locations
        OfficeLocation.objects.create(
            partner=partner,
            city='Manchester',
            country='GB'
        )
        
        OfficeLocation.objects.create(
            partner=partner,
            city='Dubai',
            country='AE'
        )
        
        # Add financial partners
        FinancialPartner.objects.create(
            partner=partner,
            name='Capital Fund ABC',
            relationship_type='equity_partner'
        )
        
        # Add shareholders
        KeyShareholder.objects.create(
            partner=partner,
            name='Founder Group',
            ownership_percentage=Decimal('60')
        )
        
        KeyShareholder.objects.create(
            partner=partner,
            name='Investment Fund',
            ownership_percentage=Decimal('40')
        )
        
        # Add financial information
        FinancialInformation.objects.create(
            partner=partner,
            financial_year_end=date(2023, 12, 31),
            total_assets_gbp=Decimal('75000000'),
            net_assets_gbp=Decimal('40000000'),
            annual_revenue_gbp=Decimal('50000000'),
            net_profit_gbp=Decimal('8000000')
        )
        
        # Add credit information
        CreditInformation.objects.create(
            partner=partner,
            credit_rating='A-',
            credit_score=750,
            total_debt_gbp=Decimal('25000000')
        )
        
        # Verify relationships
        self.assertEqual(partner.office_locations.count(), 2)
        self.assertEqual(partner.financial_partners.count(), 1)
        self.assertEqual(partner.key_shareholders.count(), 2)
        self.assertTrue(hasattr(partner, 'financial_info'))
        self.assertTrue(hasattr(partner, 'credit_info'))
        
        # Test aggregate calculations
        total_ownership = sum(s.ownership_percentage for s in partner.key_shareholders.all())
        self.assertEqual(total_ownership, Decimal('100'))
    
    def test_complete_assessment_workflow(self):
        """Test complete assessment workflow."""
        # Create partner
        partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Assessment Test Developer'
        )
        
        # Create assessment
        assessment = LegacyAssessment.objects.create(
            group=self.group,
            partner=partner,
            assessment_name='Complete Assessment Test',
            assessor=self.user,
            status=AssessmentStatus.DRAFT
        )
        
        # Add metrics
        metrics_data = [
            ('Financial Strength', 4, 5),
            ('Operational Capability', 5, 4),
            ('Track Record', 4, 5),
            ('Market Position', 3, 3),
            ('Risk Management', 4, 4)
        ]
        
        for name, score, weight in metrics_data:
            LegacyAssessmentMetric.objects.create(
                assessment=assessment,
                metric_name=name,
                metric_score=score,
                metric_weight=weight,
                metric_rationale=f'Rationale for {name}'
            )
        
        # Calculate total weighted score
        total_weighted_score = sum(m.metric_score * m.metric_weight 
                                  for m in assessment.metrics.all())
        max_possible_score = sum(5 * m.metric_weight 
                                for m in assessment.metrics.all())
        score_percentage = (total_weighted_score / max_possible_score) * 100
        
        # Update assessment
        assessment.total_weighted_score = total_weighted_score
        assessment.max_possible_score = max_possible_score
        assessment.score_percentage = score_percentage
        
        # Determine decision based on score
        if score_percentage >= 80:
            assessment.assessment_decision = AssessmentDecision.PREMIUM_PRIORITY
        elif score_percentage >= 60:
            assessment.assessment_decision = AssessmentDecision.ACCEPTABLE
        else:
            assessment.assessment_decision = AssessmentDecision.REJECT
        
        assessment.status = AssessmentStatus.APPROVED
        assessment.save()
        
        # Verify results
        self.assertEqual(assessment.metrics.count(), 5)
        self.assertEqual(assessment.total_weighted_score, 84)  # Calculated value
        self.assertEqual(assessment.max_possible_score, 105)   # 5 * (5+4+5+3+4)
        self.assertEqual(assessment.assessment_decision, AssessmentDecision.ACCEPTABLE)
        self.assertEqual(assessment.status, AssessmentStatus.APPROVED)
        
        # Create audit log
        AssessmentAuditLog_Legacy.objects.create(
            user=self.user,
            action='APPROVE',
            model_name='LegacyAssessment',
            object_id=str(assessment.id),
            changes={'status': {'old': 'DRAFT', 'new': 'APPROVED'}}
        )
        
        # Verify audit log
        audit_logs = AssessmentAuditLog_Legacy.objects.filter(
            model_name='LegacyAssessment',
            object_id=str(assessment.id)
        )
        self.assertEqual(audit_logs.count(), 1)