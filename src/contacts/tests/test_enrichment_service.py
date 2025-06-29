"""
Tests for the contact enrichment service.
"""
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from unittest.mock import patch, Mock, AsyncMock
from datetime import datetime

from accounts.models import Group
from contacts.models import Contact, ContactActivity
from contacts.services.enrichment import ContactEnrichmentService
from integrations.providers.enrichment.base import ContactData, CompanyData
from integrations.exceptions import AllProvidersFailedError

User = get_user_model()


class ContactEnrichmentServiceTestCase(TestCase):
    """Test cases for contact enrichment service."""
    
    def setUp(self):
        """Set up test data."""
        # Create group
        self.group = Group.objects.create(
            name="Test Group",
            description="Test group for enrichment"
        )
        
        # Create user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            role=User.Role.ADMIN
        )
        self.user.groups.add(self.group)
        
        # Create test contact
        self.contact = Contact.objects.create(
            email="john.doe@example.com",
            group=self.group
        )
        
        # Initialize service
        self.service = ContactEnrichmentService()
    
    def test_service_initialization(self):
        """Test service initializes correctly."""
        self.assertIsNotNone(self.service.registry)
        self.assertEqual(self.service._cache_prefix, "enrichment")
        self.assertEqual(self.service._cache_ttl, 86400)
    
    @patch('contacts.services.enrichment.cache')
    def test_enrich_contact_sync_cached(self, mock_cache):
        """Test enriching contact with cached data."""
        # Mock cached data
        cached_data = ContactData(
            email="john.doe@example.com",
            first_name="John",
            last_name="Doe",
            title="CEO",
            company="Example Corp",
            confidence_score=0.95,
            data_source="cache"
        )
        mock_cache.get.return_value = cached_data
        
        # Enrich contact
        result = self.service.enrich_contact_sync(self.contact, self.user)
        
        # Check cache was used
        mock_cache.get.assert_called_once_with("enrichment:contact:john.doe@example.com")
        
        # Check contact was updated
        self.assertEqual(result.first_name, "John")
        self.assertEqual(result.last_name, "Doe")
        self.assertEqual(result.job_title, "CEO")
        self.assertEqual(result.company_name, "Example Corp")
    
    @patch('contacts.services.enrichment.provider_registry')
    @patch('contacts.services.enrichment.cache')
    def test_enrich_contact_sync_fresh(self, mock_cache, mock_registry):
        """Test enriching contact with fresh data from provider."""
        # Mock no cached data
        mock_cache.get.return_value = None
        
        # Mock provider response
        enrichment_data = ContactData(
            email="john.doe@example.com",
            first_name="John",
            last_name="Doe",
            title="Software Engineer",
            company="Tech Corp",
            company_domain="techcorp.com",
            location="San Francisco, CA",
            linkedin_url="https://linkedin.com/in/johndoe",
            confidence_score=0.85,
            data_source="clearbit"
        )
        
        # Create async mock that returns the data
        async_mock = AsyncMock(return_value=enrichment_data)
        mock_registry.execute = async_mock
        
        # Enrich contact
        result = self.service.enrich_contact_sync(self.contact, self.user, force_refresh=False)
        
        # Check provider was called
        self.assertEqual(async_mock.call_count, 1)
        
        # Check cache was set
        mock_cache.set.assert_called_once()
        
        # Check contact was updated
        self.assertEqual(result.first_name, "John")
        self.assertEqual(result.last_name, "Doe")
        self.assertEqual(result.job_title, "Software Engineer")
        self.assertEqual(result.company_name, "Tech Corp")
        self.assertEqual(result.city, "San Francisco")
        self.assertEqual(result.current_score, 10)  # Lead score boost
        
        # Check custom fields
        self.assertIn('linkedin_url', result.custom_fields)
        self.assertEqual(result.custom_fields['linkedin_url'], "https://linkedin.com/in/johndoe")
        
        # Check enrichment metadata
        self.assertIn('enrichment', result.custom_fields)
        self.assertEqual(result.custom_fields['enrichment']['source'], 'clearbit')
        self.assertEqual(result.custom_fields['enrichment']['confidence_score'], 0.85)
    
    @patch('contacts.services.enrichment.provider_registry')
    @patch('contacts.services.enrichment.cache')
    def test_enrich_contact_sync_all_providers_fail(self, mock_cache, mock_registry):
        """Test handling when all providers fail."""
        # Mock no cached data
        mock_cache.get.return_value = None
        
        # Mock provider failure
        async_mock = AsyncMock(side_effect=AllProvidersFailedError(
            'contact_enrichment',
            ['clearbit: Connection error', 'apollo: Rate limit exceeded']
        ))
        mock_registry.execute = async_mock
        
        # Enrich contact - should not raise exception
        result = self.service.enrich_contact_sync(self.contact, self.user)
        
        # Contact should be returned unchanged
        self.assertEqual(result.id, self.contact.id)
        self.assertEqual(result.first_name, self.contact.first_name)
        
        # Check activity was created
        activity = ContactActivity.objects.filter(
            contact=self.contact,
            activity_type='NOTE',
            subject='Enrichment failed'
        ).first()
        self.assertIsNotNone(activity)
        self.assertIn('errors', activity.metadata)
    
    def test_enrich_contact_without_email(self):
        """Test enriching contact without email."""
        # Create contact without email
        contact_no_email = Contact.objects.create(
            first_name="No",
            last_name="Email",
            group=self.group
        )
        
        # Try to enrich
        result = self.service.enrich_contact_sync(contact_no_email, self.user)
        
        # Should return unchanged contact
        self.assertEqual(result.id, contact_no_email.id)
        self.assertEqual(result.first_name, "No")
    
    @patch('contacts.services.enrichment.provider_registry')
    def test_enrich_company_sync(self, mock_registry):
        """Test enriching company data."""
        # Mock provider response
        company_data = CompanyData(
            domain="techcorp.com",
            name="Tech Corp",
            description="Leading technology company",
            industry="Technology",
            employee_count=500,
            founded_year=2010,
            headquarters_city="San Francisco",
            headquarters_state="CA",
            headquarters_country="USA",
            confidence_score=0.9
        )
        
        async_mock = AsyncMock(return_value=company_data)
        mock_registry.execute = async_mock
        
        # Enrich company
        result = self.service.enrich_company_sync("techcorp.com", self.user)
        
        # Check result
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "Tech Corp")
        self.assertEqual(result.industry, "Technology")
        self.assertEqual(result.employee_count, 500)
    
    @patch('contacts.services.enrichment.provider_registry')
    def test_bulk_enrich_contacts_sync(self, mock_registry):
        """Test bulk enriching contacts."""
        # Create additional contacts
        contact2 = Contact.objects.create(
            email="jane.smith@example.com",
            group=self.group
        )
        contact3 = Contact.objects.create(
            email="john.doe@example.com",  # Same email as contact1
            first_name="Johnny",
            group=self.group
        )
        
        # Mock provider response
        enrichment_data = ContactData(
            email="john.doe@example.com",
            first_name="John",
            last_name="Doe",
            confidence_score=0.9,
            data_source="clearbit"
        )
        
        async_mock = AsyncMock(return_value=enrichment_data)
        mock_registry.execute = async_mock
        
        # Bulk enrich
        contacts = [self.contact, contact2, contact3]
        results = self.service.bulk_enrich_contacts_sync(contacts, self.user)
        
        # Check results
        self.assertEqual(len(results), 3)
        self.assertTrue(results[self.contact.id])
        self.assertTrue(results[contact3.id])
        
        # Check both contacts with same email were updated
        self.contact.refresh_from_db()
        contact3.refresh_from_db()
        self.assertEqual(self.contact.first_name, "John")
        self.assertEqual(contact3.first_name, "John")  # Updated from Johnny
    
    def test_get_enrichment_status_not_enriched(self):
        """Test getting status for non-enriched contact."""
        status = self.service.get_enrichment_status(self.contact)
        
        self.assertFalse(status['enriched'])
        self.assertIsNone(status['source'])
        self.assertIsNone(status['confidence_score'])
        self.assertIsNone(status['last_updated'])
    
    def test_get_enrichment_status_enriched(self):
        """Test getting status for enriched contact."""
        # Add enrichment data
        self.contact.custom_fields = {
            'enrichment': {
                'source': 'clearbit',
                'confidence_score': 0.95,
                'last_updated': '2024-01-01T12:00:00Z',
                'company_domain': 'example.com',
                'bio': 'Professional bio'
            }
        }
        self.contact.save()
        
        status = self.service.get_enrichment_status(self.contact)
        
        self.assertTrue(status['enriched'])
        self.assertEqual(status['source'], 'clearbit')
        self.assertEqual(status['confidence_score'], 0.95)
        self.assertEqual(status['last_updated'], '2024-01-01T12:00:00Z')
        self.assertTrue(status['has_company_data'])
        self.assertTrue(status['has_bio'])
    
    def test_update_contact_from_data_partial(self):
        """Test updating contact with partial data."""
        # Set some existing data
        self.contact.first_name = "Existing"
        self.contact.save()
        
        # Create partial enrichment data
        enrichment_data = ContactData(
            email=self.contact.email,
            last_name="Doe",
            title="Engineer",
            confidence_score=0.7,  # Below threshold for lead score boost
            data_source="test"
        )
        
        # Update contact
        import asyncio
        result = asyncio.run(
            self.service._update_contact_from_data(self.contact, enrichment_data)
        )
        
        # Check selective updates
        self.assertEqual(result.first_name, "Existing")  # Not overwritten
        self.assertEqual(result.last_name, "Doe")  # Updated
        self.assertEqual(result.job_title, "Engineer")  # Updated
        self.assertEqual(result.current_score, 0)  # No boost (low confidence)
    
    def test_copy_enrichment_data(self):
        """Test copying enrichment data between contacts."""
        # Setup source contact with enrichment
        source = Contact.objects.create(
            email="source@example.com",
            first_name="Source",
            last_name="User",
            job_title="CEO",
            company_name="Source Corp",
            city="New York",
            group=self.group,
            custom_fields={
                'linkedin_url': 'https://linkedin.com/in/source',
                'enrichment': {
                    'source': 'clearbit',
                    'confidence_score': 0.95
                }
            }
        )
        
        # Setup target contact
        target = Contact.objects.create(
            email="target@example.com",
            group=self.group
        )
        
        # Copy data
        self.service._copy_enrichment_data(source, target)
        
        # Check data was copied
        self.assertEqual(target.first_name, "Source")
        self.assertEqual(target.last_name, "User")
        self.assertEqual(target.job_title, "CEO")
        self.assertEqual(target.company_name, "Source Corp")
        self.assertEqual(target.city, "New York")
        self.assertEqual(target.custom_fields['linkedin_url'], 'https://linkedin.com/in/source')
        self.assertEqual(target.custom_fields['enrichment']['source'], 'clearbit')