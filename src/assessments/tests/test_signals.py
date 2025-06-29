"""
Tests for assessment signals.

Tests that signals are properly registered and fire correctly when assessments
are created, updated, and deleted.
"""

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
import os

from accounts.models import Group, GroupMembership
from assessments.models import Assessment, DevelopmentPartner, PBSAScheme
from notifications.models import Notification

User = get_user_model()


class AssessmentSignalTests(TestCase):
    """Test assessment signals."""
    
    def setUp(self):
        """Set up test data."""
        # Create group and user
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            role=User.Role.BUSINESS_ANALYST
        )
        GroupMembership.objects.create(user=self.user, group=self.group)
        
        # Create development partner
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name="Test Partner Ltd",
            headquarter_city="London",
            headquarter_country="GB",
            year_established=2020
        )
        
        # Create PBSA scheme
        self.scheme = PBSAScheme.objects.create(
            group=self.group,
            scheme_name="Test Scheme",
            developer=self.partner,
            total_beds=100,
            target_location="London",
            total_investment=1000000.00
        )

    @patch('notifications.tasks.create_notification.delay')
    @patch('notifications.tasks.send_webhook_event.delay')
    def test_assessment_creation_signals(self, mock_webhook, mock_notification):
        """Test that signals fire when assessment is created."""
        # Ensure signals are not disabled
        if 'DISABLE_SIGNALS' in os.environ:
            del os.environ['DISABLE_SIGNALS']
        
        # Create assessment
        assessment = Assessment.objects.create(
            group=self.group,
            development_partner=self.partner,
            pbsa_scheme=self.scheme,
            assessment_type=Assessment.AssessmentType.FULL,
            status=Assessment.AssessmentStatus.DRAFT,
            created_by=self.user
        )
        
        # Check that notification task was called
        mock_notification.assert_called_once()
        call_args = mock_notification.call_args[1]
        self.assertEqual(call_args['recipient_id'], str(self.user.id))
        self.assertEqual(call_args['notification_type'], 'assessment_created')
        self.assertEqual(call_args['assessment_id'], str(assessment.id))
        
        # Check that webhook task was called
        mock_webhook.assert_called_once()
        webhook_args = mock_webhook.call_args[0]
        self.assertEqual(webhook_args[0], 'assessment.created')
        self.assertEqual(webhook_args[1]['assessment_id'], str(assessment.id))

    @patch('notifications.tasks.create_notification.delay')
    @patch('notifications.tasks.send_webhook_event.delay')
    def test_assessment_approval_signals(self, mock_webhook, mock_notification):
        """Test that signals fire when assessment is approved."""
        # Create assessment
        assessment = Assessment.objects.create(
            group=self.group,
            development_partner=self.partner,
            pbsa_scheme=self.scheme,
            assessment_type=Assessment.AssessmentType.FULL,
            status=Assessment.AssessmentStatus.DRAFT,
            created_by=self.user
        )
        
        # Clear the creation signals
        mock_notification.reset_mock()
        mock_webhook.reset_mock()
        
        # Approve assessment
        assessment.status = Assessment.AssessmentStatus.APPROVED
        assessment.decision = Assessment.AssessmentDecision.ACCEPTABLE
        assessment.approved_by = self.user
        assessment.save()
        
        # Check that notification task was called for approval
        mock_notification.assert_called_once()
        call_args = mock_notification.call_args[1]
        self.assertEqual(call_args['notification_type'], 'assessment_approved')
        
        # Check that webhook task was called for approval
        mock_webhook.assert_called_once()
        webhook_args = mock_webhook.call_args[0]
        self.assertEqual(webhook_args[0], 'assessment.approved')

    @patch('notifications.tasks.create_notification.delay')
    @patch('notifications.tasks.send_webhook_event.delay')
    def test_assessment_rejection_signals(self, mock_webhook, mock_notification):
        """Test that signals fire when assessment is rejected."""
        # Create assessment
        assessment = Assessment.objects.create(
            group=self.group,
            development_partner=self.partner,
            pbsa_scheme=self.scheme,
            assessment_type=Assessment.AssessmentType.FULL,
            status=Assessment.AssessmentStatus.DRAFT,
            created_by=self.user
        )
        
        # Clear the creation signals
        mock_notification.reset_mock()
        mock_webhook.reset_mock()
        
        # Reject assessment
        assessment.status = Assessment.AssessmentStatus.REJECTED
        assessment.approved_by = self.user
        assessment.save()
        
        # Check that notification task was called for rejection
        mock_notification.assert_called_once()
        call_args = mock_notification.call_args[1]
        self.assertEqual(call_args['notification_type'], 'assessment_rejected')
        
        # Check that webhook task was called for rejection
        mock_webhook.assert_called_once()
        webhook_args = mock_webhook.call_args[0]
        self.assertEqual(webhook_args[0], 'assessment.rejected')

    @override_settings(DISABLE_SIGNALS=True)
    @patch('notifications.tasks.create_notification.delay')
    @patch('notifications.tasks.send_webhook_event.delay')
    def test_signals_disabled_when_env_set(self, mock_webhook, mock_notification):
        """Test that signals don't fire when DISABLE_SIGNALS is set."""
        # Set environment variable to disable signals
        os.environ['DISABLE_SIGNALS'] = '1'
        
        try:
            # Create assessment
            assessment = Assessment.objects.create(
                group=self.group,
                development_partner=self.partner,
                pbsa_scheme=self.scheme,
                assessment_type=Assessment.AssessmentType.FULL,
                status=Assessment.AssessmentStatus.DRAFT,
                created_by=self.user
            )
            
            # Check that no signals were sent
            mock_notification.assert_not_called()
            mock_webhook.assert_not_called()
            
        finally:
            # Clean up environment variable
            del os.environ['DISABLE_SIGNALS']

    @patch('assessments.signals.create_audit_log')
    def test_audit_log_signals(self, mock_audit_log):
        """Test that audit log signals fire for model changes."""
        # Create assessment
        assessment = Assessment.objects.create(
            group=self.group,
            development_partner=self.partner,
            pbsa_scheme=self.scheme,
            assessment_type=Assessment.AssessmentType.FULL,
            status=Assessment.AssessmentStatus.DRAFT,
            created_by=self.user
        )
        
        # Check that audit log was called for creation
        mock_audit_log.assert_called()
        
        # Reset mock
        mock_audit_log.reset_mock()
        
        # Update assessment
        assessment.status = Assessment.AssessmentStatus.IN_REVIEW
        assessment.save()
        
        # Check that audit log was called for update
        mock_audit_log.assert_called()

    def test_signal_import_in_apps_ready(self):
        """Test that signals module is imported when app is ready."""
        from assessments.apps import AssessmentsConfig
        from django.apps import apps
        
        # Get the app config
        app_config = apps.get_app_config('assessments')
        self.assertIsInstance(app_config, AssessmentsConfig)
        
        # Test the ready method doesn't raise exceptions
        try:
            app_config.ready()
        except Exception as e:
            self.fail(f"App ready method raised exception: {e}")