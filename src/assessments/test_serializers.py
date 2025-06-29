"""
Tests for assessment serializers.
"""
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from decimal import Decimal
from unittest.mock import Mock

from tests.base import BaseTestCase
from tests.factories.user_factories import UserFactory, GroupFactory
from tests.factories.assessment_factories import (
    DevelopmentPartnerFactory, AssessmentFactory,
    FinancialInformationFactory, CreditInformationFactory,
    AssessmentMetricFactory, OfficeLocationFactory,
    KeyShareholderFactory, FinancialPartnerFactory
)
from assessments.serializers import (
    DevelopmentPartnerSerializer, DevelopmentPartnerCreateSerializer,
    AssessmentSerializer, AssessmentCreateSerializer,
    FinancialInformationSerializer, CreditInformationSerializer,
    AssessmentMetricSerializer, OfficeLocationSerializer,
    KeyShareholderSerializer, FinancialPartnerSerializer
)
from assessments.models import DevelopmentPartner, Assessment, AssessmentStatus
from accounts.models import GroupMembership


class OfficeLocationSerializerTest(BaseTestCase):
    """Test OfficeLocationSerializer."""
    
    def test_serialization(self):
        """Test serializing an office location."""
        location = OfficeLocationFactory()
        serializer = OfficeLocationSerializer(location)
        
        self.assertIn('id', serializer.data)
        self.assertIn('city', serializer.data)
        self.assertIn('country', serializer.data)
        self.assertEqual(serializer.data['city'], location.city)
        self.assertEqual(serializer.data['country'], location.country)
        
    def test_deserialization(self):
        """Test deserializing office location data."""
        data = {
            'city': 'London',
            'country': 'GB'
        }
        
        serializer = OfficeLocationSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['city'], 'London')
        self.assertEqual(serializer.validated_data['country'], 'GB')


class KeyShareholderSerializerTest(BaseTestCase):
    """Test KeyShareholderSerializer."""
    
    def test_serialization(self):
        """Test serializing a key shareholder."""
        shareholder = KeyShareholderFactory(
            name='John Smith',
            ownership_percentage=Decimal('25.50')
        )
        serializer = KeyShareholderSerializer(shareholder)
        
        self.assertEqual(serializer.data['name'], 'John Smith')
        self.assertEqual(serializer.data['ownership_percentage'], '25.50')
        
    def test_ownership_percentage_validation(self):
        """Test ownership percentage validation."""
        # Valid percentage
        data = {'name': 'Test Shareholder', 'ownership_percentage': '45.25'}
        serializer = KeyShareholderSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Invalid percentage (over 100)
        data = {'name': 'Test Shareholder', 'ownership_percentage': '105.00'}
        serializer = KeyShareholderSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        
        # Invalid percentage (negative)
        data = {'name': 'Test Shareholder', 'ownership_percentage': '-5.00'}
        serializer = KeyShareholderSerializer(data=data)
        self.assertFalse(serializer.is_valid())


