"""
Tests for Deal models.
"""

import uuid
from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError

from accounts.models import Group
from ..models import (
    Deal, DealType, DealSource, WorkflowTemplate, DealStage, DealRole,
    DealTeamMember, DealTransition, DealActivity, 
    MilestoneTemplate, DealMilestone
)

User = get_user_model()


class DealModelTests(TestCase):
    """Test Deal model functionality."""
    
    def setUp(self):
        """Set up test data."""
        # Create group
        self.group = Group.objects.create(
            name="Test Investment Group",
            description="Test group"
        )
        
        # Create users
        self.user = User.objects.create_user(
            username="analyst@test.com",
            email="analyst@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Analyst",
            is_active=True
        )
        self.user.groups.add(self.group)
        
        # Create deal type
        self.deal_type = DealType.objects.create(
            name="Series A",
            code="series_a",
            description="Series A investments",
            configuration={
                "min_investment": 1000000,
                "max_investment": 10000000
            },
            group=self.group
        )
        
        # Create deal source
        self.deal_source = DealSource.objects.create(
            name="Partner Network",
            code="partner_net",
            group=self.group
        )
    
    def test_deal_creation(self):
        """Test creating a deal."""
        deal = Deal.objects.create(
            name="Test Investment Deal",
            code="DEAL-001",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=5000000,
            pre_money_valuation=20000000,
            post_money_valuation=25000000,
            ownership_percentage=20.0,
            irr_target=25.0,
            deal_lead=self.user,
            group=self.group
        )
        
        self.assertEqual(deal.name, "Test Investment Deal")
        self.assertEqual(deal.code, "DEAL-001")
        self.assertEqual(deal.status, Deal.Status.PIPELINE)
        self.assertEqual(deal.investment_amount, 5000000)
        self.assertEqual(deal.ownership_percentage, 20.0)
        self.assertIsNone(deal.current_stage)
        self.assertIsNone(deal.actual_close_date)
    
    def test_deal_code_generation(self):
        """Test automatic deal code generation."""
        deal = Deal.objects.create(
            name="Auto Code Deal",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=2000000,
            group=self.group
        )
        
        # Code should be auto-generated if not provided
        self.assertIsNotNone(deal.code)
        self.assertTrue(len(deal.code) > 0)
    
    def test_deal_financial_metrics(self):
        """Test financial metric properties."""
        deal = Deal.objects.create(
            name="Financial Test Deal",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=5000000,
            pre_money_valuation=20000000,
            post_money_valuation=25000000,
            ownership_percentage=20.0,
            irr_target=25.0,
            multiple_target=5.0,
            group=self.group
        )
        
        # Test ownership percentage
        self.assertEqual(deal.ownership_percentage, 20.0)
        
        # Test multiple target
        self.assertEqual(deal.multiple_target, 5.0)
    
    def test_deal_status_transitions(self):
        """Test deal status transitions."""
        deal = Deal.objects.create(
            name="Status Test Deal",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=3000000,
            group=self.group
        )
        
        # Initial status should be PIPELINE
        self.assertEqual(deal.status, Deal.Status.PIPELINE)
        
        # Update status using FSM transitions
        deal.start_review()
        deal.save()
        self.assertEqual(deal.status, Deal.Status.INITIAL_REVIEW)
        
        # Progress through workflow to completion
        deal.start_due_diligence()
        deal.start_negotiation()
        deal.start_documentation()
        deal.start_closing()
        deal.complete_deal()
        deal.save()
        
        self.assertEqual(deal.status, Deal.Status.COMPLETED)
        self.assertIsNotNone(deal.actual_close_date)


