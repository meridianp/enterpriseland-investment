"""
Contact enrichment service using the provider abstraction layer.
"""
import logging
from typing import Optional, List, Dict, Any
from django.core.cache import cache
from django.conf import settings

from asgiref.sync import sync_to_async
from integrations.registry import provider_registry
from integrations.exceptions import AllProvidersFailedError
from integrations.providers.enrichment.base import ContactData, CompanyData
from ..models import Contact, ContactActivity
from accounts.models import User

logger = logging.getLogger(__name__)


import asyncio


class ContactEnrichmentService:
    """
    High-level service for enriching contact and company data.
    
    This service provides a clean interface for the rest of the application
    to enrich contacts without worrying about provider details.
    """
    
    def __init__(self):
        self.registry = provider_registry
        self._cache_prefix = "enrichment"
        self._cache_ttl = getattr(settings, 'ENRICHMENT_CACHE_TTL', 86400)  # 24 hours
    
    async def enrich_contact(
        self,
        contact: Contact,
        user: Optional[User] = None,
        force_refresh: bool = False
    ) -> Contact:
        """
        Enrich a contact with data from external providers.
        
        Args:
            contact: The contact to enrich
            user: The user performing the enrichment (for activity tracking)
            force_refresh: Skip cache and force fresh enrichment
            
        Returns:
            The enriched contact object
        """
        if not contact.email:
            logger.warning(f"Cannot enrich contact {contact.id} without email")
            return contact
        
        # Check cache unless forced refresh
        cache_key = f"{self._cache_prefix}:contact:{contact.email}"
        if not force_refresh:
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info(f"Using cached enrichment data for {contact.email}")
                return self._update_contact_from_data(contact, cached_data, user)
        
        try:
            # Execute enrichment with automatic failover
            enrichment_data = await self.registry.execute(
                service='contact_enrichment',
                operation='enrich_contact',
                email=contact.email
            )
            
            # Cache the result
            cache.set(cache_key, enrichment_data, self._cache_ttl)
            
            # Update contact with enriched data
            contact = await self._update_contact_from_data(contact, enrichment_data, user)
            
            # Track the enrichment activity
            if user:
                await sync_to_async(ContactActivity.objects.create)(
                    contact=contact,
                    activity_type='NOTE',  # ENRICHMENT type doesn't exist
                    subject="Contact enriched",
                    description=f"Contact data enriched from {enrichment_data.data_source}",
                    actor=user,
                    metadata={
                        'provider': enrichment_data.data_source,
                        'confidence_score': enrichment_data.confidence_score
                    },
                    group=contact.group
                )
            
            logger.info(f"Successfully enriched contact {contact.id}")
            return contact
            
        except AllProvidersFailedError as e:
            logger.error(f"All enrichment providers failed for {contact.email}: {e}")
            # Track failed enrichment
            if user:
                await sync_to_async(ContactActivity.objects.create)(
                    contact=contact,
                    activity_type='NOTE',
                    subject="Enrichment failed",
                    description="Unable to enrich contact data from any provider",
                    actor=user,
                    metadata={'errors': e.errors},
                    group=contact.group
                )
            return contact
        
        except Exception as e:
            logger.error(f"Unexpected error enriching contact {contact.id}: {e}")
            return contact
    
    async def enrich_company(
        self,
        domain: str,
        user: Optional[User] = None,
        force_refresh: bool = False
    ) -> Optional[CompanyData]:
        """
        Enrich company data by domain.
        
        Args:
            domain: The company domain to enrich
            user: The user performing the enrichment
            force_refresh: Skip cache and force fresh enrichment
            
        Returns:
            CompanyData object or None if enrichment fails
        """
        # Check cache unless forced refresh
        cache_key = f"{self._cache_prefix}:company:{domain}"
        if not force_refresh:
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info(f"Using cached company data for {domain}")
                return cached_data
        
        try:
            # Execute enrichment with automatic failover
            company_data = await self.registry.execute(
                service='contact_enrichment',
                operation='enrich_company',
                domain=domain
            )
            
            # Cache the result
            cache.set(cache_key, company_data, self._cache_ttl)
            
            logger.info(f"Successfully enriched company {domain}")
            return company_data
            
        except AllProvidersFailedError as e:
            logger.error(f"All enrichment providers failed for {domain}: {e}")
            return None
        
        except Exception as e:
            logger.error(f"Unexpected error enriching company {domain}: {e}")
            return None
    
    async def bulk_enrich_contacts(
        self,
        contacts: List[Contact],
        user: Optional[User] = None,
        force_refresh: bool = False
    ) -> Dict[int, bool]:
        """
        Enrich multiple contacts in bulk.
        
        Args:
            contacts: List of contacts to enrich
            user: The user performing the enrichment
            force_refresh: Skip cache and force fresh enrichment
            
        Returns:
            Dictionary mapping contact IDs to success status
        """
        results = {}
        
        # Group contacts by email to avoid duplicate enrichments
        email_to_contacts = {}
        for contact in contacts:
            if contact.email:
                if contact.email not in email_to_contacts:
                    email_to_contacts[contact.email] = []
                email_to_contacts[contact.email].append(contact)
        
        # Enrich each unique email
        for email, contact_list in email_to_contacts.items():
            # Use the first contact for enrichment
            primary_contact = contact_list[0]
            
            try:
                enriched_contact = await self.enrich_contact(
                    primary_contact, 
                    user, 
                    force_refresh
                )
                
                # Apply enrichment to all contacts with this email
                for contact in contact_list:
                    if contact.id != primary_contact.id:
                        self._copy_enrichment_data(primary_contact, contact)
                        await sync_to_async(contact.save)()
                    results[contact.id] = True
                    
            except Exception as e:
                logger.error(f"Failed to enrich contacts with email {email}: {e}")
                for contact in contact_list:
                    results[contact.id] = False
        
        # Mark contacts without email as failed
        for contact in contacts:
            if not contact.email and contact.id not in results:
                results[contact.id] = False
        
        return results
    
    async def _update_contact_from_data(
        self,
        contact: Contact,
        data: ContactData,
        user: Optional[User] = None
    ) -> Contact:
        """Update contact fields from enrichment data."""
        # Update basic fields if not already set
        if not contact.first_name and data.first_name:
            contact.first_name = data.first_name
        
        if not contact.last_name and data.last_name:
            contact.last_name = data.last_name
        
        if not contact.job_title and data.title:
            contact.job_title = data.title
        
        if not contact.company_name and data.company:
            contact.company_name = data.company
        
        if not contact.phone_primary and data.phone:
            contact.phone_primary = data.phone
        
        # Parse location to city
        if not contact.city and data.location:
            # Assume location format is "City, State" or just "City"
            city = data.location.split(',')[0].strip()
            contact.city = city
        
        # Store social profiles in custom_fields
        contact.custom_fields = contact.custom_fields or {}
        if data.linkedin_url:
            contact.custom_fields['linkedin_url'] = data.linkedin_url
        
        if data.twitter_url:
            contact.custom_fields['twitter_url'] = data.twitter_url
        
        # Store additional data in custom_fields
        contact.custom_fields = contact.custom_fields or {}
        contact.custom_fields['enrichment'] = {
            'source': data.data_source,
            'confidence_score': data.confidence_score,
            'last_updated': data.last_updated.isoformat() if data.last_updated else None,
            'company_domain': data.company_domain,
            'seniority': data.seniority,
            'department': data.department,
            'bio': data.bio,
            'website': data.website,
            'avatar_url': data.avatar_url
        }
        
        # Update lead score based on enrichment
        if data.confidence_score and data.confidence_score >= 0.8:
            contact.current_score = min(100, contact.current_score + 10)
        
        # Save contact with async wrapper
        await sync_to_async(contact.save)()
        return contact
    
    def _copy_enrichment_data(self, source: Contact, target: Contact):
        """Copy enrichment data from one contact to another."""
        fields_to_copy = [
            'first_name', 'last_name', 'job_title', 'company_name', 
            'phone_primary', 'city'
        ]
        
        for field in fields_to_copy:
            source_value = getattr(source, field)
            target_value = getattr(target, field)
            if source_value and not target_value:
                setattr(target, field, source_value)
        
        # Copy custom fields (social profiles)
        if source.custom_fields:
            target.custom_fields = target.custom_fields or {}
            for key in ['linkedin_url', 'twitter_url']:
                if key in source.custom_fields and key not in target.custom_fields:
                    target.custom_fields[key] = source.custom_fields[key]
        
        # Copy enrichment custom_fields
        if source.custom_fields and source.custom_fields.get('enrichment'):
            target.custom_fields = target.custom_fields or {}
            target.custom_fields['enrichment'] = source.custom_fields['enrichment']
    
    def get_enrichment_status(self, contact: Contact) -> Dict[str, Any]:
        """Get the enrichment status for a contact."""
        if not contact.custom_fields or 'enrichment' not in contact.custom_fields:
            return {
                'enriched': False,
                'source': None,
                'confidence_score': None,
                'last_updated': None
            }
        
        enrichment_data = contact.custom_fields['enrichment']
        return {
            'enriched': True,
            'source': enrichment_data.get('source'),
            'confidence_score': enrichment_data.get('confidence_score'),
            'last_updated': enrichment_data.get('last_updated'),
            'has_company_data': bool(enrichment_data.get('company_domain')),
            'has_bio': bool(enrichment_data.get('bio'))
        }
    
    # Synchronous wrapper methods for Django management commands
    
    def enrich_contact_sync(
        self,
        contact: Contact,
        user: Optional[User] = None,
        force_refresh: bool = False
    ) -> Contact:
        """Synchronous wrapper for enrich_contact."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.enrich_contact(contact, user, force_refresh)
            )
        finally:
            loop.close()
    
    def enrich_company_sync(
        self,
        domain: str,
        user: Optional[User] = None,
        force_refresh: bool = False
    ) -> Optional[CompanyData]:
        """Synchronous wrapper for enrich_company."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.enrich_company(domain, user, force_refresh)
            )
        finally:
            loop.close()
    
    def bulk_enrich_contacts_sync(
        self,
        contacts: List[Contact],
        user: Optional[User] = None,
        force_refresh: bool = False
    ) -> Dict[int, bool]:
        """Synchronous wrapper for bulk_enrich_contacts."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.bulk_enrich_contacts(contacts, user, force_refresh)
            )
        finally:
            loop.close()