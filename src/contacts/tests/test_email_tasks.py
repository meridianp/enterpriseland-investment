"""
Tests for Celery email tasks.

Comprehensive test coverage for email sending tasks, batch processing,
rate limiting, retry logic, campaign completion, and external service mocking.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, Mock, MagicMock, call
from unittest import skip

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from celery.exceptions import Retry, MaxRetriesExceededError
import factory

from accounts.models import Group, GroupMembership, Role
from contacts.models import (
    Contact, ContactList, EmailTemplate, EmailCampaign,
    EmailMessage, EmailEvent, ContactActivity, ActivityType
)
from contacts.email_tasks import (
    send_campaign_emails, send_single_email, send_test_email,
    process_email_event, schedule_campaign, process_campaign_batch,
    check_campaign_completion, send_campaign_report,
    _get_campaign_recipients, _render_email_for_contact,
    _track_email_sent, _track_email_event
)
from notifications.models import Notification

User = get_user_model()


# Re-use factories from previous tests
class GroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Group
    
    name = factory.Sequence(lambda n: f"Test Group {n}")


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.Sequence(lambda n: f"user{n}@test.com")
    first_name = "Test"
    last_name = factory.Sequence(lambda n: f"User{n}")


class ContactFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Contact
    
    email = factory.Sequence(lambda n: f"contact{n}@example.com")
    first_name = factory.Sequence(lambda n: f"Contact{n}")
    last_name = "Test"
    contact_type = Contact.ContactType.INDIVIDUAL
    status = Contact.ContactStatus.LEAD
    email_opt_in = True
    group = factory.SubFactory(GroupFactory)


class ContactListFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ContactList
    
    name = factory.Sequence(lambda n: f"List {n}")
    description = "Test contact list"
    is_dynamic = False
    created_by = factory.SubFactory(UserFactory)
    group = factory.SubFactory(GroupFactory)


class EmailTemplateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailTemplate
    
    name = factory.Sequence(lambda n: f"Template {n}")
    template_type = EmailTemplate.TemplateType.MARKETING
    subject = "Test Subject - {{ first_name }}"
    preheader = "Test preheader"
    html_content = "<html><body>Hello {{ first_name }}! <a href='{{ unsubscribe_url }}'>Unsubscribe</a></body></html>"
    text_content = "Hello {{ first_name }}! Unsubscribe: {{ unsubscribe_url }}"
    from_name = "Test Sender"
    from_email = "noreply@test.com"
    is_active = True
    is_tested = False
    created_by = factory.SubFactory(UserFactory)
    group = factory.SubFactory(GroupFactory)


class EmailCampaignFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailCampaign
    
    name = factory.Sequence(lambda n: f"Campaign {n}")
    description = "Test campaign"
    template = factory.SubFactory(EmailTemplateFactory)
    status = EmailCampaign.CampaignStatus.DRAFT
    sending_strategy = EmailCampaign.SendingStrategy.IMMEDIATE
    track_opens = True
    track_clicks = True
    include_unsubscribe_link = True
    created_by = factory.SubFactory(UserFactory)
    group = factory.SubFactory(GroupFactory)


class EmailMessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailMessage
    
    campaign = factory.SubFactory(EmailCampaignFactory)
    contact = factory.SubFactory(ContactFactory)
    template_used = factory.SubFactory(EmailTemplateFactory)
    subject = "Test Email"
    from_email = "noreply@test.com"
    to_email = factory.Sequence(lambda n: f"recipient{n}@example.com")
    status = EmailMessage.MessageStatus.PENDING
    group = factory.SubFactory(GroupFactory)


class SendCampaignEmailsTaskTests(TransactionTestCase):
    """Test cases for send_campaign_emails task."""
    
    def setUp(self):
        """Set up test data."""
        self.group = GroupFactory()
        self.user = UserFactory()
        GroupMembership.objects.create(user=self.user, group=self.group)
        
        # Create campaign with template
        self.template = EmailTemplateFactory(group=self.group)
        self.campaign = EmailCampaignFactory(
            group=self.group,
            template=self.template,
            status=EmailCampaign.CampaignStatus.SENDING,
            send_rate_per_hour=120  # 2 per minute for testing
        )
        
        # Create contact list with contacts
        self.contact_list = ContactListFactory(group=self.group)
        self.contacts = [
            ContactFactory(group=self.group, email_opt_in=True)
            for _ in range(5)
        ]
        self.contact_list.contacts.add(*self.contacts)
        self.campaign.contact_lists.add(self.contact_list)
    
    @patch('contacts.email_tasks.send_single_email.delay')
    @patch('contacts.email_tasks.check_campaign_completion.delay')
    def test_send_campaign_basic(self, mock_check_completion, mock_send_single):
        """Test basic campaign sending."""
        result = send_campaign_emails(str(self.campaign.id))
        
        self.assertEqual(result['status'], 'processing')
        self.assertEqual(result['batch_size'], 2)  # Based on send rate
        
        # Verify messages were created
        messages = EmailMessage.objects.filter(campaign=self.campaign)
        self.assertEqual(messages.count(), 5)
        
        # Verify send tasks were called
        self.assertEqual(mock_send_single.call_count, 5)
        
        # Verify completion check was scheduled
        mock_check_completion.assert_called()
    
    def test_send_campaign_invalid_status(self):
        """Test sending campaign with invalid status."""
        self.campaign.status = EmailCampaign.CampaignStatus.DRAFT
        self.campaign.save()
        
        result = send_campaign_emails(str(self.campaign.id))
        
        self.assertEqual(result['status'], 'skipped')
        self.assertIn('Invalid campaign status', result['reason'])
    
    def test_send_campaign_no_recipients(self):
        """Test sending campaign with no recipients."""
        # Remove all contacts from list
        self.contact_list.contacts.clear()
        
        result = send_campaign_emails(str(self.campaign.id))
        
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['sent'], 0)
        
        # Campaign should be marked as sent
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, EmailCampaign.CampaignStatus.SENT)
        self.assertIsNotNone(self.campaign.completed_at)
    
    @patch('contacts.email_tasks.send_single_email.delay')
    def test_send_campaign_with_exclusions(self, mock_send_single):
        """Test campaign respects excluded contacts."""
        # Exclude some contacts
        self.campaign.excluded_contacts.add(self.contacts[0], self.contacts[1])
        
        result = send_campaign_emails(str(self.campaign.id))
        
        # Only 3 messages should be created (5 - 2 excluded)
        messages = EmailMessage.objects.filter(campaign=self.campaign)
        self.assertEqual(messages.count(), 3)
        
        # Verify excluded contacts didn't get messages
        excluded_emails = [c.email for c in [self.contacts[0], self.contacts[1]]]
        message_emails = list(messages.values_list('to_email', flat=True))
        for email in excluded_emails:
            self.assertNotIn(email, message_emails)
    
    @patch('contacts.email_tasks.send_single_email.delay')
    def test_send_campaign_respects_opt_out(self, mock_send_single):
        """Test campaign respects email opt-out."""
        # Opt out some contacts
        self.contacts[0].email_opt_in = False
        self.contacts[0].save()
        self.contacts[1].status = Contact.ContactStatus.UNSUBSCRIBED
        self.contacts[1].save()
        
        result = send_campaign_emails(str(self.campaign.id))
        
        # Only 3 messages should be created
        messages = EmailMessage.objects.filter(campaign=self.campaign)
        self.assertEqual(messages.count(), 3)
    
    @patch('contacts.email_tasks.send_single_email.delay')
    def test_send_campaign_batch_processing(self, mock_send_single):
        """Test campaign processes in batches according to rate limit."""
        # Set very low rate to test batching
        self.campaign.send_rate_per_hour = 60  # 1 per minute
        self.campaign.save()
        
        with patch('time.sleep') as mock_sleep:
            result = send_campaign_emails(str(self.campaign.id))
        
        # Should have processed in batches
        self.assertEqual(result['batch_size'], 1)
        # Sleep should be called between batches
        self.assertTrue(mock_sleep.called)
    
    def test_send_campaign_paused(self):
        """Test campaign respects pause status."""
        # Start sending then pause
        self.campaign.status = EmailCampaign.CampaignStatus.PAUSED
        self.campaign.save()
        
        result = send_campaign_emails(str(self.campaign.id))
        
        self.assertEqual(result['status'], 'paused')
    
    def test_send_campaign_cancelled(self):
        """Test campaign respects cancel status."""
        self.campaign.status = EmailCampaign.CampaignStatus.CANCELLED
        self.campaign.save()
        
        result = send_campaign_emails(str(self.campaign.id))
        
        self.assertEqual(result['status'], 'cancelled')
    
    @patch('contacts.email_tasks.send_single_email.delay')
    def test_send_campaign_updates_started_at(self, mock_send_single):
        """Test campaign updates started_at timestamp."""
        self.campaign.status = EmailCampaign.CampaignStatus.SCHEDULED
        self.campaign.started_at = None
        self.campaign.save()
        
        result = send_campaign_emails(str(self.campaign.id))
        
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, EmailCampaign.CampaignStatus.SENDING)
        self.assertIsNotNone(self.campaign.started_at)
    
    def test_send_campaign_retry_on_error(self):
        """Test campaign retries on error."""
        with patch('contacts.models.EmailCampaign.objects.get') as mock_get:
            mock_get.side_effect = Exception("Database error")
            
            task = send_campaign_emails
            task.retry = Mock(side_effect=Retry)
            
            with self.assertRaises(Retry):
                task(str(self.campaign.id))


class SendSingleEmailTaskTests(TestCase):
    """Test cases for send_single_email task."""
    
    def setUp(self):
        """Set up test data."""
        self.group = GroupFactory()
        self.campaign = EmailCampaignFactory(group=self.group)
        self.contact = ContactFactory(
            group=self.group,
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com"
        )
        self.message = EmailMessageFactory(
            campaign=self.campaign,
            contact=self.contact,
            group=self.group,
            status=EmailMessage.MessageStatus.PENDING
        )
    
    @patch('contacts.email_utils.get_email_backend')
    def test_send_single_email_success(self, mock_get_backend):
        """Test successful email send."""
        # Mock email backend
        mock_backend = Mock()
        mock_get_backend.return_value = mock_backend
        mock_backend.send_messages.return_value = 1
        
        result = send_single_email(str(self.message.id))
        
        self.assertEqual(result['status'], 'sent')
        self.assertEqual(result['message_id'], str(self.message.id))
        
        # Verify message status updated
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, EmailMessage.MessageStatus.SENT)
        self.assertIsNotNone(self.message.sent_at)
        
        # Verify email was sent
        mock_backend.send_messages.assert_called_once()
        
        # Verify email event created
        event = EmailEvent.objects.filter(
            message=self.message,
            event_type=EmailEvent.EventType.SENT
        ).first()
        self.assertIsNotNone(event)
    
    @patch('contacts.email_utils.render_email_template')
    def test_send_single_email_personalization(self, mock_render):
        """Test email personalization."""
        mock_render.side_effect = lambda template, context: template.replace(
            '{{ first_name }}',
            context.get('first_name', '')
        )
        
        with patch('contacts.email_utils.get_email_backend') as mock_backend:
            mock_backend.return_value.send_messages.return_value = 1
            
            result = send_single_email(str(self.message.id))
        
        # Verify personalization context
        calls = mock_render.call_args_list
        context = calls[0][0][1]  # First call, second argument
        self.assertEqual(context['first_name'], 'John')
        self.assertEqual(context['last_name'], 'Doe')
        self.assertEqual(context['email'], 'john.doe@example.com')
    
    @patch('contacts.email_utils.get_email_backend')
    def test_send_single_email_with_tracking(self, mock_get_backend):
        """Test email with tracking enabled."""
        mock_backend = Mock()
        mock_get_backend.return_value = mock_backend
        mock_backend.send_messages.return_value = 1
        
        # Enable tracking
        self.campaign.track_opens = True
        self.campaign.track_clicks = True
        self.campaign.save()
        
        with patch('contacts.email_utils.generate_tracking_pixel') as mock_pixel:
            with patch('contacts.email_utils.track_email_links') as mock_links:
                mock_pixel.return_value = '<img src="track.gif">'
                mock_links.return_value = 'tracked content'
                
                result = send_single_email(str(self.message.id))
        
        # Verify tracking functions were called
        mock_pixel.assert_called_once()
        mock_links.assert_called_once()
    
    def test_send_single_email_already_sent(self):
        """Test sending already sent email."""
        self.message.status = EmailMessage.MessageStatus.SENT
        self.message.save()
        
        result = send_single_email(str(self.message.id))
        
        self.assertEqual(result['status'], 'skipped')
        self.assertIn('already sent', result['reason'])
    
    @patch('contacts.email_utils.get_email_backend')
    def test_send_single_email_failure(self, mock_get_backend):
        """Test email send failure."""
        mock_backend = Mock()
        mock_get_backend.return_value = mock_backend
        mock_backend.send_messages.side_effect = Exception("SMTP error")
        
        result = send_single_email(str(self.message.id))
        
        self.assertEqual(result['status'], 'failed')
        self.assertIn('SMTP error', result['error'])
        
        # Verify message marked as failed
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, EmailMessage.MessageStatus.FAILED)
        self.assertIn('SMTP error', self.message.failed_reason)
        
        # Verify failure event created
        event = EmailEvent.objects.filter(
            message=self.message,
            event_type=EmailEvent.EventType.FAILED
        ).first()
        self.assertIsNotNone(event)
    
    def test_send_single_email_retry_on_temporary_failure(self):
        """Test email retries on temporary failure."""
        with patch('contacts.email_utils.get_email_backend') as mock_backend:
            mock_backend.side_effect = ConnectionError("Network error")
            
            task = send_single_email
            task.retry = Mock(side_effect=Retry)
            
            with self.assertRaises(Retry):
                task(str(self.message.id))
            
            # Should not be marked as failed yet
            self.message.refresh_from_db()
            self.assertNotEqual(self.message.status, EmailMessage.MessageStatus.FAILED)
    
    @patch('contacts.email_utils.get_email_backend')
    def test_send_single_email_updates_campaign_stats(self, mock_get_backend):
        """Test sending updates campaign statistics."""
        mock_backend = Mock()
        mock_get_backend.return_value = mock_backend
        mock_backend.send_messages.return_value = 1
        
        # Set initial stats
        self.campaign.emails_sent = 10
        self.campaign.save()
        
        result = send_single_email(str(self.message.id))
        
        # Verify campaign stats updated
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.emails_sent, 11)
    
    @patch('contacts.email_utils.get_email_backend')
    def test_send_single_email_creates_activity(self, mock_get_backend):
        """Test sending creates contact activity."""
        mock_backend = Mock()
        mock_get_backend.return_value = mock_backend
        mock_backend.send_messages.return_value = 1
        
        result = send_single_email(str(self.message.id))
        
        # Verify activity created
        activity = ContactActivity.objects.filter(
            contact=self.contact,
            activity_type=ActivityType.EMAIL_SENT
        ).first()
        self.assertIsNotNone(activity)
        self.assertEqual(activity.subject, self.message.subject)


class SendTestEmailTaskTests(TestCase):
    """Test cases for send_test_email task."""
    
    def setUp(self):
        """Set up test data."""
        self.group = GroupFactory()
        self.user = UserFactory()
        self.template = EmailTemplateFactory(group=self.group)
    
    @patch('django.core.mail.send_mail')
    def test_send_test_email_success(self, mock_send_mail):
        """Test sending test email."""
        mock_send_mail.return_value = 1
        
        result = send_test_email(
            template_id=str(self.template.id),
            recipient_email='test@example.com',
            test_data={'first_name': 'Test'},
            sender_id=str(self.user.id)
        )
        
        self.assertEqual(result['status'], 'sent')
        self.assertEqual(result['recipient'], 'test@example.com')
        
        # Verify email was sent
        mock_send_mail.assert_called_once()
        call_args = mock_send_mail.call_args
        self.assertIn('Test Subject - Test', call_args[0][0])  # Subject
        self.assertEqual(call_args[0][3], ['test@example.com'])  # Recipient
    
    @patch('django.core.mail.EmailMultiAlternatives')
    def test_send_test_email_with_html(self, mock_email_class):
        """Test sending test email with HTML content."""
        mock_email = Mock()
        mock_email_class.return_value = mock_email
        
        result = send_test_email(
            template_id=str(self.template.id),
            recipient_email='test@example.com',
            test_data={'first_name': 'Test', 'unsubscribe_url': '#'},
            sender_id=str(self.user.id)
        )
        
        # Verify HTML alternative was attached
        mock_email.attach_alternative.assert_called()
        html_content = mock_email.attach_alternative.call_args[0][0]
        self.assertIn('Hello Test!', html_content)
    
    def test_send_test_email_template_not_found(self):
        """Test sending test email with invalid template."""
        result = send_test_email(
            template_id='invalid-id',
            recipient_email='test@example.com',
            test_data={},
            sender_id=str(self.user.id)
        )
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('Template not found', result['error'])
    
    @patch('django.core.mail.send_mail')
    def test_send_test_email_with_default_data(self, mock_send_mail):
        """Test test email uses default preview data."""
        mock_send_mail.return_value = 1
        
        result = send_test_email(
            template_id=str(self.template.id),
            recipient_email='test@example.com',
            test_data={},  # Empty test data
            sender_id=str(self.user.id)
        )
        
        # Should use template's default preview data
        call_args = mock_send_mail.call_args
        self.assertIn('Test Subject - John', call_args[0][0])  # Default first_name
    
    @patch('django.core.mail.send_mail')
    def test_send_test_email_notification(self, mock_send_mail):
        """Test notification created after test email."""
        mock_send_mail.return_value = 1
        
        result = send_test_email(
            template_id=str(self.template.id),
            recipient_email='test@example.com',
            test_data={},
            sender_id=str(self.user.id)
        )
        
        # Verify notification created
        notification = Notification.objects.filter(
            user=self.user,
            notification_type='email_test'
        ).first()
        self.assertIsNotNone(notification)
        self.assertIn('test@example.com', notification.message)


class ProcessEmailEventTaskTests(TestCase):
    """Test cases for process_email_event task."""
    
    def setUp(self):
        """Set up test data."""
        self.group = GroupFactory()
        self.campaign = EmailCampaignFactory(group=self.group)
        self.contact = ContactFactory(group=self.group)
        self.message = EmailMessageFactory(
            campaign=self.campaign,
            contact=self.contact,
            group=self.group,
            message_id='test-message-id-123'
        )
    
    def test_process_delivered_event(self):
        """Test processing delivered event."""
        event_data = {
            'event': 'delivered',
            'email': self.contact.email,
            'timestamp': timezone.now().timestamp(),
            'sg_message_id': 'test-message-id-123'
        }
        
        result = process_email_event(event_data)
        
        self.assertEqual(result['status'], 'processed')
        self.assertEqual(result['event_type'], 'delivered')
        
        # Verify message status updated
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, EmailMessage.MessageStatus.DELIVERED)
        self.assertIsNotNone(self.message.delivered_at)
        
        # Verify event created
        event = EmailEvent.objects.filter(
            message=self.message,
            event_type=EmailEvent.EventType.DELIVERED
        ).first()
        self.assertIsNotNone(event)
        
        # Verify campaign stats updated
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.emails_delivered, 1)
    
    def test_process_open_event(self):
        """Test processing open event."""
        # Mark as delivered first
        self.message.status = EmailMessage.MessageStatus.DELIVERED
        self.message.save()
        
        event_data = {
            'event': 'open',
            'email': self.contact.email,
            'timestamp': timezone.now().timestamp(),
            'sg_message_id': 'test-message-id-123',
            'ip': '192.168.1.1',
            'useragent': 'Mozilla/5.0'
        }
        
        result = process_email_event(event_data)
        
        # Verify message open tracking
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, EmailMessage.MessageStatus.OPENED)
        self.assertIsNotNone(self.message.first_opened_at)
        self.assertEqual(self.message.open_count, 1)
        
        # Verify campaign stats
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.emails_opened, 1)
        
        # Verify contact activity
        activity = ContactActivity.objects.filter(
            contact=self.contact,
            activity_type=ActivityType.EMAIL_OPENED
        ).first()
        self.assertIsNotNone(activity)
    
    def test_process_click_event(self):
        """Test processing click event."""
        # Mark as opened first
        self.message.status = EmailMessage.MessageStatus.OPENED
        self.message.open_count = 1
        self.message.save()
        
        event_data = {
            'event': 'click',
            'email': self.contact.email,
            'timestamp': timezone.now().timestamp(),
            'sg_message_id': 'test-message-id-123',
            'url': 'https://example.com/product',
            'url_offset': {'index': 0, 'type': 'html'}
        }
        
        result = process_email_event(event_data)
        
        # Verify click tracking
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, EmailMessage.MessageStatus.CLICKED)
        self.assertIsNotNone(self.message.first_clicked_at)
        self.assertEqual(self.message.click_count, 1)
        
        # Verify event includes URL
        event = EmailEvent.objects.filter(
            message=self.message,
            event_type=EmailEvent.EventType.CLICKED
        ).first()
        self.assertEqual(event.link_url, 'https://example.com/product')
    
    def test_process_bounce_event(self):
        """Test processing bounce event."""
        event_data = {
            'event': 'bounce',
            'email': self.contact.email,
            'timestamp': timezone.now().timestamp(),
            'sg_message_id': 'test-message-id-123',
            'type': 'blocked',
            'reason': 'Invalid email address'
        }
        
        result = process_email_event(event_data)
        
        # Verify bounce tracking
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, EmailMessage.MessageStatus.BOUNCED)
        self.assertEqual(self.message.bounce_type, 'blocked')
        self.assertEqual(self.message.bounce_reason, 'Invalid email address')
        
        # Verify campaign stats
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.emails_bounced, 1)
    
    def test_process_unsubscribe_event(self):
        """Test processing unsubscribe event."""
        event_data = {
            'event': 'unsubscribe',
            'email': self.contact.email,
            'timestamp': timezone.now().timestamp(),
            'sg_message_id': 'test-message-id-123'
        }
        
        result = process_email_event(event_data)
        
        # Verify unsubscribe tracking
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, EmailMessage.MessageStatus.UNSUBSCRIBED)
        
        # Verify contact opted out
        self.contact.refresh_from_db()
        self.assertFalse(self.contact.email_opt_in)
        self.assertEqual(self.contact.status, Contact.ContactStatus.UNSUBSCRIBED)
        
        # Verify campaign stats
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.emails_unsubscribed, 1)
    
    def test_process_spam_complaint_event(self):
        """Test processing spam complaint event."""
        event_data = {
            'event': 'spamreport',
            'email': self.contact.email,
            'timestamp': timezone.now().timestamp(),
            'sg_message_id': 'test-message-id-123'
        }
        
        result = process_email_event(event_data)
        
        # Verify complaint tracking
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, EmailMessage.MessageStatus.COMPLAINED)
        
        # Verify contact opted out
        self.contact.refresh_from_db()
        self.assertFalse(self.contact.email_opt_in)
    
    def test_process_event_message_not_found(self):
        """Test processing event for unknown message."""
        event_data = {
            'event': 'delivered',
            'email': 'unknown@example.com',
            'timestamp': timezone.now().timestamp(),
            'sg_message_id': 'unknown-message-id'
        }
        
        result = process_email_event(event_data)
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('Message not found', result['error'])
    
    def test_process_multiple_open_events(self):
        """Test processing multiple open events."""
        # First open
        self.message.status = EmailMessage.MessageStatus.DELIVERED
        self.message.save()
        
        event_data = {
            'event': 'open',
            'email': self.contact.email,
            'timestamp': timezone.now().timestamp(),
            'sg_message_id': 'test-message-id-123'
        }
        
        process_email_event(event_data)
        
        # Second open
        event_data['timestamp'] = (timezone.now() + timedelta(hours=1)).timestamp()
        process_email_event(event_data)
        
        # Verify open count incremented
        self.message.refresh_from_db()
        self.assertEqual(self.message.open_count, 2)
        self.assertIsNotNone(self.message.last_opened_at)
        
        # Campaign stats should still show 1 unique open
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.emails_opened, 1)


class ScheduleCampaignTaskTests(TestCase):
    """Test cases for schedule_campaign task."""
    
    def setUp(self):
        """Set up test data."""
        self.group = GroupFactory()
        self.campaign = EmailCampaignFactory(
            group=self.group,
            status=EmailCampaign.CampaignStatus.SCHEDULED,
            scheduled_at=timezone.now() + timedelta(hours=1)
        )
    
    @patch('contacts.email_tasks.send_campaign_emails.delay')
    def test_schedule_campaign(self, mock_send):
        """Test scheduling a campaign."""
        result = schedule_campaign(str(self.campaign.id))
        
        self.assertEqual(result['status'], 'scheduled')
        
        # Should trigger send task
        mock_send.assert_called_once_with(str(self.campaign.id))
    
    def test_schedule_campaign_not_found(self):
        """Test scheduling non-existent campaign."""
        result = schedule_campaign('invalid-id')
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('not found', result['error'])
    
    def test_schedule_campaign_wrong_status(self):
        """Test scheduling campaign with wrong status."""
        self.campaign.status = EmailCampaign.CampaignStatus.SENT
        self.campaign.save()
        
        result = schedule_campaign(str(self.campaign.id))
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('not in scheduled status', result['error'])


class CheckCampaignCompletionTaskTests(TestCase):
    """Test cases for check_campaign_completion task."""
    
    def setUp(self):
        """Set up test data."""
        self.group = GroupFactory()
        self.user = UserFactory()
        self.campaign = EmailCampaignFactory(
            group=self.group,
            status=EmailCampaign.CampaignStatus.SENDING,
            created_by=self.user,
            total_recipients=5
        )
        
        # Create messages
        for i in range(5):
            EmailMessageFactory(
                campaign=self.campaign,
                group=self.group,
                status=EmailMessage.MessageStatus.SENT if i < 3 else EmailMessage.MessageStatus.PENDING
            )
    
    def test_check_incomplete_campaign(self):
        """Test checking incomplete campaign."""
        result = check_campaign_completion(str(self.campaign.id))
        
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['pending_count'], 2)
        
        # Campaign should still be sending
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, EmailCampaign.CampaignStatus.SENDING)
    
    @patch('contacts.email_tasks.send_campaign_report.delay')
    def test_check_complete_campaign(self, mock_report):
        """Test checking complete campaign."""
        # Mark all messages as sent
        EmailMessage.objects.filter(campaign=self.campaign).update(
            status=EmailMessage.MessageStatus.SENT
        )
        
        result = check_campaign_completion(str(self.campaign.id))
        
        self.assertEqual(result['status'], 'completed')
        
        # Campaign should be marked as sent
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, EmailCampaign.CampaignStatus.SENT)
        self.assertIsNotNone(self.campaign.completed_at)
        
        # Report should be scheduled
        mock_report.assert_called_once_with(str(self.campaign.id))
    
    def test_check_campaign_with_failures(self):
        """Test checking campaign with failed messages."""
        # Mark some as failed
        messages = EmailMessage.objects.filter(campaign=self.campaign)
        messages.filter(status=EmailMessage.MessageStatus.PENDING).update(
            status=EmailMessage.MessageStatus.FAILED
        )
        
        result = check_campaign_completion(str(self.campaign.id))
        
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['failed_count'], 2)


class SendCampaignReportTaskTests(TestCase):
    """Test cases for send_campaign_report task."""
    
    def setUp(self):
        """Set up test data."""
        self.group = GroupFactory()
        self.user = UserFactory(email='creator@example.com')
        self.campaign = EmailCampaignFactory(
            group=self.group,
            status=EmailCampaign.CampaignStatus.SENT,
            created_by=self.user,
            emails_sent=100,
            emails_delivered=95,
            emails_opened=30,
            emails_clicked=10,
            emails_bounced=5
        )
    
    @patch('django.core.mail.send_mail')
    def test_send_campaign_report(self, mock_send_mail):
        """Test sending campaign completion report."""
        mock_send_mail.return_value = 1
        
        result = send_campaign_report(str(self.campaign.id))
        
        self.assertEqual(result['status'], 'sent')
        
        # Verify email sent
        mock_send_mail.assert_called_once()
        call_args = mock_send_mail.call_args
        
        # Check recipient
        self.assertEqual(call_args[0][3], ['creator@example.com'])
        
        # Check content includes stats
        message = call_args[0][1]
        self.assertIn('100', message)  # Sent count
        self.assertIn('31.58%', message)  # Open rate
        self.assertIn('10.53%', message)  # Click rate
    
    def test_send_campaign_report_notification(self):
        """Test notification created with report."""
        with patch('django.core.mail.send_mail') as mock_send:
            mock_send.return_value = 1
            
            result = send_campaign_report(str(self.campaign.id))
        
        # Verify notification created
        notification = Notification.objects.filter(
            user=self.user,
            notification_type='campaign_complete'
        ).first()
        self.assertIsNotNone(notification)
        self.assertIn(self.campaign.name, notification.title)


class HelperFunctionTests(TestCase):
    """Test cases for helper functions."""
    
    def setUp(self):
        """Set up test data."""
        self.group = GroupFactory()
        self.campaign = EmailCampaignFactory(group=self.group)
        self.contact_list = ContactListFactory(group=self.group)
        self.campaign.contact_lists.add(self.contact_list)
    
    def test_get_campaign_recipients(self):
        """Test getting campaign recipients."""
        # Add contacts
        contacts = [
            ContactFactory(group=self.group, email_opt_in=True)
            for _ in range(5)
        ]
        self.contact_list.contacts.add(*contacts)
        
        # Add some exclusions
        self.campaign.excluded_contacts.add(contacts[0])
        
        # Make one opted out
        contacts[1].email_opt_in = False
        contacts[1].save()
        
        recipients = _get_campaign_recipients(self.campaign)
        
        # Should have 3 recipients (5 - 1 excluded - 1 opted out)
        self.assertEqual(len(recipients), 3)
        
        # Verify excluded and opted out not in list
        recipient_ids = [r.id for r in recipients]
        self.assertNotIn(contacts[0].id, recipient_ids)
        self.assertNotIn(contacts[1].id, recipient_ids)
    
    @patch('contacts.email_utils.render_email_template')
    def test_render_email_for_contact(self, mock_render):
        """Test rendering email for contact."""
        mock_render.side_effect = lambda template, context: template.format(**context)
        
        contact = ContactFactory(
            first_name='Jane',
            last_name='Smith',
            company_name='Acme Corp'
        )
        
        template = EmailTemplateFactory(
            subject='Hello {first_name}!',
            html_content='<p>Hi {first_name} from {company_name}</p>',
            text_content='Hi {first_name} from {company_name}'
        )
        
        result = _render_email_for_contact(template, contact, {})
        
        self.assertEqual(result['subject'], 'Hello Jane!')
        self.assertIn('Hi Jane from Acme Corp', result['html'])
        self.assertIn('Hi Jane from Acme Corp', result['text'])
    
    def test_track_email_sent(self):
        """Test tracking email sent."""
        message = EmailMessageFactory()
        campaign = message.campaign
        contact = message.contact
        
        # Set initial values
        campaign.emails_sent = 10
        campaign.save()
        
        _track_email_sent(message)
        
        # Verify campaign updated
        campaign.refresh_from_db()
        self.assertEqual(campaign.emails_sent, 11)
        
        # Verify contact activity created
        activity = ContactActivity.objects.filter(
            contact=contact,
            activity_type=ActivityType.EMAIL_SENT
        ).first()
        self.assertIsNotNone(activity)
        
        # Verify contact last email sent updated
        contact.refresh_from_db()
        self.assertIsNotNone(contact.last_email_sent_at)
    
    def test_track_email_event(self):
        """Test tracking various email events."""
        message = EmailMessageFactory()
        campaign = message.campaign
        
        # Track delivered
        _track_email_event(message, EmailEvent.EventType.DELIVERED, {})
        
        campaign.refresh_from_db()
        self.assertEqual(campaign.emails_delivered, 1)
        
        # Track opened
        _track_email_event(message, EmailEvent.EventType.OPENED, {})
        
        campaign.refresh_from_db()
        self.assertEqual(campaign.emails_opened, 1)
        
        # Track clicked
        _track_email_event(message, EmailEvent.EventType.CLICKED, {
            'url': 'https://example.com'
        })
        
        campaign.refresh_from_db()
        self.assertEqual(campaign.emails_clicked, 1)


class BatchProcessingTests(TransactionTestCase):
    """Test cases for batch processing and rate limiting."""
    
    def setUp(self):
        """Set up test data."""
        self.group = GroupFactory()
        self.campaign = EmailCampaignFactory(
            group=self.group,
            send_rate_per_hour=3600  # 60 per minute
        )
        
        # Create many contacts
        self.contact_list = ContactListFactory(group=self.group)
        self.contacts = [
            ContactFactory(group=self.group)
            for _ in range(150)
        ]
        self.contact_list.contacts.add(*self.contacts)
        self.campaign.contact_lists.add(self.contact_list)
    
    @patch('contacts.email_tasks.send_single_email.delay')
    def test_batch_processing_respects_rate_limit(self, mock_send):
        """Test batch processing respects rate limits."""
        with patch('time.sleep') as mock_sleep:
            result = process_campaign_batch(
                str(self.campaign.id),
                offset=0,
                limit=150
            )
        
        # Should process in batches of 60 (rate per minute)
        self.assertEqual(result['batch_size'], 60)
        self.assertEqual(result['processed'], 150)
        
        # Should have slept between batches
        expected_sleeps = 150 // 60  # 2 full batches
        self.assertEqual(mock_sleep.call_count, expected_sleeps)
    
    @patch('contacts.email_tasks.send_single_email.delay')
    def test_batch_processing_handles_errors(self, mock_send):
        """Test batch processing continues on individual errors."""
        # Make some sends fail
        mock_send.side_effect = [
            None,  # Success
            Exception("Send failed"),  # Failure
            None,  # Success
        ] * 50
        
        result = process_campaign_batch(
            str(self.campaign.id),
            offset=0,
            limit=150
        )
        
        # Should still process all messages
        self.assertEqual(result['processed'], 150)
        self.assertGreater(result['failed'], 0)


class RetryLogicTests(TestCase):
    """Test cases for retry logic and error handling."""
    
    def setUp(self):
        """Set up test data."""
        self.message = EmailMessageFactory()
    
    def test_temporary_failure_retry(self):
        """Test temporary failures trigger retry."""
        task = send_single_email
        task.retry = Mock(side_effect=Retry)
        task.request.retries = 0
        
        with patch('contacts.email_utils.get_email_backend') as mock_backend:
            mock_backend.side_effect = ConnectionError("Network error")
            
            with self.assertRaises(Retry):
                task(str(self.message.id))
        
        # Message should not be marked as failed
        self.message.refresh_from_db()
        self.assertNotEqual(self.message.status, EmailMessage.MessageStatus.FAILED)
    
    def test_max_retries_exceeded(self):
        """Test max retries marks message as failed."""
        task = send_single_email
        task.request.retries = 3  # Max retries
        
        with patch('contacts.email_utils.get_email_backend') as mock_backend:
            mock_backend.side_effect = ConnectionError("Network error")
            
            result = task(str(self.message.id))
        
        # Should be marked as failed after max retries
        self.assertEqual(result['status'], 'failed')
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, EmailMessage.MessageStatus.FAILED)
    
    def test_permanent_failure_no_retry(self):
        """Test permanent failures don't retry."""
        task = send_single_email
        
        with patch('contacts.email_utils.get_email_backend') as mock_backend:
            mock_backend.side_effect = ValueError("Invalid email format")
            
            result = task(str(self.message.id))
        
        # Should fail immediately without retry
        self.assertEqual(result['status'], 'failed')
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, EmailMessage.MessageStatus.FAILED)