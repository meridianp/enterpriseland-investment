"""
Tests for contact management serializers.

Tests cover ContactSerializer, ContactActivitySerializer, ContactListSerializer,
and related serializers with validation and multi-tenant support.
"""

from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from accounts.models import Group, GroupMembership
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request

from .models import (
    Contact, ContactActivity, ContactList, ContactPartner,
    ContactStatus, ContactType, ActivityType, RelationshipType,
    EmailTemplate, EmailCampaign, EmailMessage
)
from .serializers import (
    ContactSerializer, ContactActivitySerializer,
    ContactListSerializer, ContactListDetailSerializer, ContactPartnerSerializer,
    ContactImportSerializer, ContactExportSerializer,
    EmailTemplateSerializer, EmailCampaignSerializer, EmailMessageSerializer
)
from ..assessments.models import DevelopmentPartner

User = get_user_model()


class BaseSerializerTestCase(TestCase):
    """Base test case with common setup for serializer tests."""
    
    def setUp(self):
        """Set up test data."""
        # Create groups
        self.group1 = Group.objects.create(name="Test Group 1")
        self.group2 = Group.objects.create(name="Test Group 2")
        
        # Create users
        self.user1 = User.objects.create_user(
            username="testuser1",
            email="user1@test.com",
            password="testpass123"
        )
        GroupMembership.objects.create(user=self.user1, group=self.group1)
        
        self.user2 = User.objects.create_user(
            username="testuser2",
            email="user2@test.com",
            password="testpass123"
        )
        GroupMembership.objects.create(user=self.user2, group=self.group2)
        
        # Create request factory
        self.factory = APIRequestFactory()
        
        # Create test data
        self.contact1 = Contact.objects.create(
            email="john.doe@example.com",
            first_name="John",
            last_name="Doe",
            contact_type=ContactType.INDIVIDUAL,
            status=ContactStatus.LEAD,
            phone_primary="+1234567890",
            city="New York",
            country="US",
            group=self.group1
        )
        
        self.partner = DevelopmentPartner.objects.create(
            company_name="Dev Partner Ltd",
            group=self.group1
        )
    
    def get_request(self, user=None):
        """Create a mock request with user."""
        request = self.factory.get('/')
        request.user = user or self.user1
        return Request(request)


