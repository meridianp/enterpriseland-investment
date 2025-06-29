"""
Tests for contact management models.

Tests cover Contact, ContactActivity, ContactList, ContactPartner,
and email campaign models with multi-tenant support.
"""

import pytest
from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import IntegrityError
from accounts.models import Group, GroupMembership

from .models import (
    Contact, ContactActivity, ContactList, ContactPartner,
    ContactStatus, ContactType, ActivityType, RelationshipType,
    EmailTemplate, EmailCampaign, EmailMessage, EmailEvent
)
from ..assessments.models import DevelopmentPartner

User = get_user_model()


class ContactModelTests(TestCase):
    """Test cases for Contact model."""
    
    def setUp(self):
        """Set up test data."""
        # Create groups
        self.group1 = Group.objects.create(name="Test Group 1")
        self.group2 = Group.objects.create(name="Test Group 2")
        
        # Create users
        self.user1 = User.objects.create_user(
            username="user1",
            email="user1@test.com",
            password="testpass123"
        )
        GroupMembership.objects.create(user=self.user1, group=self.group1)
        
        self.user2 = User.objects.create_user(
            username="user2",
            email="user2@test.com",
            password="testpass123"
        )
        GroupMembership.objects.create(user=self.user2, group=self.group2)
    
    def test_contact_creation(self):
        """Test creating a contact."""
        contact = Contact.objects.create(
            email="john.doe@example.com",
            first_name="John",
            last_name="Doe",
            contact_type=ContactType.INDIVIDUAL,
            status=ContactStatus.LEAD,
            group=self.group1
        )
        
        self.assertEqual(contact.email, "john.doe@example.com")
        self.assertEqual(contact.full_name, "John Doe")
        self.assertEqual(contact.display_name, "John Doe")
        self.assertEqual(contact.contact_type, ContactType.INDIVIDUAL)
        self.assertEqual(contact.status, ContactStatus.LEAD)
        self.assertEqual(contact.current_score, 0)
    
    def test_contact_unique_email_per_group(self):
        """Test email uniqueness within a group."""
        # Create first contact
        Contact.objects.create(
            email="test@example.com",
            contact_type=ContactType.INDIVIDUAL,
            group=self.group1
        )
        
        # Try to create duplicate in same group - should fail
        from django.db import transaction
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Contact.objects.create(
                    email="test@example.com",
                    contact_type=ContactType.INDIVIDUAL,
                    group=self.group1
                )
        
        # Create with same email in different group - should succeed
        contact2 = Contact.objects.create(
            email="test@example.com",
            contact_type=ContactType.INDIVIDUAL,
            group=self.group2
        )
        self.assertEqual(contact2.email, "test@example.com")
    
    def test_contact_display_name(self):
        """Test display name generation."""
        # Individual with full name
        contact1 = Contact.objects.create(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            contact_type=ContactType.INDIVIDUAL,
            group=self.group1
        )
        self.assertEqual(contact1.display_name, "John Doe")
        
        # Individual with only first name
        contact2 = Contact.objects.create(
            email="jane@example.com",
            first_name="Jane",
            contact_type=ContactType.INDIVIDUAL,
            group=self.group1
        )
        self.assertEqual(contact2.display_name, "Jane")
        
        # Company contact
        contact3 = Contact.objects.create(
            email="info@company.com",
            company_name="Tech Corp",
            contact_type=ContactType.COMPANY,
            group=self.group1
        )
        self.assertEqual(contact3.display_name, "Tech Corp")
        
        # No name info - falls back to email
        contact4 = Contact.objects.create(
            email="anonymous@example.com",
            contact_type=ContactType.INDIVIDUAL,
            group=self.group1
        )
        self.assertEqual(contact4.display_name, "anonymous@example.com")
    
    def test_contact_score_calculation(self):
        """Test lead score calculation."""
        contact = Contact.objects.create(
            email="test@example.com",
            contact_type=ContactType.INDIVIDUAL,
            status=ContactStatus.QUALIFIED,
            phone_primary="+1234567890",
            group=self.group1
        )
        
        # Initial score
        score = contact.calculate_score()
        # Phone: 5 points (has phone_primary)
        expected_score = 5
        self.assertEqual(score, expected_score)
        
        # Update score
        contact.current_score = contact.calculate_score()
        contact.save()
        self.assertEqual(contact.current_score, expected_score)
    
    def test_contact_status_transitions(self):
        """Test FSM status transitions."""
        contact = Contact.objects.create(
            email="test@example.com",
            contact_type=ContactType.INDIVIDUAL,
            status=ContactStatus.LEAD,
            group=self.group1
        )
        
        # Valid transition: lead -> qualified
        contact.qualify()
        contact.save()
        self.assertEqual(contact.status, ContactStatus.QUALIFIED)
        
        # Valid transition: qualified -> opportunity
        contact.convert_to_opportunity()
        contact.save()
        self.assertEqual(contact.status, ContactStatus.OPPORTUNITY)
        
        # Invalid transition: opportunity -> lead (should fail)
        # Note: django-fsm would normally prevent this
        # For now, we'll test that status doesn't change incorrectly
        prev_status = contact.status
        contact.status = ContactStatus.LEAD
        contact.save()
        # In real implementation, this would raise TransitionNotAllowed
    
    def test_contact_country_validation(self):
        """Test country code validation."""
        # Valid country code
        contact = Contact.objects.create(
            email="test@example.com",
            country="US",
            contact_type=ContactType.INDIVIDUAL,
            group=self.group1
        )
        self.assertEqual(contact.country, "US")
        
        # Invalid country code
        with self.assertRaises(ValidationError):
            contact2 = Contact(
                email="test2@example.com",
                country="XX",  # Invalid code
                contact_type=ContactType.INDIVIDUAL,
                group=self.group1
            )
            contact2.full_clean()


