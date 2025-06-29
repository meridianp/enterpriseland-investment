"""
API tests for Deal endpoints.
"""

from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from accounts.models import Group
from ..models import (
    Deal, DealType, DealSource, WorkflowTemplate, DealStage,
    DealRole, DealTeamMember, DealMilestone
)

User = get_user_model()


class DealAPITestCase(APITestCase):
    """Base test case with common setup."""
    
    def setUp(self):
        """Set up test data."""
        # Create group
        self.group = Group.objects.create(
            name="Test Investment Group",
            description="Test group"
        )
        
        # Create users
        self.admin = User.objects.create_user(
            username="admin@test.com",
            email="admin@test.com",
            password="testpass123",
            is_superuser=True
        )
        self.admin.groups.add(self.group)
        
        self.manager = User.objects.create_user(
            username="manager@test.com",
            email="manager@test.com",
            password="testpass123"
        )
        self.manager.groups.add(self.group)
        
        self.analyst = User.objects.create_user(
            username="analyst@test.com",
            email="analyst@test.com",
            password="testpass123"
        )
        self.analyst.groups.add(self.group)
        
        # Create deal type
        self.deal_type = DealType.objects.create(
            name="Series A",
            code="series_a",
            configuration={
                "min_investment": 1000000,
                "max_investment": 10000000
            },
            group=self.group
        )
        
        # Create workflow and stages
        self.workflow = WorkflowTemplate.objects.create(
            name="Series A Workflow",
            code="series_a_workflow",
            deal_type=self.deal_type,
            is_default=True,
            group=self.group
        )
        
        self.stage1 = DealStage.objects.create(
            workflow_template=self.workflow,
            name="Initial Review",
            code="initial_review",
            stage_type=DealStage.StageType.SCREENING,
            order=1,
            group=self.group
        )
        
        self.stage2 = DealStage.objects.create(
            workflow_template=self.workflow,
            name="Due Diligence",
            code="due_diligence",
            stage_type=DealStage.StageType.ANALYSIS,
            order=2,
            group=self.group
        )
        
        # Create role
        self.lead_role = DealRole.objects.create(
            name="Deal Lead",
            code="deal_lead",
            permissions=["edit_deal", "approve_documents"],
            group=self.group
        )
        
        # Create deal source
        self.deal_source = DealSource.objects.create(
            name="Partner Network",
            code="partner_net",
            group=self.group
        )