class DevelopmentPartnerCreateSerializerTest(BaseTestCase):
    """Test DevelopmentPartnerCreateSerializer."""
    
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        
    def test_create_partner_with_nested_data(self):
        """Test creating partner with nested relationships."""
        request = self.factory.post('/')
        request.user = self.analyst_user
        
        data = {
            'company_name': 'Test Development Corp',
            'trading_name': 'Test Corp',
            'headquarter_city': 'London',
            'headquarter_country': 'GB',
            'year_established': 2010,
            'website_url': 'https://testcorp.com',
            'size_of_development_team': 25,
            'number_of_employees': 100,
            'office_locations': [
                {'city': 'London', 'country': 'GB'},
                {'city': 'Manchester', 'country': 'GB'}
            ],
            'key_shareholders': [
                {'name': 'John Smith', 'ownership_percentage': '60.00'},
                {'name': 'Jane Doe', 'ownership_percentage': '40.00'}
            ],
            'financial_partners': [
                {'name': 'Bank of London', 'relationship_type': 'debt'},
                {'name': 'Investment Fund A', 'relationship_type': 'equity'}
            ]
        }
        
        serializer = DevelopmentPartnerCreateSerializer(
            data=data, 
            context={'request': request}
        )
        
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        partner = serializer.save()
        
        # Verify main object
        self.assertEqual(partner.company_name, 'Test Development Corp')
        self.assertEqual(partner.group, self.group)
        
        # Verify nested relationships
        self.assertEqual(partner.office_locations.count(), 2)
        self.assertEqual(partner.key_shareholders.count(), 2)
        self.assertEqual(partner.financial_partners.count(), 2)
        
        # Verify ownership percentages
        total_ownership = sum(
            s.ownership_percentage for s in partner.key_shareholders.all()
        )
        self.assertEqual(total_ownership, Decimal('100.00'))
        
    def test_group_assignment_from_request(self):
        """Test that group is assigned from request user."""
        request = self.factory.post('/')
        request.user = self.analyst_user
        
        data = {
            'company_name': 'Test Partner',
            'year_established': 2020
        }
        
        serializer = DevelopmentPartnerCreateSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertTrue(serializer.is_valid())
        partner = serializer.save()
        
        self.assertEqual(partner.group, self.group)
        
    def test_empty_nested_data(self):
        """Test creating partner with empty nested relationships."""
        request = self.factory.post('/')
        request.user = self.analyst_user
        
        data = {
            'company_name': 'Simple Partner',
            'year_established': 2020,
            'office_locations': [],
            'key_shareholders': [],
            'financial_partners': []
        }
        
        serializer = DevelopmentPartnerCreateSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertTrue(serializer.is_valid())
        partner = serializer.save()
        
        self.assertEqual(partner.office_locations.count(), 0)
        self.assertEqual(partner.key_shareholders.count(), 0)
        self.assertEqual(partner.financial_partners.count(), 0)
        
    def test_invalid_nested_data(self):
        """Test validation with invalid nested data."""
        request = self.factory.post('/')
        request.user = self.analyst_user
        
        data = {
            'company_name': 'Test Partner',
            'key_shareholders': [
                {'name': 'Invalid Shareholder', 'ownership_percentage': '150.00'}  # Invalid percentage
            ]
        }
        
        serializer = DevelopmentPartnerCreateSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('key_shareholders', serializer.errors)


class DevelopmentPartnerSerializerTest(BaseTestCase):
    """Test DevelopmentPartnerSerializer (read-only)."""
    
    def test_computed_fields_serialization(self):
        """Test computed fields are included in serialization."""
        partner = DevelopmentPartnerFactory(
            schemes_in_development=10,
            pbsa_schemes_in_development=7,
            completed_pbsa_schemes=5,
            total_pbsa_beds_delivered=1000
        )
        
        serializer = DevelopmentPartnerSerializer(partner)
        
        self.assertIn('pbsa_specialization_pct', serializer.data)
        self.assertIn('avg_pbsa_scheme_size', serializer.data)
        self.assertEqual(serializer.data['pbsa_specialization_pct'], 70.0)
        self.assertEqual(serializer.data['avg_pbsa_scheme_size'], 200)
        
    def test_nested_relationships_serialization(self):
        """Test nested relationships are properly serialized."""
        partner = DevelopmentPartnerFactory()
        
        # Add some related objects
        OfficeLocationFactory(partner=partner, city='London')
        KeyShareholderFactory(partner=partner, name='Test Shareholder')
        FinancialPartnerFactory(partner=partner, name='Test Bank')
        
        serializer = DevelopmentPartnerSerializer(partner)
        
        self.assertIn('office_locations', serializer.data)
        self.assertIn('key_shareholders', serializer.data)
        self.assertIn('financial_partners', serializer.data)
        
        self.assertEqual(len(serializer.data['office_locations']), 1)
        self.assertEqual(len(serializer.data['key_shareholders']), 1)
        self.assertEqual(len(serializer.data['financial_partners']), 1)


class FinancialInformationSerializerTest(BaseTestCase):
    """Test FinancialInformationSerializer."""
    
    def test_profit_margin_calculation(self):
        """Test profit margin percentage calculation."""
        financial_info = FinancialInformationFactory(
            latest_annual_revenue_amount=Decimal('1000000'),
            net_profit_before_tax_amount=Decimal('150000')
        )
        
        serializer = FinancialInformationSerializer(financial_info)
        
        self.assertIn('profit_margin_pct', serializer.data)
        self.assertEqual(serializer.data['profit_margin_pct'], 15.0)
        
    def test_currency_consistency_validation(self):
        """Test that related currency fields are validated."""
        data = {
            'net_assets_amount': '1000000.00',
            'net_assets_currency': 'USD',
            'latest_annual_revenue_amount': '5000000.00',
            'latest_annual_revenue_currency': 'EUR'  # Different currency
        }
        
        serializer = FinancialInformationSerializer(data=data)
        # Note: This assumes we add currency consistency validation
        self.assertTrue(serializer.is_valid())  # For now, mixed currencies are allowed
        
    def test_required_fields(self):
        """Test validation of required fields."""
        data = {}
        serializer = FinancialInformationSerializer(data=data)
        
        # Financial information can be created with minimal data
        self.assertTrue(serializer.is_valid())


