"""
Tests for assessment models.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from decimal import Decimal
from datetime import date, datetime

from tests.base import BaseTestCase
from tests.factories.user_factories import UserFactory, GroupFactory, create_test_users
from tests.factories.assessment_factories import (
    DevelopmentPartnerFactory, AssessmentFactory, FinancialInformationFactory,
    CreditInformationFactory, AssessmentMetricFactory, FXRateFactory,
    OfficeLocationFactory, KeyShareholderFactory, FinancialPartnerFactory,
    create_complete_assessment, create_assessment_workflow
)
from assessments.models import (
    DevelopmentPartner, Assessment, FinancialInformation, 
    CreditInformation, AssessmentMetric, FXRate
)


class DevelopmentPartnerModelTest(BaseTestCase):
    """Test DevelopmentPartner model."""
    
    def test_create_development_partner(self):
        """Test creating a development partner."""
        partner = DevelopmentPartnerFactory(group=self.group)
        
        self.assertEqual(partner.group, self.group)
        self.assertTrue(partner.name)
        self.assertTrue(partner.registration_number)
        self.assertIsNotNone(partner.year_established)
        
    def test_pbsa_specialization_pct_property(self):
        """Test PBSA specialization percentage calculation."""
        partner = DevelopmentPartnerFactory(
            group=self.group,
            total_employees=100,
            development_employees=25
        )
        
        self.assertEqual(partner.pbsa_specialization_pct, 25.0)
        
    def test_pbsa_specialization_pct_zero_employees(self):
        """Test PBSA specialization with zero total employees."""
        partner = DevelopmentPartnerFactory(
            group=self.group,
            total_employees=0,
            development_employees=0
        )
        
        self.assertEqual(partner.pbsa_specialization_pct, 0)
        
    def test_avg_pbsa_scheme_size(self):
        """Test average PBSA scheme size calculation."""
        partner = DevelopmentPartnerFactory(group=self.group)
        
        # Create assessments with different total_beds
        AssessmentFactory(
            development_partner=partner,
            group=self.group,
            status='APPROVED'
        )
        
        # Since we don't have PBSA schemes in the new model, 
        # this should return 0 or be calculated differently
        self.assertEqual(partner.avg_pbsa_scheme_size, 0)
        
    def test_office_locations_relationship(self):
        """Test office locations many-to-many relationship."""
        partner = DevelopmentPartnerFactory(group=self.group)
        
        # Partner should have office locations from factory
        self.assertGreaterEqual(partner.office_locations.count(), 1)
        
        # Test headquarters
        hq = partner.office_locations.filter(is_headquarters=True).first()
        self.assertIsNotNone(hq)
        
    def test_key_shareholders_relationship(self):
        """Test key shareholders relationship."""
        partner = DevelopmentPartnerFactory(group=self.group)
        
        # Partner should have shareholders from factory
        self.assertGreaterEqual(partner.key_shareholders.count(), 2)
        
        # Total ownership should be close to 100%
        total_ownership = sum(
            s.ownership_percentage for s in partner.key_shareholders.all()
        )
        self.assertAlmostEqual(float(total_ownership), 100.0, delta=1.0)
        
    def test_financial_partners_relationship(self):
        """Test financial partners relationship."""
        partner = DevelopmentPartnerFactory(group=self.group)
        
        # Add a financial partner
        financial_partner = FinancialPartnerFactory(partner=partner)
        
        self.assertIn(financial_partner, partner.financial_partners.all())
        
    def test_group_filtering(self):
        """Test that partners are filtered by group."""
        # Create partners in different groups
        partner1 = DevelopmentPartnerFactory(group=self.group)
        
        other_group = GroupFactory()
        partner2 = DevelopmentPartnerFactory(group=other_group)
        
        # Query from perspective of user in self.group
        visible_partners = DevelopmentPartner.objects.filter(group=self.group)
        
        self.assertIn(partner1, visible_partners)
        self.assertNotIn(partner2, visible_partners)
        
    def test_str_representation(self):
        """Test string representation."""
        partner = DevelopmentPartnerFactory(name="Test Partner Ltd", group=self.group)
        self.assertEqual(str(partner), "Test Partner Ltd")


class AssessmentModelTest(BaseTestCase):
    """Test Assessment model."""
    
    def test_create_assessment(self):
        """Test creating an assessment."""
        assessment = create_complete_assessment(group=self.group)
        
        self.assertEqual(assessment.group, self.group)
        self.assertEqual(assessment.status, 'DRAFT')
        self.assertIsNone(assessment.decision)
        self.assertEqual(assessment.version_major, 1)
        self.assertEqual(assessment.version_minor, 0)
        self.assertEqual(assessment.version_patch, 0)
        
    def test_state_transitions(self):
        """Test assessment state transitions."""
        assessment = AssessmentFactory(
            group=self.group,
            status='DRAFT'
        )
        
        # Draft -> In Review
        assessment.status = 'IN_REVIEW'
        assessment.save()
        self.assertEqual(assessment.status, 'IN_REVIEW')
        
        # In Review -> Approved
        assessment.status = 'APPROVED'
        assessment.decision = 'APPROVED'
        assessment.decision_by = self.manager_user
        assessment.decision_date = datetime.now()
        assessment.save()
        
        self.assertEqual(assessment.status, 'APPROVED')
        self.assertEqual(assessment.decision, 'APPROVED')
        self.assertIsNotNone(assessment.decision_date)
        
    def test_version_increment_methods(self):
        """Test version increment methods."""
        assessment = AssessmentFactory(
            group=self.group,
            version_major=1,
            version_minor=2,
            version_patch=3
        )
        
        # Test patch increment
        assessment.increment_patch()
        self.assertEqual(assessment.version_patch, 4)
        
        # Test minor increment (resets patch)
        assessment.increment_minor()
        self.assertEqual(assessment.version_minor, 3)
        self.assertEqual(assessment.version_patch, 0)
        
        # Test major increment (resets minor and patch)
        assessment.increment_major()
        self.assertEqual(assessment.version_major, 2)
        self.assertEqual(assessment.version_minor, 0)
        self.assertEqual(assessment.version_patch, 0)
        
    def test_total_score_calculation(self):
        """Test total score calculation from metrics."""
        assessment = create_complete_assessment(group=self.group)
        
        # Metrics are created by factory
        metrics = assessment.metrics.all()
        self.assertGreater(metrics.count(), 0)
        
        # Calculate expected total score
        expected_score = sum(m.weighted_score for m in metrics)
        self.assertEqual(assessment.total_score, expected_score)
        
    def test_risk_fields_validation(self):
        """Test risk score field validation (1-10 range)."""
        assessment = AssessmentFactory.build(
            group=self.group,
            financial_risk=11  # Invalid - should be 1-10
        )
        
        with self.assertRaises(ValidationError):
            assessment.full_clean()
            
    def test_decision_requires_decision_by(self):
        """Test that decision requires decision_by user."""
        assessment = AssessmentFactory(
            group=self.group,
            status='IN_REVIEW'
        )
        
        # Set decision without decision_by should be invalid
        assessment.decision = 'APPROVED'
        assessment.decision_date = datetime.now()
        # Note: This validation might need to be implemented in the model
        
    def test_cascade_delete_related_objects(self):
        """Test cascade deletion of related objects."""
        assessment = create_complete_assessment(group=self.group)
        
        # Get related object IDs
        financial_info_id = assessment.financial_info.id
        credit_info_id = assessment.credit_info.id
        metric_ids = list(assessment.metrics.values_list('id', flat=True))
        
        # Delete assessment
        assessment.delete()
        
        # Check related objects are deleted
        self.assertFalse(
            FinancialInformation.objects.filter(id=financial_info_id).exists()
        )
        self.assertFalse(
            CreditInformation.objects.filter(id=credit_info_id).exists()
        )
        self.assertFalse(
            AssessmentMetric.objects.filter(id__in=metric_ids).exists()
        )
        
    def test_str_representation(self):
        """Test string representation."""
        partner = DevelopmentPartnerFactory(name="ABC Corp", group=self.group)
        assessment = AssessmentFactory(
            development_partner=partner,
            group=self.group,
            assessment_type='INITIAL'
        )
        
        expected = f"ABC Corp - INITIAL Assessment"
        self.assertEqual(str(assessment), expected)


class FinancialInformationModelTest(BaseTestCase):
    """Test FinancialInformation model."""
    
    def test_create_financial_information(self):
        """Test creating financial information."""
        assessment = create_complete_assessment(group=self.group)
        financial_info = assessment.financial_info
        
        self.assertIsNotNone(financial_info)
        self.assertEqual(financial_info.assessment, assessment)
        self.assertIn(financial_info.currency, ['USD', 'GBP', 'EUR'])
        
    def test_profit_margin_pct_calculation(self):
        """Test profit margin percentage calculation."""
        financial_info = FinancialInformationFactory(
            revenue=Decimal('1000000'),
            ebitda=Decimal('200000')
        )
        
        self.assertEqual(financial_info.profit_margin_pct, 20.0)
        
    def test_profit_margin_pct_zero_revenue(self):
        """Test profit margin with zero revenue."""
        financial_info = FinancialInformationFactory(
            revenue=Decimal('0'),
            ebitda=Decimal('100000')
        )
        
        self.assertEqual(financial_info.profit_margin_pct, 0)
        
    def test_leverage_band_calculation(self):
        """Test leverage band calculation."""
        # Low leverage
        financial_info = FinancialInformationFactory(
            total_debt=Decimal('1000000'),
            ebitda=Decimal('500000')  # Ratio = 2
        )
        self.assertEqual(financial_info.leverage_band, 'Low')
        
        # Medium leverage
        financial_info = FinancialInformationFactory(
            total_debt=Decimal('2000000'),
            ebitda=Decimal('500000')  # Ratio = 4
        )
        self.assertEqual(financial_info.leverage_band, 'Medium')
        
        # High leverage
        financial_info = FinancialInformationFactory(
            total_debt=Decimal('3000000'),
            ebitda=Decimal('500000')  # Ratio = 6
        )
        self.assertEqual(financial_info.leverage_band, 'High')
        
    def test_liquidity_risk_calculation(self):
        """Test liquidity risk calculation."""
        # Low risk (high net worth to debt ratio)
        financial_info = FinancialInformationFactory(
            net_worth=Decimal('5000000'),
            total_debt=Decimal('1000000')  # Ratio = 5
        )
        self.assertEqual(financial_info.liquidity_risk, 'Low')
        
        # Medium risk
        financial_info = FinancialInformationFactory(
            net_worth=Decimal('1500000'),
            total_debt=Decimal('1000000')  # Ratio = 1.5
        )
        self.assertEqual(financial_info.liquidity_risk, 'Medium')
        
        # High risk
        financial_info = FinancialInformationFactory(
            net_worth=Decimal('800000'),
            total_debt=Decimal('1000000')  # Ratio = 0.8
        )
        self.assertEqual(financial_info.liquidity_risk, 'High')
        
    def test_currency_choices(self):
        """Test currency field choices."""
        financial_info = FinancialInformationFactory.build(currency='JPY')
        
        with self.assertRaises(ValidationError):
            financial_info.full_clean()


class CreditInformationModelTest(BaseTestCase):
    """Test CreditInformation model."""
    
    def test_create_credit_information(self):
        """Test creating credit information."""
        assessment = create_complete_assessment(group=self.group)
        credit_info = assessment.credit_info
        
        self.assertIsNotNone(credit_info)
        self.assertEqual(credit_info.assessment, assessment)
        self.assertIn(credit_info.credit_rating_agency, ["Moody's", "S&P", "Fitch"])
        
    def test_rating_choices(self):
        """Test credit rating choices."""
        valid_ratings = ['AAA', 'AA', 'A', 'BBB', 'BB', 'B']
        credit_info = CreditInformationFactory(
            credit_rating='AAA'
        )
        self.assertIn(credit_info.credit_rating, valid_ratings)
        
    def test_rating_outlook_choices(self):
        """Test rating outlook choices."""
        valid_outlooks = ['Stable', 'Positive', 'Negative']
        credit_info = CreditInformationFactory(
            rating_outlook='Stable'
        )
        self.assertIn(credit_info.rating_outlook, valid_outlooks)


class AssessmentMetricModelTest(BaseTestCase):
    """Test AssessmentMetric model."""
    
    def test_create_assessment_metric(self):
        """Test creating an assessment metric."""
        assessment = create_complete_assessment(group=self.group)
        metric = AssessmentMetricFactory(
            assessment=assessment,
            metric_name='Financial Stability',
            score=4,
            weight=5
        )
        
        self.assertEqual(metric.assessment, assessment)
        self.assertEqual(metric.metric_name, 'Financial Stability')
        self.assertEqual(metric.weighted_score, 20)  # 4 * 5
        
    def test_weighted_score_calculation(self):
        """Test weighted score calculation."""
        metric = AssessmentMetricFactory(score=3, weight=4)
        self.assertEqual(metric.weighted_score, 12)
        
        metric = AssessmentMetricFactory(score=5, weight=5)
        self.assertEqual(metric.weighted_score, 25)
        
    def test_score_validation(self):
        """Test score must be between 1 and 5."""
        metric = AssessmentMetricFactory.build(score=6)
        
        with self.assertRaises(ValidationError):
            metric.full_clean()
            
        metric = AssessmentMetricFactory.build(score=0)
        
        with self.assertRaises(ValidationError):
            metric.full_clean()
            
    def test_weight_validation(self):
        """Test weight must be between 1 and 5."""
        metric = AssessmentMetricFactory.build(weight=6)
        
        with self.assertRaises(ValidationError):
            metric.full_clean()
            
    def test_unique_constraint(self):
        """Test unique constraint on assessment + metric_name."""
        assessment = create_complete_assessment(group=self.group)
        
        # Create first metric
        AssessmentMetricFactory(
            assessment=assessment,
            metric_name='Test Metric'
        )
        
        # Try to create duplicate
        with self.assertRaises(IntegrityError):
            AssessmentMetricFactory(
                assessment=assessment,
                metric_name='Test Metric'
            )


class FXRateModelTest(BaseTestCase):
    """Test FXRate model."""
    
    def test_create_fx_rate(self):
        """Test creating an FX rate."""
        rate = FXRateFactory(
            base_currency='USD',
            target_currency='EUR',
            rate=Decimal('0.85'),
            rate_date=date.today()
        )
        
        self.assertEqual(rate.base_currency, 'USD')
        self.assertEqual(rate.target_currency, 'EUR')
        self.assertEqual(rate.rate, Decimal('0.85'))
        
    def test_unique_constraint(self):
        """Test unique constraint on currency pair and date."""
        rate_date = date.today()
        
        # Create first rate
        FXRateFactory(
            base_currency='USD',
            target_currency='EUR',
            rate_date=rate_date
        )
        
        # Try to create duplicate
        with self.assertRaises(IntegrityError):
            FXRateFactory(
                base_currency='USD',
                target_currency='EUR',
                rate_date=rate_date
            )
            
    def test_str_representation(self):
        """Test string representation."""
        rate = FXRateFactory(
            base_currency='USD',
            target_currency='GBP',
            rate=Decimal('0.75'),
            rate_date=date(2024, 1, 15)
        )
        
        expected = "USD/GBP: 0.75 (2024-01-15)"
        self.assertEqual(str(rate), expected)


class AssessmentWorkflowTest(BaseTestCase):
    """Test complete assessment workflows."""
    
    def test_complete_assessment_creation(self):
        """Test creating a complete assessment with all relationships."""
        assessment = create_complete_assessment(
            group=self.group,
            created_by=self.analyst_user
        )
        
        # Check all relationships exist
        self.assertIsNotNone(assessment.development_partner)
        self.assertIsNotNone(assessment.financial_info)
        self.assertIsNotNone(assessment.credit_info)
        self.assertGreater(assessment.metrics.count(), 0)
        
        # Check partner has related data
        partner = assessment.development_partner
        self.assertGreater(partner.office_locations.count(), 0)
        self.assertGreater(partner.key_shareholders.count(), 0)
        
    def test_assessment_workflow_states(self):
        """Test creating assessments in different workflow states."""
        workflows = create_assessment_workflow(group=self.group)
        
        # Check draft assessment
        self.assertEqual(workflows['draft'].status, 'DRAFT')
        self.assertIsNone(workflows['draft'].decision)
        
        # Check in review assessment
        self.assertEqual(workflows['in_review'].status, 'IN_REVIEW')
        
        # Check approved assessment
        self.assertEqual(workflows['approved'].status, 'APPROVED')
        self.assertEqual(workflows['approved'].decision, 'APPROVED')
        self.assertIsNotNone(workflows['approved'].decision_by)
        
        # Check rejected assessment
        self.assertEqual(workflows['rejected'].status, 'REJECTED')
        self.assertEqual(workflows['rejected'].decision, 'REJECTED')
        self.assertIsNotNone(workflows['rejected'].decision_by)