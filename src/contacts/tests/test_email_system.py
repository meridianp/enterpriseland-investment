"""
Comprehensive test suite for the EnterpriseLand email system.

Tests EmailTemplate, EmailCampaign, EmailMessage models and ViewSets,
campaign CRUD operations, permissions, email sending workflow, and
external service mocking.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from contacts.models import (
    EmailTemplate, EmailCampaign, EmailMessage, EmailEvent,
    Contact, ContactList, ContactTag, CampaignStatus, EmailStatus
)
from accounts.models import Group, GroupMembership
from contacts.tasks import send_campaign_emails, process_email_events

User = get_user_model()


class EmailModelTestCase(TestCase):
    """Test email-related models"""
    
    def setUp(self):
        """Set up test data"""
        # Create test group and users
        self.group = Group.objects.create(name="Test Company")
        self.admin_user = User.objects.create_user(
            username="admin@test.com",
            email="admin@test.com",
            password="testpass123",
            role=User.Role.ADMIN
        )
        self.analyst_user = User.objects.create_user(
            username="analyst@test.com",
            email="analyst@test.com",
            password="testpass123",
            role=User.Role.BUSINESS_ANALYST
        )
        
        # Add users to group
        GroupMembership.objects.create(user=self.admin_user, group=self.group, is_admin=True)
        GroupMembership.objects.create(user=self.analyst_user, group=self.group)
        
        # Create test contacts
        self.contact1 = Contact.objects.create(
            email="contact1@example.com",
            first_name="John",
            last_name="Doe",
            company="Example Corp",
            group=self.group,
            created_by=self.admin_user
        )
        self.contact2 = Contact.objects.create(
            email="contact2@example.com",
            first_name="Jane",
            last_name="Smith",
            company="Test Inc",
            group=self.group,
            created_by=self.admin_user
        )
        
        # Create contact list
        self.contact_list = ContactList.objects.create(
            name="Test List",
            description="Test contact list",
            group=self.group,
            created_by=self.admin_user
        )
        self.contact_list.contacts.add(self.contact1, self.contact2)
    
    def test_email_template_creation(self):
        """Test creating email templates"""
        template = EmailTemplate.objects.create(
            name="Welcome Email",
            subject="Welcome to {{company_name}}",
            html_content="<h1>Welcome {{first_name}}</h1>",
            text_content="Welcome {{first_name}}",
            group=self.group,
            created_by=self.admin_user
        )
        
        self.assertEqual(template.name, "Welcome Email")
        self.assertIn("{{first_name}}", template.html_content)
        self.assertEqual(template.group, self.group)
        self.assertEqual(template.created_by, self.admin_user)
    
    def test_email_campaign_creation(self):
        """Test creating email campaigns"""
        template = EmailTemplate.objects.create(
            name="Campaign Template",
            subject="Special Offer",
            html_content="<p>Content</p>",
            group=self.group,
            created_by=self.admin_user
        )
        
        campaign = EmailCampaign.objects.create(
            name="Q1 Campaign",
            template=template,
            contact_list=self.contact_list,
            scheduled_for=timezone.now() + timedelta(days=1),
            group=self.group,
            created_by=self.admin_user
        )
        
        self.assertEqual(campaign.name, "Q1 Campaign")
        self.assertEqual(campaign.status, CampaignStatus.DRAFT)
        self.assertEqual(campaign.contact_list, self.contact_list)
        self.assertTrue(campaign.scheduled_for > timezone.now())
    
    def test_campaign_state_transitions(self):
        """Test campaign state machine transitions"""
        template = EmailTemplate.objects.create(
            name="Test Template",
            subject="Test",
            html_content="<p>Test</p>",
            group=self.group,
            created_by=self.admin_user
        )
        
        campaign = EmailCampaign.objects.create(
            name="State Test Campaign",
            template=template,
            contact_list=self.contact_list,
            group=self.group,
            created_by=self.admin_user
        )
        
        # Test draft to scheduled transition
        self.assertTrue(campaign.can_schedule())
        campaign.schedule()
        campaign.save()
        self.assertEqual(campaign.status, CampaignStatus.SCHEDULED)
        
        # Test scheduled to sending transition
        self.assertTrue(campaign.can_start_sending())
        campaign.start_sending()
        campaign.save()
        self.assertEqual(campaign.status, CampaignStatus.SENDING)
        
        # Test sending to completed transition
        self.assertTrue(campaign.can_complete())
        campaign.complete()
        campaign.save()
        self.assertEqual(campaign.status, CampaignStatus.COMPLETED)
    
    def test_email_message_creation(self):
        """Test creating email messages"""
        template = EmailTemplate.objects.create(
            name="Message Template",
            subject="Hello {{first_name}}",
            html_content="<p>Hello {{first_name}}</p>",
            group=self.group,
            created_by=self.admin_user
        )
        
        campaign = EmailCampaign.objects.create(
            name="Message Campaign",
            template=template,
            contact_list=self.contact_list,
            group=self.group,
            created_by=self.admin_user
        )
        
        message = EmailMessage.objects.create(
            campaign=campaign,
            contact=self.contact1,
            to_email=self.contact1.email,
            subject="Hello John",
            html_content="<p>Hello John</p>",
            text_content="Hello John",
            group=self.group
        )
        
        self.assertEqual(message.status, EmailStatus.PENDING)
        self.assertEqual(message.to_email, "contact1@example.com")
        self.assertEqual(message.contact, self.contact1)


class EmailAPITestCase(APITestCase):
    """Test email API endpoints"""
    
    def setUp(self):
        """Set up test data and authentication"""
        # Create test group and users
        self.group = Group.objects.create(name="API Test Company")
        self.admin_user = User.objects.create_user(
            username="admin@apitest.com",
            email="admin@apitest.com",
            password="testpass123",
            role=User.Role.ADMIN
        )
        self.analyst_user = User.objects.create_user(
            username="analyst@apitest.com",
            email="analyst@apitest.com",
            password="testpass123",
            role=User.Role.BUSINESS_ANALYST
        )
        self.readonly_user = User.objects.create_user(
            username="readonly@apitest.com",
            email="readonly@apitest.com",
            password="testpass123",
            role=User.Role.READ_ONLY
        )
        
        # Add users to group
        GroupMembership.objects.create(user=self.admin_user, group=self.group, is_admin=True)
        GroupMembership.objects.create(user=self.analyst_user, group=self.group)
        GroupMembership.objects.create(user=self.readonly_user, group=self.group)
        
        # Create JWT tokens
        self.admin_token = str(RefreshToken.for_user(self.admin_user).access_token)
        self.analyst_token = str(RefreshToken.for_user(self.analyst_user).access_token)
        self.readonly_token = str(RefreshToken.for_user(self.readonly_user).access_token)
        
        # Create test data
        self.contact_list = ContactList.objects.create(
            name="API Test List",
            group=self.group,
            created_by=self.admin_user
        )
        
        self.template = EmailTemplate.objects.create(
            name="API Test Template",
            subject="Test Subject",
            html_content="<p>Test Content</p>",
            group=self.group,
            created_by=self.admin_user
        )
    
    def test_create_email_template(self):
        """Test creating email template via API"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        
        data = {
            "name": "New Template",
            "subject": "{{company_name}} Newsletter",
            "html_content": "<h1>Newsletter</h1><p>{{content}}</p>",
            "text_content": "Newsletter\n{{content}}",
            "category": "marketing"
        }
        
        response = self.client.post('/api/email-templates/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], "New Template")
        self.assertIn("{{company_name}}", response.data['subject'])
        
        # Verify template was created with correct group
        template = EmailTemplate.objects.get(id=response.data['id'])
        self.assertEqual(template.group, self.group)
    
    def test_template_permissions(self):
        """Test template access permissions"""
        # Read-only user should not be able to create templates
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.readonly_token}')
        
        data = {
            "name": "Unauthorized Template",
            "subject": "Test",
            "html_content": "<p>Test</p>"
        }
        
        response = self.client.post('/api/email-templates/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # But should be able to list templates
        response = self.client.get('/api/email-templates/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_create_email_campaign(self):
        """Test creating email campaign via API"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        
        scheduled_time = (timezone.now() + timedelta(hours=2)).isoformat()
        data = {
            "name": "API Test Campaign",
            "template": str(self.template.id),
            "contact_list": str(self.contact_list.id),
            "scheduled_for": scheduled_time,
            "from_name": "Test Company",
            "from_email": "noreply@test.com"
        }
        
        response = self.client.post('/api/email-campaigns/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], "API Test Campaign")
        self.assertEqual(response.data['status'], CampaignStatus.DRAFT)
    
    def test_campaign_actions(self):
        """Test campaign action endpoints"""
        campaign = EmailCampaign.objects.create(
            name="Action Test Campaign",
            template=self.template,
            contact_list=self.contact_list,
            group=self.group,
            created_by=self.admin_user
        )
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        
        # Test schedule action
        response = self.client.post(f'/api/email-campaigns/{campaign.id}/schedule/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, CampaignStatus.SCHEDULED)
        
        # Test pause action
        campaign.status = CampaignStatus.SENDING
        campaign.save()
        
        response = self.client.post(f'/api/email-campaigns/{campaign.id}/pause/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, CampaignStatus.PAUSED)
    
    @patch('contacts.tasks.send_email_via_ses')
    def test_send_test_email(self, mock_send_email):
        """Test sending test email"""
        mock_send_email.return_value = {"MessageId": "test-123"}
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        
        campaign = EmailCampaign.objects.create(
            name="Test Email Campaign",
            template=self.template,
            contact_list=self.contact_list,
            group=self.group,
            created_by=self.admin_user
        )
        
        data = {
            "test_email": "test@example.com"
        }
        
        response = self.client.post(f'/api/email-campaigns/{campaign.id}/send_test/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify mock was called
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args[1]
        self.assertEqual(call_args['to_email'], "test@example.com")
    
    def test_campaign_statistics(self):
        """Test campaign statistics endpoint"""
        campaign = EmailCampaign.objects.create(
            name="Stats Test Campaign",
            template=self.template,
            contact_list=self.contact_list,
            group=self.group,
            created_by=self.admin_user
        )
        
        # Create some email messages with different statuses
        for i, contact in enumerate([self.contact_list.contacts.first()]):
            message = EmailMessage.objects.create(
                campaign=campaign,
                contact=contact,
                to_email=contact.email,
                subject="Test",
                html_content="<p>Test</p>",
                group=self.group
            )
            
            # Set different statuses
            if i == 0:
                message.status = EmailStatus.SENT
                message.sent_at = timezone.now()
            
            message.save()
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        
        response = self.client.get(f'/api/email-campaigns/{campaign.id}/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_recipients', response.data)
        self.assertIn('sent_count', response.data)
        self.assertIn('open_rate', response.data)


class EmailTaskTestCase(TestCase):
    """Test email background tasks"""
    
    def setUp(self):
        """Set up test data"""
        self.group = Group.objects.create(name="Task Test Company")
        self.user = User.objects.create_user(
            username="task@test.com",
            email="task@test.com",
            password="testpass123",
            role=User.Role.ADMIN
        )
        GroupMembership.objects.create(user=self.user, group=self.group)
        
        # Create contacts
        self.contacts = []
        for i in range(3):
            contact = Contact.objects.create(
                email=f"contact{i}@example.com",
                first_name=f"User{i}",
                last_name="Test",
                group=self.group,
                created_by=self.user
            )
            self.contacts.append(contact)
        
        # Create contact list
        self.contact_list = ContactList.objects.create(
            name="Task Test List",
            group=self.group,
            created_by=self.user
        )
        self.contact_list.contacts.set(self.contacts)
        
        # Create template
        self.template = EmailTemplate.objects.create(
            name="Task Template",
            subject="Hello {{first_name}}",
            html_content="<p>Hello {{first_name}}, welcome!</p>",
            text_content="Hello {{first_name}}, welcome!",
            group=self.group,
            created_by=self.user
        )
    
    @patch('contacts.tasks.send_email_via_ses')
    def test_send_campaign_emails_task(self, mock_send_email):
        """Test sending campaign emails via Celery task"""
        mock_send_email.return_value = {"MessageId": "mock-message-id"}
        
        campaign = EmailCampaign.objects.create(
            name="Task Campaign",
            template=self.template,
            contact_list=self.contact_list,
            group=self.group,
            created_by=self.user,
            from_name="Test Company",
            from_email="noreply@test.com"
        )
        
        # Execute task
        result = send_campaign_emails(str(campaign.id))
        
        # Verify emails were created and sent
        messages = EmailMessage.objects.filter(campaign=campaign)
        self.assertEqual(messages.count(), 3)
        
        # Verify personalization
        for message in messages:
            self.assertIn(message.contact.first_name, message.subject)
            self.assertIn(message.contact.first_name, message.html_content)
            self.assertEqual(message.status, EmailStatus.SENT)
            self.assertIsNotNone(message.sent_at)
        
        # Verify mock was called for each contact
        self.assertEqual(mock_send_email.call_count, 3)
    
    @patch('contacts.tasks.send_email_via_ses')
    def test_campaign_error_handling(self, mock_send_email):
        """Test error handling in campaign sending"""
        # Make first call succeed, second fail, third succeed
        mock_send_email.side_effect = [
            {"MessageId": "success-1"},
            Exception("Email service error"),
            {"MessageId": "success-3"}
        ]
        
        campaign = EmailCampaign.objects.create(
            name="Error Test Campaign",
            template=self.template,
            contact_list=self.contact_list,
            group=self.group,
            created_by=self.user
        )
        
        # Execute task
        result = send_campaign_emails(str(campaign.id))
        
        messages = EmailMessage.objects.filter(campaign=campaign)
        sent_messages = messages.filter(status=EmailStatus.SENT)
        failed_messages = messages.filter(status=EmailStatus.FAILED)
        
        # Should have 2 sent and 1 failed
        self.assertEqual(sent_messages.count(), 2)
        self.assertEqual(failed_messages.count(), 1)
        
        # Check error message was recorded
        failed_message = failed_messages.first()
        self.assertIn("Email service error", failed_message.error_message)
    
    def test_process_email_events(self):
        """Test processing email events (opens, clicks, etc.)"""
        campaign = EmailCampaign.objects.create(
            name="Event Test Campaign",
            template=self.template,
            contact_list=self.contact_list,
            group=self.group,
            created_by=self.user
        )
        
        message = EmailMessage.objects.create(
            campaign=campaign,
            contact=self.contacts[0],
            to_email=self.contacts[0].email,
            subject="Test",
            html_content="<p>Test</p>",
            group=self.group,
            status=EmailStatus.SENT,
            external_id="test-message-id"
        )
        
        # Simulate email open event
        events = [
            {
                "eventType": "Open",
                "mail": {"messageId": "test-message-id"},
                "open": {"timestamp": timezone.now().isoformat()}
            },
            {
                "eventType": "Click",
                "mail": {"messageId": "test-message-id"},
                "click": {
                    "timestamp": timezone.now().isoformat(),
                    "link": "https://example.com"
                }
            }
        ]
        
        # Process events
        process_email_events(events)
        
        # Verify events were created
        email_events = EmailEvent.objects.filter(email_message=message)
        self.assertEqual(email_events.count(), 2)
        
        open_event = email_events.filter(event_type="open").first()
        self.assertIsNotNone(open_event)
        
        click_event = email_events.filter(event_type="click").first()
        self.assertIsNotNone(click_event)
        self.assertEqual(click_event.data["link"], "https://example.com")
        
        # Verify message stats were updated
        message.refresh_from_db()
        self.assertEqual(message.open_count, 1)
        self.assertEqual(message.click_count, 1)
        self.assertIsNotNone(message.first_opened_at)


class EmailPermissionTestCase(APITestCase):
    """Test email system permissions and multi-tenancy"""
    
    def setUp(self):
        """Set up test data for permission testing"""
        # Create two separate groups
        self.group1 = Group.objects.create(name="Company 1")
        self.group2 = Group.objects.create(name="Company 2")
        
        # Create users in different groups
        self.user1 = User.objects.create_user(
            username="user1@company1.com",
            email="user1@company1.com",
            password="testpass123",
            role=User.Role.ADMIN
        )
        self.user2 = User.objects.create_user(
            username="user2@company2.com",
            email="user2@company2.com",
            password="testpass123",
            role=User.Role.ADMIN
        )
        
        GroupMembership.objects.create(user=self.user1, group=self.group1)
        GroupMembership.objects.create(user=self.user2, group=self.group2)
        
        # Create templates in each group
        self.template1 = EmailTemplate.objects.create(
            name="Company 1 Template",
            subject="Test",
            html_content="<p>Test</p>",
            group=self.group1,
            created_by=self.user1
        )
        self.template2 = EmailTemplate.objects.create(
            name="Company 2 Template",
            subject="Test",
            html_content="<p>Test</p>",
            group=self.group2,
            created_by=self.user2
        )
        
        # Get tokens
        self.token1 = str(RefreshToken.for_user(self.user1).access_token)
        self.token2 = str(RefreshToken.for_user(self.user2).access_token)
    
    def test_multi_tenant_isolation(self):
        """Test that users can only see their own group's data"""
        # User 1 should only see their template
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token1}')
        response = self.client.get('/api/email-templates/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], "Company 1 Template")
        
        # User 2 should only see their template
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token2}')
        response = self.client.get('/api/email-templates/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], "Company 2 Template")
    
    def test_cross_tenant_access_denied(self):
        """Test that users cannot access other tenant's resources"""
        # User 1 trying to access User 2's template
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token1}')
        response = self.client.get(f'/api/email-templates/{self.template2.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # User 1 trying to update User 2's template
        response = self.client.patch(
            f'/api/email-templates/{self.template2.id}/',
            {"name": "Hacked Template"},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)