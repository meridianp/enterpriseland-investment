"""
Tests for root aggregate models - Phase 6.

Comprehensive test suite for due diligence case management,
workflow orchestration, and cross-cutting concerns.
"""

from decimal import Decimal
from datetime import date, datetime, timedelta
import json

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import Group
from assessments.partner_models import DevelopmentPartner
from assessments.scheme_models import PBSAScheme, DevelopmentStage
from assessments.assessment_models import (
    Assessment, AssessmentType, AssessmentStatus, DecisionBand
)
from assessments.advanced_models import (
    RegulatoryCompliance, PerformanceMetric, ESGAssessment, AuditTrail
)
from assessments.root_aggregate import (
    DueDiligenceCase, CaseChecklistItem, CaseTimeline, create_standard_checklist
)
from assessments.enums import Currency, RiskLevel

User = get_user_model()


class DueDiligenceCaseTestCase(TestCase):
    """Test due diligence case functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(name="Test DD Group")
        
        # Create users
        self.lead_assessor = User.objects.create_user(
            email="lead@example.com",
            role="assessor",
            first_name="Lead",
            last_name="Assessor"
        )
        
        self.team_member = User.objects.create_user(
            email="team@example.com",
            role="analyst",
            first_name="Team",
            last_name="Member"
        )
        
        self.decision_maker = User.objects.create_user(
            email="decision@example.com",
            role="manager",
            first_name="Decision",
            last_name="Maker"
        )
        
        # Create partner and schemes
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name="Test Development Partner",
            assessment_priority="high"
        )
        
        self.scheme1 = PBSAScheme.objects.create(
            group=self.group,
            scheme_name="Test Scheme 1",
            scheme_reference="TS001",
            developer=self.partner,
            total_beds=300,
            development_stage=DevelopmentStage.OPERATIONAL,
            total_development_cost_amount=Decimal('20000000'),
            total_development_cost_currency=Currency.GBP
        )
        
        self.scheme2 = PBSAScheme.objects.create(
            group=self.group,
            scheme_name="Test Scheme 2",
            scheme_reference="TS002",
            developer=self.partner,
            total_beds=250,
            development_stage=DevelopmentStage.PLANNING,
            total_development_cost_amount=Decimal('15000000'),
            total_development_cost_currency=Currency.GBP
        )
    
    def test_case_creation(self):
        """Test creating a due diligence case."""
        case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name="Test Due Diligence Case",
            case_type='full_dd',
            primary_partner=self.partner,
            priority='high',
            target_completion_date=date.today() + timedelta(days=30),
            lead_assessor=self.lead_assessor,
            total_investment_amount=Decimal('35000000'),
            total_investment_currency=Currency.GBP
        )
        
        # Add schemes
        case.schemes.add(self.scheme1, self.scheme2)
        
        # Add team members
        case.assessment_team.add(self.team_member)
        
        self.assertEqual(case.case_type, 'full_dd')
        self.assertEqual(case.primary_partner, self.partner)
        self.assertEqual(case.schemes.count(), 2)
        self.assertEqual(case.case_status, 'initiated')
        self.assertIsNotNone(case.case_reference)
        self.assertTrue(case.case_reference.startswith('DD'))
    
    def test_case_reference_generation(self):
        """Test automatic case reference generation."""
        # Create first case
        case1 = DueDiligenceCase.objects.create(
            group=self.group,
            case_name="First Case",
            lead_assessor=self.lead_assessor
        )
        
        # Create second case
        case2 = DueDiligenceCase.objects.create(
            group=self.group,
            case_name="Second Case",
            lead_assessor=self.lead_assessor
        )
        
        year = timezone.now().year
        self.assertEqual(case1.case_reference, f'DD{year}0001')
        self.assertEqual(case2.case_reference, f'DD{year}0002')
    
    def test_overdue_detection(self):
        """Test overdue case detection."""
        # Create case due yesterday
        case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name="Overdue Case",
            lead_assessor=self.lead_assessor,
            target_completion_date=date.today() - timedelta(days=1)
        )
        
        self.assertTrue(case.is_overdue)
        self.assertEqual(case.days_until_due, -1)
        
        # Create case due in future
        future_case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name="Future Case",
            lead_assessor=self.lead_assessor,
            target_completion_date=date.today() + timedelta(days=10)
        )
        
        self.assertFalse(future_case.is_overdue)
        self.assertEqual(future_case.days_until_due, 10)
        
        # Complete the overdue case
        case.case_status = 'completed'
        case.save()
        
        self.assertFalse(case.is_overdue)
        self.assertIsNone(case.days_until_due)
    
    def test_completion_percentage(self):
        """Test completion percentage calculation."""
        case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name="Progress Test Case",
            lead_assessor=self.lead_assessor
        )
        
        # Test different statuses
        status_percentages = [
            ('initiated', 10),
            ('data_collection', 25),
            ('analysis', 50),
            ('review', 75),
            ('decision_pending', 90),
            ('approved', 100),
            ('completed', 100),
        ]
        
        for status, expected_percentage in status_percentages:
            case.case_status = status
            self.assertEqual(case.completion_percentage, expected_percentage)
    
    def test_workflow_transition(self):
        """Test workflow status transitions."""
        case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name="Workflow Test Case",
            lead_assessor=self.lead_assessor,
            primary_partner=self.partner
        )
        
        # Valid transition
        case.transition_status('data_collection', self.lead_assessor, 'Starting data collection')
        case.refresh_from_db()
        self.assertEqual(case.case_status, 'data_collection')
        self.assertIn('history', case.workflow_state)
        self.assertEqual(len(case.workflow_state['history']), 1)
        
        # Invalid transition
        with self.assertRaises(ValidationError):
            case.transition_status('approved', self.lead_assessor)
        
        # Check audit trail was created
        audit_entry = AuditTrail.objects.filter(
            entity_type='DueDiligenceCase',
            entity_id=case.id,
            action_type='update'
        ).first()
        
        self.assertIsNotNone(audit_entry)
        self.assertEqual(audit_entry.user, self.lead_assessor)
    
    def test_decision_making(self):
        """Test decision making process."""
        case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name="Decision Test Case",
            lead_assessor=self.lead_assessor,
            primary_partner=self.partner,
            case_status='decision_pending'
        )
        
        case.schemes.add(self.scheme1)
        
        # Make decision with conditions
        conditions = ['Complete ESG assessment', 'Quarterly performance reviews']
        case.make_decision('conditional', self.decision_maker, conditions, 'Approved with conditions')
        
        case.refresh_from_db()
        self.assertEqual(case.final_decision, 'conditional')
        self.assertEqual(case.decision_maker, self.decision_maker)
        self.assertEqual(case.decision_date, date.today())
        self.assertEqual(case.conditions, conditions)
        self.assertEqual(case.case_status, 'approved')
        
        # Check audit trail
        audit_entry = AuditTrail.objects.filter(
            entity_type='DueDiligenceCase',
            entity_id=case.id,
            action_type='approve'
        ).first()
        
        self.assertIsNotNone(audit_entry)
        self.assertEqual(audit_entry.risk_assessment, RiskLevel.HIGH)
    
    def test_compliance_status_aggregation(self):
        """Test compliance status aggregation."""
        case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name="Compliance Test Case",
            lead_assessor=self.lead_assessor,
            primary_partner=self.partner
        )
        
        case.schemes.add(self.scheme1)
        
        # Create compliance records
        RegulatoryCompliance.objects.create(
            group=self.group,
            partner=self.partner,
            jurisdiction='GB',
            regulatory_framework='Test Framework 1',
            regulatory_body='Test Authority',
            compliance_category='financial',
            requirement_title='Financial Compliance',
            requirement_description='Test requirement',
            compliance_status='compliant',
            compliance_risk_level=RiskLevel.LOW
        )
        
        RegulatoryCompliance.objects.create(
            group=self.group,
            scheme=self.scheme1,
            jurisdiction='GB',
            regulatory_framework='Test Framework 2',
            regulatory_body='Test Authority',
            compliance_category='building',
            requirement_title='Building Compliance',
            requirement_description='Test requirement',
            compliance_status='non_compliant',
            compliance_risk_level=RiskLevel.HIGH
        )
        
        RegulatoryCompliance.objects.create(
            group=self.group,
            partner=self.partner,
            jurisdiction='GB',
            regulatory_framework='Test Framework 3',
            regulatory_body='Test Authority',
            compliance_category='environmental',
            requirement_title='Environmental Compliance',
            requirement_description='Test requirement',
            compliance_status='pending',
            compliance_risk_level=RiskLevel.MEDIUM
        )
        
        # Get compliance status
        compliance_status = case.get_compliance_status()
        
        self.assertEqual(compliance_status['total_requirements'], 3)
        self.assertEqual(compliance_status['compliant'], 1)
        self.assertEqual(compliance_status['non_compliant'], 1)
        self.assertEqual(compliance_status['pending'], 1)
        self.assertAlmostEqual(compliance_status['compliance_rate'], 33.3, 1)
        self.assertEqual(compliance_status['high_risk_items'], 1)
    
    def test_performance_summary_aggregation(self):
        """Test performance metrics aggregation."""
        case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name="Performance Test Case",
            lead_assessor=self.lead_assessor,
            primary_partner=self.partner
        )
        
        case.schemes.add(self.scheme1)
        
        # Create performance metrics
        metrics = [
            {
                'name': 'Occupancy Rate',
                'value': Decimal('96.0'),
                'target': Decimal('95.0'),
                'trend': 'improving',
                'action': False
            },
            {
                'name': 'Cost per Bed',
                'value': Decimal('850.0'),
                'target': Decimal('800.0'),
                'trend': 'stable',
                'action': True
            },
            {
                'name': 'Student Satisfaction',
                'value': Decimal('3.8'),
                'target': Decimal('4.0'),
                'trend': 'declining',
                'action': True
            }
        ]
        
        for metric in metrics:
            PerformanceMetric.objects.create(
                group=self.group,
                partner=self.partner,
                metric_name=metric['name'],
                metric_category='operational',
                measurement_date=date.today(),
                metric_value=metric['value'],
                target_value=metric['target'],
                trend_direction=metric['trend'],
                action_required=metric['action'],
                data_source='Test System',
                data_quality_score=4,
                measurement_frequency='monthly'
            )
        
        # Get performance summary
        performance = case.get_performance_summary()
        
        self.assertEqual(performance['total_metrics'], 3)
        self.assertEqual(performance['meeting_targets'], 1)  # Only occupancy rate
        self.assertAlmostEqual(performance['target_achievement_rate'], 33.3, 1)
        self.assertEqual(performance['requiring_action'], 2)
        self.assertEqual(performance['metrics_breakdown']['improving'], 1)
        self.assertEqual(performance['metrics_breakdown']['declining'], 1)
    
    def test_esg_summary_aggregation(self):
        """Test ESG assessment aggregation."""
        case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name="ESG Test Case",
            lead_assessor=self.lead_assessor,
            primary_partner=self.partner
        )
        
        # Create ESG assessment
        esg = ESGAssessment.objects.create(
            group=self.group,
            partner=self.partner,
            assessment_name='Test ESG Assessment',
            assessment_framework='gri',
            assessment_period_start=date(2024, 1, 1),
            assessment_period_end=date(2024, 12, 31),
            environmental_score=4,
            social_score=3,
            governance_score=4,
            carbon_footprint_tonnes=Decimal('200.0'),
            renewable_energy_pct=Decimal('45.0')
        )
        
        # Get ESG summary
        esg_summary = case.get_esg_summary()
        
        self.assertTrue(esg_summary['has_esg_assessment'])
        self.assertEqual(esg_summary['latest_assessment_date'], date(2024, 12, 31))
        self.assertEqual(esg_summary['overall_score'], 3.7)  # (4*0.4 + 3*0.3 + 4*0.3)
        self.assertEqual(esg_summary['rating'], 'A')
        self.assertEqual(esg_summary['scores']['environmental'], 4)
        self.assertEqual(esg_summary['carbon_footprint'], 200.0)
        self.assertEqual(esg_summary['renewable_energy_pct'], 45.0)
    
    def test_overall_risk_calculation(self):
        """Test overall risk calculation."""
        case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name="Risk Test Case",
            lead_assessor=self.lead_assessor,
            primary_partner=self.partner
        )
        
        case.schemes.add(self.scheme1)
        
        # Create various risk factors
        
        # High compliance risk (non-compliant items)
        RegulatoryCompliance.objects.create(
            group=self.group,
            partner=self.partner,
            jurisdiction='GB',
            regulatory_framework='Test Framework',
            regulatory_body='Test Authority',
            compliance_category='financial',
            requirement_title='Critical Compliance',
            requirement_description='Test',
            compliance_status='non_compliant',
            compliance_risk_level=RiskLevel.HIGH
        )
        
        # Poor performance (low target achievement)
        PerformanceMetric.objects.create(
            group=self.group,
            scheme=self.scheme1,
            metric_name='Key Metric',
            metric_category='operational',
            measurement_date=date.today(),
            metric_value=Decimal('60.0'),
            target_value=Decimal('95.0'),
            data_source='Test',
            measurement_frequency='monthly'
        )
        
        # Poor ESG rating
        ESGAssessment.objects.create(
            group=self.group,
            partner=self.partner,
            assessment_name='Poor ESG',
            assessment_framework='gri',
            assessment_period_start=date(2024, 1, 1),
            assessment_period_end=date(2024, 12, 31),
            environmental_score=2,
            social_score=2,
            governance_score=2
        )
        
        # Calculate overall risk
        risk_level = case.calculate_overall_risk()
        
        # Should be HIGH due to multiple high-risk factors
        self.assertEqual(risk_level, RiskLevel.HIGH)
    
    def test_aggregated_scores_update(self):
        """Test aggregated scores update."""
        case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name="Score Aggregation Test",
            lead_assessor=self.lead_assessor,
            primary_partner=self.partner
        )
        
        case.schemes.add(self.scheme1)
        
        # Create assessments
        Assessment.objects.create(
            group=self.group,
            assessment_name='Partner Assessment',
            assessment_type=AssessmentType.PARTNER,
            partner=self.partner,
            status=AssessmentStatus.COMPLETED,
            decision_band=DecisionBand.ACCEPTABLE,
            total_weighted_score=140,
            max_possible_score=200,
            assessment_date=date.today(),
            assessor=self.lead_assessor
        )
        
        Assessment.objects.create(
            group=self.group,
            assessment_name='Scheme Assessment',
            assessment_type=AssessmentType.SCHEME,
            scheme=self.scheme1,
            status=AssessmentStatus.COMPLETED,
            decision_band=DecisionBand.PREMIUM_PRIORITY,
            total_weighted_score=180,
            max_possible_score=200,
            assessment_date=date.today(),
            assessor=self.lead_assessor
        )
        
        # Update aggregated scores
        case.update_aggregated_scores()
        
        self.assertIn('by_type', case.aggregated_scores)
        self.assertIn('overall', case.aggregated_scores)
        self.assertIn('decision_distribution', case.aggregated_scores)
        
        overall = case.aggregated_scores['overall']
        self.assertEqual(overall['total_assessments'], 2)
        self.assertEqual(overall['average_score'], 160.0)  # (140 + 180) / 2
        self.assertEqual(overall['highest_score'], 180.0)
        self.assertEqual(overall['lowest_score'], 140.0)
    
    def test_comprehensive_summary(self):
        """Test comprehensive case summary generation."""
        case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name="Comprehensive Test Case",
            case_type='full_dd',
            primary_partner=self.partner,
            priority='high',
            target_completion_date=date.today() + timedelta(days=30),
            lead_assessor=self.lead_assessor,
            case_status='analysis',
            overall_risk_level=RiskLevel.MEDIUM
        )
        
        case.schemes.add(self.scheme1, self.scheme2)
        case.assessment_team.add(self.team_member)
        
        # Get comprehensive summary
        summary = case.get_comprehensive_summary()
        
        # Verify structure
        self.assertIn('case_info', summary)
        self.assertIn('entities', summary)
        self.assertIn('assessments', summary)
        self.assertIn('compliance', summary)
        self.assertIn('performance', summary)
        self.assertIn('esg', summary)
        self.assertIn('risk', summary)
        self.assertIn('decision', summary)
        self.assertIn('team', summary)
        
        # Verify case info
        self.assertEqual(summary['case_info']['reference'], case.case_reference)
        self.assertEqual(summary['case_info']['completion_percentage'], 50)
        self.assertFalse(summary['case_info']['is_overdue'])
        
        # Verify entities
        self.assertEqual(summary['entities']['primary_partner'], self.partner.company_name)
        self.assertEqual(summary['entities']['scheme_count'], 2)
        
        # Verify team
        self.assertEqual(summary['team']['lead_assessor'], self.lead_assessor.get_full_name())
        self.assertEqual(summary['team']['team_size'], 1)


class CaseChecklistTestCase(TestCase):
    """Test case checklist functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(name="Checklist Test Group")
        self.user = User.objects.create_user(
            email="checklist@example.com",
            role="assessor"
        )
        
        self.case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name="Checklist Test Case",
            lead_assessor=self.user
        )
    
    def test_checklist_item_creation(self):
        """Test creating checklist items."""
        item = CaseChecklistItem.objects.create(
            case=self.case,
            group=self.group,
            category='documentation',
            item_name='Financial Statements',
            description='Obtain 3 years of audited financial statements',
            is_required=True,
            due_date=date.today() + timedelta(days=7)
        )
        
        self.assertEqual(item.case, self.case)
        self.assertFalse(item.is_completed)
        self.assertIsNone(item.completed_by)
    
    def test_mark_checklist_complete(self):
        """Test marking checklist items as complete."""
        item = CaseChecklistItem.objects.create(
            case=self.case,
            group=self.group,
            category='financial',
            item_name='Financial Analysis',
            is_required=True
        )
        
        # Mark complete
        item.mark_complete(self.user, 'Analysis completed successfully')
        
        item.refresh_from_db()
        self.assertTrue(item.is_completed)
        self.assertEqual(item.completed_by, self.user)
        self.assertIsNotNone(item.completed_at)
        self.assertEqual(item.notes, 'Analysis completed successfully')
        
        # Check audit trail
        audit = AuditTrail.objects.filter(
            entity_type='CaseChecklistItem',
            entity_id=item.id
        ).first()
        
        self.assertIsNotNone(audit)
    
    def test_standard_checklist_creation(self):
        """Test creating standard checklist for a case."""
        case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name="Standard Checklist Test",
            case_type='full_dd',
            lead_assessor=self.user
        )
        
        # Create standard checklist
        create_standard_checklist(case)
        
        # Verify checklist items were created
        checklist_items = CaseChecklistItem.objects.filter(case=case)
        self.assertGreater(checklist_items.count(), 10)
        
        # Check categories are covered
        categories = checklist_items.values_list('category', flat=True).distinct()
        expected_categories = [
            'documentation', 'financial', 'legal', 'compliance',
            'esg', 'technical', 'market', 'operational'
        ]
        
        for category in expected_categories:
            self.assertIn(category, categories)
        
        # Check timeline event was created
        timeline_event = CaseTimeline.objects.filter(
            case=case,
            event_type='created'
        ).first()
        
        self.assertIsNotNone(timeline_event)
        self.assertTrue(timeline_event.is_significant)


