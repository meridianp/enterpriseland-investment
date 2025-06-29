"""
Tests for the contacts app.
"""

from platform_core.core.tests import PlatformTestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse

from accounts.models import Group
from .models import Contact, ContactActivity, ContactList, ContactPartner
from assessments.models import DevelopmentPartner

User = get_user_model()


class ContactModelTest(TestCase):
    """Test Contact model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass"
        )
        self.user.groups.add(self.group)
        
    def test_contact_creation(self):
        """Test creating a contact."""
        contact = Contact.objects.create(
            group=self.group,
            email="contact@example.com",
            first_name="John",
            last_name="Doe",
            company_name="ACME Corp"
        )
        
        self.assertEqual(contact.email, "contact@example.com")
        self.assertEqual(contact.full_name, "John Doe")
        self.assertEqual(str(contact), "John Doe (ACME Corp)")
        
    def test_contact_status_transitions(self):
        """Test FSM status transitions."""
        contact = Contact.objects.create(
            group=self.group,
            email="lead@example.com"
        )
        
        # Initial status should be LEAD
        self.assertEqual(contact.status, "lead")
        
        # Qualify the lead
        contact.qualify()
        contact.save()
        self.assertEqual(contact.status, "qualified")
        
        # Convert to opportunity
        contact.convert_to_opportunity()
        contact.save()
        self.assertEqual(contact.status, "opportunity")
        
        # Convert to customer
        contact.convert_to_customer()
        contact.save()
        self.assertEqual(contact.status, "customer")
        
    def test_lead_scoring(self):
        """Test lead scoring calculation."""
        contact = Contact.objects.create(
            group=self.group,
            email="score@example.com",
            first_name="Jane",
            last_name="Smith",
            company_name="Tech Co",
            phone_primary="+1234567890",
            job_title="CEO"
        )
        
        # Calculate initial score
        score = contact.calculate_score()
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)


class ContactAPITest(APITestCase):
    """Test Contact API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass"
        )
        self.user.groups.add(self.group)
        self.client.force_authenticate(user=self.user)
        
    def test_create_contact(self):
        """Test creating a contact via API."""
        url = reverse('contacts:contact-list')
        data = {
            'email': 'newcontact@example.com',
            'first_name': 'New',
            'last_name': 'Contact',
            'contact_type': 'individual'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Contact.objects.count(), 1)
        
        contact = Contact.objects.first()
        self.assertEqual(contact.email, 'newcontact@example.com')
        self.assertEqual(contact.group, self.group)
        
    def test_list_contacts(self):
        """Test listing contacts with pagination."""
        # Create multiple contacts
        for i in range(5):
            Contact.objects.create(
                group=self.group,
                email=f'contact{i}@example.com',
                first_name=f'Contact{i}'
            )
        
        url = reverse('contacts:contact-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)
        
    def test_filter_contacts(self):
        """Test filtering contacts."""
        # Create contacts with different statuses
        Contact.objects.create(
            group=self.group,
            email='lead@example.com',
            status='lead'
        )
        Contact.objects.create(
            group=self.group,
            email='customer@example.com',
            status='customer'
        )
        
        url = reverse('contacts:contact-list')
        response = self.client.get(url, {'status': 'lead'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['email'], 'lead@example.com')
        
    def test_search_contacts(self):
        """Test searching contacts."""
        Contact.objects.create(
            group=self.group,
            email='john.doe@example.com',
            first_name='John',
            last_name='Doe'
        )
        Contact.objects.create(
            group=self.group,
            email='jane.smith@example.com',
            first_name='Jane',
            last_name='Smith'
        )
        
        url = reverse('contacts:contact-search')
        response = self.client.get(url, {'q': 'john'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['email'], 'john.doe@example.com')


class ContactListAPITest(APITestCase):
    """Test ContactList API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass"
        )
        self.user.groups.add(self.group)
        self.client.force_authenticate(user=self.user)
        
    def test_create_contact_list(self):
        """Test creating a contact list."""
        url = reverse('contacts:contactlist-list')
        data = {
            'name': 'VIP Customers',
            'description': 'Our most valuable customers',
            'is_public': True
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        contact_list = ContactList.objects.first()
        self.assertEqual(contact_list.name, 'VIP Customers')
        self.assertEqual(contact_list.created_by, self.user)
        
    def test_add_contacts_to_list(self):
        """Test adding contacts to a list."""
        # Create a list and contacts
        contact_list = ContactList.objects.create(
            group=self.group,
            name='Test List',
            created_by=self.user
        )
        
        contacts = []
        for i in range(3):
            contact = Contact.objects.create(
                group=self.group,
                email=f'contact{i}@example.com'
            )
            contacts.append(contact)
        
        url = reverse('contacts:contactlist-add-contacts', kwargs={'pk': contact_list.id})
        data = {'contact_ids': [str(c.id) for c in contacts]}
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['added'], 3)
        self.assertEqual(contact_list.contacts.count(), 3)