class ContactSerializerTests(BaseSerializerTestCase):
    """Test cases for ContactSerializer."""
    
    def test_serialize_contact(self):
        """Test serializing a contact."""
        serializer = ContactSerializer(self.contact1)
        data = serializer.data
        
        self.assertEqual(data['email'], 'john.doe@example.com')
        self.assertEqual(data['first_name'], 'John')
        self.assertEqual(data['last_name'], 'Doe')
        self.assertEqual(data['full_name'], 'John Doe')
        self.assertEqual(data['display_name'], 'John Doe')
        self.assertEqual(data['contact_type'], ContactType.INDIVIDUAL)
        self.assertEqual(data['status'], ContactStatus.LEAD)
        self.assertIn('id', data)
        self.assertIn('created_at', data)
        self.assertIn('updated_at', data)
    
    def test_serialize_contact_with_activities(self):
        """Test serializing contact with activities."""
        # Create activities
        activity = ContactActivity.objects.create(
            contact=self.contact1,
            activity_type=ActivityType.EMAIL_SENT,
            subject="Test Email",
            actor=self.user1,
            group=self.group1
        )
        
        serializer = ContactDetailSerializer(self.contact1)
        data = serializer.data
        
        self.assertIn('recent_activities', data)
        self.assertEqual(len(data['recent_activities']), 1)
        self.assertEqual(data['recent_activities'][0]['subject'], 'Test Email')
    
    def test_deserialize_contact(self):
        """Test deserializing contact data."""
        data = {
            'email': 'new.contact@example.com',
            'first_name': 'New',
            'last_name': 'Contact',
            'contact_type': ContactType.INDIVIDUAL,
            'status': ContactStatus.LEAD,
            'phone_primary': '+9876543210'
        }
        
        request = self.get_request()
        serializer = ContactSerializer(data=data, context={'request': request})
        
        self.assertTrue(serializer.is_valid())
        contact = serializer.save()
        
        self.assertEqual(contact.email, 'new.contact@example.com')
        self.assertEqual(contact.full_name, 'New Contact')
        self.assertEqual(contact.group, self.group1)
    
    def test_contact_validation_duplicate_email(self):
        """Test validation prevents duplicate emails in same group."""
        data = {
            'email': 'john.doe@example.com',  # Already exists
            'first_name': 'John',
            'contact_type': ContactType.INDIVIDUAL,
            'status': ContactStatus.LEAD
        }
        
        request = self.get_request()
        serializer = ContactSerializer(data=data, context={'request': request})
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)
    
    def test_contact_validation_invalid_country(self):
        """Test validation for invalid country code."""
        data = {
            'email': 'test@example.com',
            'contact_type': ContactType.INDIVIDUAL,
            'country': 'XX'  # Invalid code
        }
        
        request = self.get_request()
        serializer = ContactSerializer(data=data, context={'request': request})
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('country', serializer.errors)
    
    def test_contact_score_calculation_on_save(self):
        """Test lead score is calculated on save."""
        data = {
            'email': 'scored@example.com',
            'first_name': 'Scored',
            'contact_type': ContactType.INDIVIDUAL,
            'status': ContactStatus.QUALIFIED,
            'phone_primary': '+1234567890',
            'website': 'https://example.com'
        }
        
        request = self.get_request()
        serializer = ContactSerializer(data=data, context={'request': request})
        
        self.assertTrue(serializer.is_valid())
        contact = serializer.save()
        
        self.assertGreater(contact.current_score, 0)
        expected_score = contact.calculate_score()
        self.assertEqual(contact.current_score, expected_score)
    
    def test_update_contact(self):
        """Test updating existing contact."""
        data = {
            'email': 'john.doe@example.com',
            'first_name': 'John',
            'last_name': 'Updated',
            'contact_type': ContactType.INDIVIDUAL,
            'status': ContactStatus.QUALIFIED
        }
        
        request = self.get_request()
        serializer = ContactSerializer(
            self.contact1, 
            data=data, 
            context={'request': request}
        )
        
        self.assertTrue(serializer.is_valid())
        contact = serializer.save()
        
        self.assertEqual(contact.last_name, 'Updated')
        self.assertEqual(contact.status, ContactStatus.QUALIFIED)
    
    def test_contact_with_partner_relationships(self):
        """Test serializing contact with partner relationships."""
        # Create relationship
        ContactPartner.objects.create(
            contact=self.contact1,
            partner=self.partner,
            relationship_type=RelationshipType.EMPLOYEE,
            is_primary=True,
            group=self.group1
        )
        
        serializer = ContactDetailSerializer(self.contact1)
        data = serializer.data
        
        self.assertIn('partner_count', data)
        self.assertEqual(data['partner_count'], 1)


