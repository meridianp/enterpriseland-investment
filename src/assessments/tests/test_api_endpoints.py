"""
API Endpoint Tests for CASA Due Diligence Platform - Phase 8

Tests for all API endpoints including authentication, permissions,
filtering, pagination, and business logic.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from datetime import date, timedelta
from decimal import Decimal
import json

from accounts.models import Group, GroupMembership
from assessments.models import (
    Assessment,
    AssessmentMetric,
    DevelopmentPartner,
    PBSAScheme,
    DueDiligenceCase,
    CaseChecklistItem,
)
from assessments.enums import AssessmentStatus, CaseStatus, Priority

User = get_user_model()


class BaseAPITestCase(TestCase):
    """Base test case with common setup for API tests."""
    
    def setUp(self):
        """Set up test data."""
        # Create users
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            role=User.Role.ADMIN
        )
        
        self.analyst_user = User.objects.create_user(
            username='analyst',
            email='analyst@test.com',
            password='testpass123',
            role=User.Role.BUSINESS_ANALYST
        )
        
        self.manager_user = User.objects.create_user(
            username='manager',
            email='manager@test.com',
            password='testpass123',
            role=User.Role.PORTFOLIO_MANAGER
        )
        
        self.viewer_user = User.objects.create_user(
            username='viewer',
            email='viewer@test.com',
            password='testpass123',
            role=User.Role.READ_ONLY
        )
        
        # Create group
        self.group = Group.objects.create(
            name='Test Investment Fund',
            description='Test group for API testing'
        )
        
        # Add users to group
        for user in [self.admin_user, self.analyst_user, self.manager_user, self.viewer_user]:
            GroupMembership.objects.create(user=user, group=self.group)
        
        # Set up API client
        self.client = APIClient()
        
        # Authenticate as analyst by default
        self.client.force_authenticate(user=self.analyst_user)


class PartnerAPITest(BaseAPITestCase):
    """Test partner-related API endpoints."""
    
    def test_create_partner(self):
        """Test creating a new development partner."""
        data = {
            'company_name': 'Test Developer Ltd',
            'trading_name': 'TestDev',
            'headquarter_city': 'London',
            'headquarter_country': 'GB',
            'year_established': 2010,
            'website_url': 'https://testdev.com',
            'number_of_employees': 150,
            'years_of_pbsa_experience': 8,
            'completed_pbsa_schemes': 5,
            'total_pbsa_beds_delivered': 2500,
            'assessment_priority': 'high'
        }
        
        response = self.client.post('/api/partners/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['company_name'], data['company_name'])
        self.assertIn('id', response.data)
        
        # Verify computed fields
        self.assertIn('has_pbsa_experience', response.data)
        self.assertTrue(response.data['has_pbsa_experience'])
        
    def test_list_partners_with_filtering(self):
        """Test listing partners with filters."""
        # Create test partners
        partners = []
        for i in range(5):
            partner = DevelopmentPartner.objects.create(
                company_name=f'Partner {i}',
                headquarter_country='GB' if i % 2 == 0 else 'US',
                number_of_employees=100 + (i * 50),
                years_of_pbsa_experience=i * 2,
                is_active=i != 4,  # Last one inactive
                group=self.group,
                created_by=self.analyst_user
            )
            partners.append(partner)
        
        # Test basic listing
        response = self.client.get('/api/partners/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 4)  # Only active by default
        
        # Test country filter
        response = self.client.get('/api/partners/?country=GB')
        self.assertEqual(response.data['count'], 2)
        
        # Test employee range filter
        response = self.client.get('/api/partners/?min_employees=200')
        self.assertEqual(response.data['count'], 2)
        
        # Test PBSA experience filter
        response = self.client.get('/api/partners/?has_pbsa_experience=true')
        self.assertEqual(response.data['count'], 3)  # Partners with experience > 0
        
        # Test search
        response = self.client.get('/api/partners/?search=Partner 2')
        self.assertEqual(response.data['count'], 1)
        
    def test_partner_permissions(self):
        """Test partner API permissions."""
        data = {'company_name': 'Permission Test Ltd'}
        
        # Viewer cannot create
        self.client.force_authenticate(user=self.viewer_user)
        response = self.client.post('/api/partners/', data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # But can read
        response = self.client.get('/api/partners/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
    def test_update_partner(self):
        """Test updating a partner."""
        partner = DevelopmentPartner.objects.create(
            company_name='Update Test Ltd',
            group=self.group,
            created_by=self.analyst_user
        )
        
        update_data = {
            'company_name': 'Updated Company Ltd',
            'number_of_employees': 200,
            'website_url': 'https://updated.com'
        }
        
        response = self.client.patch(
            f'/api/partners/{partner.id}/',
            update_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['company_name'], update_data['company_name'])
        self.assertEqual(response.data['number_of_employees'], 200)
        
        # Verify last_modified_by is set
        partner.refresh_from_db()
        self.assertEqual(partner.last_modified_by, self.analyst_user)


class SchemeAPITest(BaseAPITestCase):
    """Test scheme-related API endpoints."""
    
    def setUp(self):
        super().setUp()
        # Create a partner for schemes
        self.partner = DevelopmentPartner.objects.create(
            company_name='Scheme Test Developer',
            group=self.group,
            created_by=self.analyst_user
        )
        
    def test_create_scheme(self):
        """Test creating a new PBSA scheme."""
        data = {
            'scheme_name': 'University Quarter PBSA',
            'developer': str(self.partner.id),
            'development_stage': 'PLANNING',
            'location_city': 'Birmingham',
            'location_country': 'GB',
            'total_beds': 850,
            'total_units': 425,
            'site_area_value': '5000',
            'site_area_unit': 'SQ_M',
            'total_development_cost_amount': '65000000',
            'total_development_cost_currency': 'GBP',
            'expected_completion_date': str(date.today() + timedelta(days=730))
        }
        
        response = self.client.post('/api/schemes/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['scheme_name'], data['scheme_name'])
        
        # Verify calculated fields
        self.assertIn('cost_per_bed', response.data)
        self.assertEqual(response.data['cost_per_bed'], '76470.59')  # 65M / 850
        self.assertEqual(response.data['beds_per_unit'], 2.0)
        
    def test_scheme_location_creation(self):
        """Test creating scheme location information."""
        scheme = PBSAScheme.objects.create(
            scheme_name='Location Test Scheme',
            developer=self.partner,
            development_stage='PLANNING',
            location_city='Manchester',
            location_country='GB',
            total_beds=500,
            site_area_value=3000,
            site_area_unit='SQ_M',
            group=self.group,
            created_by=self.analyst_user
        )
        
        location_data = {
            'scheme': str(scheme.id),
            'address': '123 University Road, Manchester',
            'city': 'Manchester',
            'country': 'GB',
            'postcode': 'M1 1AA',
            'location_type': 'campus_adjacent',
            'public_transport_rating': 5,
            'total_student_population': 40000,
            'latitude': '53.4808',
            'longitude': '-2.2426'
        }
        
        response = self.client.post('/api/scheme-locations/', location_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Test adding target universities
        uni_data = {
            'location_info': response.data['id'],
            'university_name': 'University of Manchester',
            'university_type': 'RUSSELL_GROUP',
            'distance_to_campus_km': '0.3',
            'walking_time_minutes': 5,
            'total_student_population': 40000,
            'international_student_pct': '35.0'
        }
        
        response = self.client.post('/api/target-universities/', uni_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify proximity score calculation
        self.assertIn('proximity_score', response.data)
        self.assertGreater(response.data['proximity_score'], 90)  # Very close
        
    def test_scheme_filtering(self):
        """Test scheme filtering options."""
        # Create schemes with different attributes
        for i in range(3):
            PBSAScheme.objects.create(
                scheme_name=f'Filter Test Scheme {i}',
                developer=self.partner,
                development_stage='CONSTRUCTION' if i == 0 else 'PLANNING',
                location_city='London' if i < 2 else 'Manchester',
                location_country='GB',
                total_beds=500 + (i * 100),
                site_area_value=2000,
                site_area_unit='SQ_M',
                group=self.group,
                created_by=self.analyst_user
            )
        
        # Test development stage filter
        response = self.client.get('/api/schemes/?development_stage=CONSTRUCTION')
        self.assertEqual(response.data['count'], 1)
        
        # Test city filter
        response = self.client.get('/api/schemes/?city=London')
        self.assertEqual(response.data['count'], 2)
        
        # Test bed range filter
        response = self.client.get('/api/schemes/?min_beds=600')
        self.assertEqual(response.data['count'], 2)


class AssessmentAPITest(BaseAPITestCase):
    """Test assessment-related API endpoints."""
    
    def setUp(self):
        super().setUp()
        self.partner = DevelopmentPartner.objects.create(
            company_name='Assessment Test Partner',
            group=self.group,
            created_by=self.analyst_user
        )
        
    def test_create_assessment(self):
        """Test creating a new assessment."""
        data = {
            'assessment_name': 'Initial Partner Assessment',
            'assessment_type': 'PARTNER',
            'partner': str(self.partner.id),
            'assessment_purpose': 'Initial due diligence assessment'
        }
        
        response = self.client.post('/api/assessments/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'DRAFT')
        self.assertEqual(response.data['assessor'], self.analyst_user.id)
        
    def test_assessment_metrics(self):
        """Test adding metrics to assessment."""
        assessment = Assessment.objects.create(
            assessment_name='Metric Test Assessment',
            assessment_type='PARTNER',
            partner=self.partner,
            group=self.group,
            assessor=self.analyst_user
        )
        
        metric_data = {
            'assessment': str(assessment.id),
            'metric_name': 'Financial Strength',
            'category': 'FINANCIAL',
            'score': 4,
            'weight': 5,
            'justification': 'Strong balance sheet and cash flow',
            'confidence_level': 'HIGH'
        }
        
        response = self.client.post('/api/assessment-metrics/', metric_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify calculated fields
        self.assertEqual(response.data['weighted_score'], 20)
        self.assertEqual(response.data['max_weighted_score'], 25)
        self.assertEqual(response.data['score_percentage'], 80.0)
        
    def test_assessment_workflow(self):
        """Test assessment workflow transitions."""
        assessment = Assessment.objects.create(
            assessment_name='Workflow Test',
            assessment_type='PARTNER',
            partner=self.partner,
            group=self.group,
            assessor=self.analyst_user
        )
        
        # Add some metrics
        for i in range(3):
            AssessmentMetric.objects.create(
                assessment=assessment,
                metric_name=f'Metric {i}',
                category='FINANCIAL',
                score=4,
                weight=4,
                justification='Test metric'
            )
        
        # Submit for review
        response = self.client.post(f'/api/assessments/{assessment.id}/submit/', {})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify status changed
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, AssessmentStatus.IN_REVIEW)
        self.assertIsNotNone(assessment.submitted_at)
        
        # Manager approves
        self.client.force_authenticate(user=self.manager_user)
        response = self.client.post(f'/api/assessments/{assessment.id}/approve/', {})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify final state
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, AssessmentStatus.APPROVED)
        self.assertEqual(assessment.approver, self.manager_user)
        self.assertIsNotNone(assessment.decision_band)
        
    def test_assessment_templates(self):
        """Test assessment template functionality."""
        # Admin creates template
        self.client.force_authenticate(user=self.admin_user)
        
        template_data = {
            'template_name': 'Standard Partner Assessment',
            'description': 'Standard template for partner assessments',
            'assessment_type': 'PARTNER',
            'is_active': True,
            'version': '1.0'
        }
        
        response = self.client.post('/api/assessment-templates/', template_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        template_id = response.data['id']
        
        # Add metric templates
        metric_template_data = {
            'template': template_id,
            'metric_name': 'Financial Stability',
            'metric_description': 'Assessment of financial health',
            'category': 'FINANCIAL',
            'default_weight': 5,
            'assessment_guidelines': 'Review last 3 years financial statements',
            'is_mandatory': True,
            'display_order': 1
        }
        
        response = self.client.post('/api/metric-templates/', metric_template_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Create assessment from template
        self.client.force_authenticate(user=self.analyst_user)
        
        assessment_data = {
            'assessment_name': 'Partner Assessment from Template',
            'assessment_type': 'PARTNER',
            'partner': str(self.partner.id),
            'use_template': template_id
        }
        
        response = self.client.post('/api/assessments/', assessment_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify metrics were created from template
        response = self.client.get(
            f'/api/assessment-metrics/?assessment={response.data["id"]}'
        )
        self.assertGreater(response.data['count'], 0)


class DueDiligenceCaseAPITest(BaseAPITestCase):
    """Test due diligence case API endpoints."""
    
    def test_create_case(self):
        """Test creating a new due diligence case."""
        data = {
            'case_name': 'New Partner Investment Case',
            'case_type': 'new_partner',
            'priority': 'high',
            'description': 'Evaluating new partnership opportunity',
            'total_investment_amount': '5000000',
            'total_investment_currency': 'GBP',
            'target_irr_percentage': '15.5',
            'target_completion_date': str(date.today() + timedelta(days=60))
        }
        
        response = self.client.post('/api/due-diligence/cases/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify case reference generation
        self.assertIn('case_reference', response.data)
        self.assertTrue(response.data['case_reference'].startswith('CASE-'))
        
        # Verify assigned to creator
        self.assertEqual(response.data['assigned_to'], self.analyst_user.id)
        
    def test_case_status_transitions(self):
        """Test case workflow status transitions."""
        case = DueDiligenceCase.objects.create(
            case_name='Status Test Case',
            case_type='new_partner',
            group=self.group,
            created_by=self.analyst_user,
            assigned_to=self.analyst_user
        )
        
        # Valid transition
        response = self.client.post(
            f'/api/due-diligence/cases/{case.id}/transition_status/',
            {'new_status': 'data_collection', 'notes': 'Starting data collection'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Invalid transition
        response = self.client.post(
            f'/api/due-diligence/cases/{case.id}/transition_status/',
            {'new_status': 'completed'}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_case_checklist(self):
        """Test case checklist functionality."""
        case = DueDiligenceCase.objects.create(
            case_name='Checklist Test Case',
            case_type='new_partner',
            group=self.group,
            created_by=self.analyst_user,
            assigned_to=self.analyst_user
        )
        
        # Add checklist item
        item_data = {
            'case': str(case.id),
            'category': 'financial',
            'item_name': 'Review audited financials',
            'description': 'Review last 3 years of audited financial statements',
            'is_required': True,
            'due_date': str(date.today() + timedelta(days=7))
        }
        
        response = self.client.post('/api/checklist-items/', item_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        item_id = response.data['id']
        
        # Complete checklist item
        response = self.client.post(
            f'/api/checklist-items/{item_id}/complete/',
            {'notes': 'Financials reviewed and approved'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify completion
        response = self.client.get(f'/api/checklist-items/{item_id}/')
        self.assertTrue(response.data['is_completed'])
        self.assertEqual(response.data['completed_by'], self.analyst_user.id)
        
    def test_case_decision_making(self):
        """Test case decision-making process."""
        case = DueDiligenceCase.objects.create(
            case_name='Decision Test Case',
            case_type='new_partner',
            case_status='decision_pending',
            group=self.group,
            created_by=self.analyst_user,
            assigned_to=self.analyst_user
        )
        
        # Manager makes decision
        self.client.force_authenticate(user=self.manager_user)
        
        decision_data = {
            'decision': 'conditional',
            'conditions': [
                'Quarterly financial reporting',
                'Board observer seat',
                'Key man insurance'
            ],
            'notes': 'Approved with standard investment conditions'
        }
        
        response = self.client.post(
            f'/api/due-diligence/cases/{case.id}/make_decision/',
            decision_data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify decision recorded
        case.refresh_from_db()
        self.assertEqual(case.final_decision, 'conditional')
        self.assertEqual(case.case_status, 'approved')
        self.assertEqual(len(case.conditions), 3)
        self.assertEqual(case.decision_maker, self.manager_user)
        
    def test_case_dashboard(self):
        """Test case dashboard analytics."""
        # Create cases with different statuses
        statuses = ['initiated', 'data_collection', 'analysis', 'completed']
        priorities = ['urgent', 'high', 'medium', 'low']
        
        for i, (status_val, priority) in enumerate(zip(statuses, priorities)):
            case = DueDiligenceCase.objects.create(
                case_name=f'Dashboard Case {i}',
                case_type='new_partner',
                case_status=status_val,
                priority=priority,
                group=self.group,
                created_by=self.analyst_user,
                assigned_to=self.analyst_user,
                target_completion_date=date.today() + timedelta(days=30-i*10)
            )
            
            # Make some overdue
            if i == 0:
                case.target_completion_date = date.today() - timedelta(days=5)
                case.save()
        
        response = self.client.get('/api/due-diligence/cases/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        dashboard = response.data
        
        # Verify summary statistics
        self.assertEqual(dashboard['summary']['total_cases'], 4)
        self.assertEqual(dashboard['summary']['overdue_cases'], 1)
        self.assertGreater(dashboard['summary']['active_cases'], 0)
        
        # Verify distributions
        self.assertEqual(len(dashboard['distributions']['by_status']), 4)
        self.assertEqual(len(dashboard['distributions']['by_priority']), 4)
        
        # Verify average metrics
        self.assertIn('avg_completion_time_days', dashboard['metrics'])
        self.assertIn('on_time_completion_rate', dashboard['metrics'])


class AdvancedFeaturesAPITest(BaseAPITestCase):
    """Test advanced features API endpoints."""
    
    def setUp(self):
        super().setUp()
        self.partner = DevelopmentPartner.objects.create(
            company_name='Advanced Features Partner',
            group=self.group,
            created_by=self.analyst_user
        )
        
    def test_regulatory_compliance(self):
        """Test regulatory compliance API."""
        data = {
            'partner': str(self.partner.id),
            'jurisdiction': 'GB',
            'regulatory_framework': 'UK Financial Services',
            'regulatory_body': 'FCA',
            'compliance_category': 'financial',
            'requirement_title': 'Capital Adequacy Requirements',
            'requirement_description': 'Maintain minimum capital ratios',
            'compliance_status': 'compliant',
            'compliance_risk_level': 'LOW',
            'next_review_date': str(date.today() + timedelta(days=90))
        }
        
        response = self.client.post('/api/regulatory-compliance/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Test expiry detection
        self.assertIn('is_expiring_soon', response.data)
        self.assertFalse(response.data['is_expiring_soon'])
        
    def test_performance_metrics(self):
        """Test performance metrics API."""
        data = {
            'partner': str(self.partner.id),
            'metric_name': 'Portfolio Occupancy Rate',
            'metric_category': 'operational',
            'measurement_date': str(date.today()),
            'metric_value': '92.5',
            'metric_unit': '%',
            'target_value': '90.0',
            'benchmark_value': '88.0',
            'data_source': 'Monthly Operations Report',
            'measurement_frequency': 'monthly'
        }
        
        response = self.client.post('/api/performance-metrics/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify calculated fields
        self.assertIn('variance_from_target_pct', response.data)
        self.assertIn('performance_rating', response.data)
        self.assertIn('is_meeting_target', response.data)
        self.assertTrue(response.data['is_meeting_target'])
        
    def test_esg_assessment(self):
        """Test ESG assessment API."""
        data = {
            'partner': str(self.partner.id),
            'assessment_name': 'Annual ESG Review',
            'assessment_framework': 'custom',
            'assessment_period_start': str(date.today() - timedelta(days=365)),
            'assessment_period_end': str(date.today()),
            'environmental_score': 4,
            'social_score': 4,
            'governance_score': 5,
            'carbon_footprint_tonnes': '2500.50',
            'renewable_energy_pct': '45.0',
            'anti_corruption_policies': True
        }
        
        response = self.client.post('/api/esg-assessments/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify ESG calculations
        self.assertIn('overall_esg_score', response.data)
        self.assertIn('esg_rating', response.data)
        
    def test_audit_trail(self):
        """Test audit trail functionality."""
        # Make a change to track
        self.partner.number_of_employees = 200
        self.partner.save()
        
        # Query audit trail
        response = self.client.get(
            f'/api/audit-trails/?entity_type=developmentpartner&entity_id={self.partner.id}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should have at least creation and update events
        self.assertGreaterEqual(response.data['count'], 2)
        
        # Verify audit entry details
        audit_entries = response.data['results']
        latest_entry = audit_entries[0]
        self.assertEqual(latest_entry['action'], 'updated')
        self.assertEqual(latest_entry['field_name'], 'number_of_employees')


class PaginationAndFilteringTest(BaseAPITestCase):
    """Test pagination and filtering across endpoints."""
    
    def test_pagination(self):
        """Test API pagination."""
        # Create many partners
        for i in range(25):
            DevelopmentPartner.objects.create(
                company_name=f'Pagination Test Partner {i}',
                group=self.group,
                created_by=self.analyst_user
            )
        
        # Test default page size
        response = self.client.get('/api/partners/')
        self.assertEqual(len(response.data['results']), 20)  # Default page size
        self.assertIn('next', response.data)
        self.assertIn('count', response.data)
        self.assertEqual(response.data['count'], 25)
        
        # Test custom page size
        response = self.client.get('/api/partners/?page_size=10')
        self.assertEqual(len(response.data['results']), 10)
        
        # Test page navigation
        response = self.client.get('/api/partners/?page=2&page_size=10')
        self.assertEqual(len(response.data['results']), 10)
        
    def test_ordering(self):
        """Test result ordering."""
        # Create partners with different names
        names = ['Zebra Corp', 'Alpha Inc', 'Beta Ltd']
        for name in names:
            DevelopmentPartner.objects.create(
                company_name=name,
                group=self.group,
                created_by=self.analyst_user
            )
        
        # Test ascending order
        response = self.client.get('/api/partners/?ordering=company_name')
        results = response.data['results']
        self.assertEqual(results[0]['company_name'], 'Alpha Inc')
        self.assertEqual(results[-1]['company_name'], 'Zebra Corp')
        
        # Test descending order
        response = self.client.get('/api/partners/?ordering=-company_name')
        results = response.data['results']
        self.assertEqual(results[0]['company_name'], 'Zebra Corp')
        
    def test_complex_filtering(self):
        """Test complex filtering scenarios."""
        # Create cases with various attributes
        today = date.today()
        
        for i in range(5):
            case = DueDiligenceCase.objects.create(
                case_name=f'Complex Filter Case {i}',
                case_type='new_partner' if i < 3 else 'new_scheme',
                case_status='initiated' if i == 0 else 'data_collection',
                priority='urgent' if i == 0 else 'high',
                total_investment_amount=Decimal(str(1000000 * (i + 1))),
                total_investment_currency='GBP',
                target_completion_date=today + timedelta(days=30 + i*10),
                group=self.group,
                created_by=self.analyst_user,
                assigned_to=self.analyst_user if i < 3 else self.manager_user
            )
        
        # Test multiple filters
        response = self.client.get(
            '/api/due-diligence/cases/?case_type=new_partner&priority=high&assigned_to=' +
            str(self.analyst_user.id)
        )
        self.assertEqual(response.data['count'], 2)
        
        # Test date range filter
        response = self.client.get(
            f'/api/due-diligence/cases/?target_completion_date_after={today}&' +
            f'target_completion_date_before={today + timedelta(days=45)}'
        )
        self.assertEqual(response.data['count'], 2)
        
        # Test investment amount range
        response = self.client.get(
            '/api/due-diligence/cases/?min_investment=2000000&max_investment=4000000'
        )
        self.assertEqual(response.data['count'], 2)


class ExportAPITest(BaseAPITestCase):
    """Test data export functionality."""
    
    def test_export_assessments(self):
        """Test exporting assessment data."""
        # Create assessment with metrics
        assessment = Assessment.objects.create(
            assessment_name='Export Test Assessment',
            assessment_type='PARTNER',
            status=AssessmentStatus.APPROVED,
            group=self.group,
            assessor=self.analyst_user
        )
        
        for i in range(3):
            AssessmentMetric.objects.create(
                assessment=assessment,
                metric_name=f'Export Metric {i}',
                category='FINANCIAL',
                score=4,
                weight=4,
                justification='Test metric for export'
            )
        
        # Test CSV export
        response = self.client.get(
            f'/api/assessments/{assessment.id}/export/?format=csv'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        
        # Test Excel export
        response = self.client.get(
            f'/api/assessments/{assessment.id}/export/?format=excel'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('spreadsheet', response['Content-Type'])
        
        # Test PDF export
        response = self.client.get(
            f'/api/assessments/{assessment.id}/export/?format=pdf'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        
    def test_bulk_export(self):
        """Test bulk data export."""
        # Only users with export permission
        self.client.force_authenticate(user=self.viewer_user)
        
        response = self.client.post('/api/due-diligence/cases/bulk_export/', {
            'format': 'csv',
            'case_ids': []
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Manager can export
        self.client.force_authenticate(user=self.manager_user)
        response = self.client.post('/api/due-diligence/cases/bulk_export/', {
            'format': 'csv',
            'case_ids': []
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)