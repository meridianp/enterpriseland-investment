"""
Comprehensive tests for leads services.

Tests all service functionality including lead scoring, workflow automation,
and business logic to ensure 90%+ code coverage.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, call
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from accounts.models import Group
from market_intelligence.models import TargetCompany, NewsArticle
from ..models import LeadScoringModel, Lead, LeadActivity
from ..services import LeadScoringService, LeadWorkflowService
from .factories import (
    LeadScoringModelFactory, LeadFactory, LeadActivityFactory,
    TargetCompanyFactory, TestDataMixin
)

User = get_user_model()


class LeadScoringServiceTest(TestCase, TestDataMixin):
    """Test LeadScoringService functionality."""
    
    def setUp(self):
        super().setUp()
        self.service = LeadScoringService()
        
        # Create a target company with articles for scoring
        self.target = TargetCompanyFactory.create(
            group=self.group1,
            company_name="PBSA Developer Ltd",
            domain="https://pbsadeveloper.com",
            linkedin_url="https://linkedin.com/company/pbsa-developer",
            description="Leading PBSA development company",
            business_model="developer",
            focus_sectors=["pbsa", "student_housing"],
            geographic_focus=["UK", "Ireland"],
            employee_count=150,
            company_size="medium"
        )
        
        # Create recent news articles
        self.recent_article = NewsArticle.objects.create(
            group=self.group1,
            title="PBSA Developer announces new project",
            content="Major new development",
            url="https://news.com/article1",
            published_date=timezone.now() - timedelta(days=5),
            relevance_score=0.9
        )
        self.target.source_articles.add(self.recent_article)
        
        # Create scoring model
        self.scoring_model = LeadScoringModelFactory.create(
            group=self.group1,
            model_type=LeadScoringModel.ModelType.RULES_BASED,
            scoring_criteria={
                'domain_authority': {'weight': 0.15, 'max_score': 100},
                'recent_activity': {'weight': 0.20, 'max_score': 100},
                'company_size': {'weight': 0.15, 'max_score': 100},
                'pbsa_focus': {'weight': 0.25, 'max_score': 100},
                'funding_status': {'weight': 0.15, 'max_score': 100},
                'geographic_fit': {'weight': 0.10, 'max_score': 100}
            }
        )
    
    def test_score_lead_with_rules_based_model(self):
        """Test scoring a lead with rules-based model."""
        lead = LeadFactory.create(
            group=self.group1,
            target_company=self.target,
            scoring_model=self.scoring_model
        )
        
        score, breakdown, confidence = self.service.score_lead(lead, self.scoring_model)
        
        # Check score is within valid range
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        
        # Check breakdown contains expected keys
        self.assertIn('domain_authority', breakdown)
        self.assertIn('recent_activity', breakdown)
        self.assertIn('company_size', breakdown)
        self.assertIn('pbsa_focus', breakdown)
        
        # Check confidence score
        self.assertGreaterEqual(confidence, 0)
        self.assertLessEqual(confidence, 1)
    
    def test_extract_features_from_target(self):
        """Test feature extraction from target company."""
        features = self.service._extract_features(self.target)
        
        # Check all expected features are present
        expected_features = [
            'domain_authority', 'recent_activity', 'company_size',
            'pbsa_focus', 'funding_status', 'geographic_fit'
        ]
        
        for feature in expected_features:
            self.assertIn(feature, features)
            self.assertGreaterEqual(features[feature], 0)
            self.assertLessEqual(features[feature], 100)
        
        # Check specific feature values
        self.assertGreater(features['domain_authority'], 0)  # Has domain
        self.assertGreater(features['recent_activity'], 0)  # Has recent article
        self.assertEqual(features['pbsa_focus'], 100)  # PBSA in focus sectors
    
    def test_calculate_domain_authority(self):
        """Test domain authority calculation."""
        # With domain and LinkedIn
        score1 = self.service._calculate_domain_authority(self.target)
        self.assertEqual(score1, 60)  # 30 for domain + 30 for LinkedIn
        
        # Only domain
        target2 = TargetCompanyFactory.create(
            group=self.group1,
            domain="https://example.com",
            linkedin_url=""
        )
        score2 = self.service._calculate_domain_authority(target2)
        self.assertEqual(score2, 30)
        
        # No online presence
        target3 = TargetCompanyFactory.create(
            group=self.group1,
            domain="",
            linkedin_url=""
        )
        score3 = self.service._calculate_domain_authority(target3)
        self.assertEqual(score3, 0)
    
    def test_calculate_recent_activity(self):
        """Test recent activity score calculation."""
        # Target with recent article (created in setUp)
        score1 = self.service._calculate_recent_activity(self.target)
        self.assertGreater(score1, 0)
        
        # Target with no articles
        target2 = TargetCompanyFactory.create(group=self.group1)
        score2 = self.service._calculate_recent_activity(target2)
        self.assertEqual(score2, 0)
        
        # Target with old article
        target3 = TargetCompanyFactory.create(group=self.group1)
        old_article = NewsArticle.objects.create(
            group=self.group1,
            title="Old news",
            content="Old content",
            url="https://old.com",
            published_date=timezone.now() - timedelta(days=100)
        )
        target3.source_articles.add(old_article)
        score3 = self.service._calculate_recent_activity(target3)
        self.assertEqual(score3, 0)  # Too old
    
    def test_calculate_company_size_score(self):
        """Test company size scoring."""
        # Large company
        target1 = TargetCompanyFactory.create(
            group=self.group1,
            company_size="large",
            employee_count=1000
        )
        score1 = self.service._calculate_company_size(target1)
        self.assertEqual(score1, 100)
        
        # Medium company
        target2 = TargetCompanyFactory.create(
            group=self.group1,
            company_size="medium",
            employee_count=100
        )
        score2 = self.service._calculate_company_size(target2)
        self.assertEqual(score2, 70)
        
        # Small company
        target3 = TargetCompanyFactory.create(
            group=self.group1,
            company_size="small",
            employee_count=10
        )
        score3 = self.service._calculate_company_size(target3)
        self.assertEqual(score3, 40)
        
        # Unknown size
        target4 = TargetCompanyFactory.create(
            group=self.group1,
            company_size="unknown",
            employee_count=None
        )
        score4 = self.service._calculate_company_size(target4)
        self.assertEqual(score4, 20)
    
    def test_calculate_pbsa_focus_score(self):
        """Test PBSA focus scoring."""
        # Strong PBSA focus
        target1 = TargetCompanyFactory.create(
            group=self.group1,
            focus_sectors=["pbsa", "student_housing"],
            description="Leading PBSA developer and operator"
        )
        score1 = self.service._calculate_pbsa_focus(target1)
        self.assertEqual(score1, 100)
        
        # Partial PBSA focus
        target2 = TargetCompanyFactory.create(
            group=self.group1,
            focus_sectors=["residential", "commercial"],
            description="We also do some student accommodation"
        )
        score2 = self.service._calculate_pbsa_focus(target2)
        self.assertGreater(score2, 0)
        self.assertLess(score2, 100)
        
        # No PBSA focus
        target3 = TargetCompanyFactory.create(
            group=self.group1,
            focus_sectors=["office", "retail"],
            description="Commercial property developer"
        )
        score3 = self.service._calculate_pbsa_focus(target3)
        self.assertEqual(score3, 0)
    
    def test_calculate_geographic_fit(self):
        """Test geographic fit scoring."""
        # Perfect fit
        target1 = TargetCompanyFactory.create(
            group=self.group1,
            geographic_focus=["UK", "Ireland"]
        )
        score1 = self.service._calculate_geographic_fit(target1)
        self.assertEqual(score1, 100)
        
        # Partial fit
        target2 = TargetCompanyFactory.create(
            group=self.group1,
            geographic_focus=["UK", "Germany", "France"]
        )
        score2 = self.service._calculate_geographic_fit(target2)
        self.assertGreater(score2, 0)
        self.assertLess(score2, 100)
        
        # No geographic focus specified
        target3 = TargetCompanyFactory.create(
            group=self.group1,
            geographic_focus=[]
        )
        score3 = self.service._calculate_geographic_fit(target3)
        self.assertEqual(score3, 50)  # Default neutral score
    
    def test_calculate_confidence_score(self):
        """Test confidence score calculation."""
        features1 = {
            'domain_authority': 80,
            'recent_activity': 90,
            'company_size': 70,
            'pbsa_focus': 100,
            'funding_status': 60,
            'geographic_fit': 85
        }
        confidence1 = self.service._calculate_confidence(features1)
        self.assertGreater(confidence1, 0.8)  # High confidence with complete data
        
        features2 = {
            'domain_authority': 0,
            'recent_activity': 0,
            'company_size': 20,
            'pbsa_focus': 0,
            'funding_status': 0,
            'geographic_fit': 50
        }
        confidence2 = self.service._calculate_confidence(features2)
        self.assertLess(confidence2, 0.5)  # Low confidence with minimal data
    
    def test_score_multiple_leads(self):
        """Test scoring multiple leads in batch."""
        leads = []
        for i in range(3):
            target = TargetCompanyFactory.create(
                group=self.group1,
                company_name=f"Company {i}"
            )
            lead = LeadFactory.create(
                group=self.group1,
                target_company=target,
                scoring_model=self.scoring_model
            )
            leads.append(lead)
        
        results = self.service.score_multiple_leads(leads, self.scoring_model)
        
        self.assertEqual(len(results), 3)
        for lead, (score, breakdown, confidence) in zip(leads, results):
            self.assertIsInstance(score, float)
            self.assertIsInstance(breakdown, dict)
            self.assertIsInstance(confidence, float)
    
    @patch('leads.services.LeadScoringService._ml_predict')
    def test_score_lead_with_ml_model(self, mock_ml_predict):
        """Test scoring with ML-based model."""
        ml_model = LeadScoringModelFactory.create(
            group=self.group1,
            model_type=LeadScoringModel.ModelType.ML_BASED,
            model_data={'model': 'serialized_model_data'}
        )
        
        lead = LeadFactory.create(
            group=self.group1,
            target_company=self.target,
            scoring_model=ml_model
        )
        
        # Mock ML prediction
        mock_ml_predict.return_value = (85.5, 0.92)
        
        score, breakdown, confidence = self.service.score_lead(lead, ml_model)
        
        self.assertEqual(score, 85.5)
        self.assertEqual(confidence, 0.92)
        mock_ml_predict.assert_called_once()
    
    def test_hybrid_scoring_model(self):
        """Test hybrid scoring model (rules + ML)."""
        hybrid_model = LeadScoringModelFactory.create(
            group=self.group1,
            model_type=LeadScoringModel.ModelType.HYBRID
        )
        
        lead = LeadFactory.create(
            group=self.group1,
            target_company=self.target,
            scoring_model=hybrid_model
        )
        
        score, breakdown, confidence = self.service.score_lead(lead, hybrid_model)
        
        # Hybrid should produce valid results
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        self.assertIsInstance(breakdown, dict)


class LeadWorkflowServiceTest(TestCase, TestDataMixin):
    """Test LeadWorkflowService functionality."""
    
    def setUp(self):
        super().setUp()
        self.service = LeadWorkflowService()
        self.scoring_service = LeadScoringService()
        
        # Create test data
        self.target = TargetCompanyFactory.create(
            group=self.group1,
            company_name="Test PBSA Developer"
        )
        
        self.scoring_model = LeadScoringModelFactory.create(
            group=self.group1,
            thresholds={
                'qualified': 70,
                'potential': 50,
                'unqualified': 30
            }
        )
        
        self.lead = LeadFactory.create(
            group=self.group1,
            target_company=self.target,
            scoring_model=self.scoring_model,
            assigned_to=self.analyst_user
        )
    
    def test_process_new_lead(self):
        """Test processing a new lead."""
        # Process the lead
        self.service.process_new_lead(self.lead)
        
        # Check lead was scored
        self.assertIsNotNone(self.lead.lead_score)
        self.assertIsNotNone(self.lead.score_breakdown)
        self.assertIsNotNone(self.lead.confidence_score)
        
        # Check status was updated based on score
        self.assertNotEqual(self.lead.status, Lead.LeadStatus.NEW)
        
        # Check activity was created
        activities = self.lead.activities.filter(
            activity_type=LeadActivity.ActivityType.STATUS_CHANGE
        )
        self.assertEqual(activities.count(), 1)
    
    def test_update_lead_status_to_qualified(self):
        """Test updating lead status to qualified."""
        self.lead.lead_score = 75.0
        self.lead.save()
        
        self.service.update_lead_status(self.lead, Lead.LeadStatus.QUALIFIED)
        
        self.assertEqual(self.lead.status, Lead.LeadStatus.QUALIFIED)
        self.assertEqual(self.lead.priority, Lead.Priority.HIGH)
        self.assertIsNotNone(self.lead.last_status_change)
        
        # Check activity was created
        activity = self.lead.activities.filter(
            activity_type=LeadActivity.ActivityType.STATUS_CHANGE
        ).first()
        self.assertIsNotNone(activity)
        self.assertIn("QUALIFIED", activity.description)
    
    def test_update_lead_status_to_converted(self):
        """Test updating lead status to converted."""
        self.service.update_lead_status(
            self.lead,
            Lead.LeadStatus.CONVERTED,
            conversion_value=Decimal('500000.00')
        )
        
        self.assertEqual(self.lead.status, Lead.LeadStatus.CONVERTED)
        self.assertIsNotNone(self.lead.converted_at)
        self.assertEqual(self.lead.conversion_value, Decimal('500000.00'))
        
        # Check activity
        activity = self.lead.activities.filter(
            activity_type=LeadActivity.ActivityType.STATUS_CHANGE
        ).first()
        self.assertIn("CONVERTED", activity.description)
        self.assertIn("500000", activity.description)
    
    def test_assign_lead(self):
        """Test lead assignment."""
        new_assignee = User.objects.create(
            username="new_analyst",
            email="new@example.com",
            group=self.group1,
            role="ANALYST"
        )
        
        self.service.assign_lead(self.lead, new_assignee)
        
        self.assertEqual(self.lead.assigned_to, new_assignee)
        
        # Check assignment activity
        activity = self.lead.activities.filter(
            activity_type=LeadActivity.ActivityType.ASSIGNMENT
        ).first()
        self.assertIsNotNone(activity)
        self.assertIn(new_assignee.username, activity.description)
    
    def test_schedule_follow_up(self):
        """Test scheduling a follow-up activity."""
        follow_up_date = timezone.now() + timedelta(days=3)
        
        activity = self.service.schedule_follow_up(
            self.lead,
            LeadActivity.ActivityType.CALL,
            follow_up_date,
            "Follow-up call to discuss proposal",
            self.analyst_user
        )
        
        self.assertEqual(activity.lead, self.lead)
        self.assertEqual(activity.activity_type, LeadActivity.ActivityType.CALL)
        self.assertEqual(activity.scheduled_at, follow_up_date)
        self.assertEqual(activity.created_by, self.analyst_user)
        self.assertIsNone(activity.completed_at)
    
    def test_get_overdue_activities(self):
        """Test retrieving overdue activities."""
        # Create overdue activity
        past_date = timezone.now() - timedelta(days=2)
        overdue = LeadActivityFactory.create(
            lead=self.lead,
            activity_type=LeadActivity.ActivityType.CALL,
            scheduled_at=past_date,
            completed_at=None
        )
        
        # Create future activity
        future_date = timezone.now() + timedelta(days=2)
        future = LeadActivityFactory.create(
            lead=self.lead,
            activity_type=LeadActivity.ActivityType.MEETING,
            scheduled_at=future_date,
            completed_at=None
        )
        
        # Create completed activity
        completed = LeadActivityFactory.create(
            lead=self.lead,
            activity_type=LeadActivity.ActivityType.EMAIL,
            scheduled_at=past_date,
            completed_at=timezone.now()
        )
        
        overdue_activities = self.service.get_overdue_activities(self.group1)
        
        self.assertIn(overdue, overdue_activities)
        self.assertNotIn(future, overdue_activities)
        self.assertNotIn(completed, overdue_activities)
    
    def test_get_leads_for_review(self):
        """Test retrieving leads that need review."""
        # Create leads with different statuses and ages
        old_new_lead = LeadFactory.create(
            group=self.group1,
            status=Lead.LeadStatus.NEW
        )
        old_new_lead.created_at = timezone.now() - timedelta(days=8)
        old_new_lead.save()
        
        recent_new_lead = LeadFactory.create(
            group=self.group1,
            status=Lead.LeadStatus.NEW
        )
        
        old_contacted_lead = LeadFactory.create(
            group=self.group1,
            status=Lead.LeadStatus.CONTACTED,
            last_status_change=timezone.now() - timedelta(days=15)
        )
        
        leads_for_review = self.service.get_leads_for_review(self.group1)
        
        self.assertIn(old_new_lead, leads_for_review)
        self.assertNotIn(recent_new_lead, leads_for_review)
        self.assertIn(old_contacted_lead, leads_for_review)
    
    def test_bulk_update_status(self):
        """Test bulk status update."""
        leads = [
            LeadFactory.create(group=self.group1, status=Lead.LeadStatus.NEW)
            for _ in range(3)
        ]
        
        updated = self.service.bulk_update_status(
            leads,
            Lead.LeadStatus.CONTACTED,
            self.analyst_user
        )
        
        self.assertEqual(updated, 3)
        
        # Check all leads were updated
        for lead in leads:
            lead.refresh_from_db()
            self.assertEqual(lead.status, Lead.LeadStatus.CONTACTED)
            
            # Check activity was created
            activity = lead.activities.filter(
                activity_type=LeadActivity.ActivityType.STATUS_CHANGE
            ).first()
            self.assertIsNotNone(activity)
    
    def test_auto_prioritize_leads(self):
        """Test automatic lead prioritization."""
        # Create leads with different scores
        high_score_lead = LeadFactory.create(
            group=self.group1,
            lead_score=85.0,
            priority=Lead.Priority.LOW  # Wrong priority
        )
        
        medium_score_lead = LeadFactory.create(
            group=self.group1,
            lead_score=55.0,
            priority=Lead.Priority.HIGH  # Wrong priority
        )
        
        low_score_lead = LeadFactory.create(
            group=self.group1,
            lead_score=25.0,
            priority=Lead.Priority.HIGH  # Wrong priority
        )
        
        leads = [high_score_lead, medium_score_lead, low_score_lead]
        updated = self.service.auto_prioritize_leads(leads)
        
        self.assertEqual(updated, 3)
        
        # Check priorities were corrected
        high_score_lead.refresh_from_db()
        self.assertEqual(high_score_lead.priority, Lead.Priority.HIGH)
        
        medium_score_lead.refresh_from_db()
        self.assertEqual(medium_score_lead.priority, Lead.Priority.MEDIUM)
        
        low_score_lead.refresh_from_db()
        self.assertEqual(low_score_lead.priority, Lead.Priority.LOW)
    
    @patch('leads.services.send_notification')
    def test_notify_assignment(self, mock_send_notification):
        """Test notification on lead assignment."""
        new_assignee = User.objects.create(
            username="new_analyst",
            email="new@example.com",
            group=self.group1,
            role="ANALYST"
        )
        
        self.service.assign_lead(self.lead, new_assignee, notify=True)
        
        # Check notification was sent
        mock_send_notification.assert_called_once()
        call_args = mock_send_notification.call_args[0]
        self.assertEqual(call_args[0], new_assignee)
        self.assertIn("assigned", call_args[1].lower())


class ServiceIntegrationTest(TestCase, TestDataMixin):
    """Test integration between different services."""
    
    def setUp(self):
        super().setUp()
        self.scoring_service = LeadScoringService()
        self.workflow_service = LeadWorkflowService()
    
    def test_complete_lead_processing_workflow(self):
        """Test complete workflow from target to qualified lead."""
        # Create high-quality target
        target = TargetCompanyFactory.create(
            group=self.group1,
            company_name="Premium PBSA Developer",
            domain="https://premiumpbsa.com",
            linkedin_url="https://linkedin.com/company/premium-pbsa",
            business_model="developer",
            focus_sectors=["pbsa"],
            company_size="large",
            lead_score=85.0
        )
        
        # Add recent news
        article = NewsArticle.objects.create(
            group=self.group1,
            title="Premium PBSA announces £100M development",
            url="https://news.com/premium-pbsa",
            published_date=timezone.now() - timedelta(days=3),
            relevance_score=0.95
        )
        target.source_articles.add(article)
        
        # Create scoring model
        model = LeadScoringModelFactory.create(
            group=self.group1,
            thresholds={
                'qualified': 70,
                'potential': 50,
                'unqualified': 30
            }
        )
        
        # Create lead from target
        lead = Lead.objects.create(
            group=self.group1,
            target_company=target,
            scoring_model=model,
            contact_name="John Smith",
            contact_email="john@premiumpbsa.com",
            assigned_to=self.analyst_user
        )
        
        # Process the lead
        self.workflow_service.process_new_lead(lead)
        
        # Verify lead was scored and qualified
        lead.refresh_from_db()
        self.assertGreaterEqual(lead.lead_score, 70)
        self.assertEqual(lead.status, Lead.LeadStatus.QUALIFIED)
        self.assertEqual(lead.priority, Lead.Priority.HIGH)
        
        # Schedule follow-up
        follow_up = self.workflow_service.schedule_follow_up(
            lead,
            LeadActivity.ActivityType.CALL,
            timezone.now() + timedelta(days=1),
            "Initial qualification call",
            self.analyst_user
        )
        
        # Complete the follow-up
        follow_up.mark_completed("Positive response, scheduling meeting")
        
        # Convert the lead
        self.workflow_service.update_lead_status(
            lead,
            Lead.LeadStatus.CONVERTED,
            conversion_value=Decimal('10000000.00')
        )
        
        # Verify final state
        lead.refresh_from_db()
        self.assertTrue(lead.is_converted)
        self.assertIsNotNone(lead.converted_at)
        self.assertEqual(lead.conversion_value, Decimal('10000000.00'))
        
        # Check complete activity history
        activities = lead.activities.all().order_by('created_at')
        self.assertGreater(activities.count(), 2)
        
        # Verify activity types
        activity_types = [a.activity_type for a in activities]
        self.assertIn(LeadActivity.ActivityType.STATUS_CHANGE, activity_types)
        self.assertIn(LeadActivity.ActivityType.CALL, activity_types)