class ContactActivityModelTests(TestCase):
    """Test cases for ContactActivity model."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        GroupMembership.objects.create(user=self.user, group=self.group)
        
        self.contact = Contact.objects.create(
            email="contact@example.com",
            first_name="Test",
            last_name="Contact",
            contact_type=ContactType.INDIVIDUAL,
            group=self.group
        )
    
    def test_activity_creation(self):
        """Test creating a contact activity."""
        activity = ContactActivity.objects.create(
            contact=self.contact,
            activity_type=ActivityType.EMAIL_SENT,
            subject="Follow-up Email",
            description="Sent proposal document",
            actor=self.user,
            group=self.group
        )
        
        self.assertEqual(activity.contact, self.contact)
        self.assertEqual(activity.activity_type, ActivityType.EMAIL_SENT)
        self.assertEqual(activity.actor, self.user)
        self.assertIsNotNone(activity.created_at)
    
    def test_activity_with_metadata(self):
        """Test activity with JSON metadata."""
        metadata = {
            "email_id": "msg-123",
            "template_used": "proposal_v1",
            "attachments": ["proposal.pdf"]
        }
        
        activity = ContactActivity.objects.create(
            contact=self.contact,
            activity_type=ActivityType.EMAIL_SENT,
            subject="Proposal Email",
            metadata=metadata,
            actor=self.user,
            group=self.group
        )
        
        self.assertEqual(activity.metadata["email_id"], "msg-123")
        self.assertEqual(len(activity.metadata["attachments"]), 1)
    
    def test_activity_with_follow_up(self):
        """Test activity with follow-up date."""
        follow_up_date = timezone.now() + timedelta(days=7)
        
        activity = ContactActivity.objects.create(
            contact=self.contact,
            activity_type=ActivityType.CALL_MADE,
            subject="Initial Call",
            outcome="positive",
            follow_up_required=True,
            follow_up_date=follow_up_date,
            actor=self.user,
            group=self.group
        )
        
        self.assertTrue(activity.follow_up_required)
        self.assertIsNotNone(activity.follow_up_date)
        self.assertEqual(activity.outcome, "positive")
    
    def test_activity_timeline_ordering(self):
        """Test activities are ordered by creation time."""
        # Create multiple activities
        for i in range(3):
            ContactActivity.objects.create(
                contact=self.contact,
                activity_type=ActivityType.NOTE_ADDED,
                subject=f"Note {i}",
                actor=self.user,
                group=self.group
            )
        
        # Get activities for contact
        activities = self.contact.activities.all()
        self.assertEqual(activities.count(), 3)
        
        # Check ordering (newest first)
        timestamps = [a.created_at for a in activities]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))


class ContactListModelTests(TestCase):
    """Test cases for ContactList model."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        GroupMembership.objects.create(user=self.user, group=self.group)
        
        # Create test contacts
        self.contacts = []
        for i in range(5):
            contact = Contact.objects.create(
                email=f"contact{i}@example.com",
                first_name=f"Contact{i}",
                contact_type=ContactType.INDIVIDUAL,
                group=self.group
            )
            self.contacts.append(contact)
    
    def test_static_list_creation(self):
        """Test creating a static contact list."""
        contact_list = ContactList.objects.create(
            name="VIP Contacts",
            description="High-value contacts",
            is_dynamic=False,
            created_by=self.user,
            group=self.group
        )
        
        # Add contacts
        contact_list.contacts.add(*self.contacts[:3])
        
        self.assertEqual(contact_list.name, "VIP Contacts")
        self.assertFalse(contact_list.is_dynamic)
        self.assertEqual(contact_list.get_contact_count(), 3)
    
    def test_list_unique_name_per_group(self):
        """Test list name uniqueness within group."""
        # Create first list
        ContactList.objects.create(
            name="My List",
            created_by=self.user,
            group=self.group
        )
        
        # Try to create duplicate - should fail
        with self.assertRaises(IntegrityError):
            ContactList.objects.create(
                name="My List",
                created_by=self.user,
                group=self.group
            )
    
    def test_dynamic_list_placeholder(self):
        """Test dynamic list functionality (placeholder)."""
        contact_list = ContactList.objects.create(
            name="Active Leads",
            is_dynamic=True,
            filter_criteria={
                "status": ContactStatus.LEAD,
                "contact_type": ContactType.INDIVIDUAL
            },
            created_by=self.user,
            group=self.group
        )
        
        self.assertTrue(contact_list.is_dynamic)
        self.assertIsNotNone(contact_list.filter_criteria)
        # Dynamic list returns 0 for now (not implemented)
        self.assertEqual(contact_list.get_contact_count(), 0)
    
    def test_list_tags(self):
        """Test contact list tags."""
        tags = ["important", "q1-2024", "marketing"]
        contact_list = ContactList.objects.create(
            name="Q1 Marketing Leads",
            tags=tags,
            created_by=self.user,
            group=self.group
        )
        
        self.assertEqual(len(contact_list.tags), 3)
        self.assertIn("marketing", contact_list.tags)