class DealTypeAPITests(DealAPITestCase):
    """Test DealType API endpoints."""
    
    def test_list_deal_types(self):
        """Test listing deal types."""
        self.client.force_authenticate(user=self.analyst)
        
        response = self.client.get('/api/deals/types/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Series A')
    
    def test_create_deal_type_requires_admin(self):
        """Test that only admins can create deal types."""
        # Try as analyst - should fail
        self.client.force_authenticate(user=self.analyst)
        
        data = {
            'name': 'Series B',
            'code': 'series_b',
            'description': 'Series B investments'
        }
        
        response = self.client.post('/api/deals/types/', data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Try as admin - should succeed
        self.client.force_authenticate(user=self.admin)
        
        response = self.client.post('/api/deals/types/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Series B')


class DealAPITests(DealAPITestCase):
    """Test Deal API endpoints."""
    
    def setUp(self):
        super().setUp()
        
        # Create a deal
        self.deal = Deal.objects.create(
            name="Test Investment",
            code="DEAL-001",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=5000000,
            deal_lead=self.manager,
            current_stage=self.stage1,
            group=self.group
        )
        
        # Add manager to team
        DealTeamMember.objects.create(
            deal=self.deal,
            user=self.manager,
            role=self.lead_role,
            can_edit=True,
            can_approve=True,
            group=self.group
        )
    
    def test_list_deals(self):
        """Test listing deals."""
        self.client.force_authenticate(user=self.analyst)
        
        response = self.client.get('/api/deals/deals/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Test Investment')
    
    def test_create_deal(self):
        """Test creating a deal."""
        self.client.force_authenticate(user=self.manager)
        
        data = {
            'name': 'New Investment Opportunity',
            'deal_type': str(self.deal_type.id),
            'deal_source': str(self.deal_source.id),
            'investment_amount': 3000000,
            'pre_money_valuation': 15000000,
            'post_money_valuation': 18000000,
            'ownership_percentage': 16.67,
            'irr_target': 30.0,
            'deal_lead': str(self.manager.id),
            'expected_close_date': (timezone.now() + timedelta(days=90)).date().isoformat(),
            'description': 'Promising tech startup'
        }
        
        response = self.client.post('/api/deals/deals/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Investment Opportunity')
        self.assertIsNotNone(response.data['code'])  # Auto-generated
        
        # Verify deal was created with correct group
        deal = Deal.objects.get(id=response.data['id'])
        self.assertEqual(deal.group, self.group)
    
    def test_update_deal_permissions(self):
        """Test deal update permissions."""
        # Analyst without permission - should fail
        self.client.force_authenticate(user=self.analyst)
        
        data = {'name': 'Updated Name'}
        response = self.client.patch(f'/api/deals/deals/{self.deal.id}/', data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Manager with permission - should succeed
        self.client.force_authenticate(user=self.manager)
        
        response = self.client.patch(f'/api/deals/deals/{self.deal.id}/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Name')
    
    def test_deal_activities(self):
        """Test getting deal activities."""
        self.client.force_authenticate(user=self.manager)
        
        response = self.client.get(f'/api/deals/deals/{self.deal.id}/activities/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should have activities from deal creation
        self.assertGreaterEqual(len(response.data['results']), 0)
    
    def test_deal_team(self):
        """Test getting deal team members."""
        self.client.force_authenticate(user=self.analyst)
        
        response = self.client.get(f'/api/deals/deals/{self.deal.id}/team/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['user'], str(self.manager.id))
    
    def test_available_transitions(self):
        """Test getting available stage transitions."""
        self.client.force_authenticate(user=self.manager)
        
        response = self.client.get(f'/api/deals/deals/{self.deal.id}/available-transitions/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        
        # Should have transition to stage2 available
        transitions = [t for t in response.data if t['stage'] and t['stage']['id'] == str(self.stage2.id)]
        self.assertEqual(len(transitions), 1)
    
    def test_transition_deal(self):
        """Test transitioning deal to new stage."""
        self.client.force_authenticate(user=self.manager)
        
        data = {
            'target_stage': str(self.stage2.id),
            'reason': 'Initial review complete',
            'force': True  # Force to bypass requirements
        }
        
        response = self.client.post(
            f'/api/deals/deals/{self.deal.id}/transition/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['current_stage_detail']['id'], str(self.stage2.id))
        
        # Verify deal was updated
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.current_stage, self.stage2)
    
    def test_pipeline_view(self):
        """Test pipeline view of deals."""
        self.client.force_authenticate(user=self.analyst)
        
        response = self.client.get('/api/deals/deals/pipeline/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('pipeline', response.data)
        self.assertIn('initial_review', response.data)
        
        # Check pipeline data
        pipeline_data = response.data['pipeline']
        self.assertEqual(pipeline_data['count'], 1)
        self.assertEqual(pipeline_data['value'], 5000000)
    
    def test_deal_analytics(self):
        """Test deal analytics endpoint."""
        self.client.force_authenticate(user=self.manager)
        
        response = self.client.get('/api/deals/deals/analytics/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_deals'], 1)
        self.assertEqual(response.data['total_investment'], 5000000)
        self.assertIn('by_status', response.data)
        self.assertIn('by_stage', response.data)
        self.assertIn('by_deal_type', response.data)


class DealMilestoneAPITests(DealAPITestCase):
    """Test DealMilestone API endpoints."""
    
    def setUp(self):
        super().setUp()
        
        # Create a deal
        self.deal = Deal.objects.create(
            name="Milestone Test Deal",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=2000000,
            deal_lead=self.manager,
            current_stage=self.stage1,
            group=self.group
        )
        
        # Create milestone
        self.milestone = DealMilestone.objects.create(
            deal=self.deal,
            name="Complete Due Diligence",
            due_date=timezone.now().date() + timedelta(days=14),
            stage=self.stage1,
            priority='high',
            assigned_to=self.analyst,
            group=self.group
        )
    
    def test_list_milestones(self):
        """Test listing milestones."""
        self.client.force_authenticate(user=self.analyst)
        
        response = self.client.get('/api/deals/milestones/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Complete Due Diligence')
    
    def test_create_milestone(self):
        """Test creating a milestone."""
        self.client.force_authenticate(user=self.manager)
        
        data = {
            'deal': str(self.deal.id),
            'name': 'Financial Review',
            'description': 'Review all financial statements',
            'due_date': (timezone.now() + timedelta(days=7)).date().isoformat(),
            'priority': 'high',
            'is_blocking': True,
            'assigned_to': str(self.analyst.id),
            'checklist_items': ['Review P&L', 'Check cash flow']
        }
        
        response = self.client.post('/api/deals/milestones/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Financial Review')
        self.assertTrue(response.data['is_blocking'])
    
    def test_complete_milestone(self):
        """Test completing a milestone."""
        # Assigned user can complete
        self.client.force_authenticate(user=self.analyst)
        
        data = {
            'completion_notes': 'All requirements verified'
        }
        
        response = self.client.post(
            f'/api/deals/milestones/{self.milestone.id}/complete/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'completed')
        self.assertIsNotNone(response.data['completed_date'])
        
        # Verify milestone was updated
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.status, 'completed')
        self.assertEqual(self.milestone.completed_by, self.analyst)
    
    def test_overdue_milestones(self):
        """Test getting overdue milestones."""
        # Create overdue milestone
        overdue_milestone = DealMilestone.objects.create(
            deal=self.deal,
            name="Overdue Task",
            due_date=timezone.now().date() - timedelta(days=5),
            status='pending',
            group=self.group
        )
        
        self.client.force_authenticate(user=self.manager)
        
        response = self.client.get('/api/deals/milestones/overdue/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(overdue_milestone.id))
        self.assertTrue(response.data['results'][0]['is_overdue'])


class DealTeamMemberAPITests(DealAPITestCase):
    """Test DealTeamMember API endpoints."""
    
    def setUp(self):
        super().setUp()
        
        # Create a deal
        self.deal = Deal.objects.create(
            name="Team Test Deal",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=3000000,
            deal_lead=self.manager,
            group=self.group
        )
    
    def test_add_team_member(self):
        """Test adding a team member."""
        self.client.force_authenticate(user=self.manager)
        
        data = {
            'deal': str(self.deal.id),
            'user': str(self.analyst.id),
            'role': str(self.lead_role.id),
            'involvement_level': 'core',
            'can_edit': True,
            'can_approve': False,
            'notify_on_updates': True
        }
        
        response = self.client.post('/api/deals/team-members/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user'], str(self.analyst.id))
        self.assertEqual(response.data['involvement_level'], 'core')
    
    def test_remove_team_member(self):
        """Test removing a team member (soft delete)."""
        # Add team member
        member = DealTeamMember.objects.create(
            deal=self.deal,
            user=self.analyst,
            role=self.lead_role,
            group=self.group
        )
        
        self.client.force_authenticate(user=self.manager)
        
        response = self.client.delete(f'/api/deals/team-members/{member.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify soft delete
        member.refresh_from_db()
        self.assertIsNotNone(member.removed_at)
        self.assertIn('Removed by', member.removal_reason)