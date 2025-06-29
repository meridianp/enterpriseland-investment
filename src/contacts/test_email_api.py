"""
Basic tests for email campaign API endpoints.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import Group, GroupMembership
from .models import EmailTemplate, EmailCampaign, Contact, ContactList

User = get_user_model()


class EmailCampaignAPITestCase(TestCase):
    """Test email campaign API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        # Create test user and group
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.group = Group.objects.create(
            name='Test Organization',
            group_type='ENTERPRISE'
        )
        GroupMembership.objects.create(
            user=self.user,
            group=self.group,
            role='ADMIN'
        )
        
        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Create test contacts
        self.contact1 = Contact.objects.create(
            group=self.group,
            email='contact1@example.com',
            first_name='John',
            last_name='Doe'
        )
        self.contact2 = Contact.objects.create(
            group=self.group,
            email='contact2@example.com',
            first_name='Jane',
            last_name='Smith'
        )
        
        # Create contact list
        self.contact_list = ContactList.objects.create(
            group=self.group,
            name='Test List',
            created_by=self.user
        )
        self.contact_list.contacts.add(self.contact1, self.contact2)
    
    def test_create_email_template(self):
        """Test creating an email template."""
        data = {
            'name': 'Test Template',
            'template_type': 'marketing',
            'subject': 'Hello {{ first_name }}!',
            'html_content': '<p>Hello {{ first_name }},</p><p>This is a test.</p><p><a href="{{ unsubscribe_url }}">Unsubscribe</a></p>',
            'text_content': 'Hello {{ first_name }},\n\nThis is a test.\n\nUnsubscribe: {{ unsubscribe_url }}',
            'from_name': 'Test Sender',
            'from_email': 'sender@example.com'
        }
        
        response = self.client.post('/api/contacts/email-templates/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Test Template')
        self.assertIn('preview_html', response.data)
        
        # Verify template was created
        template = EmailTemplate.objects.get(id=response.data['id'])
        self.assertEqual(template.group, self.group)
        self.assertEqual(template.created_by, self.user)
    
    def test_create_email_campaign(self):
        """Test creating an email campaign."""
        # First create a template
        template = EmailTemplate.objects.create(
            group=self.group,
            name='Campaign Template',
            template_type='marketing',
            subject='Campaign Test',
            html_content='<p>Test content</p><p><a href="{{ unsubscribe_url }}">Unsubscribe</a></p>',
            text_content='Test content\n\nUnsubscribe: {{ unsubscribe_url }}',
            from_name='Sender',
            from_email='sender@example.com',
            created_by=self.user,
            is_active=True,
            is_tested=True
        )
        
        # Create campaign
        data = {
            'name': 'Test Campaign',
            'description': 'A test email campaign',
            'template_id': str(template.id),
            'contact_list_ids': [str(self.contact_list.id)],
            'sending_strategy': 'immediate',
            'track_opens': True,
            'track_clicks': True
        }
        
        response = self.client.post('/api/contacts/email-campaigns/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Test Campaign')
        self.assertEqual(response.data['recipient_count'], 2)
        self.assertTrue(response.data['can_send'])
    
    def test_list_email_templates(self):
        """Test listing email templates."""
        # Create some templates
        EmailTemplate.objects.create(
            group=self.group,
            name='Template 1',
            template_type='marketing',
            subject='Subject 1',
            html_content='<p>Content 1</p>',
            text_content='Content 1',
            created_by=self.user
        )
        EmailTemplate.objects.create(
            group=self.group,
            name='Template 2',
            template_type='transactional',
            subject='Subject 2',
            html_content='<p>Content 2</p>',
            text_content='Content 2',
            created_by=self.user
        )
        
        response = self.client.get('/api/contacts/email-templates/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_email_template_preview(self):
        """Test template preview functionality."""
        template = EmailTemplate.objects.create(
            group=self.group,
            name='Preview Template',
            template_type='marketing',
            subject='Hello {{ first_name }}!',
            html_content='<p>Dear {{ first_name }} {{ last_name }},</p>',
            text_content='Dear {{ first_name }} {{ last_name }},',
            created_by=self.user
        )
        
        response = self.client.get(f'/api/contacts/email-templates/{template.id}/preview/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('preview_html', response.data)
        self.assertIn('preview_subject', response.data)
        self.assertIn('John', response.data['preview_html'])  # Default preview data
    
    def test_campaign_analytics(self):
        """Test campaign analytics endpoint."""
        # Create a sent campaign
        template = EmailTemplate.objects.create(
            group=self.group,
            name='Analytics Template',
            template_type='marketing',
            subject='Test',
            html_content='<p>Test</p>',
            text_content='Test',
            created_by=self.user
        )
        
        campaign = EmailCampaign.objects.create(
            group=self.group,
            name='Analytics Campaign',
            template=template,
            status='sent',
            total_recipients=100,
            emails_sent=100,
            emails_delivered=95,
            emails_opened=50,
            emails_clicked=20,
            emails_bounced=5,
            created_by=self.user
        )
        
        response = self.client.get(f'/api/contacts/email-campaigns/{campaign.id}/analytics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)
        self.assertEqual(response.data['summary']['open_rate'], 52.63)  # 50/95*100
        self.assertEqual(response.data['summary']['click_rate'], 21.05)  # 20/95*100