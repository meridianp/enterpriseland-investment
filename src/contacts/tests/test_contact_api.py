"""
Comprehensive test suite for contact API endpoints.

Tests contact ViewSets and serializers, cursor pagination,
full-text search, ContactPartner relationships, bulk operations,
and validation.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from contacts.models import (
    Contact, ContactList, ContactTag, ContactPartner,
    ContactStatus, ContactSource, EngagementLevel,
    Activity, ActivityType, Task, TaskStatus, TaskPriority
)
from accounts.models import Group, GroupMembership
from partners.models import DevelopmentPartner

User = get_user_model()


class ContactAPITestCase(APITestCase):
    """Test contact CRUD operations and permissions"""
    
    def setUp(self):
        """Set up test data"""
        # Create test group and users
        self.group = Group.objects.create(name="Contact API Test Company")
        self.admin_user = User.objects.create_user(
            username="admin@contactapi.com",
            email="admin@contactapi.com",
            password="testpass123",
            role=User.Role.ADMIN
        )
        self.analyst_user = User.objects.create_user(
            username="analyst@contactapi.com",
            email="analyst@contactapi.com",
            password="testpass123",
            role=User.Role.BUSINESS_ANALYST
        )
        self.readonly_user = User.objects.create_user(
            username="readonly@contactapi.com",
            email="readonly@contactapi.com",
            password="testpass123",
            role=User.Role.READ_ONLY
        )
        
        # Add users to group
        GroupMembership.objects.create(user=self.admin_user, group=self.group, is_admin=True)
        GroupMembership.objects.create(user=self.analyst_user, group=self.group)
        GroupMembership.objects.create(user=self.readonly_user, group=self.group)
        
        # Create tokens
        self.admin_token = str(RefreshToken.for_user(self.admin_user).access_token)
        self.analyst_token = str(RefreshToken.for_user(self.analyst_user).access_token)
        self.readonly_token = str(RefreshToken.for_user(self.readonly_user).access_token)
        
        # Create test contacts
        self.contact1 = Contact.objects.create(
            email="john.doe@example.com",
            first_name="John",
            last_name="Doe",
            company="Example Corp",
            title="CEO",
            phone="+1234567890",
            status=ContactStatus.QUALIFIED,
            source=ContactSource.LINKEDIN,
            group=self.group,
            created_by=self.admin_user
        )
        
        self.contact2 = Contact.objects.create(
            email="jane.smith@test.com",
            first_name="Jane",
            last_name="Smith",
            company="Test Inc",
            title="CTO",
            status=ContactStatus.LEAD,
            source=ContactSource.WEBSITE,
            group=self.group,
            created_by=self.admin_user
        )
        
        # Create tags
        self.tag1 = ContactTag.objects.create(
            name="High Priority",
            color="#FF0000",
            group=self.group,
            created_by=self.admin_user
        )
        self.tag2 = ContactTag.objects.create(
            name="Tech Industry",
            color="#0000FF",
            group=self.group,
            created_by=self.admin_user
        )
        
        # Add tags to contacts
        self.contact1.tags.add(self.tag1)
        self.contact2.tags.add(self.tag2)
    
    def test_list_contacts(self):
        """Test listing contacts with pagination"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        
        response = self.client.get('/api/contacts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        
        # Verify contact data
        contact_emails = [c['email'] for c in response.data['results']]
        self.assertIn("john.doe@example.com", contact_emails)
        self.assertIn("jane.smith@test.com", contact_emails)
    
    def test_create_contact(self):
        """Test creating a new contact"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        
        data = {
            "email": "new.contact@example.com",
            "first_name": "New",
            "last_name": "Contact",
            "company": "New Company",
            "title": "Manager",
            "phone": "+9876543210",
            "linkedin_url": "https://linkedin.com/in/newcontact",
            "status": ContactStatus.LEAD,
            "source": ContactSource.REFERRAL,
            "notes": "Met at conference",
            "tags": [str(self.tag1.id)]
        }
        
        response = self.client.post('/api/contacts/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['email'], "new.contact@example.com")
        self.assertEqual(response.data['status'], ContactStatus.LEAD)
        self.assertEqual(len(response.data['tags']), 1)
        
        # Verify contact was created with correct group
        contact = Contact.objects.get(id=response.data['id'])
        self.assertEqual(contact.group, self.group)
        self.assertEqual(contact.created_by, self.admin_user)
    
    def test_update_contact(self):
        """Test updating a contact"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        
        data = {
            "title": "Chief Executive Officer",
            "status": ContactStatus.OPPORTUNITY,
            "engagement_score": 85
        }
        
        response = self.client.patch(f'/api/contacts/{self.contact1.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], "Chief Executive Officer")
        self.assertEqual(response.data['status'], ContactStatus.OPPORTUNITY)
        self.assertEqual(response.data['engagement_score'], 85)
    
    def test_delete_contact(self):
        """Test deleting a contact"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        
        response = self.client.delete(f'/api/contacts/{self.contact2.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify contact was deleted
        self.assertFalse(Contact.objects.filter(id=self.contact2.id).exists())
    
    def test_contact_permissions(self):
        """Test contact access permissions"""
        # Read-only user should not be able to create
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.readonly_token}')
        
        data = {
            "email": "unauthorized@example.com",
            "first_name": "Unauthorized",
            "last_name": "User"
        }
        
        response = self.client.post('/api/contacts/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # But should be able to read
        response = self.client.get('/api/contacts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_contact_validation(self):
        """Test contact field validation"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        
        # Test invalid email
        data = {
            "email": "invalid-email",
            "first_name": "Test",
            "last_name": "User"
        }
        
        response = self.client.post('/api/contacts/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)
        
        # Test duplicate email
        data = {
            "email": "john.doe@example.com",  # Already exists
            "first_name": "Duplicate",
            "last_name": "User"
        }
        
        response = self.client.post('/api/contacts/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test engagement score validation
        data = {
            "email": "valid@example.com",
            "first_name": "Test",
            "last_name": "User",
            "engagement_score": 150  # Over 100
        }
        
        response = self.client.post('/api/contacts/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('engagement_score', response.data)


class ContactSearchTestCase(APITestCase):
    """Test contact search and filtering functionality"""
    
    def setUp(self):
        """Set up test data for search testing"""
        self.group = Group.objects.create(name="Search Test Company")
        self.user = User.objects.create_user(
            username="search@test.com",
            email="search@test.com",
            password="testpass123",
            role=User.Role.ADMIN
        )
        GroupMembership.objects.create(user=self.user, group=self.group)
        self.token = str(RefreshToken.for_user(self.user).access_token)
        
        # Create diverse contacts for search testing
        self.contacts = []
        
        # Contact 1: Technology sector, high engagement
        self.contacts.append(Contact.objects.create(
            email="tech.leader@techcorp.com",
            first_name="Tech",
            last_name="Leader",
            company="TechCorp International",
            title="Chief Technology Officer",
            status=ContactStatus.CUSTOMER,
            source=ContactSource.LINKEDIN,
            engagement_score=95,
            notes="Key decision maker in technology investments",
            group=self.group,
            created_by=self.user
        ))
        
        # Contact 2: Finance sector, medium engagement
        self.contacts.append(Contact.objects.create(
            email="finance.manager@investco.com",
            first_name="Finance",
            last_name="Manager",
            company="InvestCo Partners",
            title="Portfolio Manager",
            status=ContactStatus.QUALIFIED,
            source=ContactSource.REFERRAL,
            engagement_score=65,
            notes="Interested in technology partnerships",
            group=self.group,
            created_by=self.user
        ))
        
        # Contact 3: Healthcare sector, low engagement
        self.contacts.append(Contact.objects.create(
            email="health.admin@medicalgroup.com",
            first_name="Health",
            last_name="Administrator",
            company="Medical Group LLC",
            title="Healthcare Administrator",
            status=ContactStatus.LEAD,
            source=ContactSource.WEBSITE,
            engagement_score=25,
            notes="Initial contact from website form",
            group=self.group,
            created_by=self.user
        ))
        
        # Create and assign tags
        self.tech_tag = ContactTag.objects.create(
            name="Technology",
            group=self.group,
            created_by=self.user
        )
        self.finance_tag = ContactTag.objects.create(
            name="Finance",
            group=self.group,
            created_by=self.user
        )
        
        self.contacts[0].tags.add(self.tech_tag)
        self.contacts[1].tags.add(self.finance_tag)
    
    def test_full_text_search(self):
        """Test full-text search across multiple fields"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        # Search by company name
        response = self.client.get('/api/contacts/', {'search': 'TechCorp'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['company'], "TechCorp International")
        
        # Search by title
        response = self.client.get('/api/contacts/', {'search': 'Portfolio'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], "Portfolio Manager")
        
        # Search by notes
        response = self.client.get('/api/contacts/', {'search': 'technology'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)  # Both tech contacts
        
        # Search by name
        response = self.client.get('/api/contacts/', {'search': 'Health'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['first_name'], "Health")
    
    def test_filter_by_status(self):
        """Test filtering contacts by status"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        # Filter by CUSTOMER status
        response = self.client.get('/api/contacts/', {'status': ContactStatus.CUSTOMER})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['status'], ContactStatus.CUSTOMER)
        
        # Filter by multiple statuses
        response = self.client.get('/api/contacts/', {'status': f'{ContactStatus.LEAD},{ContactStatus.QUALIFIED}'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_filter_by_source(self):
        """Test filtering contacts by source"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        response = self.client.get('/api/contacts/', {'source': ContactSource.LINKEDIN})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['source'], ContactSource.LINKEDIN)
    
    def test_filter_by_engagement_score(self):
        """Test filtering contacts by engagement score range"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        # High engagement (>80)
        response = self.client.get('/api/contacts/', {'engagement_min': 80})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['engagement_score'], 95)
        
        # Medium engagement (50-70)
        response = self.client.get('/api/contacts/', {'engagement_min': 50, 'engagement_max': 70})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['engagement_score'], 65)
    
    def test_filter_by_tags(self):
        """Test filtering contacts by tags"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        # Filter by technology tag
        response = self.client.get('/api/contacts/', {'tags': str(self.tech_tag.id)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['email'], "tech.leader@techcorp.com")
        
        # Filter by multiple tags (OR operation)
        response = self.client.get('/api/contacts/', {'tags': f'{self.tech_tag.id},{self.finance_tag.id}'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_ordering(self):
        """Test ordering contacts"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        # Order by engagement score descending
        response = self.client.get('/api/contacts/', {'ordering': '-engagement_score'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        scores = [c['engagement_score'] for c in response.data['results']]
        self.assertEqual(scores, [95, 65, 25])
        
        # Order by created_at ascending
        response = self.client.get('/api/contacts/', {'ordering': 'created_at'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)


class ContactPartnerRelationshipTestCase(APITestCase):
    """Test ContactPartner relationships and operations"""
    
    def setUp(self):
        """Set up test data"""
        self.group = Group.objects.create(name="Relationship Test Company")
        self.user = User.objects.create_user(
            username="rel@test.com",
            email="rel@test.com",
            password="testpass123",
            role=User.Role.ADMIN
        )
        GroupMembership.objects.create(user=self.user, group=self.group)
        self.token = str(RefreshToken.for_user(self.user).access_token)
        
        # Create partners
        self.partner1 = DevelopmentPartner.objects.create(
            name="Partner One",
            email="partner1@example.com",
            group=self.group,
            created_by=self.user
        )
        self.partner2 = DevelopmentPartner.objects.create(
            name="Partner Two",
            email="partner2@example.com",
            group=self.group,
            created_by=self.user
        )
        
        # Create contacts
        self.contact1 = Contact.objects.create(
            email="contact1@partner1.com",
            first_name="Contact",
            last_name="One",
            company="Partner One",
            group=self.group,
            created_by=self.user
        )
        self.contact2 = Contact.objects.create(
            email="contact2@partner1.com",
            first_name="Contact",
            last_name="Two",
            company="Partner One",
            group=self.group,
            created_by=self.user
        )
    
    def test_create_contact_partner_relationship(self):
        """Test creating contact-partner relationships"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        data = {
            "contact": str(self.contact1.id),
            "partner": str(self.partner1.id),
            "role": "Primary Contact",
            "is_primary": True,
            "notes": "Main point of contact for all communications"
        }
        
        response = self.client.post('/api/contact-partners/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['role'], "Primary Contact")
        self.assertTrue(response.data['is_primary'])
        
        # Verify relationship was created
        relationship = ContactPartner.objects.get(id=response.data['id'])
        self.assertEqual(relationship.contact, self.contact1)
        self.assertEqual(relationship.partner, self.partner1)
        self.assertEqual(relationship.group, self.group)
    
    def test_multiple_relationships(self):
        """Test contact with multiple partner relationships"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        # Create first relationship
        ContactPartner.objects.create(
            contact=self.contact1,
            partner=self.partner1,
            role="Technical Lead",
            group=self.group,
            created_by=self.user
        )
        
        # Create second relationship
        ContactPartner.objects.create(
            contact=self.contact1,
            partner=self.partner2,
            role="Business Development",
            group=self.group,
            created_by=self.user
        )
        
        # Get contact with relationships
        response = self.client.get(f'/api/contacts/{self.contact1.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['partner_relationships']), 2)
        
        # Verify both relationships are included
        roles = [r['role'] for r in response.data['partner_relationships']]
        self.assertIn("Technical Lead", roles)
        self.assertIn("Business Development", roles)
    
    def test_primary_contact_constraint(self):
        """Test that only one primary contact per partner is allowed"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        # Create first primary contact
        ContactPartner.objects.create(
            contact=self.contact1,
            partner=self.partner1,
            role="Primary",
            is_primary=True,
            group=self.group,
            created_by=self.user
        )
        
        # Try to create second primary contact for same partner
        data = {
            "contact": str(self.contact2.id),
            "partner": str(self.partner1.id),
            "role": "Also Primary",
            "is_primary": True
        }
        
        response = self.client.post('/api/contact-partners/', data, format='json')
        
        # Should either fail or automatically set is_primary to False
        if response.status_code == status.HTTP_201_CREATED:
            # Check that the previous primary was updated
            first_rel = ContactPartner.objects.get(contact=self.contact1, partner=self.partner1)
            self.assertFalse(first_rel.is_primary)
    
    def test_partner_contacts_endpoint(self):
        """Test getting all contacts for a partner"""
        # Create relationships
        ContactPartner.objects.create(
            contact=self.contact1,
            partner=self.partner1,
            role="CEO",
            group=self.group,
            created_by=self.user
        )
        ContactPartner.objects.create(
            contact=self.contact2,
            partner=self.partner1,
            role="CTO",
            group=self.group,
            created_by=self.user
        )
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        # Get partner's contacts
        response = self.client.get(f'/api/partners/{self.partner1.id}/contacts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
        # Verify contact data
        contact_emails = [c['contact']['email'] for c in response.data]
        self.assertIn("contact1@partner1.com", contact_emails)
        self.assertIn("contact2@partner1.com", contact_emails)


class ContactBulkOperationsTestCase(APITestCase):
    """Test bulk operations on contacts"""
    
    def setUp(self):
        """Set up test data"""
        self.group = Group.objects.create(name="Bulk Test Company")
        self.user = User.objects.create_user(
            username="bulk@test.com",
            email="bulk@test.com",
            password="testpass123",
            role=User.Role.ADMIN
        )
        GroupMembership.objects.create(user=self.user, group=self.group)
        self.token = str(RefreshToken.for_user(self.user).access_token)
        
        # Create multiple contacts
        self.contacts = []
        for i in range(5):
            contact = Contact.objects.create(
                email=f"bulk{i}@example.com",
                first_name=f"Bulk{i}",
                last_name="Contact",
                company=f"Company {i}",
                status=ContactStatus.LEAD,
                group=self.group,
                created_by=self.user
            )
            self.contacts.append(contact)
        
        # Create tags
        self.tag1 = ContactTag.objects.create(
            name="Bulk Tag 1",
            group=self.group,
            created_by=self.user
        )
        self.tag2 = ContactTag.objects.create(
            name="Bulk Tag 2",
            group=self.group,
            created_by=self.user
        )
    
    def test_bulk_update_status(self):
        """Test bulk updating contact status"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        contact_ids = [str(c.id) for c in self.contacts[:3]]
        
        data = {
            "contact_ids": contact_ids,
            "updates": {
                "status": ContactStatus.QUALIFIED
            }
        }
        
        response = self.client.post('/api/contacts/bulk-update/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['updated_count'], 3)
        
        # Verify contacts were updated
        for contact_id in contact_ids:
            contact = Contact.objects.get(id=contact_id)
            self.assertEqual(contact.status, ContactStatus.QUALIFIED)
    
    def test_bulk_add_tags(self):
        """Test bulk adding tags to contacts"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        contact_ids = [str(c.id) for c in self.contacts]
        
        data = {
            "contact_ids": contact_ids,
            "action": "add_tags",
            "tag_ids": [str(self.tag1.id), str(self.tag2.id)]
        }
        
        response = self.client.post('/api/contacts/bulk-tag/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify tags were added
        for contact in self.contacts:
            contact.refresh_from_db()
            self.assertEqual(contact.tags.count(), 2)
            self.assertIn(self.tag1, contact.tags.all())
            self.assertIn(self.tag2, contact.tags.all())
    
    def test_bulk_remove_tags(self):
        """Test bulk removing tags from contacts"""
        # First add tags to contacts
        for contact in self.contacts:
            contact.tags.add(self.tag1, self.tag2)
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        contact_ids = [str(c.id) for c in self.contacts[:3]]
        
        data = {
            "contact_ids": contact_ids,
            "action": "remove_tags",
            "tag_ids": [str(self.tag1.id)]
        }
        
        response = self.client.post('/api/contacts/bulk-tag/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify tag was removed from first 3 contacts
        for i, contact in enumerate(self.contacts):
            contact.refresh_from_db()
            if i < 3:
                self.assertEqual(contact.tags.count(), 1)
                self.assertNotIn(self.tag1, contact.tags.all())
                self.assertIn(self.tag2, contact.tags.all())
            else:
                self.assertEqual(contact.tags.count(), 2)
    
    def test_bulk_delete(self):
        """Test bulk deleting contacts"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        contact_ids = [str(c.id) for c in self.contacts[:2]]
        
        data = {
            "contact_ids": contact_ids
        }
        
        response = self.client.post('/api/contacts/bulk-delete/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted_count'], 2)
        
        # Verify contacts were deleted
        remaining_contacts = Contact.objects.filter(group=self.group)
        self.assertEqual(remaining_contacts.count(), 3)
        
        for contact_id in contact_ids:
            self.assertFalse(Contact.objects.filter(id=contact_id).exists())
    
    def test_bulk_export(self):
        """Test bulk exporting contacts"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        # Add some data to contacts for export
        self.contacts[0].notes = "Important client"
        self.contacts[0].engagement_score = 90
        self.contacts[0].save()
        
        contact_ids = [str(c.id) for c in self.contacts]
        
        data = {
            "contact_ids": contact_ids,
            "format": "csv",
            "fields": ["email", "first_name", "last_name", "company", "status", "engagement_score", "notes"]
        }
        
        response = self.client.post('/api/contacts/export/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check response content type for CSV
        self.assertEqual(response['Content-Type'], 'text/csv')
        
        # Verify CSV content
        content = response.content.decode('utf-8')
        self.assertIn('email,first_name,last_name,company,status,engagement_score,notes', content)
        self.assertIn('bulk0@example.com', content)
        self.assertIn('Important client', content)


class ContactListTestCase(APITestCase):
    """Test contact list functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.group = Group.objects.create(name="List Test Company")
        self.user = User.objects.create_user(
            username="list@test.com",
            email="list@test.com",
            password="testpass123",
            role=User.Role.ADMIN
        )
        GroupMembership.objects.create(user=self.user, group=self.group)
        self.token = str(RefreshToken.for_user(self.user).access_token)
        
        # Create contacts
        self.contacts = []
        for i in range(10):
            contact = Contact.objects.create(
                email=f"list{i}@example.com",
                first_name=f"List{i}",
                last_name="Contact",
                company=f"Company {i}",
                status=ContactStatus.LEAD if i < 5 else ContactStatus.QUALIFIED,
                engagement_score=i * 10,
                group=self.group,
                created_by=self.user
            )
            self.contacts.append(contact)
    
    def test_create_static_list(self):
        """Test creating a static contact list"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        contact_ids = [str(c.id) for c in self.contacts[:5]]
        
        data = {
            "name": "Q1 Prospects",
            "description": "High priority prospects for Q1",
            "list_type": "static",
            "contacts": contact_ids
        }
        
        response = self.client.post('/api/contact-lists/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], "Q1 Prospects")
        self.assertEqual(response.data['contact_count'], 5)
        
        # Verify list was created with contacts
        contact_list = ContactList.objects.get(id=response.data['id'])
        self.assertEqual(contact_list.contacts.count(), 5)
    
    def test_create_dynamic_list(self):
        """Test creating a dynamic contact list with filters"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        data = {
            "name": "High Engagement Leads",
            "description": "Automatically updated list of high engagement leads",
            "list_type": "dynamic",
            "dynamic_filters": {
                "status": ContactStatus.QUALIFIED,
                "engagement_score__gte": 50
            }
        }
        
        response = self.client.post('/api/contact-lists/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['list_type'], "dynamic")
        
        # Test dynamic list computation
        response = self.client.get(f'/api/contact-lists/{response.data["id"]}/contacts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should return contacts with QUALIFIED status and engagement_score >= 50
        self.assertEqual(len(response.data['results']), 5)
        for contact in response.data['results']:
            self.assertEqual(contact['status'], ContactStatus.QUALIFIED)
            self.assertGreaterEqual(contact['engagement_score'], 50)
    
    def test_update_list_contacts(self):
        """Test adding and removing contacts from a list"""
        # Create initial list
        contact_list = ContactList.objects.create(
            name="Update Test List",
            group=self.group,
            created_by=self.user
        )
        contact_list.contacts.set(self.contacts[:3])
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        # Add contacts
        data = {
            "action": "add",
            "contact_ids": [str(self.contacts[3].id), str(self.contacts[4].id)]
        }
        
        response = self.client.post(f'/api/contact-lists/{contact_list.id}/update-contacts/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        contact_list.refresh_from_db()
        self.assertEqual(contact_list.contacts.count(), 5)
        
        # Remove contacts
        data = {
            "action": "remove",
            "contact_ids": [str(self.contacts[0].id), str(self.contacts[1].id)]
        }
        
        response = self.client.post(f'/api/contact-lists/{contact_list.id}/update-contacts/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        contact_list.refresh_from_db()
        self.assertEqual(contact_list.contacts.count(), 3)
    
    def test_list_statistics(self):
        """Test contact list statistics endpoint"""
        # Create list with varied contacts
        contact_list = ContactList.objects.create(
            name="Stats Test List",
            group=self.group,
            created_by=self.user
        )
        contact_list.contacts.set(self.contacts)
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        response = self.client.get(f'/api/contact-lists/{contact_list.id}/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify statistics
        self.assertEqual(response.data['total_contacts'], 10)
        self.assertEqual(response.data['status_breakdown'][ContactStatus.LEAD], 5)
        self.assertEqual(response.data['status_breakdown'][ContactStatus.QUALIFIED], 5)
        self.assertIn('average_engagement_score', response.data)
        self.assertIn('source_breakdown', response.data)


class ContactPaginationTestCase(APITestCase):
    """Test cursor pagination for contacts"""
    
    def setUp(self):
        """Set up test data"""
        self.group = Group.objects.create(name="Pagination Test Company")
        self.user = User.objects.create_user(
            username="page@test.com",
            email="page@test.com",
            password="testpass123",
            role=User.Role.ADMIN
        )
        GroupMembership.objects.create(user=self.user, group=self.group)
        self.token = str(RefreshToken.for_user(self.user).access_token)
        
        # Create 50 contacts for pagination testing
        self.contacts = []
        for i in range(50):
            contact = Contact.objects.create(
                email=f"page{i:02d}@example.com",
                first_name=f"Page{i:02d}",
                last_name="Contact",
                company=f"Company {i:02d}",
                created_at=timezone.now() - timedelta(days=50-i),
                group=self.group,
                created_by=self.user
            )
            self.contacts.append(contact)
    
    def test_cursor_pagination(self):
        """Test cursor-based pagination"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        # First page
        response = self.client.get('/api/contacts/', {'page_size': 10})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)
        self.assertIsNotNone(response.data['next'])
        self.assertIsNone(response.data['previous'])
        
        # Verify ordering (newest first by default)
        first_contact = response.data['results'][0]
        self.assertEqual(first_contact['email'], 'page49@example.com')
        
        # Second page using cursor
        next_url = response.data['next']
        response = self.client.get(next_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)
        self.assertIsNotNone(response.data['next'])
        self.assertIsNotNone(response.data['previous'])
        
        # Verify no duplicate results
        second_page_first = response.data['results'][0]
        self.assertEqual(second_page_first['email'], 'page39@example.com')
    
    def test_page_size_limits(self):
        """Test page size limits"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        # Test max page size limit (usually 100)
        response = self.client.get('/api/contacts/', {'page_size': 200})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data['results']), 100)
        
        # Test custom page size
        response = self.client.get('/api/contacts/', {'page_size': 5})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)
    
    def test_pagination_with_filters(self):
        """Test pagination works correctly with filters"""
        # Add status to some contacts
        for i, contact in enumerate(self.contacts):
            if i % 2 == 0:
                contact.status = ContactStatus.QUALIFIED
                contact.save()
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        # Get filtered results with pagination
        response = self.client.get('/api/contacts/', {
            'status': ContactStatus.QUALIFIED,
            'page_size': 10
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)
        
        # Verify all results match filter
        for contact in response.data['results']:
            self.assertEqual(contact['status'], ContactStatus.QUALIFIED)
        
        # Check total count
        total_qualified = Contact.objects.filter(
            group=self.group,
            status=ContactStatus.QUALIFIED
        ).count()
        self.assertEqual(total_qualified, 25)  # Half of 50 contacts