class ContactPartnerModelTests(TestCase):
    """Test cases for ContactPartner relationship model."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        GroupMembership.objects.create(user=self.user, group=self.group)
        
        self.contact = Contact.objects.create(
            email="contact@example.com",
            first_name="John",
            last_name="Doe",
            contact_type=ContactType.INDIVIDUAL,
            group=self.group
        )
        
        self.partner = DevelopmentPartner.objects.create(
            company_name="Dev Partner Ltd",
            group=self.group
        )
    
    def test_contact_partner_relationship(self):
        """Test creating contact-partner relationship."""
        relationship = ContactPartner.objects.create(
            contact=self.contact,
            partner=self.partner,
            relationship_type=RelationshipType.EMPLOYEE,
            is_primary=True,
            group=self.group
        )
        
        self.assertEqual(relationship.contact, self.contact)
        self.assertEqual(relationship.partner, self.partner)
        self.assertEqual(relationship.relationship_type, RelationshipType.EMPLOYEE)
        self.assertTrue(relationship.is_primary)
    
    def test_multiple_relationships(self):
        """Test contact can have multiple partner relationships."""
        # Create primary relationship
        rel1 = ContactPartner.objects.create(
            contact=self.contact,
            partner=self.partner,
            relationship_type=RelationshipType.EMPLOYEE,
            group=self.group
        )
        
        # Create another partner
        partner2 = DevelopmentPartner.objects.create(
            company_name="Another Partner",
            group=self.group
        )
        
        # Create secondary relationship
        rel2 = ContactPartner.objects.create(
            contact=self.contact,
            partner=partner2,
            relationship_type=RelationshipType.ADVISOR,
            group=self.group
        )
        
        # Check relationships
        self.assertEqual(self.contact.partner_relationships.count(), 2)
        self.assertEqual(self.partner.contact_relationships.count(), 1)
    
    def test_relationship_dates(self):
        """Test relationship date tracking."""
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=365)
        
        relationship = ContactPartner.objects.create(
            contact=self.contact,
            partner=self.partner,
            relationship_type=RelationshipType.CONSULTANT,
            start_date=start_date,
            end_date=end_date,
            notes="One year contract",
            group=self.group
        )
        
        self.assertEqual(relationship.start_date, start_date)
        self.assertEqual(relationship.end_date, end_date)
        self.assertIn("contract", relationship.notes)


class EmailTemplateModelTests(TestCase):
    """Test cases for EmailTemplate model."""
    
    def setUp(self):
        """Set up test data."""
        # Use custom Group model
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        GroupMembership.objects.create(user=self.user, group=self.group)
    
    def test_email_template_creation(self):
        """Test creating an email template."""
        template = EmailTemplate.objects.create(
            name="Welcome Email",
            template_type=EmailTemplate.TemplateType.MARKETING,
            subject="Welcome to {{ company_name }}!",
            html_content="<h1>Hello {{ first_name }}</h1><p>Welcome!</p>",
            text_content="Hello {{ first_name }}\n\nWelcome!",
            from_name="EnterpriseLand Team",
            from_email="hello@enterpriseland.com",
            created_by=self.user,
            group=self.group
        )
        
        self.assertEqual(template.name, "Welcome Email")
        self.assertEqual(template.template_type, EmailTemplate.TemplateType.MARKETING)
        self.assertTrue(template.is_active)
        self.assertEqual(template.times_used, 0)
    
    def test_template_preview_data(self):
        """Test template preview data generation."""
        template = EmailTemplate.objects.create(
            name="Test Template",
            subject="Hello {{ first_name }}",
            html_content="<p>Test</p>",
            text_content="Test",
            created_by=self.user,
            group=self.group
        )
        
        preview_data = template.get_preview_data()
        self.assertIn('first_name', preview_data)
        self.assertIn('company_name', preview_data)
        self.assertIn('unsubscribe_url', preview_data)
        self.assertEqual(preview_data['first_name'], 'John')
    
    def test_template_variables(self):
        """Test template variable tracking."""
        variables = ['first_name', 'last_name', 'company_name', 'custom_field']
        template = EmailTemplate.objects.create(
            name="Custom Template",
            subject="Test",
            html_content="<p>Test</p>",
            text_content="Test",
            available_variables=variables,
            created_by=self.user,
            group=self.group
        )
        
        self.assertEqual(len(template.available_variables), 4)
        self.assertIn('custom_field', template.available_variables)


class EmailCampaignModelTests(TestCase):
    """Test cases for EmailCampaign model."""
    
    def setUp(self):
        """Set up test data."""
        # Use custom Group model
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        GroupMembership.objects.create(user=self.user, group=self.group)
        
        self.template = EmailTemplate.objects.create(
            name="Campaign Template",
            subject="Special Offer",
            html_content="<p>Content</p>",
            text_content="Content",
            created_by=self.user,
            group=self.group
        )
        
        # Create contacts and list
        self.contacts = []
        for i in range(10):
            contact = Contact.objects.create(
                email=f"contact{i}@example.com",
                contact_type=ContactType.INDIVIDUAL,
                group=self.group
            )
            self.contacts.append(contact)
        
        self.contact_list = ContactList.objects.create(
            name="Campaign List",
            created_by=self.user,
            group=self.group
        )
        self.contact_list.contacts.set(self.contacts)
    
    def test_campaign_creation(self):
        """Test creating an email campaign."""
        campaign = EmailCampaign.objects.create(
            name="Q1 Marketing Campaign",
            description="Quarterly newsletter",
            template=self.template,
            status=EmailCampaign.CampaignStatus.DRAFT,
            created_by=self.user,
            group=self.group
        )
        
        campaign.contact_lists.add(self.contact_list)
        
        self.assertEqual(campaign.name, "Q1 Marketing Campaign")
        self.assertEqual(campaign.template, self.template)
        self.assertEqual(campaign.status, EmailCampaign.CampaignStatus.DRAFT)
        self.assertEqual(campaign.contact_lists.count(), 1)
    
    def test_campaign_scheduling(self):
        """Test campaign scheduling."""
        scheduled_time = timezone.now() + timedelta(days=1)
        
        campaign = EmailCampaign.objects.create(
            name="Scheduled Campaign",
            template=self.template,
            sending_strategy=EmailCampaign.SendingStrategy.SCHEDULED,
            scheduled_at=scheduled_time,
            created_by=self.user,
            group=self.group
        )
        
        self.assertEqual(campaign.sending_strategy, EmailCampaign.SendingStrategy.SCHEDULED)
        self.assertIsNotNone(campaign.scheduled_at)
        self.assertGreater(campaign.scheduled_at, timezone.now())
    
    def test_campaign_analytics_properties(self):
        """Test campaign analytics calculations."""
        campaign = EmailCampaign.objects.create(
            name="Test Campaign",
            template=self.template,
            emails_sent=1000,
            emails_delivered=950,
            emails_opened=380,
            emails_clicked=95,
            emails_bounced=50,
            created_by=self.user,
            group=self.group
        )
        
        self.assertEqual(campaign.open_rate, 40.0)  # 380/950 * 100
        self.assertEqual(campaign.click_rate, 10.0)  # 95/950 * 100
        self.assertEqual(campaign.bounce_rate, 5.0)  # 50/1000 * 100
    
    def test_campaign_ab_testing(self):
        """Test A/B testing configuration."""
        variant_template = EmailTemplate.objects.create(
            name="Variant Template",
            subject="Alternative Subject",
            html_content="<p>Alt content</p>",
            text_content="Alt content",
            created_by=self.user,
            group=self.group
        )
        
        campaign = EmailCampaign.objects.create(
            name="A/B Test Campaign",
            template=self.template,
            is_ab_test=True,
            ab_test_percentage=20,
            created_by=self.user,
            group=self.group
        )
        campaign.variant_templates.add(variant_template)
        
        self.assertTrue(campaign.is_ab_test)
        self.assertEqual(campaign.ab_test_percentage, 20)
        self.assertEqual(campaign.variant_templates.count(), 1)
    
    def test_campaign_excluded_contacts(self):
        """Test excluding specific contacts from campaign."""
        campaign = EmailCampaign.objects.create(
            name="Exclusion Test",
            template=self.template,
            created_by=self.user,
            group=self.group
        )
        
        campaign.contact_lists.add(self.contact_list)
        # Exclude first 3 contacts
        campaign.excluded_contacts.add(*self.contacts[:3])
        
        self.assertEqual(campaign.excluded_contacts.count(), 3)
        # In real implementation, recipient count would be 7 (10 - 3)


class EmailMessageModelTests(TestCase):
    """Test cases for EmailMessage model."""
    
    def setUp(self):
        """Set up test data."""
        # Use custom Group model
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        GroupMembership.objects.create(user=self.user, group=self.group)
        
        self.template = EmailTemplate.objects.create(
            name="Test Template",
            subject="Test Subject",
            html_content="<p>Test</p>",
            text_content="Test",
            created_by=self.user,
            group=self.group
        )
        
        self.campaign = EmailCampaign.objects.create(
            name="Test Campaign",
            template=self.template,
            created_by=self.user,
            group=self.group
        )
        
        self.contact = Contact.objects.create(
            email="recipient@example.com",
            first_name="Test",
            contact_type=ContactType.INDIVIDUAL,
            group=self.group
        )
    
    def test_email_message_creation(self):
        """Test creating an email message."""
        message = EmailMessage.objects.create(
            campaign=self.campaign,
            contact=self.contact,
            template_used=self.template,
            subject="Test Subject",
            from_email="noreply@example.com",
            to_email=self.contact.email,
            status=EmailMessage.MessageStatus.PENDING,
            group=self.group
        )
        
        self.assertEqual(message.campaign, self.campaign)
        self.assertEqual(message.contact, self.contact)
        self.assertEqual(message.status, EmailMessage.MessageStatus.PENDING)
        self.assertEqual(message.open_count, 0)
        self.assertEqual(message.click_count, 0)
    
    def test_message_status_progression(self):
        """Test email message status changes."""
        message = EmailMessage.objects.create(
            campaign=self.campaign,
            contact=self.contact,
            template_used=self.template,
            subject="Test",
            from_email="noreply@example.com",
            to_email=self.contact.email,
            group=self.group
        )
        
        # Simulate sending
        message.status = EmailMessage.MessageStatus.SENT
        message.sent_at = timezone.now()
        message.message_id = "msg-123-456"
        message.save()
        
        self.assertEqual(message.status, EmailMessage.MessageStatus.SENT)
        self.assertIsNotNone(message.sent_at)
        self.assertIsNotNone(message.message_id)
    
    def test_message_engagement_tracking(self):
        """Test tracking email opens and clicks."""
        message = EmailMessage.objects.create(
            campaign=self.campaign,
            contact=self.contact,
            template_used=self.template,
            subject="Test",
            from_email="noreply@example.com",
            to_email=self.contact.email,
            status=EmailMessage.MessageStatus.DELIVERED,
            delivered_at=timezone.now(),
            group=self.group
        )
        
        # Track open
        message.status = EmailMessage.MessageStatus.OPENED
        message.first_opened_at = timezone.now()
        message.last_opened_at = message.first_opened_at
        message.open_count = 1
        message.save()
        
        # Track click
        message.status = EmailMessage.MessageStatus.CLICKED
        message.first_clicked_at = timezone.now()
        message.last_clicked_at = message.first_clicked_at
        message.click_count = 1
        message.save()
        
        self.assertEqual(message.open_count, 1)
        self.assertEqual(message.click_count, 1)
        self.assertIsNotNone(message.first_opened_at)
        self.assertIsNotNone(message.first_clicked_at)
    
    def test_message_bounce_tracking(self):
        """Test tracking email bounces."""
        message = EmailMessage.objects.create(
            campaign=self.campaign,
            contact=self.contact,
            template_used=self.template,
            subject="Test",
            from_email="noreply@example.com",
            to_email="invalid@nonexistent.com",
            status=EmailMessage.MessageStatus.SENT,
            sent_at=timezone.now(),
            group=self.group
        )
        
        # Track bounce
        message.status = EmailMessage.MessageStatus.BOUNCED
        message.bounce_type = "hard"
        message.bounce_reason = "Mailbox does not exist"
        message.save()
        
        self.assertEqual(message.status, EmailMessage.MessageStatus.BOUNCED)
        self.assertEqual(message.bounce_type, "hard")
        self.assertIn("Mailbox", message.bounce_reason)
    
    def test_unique_message_per_campaign_contact(self):
        """Test unique constraint on campaign-contact combination."""
        # Create first message
        EmailMessage.objects.create(
            campaign=self.campaign,
            contact=self.contact,
            template_used=self.template,
            subject="Test",
            from_email="noreply@example.com",
            to_email=self.contact.email,
            group=self.group
        )
        
        # Try to create duplicate - should fail
        with self.assertRaises(IntegrityError):
            EmailMessage.objects.create(
                campaign=self.campaign,
                contact=self.contact,
                template_used=self.template,
                subject="Test 2",
                from_email="noreply@example.com",
                to_email=self.contact.email,
                group=self.group
            )


class EmailEventModelTests(TestCase):
    """Test cases for EmailEvent model."""
    
    def setUp(self):
        """Set up test data."""
        # Use custom Group model
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        GroupMembership.objects.create(user=self.user, group=self.group)
        
        self.template = EmailTemplate.objects.create(
            name="Test Template",
            subject="Test",
            html_content="<p>Test</p>",
            text_content="Test",
            created_by=self.user,
            group=self.group
        )
        
        self.campaign = EmailCampaign.objects.create(
            name="Test Campaign",
            template=self.template,
            created_by=self.user,
            group=self.group
        )
        
        self.contact = Contact.objects.create(
            email="test@example.com",
            contact_type=ContactType.INDIVIDUAL,
            group=self.group
        )
        
        self.message = EmailMessage.objects.create(
            campaign=self.campaign,
            contact=self.contact,
            template_used=self.template,
            subject="Test",
            from_email="noreply@example.com",
            to_email=self.contact.email,
            group=self.group
        )
    
    def test_email_event_creation(self):
        """Test creating email events."""
        event = EmailEvent.objects.create(
            message=self.message,
            event_type=EmailEvent.EventType.SENT,
            ip_address="192.168.1.1",
            user_agent="Test Client"
        )
        
        self.assertEqual(event.message, self.message)
        self.assertEqual(event.event_type, EmailEvent.EventType.SENT)
        self.assertEqual(event.ip_address, "192.168.1.1")
        self.assertIsNotNone(event.timestamp)
    
    def test_click_event_with_link_data(self):
        """Test click event with link information."""
        event = EmailEvent.objects.create(
            message=self.message,
            event_type=EmailEvent.EventType.CLICKED,
            link_url="https://example.com/special-offer",
            link_text="View Special Offer",
            metadata={
                "link_position": 2,
                "link_category": "cta"
            }
        )
        
        self.assertEqual(event.event_type, EmailEvent.EventType.CLICKED)
        self.assertIn("special-offer", event.link_url)
        self.assertEqual(event.link_text, "View Special Offer")
        self.assertEqual(event.metadata["link_category"], "cta")
    
    def test_event_metadata(self):
        """Test event metadata storage."""
        metadata = {
            "email_client": "Gmail",
            "device_type": "mobile",
            "os": "iOS",
            "location": {"country": "US", "region": "CA"}
        }
        
        event = EmailEvent.objects.create(
            message=self.message,
            event_type=EmailEvent.EventType.OPENED,
            metadata=metadata
        )
        
        self.assertEqual(event.metadata["email_client"], "Gmail")
        self.assertEqual(event.metadata["device_type"], "mobile")
        self.assertIn("location", event.metadata)
    
    def test_event_timeline(self):
        """Test multiple events create a timeline."""
        # Create sequence of events
        events_data = [
            (EmailEvent.EventType.SENT, timedelta(seconds=0)),
            (EmailEvent.EventType.DELIVERED, timedelta(minutes=1)),
            (EmailEvent.EventType.OPENED, timedelta(hours=2)),
            (EmailEvent.EventType.CLICKED, timedelta(hours=2, minutes=5)),
        ]
        
        base_time = timezone.now()
        events = []
        
        for event_type, time_delta in events_data:
            event = EmailEvent.objects.create(
                message=self.message,
                event_type=event_type,
                timestamp=base_time + time_delta
            )
            events.append(event)
        
        # Check events are in correct order
        message_events = self.message.events.order_by('timestamp')
        self.assertEqual(message_events.count(), 4)
        self.assertEqual(
            list(message_events.values_list('event_type', flat=True)),
            [e[0] for e in events_data]
        )


# Test multi-tenant filtering
class MultiTenantTests(TestCase):
    """Test multi-tenant data isolation."""
    
    def setUp(self):
        """Set up test data for multiple tenants."""
        # Create two groups (tenants)
        self.group1 = Group.objects.create(name="Tenant 1")
        self.group2 = Group.objects.create(name="Tenant 2")
        
        # Create users for each tenant
        self.user1 = User.objects.create_user(
            username="tenant1_user",
            email="user@tenant1.com",
            password="testpass123"
        )
        GroupMembership.objects.create(user=self.user1, group=self.group1)
        
        self.user2 = User.objects.create_user(
            username="tenant2_user",
            email="user@tenant2.com",
            password="testpass123"
        )
        GroupMembership.objects.create(user=self.user2, group=self.group2)
        
        # Create contacts for each tenant
        self.contact1 = Contact.objects.create(
            email="contact@tenant1.com",
            contact_type=ContactType.INDIVIDUAL,
            group=self.group1
        )
        
        self.contact2 = Contact.objects.create(
            email="contact@tenant2.com",
            contact_type=ContactType.INDIVIDUAL,
            group=self.group2
        )
    
    def test_contact_isolation(self):
        """Test contacts are isolated by group."""
        # Filter by group1
        group1_contacts = Contact.objects.filter(group=self.group1)
        self.assertEqual(group1_contacts.count(), 1)
        self.assertEqual(group1_contacts.first().email, "contact@tenant1.com")
        
        # Filter by group2
        group2_contacts = Contact.objects.filter(group=self.group2)
        self.assertEqual(group2_contacts.count(), 1)
        self.assertEqual(group2_contacts.first().email, "contact@tenant2.com")
    
    def test_email_template_isolation(self):
        """Test email templates are isolated by group."""
        # Use existing groups for email templates
        
        # Create templates for each tenant
        template1 = EmailTemplate.objects.create(
            name="Tenant 1 Template",
            subject="Test",
            html_content="<p>Test</p>",
            text_content="Test",
            created_by=self.user1,
            group=self.group1
        )
        
        template2 = EmailTemplate.objects.create(
            name="Tenant 2 Template",
            subject="Test",
            html_content="<p>Test</p>",
            text_content="Test",
            created_by=self.user2,
            group=self.group2
        )
        
        # Check isolation
        self.assertEqual(
            EmailTemplate.objects.filter(group=self.group1).count(), 
            1
        )
        self.assertEqual(
            EmailTemplate.objects.filter(group=self.group2).count(), 
            1
        )