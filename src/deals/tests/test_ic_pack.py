"""
Tests for IC pack automation models.

Comprehensive tests covering ICPackTemplate, ICPack, ICPackApproval,
ICPackDistribution, and ICPackAuditLog models with FSM transitions,
validation, constraints, and business logic.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from datetime import datetime, timedelta
from unittest.mock import patch

from accounts.models import Group
from assessments.models import DevelopmentPartner, Assessment
from files.models import FileAttachment
from deals.models import (
    Deal, DealType, DealSource, ICPackTemplate, ICPack, ICPackApproval,
    ICPackDistribution, ICPackAuditLog, ICPackStatus
)

User = get_user_model()


class ICPackTemplateModelTests(TestCase):
    """Test ICPackTemplate model functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.user.groups.add(self.group)
    
    def test_create_template(self):
        """Test creating an IC pack template."""
        template = ICPackTemplate.objects.create(
            name="Standard IC Pack",
            description="Standard template for IC packs",
            sections=[
                {
                    "id": "executive_summary",
                    "title": "Executive Summary",
                    "order": 1,
                    "required": True,
                    "data_sources": ["deal", "partner"]
                }
            ],
            approval_stages=[
                {
                    "stage": "analyst_review",
                    "name": "Analyst Review",
                    "required_role": "ANALYST",
                    "order": 1
                }
            ],
            created_by=self.user,
            group=self.group
        )
        
        self.assertEqual(template.name, "Standard IC Pack")
        self.assertTrue(template.is_active)
        self.assertFalse(template.is_default)
        self.assertEqual(template.output_format, 'pdf')
        self.assertEqual(len(template.sections), 1)
        self.assertEqual(len(template.approval_stages), 1)
    
    def test_default_template_constraint(self):
        """Test that only one default template is allowed per group."""
        # Create first default template
        template1 = ICPackTemplate.objects.create(
            name="Default Template 1",
            is_default=True,
            created_by=self.user,
            group=self.group
        )
        
        # Try to create another default template in same group
        with self.assertRaises(IntegrityError):
            ICPackTemplate.objects.create(
                name="Default Template 2",
                is_default=True,
                created_by=self.user,
                group=self.group
            )
        
        # Should be able to create default in different group
        group2 = Group.objects.create(name="Group 2")
        template2 = ICPackTemplate.objects.create(
            name="Default Template 2",
            is_default=True,
            created_by=self.user,
            group=group2
        )
        
        self.assertTrue(template2.is_default)
    
    def test_unique_name_per_group(self):
        """Test unique name constraint per group."""
        ICPackTemplate.objects.create(
            name="Test Template",
            created_by=self.user,
            group=self.group
        )
        
        # Should not allow duplicate name in same group
        with self.assertRaises(IntegrityError):
            ICPackTemplate.objects.create(
                name="Test Template",
                created_by=self.user,
                group=self.group
            )
        
        # Should allow same name in different group
        group2 = Group.objects.create(name="Group 2")
        template2 = ICPackTemplate.objects.create(
            name="Test Template",
            created_by=self.user,
            group=group2
        )
        
        self.assertEqual(template2.name, "Test Template")
    
    def test_validate_sections(self):
        """Test section validation."""
        template = ICPackTemplate(
            name="Invalid Template",
            sections=[
                {"title": "Section 1", "order": 1},  # Missing id
                {"id": "section2"},  # Missing title and order
                {"id": "section1", "title": "Duplicate", "order": 2}  # Duplicate id
            ],
            created_by=self.user,
            group=self.group
        )
        
        errors = template.validate_sections()
        
        self.assertIn("Section 0 missing 'id'", errors)
        self.assertIn("Section 1 missing 'title'", errors)
        self.assertIn("Section 1 missing 'order'", errors)
        self.assertIn("Duplicate section ID: section1", errors)
    
    def test_template_string_representation(self):
        """Test template string representation."""
        template = ICPackTemplate.objects.create(
            name="Test Template",
            created_by=self.user,
            group=self.group
        )
        
        self.assertEqual(str(template), "Test Template ")
        
        # Test with default template
        template.is_default = True
        template.save()
        
        self.assertEqual(str(template), "Test Template (Default)")


