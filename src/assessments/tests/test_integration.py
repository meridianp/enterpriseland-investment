"""
Integration Tests for CASA Due Diligence Platform - Phase 8

Comprehensive integration tests covering the complete workflow
from case creation through to final decision.
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from rest_framework.test import APIClient
from rest_framework import status
from datetime import date, timedelta
from decimal import Decimal
import json

from accounts.models import Group, GroupMembership
from assessments.models import (
    DevelopmentPartner,
    PBSAScheme,
    Assessment,
    AssessmentMetric,
    DueDiligenceCase,
    CaseChecklistItem,
    CaseTimeline,
)
from assessments.partner_models import OfficeLocation, FinancialPartner, KeyShareholder
from assessments.scheme_models import SchemeLocationInformation, SchemeSiteInformation, TargetUniversity
from assessments.advanced_models import RegulatoryCompliance, PerformanceMetric, ESGAssessment
from assessments.enums import AssessmentStatus, CaseStatus, Priority, RiskLevel

User = get_user_model()


class CompleteDueDiligenceWorkflowTest(TransactionTestCase):
    """Test the complete due diligence workflow from start to finish."""
    
    def setUp(self):
        """Set up test data."""
        # Create users with different roles
        self.analyst_user = User.objects.create_user(
            username='analyst',
            email='analyst@test.com',
            password='testpass123',
            role=User.Role.BUSINESS_ANALYST,
            first_name='Test',
            last_name='Analyst'
        )
        
        self.manager_user = User.objects.create_user(
            username='manager',
            email='manager@test.com',
            password='testpass123',
            role=User.Role.PORTFOLIO_MANAGER,
            first_name='Test',
            last_name='Manager'
        )
        
        # Create group and memberships
        self.group = Group.objects.create(
            name='Test Investment Fund',
            description='Test group for integration testing'
        )
        
        GroupMembership.objects.create(
            user=self.analyst_user,
            group=self.group,
            is_admin=False
        )
        
        GroupMembership.objects.create(
            user=self.manager_user,
            group=self.group,
            is_admin=True
        )
        
        # Set up API client
        self.client = APIClient()
        
    def test_complete_partner_assessment_workflow(self):
        """Test the complete workflow for partner assessment."""
        # Step 1: Analyst creates a development partner
        self.client.force_authenticate(user=self.analyst_user)
        
        partner_data = {
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
        
        response = self.client.post('/api/partners/', partner_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        partner_id = response.data['id']
        
        # Add office locations
        office_data = {
            'partner': partner_id,
            'city': 'Manchester',
            'country': 'GB',
            'is_headquarters': False,
            'employee_count': 50
        }
        response = self.client.post('/api/office-locations/', office_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Add financial partners
        financial_partner_data = {
            'partner': partner_id,
            'name': 'Test Capital Partners',
            'relationship_type': 'equity',
            'commitment_amount': '50000000',
            'commitment_currency': 'GBP',
            'is_active': True
        }
        response = self.client.post('/api/financial-partners/', financial_partner_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Step 2: Create a due diligence case
        case_data = {
            'case_name': 'Test Developer Partnership Assessment',
            'case_type': 'new_partner',
            'partner': partner_id,
            'priority': 'high',
            'description': 'Initial partnership assessment for Test Developer Ltd',
            'total_investment_amount': '10000000',
            'total_investment_currency': 'GBP',
            'target_irr_percentage': '15.5',
            'target_completion_date': str(date.today() + timedelta(days=90))
        }
        
        response = self.client.post('/api/due-diligence/cases/', case_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        case_id = response.data['id']
        case_reference = response.data['case_reference']
        
        # Verify case reference format
        self.assertTrue(case_reference.startswith('CASE-'))
        
        # Step 3: Create assessment
        assessment_data = {
            'assessment_name': f'Partner Assessment - {partner_data["company_name"]}',
            'assessment_type': 'PARTNER',
            'partner': partner_id,
            'assessment_purpose': 'Initial partner due diligence'
        }
        
        response = self.client.post('/api/assessments/', assessment_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        assessment_id = response.data['id']
        
        # Add assessment to case
        response = self.client.post(
            f'/api/due-diligence/cases/{case_id}/add_assessment/',
            {'assessment_id': assessment_id}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 4: Add assessment metrics
        metrics = [
            {
                'assessment': assessment_id,
                'metric_name': 'Financial Strength',
                'category': 'FINANCIAL',
                'score': 4,
                'weight': 5,
                'justification': 'Strong financial position with diverse funding sources'
            },
            {
                'assessment': assessment_id,
                'metric_name': 'PBSA Experience',
                'category': 'TRACK_RECORD',
                'score': 5,
                'weight': 4,
                'justification': 'Extensive PBSA portfolio with successful projects'
            },
            {
                'assessment': assessment_id,
                'metric_name': 'Team Capability',
                'category': 'OPERATIONAL',
                'score': 4,
                'weight': 4,
                'justification': 'Experienced team with relevant expertise'
            }
        ]
        
        for metric in metrics:
            response = self.client.post('/api/assessment-metrics/', metric)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Step 5: Submit assessment for review
        response = self.client.post(
            f'/api/assessments/{assessment_id}/submit/',
            {}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 6: Manager reviews and approves assessment
        self.client.force_authenticate(user=self.manager_user)
        
        response = self.client.post(
            f'/api/assessments/{assessment_id}/approve/',
            {}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify assessment status
        response = self.client.get(f'/api/assessments/{assessment_id}/')
        self.assertEqual(response.data['status'], 'APPROVED')
        self.assertIsNotNone(response.data['total_weighted_score'])
        
        # Step 7: Add regulatory compliance check
        compliance_data = {
            'partner': partner_id,
            'jurisdiction': 'GB',
            'regulatory_framework': 'UK Financial Services',
            'regulatory_body': 'FCA',
            'compliance_category': 'financial',
            'requirement_title': 'AML/KYC Compliance',
            'requirement_description': 'Anti-money laundering and know your customer requirements',
            'compliance_status': 'compliant',
            'compliance_risk_level': 'LOW'
        }
        
        response = self.client.post('/api/regulatory-compliance/', compliance_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Step 8: Add ESG assessment
        esg_data = {
            'partner': partner_id,
            'assessment_name': 'Initial ESG Assessment',
            'assessment_framework': 'custom',
            'assessment_period_start': str(date.today() - timedelta(days=365)),
            'assessment_period_end': str(date.today()),
            'environmental_score': 4,
            'social_score': 4,
            'governance_score': 5,
            'carbon_footprint_tonnes': '1250.50',
            'renewable_energy_pct': '35.0',
            'local_employment_pct': '75.0',
            'board_diversity_pct': '40.0',
            'anti_corruption_policies': True
        }
        
        response = self.client.post('/api/esg-assessments/', esg_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Step 9: Complete case checklist
        response = self.client.get(f'/api/checklist-items/by_case/?case_id={case_id}')
        checklist_items = response.data['checklist']
        
        # Complete some checklist items
        for category, items in checklist_items.items():
            for item in items[:2]:  # Complete first 2 items in each category
                response = self.client.post(
                    f'/api/checklist-items/{item["id"]}/complete/',
                    {'notes': 'Completed during assessment'}
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 10: Transition case through workflow
        transitions = [
            ('data_collection', 'Moving to data collection phase'),
            ('analysis', 'Data collection complete, beginning analysis'),
            ('review', 'Analysis complete, ready for review'),
            ('decision_pending', 'Review complete, awaiting decision')
        ]
        
        for new_status, notes in transitions:
            response = self.client.post(
                f'/api/due-diligence/cases/{case_id}/transition_status/',
                {
                    'new_status': new_status,
                    'notes': notes
                }
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 11: Make final decision
        decision_data = {
            'decision': 'conditional',
            'conditions': [
                'Annual financial reporting required',
                'ESG improvement plan to be submitted within 90 days',
                'Board observer rights'
            ],
            'notes': 'Strong partner with good track record. Proceed with standard conditions.'
        }
        
        response = self.client.post(
            f'/api/due-diligence/cases/{case_id}/make_decision/',
            decision_data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 12: Verify final case state
        response = self.client.get(f'/api/due-diligence/cases/{case_id}/')
        final_case = response.data
        
        self.assertEqual(final_case['case_status'], 'approved')
        self.assertEqual(final_case['final_decision'], 'conditional')
        self.assertEqual(len(final_case['conditions']), 3)
        self.assertIsNotNone(final_case['decision_date'])
        
        # Verify timeline
        response = self.client.get(f'/api/case-timeline/?case={case_id}')
        timeline_events = response.data['results']
        
        # Should have events for status changes and decision
        event_types = [event['event_type'] for event in timeline_events]
        self.assertIn('status_change', event_types)
        self.assertIn('decision_made', event_types)
        
        # Verify analytics
        response = self.client.get('/api/due-diligence/cases/dashboard/')
        dashboard = response.data
        
        self.assertGreater(dashboard['summary']['total_cases'], 0)
        self.assertIn('approved', dashboard['distributions']['by_status'])
        
    def test_scheme_assessment_with_multiple_assessments(self):
        """Test scheme assessment with both partner and scheme assessments."""
        self.client.force_authenticate(user=self.analyst_user)
        
        # Create partner first
        partner = DevelopmentPartner.objects.create(
            company_name='Multi-Assessment Developer',
            group=self.group,
            created_by=self.analyst_user,
            number_of_employees=200,
            years_of_pbsa_experience=10
        )
        
        # Create scheme
        scheme_data = {
            'scheme_name': 'University Quarter PBSA',
            'developer': str(partner.id),
            'development_stage': 'PLANNING',
            'location_city': 'Birmingham',
            'location_country': 'GB',
            'total_beds': 850,
            'total_units': 425,
            'site_area_value': '5000',
            'site_area_unit': 'SQ_M',
            'total_development_cost_amount': '65000000',
            'total_development_cost_currency': 'GBP'
        }
        
        response = self.client.post('/api/schemes/', scheme_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        scheme_id = response.data['id']
        
        # Add location information
        location_data = {
            'scheme': scheme_id,
            'address': '123 University Street, Birmingham',
            'city': 'Birmingham',
            'country': 'GB',
            'postcode': 'B1 1AA',
            'location_type': 'campus_adjacent',
            'public_transport_rating': 5,
            'total_student_population': 45000
        }
        
        response = self.client.post('/api/scheme-locations/', location_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        location_id = response.data['id']
        
        # Add target universities
        uni_data = {
            'location_info': location_id,
            'university_name': 'University of Birmingham',
            'university_type': 'RUSSELL_GROUP',
            'distance_to_campus_km': '0.5',
            'walking_time_minutes': 10,
            'total_student_population': 35000,
            'international_student_pct': '28.5'
        }
        
        response = self.client.post('/api/target-universities/', uni_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Create combined case
        case_data = {
            'case_name': 'University Quarter Development Assessment',
            'case_type': 'new_scheme',
            'partner': str(partner.id),
            'scheme': scheme_id,
            'priority': 'urgent',
            'total_investment_amount': '15000000',
            'total_investment_currency': 'GBP',
            'target_irr_percentage': '18.0'
        }
        
        response = self.client.post('/api/due-diligence/cases/', case_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        case_id = response.data['id']
        
        # Create both partner and scheme assessments
        assessments = []
        
        # Partner assessment
        response = self.client.post('/api/assessments/', {
            'assessment_name': 'Partner Track Record Review',
            'assessment_type': 'PARTNER',
            'partner': str(partner.id)
        })
        assessments.append(response.data['id'])
        
        # Scheme assessment
        response = self.client.post('/api/assessments/', {
            'assessment_name': 'Scheme Feasibility Assessment',
            'assessment_type': 'SCHEME',
            'scheme': scheme_id
        })
        assessments.append(response.data['id'])
        
        # Add both assessments to case
        for assessment_id in assessments:
            response = self.client.post(
                f'/api/due-diligence/cases/{case_id}/add_assessment/',
                {'assessment_id': assessment_id}
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify case has multiple assessments
        response = self.client.get(f'/api/due-diligence/cases/{case_id}/')
        self.assertEqual(len(response.data['assessments']), 2)
        
        # Complete workflow quickly
        response = self.client.post(
            f'/api/due-diligence/cases/{case_id}/transition_status/',
            {'new_status': 'decision_pending'}
        )
        
        # Make decision
        response = self.client.post(
            f'/api/due-diligence/cases/{case_id}/make_decision/',
            {'decision': 'proceed', 'notes': 'Excellent opportunity'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
    def test_concurrent_user_workflow(self):
        """Test workflow with multiple users working concurrently."""
        # Create additional users
        analyst2 = User.objects.create_user(
            username='analyst2',
            email='analyst2@test.com',
            password='testpass123',
            role=User.Role.BUSINESS_ANALYST
        )
        GroupMembership.objects.create(user=analyst2, group=self.group)
        
        # User 1 creates a case
        self.client.force_authenticate(user=self.analyst_user)
        case_response = self.client.post('/api/due-diligence/cases/', {
            'case_name': 'Concurrent Test Case',
            'case_type': 'new_partner',
            'priority': 'high'
        })
        case_id = case_response.data['id']
        
        # User 2 adds checklist items
        self.client.force_authenticate(user=analyst2)
        checklist_response = self.client.post('/api/checklist-items/', {
            'case': case_id,
            'category': 'financial',
            'item_name': 'Review financial statements',
            'is_required': True
        })
        self.assertEqual(checklist_response.status_code, status.HTTP_201_CREATED)
        
        # User 1 transitions status
        self.client.force_authenticate(user=self.analyst_user)
        transition_response = self.client.post(
            f'/api/due-diligence/cases/{case_id}/transition_status/',
            {'new_status': 'data_collection'}
        )
        self.assertEqual(transition_response.status_code, status.HTTP_200_OK)
        
        # Verify both actions in timeline
        timeline_response = self.client.get(f'/api/case-timeline/?case={case_id}')
        events = timeline_response.data['results']
        
        creators = [event['created_by'] for event in events]
        self.assertIn(self.analyst_user.id, creators)
        self.assertIn(analyst2.id, creators)
        
    def test_performance_tracking_over_time(self):
        """Test performance metric tracking and trend analysis."""
        self.client.force_authenticate(user=self.analyst_user)
        
        # Create partner
        partner = DevelopmentPartner.objects.create(
            company_name='Performance Test Developer',
            group=self.group,
            created_by=self.analyst_user
        )
        
        # Add performance metrics over time
        base_date = date.today() - timedelta(days=365)
        metrics_data = []
        
        for month in range(12):
            metric_date = base_date + timedelta(days=30 * month)
            occupancy = 85 + (month * 1.2)  # Improving occupancy
            
            metrics_data.append({
                'partner': str(partner.id),
                'metric_name': 'Portfolio Occupancy Rate',
                'metric_category': 'operational',
                'measurement_date': str(metric_date),
                'metric_value': str(occupancy),
                'metric_unit': '%',
                'target_value': '92.0',
                'benchmark_value': '90.0',
                'data_source': 'Monthly Operations Report',
                'measurement_frequency': 'monthly'
            })
        
        # Create metrics
        for metric_data in metrics_data:
            response = self.client.post('/api/performance-metrics/', metric_data)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Query performance trend
        response = self.client.get(
            f'/api/performance-metrics/?partner={partner.id}&metric_name=Portfolio Occupancy Rate'
        )
        metrics = response.data['results']
        
        # Verify improving trend
        self.assertGreater(len(metrics), 10)
        first_value = float(metrics[-1]['metric_value'])  # Oldest
        last_value = float(metrics[0]['metric_value'])    # Newest
        self.assertGreater(last_value, first_value)
        
        # Check if target is met
        latest_metric = metrics[0]
        self.assertGreater(
            float(latest_metric['metric_value']),
            float(latest_metric['target_value'])
        )
        
    def test_error_handling_and_validation(self):
        """Test error handling and validation throughout the workflow."""
        self.client.force_authenticate(user=self.analyst_user)
        
        # Test invalid case creation
        response = self.client.post('/api/due-diligence/cases/', {
            'case_name': '',  # Empty name
            'case_type': 'invalid_type',
            'priority': 'super_urgent'  # Invalid priority
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test invalid status transition
        case = DueDiligenceCase.objects.create(
            case_name='Test Case',
            case_type='new_partner',
            case_status='initiated',
            group=self.group,
            created_by=self.analyst_user,
            assigned_to=self.analyst_user
        )
        
        # Try invalid transition (initiated -> approved)
        response = self.client.post(
            f'/api/due-diligence/cases/{case.id}/transition_status/',
            {'new_status': 'approved'}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test decision without proper status
        response = self.client.post(
            f'/api/due-diligence/cases/{case.id}/make_decision/',
            {'decision': 'proceed'}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test assessment metric validation
        assessment = Assessment.objects.create(
            assessment_name='Test Assessment',
            assessment_type='PARTNER',
            group=self.group,
            assessor=self.analyst_user
        )
        
        response = self.client.post('/api/assessment-metrics/', {
            'assessment': str(assessment.id),
            'metric_name': 'Test Metric',
            'category': 'FINANCIAL',
            'score': 6,  # Invalid score (>5)
            'weight': 0,  # Invalid weight (<1)
            'justification': 'Test'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_dashboard_analytics(self):
        """Test dashboard analytics and reporting."""
        self.client.force_authenticate(user=self.manager_user)
        
        # Create multiple cases with different statuses
        statuses = ['initiated', 'data_collection', 'analysis', 'review', 'completed']
        for i, status_value in enumerate(statuses):
            DueDiligenceCase.objects.create(
                case_name=f'Dashboard Test Case {i}',
                case_type='new_partner',
                case_status=status_value,
                priority='high' if i % 2 == 0 else 'medium',
                group=self.group,
                created_by=self.analyst_user,
                assigned_to=self.analyst_user,
                target_completion_date=date.today() + timedelta(days=30 - (i * 10))
            )
        
        # Get dashboard data
        response = self.client.get('/api/due-diligence/cases/dashboard/')
        dashboard = response.data
        
        # Verify summary statistics
        self.assertEqual(dashboard['summary']['total_cases'], 5)
        self.assertGreater(dashboard['summary']['active_cases'], 0)
        
        # Verify status distribution
        status_dist = dashboard['distributions']['by_status']
        self.assertEqual(len(status_dist), 5)
        
        # Verify priority distribution
        priority_dist = dashboard['distributions']['by_priority']
        self.assertIn('high', priority_dist)
        self.assertIn('medium', priority_dist)
        
        # Test filtered dashboard
        response = self.client.get(
            '/api/due-diligence/cases/dashboard/?priority=high'
        )
        filtered_dashboard = response.data
        self.assertLess(
            filtered_dashboard['summary']['total_cases'],
            dashboard['summary']['total_cases']
        )


class APIPermissionTest(TestCase):
    """Test API permissions and access control."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(name='Test Group')
        
        # Create users with different roles
        self.users = {
            'admin': User.objects.create_user(
                username='admin',
                email='admin@test.com',
                password='test',
                role=User.Role.ADMIN
            ),
            'analyst': User.objects.create_user(
                username='analyst',
                email='analyst@test.com',
                password='test',
                role=User.Role.BUSINESS_ANALYST
            ),
            'viewer': User.objects.create_user(
                username='viewer',
                email='viewer@test.com',
                password='test',
                role=User.Role.READ_ONLY
            ),
            'external': User.objects.create_user(
                username='external',
                email='external@test.com',
                password='test',
                role=User.Role.EXTERNAL_PARTNER
            )
        }
        
        # Add all users to group except external
        for role, user in self.users.items():
            if role != 'external':
                GroupMembership.objects.create(user=user, group=self.group)
        
        self.client = APIClient()
        
    def test_case_creation_permissions(self):
        """Test that only authorized users can create cases."""
        case_data = {
            'case_name': 'Permission Test Case',
            'case_type': 'new_partner',
            'priority': 'medium'
        }
        
        # Admin should succeed
        self.client.force_authenticate(user=self.users['admin'])
        response = self.client.post('/api/due-diligence/cases/', case_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Analyst should succeed
        self.client.force_authenticate(user=self.users['analyst'])
        response = self.client.post('/api/due-diligence/cases/', case_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Viewer should fail
        self.client.force_authenticate(user=self.users['viewer'])
        response = self.client.post('/api/due-diligence/cases/', case_data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # External should fail
        self.client.force_authenticate(user=self.users['external'])
        response = self.client.post('/api/due-diligence/cases/', case_data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
    def test_assessment_approval_permissions(self):
        """Test that only managers can approve assessments."""
        # Create assessment as analyst
        self.client.force_authenticate(user=self.users['analyst'])
        assessment = Assessment.objects.create(
            assessment_name='Permission Test',
            assessment_type='PARTNER',
            status=AssessmentStatus.IN_REVIEW,
            group=self.group,
            assessor=self.users['analyst']
        )
        
        # Analyst cannot approve
        response = self.client.post(f'/api/assessments/{assessment.id}/approve/', {})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Admin can approve
        self.client.force_authenticate(user=self.users['admin'])
        response = self.client.post(f'/api/assessments/{assessment.id}/approve/', {})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
    def test_cross_group_isolation(self):
        """Test that users cannot access data from other groups."""
        # Create another group
        other_group = Group.objects.create(name='Other Group')
        other_user = User.objects.create_user(
            username='other',
            email='other@test.com',
            password='test',
            role=User.Role.BUSINESS_ANALYST
        )
        GroupMembership.objects.create(user=other_user, group=other_group)
        
        # Create case in other group
        self.client.force_authenticate(user=other_user)
        response = self.client.post('/api/due-diligence/cases/', {
            'case_name': 'Other Group Case',
            'case_type': 'new_partner',
            'priority': 'low'
        })
        other_case_id = response.data['id']
        
        # Our analyst cannot see it
        self.client.force_authenticate(user=self.users['analyst'])
        response = self.client.get(f'/api/due-diligence/cases/{other_case_id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # List view should not include it
        response = self.client.get('/api/due-diligence/cases/')
        case_ids = [case['id'] for case in response.data['results']]
        self.assertNotIn(other_case_id, case_ids)


class DataValidationTest(TestCase):
    """Test data validation and business rules."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='test',
            email='test@test.com',
            password='test'
        )
        self.group = Group.objects.create(name='Test Group')
        GroupMembership.objects.create(user=self.user, group=self.group)
        
    def test_partner_validation(self):
        """Test partner model validation."""
        # Test required fields
        with self.assertRaises(Exception):
            DevelopmentPartner.objects.create(
                # Missing required company_name
                group=self.group,
                created_by=self.user
            )
        
        # Test ownership percentage validation
        partner = DevelopmentPartner.objects.create(
            company_name='Test Partner',
            group=self.group,
            created_by=self.user
        )
        
        # Create shareholders totaling 100%
        KeyShareholder.objects.create(
            partner=partner,
            name='Shareholder 1',
            ownership_percentage=Decimal('60.0'),
            shareholder_type='individual'
        )
        
        KeyShareholder.objects.create(
            partner=partner,
            name='Shareholder 2',
            ownership_percentage=Decimal('40.0'),
            shareholder_type='corporation'
        )
        
        # Verify total is 100%
        total_ownership = partner.total_shareholder_percentage
        self.assertEqual(total_ownership, Decimal('100.0'))
        
    def test_scheme_financial_validation(self):
        """Test scheme financial calculations."""
        partner = DevelopmentPartner.objects.create(
            company_name='Test Developer',
            group=self.group,
            created_by=self.user
        )
        
        scheme = PBSAScheme.objects.create(
            scheme_name='Test Scheme',
            developer=partner,
            development_stage='PLANNING',
            location_city='London',
            location_country='GB',
            total_beds=500,
            total_units=250,
            site_area_value=Decimal('2000'),
            site_area_unit='SQ_M',
            total_development_cost_amount=Decimal('50000000'),
            total_development_cost_currency='GBP',
            group=self.group,
            created_by=self.user
        )
        
        # Test calculated properties
        self.assertEqual(scheme.cost_per_bed, Decimal('100000'))
        self.assertEqual(scheme.beds_per_unit, 2.0)
        
    def test_assessment_scoring_validation(self):
        """Test assessment scoring calculations."""
        assessment = Assessment.objects.create(
            assessment_name='Scoring Test',
            assessment_type='PARTNER',
            group=self.group,
            assessor=self.user
        )
        
        # Add metrics with different scores and weights
        metrics = [
            {'score': 5, 'weight': 5},  # 25 weighted
            {'score': 4, 'weight': 4},  # 16 weighted
            {'score': 3, 'weight': 3},  # 9 weighted
            {'score': 2, 'weight': 2},  # 4 weighted
            {'score': 1, 'weight': 1},  # 1 weighted
        ]
        
        for i, metric_data in enumerate(metrics):
            AssessmentMetric.objects.create(
                assessment=assessment,
                metric_name=f'Metric {i+1}',
                category='FINANCIAL',
                score=metric_data['score'],
                weight=metric_data['weight'],
                justification='Test metric',
                confidence_level='HIGH'
            )
        
        # Calculate scores
        scores = assessment.calculate_scores()
        
        # Total weighted score: 25 + 16 + 9 + 4 + 1 = 55
        # Max possible: 5*5 + 4*5 + 3*5 + 2*5 + 1*5 = 75
        self.assertEqual(scores['total_weighted_score'], 55)
        self.assertEqual(scores['max_possible_score'], 75)
        self.assertAlmostEqual(scores['score_percentage'], 73.33, places=2)
        
        # Update assessment scores
        assessment.update_scores()
        assessment.refresh_from_db()
        
        # Check decision band (73.33% = 146.67 points on 200 scale)
        self.assertEqual(assessment.decision_band, 'ACCEPTABLE')
        
    def test_case_workflow_validation(self):
        """Test case workflow state transitions."""
        case = DueDiligenceCase.objects.create(
            case_name='Workflow Test',
            case_type='new_partner',
            group=self.group,
            created_by=self.user,
            assigned_to=self.user
        )
        
        # Valid transitions
        valid_transitions = [
            ('initiated', 'data_collection'),
            ('data_collection', 'analysis'),
            ('analysis', 'review'),
            ('review', 'decision_pending')
        ]
        
        for from_status, to_status in valid_transitions:
            case.case_status = from_status
            case.save()
            
            # Should not raise exception
            case.transition_status(to_status, self.user)
            case.refresh_from_db()
            self.assertEqual(case.case_status, to_status)
        
        # Invalid transition
        case.case_status = 'initiated'
        case.save()
        
        with self.assertRaises(ValueError):
            case.transition_status('completed', self.user)
        
    def test_decision_requirements(self):
        """Test decision-making requirements."""
        case = DueDiligenceCase.objects.create(
            case_name='Decision Test',
            case_type='new_partner',
            case_status='initiated',
            group=self.group,
            created_by=self.user,
            assigned_to=self.user
        )
        
        # Cannot make decision in wrong status
        with self.assertRaises(ValueError):
            case.make_decision('proceed', self.user)
        
        # Move to correct status
        case.case_status = 'decision_pending'
        case.save()
        
        # Now decision should work
        case.make_decision(
            decision='conditional',
            decision_maker=self.user,
            rationale='Test decision',
            conditions=['Condition 1', 'Condition 2']
        )
        
        case.refresh_from_db()
        self.assertEqual(case.final_decision, 'conditional')
        self.assertEqual(case.case_status, 'approved')
        self.assertEqual(len(case.conditions), 2)
        self.assertIsNotNone(case.decision_date)