class ContactActivitySerializerTests(BaseSerializerTestCase):
    """Test cases for ContactActivitySerializer."""
    
    def test_serialize_activity(self):
        """Test serializing an activity."""
        activity = ContactActivity.objects.create(
            contact=self.contact1,
            activity_type=ActivityType.CALL_MADE,
            subject="Sales Call",
            description="Initial discussion",
            outcome="interested",
            actor=self.user1,
            group=self.group1
        )
        
        serializer = ContactActivitySerializer(activity)
        data = serializer.data
        
        self.assertEqual(data['activity_type'], ActivityType.CALL_MADE)
        self.assertEqual(data['subject'], 'Sales Call')
        self.assertEqual(data['outcome'], 'interested')
        self.assertEqual(data['actor']['id'], str(self.user1.id))
        self.assertEqual(data['actor']['username'], 'testuser1')
    
    def test_deserialize_activity(self):
        """Test deserializing activity data."""
        data = {
            'activity_type': ActivityType.MEETING_SCHEDULED,
            'subject': 'Product Demo',
            'description': 'Demonstrated features',
            'follow_up_required': True,
            'follow_up_date': (timezone.now() + timedelta(days=3)).isoformat()
        }
        
        request = self.get_request()
        serializer = ContactActivitySerializer(
            data=data,
            context={
                'request': request,
                'contact': self.contact1
            }
        )
        
        self.assertTrue(serializer.is_valid())
        activity = serializer.save()
        
        self.assertEqual(activity.contact, self.contact1)
        self.assertEqual(activity.actor, self.user1)
        self.assertEqual(activity.group, self.group1)
        self.assertTrue(activity.follow_up_required)
    
    def test_activity_with_metadata(self):
        """Test activity with JSON metadata."""
        metadata = {
            'call_duration': '45 minutes',
            'attendees': ['John Doe', 'Jane Smith'],
            'next_steps': ['Send proposal', 'Schedule follow-up']
        }
        
        activity = ContactActivity.objects.create(
            contact=self.contact1,
            activity_type=ActivityType.MEETING_SCHEDULED,
            subject="Strategy Meeting",
            metadata=metadata,
            actor=self.user1,
            group=self.group1
        )
        
        serializer = ContactActivitySerializer(activity)
        data = serializer.data
        
        self.assertIn('metadata', data)
        self.assertEqual(data['metadata']['call_duration'], '45 minutes')
        self.assertEqual(len(data['metadata']['attendees']), 2)
    
    def test_activity_validation_future_date(self):
        """Test validation allows future follow-up dates."""
        data = {
            'activity_type': ActivityType.CALL,
            'subject': 'Follow-up Call',
            'follow_up_required': True,
            'follow_up_date': (timezone.now() + timedelta(days=30)).isoformat()
        }
        
        request = self.get_request()
        serializer = ContactActivitySerializer(
            data=data,
            context={'request': request, 'contact': self.contact1}
        )
        
        self.assertTrue(serializer.is_valid())


class ContactListSerializerTests(BaseSerializerTestCase):
    """Test cases for ContactListSerializer."""
    
    def test_serialize_static_list(self):
        """Test serializing a static contact list."""
        contact_list = ContactList.objects.create(
            name="VIP Contacts",
            description="High-value contacts",
            is_dynamic=False,
            tags=['important', 'vip'],
            created_by=self.user1,
            group=self.group1
        )
        contact_list.contacts.add(self.contact1)
        
        serializer = ContactListSerializer(contact_list)
        data = serializer.data
        
        self.assertEqual(data['name'], 'VIP Contacts')
        self.assertEqual(data['description'], 'High-value contacts')
        self.assertFalse(data['is_dynamic'])
        self.assertEqual(data['contact_count'], 1)
        self.assertEqual(len(data['tags']), 2)
        self.assertIn('vip', data['tags'])
    
    def test_serialize_dynamic_list(self):
        """Test serializing a dynamic contact list."""
        contact_list = ContactList.objects.create(
            name="Active Leads",
            is_dynamic=True,
            filter_criteria={
                'status': ContactStatus.LEAD,
                'contact_type': ContactType.INDIVIDUAL
            },
            created_by=self.user1,
            group=self.group1
        )
        
        serializer = ContactListSerializer(contact_list)
        data = serializer.data
        
        self.assertTrue(data['is_dynamic'])
        self.assertIn('filter_criteria', data)
        self.assertEqual(data['filter_criteria']['status'], ContactStatus.LEAD)
    
    def test_serialize_list_detail(self):
        """Test detailed list serialization with contacts."""
        contact_list = ContactList.objects.create(
            name="Test List",
            created_by=self.user1,
            group=self.group1
        )
        contact_list.contacts.add(self.contact1)
        
        serializer = ContactListDetailSerializer(contact_list)
        data = serializer.data
        
        self.assertIn('contacts', data)
        self.assertEqual(len(data['contacts']), 1)
        self.assertEqual(data['contacts'][0]['email'], 'john.doe@example.com')
    
    def test_deserialize_list(self):
        """Test deserializing list data."""
        data = {
            'name': 'New List',
            'description': 'Test description',
            'is_dynamic': False,
            'tags': ['test', 'new'],
            'is_public': True
        }
        
        request = self.get_request()
        serializer = ContactListSerializer(data=data, context={'request': request})
        
        self.assertTrue(serializer.is_valid())
        contact_list = serializer.save()
        
        self.assertEqual(contact_list.name, 'New List')
        self.assertEqual(contact_list.created_by, self.user1)
        self.assertEqual(contact_list.group, self.group1)
        self.assertTrue(contact_list.is_public)
    
    def test_list_name_uniqueness(self):
        """Test list name must be unique within group."""
        # Create existing list
        ContactList.objects.create(
            name="Existing List",
            created_by=self.user1,
            group=self.group1
        )
        
        data = {
            'name': 'Existing List',  # Duplicate
            'is_dynamic': False
        }
        
        request = self.get_request()
        serializer = ContactListSerializer(data=data, context={'request': request})
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)


