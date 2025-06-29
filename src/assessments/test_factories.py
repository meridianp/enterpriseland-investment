"""
Test that assessment factories work correctly.
"""
from django.test import TestCase
from tests.base import BaseTestCase
from tests.factories.user_factories import UserFactory, GroupFactory
from tests.factories.assessment_factories import (
    DevelopmentPartnerFactory, AssessmentFactory,
    create_complete_assessment
)


class FactoryTest(BaseTestCase):
    """Test factory functionality."""
    
    def test_development_partner_factory(self):
        """Test DevelopmentPartnerFactory creates valid objects."""
        partner = DevelopmentPartnerFactory(group=self.group)
        
        self.assertIsNotNone(partner.id)
        self.assertEqual(partner.group, self.group)
        self.assertTrue(partner.company_name)
        self.assertIsNotNone(partner.year_established)
        
    def test_assessment_factory(self):
        """Test AssessmentFactory creates valid objects."""
        partner = DevelopmentPartnerFactory(group=self.group)
        assessment = AssessmentFactory(
            group=self.group,
            partner=partner,
            created_by=self.analyst_user
        )
        
        self.assertIsNotNone(assessment.id)
        self.assertEqual(assessment.group, self.group)
        self.assertEqual(assessment.partner, partner)
        self.assertEqual(assessment.created_by, self.analyst_user)
        
    def test_create_complete_assessment(self):
        """Test create_complete_assessment helper."""
        assessment = create_complete_assessment(
            group=self.group,
            created_by=self.analyst_user
        )
        
        self.assertIsNotNone(assessment)
        self.assertIsNotNone(assessment.partner)
        self.assertIsNotNone(assessment.financial_info)
        self.assertIsNotNone(assessment.credit_info)
        self.assertGreater(assessment.metrics.count(), 0)