class CaseTimelineTestCase(TestCase):
    """Test case timeline functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(name="Timeline Test Group")
        self.user = User.objects.create_user(
            email="timeline@example.com",
            role="assessor"
        )
        
        self.case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name="Timeline Test Case",
            lead_assessor=self.user
        )
    
    def test_timeline_event_creation(self):
        """Test creating timeline events."""
        event = CaseTimeline.objects.create(
            case=self.case,
            group=self.group,
            event_type='status_change',
            event_title='Status Changed to Analysis',
            event_description='Case moved from data collection to analysis phase',
            created_by=self.user,
            is_significant=True,
            metadata={
                'from_status': 'data_collection',
                'to_status': 'analysis'
            }
        )
        
        self.assertEqual(event.case, self.case)
        self.assertEqual(event.event_type, 'status_change')
        self.assertTrue(event.is_significant)
        self.assertEqual(event.metadata['from_status'], 'data_collection')
    
    def test_timeline_ordering(self):
        """Test timeline events are ordered by date."""
        # Create events in random order
        event1 = CaseTimeline.objects.create(
            case=self.case,
            group=self.group,
            event_type='note',
            event_title='First Event',
            event_description='First',
            created_by=self.user,
            event_date=timezone.now() - timedelta(days=2)
        )
        
        event2 = CaseTimeline.objects.create(
            case=self.case,
            group=self.group,
            event_type='milestone',
            event_title='Latest Event',
            event_description='Latest',
            created_by=self.user,
            event_date=timezone.now()
        )
        
        event3 = CaseTimeline.objects.create(
            case=self.case,
            group=self.group,
            event_type='assessment_added',
            event_title='Middle Event',
            event_description='Middle',
            created_by=self.user,
            event_date=timezone.now() - timedelta(days=1)
        )
        
        # Get ordered events
        events = list(CaseTimeline.objects.filter(case=self.case))
        
        # Should be ordered newest first
        self.assertEqual(events[0], event2)  # Latest
        self.assertEqual(events[1], event3)  # Middle
        self.assertEqual(events[2], event1)  # First
    
    def test_timeline_with_workflow_transitions(self):
        """Test timeline integration with workflow transitions."""
        # Transition case status
        self.case.transition_status('data_collection', self.user, 'Starting data collection')
        
        # Should create timeline event through workflow
        # (In real implementation, this would be done in transition_status method)
        CaseTimeline.objects.create(
            case=self.case,
            group=self.group,
            event_type='status_change',
            event_title='Status changed to Data Collection',
            event_description='Case transitioned from initiated to data_collection',
            created_by=self.user,
            metadata={
                'from_status': 'initiated',
                'to_status': 'data_collection'
            }
        )
        
        timeline_events = CaseTimeline.objects.filter(
            case=self.case,
            event_type='status_change'
        )
        
        self.assertEqual(timeline_events.count(), 1)