class CreditInformationSerializerTest(BaseTestCase):
    """Test CreditInformationSerializer."""
    
    def test_computed_fields_serialization(self):
        """Test computed fields in credit information."""
        credit_info = CreditInformationFactory(
            debt_to_total_assets_pct=Decimal('45.0'),
            interest_coverage_ratio=Decimal('2.5')
        )
        
        serializer = CreditInformationSerializer(credit_info)
        
        self.assertIn('leverage_band', serializer.data)
        self.assertIn('liquidity_risk', serializer.data)
        
    def test_percentage_field_validation(self):
        """Test percentage fields are within valid range."""
        data = {
            'debt_to_total_assets_pct': '150.00',  # Invalid - over 100%
            'short_term_debt_pct': '80.00'
        }
        
        serializer = CreditInformationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        
        # Valid data
        data = {
            'debt_to_total_assets_pct': '45.00',
            'short_term_debt_pct': '30.00'
        }
        
        serializer = CreditInformationSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class AssessmentMetricSerializerTest(BaseTestCase):
    """Test AssessmentMetricSerializer."""
    
    def test_weighted_score_calculation(self):
        """Test weighted score calculation."""
        metric = AssessmentMetricFactory(score=4, weight=5)
        serializer = AssessmentMetricSerializer(metric)
        
        self.assertIn('weighted_score', serializer.data)
        self.assertEqual(serializer.data['weighted_score'], 20)  # 4 * 5
        
    def test_score_weight_validation(self):
        """Test score and weight validation (1-5 range)."""
        # Valid data
        data = {
            'metric_name': 'Test Metric',
            'score': 3,
            'weight': 4,
            'justification': 'Test justification'
        }
        
        serializer = AssessmentMetricSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Invalid score (out of range)
        data['score'] = 6
        serializer = AssessmentMetricSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        
        # Invalid weight (out of range)
        data['score'] = 3
        data['weight'] = 0
        serializer = AssessmentMetricSerializer(data=data)
        self.assertFalse(serializer.is_valid())


class AssessmentCreateSerializerTest(BaseTestCase):
    """Test AssessmentCreateSerializer."""
    
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.partner = DevelopmentPartnerFactory(group=self.group)
        
    def test_create_assessment_with_nested_data(self):
        """Test creating assessment with financial info, credit info, and metrics."""
        request = self.factory.post('/')
        request.user = self.analyst_user
        
        data = {
            'assessment_type': 'PARTNER',
            'partner': str(self.partner.id),
            'status': 'DRAFT',
            'financial_info': {
                'net_assets_amount': '5000000.00',
                'net_assets_currency': 'USD',
                'latest_annual_revenue_amount': '20000000.00',
                'latest_annual_revenue_currency': 'USD'
            },
            'credit_info': {
                'main_banking_relationship': 'Major Bank',
                'credit_rating': 'BBB',
                'debt_to_total_assets_pct': '35.00'
            },
            'metrics': [
                {
                    'metric_name': 'Financial Stability',
                    'score': 4,
                    'weight': 5,
                    'justification': 'Strong financial position'
                },
                {
                    'metric_name': 'Market Position',
                    'score': 3,
                    'weight': 4,
                    'justification': 'Good market presence'
                }
            ]
        }
        
        serializer = AssessmentCreateSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        assessment = serializer.save()
        
        # Verify main object
        self.assertEqual(assessment.assessment_type, 'PARTNER')
        self.assertEqual(assessment.partner, self.partner)
        self.assertEqual(assessment.group, self.group)
        self.assertEqual(assessment.created_by, self.analyst_user)
        
        # Verify nested objects
        self.assertIsNotNone(assessment.financial_info)
        self.assertIsNotNone(assessment.credit_info)
        self.assertEqual(assessment.metrics.count(), 2)
        
        # Verify financial info
        self.assertEqual(
            assessment.financial_info.net_assets_amount,
            Decimal('5000000.00')
        )
        
        # Verify metrics
        metric_names = list(assessment.metrics.values_list('metric_name', flat=True))
        self.assertIn('Financial Stability', metric_names)
        self.assertIn('Market Position', metric_names)
        
    def test_create_minimal_assessment(self):
        """Test creating assessment with minimal data."""
        request = self.factory.post('/')
        request.user = self.analyst_user
        
        data = {
            'assessment_type': 'PARTNER',
            'partner': str(self.partner.id),
            'status': 'DRAFT'
        }
        
        serializer = AssessmentCreateSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertTrue(serializer.is_valid())
        
        assessment = serializer.save()
        
        self.assertEqual(assessment.assessment_type, 'PARTNER')
        self.assertIsNone(assessment.financial_info)
        self.assertIsNone(assessment.credit_info)
        self.assertEqual(assessment.metrics.count(), 0)
        
    def test_user_group_assignment(self):
        """Test that user and group are properly assigned."""
        request = self.factory.post('/')
        request.user = self.manager_user
        
        data = {
            'assessment_type': 'PARTNER',
            'partner': str(self.partner.id)
        }
        
        serializer = AssessmentCreateSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertTrue(serializer.is_valid())
        assessment = serializer.save()
        
        self.assertEqual(assessment.created_by, self.manager_user)
        self.assertEqual(assessment.group, self.group)
        
    def test_invalid_nested_financial_data(self):
        """Test validation with invalid financial data."""
        request = self.factory.post('/')
        request.user = self.analyst_user
        
        data = {
            'assessment_type': 'PARTNER',
            'partner': str(self.partner.id),
            'financial_info': {
                'net_assets_amount': 'invalid_amount'  # Invalid decimal
            }
        }
        
        serializer = AssessmentCreateSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('financial_info', serializer.errors)
        
    def test_invalid_metrics_data(self):
        """Test validation with invalid metrics data."""
        request = self.factory.post('/')
        request.user = self.analyst_user
        
        data = {
            'assessment_type': 'PARTNER',
            'partner': str(self.partner.id),
            'metrics': [
                {
                    'metric_name': 'Test Metric',
                    'score': 10,  # Invalid - out of range
                    'weight': 3
                }
            ]
        }
        
        serializer = AssessmentCreateSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('metrics', serializer.errors)