class ContactPartnerSerializerTests(BaseSerializerTestCase):
    """Test cases for ContactPartnerSerializer."""
    
    def test_serialize_relationship(self):
        """Test serializing contact-partner relationship."""
        relationship = ContactPartner.objects.create(
            contact=self.contact1,
            partner=self.partner,
            relationship_type=RelationshipType.EMPLOYEE,
            is_primary=True,
            start_date=timezone.now().date(),
            notes="Key technical contact",
            group=self.group1
        )
        
        serializer = ContactPartnerSerializer(relationship)
        data = serializer.data
        
        self.assertEqual(data['relationship_type'], RelationshipType.EMPLOYEE)
        self.assertTrue(data['is_primary'])
        self.assertIn('start_date', data)
        self.assertEqual(data['notes'], 'Key technical contact')
        
        # Check nested objects
        self.assertEqual(data['contact']['email'], 'john.doe@example.com')
        self.assertEqual(data['partner']['company_name'], 'Dev Partner Ltd')
    
    def test_deserialize_relationship(self):
        """Test deserializing relationship data."""
        data = {
            'contact': self.contact1.id,
            'partner': self.partner.id,
            'relationship_type': RelationshipType.ADVISOR,
            'start_date': timezone.now().date().isoformat(),
            'notes': 'Financial advisor'
        }
        
        request = self.get_request()
        serializer = ContactPartnerSerializer(data=data, context={'request': request})
        
        self.assertTrue(serializer.is_valid())
        relationship = serializer.save()
        
        self.assertEqual(relationship.contact, self.contact1)
        self.assertEqual(relationship.partner, self.partner)
        self.assertEqual(relationship.relationship_type, RelationshipType.ADVISOR)
        self.assertEqual(relationship.group, self.group1)