class ICPackModelTests(TestCase):
    """Test ICPack model functionality including FSM transitions."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.user.groups.add(self.group)
        
        self.partner = DevelopmentPartner.objects.create(
            company_name="Test Partner Company",
            group=self.group
        )
        
        self.deal_type = DealType.objects.create(
            name="Test Deal Type",
            code="TEST",
            group=self.group
        )
        
        self.deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=1000000,
            group=self.group
        )
        
        self.template = ICPackTemplate.objects.create(
            name="Test Template",
            sections=[
                {
                    "id": "executive_summary",
                    "title": "Executive Summary",
                    "order": 1,
                    "required": True
                }
            ],
            approval_stages=[
                {
                    "stage": "analyst_review",
                    "name": "Analyst Review",
                    "required_role": "ANALYST",
                    "order": 1
                }
            ],
            created_by=self.user,
            group=self.group
        )
        
        # Create assessment for file attachments
        self.assessment = Assessment.objects.create(
            group=self.group,
            created_by=self.user,
            updated_by=self.user
        )
    
    def test_create_ic_pack(self):
        """Test creating an IC pack."""
        meeting_date = timezone.now() + timedelta(days=7)
        
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test IC Pack",
            meeting_date=meeting_date,
            created_by=self.user,
            group=self.group
        )
        
        self.assertEqual(ic_pack.deal, self.deal)
        self.assertEqual(ic_pack.template, self.template)
        self.assertEqual(ic_pack.version, 1)
        self.assertEqual(ic_pack.status, ICPackStatus.DRAFT)
        self.assertEqual(ic_pack.meeting_date, meeting_date)
        self.assertEqual(ic_pack.times_viewed, 0)
    
    def test_ic_pack_string_representation(self):
        """Test IC pack string representation."""
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test IC Pack",
            created_by=self.user,
            group=self.group
        )
        
        expected = "Test IC Pack v1 - Draft"
        self.assertEqual(str(ic_pack), expected)
    
    def test_unique_version_per_deal(self):
        """Test unique version constraint per deal."""
        ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="IC Pack v1",
            version=1,
            created_by=self.user,
            group=self.group
        )
        
        # Should not allow duplicate version for same deal
        with self.assertRaises(IntegrityError):
            ICPack.objects.create(
                deal=self.deal,
                template=self.template,
                title="IC Pack v1 Duplicate",
                version=1,
                created_by=self.user,
                group=self.group
            )
    
    def test_fsm_submit_for_review_transition(self):
        """Test FSM transition from DRAFT to READY_FOR_REVIEW."""
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test IC Pack",
            created_by=self.user,
            group=self.group
        )
        
        self.assertEqual(ic_pack.status, ICPackStatus.DRAFT)
        
        # Submit for review
        ic_pack.submit_for_review()
        
        self.assertEqual(ic_pack.status, ICPackStatus.READY_FOR_REVIEW)
        self.assertEqual(ic_pack.last_modified_by, self.user)
    
    def test_fsm_start_review_transition(self):
        """Test FSM transition from READY_FOR_REVIEW to IN_REVIEW."""
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test IC Pack",
            status=ICPackStatus.READY_FOR_REVIEW,
            created_by=self.user,
            group=self.group
        )
        
        # Start review
        ic_pack.start_review()
        
        self.assertEqual(ic_pack.status, ICPackStatus.IN_REVIEW)
        self.assertEqual(ic_pack.current_approval_stage, "analyst_review")
    
    def test_fsm_approve_transition(self):
        """Test FSM transition from IN_REVIEW to APPROVED."""
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test IC Pack",
            status=ICPackStatus.IN_REVIEW,
            created_by=self.user,
            group=self.group
        )
        
        # Approve
        ic_pack.approve()
        
        self.assertEqual(ic_pack.status, ICPackStatus.APPROVED)
    
    def test_fsm_reject_transition(self):
        """Test FSM transition from IN_REVIEW to REJECTED."""
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test IC Pack",
            status=ICPackStatus.IN_REVIEW,
            created_by=self.user,
            group=self.group
        )
        
        # Reject
        ic_pack.reject()
        
        self.assertEqual(ic_pack.status, ICPackStatus.REJECTED)
    
    def test_fsm_send_back_to_draft_transition(self):
        """Test FSM transition from IN_REVIEW/REJECTED to DRAFT."""
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test IC Pack",
            status=ICPackStatus.IN_REVIEW,
            version=1,
            created_by=self.user,
            group=self.group
        )
        
        # Send back to draft
        ic_pack.send_back_to_draft()
        
        self.assertEqual(ic_pack.status, ICPackStatus.DRAFT)
        self.assertEqual(ic_pack.version, 2)
    
    def test_fsm_distribute_transition(self):
        """Test FSM transition from APPROVED to DISTRIBUTED."""
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test IC Pack",
            status=ICPackStatus.APPROVED,
            created_by=self.user,
            group=self.group
        )
        
        # Distribute
        ic_pack.distribute()
        
        self.assertEqual(ic_pack.status, ICPackStatus.DISTRIBUTED)
        self.assertIsNotNone(ic_pack.distributed_at)
    
    def test_fsm_archive_transition(self):
        """Test FSM transition to ARCHIVED from any state."""
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test IC Pack",
            status=ICPackStatus.APPROVED,
            created_by=self.user,
            group=self.group
        )
        
        # Archive
        ic_pack.archive()
        
        self.assertEqual(ic_pack.status, ICPackStatus.ARCHIVED)
    
    def test_create_new_version(self):
        """Test creating a new version of an IC pack."""
        original_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Original Pack",
            version=1,
            sections_data={"test": "data"},
            custom_content={"custom": "content"},
            distribution_list=["test@example.com"],
            created_by=self.user,
            group=self.group
        )
        
        new_pack = original_pack.create_new_version()
        
        self.assertEqual(new_pack.version, 2)
        self.assertEqual(new_pack.deal, original_pack.deal)
        self.assertEqual(new_pack.template, original_pack.template)
        self.assertEqual(new_pack.sections_data, original_pack.sections_data)
        self.assertEqual(new_pack.custom_content, original_pack.custom_content)
        self.assertEqual(new_pack.distribution_list, original_pack.distribution_list)
        self.assertEqual(new_pack.status, ICPackStatus.DRAFT)
    
    def test_get_next_approval_stage(self):
        """Test getting the next approval stage."""
        template = ICPackTemplate.objects.create(
            name="Multi-Stage Template",
            approval_stages=[
                {
                    "stage": "analyst_review",
                    "name": "Analyst Review",
                    "required_role": "ANALYST",
                    "order": 1
                },
                {
                    "stage": "manager_approval",
                    "name": "Manager Approval",
                    "required_role": "MANAGER",
                    "order": 2
                }
            ],
            created_by=self.user,
            group=self.group
        )
        
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=template,
            title="Multi-Stage Pack",
            current_approval_stage="analyst_review",
            created_by=self.user,
            group=self.group
        )
        
        # Get next stage
        next_stage = ic_pack.get_next_approval_stage()
        
        self.assertIsNotNone(next_stage)
        self.assertEqual(next_stage['stage'], "manager_approval")
        self.assertEqual(next_stage['name'], "Manager Approval")
        
        # Test when at last stage
        ic_pack.current_approval_stage = "manager_approval"
        next_stage = ic_pack.get_next_approval_stage()
        
        self.assertIsNone(next_stage)


class ICPackApprovalModelTests(TestCase):
    """Test ICPackApproval model functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.approver = User.objects.create_user(
            username="approver",
            email="approver@example.com",
            password="testpass123"
        )
        self.user.groups.add(self.group)
        self.approver.groups.add(self.group)
        
        # Create deal and template
        self.partner = DevelopmentPartner.objects.create(
            company_name="Test Partner Company",
            group=self.group
        )
        
        self.deal_type = DealType.objects.create(
            name="Test Deal Type",
            code="TEST",
            group=self.group
        )
        
        self.deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=1000000,
            group=self.group
        )
        
        self.template = ICPackTemplate.objects.create(
            name="Test Template",
            approval_stages=[
                {
                    "stage": "analyst_review",
                    "name": "Analyst Review",
                    "required_role": "ANALYST",
                    "order": 1
                },
                {
                    "stage": "manager_approval",
                    "name": "Manager Approval",
                    "required_role": "MANAGER",
                    "order": 2
                }
            ],
            created_by=self.user,
            group=self.group
        )
        
        self.ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test IC Pack",
            created_by=self.user,
            group=self.group
        )
    
    def test_create_approval(self):
        """Test creating an IC pack approval."""
        approval = ICPackApproval.objects.create(
            ic_pack=self.ic_pack,
            stage="analyst_review",
            stage_name="Analyst Review",
            group=self.group
        )
        
        self.assertEqual(approval.ic_pack, self.ic_pack)
        self.assertEqual(approval.stage, "analyst_review")
        self.assertEqual(approval.decision, ICPackApproval.ApprovalDecision.PENDING)
        self.assertIsNone(approval.decided_by)
        self.assertIsNone(approval.decided_at)
    
    def test_unique_approval_per_stage(self):
        """Test unique approval constraint per stage."""
        ICPackApproval.objects.create(
            ic_pack=self.ic_pack,
            stage="analyst_review",
            stage_name="Analyst Review",
            group=self.group
        )
        
        # Should not allow duplicate approval for same stage
        with self.assertRaises(IntegrityError):
            ICPackApproval.objects.create(
                ic_pack=self.ic_pack,
                stage="analyst_review",
                stage_name="Analyst Review Duplicate",
                group=self.group
            )
    
    def test_approval_string_representation(self):
        """Test approval string representation."""
        approval = ICPackApproval.objects.create(
            ic_pack=self.ic_pack,
            stage="analyst_review",
            stage_name="Analyst Review",
            group=self.group
        )
        
        expected = f"{self.ic_pack} - Analyst Review: Pending"
        self.assertEqual(str(approval), expected)
    
    @patch('deals.models.ic_pack.datetime')
    def test_make_decision_approved(self, mock_datetime):
        """Test making an approval decision."""
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 0, 0)
        
        approval = ICPackApproval.objects.create(
            ic_pack=self.ic_pack,
            stage="analyst_review",
            stage_name="Analyst Review",
            group=self.group
        )
        
        # Make approval decision
        approval.make_decision(
            user=self.approver,
            decision=ICPackApproval.ApprovalDecision.APPROVED,
            comments="Approved with minor conditions",
            conditions=["Complete final review", "Update section 3"]
        )
        
        approval.refresh_from_db()
        
        self.assertEqual(approval.decision, ICPackApproval.ApprovalDecision.APPROVED)
        self.assertEqual(approval.decided_by, self.approver)
        self.assertEqual(approval.decided_at, datetime(2024, 1, 15, 10, 0, 0))
        self.assertEqual(approval.comments, "Approved with minor conditions")
        self.assertEqual(approval.conditions, ["Complete final review", "Update section 3"])
        
        # Check that next approval stage was created
        next_approval = ICPackApproval.objects.filter(
            ic_pack=self.ic_pack,
            stage="manager_approval"
        ).first()
        
        self.assertIsNotNone(next_approval)
        self.assertEqual(next_approval.stage_name, "Manager Approval")
        
        # Check IC pack status updated
        self.ic_pack.refresh_from_db()
        self.assertEqual(self.ic_pack.current_approval_stage, "manager_approval")
    
    @patch('deals.models.ic_pack.datetime')
    def test_make_decision_final_approval(self, mock_datetime):
        """Test making final approval decision (all stages completed)."""
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 0, 0)
        
        # Create approval for final stage
        approval = ICPackApproval.objects.create(
            ic_pack=self.ic_pack,
            stage="manager_approval",
            stage_name="Manager Approval",
            group=self.group
        )
        
        # Set IC pack to final stage
        self.ic_pack.current_approval_stage = "manager_approval"
        self.ic_pack.save()
        
        # Make final approval decision
        approval.make_decision(
            user=self.approver,
            decision=ICPackApproval.ApprovalDecision.APPROVED,
            comments="Final approval granted"
        )
        
        # Check IC pack was approved
        self.ic_pack.refresh_from_db()
        self.assertEqual(self.ic_pack.status, ICPackStatus.APPROVED)
    
    @patch('deals.models.ic_pack.datetime')
    def test_make_decision_rejected(self, mock_datetime):
        """Test making a rejection decision."""
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 0, 0)
        
        approval = ICPackApproval.objects.create(
            ic_pack=self.ic_pack,
            stage="analyst_review",
            stage_name="Analyst Review",
            group=self.group
        )
        
        # Make rejection decision
        approval.make_decision(
            user=self.approver,
            decision=ICPackApproval.ApprovalDecision.REJECTED,
            comments="Needs significant revisions"
        )
        
        # Check IC pack was rejected
        self.ic_pack.refresh_from_db()
        self.assertEqual(self.ic_pack.status, ICPackStatus.REJECTED)