class WorkflowModelTests(TestCase):
    """Test workflow-related models."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(
            name="Test Investment Group",
            description="Test group"
        )
        
        self.deal_type = DealType.objects.create(
            name="Series A",
            code="series_a",
            group=self.group
        )
    
    def test_workflow_template_creation(self):
        """Test creating a workflow template."""
        workflow = WorkflowTemplate.objects.create(
            name="Standard Series A Workflow",
            code="standard_series_a",
            deal_type=self.deal_type,
            description="Standard workflow for Series A deals",
            is_default=True,
            configuration={
                "require_legal_review": True,
                "require_financial_audit": True
            },
            group=self.group
        )
        
        self.assertEqual(workflow.name, "Standard Series A Workflow")
        self.assertTrue(workflow.is_default)
        self.assertTrue(workflow.is_active)
        self.assertEqual(workflow.deal_type, self.deal_type)
    
    def test_deal_stage_creation(self):
        """Test creating deal stages."""
        workflow = WorkflowTemplate.objects.create(
            name="Test Workflow",
            code="test_workflow",
            deal_type=self.deal_type,
            group=self.group
        )
        
        stage = DealStage.objects.create(
            workflow_template=workflow,
            name="Due Diligence",
            code="due_diligence",
            stage_type=DealStage.StageType.ANALYSIS,
            order=2,
            description="Perform due diligence",
            target_duration_days=30,
            max_duration_days=45,
            required_documents=["financial_statements", "legal_agreements"],
            required_tasks=["financial_review", "legal_review"],
            entry_criteria={
                "nda_signed": {"required": True, "description": "NDA must be signed"}
            },
            group=self.group
        )
        
        self.assertEqual(stage.name, "Due Diligence")
        self.assertEqual(stage.stage_type, DealStage.StageType.ANALYSIS)
        self.assertEqual(stage.order, 2)
        self.assertEqual(len(stage.required_documents), 2)
        self.assertEqual(stage.target_duration_days, 30)
    
    def test_stage_ordering(self):
        """Test that stages are ordered correctly."""
        workflow = WorkflowTemplate.objects.create(
            name="Test Workflow",
            code="test_workflow",
            deal_type=self.deal_type,
            group=self.group
        )
        
        # Create stages out of order
        stage3 = DealStage.objects.create(
            workflow_template=workflow,
            name="Stage 3",
            code="stage_3",
            stage_type=DealStage.StageType.CLOSING,
            order=3,
            group=self.group
        )
        
        stage1 = DealStage.objects.create(
            workflow_template=workflow,
            name="Stage 1",
            code="stage_1",
            stage_type=DealStage.StageType.ORIGINATION,
            order=1,
            group=self.group
        )
        
        stage2 = DealStage.objects.create(
            workflow_template=workflow,
            name="Stage 2",
            code="stage_2",
            stage_type=DealStage.StageType.SCREENING,
            order=2,
            group=self.group
        )
        
        # Check ordering
        stages = workflow.stages.all()
        self.assertEqual(stages[0], stage1)
        self.assertEqual(stages[1], stage2)
        self.assertEqual(stages[2], stage3)


class DealTeamTests(TestCase):
    """Test deal team management."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(
            name="Test Investment Group",
            description="Test group"
        )
        
        self.user1 = User.objects.create_user(
            username="user1@test.com",
            email="user1@test.com",
            password="testpass123",
            first_name="User",
            last_name="One"
        )
        
        self.user2 = User.objects.create_user(
            username="user2@test.com",
            email="user2@test.com",
            password="testpass123",
            first_name="User",
            last_name="Two"
        )
        
        self.deal_type = DealType.objects.create(
            name="Series A",
            code="series_a",
            group=self.group
        )
        
        # Create deal source
        self.deal_source = DealSource.objects.create(
            name="Partner Network",
            code="partner_net",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Team Test Deal",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=1000000,
            group=self.group
        )
        
        # Create roles
        self.lead_role = DealRole.objects.create(
            name="Deal Lead",
            code="deal_lead",
            permissions=["edit_deal", "approve_documents"],
            group=self.group
        )
        
        self.analyst_role = DealRole.objects.create(
            name="Analyst",
            code="analyst",
            permissions=["view_deal", "add_documents"],
            group=self.group
        )
    
    def test_add_team_member(self):
        """Test adding team members to a deal."""
        member = DealTeamMember.objects.create(
            deal=self.deal,
            user=self.user1,
            role=self.lead_role,
            involvement_level='lead',
            can_edit=True,
            can_approve=True,
            group=self.group
        )
        
        self.assertEqual(member.deal, self.deal)
        self.assertEqual(member.user, self.user1)
        self.assertEqual(member.role, self.lead_role)
        self.assertTrue(member.can_edit)
        self.assertTrue(member.can_approve)
        self.assertIsNone(member.removed_at)
    
    def test_team_member_removal(self):
        """Test removing team members."""
        member = DealTeamMember.objects.create(
            deal=self.deal,
            user=self.user1,
            role=self.lead_role,
            group=self.group
        )
        
        # Remove member
        member.removed_at = timezone.now()
        member.removal_reason = "Role change"
        member.save()
        
        self.assertIsNotNone(member.removed_at)
        self.assertEqual(member.removal_reason, "Role change")
    
    def test_team_member_permissions(self):
        """Test team member permission checking."""
        lead = DealTeamMember.objects.create(
            deal=self.deal,
            user=self.user1,
            role=self.lead_role,
            can_edit=True,
            can_approve=True,
            group=self.group
        )
        
        analyst = DealTeamMember.objects.create(
            deal=self.deal,
            user=self.user2,
            role=self.analyst_role,
            can_edit=True,
            can_approve=False,
            group=self.group
        )
        
        # Check permissions
        self.assertTrue(lead.has_permission("edit_deal"))
        self.assertTrue(lead.has_permission("approve_documents"))
        self.assertTrue(analyst.has_permission("view_deal"))
        self.assertFalse(analyst.has_permission("approve_documents"))


