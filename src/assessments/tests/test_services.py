"""
Tests for assessment services.

Tests the business logic layer to ensure proper separation of concerns
and validate that complex operations work correctly.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from decimal import Decimal

from accounts.models import Group, GroupMembership
from assessments.models import Assessment, DevelopmentPartner, PBSAScheme
from assessments.services import AssessmentService, DevelopmentPartnerService, PBSASchemeService
from assessments.services.base import (
    ValidationServiceError, PermissionServiceError, NotFoundServiceError
)

User = get_user_model()


class BaseServiceTestCase(TestCase):
    """Base test case with common setup for service tests."""
    
    def setUp(self):
        """Set up test data."""
        # Create group and users
        self.group = Group.objects.create(name="Test Group")
        
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role=User.Role.ADMIN
        )
        
        self.analyst_user = User.objects.create_user(
            username="analyst",
            email="analyst@example.com",
            password="testpass123",
            role=User.Role.BUSINESS_ANALYST
        )
        
        self.manager_user = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="testpass123",
            role=User.Role.PORTFOLIO_MANAGER
        )
        
        # Add users to group
        GroupMembership.objects.create(user=self.analyst_user, group=self.group)
        GroupMembership.objects.create(user=self.manager_user, group=self.group)
        
        # Create development partner
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name="Test Partner Ltd",
            headquarter_city="London",
            headquarter_country="GB",
            year_established=2020,
            years_of_pbsa_experience=5,
            completed_pbsa_schemes=3
        )
        
        # Create PBSA scheme
        self.scheme = PBSAScheme.objects.create(
            group=self.group,
            scheme_name="Test Scheme",
            developer=self.partner,
            total_beds=100,
            target_location="London",
            total_investment=Decimal('5000000.00')
        )


class AssessmentServiceTests(BaseServiceTestCase):
    """Test AssessmentService business logic."""
    
    def test_create_assessment_success(self):
        """Test successful assessment creation."""
        service = AssessmentService(user=self.analyst_user, group=self.group)
        
        assessment = service.create_assessment(
            development_partner_id=str(self.partner.id),
            pbsa_scheme_id=str(self.scheme.id),
            assessment_type=Assessment.AssessmentType.FULL
        )
        
        self.assertIsInstance(assessment, Assessment)
        self.assertEqual(assessment.development_partner, self.partner)
        self.assertEqual(assessment.pbsa_scheme, self.scheme)
        self.assertEqual(assessment.status, Assessment.AssessmentStatus.DRAFT)
        self.assertEqual(assessment.created_by, self.analyst_user)
    
    def test_create_assessment_validation_error(self):
        """Test assessment creation with validation errors."""
        service = AssessmentService(user=self.analyst_user, group=self.group)
        
        # Test with partner too young (established this year)
        young_partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name="Young Partner",
            headquarter_city="London",
            headquarter_country="GB",
            year_established=2024  # Current year
        )
        
        with self.assertRaises(ValidationServiceError) as context:
            service.create_assessment(
                development_partner_id=str(young_partner.id),
                pbsa_scheme_id=str(self.scheme.id),
                assessment_type=Assessment.AssessmentType.FULL
            )
        
        self.assertIn("established for at least 1 year", str(context.exception))
    
    def test_create_assessment_not_found_error(self):
        """Test assessment creation with non-existent partner."""
        service = AssessmentService(user=self.analyst_user, group=self.group)
        
        with self.assertRaises(NotFoundServiceError):
            service.create_assessment(
                development_partner_id="00000000-0000-0000-0000-000000000000",
                pbsa_scheme_id=str(self.scheme.id),
                assessment_type=Assessment.AssessmentType.FULL
            )
    
    def test_submit_assessment_success(self):
        """Test successful assessment submission."""
        # Create assessment
        assessment = Assessment.objects.create(
            group=self.group,
            development_partner=self.partner,
            pbsa_scheme=self.scheme,
            assessment_type=Assessment.AssessmentType.FULL,
            status=Assessment.AssessmentStatus.DRAFT,
            created_by=self.analyst_user
        )
        
        service = AssessmentService(user=self.analyst_user, group=self.group)
        updated_assessment = service.submit_assessment(str(assessment.id))
        
        self.assertEqual(updated_assessment.status, Assessment.AssessmentStatus.IN_REVIEW)
        self.assertIsNotNone(updated_assessment.submitted_at)
    
    def test_submit_assessment_wrong_status(self):
        """Test submission of non-draft assessment."""
        # Create assessment in review
        assessment = Assessment.objects.create(
            group=self.group,
            development_partner=self.partner,
            pbsa_scheme=self.scheme,
            assessment_type=Assessment.AssessmentType.FULL,
            status=Assessment.AssessmentStatus.IN_REVIEW,
            created_by=self.analyst_user
        )
        
        service = AssessmentService(user=self.analyst_user, group=self.group)
        
        with self.assertRaises(ValidationServiceError) as context:
            service.submit_assessment(str(assessment.id))
        
        self.assertIn("Only draft assessments can be submitted", str(context.exception))
    
    def test_approve_assessment_success(self):
        """Test successful assessment approval."""
        # Create assessment in review
        assessment = Assessment.objects.create(
            group=self.group,
            development_partner=self.partner,
            pbsa_scheme=self.scheme,
            assessment_type=Assessment.AssessmentType.FULL,
            status=Assessment.AssessmentStatus.IN_REVIEW,
            created_by=self.analyst_user
        )
        
        service = AssessmentService(user=self.manager_user, group=self.group)
        updated_assessment = service.approve_assessment(
            str(assessment.id),
            Assessment.AssessmentDecision.ACCEPTABLE,
            "Looks good"
        )
        
        self.assertEqual(updated_assessment.status, Assessment.AssessmentStatus.APPROVED)
        self.assertEqual(updated_assessment.decision, Assessment.AssessmentDecision.ACCEPTABLE)
        self.assertEqual(updated_assessment.approved_by, self.manager_user)
        self.assertEqual(updated_assessment.approval_comments, "Looks good")
    
    def test_approve_assessment_permission_denied(self):
        """Test approval by user without permission."""
        # Create assessment in review
        assessment = Assessment.objects.create(
            group=self.group,
            development_partner=self.partner,
            pbsa_scheme=self.scheme,
            assessment_type=Assessment.AssessmentType.FULL,
            status=Assessment.AssessmentStatus.IN_REVIEW,
            created_by=self.analyst_user
        )
        
        # Try to approve with analyst user (no approval authority)
        service = AssessmentService(user=self.analyst_user, group=self.group)
        
        with self.assertRaises(PermissionServiceError) as context:
            service.approve_assessment(
                str(assessment.id),
                Assessment.AssessmentDecision.ACCEPTABLE
            )
        
        self.assertIn("approval authority", str(context.exception))
    
    def test_calculate_assessment_score(self):
        """Test assessment score calculation."""
        # Create assessment
        assessment = Assessment.objects.create(
            group=self.group,
            development_partner=self.partner,
            pbsa_scheme=self.scheme,
            assessment_type=Assessment.AssessmentType.FULL,
            status=Assessment.AssessmentStatus.DRAFT,
            created_by=self.analyst_user
        )
        
        service = AssessmentService(user=self.analyst_user, group=self.group)
        scores = service.calculate_assessment_score(str(assessment.id))
        
        # Check score structure
        expected_keys = [
            'financial_score', 'credit_score', 'experience_score', 
            'scheme_score', 'overall_score', 'risk_level', 'recommendation'
        ]
        for key in expected_keys:
            self.assertIn(key, scores)
        
        # Check score ranges
        self.assertGreaterEqual(scores['overall_score'], 0)
        self.assertLessEqual(scores['overall_score'], 100)
        self.assertIn(scores['risk_level'], ['LOW', 'MEDIUM', 'HIGH'])
    
    def test_get_assessment_analytics(self):
        """Test assessment analytics calculation."""
        # Create multiple assessments
        for i in range(5):
            Assessment.objects.create(
                group=self.group,
                development_partner=self.partner,
                pbsa_scheme=self.scheme,
                assessment_type=Assessment.AssessmentType.FULL,
                status=Assessment.AssessmentStatus.APPROVED if i < 3 else Assessment.AssessmentStatus.REJECTED,
                created_by=self.analyst_user
            )
        
        service = AssessmentService(user=self.analyst_user, group=self.group)
        analytics = service.get_assessment_analytics()
        
        # Check analytics structure
        expected_keys = [
            'total_assessments', 'recent_assessments', 'status_breakdown',
            'decision_breakdown', 'completion_rate'
        ]
        for key in expected_keys:
            self.assertIn(key, analytics)
        
        self.assertEqual(analytics['total_assessments'], 5)
        self.assertGreaterEqual(analytics['completion_rate'], 0)


class DevelopmentPartnerServiceTests(BaseServiceTestCase):
    """Test DevelopmentPartnerService business logic."""
    
    def test_create_partner_success(self):
        """Test successful partner creation."""
        service = DevelopmentPartnerService(user=self.analyst_user, group=self.group)
        
        partner_data = {
            'company_name': 'New Partner Ltd',
            'headquarter_city': 'Manchester',
            'headquarter_country': 'GB',
            'year_established': 2021,
            'number_of_employees': 50
        }
        
        partner = service.create_partner(partner_data)
        
        self.assertIsInstance(partner, DevelopmentPartner)
        self.assertEqual(partner.company_name, 'New Partner Ltd')
        self.assertEqual(partner.group, self.group)
    
    def test_create_partner_validation_error(self):
        """Test partner creation with validation errors."""
        service = DevelopmentPartnerService(user=self.analyst_user, group=self.group)
        
        # Test with missing required field
        partner_data = {
            'headquarter_city': 'Manchester',
            'headquarter_country': 'GB',
        }
        
        with self.assertRaises(ValidationServiceError) as context:
            service.create_partner(partner_data)
        
        self.assertIn("company_name", str(context.exception))
    
    def test_get_partner_performance(self):
        """Test partner performance metrics calculation."""
        # Create some assessments for the partner
        for i in range(3):
            Assessment.objects.create(
                group=self.group,
                development_partner=self.partner,
                pbsa_scheme=self.scheme,
                assessment_type=Assessment.AssessmentType.FULL,
                status=Assessment.AssessmentStatus.APPROVED,
                created_by=self.analyst_user
            )
        
        service = DevelopmentPartnerService(user=self.analyst_user, group=self.group)
        performance = service.get_partner_performance(str(self.partner.id))
        
        # Check performance structure
        expected_keys = [
            'basic_info', 'assessment_metrics', 'scheme_metrics',
            'financial_metrics', 'risk_assessment', 'performance_trends'
        ]
        for key in expected_keys:
            self.assertIn(key, performance)
        
        # Check assessment metrics
        self.assertEqual(performance['assessment_metrics']['total_assessments'], 3)
        self.assertEqual(performance['assessment_metrics']['approved_assessments'], 3)
    
    def test_get_partner_recommendations(self):
        """Test partner recommendations generation."""
        # Create partner with limited experience
        young_partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name="Young Partner",
            headquarter_city="London",
            headquarter_country="GB",
            year_established=2023,
            years_of_pbsa_experience=1,
            completed_pbsa_schemes=0
        )
        
        service = DevelopmentPartnerService(user=self.analyst_user, group=self.group)
        recommendations = service.get_partner_recommendations(str(young_partner.id))
        
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)
        
        # Check recommendation structure
        for rec in recommendations:
            self.assertIn('type', rec)
            self.assertIn('priority', rec)
            self.assertIn('title', rec)
            self.assertIn('description', rec)
            self.assertIn('action_items', rec)


class PBSASchemeServiceTests(BaseServiceTestCase):
    """Test PBSASchemeService business logic."""
    
    def test_create_scheme_success(self):
        """Test successful scheme creation."""
        service = PBSASchemeService(user=self.analyst_user, group=self.group)
        
        scheme_data = {
            'scheme_name': 'New Test Scheme',
            'developer': str(self.partner.id),
            'total_beds': 150,
            'target_location': 'Birmingham',
            'total_investment': Decimal('7500000.00')
        }
        
        scheme = service.create_scheme(scheme_data)
        
        self.assertIsInstance(scheme, PBSAScheme)
        self.assertEqual(scheme.scheme_name, 'New Test Scheme')
        self.assertEqual(scheme.developer, self.partner)
        self.assertEqual(scheme.group, self.group)
    
    def test_create_scheme_validation_error(self):
        """Test scheme creation with validation errors."""
        service = PBSASchemeService(user=self.analyst_user, group=self.group)
        
        # Test with unreasonably low investment
        scheme_data = {
            'scheme_name': 'Bad Scheme',
            'developer': str(self.partner.id),
            'total_beds': 100,
            'target_location': 'London',
            'total_investment': Decimal('5000.00')  # Too low
        }
        
        with self.assertRaises(ValidationServiceError) as context:
            service.create_scheme(scheme_data)
        
        self.assertIn("at least £10,000", str(context.exception))
    
    def test_get_scheme_analysis(self):
        """Test comprehensive scheme analysis."""
        service = PBSASchemeService(user=self.analyst_user, group=self.group)
        analysis = service.get_scheme_analysis(str(self.scheme.id))
        
        # Check analysis structure
        expected_keys = [
            'basic_info', 'financial_analysis', 'market_analysis',
            'risk_assessment', 'benchmarking', 'assessment_history'
        ]
        for key in expected_keys:
            self.assertIn(key, analysis)
        
        # Check basic info
        self.assertEqual(analysis['basic_info']['scheme_name'], self.scheme.scheme_name)
        self.assertEqual(analysis['basic_info']['total_beds'], self.scheme.total_beds)
    
    def test_calculate_scheme_metrics(self):
        """Test scheme metrics calculation."""
        service = PBSASchemeService(user=self.analyst_user, group=self.group)
        metrics = service.calculate_scheme_metrics(str(self.scheme.id))
        
        # Check metrics structure
        expected_keys = [
            'financial_metrics', 'operational_metrics', 
            'market_metrics', 'performance_score'
        ]
        for key in expected_keys:
            self.assertIn(key, metrics)
        
        # Check performance score range
        self.assertGreaterEqual(metrics['performance_score'], 0)
        self.assertLessEqual(metrics['performance_score'], 100)
    
    def test_get_scheme_recommendations(self):
        """Test scheme recommendations generation."""
        # Create scheme with high cost per bed
        expensive_scheme = PBSAScheme.objects.create(
            group=self.group,
            scheme_name="Expensive Scheme",
            developer=self.partner,
            total_beds=50,  # Small scheme
            target_location="London",
            total_investment=Decimal('10000000.00')  # High investment
        )
        
        service = PBSASchemeService(user=self.analyst_user, group=self.group)
        recommendations = service.get_scheme_recommendations(str(expensive_scheme.id))
        
        self.assertIsInstance(recommendations, list)
        
        # Should have recommendations for small scheme and high cost
        rec_types = [rec['type'] for rec in recommendations]
        self.assertIn('scale', rec_types)  # Small scheme recommendation
    
    def test_search_schemes(self):
        """Test scheme search functionality."""
        # Create additional schemes
        for i in range(3):
            PBSAScheme.objects.create(
                group=self.group,
                scheme_name=f"Search Test Scheme {i}",
                developer=self.partner,
                total_beds=100 + i * 50,
                target_location="Test Location",
                total_investment=Decimal('5000000.00')
            )
        
        service = PBSASchemeService(user=self.analyst_user, group=self.group)
        
        # Test search by name
        results = service.search_schemes(search_term="Search Test")
        self.assertEqual(results['total_count'], 3)
        self.assertGreater(len(results['schemes']), 0)
        
        # Test filter by beds
        filtered_results = service.search_schemes(
            filters={'min_beds': 150, 'max_beds': 200}
        )
        self.assertGreaterEqual(filtered_results['total_count'], 1)