"""
Tests for email campaign serializers.

Comprehensive test coverage for email template, campaign, message,
and event serializers including validation and nested relationships.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, Mock

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.template import Template, Context, TemplateDoesNotExist
from rest_framework.test import APIRequestFactory
from rest_framework.exceptions import ValidationError
import factory

from accounts.models import Group, GroupMembership, Role
from contacts.models import (
    Contact, ContactList, EmailTemplate, EmailCampaign,
    EmailMessage, EmailEvent
)
from contacts.email_serializers import (
    EmailTemplateSerializer, EmailTemplateListSerializer,
    EmailCampaignSerializer, EmailCampaignListSerializer,
    EmailMessageSerializer, EmailEventSerializer,
    CampaignStatsSerializer, SendTestEmailSerializer
)

User = get_user_model()


# Re-use factories from test_email_views
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


class EmailEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailEvent
    
    message = factory.SubFactory(EmailMessageFactory)
    event_type = EmailEvent.EventType.SENT
    timestamp = factory.LazyFunction(timezone.now)


class EmailTemplateSerializerTests(TestCase):
    """Test cases for EmailTemplate serializers."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = APIRequestFactory()
        self.group = GroupFactory()
        self.user = UserFactory()
        GroupMembership.objects.create(user=self.user, group=self.group)
        
        self.template = EmailTemplateFactory(group=self.group, created_by=self.user)
    
    def test_template_serialization(self):
        """Test basic template serialization."""
        serializer = EmailTemplateSerializer(self.template)
        data = serializer.data
        
        self.assertEqual(data['name'], self.template.name)
        self.assertEqual(data['template_type'], self.template.template_type)
        self.assertEqual(data['subject'], self.template.subject)
        self.assertEqual(data['html_content'], self.template.html_content)
        self.assertEqual(data['text_content'], self.template.text_content)
        self.assertIn('preview_html', data)
        self.assertIn('preview_text', data)
        self.assertIn('preview_subject', data)
    
    def test_template_preview_rendering(self):
        """Test template preview with sample data."""
        serializer = EmailTemplateSerializer(self.template)
        data = serializer.data
        
        # Check preview contains rendered content
        self.assertIn('Hello John!', data['preview_html'])
        self.assertIn('Hello John!', data['preview_text'])
        self.assertIn('Test Subject - John', data['preview_subject'])
    
    def test_template_preview_with_custom_context(self):
        """Test template preview with custom context data."""
        context = {
            'preview_data': {
                'first_name': 'Jane',
                'last_name': 'Smith',
                'unsubscribe_url': 'https://example.com/unsub'
            }
        }
        serializer = EmailTemplateSerializer(self.template, context=context)
        data = serializer.data
        
        self.assertIn('Hello Jane!', data['preview_html'])
        self.assertIn('Test Subject - Jane', data['preview_subject'])
    
    def test_template_preview_with_error(self):
        """Test template preview handles template errors gracefully."""
        self.template.html_content = "{{ invalid_syntax"
        self.template.save()
        
        serializer = EmailTemplateSerializer(self.template)
        data = serializer.data
        
        self.assertIn('Template error:', data['preview_html'])
    
    def test_subject_validation(self):
        """Test subject line length validation."""
        data = {
            'name': 'Test Template',
            'template_type': EmailTemplate.TemplateType.MARKETING,
            'subject': 'x' * 151,  # Too long
            'html_content': '<p>Test {{ unsubscribe_url }}</p>',
            'text_content': 'Test {{ unsubscribe_url }}'
        }
        
        serializer = EmailTemplateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('subject', serializer.errors)
        self.assertIn('less than 150 characters', str(serializer.errors['subject']))
    
    def test_html_content_validation_empty(self):
        """Test HTML content cannot be empty."""
        data = {
            'name': 'Test Template',
            'template_type': EmailTemplate.TemplateType.MARKETING,
            'subject': 'Test Subject',
            'html_content': '   ',  # Just whitespace
            'text_content': 'Test {{ unsubscribe_url }}'
        }
        
        serializer = EmailTemplateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('html_content', serializer.errors)
        self.assertIn('cannot be empty', str(serializer.errors['html_content']))
    
    def test_html_content_validation_missing_unsubscribe(self):
        """Test HTML content must include unsubscribe link."""
        data = {
            'name': 'Test Template',
            'template_type': EmailTemplate.TemplateType.MARKETING,
            'subject': 'Test Subject',
            'html_content': '<p>No unsubscribe link here!</p>',
            'text_content': 'No unsubscribe link here!'
        }
        
        serializer = EmailTemplateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('html_content', serializer.errors)
        self.assertIn('must include {{ unsubscribe_url }}', str(serializer.errors['html_content']))
    
    def test_text_content_validation(self):
        """Test text content validation."""
        data = {
            'name': 'Test Template',
            'template_type': EmailTemplate.TemplateType.MARKETING,
            'subject': 'Test Subject',
            'html_content': '<p>Test {{ unsubscribe_url }}</p>',
            'text_content': 'No unsubscribe link here!'
        }
        
        serializer = EmailTemplateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('text_content', serializer.errors)
        self.assertIn('must include {{ unsubscribe_url }}', str(serializer.errors['text_content']))
    
    def test_from_email_validation(self):
        """Test from email validation."""
        data = {
            'name': 'Test Template',
            'template_type': EmailTemplate.TemplateType.MARKETING,
            'subject': 'Test Subject',
            'html_content': '<p>Test {{ unsubscribe_url }}</p>',
            'text_content': 'Test {{ unsubscribe_url }}',
            'from_email': 'invalid-email'
        }
        
        serializer = EmailTemplateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('from_email', serializer.errors)
    
    def test_valid_template_creation(self):
        """Test creating a valid template."""
        data = {
            'name': 'Valid Template',
            'template_type': EmailTemplate.TemplateType.NEWSLETTER,
            'subject': 'Monthly Newsletter - {{ current_month }}',
            'preheader': 'Your monthly update',
            'html_content': '''
                <html>
                <body>
                    <h1>Hello {{ first_name }}!</h1>
                    <p>Welcome to our newsletter.</p>
                    <a href="{{ unsubscribe_url }}">Unsubscribe</a>
                </body>
                </html>
            ''',
            'text_content': '''
                Hello {{ first_name }}!
                Welcome to our newsletter.
                Unsubscribe: {{ unsubscribe_url }}
            ''',
            'from_name': 'Newsletter Team',
            'from_email': 'newsletter@company.com',
            'reply_to_email': 'support@company.com'
        }
        
        request = self.factory.post('/api/templates/')
        request.user = self.user
        
        serializer = EmailTemplateSerializer(data=data, context={'request': request})
        self.assertTrue(serializer.is_valid())
        
        template = serializer.save(group=self.group, created_by=self.user)
        self.assertEqual(template.name, 'Valid Template')
        self.assertEqual(template.template_type, EmailTemplate.TemplateType.NEWSLETTER)
        self.assertEqual(template.group, self.group)
        self.assertEqual(template.created_by, self.user)
    
    def test_list_serializer(self):
        """Test lightweight list serializer."""
        templates = [
            EmailTemplateFactory(group=self.group),
            EmailTemplateFactory(group=self.group)
        ]
        
        serializer = EmailTemplateListSerializer(templates, many=True)
        data = serializer.data
        
        self.assertEqual(len(data), 2)
        
        # List serializer should have fewer fields
        self.assertIn('id', data[0])
        self.assertIn('name', data[0])
        self.assertIn('template_type', data[0])
        self.assertNotIn('html_content', data[0])  # Heavy fields excluded
        self.assertNotIn('text_content', data[0])