class ContactImportSerializerTests(BaseSerializerTestCase):
    """Test cases for ContactImportSerializer."""
    
    def test_import_single_contact(self):
        """Test importing a single contact."""
        data = {
            'contacts': [
                {
                    'email': 'import@example.com',
                    'first_name': 'Import',
                    'last_name': 'Test',
                    'contact_type': ContactType.INDIVIDUAL,
                    'status': ContactStatus.LEAD
                }
            ]
        }
        
        request = self.get_request()
        serializer = ContactImportSerializer(data=data, context={'request': request})
        
        self.assertTrue(serializer.is_valid())
        result = serializer.save()
        
        self.assertEqual(result['created'], 1)
        self.assertEqual(result['updated'], 0)
        self.assertEqual(result['skipped'], 0)
        
        # Verify contact was created
        contact = Contact.objects.get(email='import@example.com')
        self.assertEqual(contact.first_name, 'Import')
        self.assertEqual(contact.group, self.group1)
    
    def test_import_update_existing(self):
        """Test importing updates existing contacts."""
        data = {
            'contacts': [
                {
                    'email': 'john.doe@example.com',  # Existing
                    'first_name': 'John',
                    'last_name': 'Updated',
                    'phone_primary': '+9999999999'
                }
            ],
            'update_existing': True
        }
        
        request = self.get_request()
        serializer = ContactImportSerializer(data=data, context={'request': request})
        
        self.assertTrue(serializer.is_valid())
        result = serializer.save()
        
        self.assertEqual(result['created'], 0)
        self.assertEqual(result['updated'], 1)
        self.assertEqual(result['skipped'], 0)
        
        # Verify contact was updated
        self.contact1.refresh_from_db()
        self.assertEqual(self.contact1.last_name, 'Updated')
        self.assertEqual(self.contact1.phone_primary, '+9999999999')
    
    def test_import_skip_duplicates(self):
        """Test importing skips duplicates when update_existing is False."""
        data = {
            'contacts': [
                {
                    'email': 'john.doe@example.com',  # Existing
                    'first_name': 'John',
                    'last_name': 'Skipped'
                }
            ],
            'update_existing': False
        }
        
        request = self.get_request()
        serializer = ContactImportSerializer(data=data, context={'request': request})
        
        self.assertTrue(serializer.is_valid())
        result = serializer.save()
        
        self.assertEqual(result['created'], 0)
        self.assertEqual(result['updated'], 0)
        self.assertEqual(result['skipped'], 1)
        self.assertIn('john.doe@example.com', result['skipped_emails'])
        
        # Verify contact was not updated
        self.contact1.refresh_from_db()
        self.assertEqual(self.contact1.last_name, 'Doe')  # Unchanged
    
    def test_import_validation_invalid_data(self):
        """Test import validation catches invalid data."""
        data = {
            'contacts': [
                {
                    'email': 'invalid-email',  # Invalid email
                    'contact_type': 'INVALID_TYPE'  # Invalid type
                }
            ]
        }
        
        request = self.get_request()
        serializer = ContactImportSerializer(data=data, context={'request': request})
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('contacts', serializer.errors)


class ContactExportSerializerTests(BaseSerializerTestCase):
    """Test cases for ContactExportSerializer."""
    
    def test_export_csv_format(self):
        """Test export serializer for CSV format."""
        data = {
            'format': 'csv',
            'fields': ['email', 'first_name', 'last_name']
        }
        
        serializer = ContactExportSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['format'], 'csv')
        self.assertEqual(len(serializer.validated_data['fields']), 3)
    
    def test_export_excel_format(self):
        """Test export serializer for Excel format."""
        data = {
            'format': 'excel',
            'list_id': str(self.contact1.id)
        }
        
        serializer = ContactExportSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['format'], 'excel')
        self.assertIn('list_id', serializer.validated_data)
    
    def test_export_invalid_format(self):
        """Test export validation for invalid format."""
        data = {
            'format': 'pdf'  # Not supported
        }
        
        serializer = ContactExportSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('format', serializer.errors)
    
    def test_export_default_fields(self):
        """Test export uses default fields when not specified."""
        data = {
            'format': 'csv'
        }
        
        serializer = ContactExportSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        # Fields should be None, handled by view
        self.assertIsNone(serializer.validated_data.get('fields'))