class ICPackDistributionModelTests(TestCase):
    """Test ICPackDistribution model functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.recipient_user = User.objects.create_user(
            username="recipient",
            email="recipient@example.com",
            password="testpass123"
        )
        self.user.groups.add(self.group)
        self.recipient_user.groups.add(self.group)
        
        # Create deal and template
        self.partner = DevelopmentPartner.objects.create(
            company_name="Test Partner Company",
            group=self.group
        )
        
        self.deal_type = DealType.objects.create(
            name="Test Deal Type",
            code="TEST",
            group=self.group
        )
        
        self.deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=1000000,
            group=self.group
        )
        
        self.template = ICPackTemplate.objects.create(
            name="Test Template",
            created_by=self.user,
            group=self.group
        )
        
        self.ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test IC Pack",
            status=ICPackStatus.DISTRIBUTED,
            created_by=self.user,
            group=self.group
        )
    
    def test_create_distribution(self):
        """Test creating an IC pack distribution."""
        distribution = ICPackDistribution.objects.create(
            ic_pack=self.ic_pack,
            recipient_email="recipient@example.com",
            recipient_name="John Doe",
            recipient_user=self.recipient_user,
            sent_by=self.user,
            group=self.group
        )
        
        self.assertEqual(distribution.ic_pack, self.ic_pack)
        self.assertEqual(distribution.recipient_email, "recipient@example.com")
        self.assertEqual(distribution.recipient_user, self.recipient_user)
        self.assertEqual(distribution.sent_by, self.user)
        self.assertEqual(distribution.view_count, 0)
        self.assertEqual(distribution.download_count, 0)
        self.assertIsNotNone(distribution.access_token)
    
    def test_unique_distribution_per_recipient(self):
        """Test unique distribution constraint per recipient."""
        ICPackDistribution.objects.create(
            ic_pack=self.ic_pack,
            recipient_email="recipient@example.com",
            sent_by=self.user,
            group=self.group
        )
        
        # Should not allow duplicate distribution to same recipient
        with self.assertRaises(IntegrityError):
            ICPackDistribution.objects.create(
                ic_pack=self.ic_pack,
                recipient_email="recipient@example.com",
                sent_by=self.user,
                group=self.group
            )
    
    def test_distribution_string_representation(self):
        """Test distribution string representation."""
        distribution = ICPackDistribution.objects.create(
            ic_pack=self.ic_pack,
            recipient_email="recipient@example.com",
            sent_by=self.user,
            group=self.group
        )
        
        expected = f"{self.ic_pack} -> recipient@example.com"
        self.assertEqual(str(distribution), expected)
    
    @patch('django.utils.timezone.now')
    def test_record_view(self, mock_now):
        """Test recording a view of the distributed pack."""
        mock_time = timezone.now()
        mock_now.return_value = mock_time
        
        distribution = ICPackDistribution.objects.create(
            ic_pack=self.ic_pack,
            recipient_email="recipient@example.com",
            sent_by=self.user,
            group=self.group
        )
        
        initial_pack_views = self.ic_pack.times_viewed
        
        # Record first view
        distribution.record_view()
        
        distribution.refresh_from_db()
        self.ic_pack.refresh_from_db()
        
        self.assertEqual(distribution.view_count, 1)
        self.assertEqual(distribution.first_viewed_at, mock_time)
        self.assertEqual(distribution.last_viewed_at, mock_time)
        self.assertEqual(self.ic_pack.times_viewed, initial_pack_views + 1)
        
        # Record second view
        mock_time2 = mock_time + timedelta(hours=1)
        mock_now.return_value = mock_time2
        
        distribution.record_view()
        
        distribution.refresh_from_db()
        self.ic_pack.refresh_from_db()
        
        self.assertEqual(distribution.view_count, 2)
        self.assertEqual(distribution.first_viewed_at, mock_time)  # Should not change
        self.assertEqual(distribution.last_viewed_at, mock_time2)
        self.assertEqual(self.ic_pack.times_viewed, initial_pack_views + 2)
    
    def test_is_expired(self):
        """Test expiration check."""
        # Create non-expired distribution
        active_distribution = ICPackDistribution.objects.create(
            ic_pack=self.ic_pack,
            recipient_email="active@example.com",
            sent_by=self.user,
            expires_at=timezone.now() + timedelta(days=1),
            group=self.group
        )
        
        # Create expired distribution
        expired_distribution = ICPackDistribution.objects.create(
            ic_pack=self.ic_pack,
            recipient_email="expired@example.com",
            sent_by=self.user,
            expires_at=timezone.now() - timedelta(days=1),
            group=self.group
        )
        
        # Create distribution with no expiry
        no_expiry_distribution = ICPackDistribution.objects.create(
            ic_pack=self.ic_pack,
            recipient_email="noexpiry@example.com",
            sent_by=self.user,
            group=self.group
        )
        
        self.assertFalse(active_distribution.is_expired())
        self.assertTrue(expired_distribution.is_expired())
        self.assertFalse(no_expiry_distribution.is_expired())


class ICPackAuditLogModelTests(TestCase):
    """Test ICPackAuditLog model functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.user.groups.add(self.group)
        
        # Create deal and template
        self.partner = DevelopmentPartner.objects.create(
            company_name="Test Partner Company",
            group=self.group
        )
        
        self.deal_type = DealType.objects.create(
            name="Test Deal Type",
            code="TEST",
            group=self.group
        )
        
        self.deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=1000000,
            group=self.group
        )
        
        self.template = ICPackTemplate.objects.create(
            name="Test Template",
            created_by=self.user,
            group=self.group
        )
        
        self.ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test IC Pack",
            created_by=self.user,
            group=self.group
        )
    
    def test_create_audit_log(self):
        """Test creating an audit log entry."""
        log_entry = ICPackAuditLog.objects.create(
            ic_pack=self.ic_pack,
            action=ICPackAuditLog.ActionType.CREATED,
            actor=self.user,
            description="IC pack created",
            metadata={"version": 1},
            changes={"status": "draft"},
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0 Test Browser",
            group=self.group
        )
        
        self.assertEqual(log_entry.ic_pack, self.ic_pack)
        self.assertEqual(log_entry.action, ICPackAuditLog.ActionType.CREATED)
        self.assertEqual(log_entry.actor, self.user)
        self.assertEqual(log_entry.description, "IC pack created")
        self.assertEqual(log_entry.metadata["version"], 1)
        self.assertEqual(log_entry.changes["status"], "draft")
        self.assertEqual(log_entry.ip_address, "192.168.1.1")
    
    def test_audit_log_string_representation(self):
        """Test audit log string representation."""
        log_entry = ICPackAuditLog.objects.create(
            ic_pack=self.ic_pack,
            action=ICPackAuditLog.ActionType.CREATED,
            actor=self.user,
            group=self.group
        )
        
        expected = f"{self.ic_pack} - Created by {self.user}"
        self.assertEqual(str(log_entry), expected)
    
    def test_log_action_classmethod(self):
        """Test the log_action class method."""
        metadata = {"key": "value"}
        changes = {"field": "old_value"}
        
        log_entry = ICPackAuditLog.log_action(
            ic_pack=self.ic_pack,
            action=ICPackAuditLog.ActionType.MODIFIED,
            actor=self.user,
            description="Pack was modified",
            metadata=metadata,
            changes=changes,
            ip_address="10.0.0.1",
            user_agent="Test Agent"
        )
        
        self.assertEqual(log_entry.ic_pack, self.ic_pack)
        self.assertEqual(log_entry.action, ICPackAuditLog.ActionType.MODIFIED)
        self.assertEqual(log_entry.actor, self.user)
        self.assertEqual(log_entry.description, "Pack was modified")
        self.assertEqual(log_entry.metadata, metadata)
        self.assertEqual(log_entry.changes, changes)
        self.assertEqual(log_entry.ip_address, "10.0.0.1")
        self.assertEqual(log_entry.user_agent, "Test Agent")
    
    def test_log_action_with_defaults(self):
        """Test log_action with default parameters."""
        log_entry = ICPackAuditLog.log_action(
            ic_pack=self.ic_pack,
            action=ICPackAuditLog.ActionType.VIEWED,
            actor=self.user
        )
        
        self.assertEqual(log_entry.description, '')
        self.assertEqual(log_entry.metadata, {})
        self.assertEqual(log_entry.changes, {})
        self.assertIsNone(log_entry.ip_address)
        self.assertEqual(log_entry.user_agent, '')