class EmailCampaignSerializerTests(TestCase):
    """Test cases for EmailCampaign serializers."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = APIRequestFactory()
        self.group = GroupFactory()
        self.user = UserFactory()
        GroupMembership.objects.create(user=self.user, group=self.group)
        
        self.template = EmailTemplateFactory(group=self.group)
        self.contact_list = ContactListFactory(group=self.group, created_by=self.user)
        self.campaign = EmailCampaignFactory(
            group=self.group,
            template=self.template,
            created_by=self.user
        )
        self.campaign.contact_lists.add(self.contact_list)
    
    def test_campaign_serialization(self):
        """Test basic campaign serialization."""
        serializer = EmailCampaignSerializer(self.campaign)
        data = serializer.data
        
        self.assertEqual(data['name'], self.campaign.name)
        self.assertEqual(data['status'], self.campaign.status)
        self.assertEqual(data['template']['id'], str(self.template.id))
        self.assertEqual(len(data['contact_lists']), 1)
        self.assertEqual(data['open_rate'], 0)
        self.assertEqual(data['click_rate'], 0)
    
    def test_campaign_with_metrics(self):
        """Test campaign serialization with engagement metrics."""
        self.campaign.emails_sent = 100
        self.campaign.emails_delivered = 95
        self.campaign.emails_opened = 30
        self.campaign.emails_clicked = 10
        self.campaign.save()
        
        serializer = EmailCampaignSerializer(self.campaign)
        data = serializer.data
        
        self.assertEqual(data['open_rate'], 31.58)  # 30/95 * 100
        self.assertEqual(data['click_rate'], 10.53)  # 10/95 * 100
    
    def test_campaign_creation(self):
        """Test creating a campaign through serializer."""
        data = {
            'name': 'New Campaign',
            'description': 'Test campaign description',
            'template': str(self.template.id),
            'sending_strategy': EmailCampaign.SendingStrategy.SCHEDULED,
            'scheduled_at': (timezone.now() + timedelta(hours=2)).isoformat(),
            'contact_lists': [str(self.contact_list.id)],
            'track_opens': True,
            'track_clicks': True,
            'send_rate_per_hour': 500
        }
        
        request = self.factory.post('/api/campaigns/')
        request.user = self.user
        
        serializer = EmailCampaignSerializer(data=data, context={'request': request})
        self.assertTrue(serializer.is_valid())
        
        campaign = serializer.save(group=self.group, created_by=self.user)
        self.assertEqual(campaign.name, 'New Campaign')
        self.assertEqual(campaign.sending_strategy, EmailCampaign.SendingStrategy.SCHEDULED)
        self.assertIsNotNone(campaign.scheduled_at)
        self.assertEqual(campaign.contact_lists.count(), 1)
    
    def test_scheduled_campaign_validation(self):
        """Test scheduled campaign must have scheduled_at."""
        data = {
            'name': 'Scheduled Campaign',
            'template': str(self.template.id),
            'sending_strategy': EmailCampaign.SendingStrategy.SCHEDULED,
            # Missing scheduled_at
        }
        
        serializer = EmailCampaignSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('scheduled_at', serializer.errors)
    
    def test_scheduled_at_in_past_validation(self):
        """Test scheduled_at cannot be in the past."""
        data = {
            'name': 'Past Campaign',
            'template': str(self.template.id),
            'sending_strategy': EmailCampaign.SendingStrategy.SCHEDULED,
            'scheduled_at': (timezone.now() - timedelta(hours=1)).isoformat()
        }
        
        serializer = EmailCampaignSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('scheduled_at', serializer.errors)
        self.assertIn('cannot be in the past', str(serializer.errors['scheduled_at']))
    
    def test_ab_test_validation(self):
        """Test A/B test campaign validation."""
        variant1 = EmailTemplateFactory(group=self.group)
        variant2 = EmailTemplateFactory(group=self.group)
        
        data = {
            'name': 'A/B Test Campaign',
            'template': str(self.template.id),
            'is_ab_test': True,
            'ab_test_percentage': 150,  # Invalid percentage
            'variant_templates': [str(variant1.id), str(variant2.id)]
        }
        
        serializer = EmailCampaignSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('ab_test_percentage', serializer.errors)
    
    def test_ab_test_requires_variants(self):
        """Test A/B test campaign requires variant templates."""
        data = {
            'name': 'A/B Test Campaign',
            'template': str(self.template.id),
            'is_ab_test': True,
            'ab_test_percentage': 20,
            'variant_templates': []  # No variants
        }
        
        serializer = EmailCampaignSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('variant_templates', serializer.errors)
        self.assertIn('at least one variant', str(serializer.errors['variant_templates']))
    
    def test_campaign_update(self):
        """Test updating a campaign."""
        data = {
            'name': 'Updated Campaign Name',
            'description': 'Updated description'
        }
        
        serializer = EmailCampaignSerializer(
            self.campaign,
            data=data,
            partial=True
        )
        self.assertTrue(serializer.is_valid())
        
        campaign = serializer.save()
        self.assertEqual(campaign.name, 'Updated Campaign Name')
        self.assertEqual(campaign.description, 'Updated description')
    
    def test_list_serializer(self):
        """Test lightweight list serializer."""
        campaigns = [
            EmailCampaignFactory(group=self.group),
            EmailCampaignFactory(group=self.group)
        ]
        
        serializer = EmailCampaignListSerializer(campaigns, many=True)
        data = serializer.data
        
        self.assertEqual(len(data), 2)
        
        # List serializer should have summary fields
        self.assertIn('id', data[0])
        self.assertIn('name', data[0])
        self.assertIn('status', data[0])
        self.assertIn('emails_sent', data[0])
        self.assertNotIn('contact_lists', data[0])  # Detailed fields excluded
    
    def test_recipient_count_calculation(self):
        """Test recipient count calculation."""
        # Add contacts to list
        contacts = [ContactFactory(group=self.group) for _ in range(10)]
        self.contact_list.contacts.add(*contacts)
        
        serializer = EmailCampaignSerializer(self.campaign)
        data = serializer.data
        
        self.assertEqual(data['recipient_count'], 10)
    
    def test_excluded_contacts_handling(self):
        """Test excluded contacts in serialization."""
        # Add contacts and exclude some
        contacts = [ContactFactory(group=self.group) for _ in range(5)]
        self.contact_list.contacts.add(*contacts)
        self.campaign.excluded_contacts.add(contacts[0], contacts[1])
        
        serializer = EmailCampaignSerializer(self.campaign)
        data = serializer.data
        
        self.assertEqual(data['recipient_count'], 3)  # 5 - 2 excluded


class EmailMessageSerializerTests(TestCase):
    """Test cases for EmailMessage serializer."""
    
    def setUp(self):
        """Set up test data."""
        self.group = GroupFactory()
        self.campaign = EmailCampaignFactory(group=self.group)
        self.contact = ContactFactory(group=self.group)
        self.message = EmailMessageFactory(
            campaign=self.campaign,
            contact=self.contact,
            group=self.group
        )
    
    def test_message_serialization(self):
        """Test basic message serialization."""
        serializer = EmailMessageSerializer(self.message)
        data = serializer.data
        
        self.assertEqual(data['campaign'], str(self.campaign.id))
        self.assertEqual(data['contact']['id'], str(self.contact.id))
        self.assertEqual(data['status'], self.message.status)
        self.assertEqual(data['subject'], self.message.subject)
        self.assertEqual(data['to_email'], self.message.to_email)
    
    def test_message_with_events(self):
        """Test message serialization includes events."""
        # Create events
        events = [
            EmailEventFactory(message=self.message, event_type=EmailEvent.EventType.SENT),
            EmailEventFactory(message=self.message, event_type=EmailEvent.EventType.DELIVERED),
            EmailEventFactory(message=self.message, event_type=EmailEvent.EventType.OPENED)
        ]
        
        serializer = EmailMessageSerializer(self.message)
        data = serializer.data
        
        self.assertEqual(len(data['events']), 3)
        # Events should be in reverse chronological order
        self.assertEqual(data['events'][0]['event_type'], EmailEvent.EventType.OPENED)
    
    def test_message_engagement_metrics(self):
        """Test message engagement metrics in serialization."""
        self.message.first_opened_at = timezone.now()
        self.message.open_count = 3
        self.message.first_clicked_at = timezone.now()
        self.message.click_count = 2
        self.message.save()
        
        serializer = EmailMessageSerializer(self.message)
        data = serializer.data
        
        self.assertEqual(data['open_count'], 3)
        self.assertEqual(data['click_count'], 2)
        self.assertIsNotNone(data['first_opened_at'])
        self.assertIsNotNone(data['first_clicked_at'])
    
    def test_message_bounce_info(self):
        """Test message bounce information."""
        self.message.status = EmailMessage.MessageStatus.BOUNCED
        self.message.bounce_type = 'hard'
        self.message.bounce_reason = 'Invalid recipient'
        self.message.save()
        
        serializer = EmailMessageSerializer(self.message)
        data = serializer.data
        
        self.assertEqual(data['status'], EmailMessage.MessageStatus.BOUNCED)
        self.assertEqual(data['bounce_type'], 'hard')
        self.assertEqual(data['bounce_reason'], 'Invalid recipient')
    
    def test_contact_summary_serialization(self):
        """Test contact is serialized as summary."""
        serializer = EmailMessageSerializer(self.message)
        data = serializer.data
        
        # Contact should be summary, not full details
        self.assertIn('id', data['contact'])
        self.assertIn('email', data['contact'])
        self.assertIn('first_name', data['contact'])
        self.assertNotIn('activities', data['contact'])  # Detailed fields excluded


class EmailEventSerializerTests(TestCase):
    """Test cases for EmailEvent serializer."""
    
    def setUp(self):
        """Set up test data."""
        self.group = GroupFactory()
        self.campaign = EmailCampaignFactory(group=self.group)
        self.message = EmailMessageFactory(campaign=self.campaign, group=self.group)
        self.event = EmailEventFactory(message=self.message)
    
    def test_event_serialization(self):
        """Test basic event serialization."""
        serializer = EmailEventSerializer(self.event)
        data = serializer.data
        
        self.assertEqual(data['message'], str(self.message.id))
        self.assertEqual(data['event_type'], self.event.event_type)
        self.assertIn('timestamp', data)
        self.assertIn('campaign_name', data)
        self.assertIn('contact_email', data)
    
    def test_event_with_metadata(self):
        """Test event with additional metadata."""
        self.event.ip_address = '192.168.1.1'
        self.event.user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
        self.event.metadata = {
            'email_client': 'Gmail',
            'device': 'Desktop'
        }
        self.event.save()
        
        serializer = EmailEventSerializer(self.event)
        data = serializer.data
        
        self.assertEqual(data['ip_address'], '192.168.1.1')
        self.assertEqual(data['user_agent'], 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)')
        self.assertEqual(data['metadata']['email_client'], 'Gmail')
    
    def test_click_event_serialization(self):
        """Test click event with link information."""
        self.event.event_type = EmailEvent.EventType.CLICKED
        self.event.link_url = 'https://example.com/product'
        self.event.link_text = 'View Product'
        self.event.save()
        
        serializer = EmailEventSerializer(self.event)
        data = serializer.data
        
        self.assertEqual(data['event_type'], EmailEvent.EventType.CLICKED)
        self.assertEqual(data['link_url'], 'https://example.com/product')
        self.assertEqual(data['link_text'], 'View Product')
    
    def test_event_includes_campaign_info(self):
        """Test event includes campaign information."""
        serializer = EmailEventSerializer(self.event)
        data = serializer.data
        
        self.assertEqual(data['campaign_name'], self.campaign.name)
        self.assertEqual(data['contact_email'], self.message.to_email)


class SendTestEmailSerializerTests(TestCase):
    """Test cases for SendTestEmailSerializer."""
    
    def test_valid_test_email(self):
        """Test valid test email data."""
        data = {
            'recipient_email': 'test@example.com',
            'test_data': {
                'first_name': 'Test',
                'last_name': 'User',
                'company_name': 'Test Company'
            }
        }
        
        serializer = SendTestEmailSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['recipient_email'], 'test@example.com')
    
    def test_invalid_email(self):
        """Test invalid email validation."""
        data = {
            'recipient_email': 'not-an-email',
            'test_data': {}
        }
        
        serializer = SendTestEmailSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('recipient_email', serializer.errors)
    
    def test_missing_recipient(self):
        """Test recipient email is required."""
        data = {
            'test_data': {'first_name': 'Test'}
        }
        
        serializer = SendTestEmailSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('recipient_email', serializer.errors)
    
    def test_empty_test_data(self):
        """Test empty test data is allowed."""
        data = {
            'recipient_email': 'test@example.com'
            # No test_data
        }
        
        serializer = SendTestEmailSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data.get('test_data'), {})


class CampaignStatsSerializerTests(TestCase):
    """Test cases for CampaignStatsSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.group = GroupFactory()
        self.campaigns = [
            EmailCampaignFactory(group=self.group, status=EmailCampaign.CampaignStatus.SENT),
            EmailCampaignFactory(group=self.group, status=EmailCampaign.CampaignStatus.SENDING)
        ]
    
    def test_stats_serialization(self):
        """Test campaign statistics serialization."""
        stats_data = {
            'total_campaigns': 10,
            'active_campaigns': 2,
            'total_emails_sent': 1500,
            'average_open_rate': 25.5,
            'average_click_rate': 5.2,
            'recent_campaigns': self.campaigns
        }
        
        serializer = CampaignStatsSerializer(stats_data)
        data = serializer.data
        
        self.assertEqual(data['total_campaigns'], 10)
        self.assertEqual(data['active_campaigns'], 2)
        self.assertEqual(data['total_emails_sent'], 1500)
        self.assertEqual(data['average_open_rate'], 25.5)
        self.assertEqual(data['average_click_rate'], 5.2)
        self.assertEqual(len(data['recent_campaigns']), 2)
    
    def test_recent_campaigns_summary(self):
        """Test recent campaigns are serialized as summaries."""
        stats_data = {
            'total_campaigns': 2,
            'active_campaigns': 1,
            'total_emails_sent': 0,
            'average_open_rate': 0,
            'average_click_rate': 0,
            'recent_campaigns': self.campaigns
        }
        
        serializer = CampaignStatsSerializer(stats_data)
        data = serializer.data
        
        # Recent campaigns should use list serializer
        campaign_data = data['recent_campaigns'][0]
        self.assertIn('id', campaign_data)
        self.assertIn('name', campaign_data)
        self.assertIn('status', campaign_data)
        self.assertNotIn('contact_lists', campaign_data)  # Detailed fields excluded