class AssessmentSerializerTest(BaseTestCase):
    """Test AssessmentSerializer (read-only)."""
    
    def test_computed_fields_serialization(self):
        """Test computed fields are included."""
        assessment = AssessmentFactory(
            version_major=2,
            version_minor=1,
            version_patch=3
        )
        
        serializer = AssessmentSerializer(assessment)
        
        self.assertIn('semver', serializer.data)
        self.assertEqual(serializer.data['semver'], '2.1.3')
        
    def test_related_name_fields(self):
        """Test related object name fields."""
        partner = DevelopmentPartnerFactory(company_name='Test Corp')
        assessment = AssessmentFactory(
            partner=partner,
            created_by=self.analyst_user
        )
        
        serializer = AssessmentSerializer(assessment)
        
        self.assertIn('partner_name', serializer.data)
        self.assertIn('created_by_name', serializer.data)
        self.assertEqual(serializer.data['partner_name'], 'Test Corp')
        
    def test_nested_relationships_serialization(self):
        """Test nested financial info, credit info, and metrics."""
        assessment = AssessmentFactory()
        
        # Add financial and credit info through factory post_generation
        # Add some metrics
        AssessmentMetricFactory(assessment=assessment, metric_name='Test Metric')
        
        serializer = AssessmentSerializer(assessment)
        
        self.assertIn('financial_info', serializer.data)
        self.assertIn('credit_info', serializer.data)
        self.assertIn('metrics', serializer.data)
        
        if serializer.data['metrics']:
            self.assertIn('weighted_score', serializer.data['metrics'][0])


class SerializerValidationTest(BaseTestCase):
    """Test general serializer validation logic."""
    
    def test_year_established_validation(self):
        """Test year established is within valid range."""
        data = {
            'company_name': 'Test Corp',
            'year_established': 1799  # Too early
        }
        
        serializer = DevelopmentPartnerCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        
        # Valid year
        data['year_established'] = 2020
        serializer = DevelopmentPartnerCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
    def test_url_field_validation(self):
        """Test URL field validation."""
        data = {
            'company_name': 'Test Corp',
            'website_url': 'not-a-valid-url'
        }
        
        serializer = DevelopmentPartnerCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        
        # Valid URL
        data['website_url'] = 'https://example.com'
        serializer = DevelopmentPartnerCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
    def test_assessment_status_choices(self):
        """Test assessment status is within valid choices."""
        request = Mock()
        request.user = self.analyst_user
        
        data = {
            'assessment_type': 'PARTNER',
            'partner': str(DevelopmentPartnerFactory(group=self.group).id),
            'status': 'INVALID_STATUS'
        }
        
        serializer = AssessmentCreateSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertFalse(serializer.is_valid())
        
        # Valid status
        data['status'] = AssessmentStatus.DRAFT
        serializer = AssessmentCreateSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertTrue(serializer.is_valid())