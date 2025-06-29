"""
Tests for IC pack automation service.

Comprehensive tests covering ICPackService functionality including
pack creation, data collection, PDF generation, approval workflows,
and distribution analytics.
"""

import io
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.base import ContentFile

from accounts.models import Group
from assessments.models import DevelopmentPartner, Assessment
from files.models import FileAttachment
from notifications.models import Notification
from deals.models import (
    Deal, DealType, DealSource, ICPackTemplate, ICPack, ICPackApproval,
    ICPackDistribution, ICPackAuditLog, ICPackStatus
)
from deals.services.ic_pack_service import ICPackService, ICPackGenerationError

User = get_user_model()


class ICPackServiceTests(TestCase):
    """Test ICPackService functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            role=User.Role.ANALYST
        )
        self.manager = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="testpass123",
            role=User.Role.MANAGER
        )
        self.user.groups.add(self.group)
        self.manager.groups.add(self.group)
        
        # Create basic models
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
            description="Test deal description",
            group=self.group
        )
        
        self.template = ICPackTemplate.objects.create(
            name="Test Template",
            sections=[
                {
                    "id": "executive_summary",
                    "title": "Executive Summary",
                    "order": 1,
                    "required": True,
                    "data_sources": ["deal", "partner"]
                },
                {
                    "id": "financial_analysis",
                    "title": "Financial Analysis",
                    "order": 2,
                    "required": True,
                    "data_sources": ["deal"]
                }
            ],
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
        
        # Create assessment for file attachments
        self.assessment = Assessment.objects.create(
            group=self.group,
            created_by=self.user,
            updated_by=self.user
        )
        
        self.service = ICPackService()
    
    def test_service_initialization(self):
        """Test ICPackService initialization."""
        service = ICPackService()
        
        # Check that custom styles are set up
        self.assertIn('ICTitle', service.styles)
        self.assertIn('SectionHeader', service.styles)
        self.assertIn('SubsectionHeader', service.styles)
    
    @patch('deals.services.ic_pack_service.ICPackAuditLog.log_action')
    def test_create_ic_pack_new(self, mock_log_action):
        """Test creating a new IC pack."""
        meeting_date = timezone.now() + timedelta(days=7)
        
        ic_pack = self.service.create_ic_pack(
            deal=self.deal,
            template=self.template,
            created_by=self.user,
            meeting_date=meeting_date
        )
        
        self.assertIsNotNone(ic_pack)
        self.assertEqual(ic_pack.deal, self.deal)
        self.assertEqual(ic_pack.template, self.template)
        self.assertEqual(ic_pack.created_by, self.user)
        self.assertEqual(ic_pack.meeting_date, meeting_date)
        self.assertEqual(ic_pack.version, 1)
        self.assertEqual(ic_pack.status, ICPackStatus.DRAFT)
        self.assertEqual(ic_pack.title, f"IC Pack - {self.deal.name}")
        
        # Check that sections data was collected
        self.assertIn('executive_summary', ic_pack.sections_data)
        self.assertIn('financial_analysis', ic_pack.sections_data)
        
        # Check audit log was called
        mock_log_action.assert_called_once_with(
            ic_pack=ic_pack,
            action=ICPackAuditLog.ActionType.CREATED,
            actor=self.user,
            description=f"Created IC pack v{ic_pack.version} for {self.deal.name}"
        )
    
    @patch('deals.services.ic_pack_service.ICPackAuditLog.log_action')
    def test_create_ic_pack_with_existing_draft(self, mock_log_action):
        """Test creating IC pack when a draft already exists."""
        # Create existing draft
        existing_draft = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Existing Draft",
            version=1,
            status=ICPackStatus.DRAFT,
            created_by=self.user,
            group=self.group
        )
        
        # Create new pack
        new_pack = self.service.create_ic_pack(
            deal=self.deal,
            template=self.template,
            created_by=self.manager
        )
        
        # Should create new version instead
        self.assertEqual(new_pack.version, 2)
        self.assertEqual(new_pack.created_by, self.manager)
        self.assertEqual(new_pack.deal, self.deal)
        self.assertEqual(new_pack.template, self.template)
        
        # Original draft should still exist
        existing_draft.refresh_from_db()
        self.assertEqual(existing_draft.version, 1)
    
    def test_collect_pack_data(self):
        """Test data collection for IC pack sections."""
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test Pack",
            created_by=self.user,
            group=self.group
        )
        
        # Call private method for testing
        self.service._collect_pack_data(ic_pack)
        
        ic_pack.refresh_from_db()
        
        # Check executive summary data
        exec_summary = ic_pack.sections_data['executive_summary']
        self.assertEqual(exec_summary['deal_name'], self.deal.name)
        self.assertEqual(exec_summary['deal_type'], self.deal.get_deal_type_display())
        self.assertIn('key_highlights', exec_summary)
        self.assertIn('recommendation', exec_summary)
        
        # Check deal overview data
        deal_overview = ic_pack.sections_data['deal_overview']
        self.assertEqual(deal_overview['description'], self.deal.description)
        self.assertIn('objectives', deal_overview)
        self.assertIn('timeline', deal_overview)
        
        # Check financial analysis data
        financial = ic_pack.sections_data['financial_analysis']
        self.assertIn('investment_structure', financial)
        self.assertIn('financial_projections', financial)
        
        # Check risk assessment data
        risk = ic_pack.sections_data['risk_assessment']
        self.assertIn('key_risks', risk)
        self.assertIn('mitigation_strategies', risk)
        
        # Check due diligence data
        dd = ic_pack.sections_data['due_diligence']
        self.assertIn('completed_items', dd)
        self.assertIn('outstanding_items', dd)
        
        # Check market analysis data
        market = ic_pack.sections_data['market_analysis']
        self.assertIn('market_overview', market)
        self.assertIn('competitive_landscape', market)
    
    def test_get_key_highlights_with_milestones(self):
        """Test key highlights generation with milestones."""
        # Create some milestones
        from deals.models import DealMilestone
        
        # Create completed milestone
        DealMilestone.objects.create(
            deal=self.deal,
            title="Due Diligence Complete",
            description="DD completed",
            target_date=timezone.now().date(),
            status='completed',
            group=self.group
        )
        
        # Create pending milestone
        DealMilestone.objects.create(
            deal=self.deal,
            title="Final Approval",
            description="Get final approval",
            target_date=timezone.now().date() + timedelta(days=30),
            status='pending',
            group=self.group
        )
        
        highlights = self.service._get_key_highlights(self.deal)
        
        # Should include milestone progress
        milestone_highlight = next(
            (h for h in highlights if "Milestone Progress" in h),
            None
        )
        self.assertIsNotNone(milestone_highlight)
        self.assertIn("1/2 completed", milestone_highlight)
    
    def test_get_key_highlights_default(self):
        """Test key highlights with default values."""
        highlights = self.service._get_key_highlights(self.deal)
        
        # Should have default highlights when no specific data
        self.assertIn("Strategic investment opportunity", highlights)
        self.assertIn("Strong market position", highlights)
    
    def test_generate_recommendation_with_stage(self):
        """Test recommendation generation based on deal stage."""
        from deals.models import DealStage
        
        # Create deal stage
        stage = DealStage.objects.create(
            name="Due Diligence",
            order=3,
            group=self.group
        )
        self.deal.current_stage = stage
        self.deal.save()
        
        recommendation = self.service._generate_recommendation(self.deal)
        
        self.assertEqual(
            recommendation,
            "Proceed with investment subject to final due diligence completion"
        )
    
    def test_generate_recommendation_early_stage(self):
        """Test recommendation for early stage deal."""
        from deals.models import DealStage
        
        # Create early stage
        stage = DealStage.objects.create(
            name="Initial Review",
            order=1,
            group=self.group
        )
        self.deal.current_stage = stage
        self.deal.save()
        
        recommendation = self.service._generate_recommendation(self.deal)
        
        self.assertEqual(
            recommendation,
            "Continue evaluation and address outstanding items"
        )
    
    def test_get_team_summary(self):
        """Test getting deal team summary."""
        from deals.models import DealTeamMember, DealRole
        
        # Create deal role and team member
        role = DealRole.objects.create(
            name="Deal Lead",
            code="deal_lead",
            group=self.group
        )
        
        DealTeamMember.objects.create(
            deal=self.deal,
            user=self.user,
            role=role,
            group=self.group
        )
        
        team_summary = self.service._get_team_summary(self.deal)
        
        self.assertEqual(len(team_summary), 1)
        self.assertEqual(team_summary[0]['name'], self.user.get_full_name())
        self.assertEqual(team_summary[0]['email'], self.user.email)
    
    @patch('deals.services.ic_pack_service.SimpleDocTemplate')
    @patch('deals.services.ic_pack_service.FileAttachment.objects.create')
    @patch('deals.services.ic_pack_service.ICPackAuditLog.log_action')
    @patch('django.utils.timezone.now')
    def test_generate_ic_pack_document_success(self, mock_now, mock_log_action, 
                                               mock_file_create, mock_doc):
        """Test successful IC pack document generation."""
        # Setup mocks
        start_time = timezone.now()
        end_time = start_time + timedelta(seconds=5)
        mock_now.side_effect = [start_time, end_time]
        
        mock_doc_instance = MagicMock()
        mock_doc.return_value = mock_doc_instance
        
        mock_file_attachment = MagicMock()
        mock_file_attachment.file = MagicMock()
        mock_file_create.return_value = mock_file_attachment
        
        # Create IC pack
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test Pack",
            created_by=self.user,
            sections_data={
                "executive_summary": {"deal_name": "Test Deal"},
                "financial_analysis": {"investment_structure": "TBD"}
            },
            group=self.group
        )
        
        # Generate document
        result = self.service.generate_ic_pack_document(ic_pack, self.user)
        
        # Verify document was built
        mock_doc_instance.build.assert_called_once()
        
        # Verify file attachment was created
        mock_file_create.assert_called_once()
        create_args = mock_file_create.call_args[1]
        self.assertIn("IC_Pack_", create_args['file_name'])
        self.assertEqual(create_args['file_type'], 'application/pdf')
        self.assertEqual(create_args['uploaded_by'], self.user)
        
        # Verify IC pack was updated
        ic_pack.refresh_from_db()
        self.assertEqual(ic_pack.generated_document, mock_file_attachment)
        self.assertEqual(ic_pack.generation_time_seconds, 5.0)
        
        # Verify audit log
        mock_log_action.assert_called_once_with(
            ic_pack=ic_pack,
            action=ICPackAuditLog.ActionType.MODIFIED,
            actor=self.user,
            description="Generated PDF document in 5.00 seconds"
        )
        
        self.assertEqual(result, mock_file_attachment)
    
    @patch('deals.services.ic_pack_service.SimpleDocTemplate')
    def test_generate_ic_pack_document_error(self, mock_doc):
        """Test IC pack document generation error handling."""
        # Setup mock to raise exception
        mock_doc.side_effect = Exception("PDF generation failed")
        
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test Pack",
            created_by=self.user,
            group=self.group
        )
        
        # Should raise ICPackGenerationError
        with self.assertRaises(ICPackGenerationError) as context:
            self.service.generate_ic_pack_document(ic_pack, self.user)
        
        self.assertIn("Failed to generate IC pack", str(context.exception))
    
    def test_build_pdf_content(self):
        """Test building PDF content from IC pack data."""
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test IC Pack",
            meeting_date=timezone.now() + timedelta(days=7),
            version=2,
            sections_data={
                "executive_summary": {
                    "deal_name": "Test Deal",
                    "key_highlights": ["Highlight 1", "Highlight 2"]
                },
                "financial_analysis": {
                    "investment_structure": {"total": "1M", "type": "Equity"}
                }
            },
            created_by=self.user,
            group=self.group
        )
        
        story = self.service._build_pdf_content(ic_pack)
        
        # Should have content elements
        self.assertGreater(len(story), 0)
        
        # Should include page breaks for sections
        from reportlab.platypus import PageBreak
        page_breaks = [elem for elem in story if isinstance(elem, PageBreak)]
        self.assertGreater(len(page_breaks), 0)
    
    def test_build_section(self):
        """Test building a PDF section from data."""
        data = {
            "deal_name": "Test Deal",
            "key_highlights": ["Highlight 1", "Highlight 2"],
            "financial_details": {
                "amount": "1M",
                "currency": "USD"
            }
        }
        
        elements = self.service._build_section("Executive Summary", data)
        
        # Should have section header and content
        self.assertGreater(len(elements), 0)
        
        # Check that all data types are handled
        from reportlab.platypus import Paragraph
        paragraphs = [elem for elem in elements if isinstance(elem, Paragraph)]
        self.assertGreater(len(paragraphs), 0)
    
    @patch('deals.services.ic_pack_service.ICPackAuditLog.log_action')
    @patch('deals.services.ic_pack_service.Notification.objects.create')
    def test_submit_for_approval_success(self, mock_notification, mock_log_action):
        """Test successful submission for approval."""
        # Create file attachment for the pack
        file_attachment = FileAttachment.objects.create(
            file_name="test_pack.pdf",
            file_type="application/pdf",
            file_size=1024,
            uploaded_by=self.user,
            assessment=self.assessment
        )
        
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test Pack",
            generated_document=file_attachment,
            created_by=self.user,
            group=self.group
        )
        
        # Submit for approval
        self.service.submit_for_approval(ic_pack, self.user)
        
        # Check status transitions
        ic_pack.refresh_from_db()
        self.assertEqual(ic_pack.status, ICPackStatus.IN_REVIEW)
        self.assertEqual(ic_pack.current_approval_stage, "analyst_review")
        
        # Check approval record was created
        approval = ICPackApproval.objects.get(ic_pack=ic_pack)
        self.assertEqual(approval.stage, "analyst_review")
        self.assertEqual(approval.stage_name, "Analyst Review")
        
        # Check notifications were sent to analysts
        mock_notification.assert_called()
        notification_calls = mock_notification.call_args_list
        
        # Should have notifications for analysts
        analyst_notifications = [
            call for call in notification_calls
            if call[1]['notification_type'] == 'IC_PACK_APPROVAL'
        ]
        self.assertGreater(len(analyst_notifications), 0)
        
        # Check audit log
        mock_log_action.assert_called_with(
            ic_pack=ic_pack,
            action=ICPackAuditLog.ActionType.SUBMITTED,
            actor=self.user,
            description="Submitted for approval"
        )
    
    def test_submit_for_approval_without_document(self):
        """Test submission for approval without generated document."""
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test Pack",
            created_by=self.user,
            group=self.group
        )
        
        # Should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.service.submit_for_approval(ic_pack, self.user)
        
        self.assertIn("must have a generated document", str(context.exception))
    
    def test_find_approvers_for_stage(self):
        """Test finding approvers for approval stage."""
        # Create additional analyst
        analyst2 = User.objects.create_user(
            username="analyst2",
            email="analyst2@example.com",
            password="testpass123",
            role=User.Role.ANALYST
        )
        analyst2.groups.add(self.group)
        
        # Create user in different group
        other_group = Group.objects.create(name="Other Group")
        other_analyst = User.objects.create_user(
            username="other_analyst",
            email="other@example.com",
            password="testpass123",
            role=User.Role.ANALYST
        )
        other_analyst.groups.add(other_group)
        
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test Pack",
            created_by=self.manager,  # Different from analysts
            group=self.group
        )
        
        stage_config = {
            "stage": "analyst_review",
            "required_role": "ANALYST"
        }
        
        approvers = self.service._find_approvers_for_stage(ic_pack, stage_config)
        
        # Should find analysts in same group, excluding creator
        self.assertEqual(len(approvers), 2)  # self.user and analyst2
        self.assertIn(self.user, approvers)
        self.assertIn(analyst2, approvers)
        self.assertNotIn(self.manager, approvers)  # Creator excluded
        self.assertNotIn(other_analyst, approvers)  # Different group
    
    @patch('deals.services.ic_pack_service.ICPackAuditLog.log_action')
    def test_distribute_ic_pack_success(self, mock_log_action):
        """Test successful IC pack distribution."""
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test Pack",
            status=ICPackStatus.APPROVED,
            created_by=self.user,
            group=self.group
        )
        
        recipient_emails = ["investor1@example.com", "investor2@example.com"]
        message = "Please review the attached IC pack"
        
        # Mock email sending
        with patch.object(self.service, '_send_distribution_email') as mock_email:
            self.service.distribute_ic_pack(
                ic_pack=ic_pack,
                user=self.user,
                recipient_emails=recipient_emails,
                message=message
            )
        
        # Check status updated
        ic_pack.refresh_from_db()
        self.assertEqual(ic_pack.status, ICPackStatus.DISTRIBUTED)
        self.assertIsNotNone(ic_pack.distributed_at)
        
        # Check distribution records created
        distributions = ICPackDistribution.objects.filter(ic_pack=ic_pack)
        self.assertEqual(distributions.count(), 2)
        
        distribution_emails = list(distributions.values_list('recipient_email', flat=True))
        self.assertEqual(sorted(distribution_emails), sorted(recipient_emails))
        
        # Check expiration dates set
        for dist in distributions:
            self.assertIsNotNone(dist.expires_at)
            self.assertEqual(dist.sent_by, self.user)
        
        # Check emails were sent
        self.assertEqual(mock_email.call_count, 2)
        
        # Check audit log
        mock_log_action.assert_called_with(
            ic_pack=ic_pack,
            action=ICPackAuditLog.ActionType.DISTRIBUTED,
            actor=self.user,
            description="Distributed to 2 recipients",
            metadata={'recipients': recipient_emails}
        )
    
    def test_distribute_ic_pack_not_approved(self):
        """Test distribution of non-approved IC pack."""
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test Pack",
            status=ICPackStatus.DRAFT,
            created_by=self.user,
            group=self.group
        )
        
        # Should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.service.distribute_ic_pack(
                ic_pack=ic_pack,
                user=self.user,
                recipient_emails=["test@example.com"]
            )
        
        self.assertIn("Only approved IC packs can be distributed", str(context.exception))
    
    @patch('deals.services.ic_pack_service.logger')
    def test_send_distribution_email(self, mock_logger):
        """Test sending distribution email."""
        ic_pack = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Test Pack",
            created_by=self.user,
            group=self.group
        )
        
        distribution = ICPackDistribution.objects.create(
            ic_pack=ic_pack,
            recipient_email="test@example.com",
            sent_by=self.user,
            group=self.group
        )
        
        # Call the method
        self.service._send_distribution_email(distribution, "Test message")
        
        # Should log the email sending
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        self.assertIn("Test Pack", log_message)
        self.assertIn("test@example.com", log_message)
    
    def test_get_ic_pack_analytics_empty(self):
        """Test analytics for deal with no IC packs."""
        analytics = self.service.get_ic_pack_analytics(self.deal)
        
        self.assertEqual(analytics['total_packs'], 0)
        self.assertEqual(analytics['latest_version'], 0)
        self.assertEqual(analytics['average_generation_time'], 0)
        self.assertEqual(analytics['total_distributions'], 0)
        self.assertIsNone(analytics['average_approval_time'])
    
    def test_get_ic_pack_analytics_with_data(self):
        """Test analytics with actual IC pack data."""
        # Create IC packs with different statuses
        pack1 = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Pack 1",
            version=1,
            status=ICPackStatus.DRAFT,
            generation_time_seconds=3.5,
            created_by=self.user,
            group=self.group
        )
        
        pack2 = ICPack.objects.create(
            deal=self.deal,
            template=self.template,
            title="Pack 2",
            version=2,
            status=ICPackStatus.APPROVED,
            generation_time_seconds=4.5,
            created_by=self.user,
            group=self.group
        )
        
        # Create distributions
        ICPackDistribution.objects.create(
            ic_pack=pack2,
            recipient_email="user1@example.com",
            sent_by=self.user,
            view_count=3,
            group=self.group
        )
        
        ICPackDistribution.objects.create(
            ic_pack=pack2,
            recipient_email="user2@example.com",
            sent_by=self.user,
            view_count=2,
            group=self.group
        )
        
        # Create audit logs for approval time calculation
        ICPackAuditLog.objects.create(
            ic_pack=pack2,
            action=ICPackAuditLog.ActionType.SUBMITTED,
            actor=self.user,
            created_at=timezone.now() - timedelta(hours=2),
            group=self.group
        )
        
        ICPackAuditLog.objects.create(
            ic_pack=pack2,
            action=ICPackAuditLog.ActionType.APPROVED,
            actor=self.manager,
            created_at=timezone.now(),
            group=self.group
        )
        
        analytics = self.service.get_ic_pack_analytics(self.deal)
        
        # Check basic metrics
        self.assertEqual(analytics['total_packs'], 2)
        self.assertEqual(analytics['latest_version'], 2)
        self.assertEqual(analytics['average_generation_time'], 4.0)  # (3.5 + 4.5) / 2
        self.assertEqual(analytics['total_distributions'], 2)
        
        # Check status distribution
        self.assertEqual(analytics['status_distribution']['Draft'], 1)
        self.assertEqual(analytics['status_distribution']['Approved'], 1)
        
        # Check approval time (should be ~2 hours)
        self.assertIsNotNone(analytics['average_approval_time'])
        self.assertAlmostEqual(analytics['average_approval_time'], 2.0, places=1)
        
        # Check engagement metrics
        self.assertEqual(analytics['engagement_metrics']['total_views'], 5)  # 3 + 2
        self.assertEqual(analytics['engagement_metrics']['unique_viewers'], 2)


class ICPackServiceEdgeCasesTests(TestCase):
    """Test edge cases and error conditions for ICPackService."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.user.groups.add(self.group)
        
        self.service = ICPackService()
    
    def test_collect_pack_data_with_minimal_deal(self):
        """Test data collection with minimal deal data."""
        # Create minimal deal without optional fields
        deal_type = DealType.objects.create(
            name="Minimal Type",
            code="MIN",
            group=self.group
        )
        
        deal_source = DealSource.objects.create(
            name="Minimal Source",
            code="MIN_SRC",
            group=self.group
        )
        
        deal = Deal.objects.create(
            name="Minimal Deal",
            code="MIN-001",
            deal_type=deal_type,
            deal_source=deal_source,
            investment_amount=100000,
            group=self.group
        )
        
        template = ICPackTemplate.objects.create(
            name="Minimal Template",
            sections=[],
            created_by=self.user,
            group=self.group
        )
        
        ic_pack = ICPack.objects.create(
            deal=deal,
            template=template,
            title="Minimal Pack",
            created_by=self.user,
            group=self.group
        )
        
        # Should not raise errors
        self.service._collect_pack_data(ic_pack)
        
        ic_pack.refresh_from_db()
        self.assertIsInstance(ic_pack.sections_data, dict)
    
    def test_build_pdf_content_with_no_sections(self):
        """Test PDF building with no sections."""
        deal_type = DealType.objects.create(
            name="Test Type",
            code="TEST",
            group=self.group
        )
        
        deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=deal_type,
            deal_source=deal_source,
            investment_amount=100000,
            group=self.group
        )
        
        template = ICPackTemplate.objects.create(
            name="Empty Template",
            sections=[],
            created_by=self.user,
            group=self.group
        )
        
        ic_pack = ICPack.objects.create(
            deal=deal,
            template=template,
            title="Empty Pack",
            created_by=self.user,
            group=self.group
        )
        
        story = self.service._build_pdf_content(ic_pack)
        
        # Should have at least title page elements
        self.assertGreater(len(story), 0)
    
    def test_build_section_with_empty_data(self):
        """Test building section with empty data."""
        elements = self.service._build_section("Empty Section", {})
        
        # Should have at least section header
        self.assertGreater(len(elements), 0)
    
    def test_build_section_with_nested_data(self):
        """Test building section with deeply nested data."""
        complex_data = {
            "overview": {
                "company": {
                    "name": "Complex Corp",
                    "details": {
                        "founded": "2020",
                        "employees": 50
                    }
                }
            },
            "metrics": [
                {"name": "Revenue", "value": "1M", "trend": "up"},
                {"name": "Profit", "value": "200K", "trend": "stable"}
            ]
        }
        
        elements = self.service._build_section("Complex Section", complex_data)
        
        # Should handle nested structures without errors
        self.assertGreater(len(elements), 0)
    
    def test_find_approvers_with_no_matching_users(self):
        """Test finding approvers when no users match criteria."""
        deal_type = DealType.objects.create(
            name="Test Type",
            code="TEST",
            group=self.group
        )
        
        deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=deal_type,
            deal_source=deal_source,
            investment_amount=100000,
            group=self.group
        )
        
        template = ICPackTemplate.objects.create(
            name="Test Template",
            created_by=self.user,
            group=self.group
        )
        
        ic_pack = ICPack.objects.create(
            deal=deal,
            template=template,
            title="Test Pack",
            created_by=self.user,
            group=self.group
        )
        
        stage_config = {
            "stage": "ceo_approval",
            "required_role": "CEO"  # No users with this role
        }
        
        approvers = self.service._find_approvers_for_stage(ic_pack, stage_config)
        
        # Should return empty list
        self.assertEqual(len(approvers), 0)
    
    def test_analytics_with_no_audit_logs(self):
        """Test analytics calculation with missing audit logs."""
        deal_type = DealType.objects.create(
            name="Test Type",
            code="TEST",
            group=self.group
        )
        
        deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=deal_type,
            deal_source=deal_source,
            investment_amount=100000,
            group=self.group
        )
        
        template = ICPackTemplate.objects.create(
            name="Test Template",
            created_by=self.user,
            group=self.group
        )
        
        # Create approved pack without audit logs
        ICPack.objects.create(
            deal=deal,
            template=template,
            title="Approved Pack",
            status=ICPackStatus.APPROVED,
            created_by=self.user,
            group=self.group
        )
        
        analytics = self.service.get_ic_pack_analytics(deal)
        
        # Should handle missing audit logs gracefully
        self.assertIsNone(analytics['average_approval_time'])
        self.assertEqual(analytics['total_packs'], 1)
    
    @patch('deals.services.ic_pack_service.User.objects.filter')
    def test_submit_for_approval_with_no_template_stages(self, mock_filter):
        """Test submission when template has no approval stages."""
        mock_filter.return_value = []
        
        deal_type = DealType.objects.create(
            name="Test Type",
            code="TEST",
            group=self.group
        )
        
        deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=deal_type,
            deal_source=deal_source,
            investment_amount=100000,
            group=self.group
        )
        
        template = ICPackTemplate.objects.create(
            name="No Stages Template",
            approval_stages=[],  # No approval stages
            created_by=self.user,
            group=self.group
        )
        
        # Create assessment for file attachment
        assessment = Assessment.objects.create(
            group=self.group,
            created_by=self.user,
            updated_by=self.user
        )
        
        file_attachment = FileAttachment.objects.create(
            file_name="test.pdf",
            file_type="application/pdf",
            file_size=1024,
            uploaded_by=self.user,
            assessment=assessment
        )
        
        ic_pack = ICPack.objects.create(
            deal=deal,
            template=template,
            title="No Stages Pack",
            generated_document=file_attachment,
            created_by=self.user,
            group=self.group
        )
        
        # Should not create approval records
        self.service.submit_for_approval(ic_pack, self.user)
        
        # Check status transitions still occur
        ic_pack.refresh_from_db()
        self.assertEqual(ic_pack.status, ICPackStatus.IN_REVIEW)
        
        # Should not have any approval records
        self.assertEqual(ICPackApproval.objects.filter(ic_pack=ic_pack).count(), 0)