class DealActivityTests(TestCase):
    """Test deal activity tracking."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(
            name="Test Investment Group",
            description="Test group"
        )
        
        self.user = User.objects.create_user(
            username="user@test.com",
            email="user@test.com",
            password="testpass123"
        )
        
        self.deal_type = DealType.objects.create(
            name="Series A",
            code="series_a",
            group=self.group
        )
        
        # Create deal source
        self.deal_source = DealSource.objects.create(
            name="Partner Network",
            code="partner_net",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Activity Test Deal",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=1000000,
            group=self.group
        )
    
    def test_create_activity(self):
        """Test creating deal activities."""
        activity = DealActivity.objects.create(
            deal=self.deal,
            activity_type='deal_created',
            performed_by=self.user,
            description="Deal was created",
            metadata={"initial_amount": 1000000},
            group=self.group
        )
        
        self.assertEqual(activity.deal, self.deal)
        self.assertEqual(activity.activity_type, 'deal_created')
        self.assertEqual(activity.performed_by, self.user)
    
    def test_activity_auto_title(self):
        """Test automatic title generation."""
        activity = DealActivity.objects.create(
            deal=self.deal,
            activity_type='stage_changed',
            performed_by=self.user,
            description="Stage changed",
            metadata={"to_stage": "Due Diligence"},
            group=self.group
        )
        
        # Title should be auto-generated or use description
        self.assertTrue(len(activity.title) > 0)
    
    def test_activity_ordering(self):
        """Test that activities are ordered by creation time."""
        # Create activities with different timestamps
        activity1 = DealActivity.objects.create(
            deal=self.deal,
            activity_type='deal_created',
            performed_by=self.user,
            description="Deal created",
            group=self.group
        )
        
        # Create second activity
        activity2 = DealActivity.objects.create(
            deal=self.deal,
            activity_type='note_added',
            performed_by=self.user,
            description="Added a note",
            group=self.group
        )
        
        activities = self.deal.activities.all()
        # Most recent first
        self.assertEqual(activities[0], activity2)
        self.assertEqual(activities[1], activity1)


class MilestoneTests(TestCase):
    """Test milestone functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(
            name="Test Investment Group",
            description="Test group"
        )
        
        self.user = User.objects.create_user(
            username="user@test.com",
            email="user@test.com",
            password="testpass123"
        )
        
        self.deal_type = DealType.objects.create(
            name="Series A",
            code="series_a",
            group=self.group
        )
        
        # Create deal source
        self.deal_source = DealSource.objects.create(
            name="Partner Network",
            code="partner_net",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Milestone Test Deal",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=1000000,
            group=self.group
        )
        
        self.workflow = WorkflowTemplate.objects.create(
            name="Test Workflow",
            deal_type=self.deal_type,
            group=self.group
        )
        
        self.stage = DealStage.objects.create(
            workflow_template=self.workflow,
            name="Due Diligence",
            stage_type=DealStage.StageType.ANALYSIS,
            order=1,
            group=self.group
        )
    
    def test_milestone_creation(self):
        """Test creating milestones."""
        milestone = DealMilestone.objects.create(
            deal=self.deal,
            name="Complete Financial Review",
            description="Review all financial documents",
            due_date=timezone.now().date() + timedelta(days=14),
            stage=self.stage,
            priority='high',
            is_blocking=True,
            assigned_to=self.user,
            group=self.group
        )
        
        self.assertEqual(milestone.name, "Complete Financial Review")
        self.assertEqual(milestone.status, 'pending')
        self.assertEqual(milestone.priority, 'high')
        self.assertTrue(milestone.is_blocking)
        self.assertEqual(milestone.progress_percentage, 0)
    
    def test_milestone_overdue_check(self):
        """Test milestone overdue detection."""
        # Create past due milestone
        milestone = DealMilestone.objects.create(
            deal=self.deal,
            name="Overdue Milestone",
            due_date=timezone.now().date() - timedelta(days=5),
            stage=self.stage,
            group=self.group
        )
        
        self.assertTrue(milestone.is_overdue)
        self.assertEqual(milestone.days_until_due, -5)
        
        # Complete the milestone
        milestone.status = 'completed'
        milestone.completed_by = self.user
        milestone.completion_notes = "Completed late"
        milestone.completed_date = timezone.now().date()
        milestone.save()
        
        self.assertEqual(milestone.status, 'completed')
    
    def test_milestone_checklist_progress(self):
        """Test milestone checklist tracking."""
        milestone = DealMilestone.objects.create(
            deal=self.deal,
            name="Checklist Milestone",
            due_date=timezone.now().date() + timedelta(days=7),
            checklist_items=["Review financials", "Check legal docs", "Verify data"],
            completed_items=["Review financials"],
            stage=self.stage,
            group=self.group
        )
        
        # Should be 33% complete (1 of 3 items)
        self.assertEqual(milestone.checklist_progress, 33)
        
        # Complete another item
        milestone.completed_items = ["Review financials", "Check legal docs"]
        milestone.save()
        self.assertEqual(milestone.checklist_progress, 66)
    
    def test_milestone_completion(self):
        """Test completing a milestone."""
        milestone = DealMilestone.objects.create(
            deal=self.deal,
            name="Test Milestone",
            due_date=timezone.now().date() + timedelta(days=7),
            stage=self.stage,
            group=self.group
        )
        
        # Complete the milestone
        milestone.status = 'completed'
        milestone.completed_by = self.user
        milestone.completion_notes = "All requirements met"
        milestone.progress_percentage = 100
        milestone.completed_date = timezone.now().date()
        milestone.save()
        
        self.assertEqual(milestone.status, 'completed')
        self.assertEqual(milestone.completed_by, self.user)
        self.assertEqual(milestone.completion_notes, "All requirements met")
        self.assertEqual(milestone.progress_percentage, 100)
        self.assertIsNotNone(milestone.completed_date)
    
    def test_milestone_template_creation(self):
        """Test creating milestone templates."""
        template = MilestoneTemplate.objects.create(
            name="Financial Review Template",
            code="financial_review",
            description="Standard financial review milestone",
            stage=self.stage,
            days_from_stage_start=14,
            is_blocking=True,
            required_documents=["financial_statements", "bank_records"],
            checklist_items=["Review P&L", "Check cash flow", "Verify assets"],
            group=self.group
        )
        
        self.assertEqual(template.name, "Financial Review Template")
        self.assertEqual(template.days_from_stage_start, 14)
        self.assertTrue(template.is_blocking)
        self.assertEqual(len(template.required_documents), 2)
        self.assertEqual(len(template.checklist_items), 3)
        
        # Add to deal type
        template.deal_types.add(self.deal_type)
        self.assertIn(self.deal_type, template.deal_types.all())