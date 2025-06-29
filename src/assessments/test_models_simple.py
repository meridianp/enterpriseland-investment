"""
Simple tests for assessment models without signals.
"""
from django.test import TestCase
from django.db.models.signals import post_save
from tests.base import BaseTestCase
from tests.factories.user_factories import UserFactory, GroupFactory
from tests.factories.assessment_factories import (
    DevelopmentPartnerFactory, AssessmentFactory,
    FinancialInformationFactory, CreditInformationFactory,
    create_complete_assessment
)
from assessments.models import (
    DevelopmentPartner, Assessment, FinancialInformation,
    CreditInformation, Currency
)
from assessments.signals import assessment_post_save


class DevelopmentPartnerModelTest(BaseTestCase):
    """Test DevelopmentPartner model."""
    
    @classmethod
    def setUpTestData(cls):
        # Disconnect the signal that causes issues with SQLite
        post_save.disconnect(assessment_post_save, sender=Assessment)
    
    @classmethod
    def tearDownClass(cls):
        # Reconnect the signal
        post_save.connect(assessment_post_save, sender=Assessment)
        super().tearDownClass()
    
    def test_create_development_partner(self):
        """Test creating a development partner."""
        partner = DevelopmentPartnerFactory(group=self.group)
        
        self.assertEqual(partner.group, self.group)
        self.assertTrue(partner.company_name)
        self.assertIsNotNone(partner.year_established)
        
    def test_pbsa_specialization_pct_property(self):
        """Test PBSA specialization percentage calculation."""
        partner = DevelopmentPartnerFactory(
            group=self.group,
            schemes_in_development=10,
            pbsa_schemes_in_development=7
        )
        
        self.assertEqual(partner.pbsa_specialization_pct, 70.0)
        
    def test_pbsa_specialization_pct_none(self):
        """Test PBSA specialization with no schemes."""
        partner = DevelopmentPartnerFactory(
            group=self.group,
            schemes_in_development=0,
            pbsa_schemes_in_development=0
        )
        
        self.assertIsNone(partner.pbsa_specialization_pct)
        
    def test_avg_pbsa_scheme_size(self):
        """Test average PBSA scheme size calculation."""
        partner = DevelopmentPartnerFactory(
            group=self.group,
            completed_pbsa_schemes=5,
            total_pbsa_beds_delivered=1000
        )
        
        self.assertEqual(partner.avg_pbsa_scheme_size, 200)
        
    def test_str_representation(self):
        """Test string representation."""
        partner = DevelopmentPartnerFactory(company_name="Test Partner Ltd", group=self.group)
        self.assertEqual(str(partner), "Test Partner Ltd")


class AssessmentModelTest(BaseTestCase):
    """Test Assessment model."""
    
    @classmethod
    def setUpTestData(cls):
        # Disconnect the signal that causes issues with SQLite
        post_save.disconnect(assessment_post_save, sender=Assessment)
    
    @classmethod
    def tearDownClass(cls):
        # Reconnect the signal
        post_save.connect(assessment_post_save, sender=Assessment)
        super().tearDownClass()
    
    def test_create_assessment(self):
        """Test creating an assessment."""
        partner = DevelopmentPartnerFactory(group=self.group)
        assessment = AssessmentFactory(
            group=self.group,
            partner=partner,
            created_by=self.analyst_user,
            status='DRAFT'
        )
        
        self.assertEqual(assessment.group, self.group)
        self.assertEqual(assessment.status, 'DRAFT')
        self.assertEqual(assessment.version_major, 1)
        self.assertEqual(assessment.version_minor, 0)
        self.assertEqual(assessment.version_patch, 0)
        
    def test_version_methods(self):
        """Test version increment methods."""
        partner = DevelopmentPartnerFactory(group=self.group)
        assessment = AssessmentFactory(
            group=self.group,
            partner=partner,
            created_by=self.analyst_user
        )
        
        # Test increment_patch
        assessment.increment_patch(self.analyst_user)
        self.assertEqual(assessment.version_patch, 1)
        self.assertEqual(assessment.updated_by, self.analyst_user)
        
        # Test increment_minor
        assessment.increment_minor(self.analyst_user)
        self.assertEqual(assessment.version_minor, 1)
        self.assertEqual(assessment.version_patch, 0)
        
        # Test increment_major
        assessment.increment_major(self.analyst_user)
        self.assertEqual(assessment.version_major, 2)
        self.assertEqual(assessment.version_minor, 0)
        self.assertEqual(assessment.version_patch, 0)
        
    def test_semver_property(self):
        """Test semantic version string."""
        partner = DevelopmentPartnerFactory(group=self.group)
        assessment = AssessmentFactory(
            group=self.group,
            partner=partner,
            version_major=2,
            version_minor=3,
            version_patch=4
        )
        
        self.assertEqual(assessment.semver, "2.3.4")


class FinancialInformationModelTest(BaseTestCase):
    """Test FinancialInformation model."""
    
    def test_profit_margin_calculation(self):
        """Test profit margin percentage calculation."""
        financial_info = FinancialInformationFactory(
            latest_annual_revenue_amount=1000000,
            net_profit_before_tax_amount=150000
        )
        
        self.assertEqual(financial_info.profit_margin_pct, 15.0)
        
    def test_profit_margin_zero_revenue(self):
        """Test profit margin with zero revenue."""
        financial_info = FinancialInformationFactory(
            latest_annual_revenue_amount=0,
            net_profit_before_tax_amount=100000
        )
        
        self.assertIsNone(financial_info.profit_margin_pct)