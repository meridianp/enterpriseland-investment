"""
Management command to test contact enrichment functionality.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from contacts.models import Contact
from contacts.services.enrichment import ContactEnrichmentService
from accounts.models import Group

User = get_user_model()


class Command(BaseCommand):
    help = 'Test contact enrichment functionality'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email address to enrich'
        )
        parser.add_argument(
            '--contact-id',
            type=int,
            help='Contact ID to enrich'
        )
        parser.add_argument(
            '--domain',
            type=str,
            help='Company domain to enrich'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force refresh (skip cache)'
        )
    
    def handle(self, *args, **options):
        """Handle the command execution."""
        # Get enrichment service
        service = ContactEnrichmentService()
        
        # Get a user for activity tracking
        user = User.objects.filter(role=User.Role.ADMIN).first()
        if not user:
            self.stdout.write(self.style.WARNING('No admin user found, creating one...'))
            # Create a default group first
            group, _ = Group.objects.get_or_create(
                name='Default Group',
                defaults={'description': 'Default group for testing'}
            )
            
            user = User.objects.create_user(
                email='admin@example.com',
                username='admin',
                password='admin123',
                role=User.Role.ADMIN,
                first_name='Admin',
                last_name='User'
            )
            
            # Add user to group
            user.groups.add(group)
        
        if options['email']:
            # Create or get contact with this email
            contact, created = Contact.objects.get_or_create(
                email=options['email'],
                defaults={
                    'group': user.groups.first() or Group.objects.first()
                }
            )
            if created:
                self.stdout.write(f"Created new contact with email {options['email']}")
            
            # Enrich the contact
            self.stdout.write(f"Enriching contact {contact.id} ({contact.email})...")
            enriched_contact = service.enrich_contact_sync(contact, user, force_refresh=options['force'])
            
            # Display results
            self._display_contact(enriched_contact)
            
        elif options['contact_id']:
            # Get existing contact
            try:
                contact = Contact.objects.get(id=options['contact_id'])
            except Contact.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Contact {options['contact_id']} not found"))
                return
            
            # Enrich the contact
            self.stdout.write(f"Enriching contact {contact.id} ({contact.email})...")
            enriched_contact = service.enrich_contact_sync(contact, user, force_refresh=options['force'])
            
            # Display results
            self._display_contact(enriched_contact)
            
        elif options['domain']:
            # Enrich company by domain
            self.stdout.write(f"Enriching company {options['domain']}...")
            company_data = service.enrich_company_sync(options['domain'], user, force_refresh=options['force'])
            
            if company_data:
                self._display_company(company_data)
            else:
                self.stdout.write(self.style.ERROR("Failed to enrich company"))
        
        else:
            # Test with sample contacts
            self.stdout.write("Testing with sample contacts...")
            
            # Create test contacts
            test_emails = [
                'john.doe@example.com',
                'jane.smith@techcorp.com',
                'bob.johnson@startup.io'
            ]
            
            contacts = []
            for email in test_emails:
                contact, _ = Contact.objects.get_or_create(
                    email=email,
                    defaults={
                        'group': user.groups.first() or Group.objects.first()
                    }
                )
                contacts.append(contact)
            
            # Bulk enrich
            self.stdout.write(f"Bulk enriching {len(contacts)} contacts...")
            results = service.bulk_enrich_contacts_sync(contacts, user, force_refresh=options['force'])
            
            # Display results
            for contact in contacts:
                contact.refresh_from_db()
                self.stdout.write(f"\n{'='*60}")
                self._display_contact(contact)
                status = service.get_enrichment_status(contact)
                self.stdout.write(f"Enrichment status: {status}")
    
    def _display_contact(self, contact):
        """Display contact information."""
        self.stdout.write(f"\nContact ID: {contact.id}")
        self.stdout.write(f"Email: {contact.email}")
        self.stdout.write(f"Name: {contact.first_name} {contact.last_name}")
        self.stdout.write(f"Title: {contact.job_title or 'N/A'}")
        self.stdout.write(f"Company: {contact.company_name or 'N/A'}")
        self.stdout.write(f"Phone: {contact.phone_primary or 'N/A'}")
        self.stdout.write(f"Location: {contact.city or 'N/A'}")
        
        # Check for social profiles in custom_fields
        linkedin = contact.custom_fields.get('linkedin_url', 'N/A') if contact.custom_fields else 'N/A'
        self.stdout.write(f"LinkedIn: {linkedin}")
        self.stdout.write(f"Lead Score: {contact.current_score}")
        
        if contact.custom_fields and contact.custom_fields.get('enrichment'):
            enrichment = contact.custom_fields['enrichment']
            self.stdout.write(f"\nEnrichment Data:")
            self.stdout.write(f"  Source: {enrichment.get('source')}")
            self.stdout.write(f"  Confidence: {enrichment.get('confidence_score')}")
            self.stdout.write(f"  Industry: {enrichment.get('industry', 'N/A')}")
            self.stdout.write(f"  Company Size: {enrichment.get('company_size', 'N/A')}")
    
    def _display_company(self, company_data):
        """Display company information."""
        self.stdout.write(f"\nCompany Domain: {company_data.domain}")
        self.stdout.write(f"Name: {company_data.name}")
        self.stdout.write(f"Description: {company_data.description}")
        self.stdout.write(f"Industry: {company_data.industry}")
        self.stdout.write(f"Employee Count: {company_data.employee_count}")
        self.stdout.write(f"Founded: {company_data.founded_year}")
        self.stdout.write(f"Location: {company_data.headquarters_city}, {company_data.headquarters_state}")
        self.stdout.write(f"Technologies: {', '.join(company_data.technologies or [])}")
        self.stdout.write(f"Confidence Score: {company_data.confidence_score}")