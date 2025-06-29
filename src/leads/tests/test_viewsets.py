"""
Comprehensive tests for leads viewsets.

Tests all ViewSet functionality including CRUD operations, permissions,
filtering, custom actions, and API endpoints.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, force_authenticate

from accounts.models import Group
from market_intelligence.models import TargetCompany
from ..models import LeadScoringModel, Lead, LeadActivity
from ..views import LeadScoringModelViewSet, LeadViewSet, LeadActivityViewSet
from .factories import (
    LeadScoringModelFactory, LeadFactory, LeadActivityFactory,
    TargetCompanyFactory, UserFactory, TestDataMixin,
    QualifiedLeadFactory, ConvertedLeadFactory
)


class LeadScoringModelViewSetTest(TestCase, TestDataMixin):
    """Test LeadScoringModelViewSet functionality."""
    
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.viewset_class = LeadScoringModelViewSet
        self.base_url = '/api/leads/scoring-models/'
    
    def test_list_scoring_models(self):
        """Test listing scoring models filtered by group."""
        # Create models in different groups
        model1 = LeadScoringModelFactory.create(group=self.group1)
        model2 = LeadScoringModelFactory.create(group=self.group1)
        model3 = LeadScoringModelFactory.create(group=self.group2)
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        
        model_ids = [m['id'] for m in response.data['results']]
        self.assertIn(str(model1.id), model_ids)
        self.assertIn(str(model2.id), model_ids)
        self.assertNotIn(str(model3.id), model_ids)
    
    def test_create_scoring_model(self):
        """Test creating a new scoring model."""
        data = {
            'name': 'New PBSA Scorer',
            'description': 'Advanced PBSA lead scoring',
            'model_type': LeadScoringModel.ModelType.RULES_BASED,
            'version': '1.0.0',
            'scoring_criteria': {
                'pbsa_focus': {'weight': 0.4, 'max_score': 100},
                'company_size': {'weight': 0.3, 'max_score': 100},
                'recent_activity': {'weight': 0.3, 'max_score': 100}
            },
            'thresholds': {
                'qualified': 75,
                'potential': 50,
                'unqualified': 25
            }
        }
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(self.base_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New PBSA Scorer')
        
        # Verify model was created with correct group
        model = LeadScoringModel.objects.get(id=response.data['id'])
        self.assertEqual(model.group, self.admin_user.group)
    
    def test_retrieve_scoring_model(self):
        """Test retrieving a specific scoring model."""
        model = LeadScoringModelFactory.create(
            group=self.group1,
            name='Test Model'
        )
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(f'{self.base_url}{model.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Model')
        self.assertIn('performance_metrics', response.data)
    
    def test_update_scoring_model(self):
        """Test updating a scoring model."""
        model = LeadScoringModelFactory.create(group=self.group1)
        
        data = {
            'name': 'Updated Model Name',
            'is_active': False
        }
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(
            f'{self.base_url}{model.id}/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        model.refresh_from_db()
        self.assertEqual(model.name, 'Updated Model Name')
        self.assertFalse(model.is_active)
    
    def test_delete_scoring_model(self):
        """Test deleting a scoring model."""
        model = LeadScoringModelFactory.create(group=self.group1)
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.delete(f'{self.base_url}{model.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            LeadScoringModel.objects.filter(id=model.id).exists()
        )
    
    def test_activate_deactivate_actions(self):
        """Test custom activate/deactivate actions."""
        model = LeadScoringModelFactory.create(
            group=self.group1,
            is_active=True
        )
        
        self.client.force_authenticate(user=self.admin_user)
        
        # Deactivate
        response = self.client.post(
            f'{self.base_url}{model.id}/deactivate/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        model.refresh_from_db()
        self.assertFalse(model.is_active)
        
        # Activate
        response = self.client.post(
            f'{self.base_url}{model.id}/activate/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        model.refresh_from_db()
        self.assertTrue(model.is_active)
    
    def test_evaluate_performance_action(self):
        """Test evaluate_performance custom action."""
        model = LeadScoringModelFactory.create(group=self.group1)
        
        # Create test leads with known outcomes
        lead1 = LeadFactory.create(
            group=self.group1,
            scoring_model=model,
            lead_score=80,
            status=Lead.LeadStatus.CONVERTED
        )
        lead2 = LeadFactory.create(
            group=self.group1,
            scoring_model=model,
            lead_score=30,
            status=Lead.LeadStatus.UNQUALIFIED
        )
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            f'{self.base_url}{model.id}/evaluate_performance/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('accuracy', response.data)
        self.assertIn('precision', response.data)
        self.assertIn('recall', response.data)
        
        model.refresh_from_db()
        self.assertIsNotNone(model.last_evaluated)
    
    def test_filter_by_model_type(self):
        """Test filtering models by type."""
        rules_model = LeadScoringModelFactory.create(
            group=self.group1,
            model_type=LeadScoringModel.ModelType.RULES_BASED
        )
        ml_model = LeadScoringModelFactory.create(
            group=self.group1,
            model_type=LeadScoringModel.ModelType.ML_BASED
        )
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            self.base_url,
            {'model_type': LeadScoringModel.ModelType.RULES_BASED}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(
            response.data['results'][0]['id'],
            str(rules_model.id)
        )
    
    def test_permissions(self):
        """Test ViewSet permissions."""
        model = LeadScoringModelFactory.create(group=self.group1)
        
        # Unauthenticated - should fail
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Viewer - read only
        self.client.force_authenticate(user=self.viewer_user)
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        response = self.client.post(self.base_url, {})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Different group - no access
        other_user = UserFactory.create(group=self.group2, role="ADMIN")
        self.client.force_authenticate(user=other_user)
        response = self.client.get(f'{self.base_url}{model.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class LeadViewSetTest(TestCase, TestDataMixin):
    """Test LeadViewSet functionality."""
    
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.viewset_class = LeadViewSet
        self.base_url = '/api/leads/'
        
        # Create test data
        self.target = TargetCompanyFactory.create(
            group=self.group1,
            company_name="Test PBSA Developer"
        )
        self.scoring_model = LeadScoringModelFactory.create(
            group=self.group1
        )
    
    def test_list_leads(self):
        """Test listing leads with pagination."""
        # Create multiple leads
        leads = LeadFactory.create_batch(
            5,
            group=self.group1,
            assigned_to=self.analyst_user
        )
        
        # Create lead in different group
        other_lead = LeadFactory.create(group=self.group2)
        
        self.client.force_authenticate(user=self.analyst_user)
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)
        
        # Check ordering (by score descending)
        scores = [l['lead_score'] for l in response.data['results']]
        self.assertEqual(scores, sorted(scores, reverse=True))
    
    def test_create_lead(self):
        """Test creating a new lead."""
        data = {
            'target_company': str(self.target.id),
            'scoring_model': str(self.scoring_model.id),
            'contact_name': 'John Smith',
            'contact_email': 'john@pbsadeveloper.com',
            'contact_phone': '+44 20 1234 5678',
            'contact_title': 'CEO',
            'source': Lead.LeadSource.MARKET_INTELLIGENCE,
            'tags': ['pbsa', 'high-priority']
        }
        
        self.client.force_authenticate(user=self.analyst_user)
        response = self.client.post(self.base_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['contact_name'], 'John Smith')
        
        # Verify lead was created and assigned
        lead = Lead.objects.get(id=response.data['id'])
        self.assertEqual(lead.group, self.analyst_user.group)
        self.assertEqual(lead.assigned_to, self.analyst_user)
        self.assertEqual(lead.status, Lead.LeadStatus.NEW)
    
    def test_retrieve_lead_detail(self):
        """Test retrieving lead with full details."""
        lead = LeadFactory.create(
            group=self.group1,
            target_company=self.target
        )
        
        # Add activities
        LeadActivityFactory.create_batch(3, lead=lead)
        
        self.client.force_authenticate(user=self.analyst_user)
        response = self.client.get(f'{self.base_url}{lead.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('activities', response.data)
        self.assertEqual(len(response.data['activities']), 3)
        self.assertIn('days_since_creation', response.data)
        self.assertIn('days_in_current_status', response.data)
    
    def test_update_lead(self):
        """Test updating a lead."""
        lead = LeadFactory.create(
            group=self.group1,
            status=Lead.LeadStatus.NEW
        )
        
        data = {
            'status': Lead.LeadStatus.CONTACTED,
            'priority': Lead.Priority.HIGH
        }
        
        self.client.force_authenticate(user=self.analyst_user)
        response = self.client.patch(
            f'{self.base_url}{lead.id}/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.LeadStatus.CONTACTED)
        self.assertEqual(lead.priority, Lead.Priority.HIGH)
        
        # Check status change activity was created
        activity = lead.activities.filter(
            activity_type=LeadActivity.ActivityType.STATUS_CHANGE
        ).first()
        self.assertIsNotNone(activity)
    
    def test_score_lead_action(self):
        """Test score custom action."""
        lead = LeadFactory.create(
            group=self.group1,
            target_company=self.target,
            scoring_model=self.scoring_model
        )
        
        self.client.force_authenticate(user=self.analyst_user)
        response = self.client.post(f'{self.base_url}{lead.id}/score/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('lead_score', response.data)
        self.assertIn('confidence_score', response.data)
        self.assertIn('score_breakdown', response.data)
        
        lead.refresh_from_db()
        self.assertIsNotNone(lead.lead_score)
        self.assertIsNotNone(lead.scoring_timestamp)
    
    def test_convert_lead_action(self):
        """Test convert custom action."""
        lead = QualifiedLeadFactory.create(
            group=self.group1,
            status=Lead.LeadStatus.QUALIFIED
        )
        
        data = {'conversion_value': '500000.00'}
        
        self.client.force_authenticate(user=self.manager_user)
        response = self.client.post(
            f'{self.base_url}{lead.id}/convert/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.LeadStatus.CONVERTED)
        self.assertIsNotNone(lead.converted_at)
        self.assertEqual(lead.conversion_value, Decimal('500000.00'))
    
    def test_bulk_update_action(self):
        """Test bulk update custom action."""
        leads = LeadFactory.create_batch(
            3,
            group=self.group1,
            status=Lead.LeadStatus.NEW
        )
        
        data = {
            'lead_ids': [str(l.id) for l in leads],
            'action': 'update_status',
            'status': Lead.LeadStatus.CONTACTED
        }
        
        self.client.force_authenticate(user=self.analyst_user)
        response = self.client.post(
            f'{self.base_url}bulk_update/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['updated'], 3)
        
        # Verify all leads were updated
        for lead in leads:
            lead.refresh_from_db()
            self.assertEqual(lead.status, Lead.LeadStatus.CONTACTED)
    
    def test_analytics_action(self):
        """Test analytics custom action."""
        # Create leads with different statuses
        LeadFactory.create(
            group=self.group1,
            status=Lead.LeadStatus.NEW,
            lead_score=40
        )
        QualifiedLeadFactory.create(
            group=self.group1,
            lead_score=85
        )
        ConvertedLeadFactory.create(
            group=self.group1,
            lead_score=92,
            conversion_value=Decimal('1000000')
        )
        
        self.client.force_authenticate(user=self.manager_user)
        response = self.client.get(f'{self.base_url}analytics/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_leads'], 3)
        self.assertIn('leads_by_status', response.data)
        self.assertIn('average_lead_score', response.data)
        self.assertIn('conversion_rate', response.data)
        self.assertIn('total_conversion_value', response.data)
    
    def test_filter_by_status(self):
        """Test filtering leads by status."""
        qualified = QualifiedLeadFactory.create(group=self.group1)
        new = LeadFactory.create(
            group=self.group1,
            status=Lead.LeadStatus.NEW
        )
        
        self.client.force_authenticate(user=self.analyst_user)
        response = self.client.get(
            self.base_url,
            {'status': Lead.LeadStatus.QUALIFIED}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(
            response.data['results'][0]['id'],
            str(qualified.id)
        )
    
    def test_filter_by_score_range(self):
        """Test filtering leads by score range."""
        high_score = LeadFactory.create(
            group=self.group1,
            lead_score=85
        )
        low_score = LeadFactory.create(
            group=self.group1,
            lead_score=25
        )
        
        self.client.force_authenticate(user=self.analyst_user)
        response = self.client.get(
            self.base_url,
            {'min_score': 70}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(
            response.data['results'][0]['id'],
            str(high_score.id)
        )
    
    def test_search_leads(self):
        """Test searching leads by contact name or company."""
        lead1 = LeadFactory.create(
            group=self.group1,
            contact_name="John Smith",
            target_company__company_name="PBSA Developers Ltd"
        )
        lead2 = LeadFactory.create(
            group=self.group1,
            contact_name="Jane Doe",
            target_company__company_name="Student Housing Inc"
        )
        
        self.client.force_authenticate(user=self.analyst_user)
        
        # Search by contact name
        response = self.client.get(self.base_url, {'search': 'john'})
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(
            response.data['results'][0]['id'],
            str(lead1.id)
        )
        
        # Search by company name
        response = self.client.get(self.base_url, {'search': 'PBSA'})
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(
            response.data['results'][0]['id'],
            str(lead1.id)
        )
    
    def test_my_leads_filter(self):
        """Test filtering to show only assigned leads."""
        my_lead = LeadFactory.create(
            group=self.group1,
            assigned_to=self.analyst_user
        )
        other_lead = LeadFactory.create(
            group=self.group1,
            assigned_to=self.manager_user
        )
        
        self.client.force_authenticate(user=self.analyst_user)
        response = self.client.get(self.base_url, {'my_leads': 'true'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(
            response.data['results'][0]['id'],
            str(my_lead.id)
        )


class LeadActivityViewSetTest(TestCase, TestDataMixin):
    """Test LeadActivityViewSet functionality."""
    
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.viewset_class = LeadActivityViewSet
        self.base_url = '/api/leads/activities/'
        
        self.lead = LeadFactory.create(
            group=self.group1,
            assigned_to=self.analyst_user
        )
    
    def test_list_activities(self):
        """Test listing activities."""
        # Create activities
        activity1 = LeadActivityFactory.create(
            lead=self.lead,
            created_by=self.analyst_user
        )
        activity2 = LeadActivityFactory.create(
            lead=self.lead,
            created_by=self.analyst_user
        )
        
        # Create activity for different lead
        other_lead = LeadFactory.create(group=self.group1)
        other_activity = LeadActivityFactory.create(lead=other_lead)
        
        self.client.force_authenticate(user=self.analyst_user)
        response = self.client.get(
            self.base_url,
            {'lead': str(self.lead.id)}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_create_activity(self):
        """Test creating a new activity."""
        data = {
            'lead': str(self.lead.id),
            'activity_type': LeadActivity.ActivityType.EMAIL,
            'description': 'Sent follow-up email',
            'contact_method': 'email'
        }
        
        self.client.force_authenticate(user=self.analyst_user)
        response = self.client.post(self.base_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data['activity_type'],
            LeadActivity.ActivityType.EMAIL
        )
        
        # Verify activity was created
        activity = LeadActivity.objects.get(id=response.data['id'])
        self.assertEqual(activity.created_by, self.analyst_user)
    
    def test_complete_activity(self):
        """Test marking activity as completed."""
        activity = LeadActivityFactory.create(
            lead=self.lead,
            activity_type=LeadActivity.ActivityType.CALL,
            scheduled_at=timezone.now() - timedelta(hours=1),
            completed_at=None
        )
        
        data = {'outcome': 'Connected - positive response'}
        
        self.client.force_authenticate(user=self.analyst_user)
        response = self.client.post(
            f'{self.base_url}{activity.id}/complete/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        activity.refresh_from_db()
        self.assertTrue(activity.is_completed)
        self.assertEqual(activity.outcome, 'Connected - positive response')
        self.assertIsNotNone(activity.completed_at)
    
    def test_overdue_activities_filter(self):
        """Test filtering overdue activities."""
        # Create overdue activity
        overdue = LeadActivityFactory.create(
            lead=self.lead,
            scheduled_at=timezone.now() - timedelta(days=1),
            completed_at=None
        )
        
        # Create future activity
        future = LeadActivityFactory.create(
            lead=self.lead,
            scheduled_at=timezone.now() + timedelta(days=1),
            completed_at=None
        )
        
        self.client.force_authenticate(user=self.analyst_user)
        response = self.client.get(
            self.base_url,
            {'overdue': 'true'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(
            response.data['results'][0]['id'],
            str(overdue.id)
        )
    
    def test_upcoming_activities_action(self):
        """Test upcoming activities custom action."""
        # Create upcoming activities
        tomorrow = timezone.now() + timedelta(days=1)
        next_week = timezone.now() + timedelta(days=8)
        
        upcoming = LeadActivityFactory.create(
            lead=self.lead,
            scheduled_at=tomorrow,
            completed_at=None
        )
        far_future = LeadActivityFactory.create(
            lead=self.lead,
            scheduled_at=next_week,
            completed_at=None
        )
        
        self.client.force_authenticate(user=self.analyst_user)
        response = self.client.get(f'{self.base_url}upcoming/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only show activities in next 7 days
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], str(upcoming.id))
    
    def test_permissions(self):
        """Test activity permissions."""
        activity = LeadActivityFactory.create(
            lead=self.lead,
            created_by=self.analyst_user
        )
        
        # Owner can update
        self.client.force_authenticate(user=self.analyst_user)
        response = self.client.patch(
            f'{self.base_url}{activity.id}/',
            {'description': 'Updated description'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Other user in same group can view
        self.client.force_authenticate(user=self.manager_user)
        response = self.client.get(f'{self.base_url}{activity.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # User from different group cannot access
        other_user = UserFactory.create(group=self.group2)
        self.client.force_authenticate(user=other_user)
        response = self.client.get(f'{self.base_url}{activity.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ViewSetIntegrationTest(TestCase, TestDataMixin):
    """Test integration between different ViewSets."""
    
    def setUp(self):
        super().setUp()
        self.client = APIClient()
    
    def test_complete_lead_workflow_via_api(self):
        """Test complete lead workflow through API endpoints."""
        # Create scoring model
        model_data = {
            'name': 'API Test Scorer',
            'model_type': LeadScoringModel.ModelType.RULES_BASED,
            'scoring_criteria': {
                'pbsa_focus': {'weight': 0.5, 'max_score': 100},
                'company_size': {'weight': 0.5, 'max_score': 100}
            },
            'thresholds': {
                'qualified': 70,
                'potential': 50,
                'unqualified': 30
            }
        }
        
        self.client.force_authenticate(user=self.admin_user)
        model_response = self.client.post(
            '/api/leads/scoring-models/',
            model_data,
            format='json'
        )
        self.assertEqual(model_response.status_code, status.HTTP_201_CREATED)
        model_id = model_response.data['id']
        
        # Create target company
        target = TargetCompanyFactory.create(
            group=self.group1,
            company_name="API Test PBSA Developer",
            business_model="developer",
            focus_sectors=["pbsa"]
        )
        
        # Create lead
        lead_data = {
            'target_company': str(target.id),
            'scoring_model': model_id,
            'contact_name': 'API Test Contact',
            'contact_email': 'api@test.com',
            'source': Lead.LeadSource.MARKET_INTELLIGENCE
        }
        
        self.client.force_authenticate(user=self.analyst_user)
        lead_response = self.client.post(
            '/api/leads/',
            lead_data,
            format='json'
        )
        self.assertEqual(lead_response.status_code, status.HTTP_201_CREATED)
        lead_id = lead_response.data['id']
        
        # Score the lead
        score_response = self.client.post(f'/api/leads/{lead_id}/score/')
        self.assertEqual(score_response.status_code, status.HTTP_200_OK)
        
        # Create activity
        activity_data = {
            'lead': lead_id,
            'activity_type': LeadActivity.ActivityType.CALL,
            'description': 'Initial qualification call',
            'scheduled_at': (timezone.now() + timedelta(hours=2)).isoformat()
        }
        
        activity_response = self.client.post(
            '/api/leads/activities/',
            activity_data,
            format='json'
        )
        self.assertEqual(activity_response.status_code, status.HTTP_201_CREATED)
        activity_id = activity_response.data['id']
        
        # Complete activity
        complete_response = self.client.post(
            f'/api/leads/activities/{activity_id}/complete/',
            {'outcome': 'Successful call'},
            format='json'
        )
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        
        # Update lead status
        update_response = self.client.patch(
            f'/api/leads/{lead_id}/',
            {'status': Lead.LeadStatus.QUALIFIED},
            format='json'
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        
        # Get analytics
        analytics_response = self.client.get('/api/leads/analytics/')
        self.assertEqual(analytics_response.status_code, status.HTTP_200_OK)
        self.assertGreater(analytics_response.data['total_leads'], 0)