class EmailTemplateSerializerTests(BaseSerializerTestCase):
    """Test cases for EmailTemplateSerializer."""
    
    def test_serialize_template(self):
        """Test serializing email template."""
        template = EmailTemplate.objects.create(
            name="Welcome Email",
            template_type=EmailTemplate.TemplateType.MARKETING,
            subject="Welcome to {{ company_name }}",
            html_content="<h1>Hello {{ first_name }}</h1>",
            text_content="Hello {{ first_name }}",
            from_name="Test Team",
            from_email="hello@test.com",
            created_by=self.user1,
            group=self.group1
        )
        
        serializer = EmailTemplateSerializer(template)
        data = serializer.data
        
        self.assertEqual(data['name'], 'Welcome Email')
        self.assertEqual(data['template_type'], EmailTemplate.TemplateType.MARKETING)
        self.assertTrue(data['is_active'])
        self.assertEqual(data['times_used'], 0)
        self.assertIn('preview_html', data)
        self.assertIn('preview_text', data)
        self.assertIn('preview_subject', data)
    
    def test_deserialize_template(self):
        """Test deserializing template data."""
        data = {
            'name': 'New Template',
            'template_type': EmailTemplate.TemplateType.TRANSACTIONAL,
            'subject': 'Order Confirmation',
            'html_content': '<p>Your order is confirmed</p>',
            'text_content': 'Your order is confirmed',
            'from_email': 'orders@test.com'
        }
        
        request = self.get_request()
        serializer = EmailTemplateSerializer(data=data, context={'request': request})
        
        self.assertTrue(serializer.is_valid())
        template = serializer.save()
        
        self.assertEqual(template.name, 'New Template')
        self.assertEqual(template.created_by, self.user1)
        self.assertEqual(template.group, self.group1)


class EmailCampaignSerializerTests(BaseSerializerTestCase):
    """Test cases for EmailCampaignSerializer."""
    
    def setUp(self):
        """Set up test data."""
        super().setUp()
        
        self.template = EmailTemplate.objects.create(
            name="Campaign Template",
            subject="Test Subject",
            html_content="<p>Test</p>",
            text_content="Test",
            created_by=self.user1,
            group=self.group1
        )
        
        self.contact_list = ContactList.objects.create(
            name="Campaign List",
            created_by=self.user1,
            group=self.group1
        )
        self.contact_list.contacts.add(self.contact1)
    
    def test_serialize_campaign(self):
        """Test serializing email campaign."""
        campaign = EmailCampaign.objects.create(
            name="Q1 Campaign",
            description="Quarterly update",
            template=self.template,
            status=EmailCampaign.CampaignStatus.DRAFT,
            emails_sent=100,
            emails_delivered=95,
            emails_opened=40,
            emails_clicked=10,
            emails_bounced=5,
            created_by=self.user1,
            group=self.group1
        )
        campaign.contact_lists.add(self.contact_list)
        
        serializer = EmailCampaignSerializer(campaign)
        data = serializer.data
        
        self.assertEqual(data['name'], 'Q1 Campaign')
        self.assertEqual(data['status'], EmailCampaign.CampaignStatus.DRAFT)
        self.assertEqual(data['open_rate'], 42.11)  # 40/95 * 100
        self.assertEqual(data['click_rate'], 10.53)  # 10/95 * 100
        self.assertEqual(data['bounce_rate'], 5.0)   # 5/100 * 100
        self.assertEqual(data['recipient_count'], 1)
    
    def test_deserialize_campaign(self):
        """Test deserializing campaign data."""
        data = {
            'name': 'New Campaign',
            'template': self.template.id,
            'contact_lists': [self.contact_list.id],
            'sending_strategy': EmailCampaign.SendingStrategy.IMMEDIATE
        }
        
        request = self.get_request()
        serializer = EmailCampaignSerializer(data=data, context={'request': request})
        
        self.assertTrue(serializer.is_valid())
        campaign = serializer.save()
        
        self.assertEqual(campaign.name, 'New Campaign')
        self.assertEqual(campaign.created_by, self.user1)
        self.assertEqual(campaign.group, self.group1)
        self.assertEqual(campaign.contact_lists.count(), 1)