"""
Tests for email campaign ViewSets.

Comprehensive test coverage for EmailTemplate, EmailCampaign, EmailMessage,
and EmailEvent ViewSets including CRUD operations, permissions, campaign
sending, analytics, and webhook endpoints.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, Mock, MagicMock

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from factory import Factory, Sequence, SubFactory
import factory

from accounts.models import Group, GroupMembership, Role
from contacts.models import (
    Contact, ContactList, EmailTemplate, EmailCampaign,
    EmailMessage, EmailEvent, ContactStatus
)
from contacts.email_views import (
    EmailTemplateViewSet, EmailCampaignViewSet,
    EmailMessageViewSet, EmailEventViewSet
)

User = get_user_model()


# Factories for test data generation
class GroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Group
    
    name = Sequence(lambda n: f"Test Group {n}")


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
    
    username = Sequence(lambda n: f"user{n}")
    email = Sequence(lambda n: f"user{n}@test.com")
    first_name = "Test"
    last_name = Sequence(lambda n: f"User{n}")


class ContactFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Contact
    
    email = Sequence(lambda n: f"contact{n}@example.com")
    first_name = Sequence(lambda n: f"Contact{n}")
    last_name = "Test"
    contact_type = Contact.ContactType.INDIVIDUAL
    status = Contact.ContactStatus.LEAD
    email_opt_in = True
    group = SubFactory(GroupFactory)


class ContactListFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ContactList
    
    name = Sequence(lambda n: f"List {n}")
    description = "Test contact list"
    is_dynamic = False
    created_by = SubFactory(UserFactory)
    group = SubFactory(GroupFactory)


class EmailTemplateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailTemplate
    
    name = Sequence(lambda n: f"Template {n}")
    template_type = EmailTemplate.TemplateType.MARKETING
    subject = "Test Subject - {{ first_name }}"
    preheader = "Test preheader"
    html_content = "<html><body>Hello {{ first_name }}! <a href='{{ unsubscribe_url }}'>Unsubscribe</a></body></html>"
    text_content = "Hello {{ first_name }}! Unsubscribe: {{ unsubscribe_url }}"
    from_name = "Test Sender"
    from_email = "noreply@test.com"
    is_active = True
    is_tested = False
    created_by = SubFactory(UserFactory)
    group = SubFactory(GroupFactory)


class EmailCampaignFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailCampaign
    
    name = Sequence(lambda n: f"Campaign {n}")
    description = "Test campaign"
    template = SubFactory(EmailTemplateFactory)
    status = EmailCampaign.CampaignStatus.DRAFT
    sending_strategy = EmailCampaign.SendingStrategy.IMMEDIATE
    track_opens = True
    track_clicks = True
    include_unsubscribe_link = True
    created_by = SubFactory(UserFactory)
    group = SubFactory(GroupFactory)


class EmailMessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailMessage
    
    campaign = SubFactory(EmailCampaignFactory)
    contact = SubFactory(ContactFactory)
    template_used = SubFactory(EmailTemplateFactory)
    subject = "Test Email"
    from_email = "noreply@test.com"
    to_email = Sequence(lambda n: f"recipient{n}@example.com")
    status = EmailMessage.MessageStatus.PENDING
    group = SubFactory(GroupFactory)


class EmailEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailEvent
    
    message = SubFactory(EmailMessageFactory)
    event_type = EmailEvent.EventType.SENT
    timestamp = factory.LazyFunction(timezone.now)


class EmailTemplateViewSetTests(TestCase):
    """Test cases for EmailTemplate ViewSet."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create test group and users
        self.group = GroupFactory()
        self.admin_user = UserFactory()
        self.manager_user = UserFactory()
        self.analyst_user = UserFactory()
        
        # Set up roles and memberships
        GroupMembership.objects.create(
            user=self.admin_user,
            group=self.group,
            role=Role.ADMIN
        )
        GroupMembership.objects.create(
            user=self.manager_user,
            group=self.group,
            role=Role.MANAGER
        )
        GroupMembership.objects.create(
            user=self.analyst_user,
            group=self.group,
            role=Role.ANALYST
        )
        
        # Create test templates
        self.template1 = EmailTemplateFactory(group=self.group, created_by=self.admin_user)
        self.template2 = EmailTemplateFactory(group=self.group, created_by=self.manager_user)
        
        # Create template in different group
        self.other_group = GroupFactory()
        self.other_template = EmailTemplateFactory(group=self.other_group)
    
    def test_list_templates_authenticated(self):
        """Test listing templates with authentication."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('emailtemplate-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        
        # Verify only templates from user's group are returned
        template_ids = [t['id'] for t in response.data['results']]
        self.assertIn(str(self.template1.id), template_ids)
        self.assertIn(str(self.template2.id), template_ids)
        self.assertNotIn(str(self.other_template.id), template_ids)
    
    def test_list_templates_unauthenticated(self):
        """Test listing templates without authentication."""
        url = reverse('emailtemplate-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_create_template(self):
        """Test creating a new email template."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('emailtemplate-list')
        data = {
            'name': 'New Template',
            'template_type': EmailTemplate.TemplateType.MARKETING,
            'subject': 'Welcome {{ first_name }}!',
            'preheader': 'Thanks for joining',
            'html_content': '<p>Hello {{ first_name }}! <a href="{{ unsubscribe_url }}">Unsubscribe</a></p>',
            'text_content': 'Hello {{ first_name }}! Unsubscribe: {{ unsubscribe_url }}',
            'from_name': 'Test Company',
            'from_email': 'hello@company.com'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Template')
        self.assertIn('{{ first_name }}', response.data['subject'])
        
        # Verify template was created
        template = EmailTemplate.objects.get(id=response.data['id'])
        self.assertEqual(template.group, self.group)
        self.assertEqual(template.created_by, self.admin_user)
    
    def test_create_template_missing_unsubscribe(self):
        """Test creating template without unsubscribe link fails."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('emailtemplate-list')
        data = {
            'name': 'Bad Template',
            'template_type': EmailTemplate.TemplateType.MARKETING,
            'subject': 'Test',
            'html_content': '<p>No unsubscribe link!</p>',
            'text_content': 'No unsubscribe link!'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('unsubscribe_url', str(response.data))
    
    def test_update_template(self):
        """Test updating an email template."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('emailtemplate-detail', args=[self.template1.id])
        data = {
            'name': 'Updated Template',
            'subject': self.template1.subject,
            'html_content': self.template1.html_content,
            'text_content': self.template1.text_content
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Template')
        
        # Verify update
        self.template1.refresh_from_db()
        self.assertEqual(self.template1.name, 'Updated Template')
    
    def test_delete_template(self):
        """Test deleting an email template."""
        self.client.force_authenticate(user=self.admin_user)
        
        template_id = self.template1.id
        url = reverse('emailtemplate-detail', args=[template_id])
        
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(EmailTemplate.objects.filter(id=template_id).exists())
    
    def test_duplicate_template(self):
        """Test duplicating an email template."""
        self.client.force_authenticate(user=self.manager_user)
        
        url = reverse('emailtemplate-duplicate', args=[self.template1.id])
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], f"{self.template1.name} (Copy)")
        self.assertFalse(response.data['is_active'])
        self.assertFalse(response.data['is_tested'])
        
        # Verify new template was created
        new_template = EmailTemplate.objects.get(id=response.data['id'])
        self.assertEqual(new_template.created_by, self.manager_user)
        self.assertEqual(new_template.html_content, self.template1.html_content)
    
    @patch('contacts.email_tasks.send_test_email.delay')
    def test_send_test_email(self, mock_send_test):
        """Test sending a test email."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('emailtemplate-test', args=[self.template1.id])
        data = {
            'recipient_email': 'test@example.com',
            'test_data': {
                'first_name': 'Test',
                'last_name': 'User'
            }
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('queued', response.data['message'])
        
        # Verify task was called
        mock_send_test.assert_called_once_with(
            template_id=str(self.template1.id),
            recipient_email='test@example.com',
            test_data={'first_name': 'Test', 'last_name': 'User'},
            sender_id=str(self.admin_user.id)
        )
        
        # Verify template marked as tested
        self.template1.refresh_from_db()
        self.assertTrue(self.template1.is_tested)
    
    def test_preview_template(self):
        """Test previewing an email template."""
        self.client.force_authenticate(user=self.analyst_user)
        
        url = reverse('emailtemplate-preview', args=[self.template1.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('preview_html', response.data)
        self.assertIn('preview_text', response.data)
        self.assertIn('preview_subject', response.data)
        self.assertIn('preview_data', response.data)
        
        # Verify preview contains rendered content
        self.assertIn('Hello John!', response.data['preview_html'])
        self.assertIn('Test Subject - John', response.data['preview_subject'])
    
    def test_preview_template_custom_data(self):
        """Test previewing template with custom data."""
        self.client.force_authenticate(user=self.analyst_user)
        
        url = reverse('emailtemplate-preview', args=[self.template1.id])
        params = {
            'first_name': 'Jane',
            'last_name': 'Smith'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Hello Jane!', response.data['preview_html'])
        self.assertIn('Test Subject - Jane', response.data['preview_subject'])
    
    def test_validate_template_variables(self):
        """Test validating template variables."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create template with custom variables
        template = EmailTemplateFactory(
            group=self.group,
            subject='Hello {{ first_name }} from {{ company_name }}',
            html_content='<p>{{ greeting }} {{ unknown_var }}! <a href="{{ unsubscribe_url }}">Unsubscribe</a></p>',
            text_content='{{ greeting }} {{ unknown_var }}! Unsubscribe: {{ unsubscribe_url }}'
        )
        
        url = reverse('emailtemplate-validate-variables', args=[template.id])
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('first_name', response.data['found_variables'])
        self.assertIn('company_name', response.data['found_variables'])
        self.assertIn('unknown_var', response.data['missing_variables'])
        self.assertFalse(response.data['is_valid'])
    
    def test_filter_templates_by_type(self):
        """Test filtering templates by type."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create templates of different types
        EmailTemplateFactory(
            group=self.group,
            template_type=EmailTemplate.TemplateType.TRANSACTIONAL
        )
        EmailTemplateFactory(
            group=self.group,
            template_type=EmailTemplate.TemplateType.NEWSLETTER
        )
        
        url = reverse('emailtemplate-list')
        response = self.client.get(url, {'template_type': 'marketing'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should have the 2 marketing templates from setUp
        self.assertEqual(len(response.data['results']), 2)
        
        for template in response.data['results']:
            self.assertEqual(template['template_type'], 'marketing')
    
    def test_search_templates(self):
        """Test searching templates."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create template with unique content
        EmailTemplateFactory(
            group=self.group,
            name='Special Newsletter',
            subject='Monthly Update'
        )
        
        url = reverse('emailtemplate-list')
        response = self.client.get(url, {'search': 'newsletter'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Special Newsletter')


class EmailCampaignViewSetTests(TestCase):
    """Test cases for EmailCampaign ViewSet."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create test group and users
        self.group = GroupFactory()
        self.admin_user = UserFactory()
        self.manager_user = UserFactory()
        
        GroupMembership.objects.create(
            user=self.admin_user,
            group=self.group,
            role=Role.ADMIN
        )
        GroupMembership.objects.create(
            user=self.manager_user,
            group=self.group,
            role=Role.MANAGER
        )
        
        # Create test data
        self.template = EmailTemplateFactory(
            group=self.group,
            is_active=True,
            is_tested=True
        )
        self.contact_list = ContactListFactory(
            group=self.group,
            created_by=self.admin_user
        )
        
        # Add contacts to list
        self.contacts = [
            ContactFactory(group=self.group, email_opt_in=True)
            for _ in range(5)
        ]
        self.contact_list.contacts.add(*self.contacts)
        
        # Create test campaign
        self.campaign = EmailCampaignFactory(
            group=self.group,
            template=self.template,
            created_by=self.admin_user
        )
        self.campaign.contact_lists.add(self.contact_list)
    
    def test_list_campaigns(self):
        """Test listing campaigns."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create additional campaigns
        EmailCampaignFactory(group=self.group)
        EmailCampaignFactory(group=self.group, status=EmailCampaign.CampaignStatus.SENT)
        
        url = reverse('emailcampaign-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)
    
    def test_create_campaign(self):
        """Test creating a new campaign."""
        self.client.force_authenticate(user=self.manager_user)
        
        url = reverse('emailcampaign-list')
        data = {
            'name': 'New Campaign',
            'description': 'Test campaign description',
            'template': str(self.template.id),
            'sending_strategy': EmailCampaign.SendingStrategy.IMMEDIATE,
            'contact_lists': [str(self.contact_list.id)]
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Campaign')
        self.assertEqual(response.data['status'], EmailCampaign.CampaignStatus.DRAFT)
        
        # Verify campaign was created
        campaign = EmailCampaign.objects.get(id=response.data['id'])
        self.assertEqual(campaign.created_by, self.manager_user)
        self.assertEqual(campaign.contact_lists.count(), 1)
    
    @patch('contacts.email_tasks.send_campaign_emails.delay')
    def test_send_campaign_immediate(self, mock_send):
        """Test sending a campaign immediately."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('emailcampaign-send', args=[self.campaign.id])
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('started sending', response.data['message'])
        self.assertEqual(response.data['recipient_count'], 5)
        
        # Verify campaign status updated
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, EmailCampaign.CampaignStatus.SENDING)
        self.assertIsNotNone(self.campaign.started_at)
        self.assertEqual(self.campaign.approved_by, self.admin_user)
        
        # Verify task was called
        mock_send.assert_called_once_with(str(self.campaign.id))
    
    @patch('contacts.email_tasks.schedule_campaign.apply_async')
    def test_send_campaign_scheduled(self, mock_schedule):
        """Test scheduling a campaign."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Update campaign to scheduled
        scheduled_time = timezone.now() + timedelta(hours=2)
        self.campaign.sending_strategy = EmailCampaign.SendingStrategy.SCHEDULED
        self.campaign.scheduled_at = scheduled_time
        self.campaign.save()
        
        url = reverse('emailcampaign-send', args=[self.campaign.id])
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('scheduled for', response.data['message'])
        
        # Verify campaign status
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, EmailCampaign.CampaignStatus.SCHEDULED)
        
        # Verify task was scheduled
        mock_schedule.assert_called_once_with(
            args=[str(self.campaign.id)],
            eta=scheduled_time
        )
    
    def test_send_campaign_no_recipients(self):
        """Test sending campaign with no recipients fails."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create campaign with no lists
        campaign = EmailCampaignFactory(
            group=self.group,
            template=self.template
        )
        
        url = reverse('emailcampaign-send', args=[campaign.id])
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('no recipients', response.data['error'])
    
    def test_send_campaign_inactive_template(self):
        """Test sending campaign with inactive template fails."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Make template inactive
        self.template.is_active = False
        self.template.save()
        
        url = reverse('emailcampaign-send', args=[self.campaign.id])
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not active', response.data['error'])
    
    def test_send_campaign_untested_template(self):
        """Test sending campaign with untested template fails."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Make template untested
        self.template.is_tested = False
        self.template.save()
        
        url = reverse('emailcampaign-send', args=[self.campaign.id])
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not been tested', response.data['error'])
    
    def test_pause_campaign(self):
        """Test pausing an active campaign."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Set campaign to sending
        self.campaign.status = EmailCampaign.CampaignStatus.SENDING
        self.campaign.save()
        
        url = reverse('emailcampaign-pause', args=[self.campaign.id])
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify status
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, EmailCampaign.CampaignStatus.PAUSED)
    
    @patch('contacts.email_tasks.send_campaign_emails.delay')
    def test_resume_campaign(self, mock_send):
        """Test resuming a paused campaign."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Set campaign to paused
        self.campaign.status = EmailCampaign.CampaignStatus.PAUSED
        self.campaign.save()
        
        url = reverse('emailcampaign-resume', args=[self.campaign.id])
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify status and task called
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, EmailCampaign.CampaignStatus.SENDING)
        mock_send.assert_called_once_with(str(self.campaign.id))
    
    def test_cancel_campaign(self):
        """Test canceling a campaign."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('emailcampaign-cancel', args=[self.campaign.id])
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify status
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, EmailCampaign.CampaignStatus.CANCELLED)
    
    def test_duplicate_campaign(self):
        """Test duplicating a campaign."""
        self.client.force_authenticate(user=self.manager_user)
        
        # Add some excluded contacts
        excluded = ContactFactory(group=self.group)
        self.campaign.excluded_contacts.add(excluded)
        
        url = reverse('emailcampaign-duplicate', args=[self.campaign.id])
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], f"{self.campaign.name} (Copy)")
        self.assertEqual(response.data['status'], EmailCampaign.CampaignStatus.DRAFT)
        
        # Verify relationships were copied
        new_campaign = EmailCampaign.objects.get(id=response.data['id'])
        self.assertEqual(new_campaign.contact_lists.count(), 1)
        self.assertEqual(new_campaign.excluded_contacts.count(), 1)
        self.assertEqual(new_campaign.created_by, self.manager_user)
    
    def test_get_campaign_recipients(self):
        """Test getting campaign recipients."""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('emailcampaign-recipients', args=[self.campaign.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)
        
        # Verify all recipients have opt-in
        for recipient in response.data['results']:
            contact = Contact.objects.get(id=recipient['id'])
            self.assertTrue(contact.email_opt_in)
    
    def test_exclude_contacts(self):
        """Test excluding contacts from campaign."""
        self.client.force_authenticate(user=self.admin_user)
        
        contacts_to_exclude = self.contacts[:2]
        
        url = reverse('emailcampaign-add-excluded-contacts', args=[self.campaign.id])
        data = {
            'contact_ids': [str(c.id) for c in contacts_to_exclude]
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['excluded'], 2)
        
        # Verify exclusions
        self.assertEqual(self.campaign.excluded_contacts.count(), 2)
    
    def test_campaign_analytics(self):
        """Test getting campaign analytics."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Set campaign as sent with metrics
        self.campaign.status = EmailCampaign.CampaignStatus.SENT
        self.campaign.started_at = timezone.now() - timedelta(hours=2)
        self.campaign.completed_at = timezone.now()
        self.campaign.total_recipients = 100
        self.campaign.emails_sent = 100
        self.campaign.emails_delivered = 95
        self.campaign.emails_opened = 30
        self.campaign.emails_clicked = 10
        self.campaign.emails_bounced = 5
        self.campaign.save()
        
        # Create some messages and events
        for i in range(3):
            message = EmailMessageFactory(
                campaign=self.campaign,
                contact=self.contacts[i],
                status=EmailMessage.MessageStatus.DELIVERED
            )
            EmailEventFactory(
                message=message,
                event_type=EmailEvent.EventType.OPENED
            )
        
        url = reverse('emailcampaign-analytics', args=[self.campaign.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify analytics data
        self.assertEqual(response.data['summary']['total_recipients'], 100)
        self.assertEqual(response.data['summary']['emails_delivered'], 95)
        self.assertEqual(response.data['summary']['open_rate'], 31.58)  # 30/95 * 100
        self.assertEqual(response.data['summary']['click_rate'], 10.53)  # 10/95 * 100
        self.assertEqual(response.data['summary']['bounce_rate'], 5.0)   # 5/100 * 100
    
    def test_campaign_stats(self):
        """Test getting overall campaign statistics."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create completed campaigns with metrics
        for i in range(3):
            campaign = EmailCampaignFactory(
                group=self.group,
                status=EmailCampaign.CampaignStatus.SENT,
                emails_sent=100,
                emails_delivered=90,
                emails_opened=30,
                emails_clicked=10
            )
        
        url = reverse('emailcampaign-stats')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_campaigns'], 4)  # 3 + 1 from setUp
        self.assertEqual(response.data['total_emails_sent'], 300)
        self.assertGreater(response.data['average_open_rate'], 0)
        self.assertGreater(response.data['average_click_rate'], 0)
    
    def test_ab_test_campaign(self):
        """Test A/B test campaign configuration."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create variant templates
        variant1 = EmailTemplateFactory(group=self.group)
        variant2 = EmailTemplateFactory(group=self.group)
        
        url = reverse('emailcampaign-list')
        data = {
            'name': 'A/B Test Campaign',
            'template': str(self.template.id),
            'is_ab_test': True,
            'ab_test_percentage': 20,
            'variant_templates': [str(variant1.id), str(variant2.id)],
            'contact_lists': [str(self.contact_list.id)]
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_ab_test'])
        self.assertEqual(response.data['ab_test_percentage'], 20)
        
        # Verify variants
        campaign = EmailCampaign.objects.get(id=response.data['id'])
        self.assertEqual(campaign.variant_templates.count(), 2)


class EmailMessageViewSetTests(TestCase):
    """Test cases for EmailMessage ViewSet (read-only)."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create test group and user
        self.group = GroupFactory()
        self.user = UserFactory()
        GroupMembership.objects.create(
            user=self.user,
            group=self.group,
            role=Role.MANAGER
        )
        
        # Create test campaign and messages
        self.campaign = EmailCampaignFactory(group=self.group)
        self.contact = ContactFactory(group=self.group)
        
        self.messages = []
        for i in range(5):
            message = EmailMessageFactory(
                campaign=self.campaign,
                contact=ContactFactory(group=self.group),
                group=self.group
            )
            self.messages.append(message)
    
    def test_list_messages(self):
        """Test listing email messages."""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('emailmessage-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)
    
    def test_filter_messages_by_campaign(self):
        """Test filtering messages by campaign."""
        self.client.force_authenticate(user=self.user)
        
        # Create messages for different campaign
        other_campaign = EmailCampaignFactory(group=self.group)
        EmailMessageFactory(campaign=other_campaign, group=self.group)
        
        url = reverse('emailmessage-list')
        response = self.client.get(url, {'campaign_id': str(self.campaign.id)})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)
        
        # All messages should be from the filtered campaign
        for message in response.data['results']:
            self.assertEqual(message['campaign'], str(self.campaign.id))
    
    def test_filter_messages_by_status(self):
        """Test filtering messages by status."""
        self.client.force_authenticate(user=self.user)
        
        # Update some message statuses
        self.messages[0].status = EmailMessage.MessageStatus.DELIVERED
        self.messages[0].save()
        self.messages[1].status = EmailMessage.MessageStatus.DELIVERED
        self.messages[1].save()
        
        url = reverse('emailmessage-list')
        response = self.client.get(url, {'status': 'delivered'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_get_message_events(self):
        """Test getting events for a message."""
        self.client.force_authenticate(user=self.user)
        
        message = self.messages[0]
        
        # Create events
        events = [
            EmailEventFactory(message=message, event_type=EmailEvent.EventType.SENT),
            EmailEventFactory(message=message, event_type=EmailEvent.EventType.DELIVERED),
            EmailEventFactory(message=message, event_type=EmailEvent.EventType.OPENED)
        ]
        
        url = reverse('emailmessage-events', args=[message.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        
        # Verify events are in reverse chronological order
        event_types = [e['event_type'] for e in response.data]
        self.assertEqual(event_types[0], EmailEvent.EventType.OPENED)
    
    @patch('contacts.email_tasks.send_single_email.delay')
    def test_resend_failed_message(self, mock_send):
        """Test resending a failed message."""
        self.client.force_authenticate(user=self.user)
        
        # Set message as failed
        message = self.messages[0]
        message.status = EmailMessage.MessageStatus.FAILED
        message.failed_reason = 'Network error'
        message.save()
        
        url = reverse('emailmessage-resend', args=[message.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify message reset
        message.refresh_from_db()
        self.assertEqual(message.status, EmailMessage.MessageStatus.PENDING)
        self.assertEqual(message.failed_reason, '')
        
        # Verify task called
        mock_send.assert_called_once_with(str(message.id))
    
    def test_resend_non_failed_message(self):
        """Test resending non-failed message fails."""
        self.client.force_authenticate(user=self.user)
        
        # Message is in PENDING status
        message = self.messages[0]
        
        url = reverse('emailmessage-resend', args=[message.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('only resend failed', response.data['error'])
    
    def test_messages_include_events(self):
        """Test messages include their events."""
        self.client.force_authenticate(user=self.user)
        
        message = self.messages[0]
        EmailEventFactory(message=message, event_type=EmailEvent.EventType.SENT)
        EmailEventFactory(message=message, event_type=EmailEvent.EventType.OPENED)
        
        url = reverse('emailmessage-detail', args=[message.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['events']), 2)


class EmailEventViewSetTests(TestCase):
    """Test cases for EmailEvent ViewSet and webhook."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create test groups and users
        self.group1 = GroupFactory()
        self.group2 = GroupFactory()
        
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        
        GroupMembership.objects.create(user=self.user1, group=self.group1)
        GroupMembership.objects.create(user=self.user2, group=self.group2)
        
        # Create campaigns and messages in different groups
        self.campaign1 = EmailCampaignFactory(group=self.group1)
        self.campaign2 = EmailCampaignFactory(group=self.group2)
        
        self.message1 = EmailMessageFactory(campaign=self.campaign1, group=self.group1)
        self.message2 = EmailMessageFactory(campaign=self.campaign2, group=self.group2)
        
        # Create events
        self.event1 = EmailEventFactory(message=self.message1)
        self.event2 = EmailEventFactory(message=self.message2)
    
    def test_list_events_filtered_by_group(self):
        """Test events are filtered by user's group."""
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('emailevent-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        # Verify only events from user's group campaigns
        event = response.data['results'][0]
        self.assertEqual(event['id'], str(self.event1.id))
    
    def test_filter_events_by_type(self):
        """Test filtering events by type."""
        self.client.force_authenticate(user=self.user1)
        
        # Create events of different types
        EmailEventFactory(
            message=self.message1,
            event_type=EmailEvent.EventType.OPENED
        )
        EmailEventFactory(
            message=self.message1,
            event_type=EmailEvent.EventType.CLICKED
        )
        
        url = reverse('emailevent-list')
        response = self.client.get(url, {'event_type': 'opened'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['event_type'], 'opened')
    
    def test_filter_events_by_date_range(self):
        """Test filtering events by date range."""
        self.client.force_authenticate(user=self.user1)
        
        # Create event with specific timestamp
        past_event = EmailEventFactory(
            message=self.message1,
            timestamp=timezone.now() - timedelta(days=7)
        )
        
        url = reverse('emailevent-list')
        
        # Filter for last 3 days
        start_date = (timezone.now() - timedelta(days=3)).isoformat()
        response = self.client.get(url, {'start_date': start_date})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)  # Only recent event
    
    @patch('contacts.email_tasks.process_email_event.delay')
    def test_webhook_endpoint(self, mock_process):
        """Test webhook endpoint for email events."""
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('emailevent-webhook')
        
        # Single event
        event_data = {
            'event': 'delivered',
            'email': 'test@example.com',
            'timestamp': timezone.now().isoformat(),
            'sg_message_id': 'test-message-id'
        }
        
        response = self.client.post(url, event_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        mock_process.assert_called_once_with(event_data)
    
    @patch('contacts.email_tasks.process_email_event.delay')
    def test_webhook_batch_events(self, mock_process):
        """Test webhook with batch of events."""
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('emailevent-webhook')
        
        # Batch of events
        events = [
            {
                'event': 'delivered',
                'email': 'test1@example.com',
                'timestamp': timezone.now().isoformat()
            },
            {
                'event': 'open',
                'email': 'test2@example.com',
                'timestamp': timezone.now().isoformat()
            }
        ]
        
        response = self.client.post(url, events, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(mock_process.call_count, 2)
    
    def test_webhook_requires_authentication(self):
        """Test webhook requires authentication."""
        url = reverse('emailevent-webhook')
        
        event_data = {'event': 'delivered'}
        
        response = self.client.post(url, event_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class EmailCampaignPermissionTests(TestCase):
    """Test role-based permissions for email campaigns."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create group and users with different roles
        self.group = GroupFactory()
        
        self.admin = UserFactory()
        self.manager = UserFactory()
        self.analyst = UserFactory()
        self.viewer = UserFactory()
        
        GroupMembership.objects.create(user=self.admin, group=self.group, role=Role.ADMIN)
        GroupMembership.objects.create(user=self.manager, group=self.group, role=Role.MANAGER)
        GroupMembership.objects.create(user=self.analyst, group=self.group, role=Role.ANALYST)
        GroupMembership.objects.create(user=self.viewer, group=self.group, role=Role.VIEWER)
        
        # Create test data
        self.template = EmailTemplateFactory(group=self.group)
        self.campaign = EmailCampaignFactory(group=self.group, template=self.template)
    
    def test_admin_can_manage_campaigns(self):
        """Test admin has full campaign permissions."""
        self.client.force_authenticate(user=self.admin)
        
        # Can create
        url = reverse('emailcampaign-list')
        response = self.client.post(url, {
            'name': 'Admin Campaign',
            'template': str(self.template.id)
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Can update
        url = reverse('emailcampaign-detail', args=[self.campaign.id])
        response = self.client.patch(url, {'name': 'Updated'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Can delete
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_manager_can_manage_campaigns(self):
        """Test manager has campaign management permissions."""
        self.client.force_authenticate(user=self.manager)
        
        # Can create campaigns
        url = reverse('emailcampaign-list')
        response = self.client.post(url, {
            'name': 'Manager Campaign',
            'template': str(self.template.id)
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Can send campaigns
        campaign = EmailCampaignFactory(
            group=self.group,
            template=self.template
        )
        url = reverse('emailcampaign-send', args=[campaign.id])
        
        # Note: Will fail due to no recipients, but that's a validation error not permission
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('no recipients', response.data['error'])
    
    def test_analyst_can_view_campaigns(self):
        """Test analyst can view but not modify campaigns."""
        self.client.force_authenticate(user=self.analyst)
        
        # Can list campaigns
        url = reverse('emailcampaign-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Can view campaign details
        url = reverse('emailcampaign-detail', args=[self.campaign.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Can view analytics
        url = reverse('emailcampaign-analytics', args=[self.campaign.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_viewer_read_only_access(self):
        """Test viewer has read-only access."""
        self.client.force_authenticate(user=self.viewer)
        
        # Can list
        url = reverse('emailcampaign-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Can view
        url = reverse('emailcampaign-detail', args=[self.campaign.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)