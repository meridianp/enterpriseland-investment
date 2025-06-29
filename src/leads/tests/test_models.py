"""
Comprehensive tests for leads models.

Tests all model functionality including validation, properties, methods,
and business logic to ensure 95%+ code coverage.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from django.contrib.auth import get_user_model

# from accounts.models import Group
# from market_intelligence.models import TargetCompany
from ..models import LeadScoringModel, Lead, LeadActivity
from .factories import (
    LeadScoringModelFactory, LeadFactory, LeadActivityFactory,
    QualifiedLeadFactory, ConvertedLeadFactory, UnqualifiedLeadFactory,
    TestDataMixin
)

User = get_user_model()


class LeadScoringModelTest(TestCase, TestDataMixin):
    """Test LeadScoringModel functionality."""
    
    def setUp(self):
        super().setUp()
    
    def test_lead_scoring_model_creation(self):
        """Test basic lead scoring model creation."""
        model = LeadScoringModelFactory.create(group=self.group1)
        
        self.assertIsNotNone(model.id)
        self.assertEqual(model.group, self.group1)
        self.assertTrue(model.is_active)
        self.assertIsNotNone(model.created_at)
        self.assertIsNotNone(model.updated_at)
    
    def test_lead_scoring_model_str_representation(self):
        """Test string representation of lead scoring model."""
        model = LeadScoringModelFactory.create(
            group=self.group1,
            name="PBSA Lead Scorer",
            version="2.1.0",
            scoring_method=LeadScoringModel.ScoringMethod.WEIGHTED_AVERAGE
        )
        
        expected = "PBSA Lead Scorer v2.1.0 (Weighted Average)"
        self.assertEqual(str(model), expected)
    
    def test_unique_name_version_per_group(self):
        """Test that model name+version must be unique within a group."""
        LeadScoringModelFactory.create(
            group=self.group1,
            name="Unique Model",
            version="1.0.0"
        )
        
        # Should raise IntegrityError for duplicate name+version in same group
        with self.assertRaises(IntegrityError):
            LeadScoringModelFactory.create(
                group=self.group1,
                name="Unique Model",
                version="1.0.0"
            )
    
    def test_same_name_different_groups(self):
        """Test that same model name can exist in different groups."""
        model1 = LeadScoringModelFactory.create(
            group=self.group1,
            name="Scoring Model"
        )
        model2 = LeadScoringModelFactory.create(
            group=self.group2,
            name="Scoring Model"
        )
        
        self.assertEqual(model1.name, model2.name)
        self.assertNotEqual(model1.group, model2.group)
    
    def test_scoring_method_choices(self):
        """Test all scoring method choices are valid."""
        for choice_value, choice_label in LeadScoringModel.ScoringMethod.choices:
            model = LeadScoringModelFactory.create(
                group=self.group1,
                scoring_method=choice_value
            )
            self.assertEqual(model.scoring_method, choice_value)
    
    def test_threshold_values(self):
        """Test threshold values are set correctly."""
        model = LeadScoringModelFactory.create(
            group=self.group1,
            qualification_threshold=70.0,
            high_priority_threshold=85.0,
            auto_convert_threshold=95.0
        )
        
        self.assertEqual(model.qualification_threshold, 70.0)
        self.assertEqual(model.high_priority_threshold, 85.0)
        self.assertEqual(model.auto_convert_threshold, 95.0)
    
    def test_calculate_score_weighted_average(self):
        """Test score calculation for weighted average model."""
        model = LeadScoringModelFactory.create(
            group=self.group1,
            scoring_method=LeadScoringModel.ScoringMethod.WEIGHTED_AVERAGE,
            status=LeadScoringModel.ModelStatus.ACTIVE,
            component_weights={
                'business_alignment': 0.25,
                'market_presence': 0.20,
                'financial_strength': 0.20,
                'strategic_fit': 0.20,
                'geographic_fit': 0.10,
                'engagement_potential': 0.05
            }
        )
        
        lead_data = {
            'business_alignment': 80,
            'market_presence': 90,
            'financial_strength': 70,
            'strategic_fit': 100,
            'geographic_fit': 60,
            'engagement_potential': 80
        }
        
        score = model.calculate_score(lead_data)
        
        # Check overall score
        expected_score = (80 * 0.25) + (90 * 0.20) + (70 * 0.20) + (100 * 0.20) + (60 * 0.10) + (80 * 0.05)
        self.assertAlmostEqual(score, expected_score, places=2)
        
        # Score calculation doesn't return breakdown in the model
        # Just verify the score is calculated correctly
    
    def test_calculate_score_inactive_model(self):
        """Test score calculation for inactive model raises error."""
        model = LeadScoringModelFactory.create(
            group=self.group1,
            status=LeadScoringModel.ModelStatus.DRAFT
        )
        
        lead_data = {
            'business_alignment': 80,
            'market_presence': 90
        }
        
        # Inactive model should raise ValueError
        with self.assertRaises(ValueError) as context:
            model.calculate_score(lead_data)
        
        self.assertIn("Cannot score with inactive model", str(context.exception))
    
    def test_performance_metrics(self):
        """Test performance metrics fields."""
        model = LeadScoringModelFactory.create(
            group=self.group1,
            accuracy_score=0.85,
            precision_score=0.82,
            recall_score=0.78
        )
        
        # Check metrics were set
        self.assertEqual(model.accuracy_score, 0.85)
        self.assertEqual(model.precision_score, 0.82)
        self.assertEqual(model.recall_score, 0.78)
        
        # Check F1 score calculation
        expected_f1 = 2 * (0.82 * 0.78) / (0.82 + 0.78)
        self.assertAlmostEqual(model.f1_score, expected_f1, places=4)
    
    def test_component_weights_json_field(self):
        """Test component_weights JSON field functionality."""
        weights = {
            'business_alignment': 0.3,
            'market_presence': 0.3,
            'financial_strength': 0.2,
            'strategic_fit': 0.2
        }
        
        model = LeadScoringModelFactory.create(
            group=self.group1,
            component_weights=weights
        )
        
        self.assertEqual(model.component_weights, weights)
        self.assertIsInstance(model.component_weights, dict)
    
    def test_activate_model(self):
        """Test model activation functionality."""
        # Create an active model
        old_model = LeadScoringModelFactory.create(
            group=self.group1,
            status=LeadScoringModel.ModelStatus.ACTIVE
        )
        
        # Create a new model to activate
        new_model = LeadScoringModelFactory.create(
            group=self.group1,
            status=LeadScoringModel.ModelStatus.DRAFT
        )
        
        # Activate the new model
        new_model.activate()
        
        # Refresh models from DB
        old_model.refresh_from_db()
        new_model.refresh_from_db()
        
        # Check old model is archived
        self.assertEqual(old_model.status, LeadScoringModel.ModelStatus.ARCHIVED)
        self.assertIsNotNone(old_model.deactivated_at)
        
        # Check new model is active
        self.assertEqual(new_model.status, LeadScoringModel.ModelStatus.ACTIVE)
        self.assertIsNotNone(new_model.activated_at)
    
    def test_is_active_property(self):
        """Test is_active property based on status."""
        # Test active model
        active_model = LeadScoringModelFactory.create(
            group=self.group1,
            status=LeadScoringModel.ModelStatus.ACTIVE
        )
        self.assertTrue(active_model.is_active)
        
        # Test draft model
        draft_model = LeadScoringModelFactory.create(
            group=self.group1,
            status=LeadScoringModel.ModelStatus.DRAFT
        )
        self.assertFalse(draft_model.is_active)


class LeadModelTest(TestCase, TestDataMixin):
    """Test Lead model functionality."""
    
    def setUp(self):
        super().setUp()
        # Use the factory instead of direct creation
        self.target_company = TargetCompanyFactory.create(
            group=self.group1,
            name="Test PBSA Developer"
        )
    
    def test_lead_creation(self):
        """Test basic lead creation."""
        lead = LeadFactory.create(
            group=self.group1,
            market_intelligence_target=self.target_company
        )
        
        self.assertIsNotNone(lead.id)
        self.assertEqual(lead.group, self.group1)
        self.assertEqual(lead.market_intelligence_target, self.target_company)
        self.assertIsNotNone(lead.created_at)
        self.assertIsNotNone(lead.updated_at)
    
    def test_lead_str_representation(self):
        """Test string representation of lead."""
        lead = LeadFactory.create(
            group=self.group1,
            company_name="Test Company",
            primary_contact_name="John Doe",
            current_score=85.5
        )
        
        expected = "Test Company (New)"
        self.assertEqual(str(lead), expected)
    
    def test_lead_properties(self):
        """Test lead property methods."""
        # Create a qualified lead
        lead = LeadFactory.create(
            group=self.group1,
            current_score=75.0,
            status=Lead.LeadStatus.QUALIFIED
        )
        
        # Test is_qualified property
        self.assertTrue(lead.is_qualified)
        
        # Test is_high_priority property
        lead.current_score = 90.0
        lead.save()
        self.assertTrue(lead.is_high_priority)
    
    def test_same_company_different_groups(self):
        """Test that same company can have leads in different groups."""
        lead1 = LeadFactory.create(
            group=self.group1,
            company_name="Test Company"
        )
        lead2 = LeadFactory.create(
            group=self.group2,
            company_name="Test Company"
        )
        
        self.assertEqual(lead1.company_name, lead2.company_name)
        self.assertNotEqual(lead1.group, lead2.group)
    
    def test_lead_status_choices(self):
        """Test all lead status choices are valid."""
        for choice_value, choice_label in Lead.LeadStatus.choices:
            lead = LeadFactory.create(
                group=self.group1,
                status=choice_value
            )
            self.assertEqual(lead.status, choice_value)
    
    def test_priority_choices(self):
        """Test all priority choices are valid."""
        for choice_value, choice_label in Lead.Priority.choices:
            lead = LeadFactory.create(
                group=self.group1,
                priority=choice_value
            )
            self.assertEqual(lead.priority, choice_value)
    
    def test_lead_source_choices(self):
        """Test all lead source choices are valid."""
        for choice_value, choice_label in Lead.LeadSource.choices:
            lead = LeadFactory.create(
                group=self.group1,
                source=choice_value
            )
            self.assertEqual(lead.source, choice_value)
    
    def test_is_qualified_property(self):
        """Test is_qualified property based on status."""
        qualified_lead = LeadFactory.create(
            group=self.group1,
            status=Lead.LeadStatus.QUALIFIED
        )
        self.assertTrue(qualified_lead.is_qualified)
        
        unqualified_lead = LeadFactory.create(
            group=self.group1,
            status=Lead.LeadStatus.UNQUALIFIED
        )
        self.assertFalse(unqualified_lead.is_qualified)
        
        new_lead = LeadFactory.create(
            group=self.group1,
            status=Lead.LeadStatus.NEW
        )
        self.assertFalse(new_lead.is_qualified)
    
    def test_is_converted_property(self):
        """Test is_converted property based on status."""
        converted_lead = LeadFactory.create(
            group=self.group1,
            status=Lead.LeadStatus.CONVERTED
        )
        self.assertTrue(converted_lead.is_converted)
        
        qualified_lead = LeadFactory.create(
            group=self.group1,
            status=Lead.LeadStatus.QUALIFIED
        )
        self.assertFalse(qualified_lead.is_converted)
    
    def test_days_since_creation_property(self):
        """Test days_since_creation calculation."""
        past_date = timezone.now() - timedelta(days=7)
        lead = LeadFactory.create(group=self.group1)
        lead.created_at = past_date
        lead.save()
        
        self.assertEqual(lead.days_since_creation, 7)
    
    def test_days_in_current_status_property(self):
        """Test days_in_current_status calculation."""
        past_date = timezone.now() - timedelta(days=3)
        lead = LeadFactory.create(
            group=self.group1,
            last_status_change=past_date
        )
        
        self.assertEqual(lead.days_in_current_status, 3)
    
    def test_days_in_current_status_no_change(self):
        """Test days_in_current_status when no status change recorded."""
        lead = LeadFactory.create(
            group=self.group1,
            last_status_change=None
        )
        
        # Should use created_at when last_status_change is None
        self.assertEqual(lead.days_in_current_status, 0)
    
    def test_update_score_method(self):
        """Test update_score method."""
        model = LeadScoringModelFactory.create(group=self.group1)
        lead = LeadFactory.create(
            group=self.group1,
            scoring_model=model
        )
        
        new_score = 85.5
        breakdown = {'criterion1': 90, 'criterion2': 81}
        confidence = 0.92
        
        lead.update_score(new_score, breakdown, confidence)
        
        self.assertEqual(lead.lead_score, new_score)
        self.assertEqual(lead.score_breakdown, breakdown)
        self.assertEqual(lead.confidence_score, confidence)
        self.assertIsNotNone(lead.scoring_timestamp)
    
    def test_add_activity_method(self):
        """Test add_activity convenience method."""
        lead = LeadFactory.create(group=self.group1)
        
        activity = lead.add_activity(
            activity_type=LeadActivity.ActivityType.NOTE,
            description="Test note",
            created_by=self.analyst_user
        )
        
        self.assertEqual(activity.lead, lead)
        self.assertEqual(activity.activity_type, LeadActivity.ActivityType.NOTE)
        self.assertEqual(activity.description, "Test note")
        self.assertEqual(activity.created_by, self.analyst_user)
    
    def test_lead_score_validation(self):
        """Test lead score validation range."""
        # Valid scores
        for score in [0.0, 50.0, 100.0]:
            lead = LeadFactory.create(
                group=self.group1,
                lead_score=score
            )
            self.assertEqual(lead.lead_score, score)
    
    def test_confidence_score_validation(self):
        """Test confidence score validation range."""
        # Valid scores
        for score in [0.0, 0.5, 1.0]:
            lead = LeadFactory.create(
                group=self.group1,
                confidence_score=score
            )
            self.assertEqual(lead.confidence_score, score)
    
    def test_tags_array_field(self):
        """Test tags ArrayField functionality."""
        tags = ['pbsa', 'uk', 'high-value', 'developer']
        lead = LeadFactory.create(
            group=self.group1,
            tags=tags
        )
        
        self.assertEqual(lead.tags, tags)
        self.assertIsInstance(lead.tags, list)
    
    def test_metadata_json_field(self):
        """Test metadata JSON field functionality."""
        metadata = {
            'campaign_id': '12345',
            'referrer': 'linkedin',
            'initial_interest': 'PBSA development funding'
        }
        
        lead = LeadFactory.create(
            group=self.group1,
            metadata=metadata
        )
        
        self.assertEqual(lead.metadata, metadata)
        self.assertIsInstance(lead.metadata, dict)
    
    def test_score_breakdown_json_field(self):
        """Test score_breakdown JSON field functionality."""
        breakdown = {
            'domain_authority': 85,
            'recent_activity': 90,
            'company_size': 75
        }
        
        lead = LeadFactory.create(
            group=self.group1,
            score_breakdown=breakdown
        )
        
        self.assertEqual(lead.score_breakdown, breakdown)
        self.assertIsInstance(lead.score_breakdown, dict)
    
    def test_conversion_tracking(self):
        """Test conversion tracking fields."""
        lead = ConvertedLeadFactory.create(group=self.group1)
        
        self.assertEqual(lead.status, Lead.LeadStatus.CONVERTED)
        self.assertIsNotNone(lead.converted_at)
        self.assertIsNotNone(lead.conversion_value)
        self.assertGreater(lead.conversion_value, 0)
    
    def test_ordering(self):
        """Test default ordering by lead_score descending, then created_at descending."""
        # Create leads with different scores
        low_score = LeadFactory.create(group=self.group1, lead_score=30.0)
        high_score = LeadFactory.create(group=self.group1, lead_score=90.0)
        medium_score = LeadFactory.create(group=self.group1, lead_score=60.0)
        
        leads = list(Lead.objects.all())
        self.assertEqual(leads[0], high_score)
        self.assertEqual(leads[1], medium_score)
        self.assertEqual(leads[2], low_score)


class LeadActivityModelTest(TestCase, TestDataMixin):
    """Test LeadActivity model functionality."""
    
    def setUp(self):
        super().setUp()
        self.lead = LeadFactory.create(group=self.group1)
    
    def test_lead_activity_creation(self):
        """Test basic lead activity creation."""
        activity = LeadActivityFactory.create(
            lead=self.lead,
            created_by=self.analyst_user
        )
        
        self.assertIsNotNone(activity.id)
        self.assertEqual(activity.lead, self.lead)
        self.assertEqual(activity.created_by, self.analyst_user)
        self.assertIsNotNone(activity.created_at)
    
    def test_lead_activity_str_representation(self):
        """Test string representation of lead activity."""
        activity = LeadActivityFactory.create(
            lead=self.lead,
            activity_type=LeadActivity.ActivityType.EMAIL,
            created_by=self.analyst_user
        )
        
        expected = f"{self.lead} - email - {self.analyst_user}"
        self.assertEqual(str(activity), expected)
    
    def test_activity_type_choices(self):
        """Test all activity type choices are valid."""
        for choice_value, choice_label in LeadActivity.ActivityType.choices:
            activity = LeadActivityFactory.create(
                lead=self.lead,
                activity_type=choice_value
            )
            self.assertEqual(activity.activity_type, choice_value)
    
    def test_is_completed_property(self):
        """Test is_completed property."""
        # Completed activity
        completed = LeadActivityFactory.create(
            lead=self.lead,
            completed_at=timezone.now()
        )
        self.assertTrue(completed.is_completed)
        
        # Uncompleted activity
        uncompleted = LeadActivityFactory.create(
            lead=self.lead,
            completed_at=None
        )
        self.assertFalse(uncompleted.is_completed)
    
    def test_is_overdue_property(self):
        """Test is_overdue property."""
        # Overdue activity
        past_date = timezone.now() - timedelta(days=1)
        overdue = LeadActivityFactory.create(
            lead=self.lead,
            scheduled_at=past_date,
            completed_at=None
        )
        self.assertTrue(overdue.is_overdue)
        
        # Future activity
        future_date = timezone.now() + timedelta(days=1)
        future = LeadActivityFactory.create(
            lead=self.lead,
            scheduled_at=future_date,
            completed_at=None
        )
        self.assertFalse(future.is_overdue)
        
        # Completed activity (not overdue even if past scheduled)
        completed = LeadActivityFactory.create(
            lead=self.lead,
            scheduled_at=past_date,
            completed_at=timezone.now()
        )
        self.assertFalse(completed.is_overdue)
    
    def test_mark_completed_method(self):
        """Test mark_completed method."""
        activity = LeadActivityFactory.create(
            lead=self.lead,
            completed_at=None,
            outcome=None
        )
        
        activity.mark_completed("Success")
        
        self.assertIsNotNone(activity.completed_at)
        self.assertEqual(activity.outcome, "Success")
    
    def test_email_activity_with_details(self):
        """Test email activity with contact method and outcome."""
        activity = LeadActivityFactory.create(
            lead=self.lead,
            activity_type=LeadActivity.ActivityType.EMAIL,
            contact_method='email',
            outcome='opened'
        )
        
        self.assertEqual(activity.contact_method, 'email')
        self.assertEqual(activity.outcome, 'opened')
    
    def test_call_activity_with_details(self):
        """Test call activity with contact method and outcome."""
        activity = LeadActivityFactory.create(
            lead=self.lead,
            activity_type=LeadActivity.ActivityType.CALL,
            contact_method='phone',
            outcome='voicemail'
        )
        
        self.assertEqual(activity.contact_method, 'phone')
        self.assertEqual(activity.outcome, 'voicemail')
    
    def test_meeting_activity_with_scheduling(self):
        """Test meeting activity with scheduled time."""
        scheduled_time = timezone.now() + timedelta(days=2)
        activity = LeadActivityFactory.create(
            lead=self.lead,
            activity_type=LeadActivity.ActivityType.MEETING,
            scheduled_at=scheduled_time
        )
        
        self.assertEqual(activity.scheduled_at, scheduled_time)
        self.assertFalse(activity.is_overdue)
    
    def test_status_change_activity(self):
        """Test status change activity type."""
        activity = LeadActivityFactory.create(
            lead=self.lead,
            activity_type=LeadActivity.ActivityType.STATUS_CHANGE,
            description="Status changed from NEW to QUALIFIED"
        )
        
        self.assertEqual(activity.activity_type, LeadActivity.ActivityType.STATUS_CHANGE)
        self.assertIn("QUALIFIED", activity.description)
    
    def test_ordering(self):
        """Test default ordering by created_at descending."""
        # Create activities at different times
        old_activity = LeadActivityFactory.create(lead=self.lead)
        old_activity.created_at = timezone.now() - timedelta(days=2)
        old_activity.save()
        
        new_activity = LeadActivityFactory.create(lead=self.lead)
        
        activities = list(LeadActivity.objects.all())
        self.assertEqual(activities[0], new_activity)  # Newest first
        self.assertEqual(activities[1], old_activity)


class ModelIntegrationTest(TestCase, TestDataMixin):
    """Test integration between different models."""
    
    def setUp(self):
        super().setUp()
    
    def test_complete_lead_workflow(self):
        """Test complete workflow from target to converted lead."""
        # Create target company
        target = TargetCompany.objects.create(
            group=self.group1,
            company_name="PBSA Developer Ltd",
            business_model="developer",
            lead_score=85.0,
            identified_by=self.analyst_user
        )
        
        # Create scoring model
        model = LeadScoringModelFactory.create(
            group=self.group1,
            name="PBSA Scoring Model"
        )
        
        # Create lead
        lead = Lead.objects.create(
            group=self.group1,
            target_company=target,
            scoring_model=model,
            contact_name="John Smith",
            contact_email="john@pbsadeveloper.com",
            assigned_to=self.analyst_user
        )
        
        # Score the lead
        lead.update_score(85.0, {'pbsa_focus': 100}, 0.95)
        
        # Add activities
        lead.add_activity(
            LeadActivity.ActivityType.EMAIL,
            "Initial outreach",
            self.analyst_user
        )
        
        lead.add_activity(
            LeadActivity.ActivityType.CALL,
            "Discovery call completed",
            self.analyst_user
        )
        
        # Update status
        lead.status = Lead.LeadStatus.QUALIFIED
        lead.save()
        
        # Test relationships
        self.assertEqual(lead.target_company, target)
        self.assertEqual(lead.scoring_model, model)
        self.assertEqual(lead.activities.count(), 2)
        self.assertTrue(lead.is_qualified)
    
    def test_group_isolation(self):
        """Test that group-based isolation works correctly."""
        # Create data in group1
        model1 = LeadScoringModelFactory.create(group=self.group1)
        lead1 = LeadFactory.create(group=self.group1)
        activity1 = LeadActivityFactory.create(lead=lead1)
        
        # Create data in group2  
        model2 = LeadScoringModelFactory.create(group=self.group2)
        target2 = TargetCompany.objects.create(
            group=self.group2,
            company_name="Group2 Company",
            identified_by=self.analyst_user
        )
        lead2 = LeadFactory.create(
            group=self.group2,
            target_company=target2
        )
        activity2 = LeadActivityFactory.create(lead=lead2)
        
        # Test group1 only sees its data
        group1_models = LeadScoringModel.objects.filter(group=self.group1)
        self.assertIn(model1, group1_models)
        self.assertNotIn(model2, group1_models)
        
        group1_leads = Lead.objects.filter(group=self.group1)
        self.assertIn(lead1, group1_leads)
        self.assertNotIn(lead2, group1_leads)
    
    def test_cascade_deletion(self):
        """Test cascade deletion behavior."""
        # Create lead with activities
        lead = LeadFactory.create(group=self.group1)
        activity1 = LeadActivityFactory.create(lead=lead)
        activity2 = LeadActivityFactory.create(lead=lead)
        
        # Delete lead - activities should be deleted
        lead_id = lead.id
        lead.delete()
        
        self.assertFalse(Lead.objects.filter(id=lead_id).exists())
        self.assertFalse(LeadActivity.objects.filter(lead_id=lead_id).exists())
    
    def test_scoring_model_deactivation(self):
        """Test impact of deactivating a scoring model."""
        model = LeadScoringModelFactory.create(
            group=self.group1,
            is_active=True
        )
        lead = LeadFactory.create(
            group=self.group1,
            scoring_model=model
        )
        
        # Deactivate model
        model.is_active = False
        model.save()
        
        # Lead should still reference the model
        lead.refresh_from_db()
        self.assertEqual(lead.scoring_model, model)
        self.assertFalse(lead.scoring_model.is_active)
    
    def test_qualified_lead_factory(self):
        """Test QualifiedLeadFactory creates proper qualified lead."""
        lead = QualifiedLeadFactory.create(group=self.group1)
        
        self.assertGreaterEqual(lead.lead_score, 70)
        self.assertEqual(lead.status, Lead.LeadStatus.QUALIFIED)
        self.assertEqual(lead.priority, Lead.Priority.HIGH)
        self.assertGreater(lead.activities.count(), 0)
    
    def test_converted_lead_factory(self):
        """Test ConvertedLeadFactory creates proper converted lead."""
        lead = ConvertedLeadFactory.create(group=self.group1)
        
        self.assertGreaterEqual(lead.lead_score, 80)
        self.assertEqual(lead.status, Lead.LeadStatus.CONVERTED)
        self.assertIsNotNone(lead.converted_at)
        self.assertIsNotNone(lead.conversion_value)
        self.assertGreater(lead.activities.count(), 0)
    
    def test_unqualified_lead_factory(self):
        """Test UnqualifiedLeadFactory creates proper unqualified lead."""
        lead = UnqualifiedLeadFactory.create(group=self.group1)
        
        self.assertLessEqual(lead.lead_score, 30)
        self.assertEqual(lead.status, Lead.LeadStatus.UNQUALIFIED)
        self.assertEqual(lead.priority, Lead.Priority.LOW)
        self.assertGreater(lead.activities.count(), 0)