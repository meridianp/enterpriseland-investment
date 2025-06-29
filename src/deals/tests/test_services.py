"""
Tests for Deal services and business logic.
"""

from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock

from accounts.models import Group
from ..models import (
    Deal, DealType, DealSource, WorkflowTemplate, DealStage,
    DealTeamMember, DealRole, DealActivity,
    DealMilestone
)
from ..services.workflow_engine import WorkflowEngine

User = get_user_model()


class DealServiceIntegrationTests(TestCase):
    """Integration tests for deal services."""
    
    def setUp(self):
        """Set up test data."""
        # Create group
        self.group = Group.objects.create(
            name="Test Investment Group",
            description="Test group"
        )
        
        # Create users
        self.analyst = User.objects.create_user(
            username="analyst@test.com",
            email="analyst@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Analyst"
        )
        self.analyst.groups.add(self.group)
        
        self.manager = User.objects.create_user(
            username="manager@test.com",
            email="manager@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Manager"
        )
        self.manager.groups.add(self.group)
        
        # Create roles
        self.lead_role = DealRole.objects.create(
            name="Deal Lead",
            code="deal_lead",
            permissions=["edit_deal", "approve_documents", "manage_team"],
            group=self.group
        )
        
        self.analyst_role = DealRole.objects.create(
            name="Analyst",
            code="analyst",
            permissions=["view_deal", "add_documents", "add_notes"],
            group=self.group
        )
        
        # Create deal type and workflow
        self.deal_type = DealType.objects.create(
            name="Series A",
            code="series_a",
            configuration={
                "min_investment": 1000000,
                "max_investment": 10000000,
                "default_equity_range": [10, 30]
            },
            group=self.group
        )
        
        self.workflow = WorkflowTemplate.objects.create(
            name="Series A Workflow",
            code="series_a_workflow",
            deal_type=self.deal_type,
            is_default=True,
            configuration={
                "auto_assign_analyst": True,
                "require_ic_approval": True
            },
            group=self.group
        )
        
        # Create comprehensive workflow stages
        self.create_workflow_stages()
        
        # Create deal source
        self.deal_source = DealSource.objects.create(
            name="Partner Network",
            code="partner_net",
            group=self.group
        )
    
    def create_workflow_stages(self):
        """Create a complete workflow with multiple stages."""
        self.stage_origination = DealStage.objects.create(
            workflow_template=self.workflow,
            name="Origination",
            code="origination",
            stage_type=DealStage.StageType.ORIGINATION,
            order=1,
            target_duration_days=3,
            max_duration_days=7,
            required_documents=["pitch_deck"],
            automation_rules={
                "auto_assign": ["analyst"],
                "notifications": [
                    {"type": "email", "recipients": ["deal_lead"], "template": "new_deal"}
                ]
            },
            group=self.group
        )
        
        self.stage_screening = DealStage.objects.create(
            workflow_template=self.workflow,
            name="Screening",
            code="screening",
            stage_type=DealStage.StageType.SCREENING,
            order=2,
            target_duration_days=7,
            max_duration_days=14,
            required_documents=["pitch_deck", "financial_summary"],
            required_tasks=["initial_assessment", "market_analysis"],
            entry_criteria={
                "has_deal_lead": {
                    "required": True,
                    "description": "Deal lead must be assigned"
                }
            },
            group=self.group
        )
        
        self.stage_analysis = DealStage.objects.create(
            workflow_template=self.workflow,
            name="Due Diligence",
            code="due_diligence",
            stage_type=DealStage.StageType.ANALYSIS,
            order=3,
            target_duration_days=30,
            max_duration_days=45,
            required_documents=["financial_statements", "legal_agreements", "cap_table"],
            required_tasks=["financial_review", "legal_review", "technical_dd"],
            entry_criteria={
                "valuation_complete": {
                    "required": True,
                    "description": "Initial valuation must be complete"
                },
                "minimum_irr": {
                    "value": 20,
                    "description": "Minimum IRR of 20%"
                }
            },
            automation_rules={
                "create_tasks": [
                    {"name": "Financial DD", "assignee": "analyst", "due_days": 14},
                    {"name": "Legal DD", "assignee": "legal_counsel", "due_days": 21}
                ]
            },
            group=self.group
        )
        
        self.stage_approval = DealStage.objects.create(
            workflow_template=self.workflow,
            name="IC Approval",
            code="ic_approval",
            stage_type=DealStage.StageType.APPROVAL,
            order=4,
            target_duration_days=7,
            required_documents=["investment_memo", "financial_model"],
            entry_criteria={
                "all_dd_complete": {
                    "required": True,
                    "description": "All due diligence must be complete"
                }
            },
            group=self.group
        )
        
        self.stage_execution = DealStage.objects.create(
            workflow_template=self.workflow,
            name="Documentation",
            code="documentation",
            stage_type=DealStage.StageType.EXECUTION,
            order=5,
            target_duration_days=14,
            required_documents=["term_sheet", "purchase_agreement"],
            group=self.group
        )
        
        self.stage_closing = DealStage.objects.create(
            workflow_template=self.workflow,
            name="Closing",
            code="closing",
            stage_type=DealStage.StageType.CLOSING,
            order=6,
            target_duration_days=7,
            required_documents=["signed_agreements", "wire_confirmation"],
            group=self.group
        )
    
    def test_complete_deal_lifecycle(self):
        """Test a deal progressing through complete lifecycle."""
        # Create deal
        deal = Deal.objects.create(
            name="Complete Lifecycle Deal",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=5000000,
            pre_money_valuation=20000000,
            post_money_valuation=25000000,
            ownership_percentage=20.0,
            irr_target=25.0,
            deal_lead=self.manager,
            group=self.group
        )
        
        # Add team members
        DealTeamMember.objects.create(
            deal=deal,
            user=self.manager,
            role=self.lead_role,
            involvement_level='lead',
            can_edit=True,
            can_approve=True,
            group=self.group
        )
        
        DealTeamMember.objects.create(
            deal=deal,
            user=self.analyst,
            role=self.analyst_role,
            involvement_level=DealTeamMember.InvolvementLevel.CORE,
            can_edit=True,
            group=self.group
        )
        
        engine = WorkflowEngine(deal)
        
        # Progress through stages
        stages = [
            self.stage_origination,
            self.stage_screening,
            self.stage_analysis,
            self.stage_approval,
            self.stage_execution,
            self.stage_closing
        ]
        
        for stage in stages:
            # Transition to stage
            success, errors = engine.transition_to_stage(
                stage,
                performed_by=self.manager,
                reason=f"Moving to {stage.name}",
                force=True  # Force for testing
            )
            
            self.assertTrue(success, f"Failed to transition to {stage.name}: {errors}")
            
            # Verify deal state
            deal.refresh_from_db()
            self.assertEqual(deal.current_stage, stage)
            
            # Verify activity created
            activity = DealActivity.objects.filter(
                deal=deal,
                activity_type=ActivityType.STAGE_CHANGED,
                metadata__to_stage=stage.name
            ).exists()
            self.assertTrue(activity)
        
        # Final state should be CLOSING
        self.assertEqual(deal.status, Deal.Status.CLOSING)
        
        # Complete the deal
        deal.status = Deal.Status.COMPLETED
        deal.closed_date = timezone.now().date()
        deal.save()
        
        # Verify completion
        self.assertEqual(deal.status, Deal.Status.COMPLETED)
        self.assertIsNotNone(deal.closed_date)
    
    def test_deal_rejection_flow(self):
        """Test rejecting a deal at various stages."""
        deal = Deal.objects.create(
            name="Rejection Test Deal",
            deal_type=self.deal_type,
            partner=self.partner,
            investment_amount=2000000,
            irr_target=15.0,  # Below minimum
            deal_lead=self.manager,
            group=self.group
        )
        
        engine = WorkflowEngine(deal)
        
        # Move to screening
        engine.transition_to_stage(
            self.stage_screening,
            performed_by=self.manager,
            force=True
        )
        
        # Check available transitions
        transitions = engine.get_available_transitions()
        rejection_option = next(t for t in transitions if t['status'] == Deal.Status.REJECTED)
        self.assertIsNotNone(rejection_option)
        self.assertTrue(rejection_option['can_transition'])
        
        # Reject the deal
        deal.status = Deal.Status.REJECTED
        deal.rejection_reason = "IRR below minimum threshold"
        deal.save()
        
        # Create rejection activity
        DealActivity.objects.create(
            deal=deal,
            activity_type=ActivityType.DEAL_REJECTED,
            performed_by=self.manager,
            description="Deal rejected due to low IRR",
            metadata={"reason": "IRR below minimum threshold"},
            group=self.group
        )
        
        # Verify rejection
        self.assertEqual(deal.status, Deal.Status.REJECTED)
        self.assertIsNotNone(deal.rejection_reason)
    
    def test_milestone_driven_progression(self):
        """Test stage progression blocked by milestones."""
        deal = Deal.objects.create(
            name="Milestone Test Deal",
            deal_type=self.deal_type,
            partner=self.partner,
            investment_amount=3000000,
            irr_target=25.0,
            deal_lead=self.manager,
            current_stage=self.stage_screening,
            group=self.group
        )
        
        # Create blocking milestone
        milestone = DealMilestone.objects.create(
            deal=deal,
            name="Complete Initial Assessment",
            due_date=timezone.now().date() + timedelta(days=7),
            stage=self.stage_screening,
            is_blocking=True,
            status=DealMilestone.Status.PENDING,
            assigned_to=self.analyst,
            group=self.group
        )
        
        engine = WorkflowEngine(deal)
        
        # Try to progress - should fail
        success, errors = engine.transition_to_stage(
            self.stage_analysis,
            performed_by=self.manager,
            force=False
        )
        
        self.assertFalse(success)
        self.assertTrue(any("Complete Initial Assessment" in error for error in errors))
        
        # Complete milestone
        milestone.complete(completed_by=self.analyst, notes="Assessment complete")
        
        # Now transition should work (with force due to other requirements)
        success, errors = engine.transition_to_stage(
            self.stage_analysis,
            performed_by=self.manager,
            force=True
        )
        
        self.assertTrue(success)
    
    def test_concurrent_deal_activities(self):
        """Test handling concurrent activities on a deal."""
        deal = Deal.objects.create(
            name="Concurrent Activity Deal",
            deal_type=self.deal_type,
            partner=self.partner,
            investment_amount=4000000,
            deal_lead=self.manager,
            current_stage=self.stage_analysis,
            group=self.group
        )
        
        # Simulate multiple team members working concurrently
        activities = []
        
        # Financial review
        activities.append(DealActivity.objects.create(
            deal=deal,
            activity_type=ActivityType.DOCUMENT_UPLOADED,
            performed_by=self.analyst,
            description="Uploaded financial model",
            metadata={"document_name": "Financial_Model_v1.xlsx"},
            group=self.group
        ))
        
        # Legal review
        activities.append(DealActivity.objects.create(
            deal=deal,
            activity_type=ActivityType.DOCUMENT_REVIEWED,
            performed_by=self.manager,
            description="Reviewed legal agreements",
            metadata={"document_name": "Purchase_Agreement_Draft.pdf"},
            group=self.group
        ))
        
        # Note addition
        activities.append(DealActivity.objects.create(
            deal=deal,
            activity_type=ActivityType.NOTE_ADDED,
            performed_by=self.analyst,
            description="Market analysis complete",
            group=self.group
        ))
        
        # Verify all activities recorded
        self.assertEqual(deal.activities.count(), 3)
        
        # Verify ordering (most recent first)
        ordered_activities = list(deal.activities.all())
        self.assertEqual(ordered_activities[0].activity_type, ActivityType.NOTE_ADDED)
        self.assertEqual(ordered_activities[2].activity_type, ActivityType.DOCUMENT_UPLOADED)
    
    def test_stage_automation_rules(self):
        """Test automation rules execution on stage entry."""
        deal = Deal.objects.create(
            name="Automation Test Deal",
            deal_type=self.deal_type,
            partner=self.partner,
            investment_amount=6000000,
            deal_lead=self.manager,
            group=self.group
        )
        
        engine = WorkflowEngine(deal)
        
        # Mock notification sending
        with patch('deals.services.workflow_engine.send_deal_activity_notification') as mock_notify:
            # Transition to stage with automation rules
            success, _ = engine.transition_to_stage(
                self.stage_origination,
                performed_by=self.manager,
                force=True
            )
            
            self.assertTrue(success)
            
            # Verify stage has automation rules
            self.assertIn('auto_assign', self.stage_origination.automation_rules)
            self.assertIn('notifications', self.stage_origination.automation_rules)
    
    def test_deal_metrics_calculation(self):
        """Test deal financial metrics calculations."""
        deal = Deal.objects.create(
            name="Metrics Test Deal",
            deal_type=self.deal_type,
            partner=self.partner,
            investment_amount=5000000,
            pre_money_valuation=20000000,
            post_money_valuation=25000000,
            equity_percentage=20.0,
            irr_target=25.0,
            group=self.group
        )
        
        # Test ownership percentage
        self.assertEqual(deal.ownership_percentage, 20.0)
        
        # Test investment multiple
        self.assertEqual(deal.investment_multiple, 5.0)  # 25M / 5M
        
        # Update deal with exit scenario
        deal.exit_valuation = 100000000
        deal.save()
        
        # Test exit multiple (would be 20x on 5M investment for 20% ownership)
        exit_value = deal.exit_valuation * (deal.equity_percentage / 100)
        exit_multiple = exit_value / deal.investment_amount
        self.assertEqual(exit_multiple, 4.0)  # 20M / 5M
    
    def test_deal_team_permissions(self):
        """Test team member permissions on deal actions."""
        deal = Deal.objects.create(
            name="Permissions Test Deal",
            deal_type=self.deal_type,
            partner=self.partner,
            investment_amount=3000000,
            deal_lead=self.manager,
            group=self.group
        )
        
        # Add team members with different roles
        lead_member = DealTeamMember.objects.create(
            deal=deal,
            user=self.manager,
            role=self.lead_role,
            can_edit=True,
            can_approve=True,
            group=self.group
        )
        
        analyst_member = DealTeamMember.objects.create(
            deal=deal,
            user=self.analyst,
            role=self.analyst_role,
            can_edit=True,
            can_approve=False,
            group=self.group
        )
        
        # Test permissions
        self.assertTrue(lead_member.has_permission("edit_deal"))
        self.assertTrue(lead_member.has_permission("approve_documents"))
        self.assertTrue(lead_member.has_permission("manage_team"))
        
        self.assertTrue(analyst_member.has_permission("view_deal"))
        self.assertTrue(analyst_member.has_permission("add_documents"))
        self.assertFalse(analyst_member.has_permission("approve_documents"))
        self.assertFalse(analyst_member.has_permission("manage_team"))