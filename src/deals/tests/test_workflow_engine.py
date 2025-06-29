"""
Tests for the Deal Workflow Engine.
"""

from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Group
from ..models import (
    Deal, DealType, DealSource, WorkflowTemplate, DealStage, 
    DealTransition, DealActivity,
    MilestoneTemplate, DealMilestone, DealRole
)
from ..services.workflow_engine import WorkflowEngine

User = get_user_model()


class WorkflowEngineTests(TestCase):
    """Test workflow engine functionality."""
    
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
            last_name="Analyst"
        )
        self.user.groups.add(self.group)
        
        # Create deal type
        self.deal_type = DealType.objects.create(
            name="Series A",
            code="series_a",
            group=self.group
        )
        
        # Create workflow template
        self.workflow = WorkflowTemplate.objects.create(
            name="Standard Series A Workflow",
            code="standard_series_a",
            deal_type=self.deal_type,
            is_default=True,
            group=self.group
        )
        
        # Create stages
        self.stage1 = DealStage.objects.create(
            workflow_template=self.workflow,
            name="Initial Review",
            code="initial_review",
            stage_type=DealStage.StageType.SCREENING,
            order=1,
            target_duration_days=7,
            max_duration_days=14,
            required_documents=["pitch_deck", "financial_summary"],
            required_tasks=["initial_assessment"],
            group=self.group
        )
        
        self.stage2 = DealStage.objects.create(
            workflow_template=self.workflow,
            name="Due Diligence",
            code="due_diligence",
            stage_type=DealStage.StageType.ANALYSIS,
            order=2,
            target_duration_days=30,
            max_duration_days=45,
            required_documents=["financial_statements", "legal_agreements"],
            required_tasks=["financial_review", "legal_review"],
            entry_criteria={
                "nda_signed": {
                    "required": True,
                    "description": "NDA must be signed"
                },
                "minimum_irr": {
                    "value": 20,
                    "description": "Minimum IRR of 20%"
                }
            },
            group=self.group
        )
        
        self.stage3 = DealStage.objects.create(
            workflow_template=self.workflow,
            name="Negotiation",
            code="negotiation",
            stage_type=DealStage.StageType.APPROVAL,
            order=3,
            target_duration_days=14,
            required_documents=["term_sheet"],
            group=self.group
        )
        
        # Create deal source and deal
        self.deal_source = DealSource.objects.create(
            name="Partner Network",
            code="partner_net",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Test Deal",
            code="DEAL-001",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=5000000,
            irr_target=25.0,
            deal_lead=self.user,
            group=self.group
        )
    
    def test_workflow_engine_initialization(self):
        """Test workflow engine initialization."""
        engine = WorkflowEngine(self.deal)
        
        self.assertEqual(engine.deal, self.deal)
        self.assertEqual(engine.workflow, self.workflow)
    
    def test_get_current_stage(self):
        """Test getting current stage."""
        engine = WorkflowEngine(self.deal)
        
        # Initially no stage
        self.assertIsNone(engine.get_current_stage())
        
        # Set stage
        self.deal.current_stage = self.stage1
        self.deal.save()
        
        self.assertEqual(engine.get_current_stage(), self.stage1)
    
    def test_get_available_transitions_initial(self):
        """Test getting available transitions from initial state."""
        engine = WorkflowEngine(self.deal)
        
        transitions = engine.get_available_transitions()
        
        # Should have one transition to first stage
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0]['stage'], self.stage1)
        self.assertEqual(transitions[0]['status'], Deal.Status.INITIAL_REVIEW)
        self.assertTrue(transitions[0]['can_transition'])
    
    def test_get_available_transitions_with_requirements(self):
        """Test transitions with unmet requirements."""
        # Move to first stage
        self.deal.current_stage = self.stage1
        self.deal.status = Deal.Status.INITIAL_REVIEW
        self.deal.save()
        
        engine = WorkflowEngine(self.deal)
        transitions = engine.get_available_transitions()
        
        # Should have transitions to stage 2 and rejection
        self.assertEqual(len(transitions), 2)
        
        # Check stage 2 transition
        stage2_transition = next(t for t in transitions if t['stage'] == self.stage2)
        self.assertEqual(stage2_transition['stage'], self.stage2)
        self.assertFalse(stage2_transition['can_transition'])  # Requirements not met
        
        # Check requirements
        requirements = stage2_transition['requirements']
        doc_requirements = [r for r in requirements if r['type'] == 'document']
        self.assertEqual(len(doc_requirements), 2)  # financial_statements, legal_agreements
        
        criterion_requirements = [r for r in requirements if r['type'] == 'criterion']
        self.assertEqual(len(criterion_requirements), 2)  # nda_signed, minimum_irr
    
    def test_check_stage_requirements(self):
        """Test checking stage requirements."""
        engine = WorkflowEngine(self.deal)
        
        requirements = engine._check_stage_requirements(self.stage2)
        
        # Check document requirements
        doc_reqs = [r for r in requirements if r['type'] == 'document']
        self.assertEqual(len(doc_reqs), 2)
        self.assertFalse(all(r['met'] for r in doc_reqs))
        
        # Check criteria
        criteria = [r for r in requirements if r['type'] == 'criterion']
        self.assertEqual(len(criteria), 2)
        
        # Check minimum IRR criterion
        irr_criterion = next(r for r in criteria if r['name'] == 'minimum_irr')
        self.assertTrue(irr_criterion['met'])  # Deal has 25% IRR, requirement is 20%
    
    def test_transition_to_stage_success(self):
        """Test successful stage transition."""
        # Start from initial stage
        self.deal.current_stage = self.stage1
        self.deal.status = Deal.Status.INITIAL_REVIEW
        self.deal.save()
        
        # Meet requirements for stage 2
        # Would normally create file records, but we'll force transition
        engine = WorkflowEngine(self.deal)
        
        success, errors = engine.transition_to_stage(
            self.stage2,
            performed_by=self.user,
            reason="Requirements verified externally",
            force=True
        )
        
        self.assertTrue(success)
        self.assertEqual(len(errors), 0)
        
        # Refresh deal
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.current_stage, self.stage2)
        self.assertEqual(self.deal.status, Deal.Status.DUE_DILIGENCE)
        self.assertIsNotNone(self.deal.stage_entered_at)
        
        # Check transition record
        transition = DealTransition.objects.filter(deal=self.deal).first()
        self.assertIsNotNone(transition)
        self.assertEqual(transition.from_stage, self.stage1)
        self.assertEqual(transition.to_stage, self.stage2)
        self.assertEqual(transition.performed_by, self.user)
        
        # Check activity
        activity = DealActivity.objects.filter(
            deal=self.deal,
            activity_type=ActivityType.STAGE_CHANGED
        ).first()
        self.assertIsNotNone(activity)
    
    def test_transition_to_stage_blocked(self):
        """Test blocked stage transition."""
        self.deal.current_stage = self.stage1
        self.deal.save()
        
        engine = WorkflowEngine(self.deal)
        
        # Try to transition without meeting requirements
        success, errors = engine.transition_to_stage(
            self.stage2,
            performed_by=self.user,
            reason="Trying to move forward",
            force=False
        )
        
        self.assertFalse(success)
        self.assertTrue(len(errors) > 0)
        
        # Deal should not have changed
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.current_stage, self.stage1)
    
    def test_stage_duration_alerts(self):
        """Test stage duration alert detection."""
        # Set deal in stage with past entry date
        self.deal.current_stage = self.stage1
        self.deal.stage_entered_at = timezone.now() - timedelta(days=10)
        self.deal.save()
        
        engine = WorkflowEngine(self.deal)
        alerts = engine.check_stage_duration_alerts()
        
        # Should have warning (exceeded target of 7 days)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['type'], 'target_exceeded')
        self.assertEqual(alerts[0]['severity'], 'warning')
        
        # Test max duration exceeded
        self.deal.stage_entered_at = timezone.now() - timedelta(days=20)
        self.deal.save()
        
        alerts = engine.check_stage_duration_alerts()
        
        # Should have both warning and critical
        self.assertEqual(len(alerts), 2)
        critical_alert = next(a for a in alerts if a['severity'] == 'critical')
        self.assertEqual(critical_alert['type'], 'max_exceeded')
    
    def test_milestone_creation_on_transition(self):
        """Test milestone creation when entering a stage."""
        # Create milestone template for stage 2
        template = MilestoneTemplate.objects.create(
            name="Financial Review",
            code="financial_review",
            stage=self.stage2,
            days_from_stage_start=7,
            is_blocking=True,
            group=self.group
        )
        template.deal_types.add(self.deal_type)
        
        # Transition to stage 2
        self.deal.current_stage = self.stage1
        self.deal.save()
        
        engine = WorkflowEngine(self.deal)
        success, _ = engine.transition_to_stage(
            self.stage2,
            performed_by=self.user,
            force=True
        )
        
        self.assertTrue(success)
        
        # Check milestone was created
        milestone = DealMilestone.objects.filter(
            deal=self.deal,
            template=template
        ).first()
        
        self.assertIsNotNone(milestone)
        self.assertEqual(milestone.name, "Financial Review")
        self.assertTrue(milestone.is_blocking)
        self.assertEqual(
            milestone.due_date,
            (timezone.now() + timedelta(days=7)).date()
        )
    
    def test_evaluate_custom_criteria(self):
        """Test custom criterion evaluation."""
        engine = WorkflowEngine(self.deal)
        
        # Test minimum IRR
        self.assertTrue(
            engine._evaluate_criterion('minimum_irr', {'value': 20})
        )
        self.assertFalse(
            engine._evaluate_criterion('minimum_irr', {'value': 30})
        )
        
        # Test valuation complete
        self.assertFalse(
            engine._evaluate_criterion('valuation_complete', {})
        )
        
        self.deal.post_money_valuation = 25000000
        self.deal.save()
        
        self.assertTrue(
            engine._evaluate_criterion('valuation_complete', {})
        )
        
        # Test has deal lead
        self.assertTrue(
            engine._evaluate_criterion('has_deal_lead', {})
        )
        
        self.deal.deal_lead = None
        self.deal.save()
        
        self.assertFalse(
            engine._evaluate_criterion('has_deal_lead', {})
        )
    
    def test_blocking_milestone_prevents_transition(self):
        """Test that blocking milestones prevent stage transitions."""
        # Set current stage
        self.deal.current_stage = self.stage1
        self.deal.save()
        
        # Create a blocking milestone in current stage
        milestone = DealMilestone.objects.create(
            deal=self.deal,
            name="Blocking Milestone",
            due_date=timezone.now().date() + timedelta(days=7),
            stage=self.stage1,
            is_blocking=True,
            status=DealMilestone.Status.IN_PROGRESS,
            group=self.group
        )
        
        engine = WorkflowEngine(self.deal)
        requirements = engine._check_stage_requirements(self.stage2)
        
        # Should include the blocking milestone as unmet requirement
        milestone_reqs = [r for r in requirements if r['type'] == 'milestone']
        self.assertEqual(len(milestone_reqs), 1)
        self.assertFalse(milestone_reqs[0]['met'])
        
        # Complete the milestone
        milestone.status = DealMilestone.Status.COMPLETED
        milestone.save()
        
        # Now requirement should be met
        requirements = engine._check_stage_requirements(self.stage2)
        milestone_reqs = [r for r in requirements if r['type'] == 'milestone']
        self.assertEqual(len(milestone_reqs), 0)  # No blocking milestones
    
    def test_get_status_for_stage(self):
        """Test mapping stage types to deal statuses."""
        engine = WorkflowEngine(self.deal)
        
        test_cases = [
            (DealStage.StageType.ORIGINATION, Deal.Status.PIPELINE),
            (DealStage.StageType.SCREENING, Deal.Status.INITIAL_REVIEW),
            (DealStage.StageType.ANALYSIS, Deal.Status.DUE_DILIGENCE),
            (DealStage.StageType.APPROVAL, Deal.Status.NEGOTIATION),
            (DealStage.StageType.EXECUTION, Deal.Status.DOCUMENTATION),
            (DealStage.StageType.CLOSING, Deal.Status.CLOSING),
            (DealStage.StageType.POST_CLOSING, Deal.Status.COMPLETED),
        ]
        
        for stage_type, expected_status in test_cases:
            stage = DealStage(stage_type=stage_type)
            status = engine._get_status_for_stage(stage)
            self.assertEqual(status, expected_status)