class ICPackModelEdgeCasesTests(TestCase):
    """Test edge cases and error conditions for IC pack models."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.user.groups.add(self.group)
        
        # Create basic objects
        self.partner = DevelopmentPartner.objects.create(
            company_name="Test Partner Company",
            group=self.group
        )
        
        self.deal_type = DealType.objects.create(
            name="Test Deal Type",
            code="TEST",
            group=self.group
        )
        
        self.deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=1000000,
            group=self.group
        )
    
    def test_template_with_empty_sections(self):
        """Test template with empty sections list."""
        template = ICPackTemplate.objects.create(
            name="Empty Template",
            sections=[],
            approval_stages=[],
            created_by=self.user,
            group=self.group
        )
        
        self.assertEqual(len(template.sections), 0)
        self.assertEqual(len(template.approval_stages), 0)
        
        # Should be able to create IC pack
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=template,
            title="Empty Template Pack",
            created_by=self.user,
            group=self.group
        )
        
        self.assertIsNotNone(ic_pack)
    
    def test_ic_pack_without_meeting_date(self):
        """Test IC pack without meeting date."""
        template = ICPackTemplate.objects.create(
            name="Test Template",
            created_by=self.user,
            group=self.group
        )
        
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=template,
            title="No Meeting Date Pack",
            created_by=self.user,
            group=self.group
        )
        
        self.assertIsNone(ic_pack.meeting_date)
        self.assertIsNone(ic_pack.approval_deadline)
    
    def test_get_next_approval_stage_with_no_current_stage(self):
        """Test getting next approval stage when no current stage is set."""
        template = ICPackTemplate.objects.create(
            name="Test Template",
            approval_stages=[
                {
                    "stage": "review",
                    "name": "Review",
                    "order": 1
                }
            ],
            created_by=self.user,
            group=self.group
        )
        
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=template,
            title="No Current Stage Pack",
            created_by=self.user,
            group=self.group
        )
        
        # Should return None when no current stage is set
        next_stage = ic_pack.get_next_approval_stage()
        self.assertIsNone(next_stage)
    
    def test_get_next_approval_stage_with_invalid_current_stage(self):
        """Test getting next approval stage with invalid current stage."""
        template = ICPackTemplate.objects.create(
            name="Test Template",
            approval_stages=[
                {
                    "stage": "review",
                    "name": "Review",
                    "order": 1
                }
            ],
            created_by=self.user,
            group=self.group
        )
        
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=template,
            title="Invalid Stage Pack",
            current_approval_stage="invalid_stage",
            created_by=self.user,
            group=self.group
        )
        
        # Should return None when current stage doesn't exist
        next_stage = ic_pack.get_next_approval_stage()
        self.assertIsNone(next_stage)
    
    def test_distribution_access_token_uniqueness(self):
        """Test that access tokens are unique across distributions."""
        template = ICPackTemplate.objects.create(
            name="Test Template",
            created_by=self.user,
            group=self.group
        )
        
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=template,
            title="Test Pack",
            created_by=self.user,
            group=self.group
        )
        
        # Create multiple distributions
        dist1 = ICPackDistribution.objects.create(
            ic_pack=ic_pack,
            recipient_email="user1@example.com",
            sent_by=self.user,
            group=self.group
        )
        
        dist2 = ICPackDistribution.objects.create(
            ic_pack=ic_pack,
            recipient_email="user2@example.com",
            sent_by=self.user,
            group=self.group
        )
        
        # Access tokens should be different
        self.assertNotEqual(dist1.access_token, dist2.access_token)