class NestedSerializerTests(TestCase):
    """Test cases for nested serializer functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.group = GroupFactory()
        self.user = UserFactory()
        GroupMembership.objects.create(user=self.user, group=self.group)
    
    def test_campaign_with_nested_template(self):
        """Test campaign serializer includes nested template."""
        template = EmailTemplateFactory(group=self.group, name='Nested Template')
        campaign = EmailCampaignFactory(group=self.group, template=template)
        
        serializer = EmailCampaignSerializer(campaign)
        data = serializer.data
        
        self.assertEqual(data['template']['name'], 'Nested Template')
        self.assertIn('template_type', data['template'])
    
    def test_campaign_with_nested_lists(self):
        """Test campaign serializer includes nested contact lists."""
        campaign = EmailCampaignFactory(group=self.group)
        
        # Create and add multiple lists
        lists = [
            ContactListFactory(group=self.group, name=f'List {i}')
            for i in range(3)
        ]
        campaign.contact_lists.add(*lists)
        
        serializer = EmailCampaignSerializer(campaign)
        data = serializer.data
        
        self.assertEqual(len(data['contact_lists']), 3)
        self.assertEqual(data['contact_lists'][0]['name'], 'List 0')
    
    def test_message_with_nested_relationships(self):
        """Test message serializer includes nested relationships."""
        campaign = EmailCampaignFactory(group=self.group, name='Test Campaign')
        contact = ContactFactory(
            group=self.group,
            email='nested@example.com',
            first_name='Nested',
            last_name='Contact'
        )
        message = EmailMessageFactory(
            campaign=campaign,
            contact=contact,
            group=self.group
        )
        
        # Add events
        EmailEventFactory(message=message, event_type=EmailEvent.EventType.SENT)
        EmailEventFactory(message=message, event_type=EmailEvent.EventType.OPENED)
        
        serializer = EmailMessageSerializer(message)
        data = serializer.data
        
        # Check nested campaign info
        self.assertEqual(data['campaign'], str(campaign.id))
        
        # Check nested contact info
        self.assertEqual(data['contact']['email'], 'nested@example.com')
        self.assertEqual(data['contact']['first_name'], 'Nested')
        
        # Check nested events
        self.assertEqual(len(data['events']), 2)


class ValidationEdgeCaseTests(TestCase):
    """Test edge cases and complex validation scenarios."""
    
    def setUp(self):
        """Set up test data."""
        self.group = GroupFactory()
        self.user = UserFactory()
        GroupMembership.objects.create(user=self.user, group=self.group)
    
    def test_template_with_complex_variables(self):
        """Test template validation with complex variable patterns."""
        template = EmailTemplateFactory(
            group=self.group,
            subject='Hello {{ user.first_name }} - {{ date|format:"Y-m-d" }}',
            html_content='''
                <p>Dear {{ user.get_full_name|default:"Valued Customer" }},</p>
                <p>Your balance is {{ account.balance|floatformat:2 }}</p>
                <a href="{{ unsubscribe_url }}">Unsubscribe</a>
            ''',
            text_content='Simple text {{ unsubscribe_url }}'
        )
        
        serializer = EmailTemplateSerializer(template)
        data = serializer.data
        
        # Should handle complex template syntax without errors
        self.assertIn('preview_html', data)
        self.assertIn('Template error:', data['preview_html'])  # Complex syntax will fail with simple context
    
    def test_campaign_with_timezone_scheduling(self):
        """Test campaign scheduling with timezone considerations."""
        import pytz
        
        # Create campaign scheduled in different timezone
        eastern = pytz.timezone('US/Eastern')
        scheduled_time = eastern.localize(datetime(2024, 12, 25, 9, 0))
        
        data = {
            'name': 'Holiday Campaign',
            'template': str(EmailTemplateFactory(group=self.group).id),
            'sending_strategy': EmailCampaign.SendingStrategy.SCHEDULED,
            'scheduled_at': scheduled_time.isoformat()
        }
        
        serializer = EmailCampaignSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Verify timezone is preserved
        campaign = serializer.save(group=self.group, created_by=self.user)
        self.assertEqual(campaign.scheduled_at.tzinfo, pytz.UTC)
    
    def test_html_content_sanitization(self):
        """Test HTML content with potentially malicious content."""
        data = {
            'name': 'Test Template',
            'template_type': EmailTemplate.TemplateType.MARKETING,
            'subject': 'Test',
            'html_content': '''
                <script>alert('XSS')</script>
                <p>Hello {{ first_name }}!</p>
                <iframe src="http://evil.com"></iframe>
                <a href="{{ unsubscribe_url }}">Unsubscribe</a>
            ''',
            'text_content': 'Hello {{ first_name }}! {{ unsubscribe_url }}'
        }
        
        serializer = EmailTemplateSerializer(data=data)
        # Should be valid - sanitization happens at render time
        self.assertTrue(serializer.is_valid())
    
    def test_circular_reference_handling(self):
        """Test handling of circular references in serialization."""
        # Create campaign with self-referencing relationships
        campaign = EmailCampaignFactory(group=self.group)
        contact_list = ContactListFactory(group=self.group)
        contact = ContactFactory(group=self.group)
        
        campaign.contact_lists.add(contact_list)
        contact_list.contacts.add(contact)
        
        # Create message that references back to campaign
        message = EmailMessageFactory(
            campaign=campaign,
            contact=contact,
            group=self.group
        )
        
        # This should not cause infinite recursion
        serializer = EmailMessageSerializer(message)
        data = serializer.data
        
        self.assertEqual(data['campaign'], str(campaign.id))
        self.assertEqual(data['contact']['id'], str(contact.id))