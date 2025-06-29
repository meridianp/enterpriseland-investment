"""
Django management command to import HubSpot data.

Imports companies and contacts from HubSpot export tables in PostgreSQL,
preserving all metadata and creating appropriate relationships.
"""

import psycopg2
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from accounts.models import Group, User
from market_intelligence.models import TargetCompany
from market_intelligence.utils.hubspot_import import (
    convert_excel_date,
    map_country_to_iso,
    map_industry_to_business_model,
    clean_phone_number,
    parse_company_size,
)
from contacts.models import Contact, ContactStatus, ContactType
from leads.models import Lead, LeadScoringModel


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Import HubSpot data from PostgreSQL tables into Django models."""
    
    help = 'Import companies and contacts from HubSpot export tables'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stats = {
            'companies_processed': 0,
            'companies_created': 0,
            'companies_updated': 0,
            'companies_skipped': 0,
            'contacts_processed': 0,
            'contacts_created': 0,
            'contacts_updated': 0,
            'contacts_skipped': 0,
            'errors': []
        }
        self.group = None
        self.default_user = None
        self.hubspot_conn = None
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--group-id',
            type=str,
            required=True,
            help='UUID of the group to import data into'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of records to process in each batch'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing records instead of skipping'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making any database changes'
        )
        parser.add_argument(
            '--companies-only',
            action='store_true',
            help='Import only companies, skip contacts'
        )
        parser.add_argument(
            '--contacts-only',
            action='store_true',
            help='Import only contacts, skip companies'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of records to import (for testing)'
        )
    
    def handle(self, *args, **options):
        """Main command handler."""
        try:
            # Validate group
            try:
                self.group = Group.objects.get(id=options['group_id'])
                self.stdout.write(f"Importing into group: {self.group.name}")
            except Group.DoesNotExist:
                raise CommandError(f"Group with ID {options['group_id']} not found")
            
            # Get a default user for the group (first admin or manager)
            self.default_user = User.objects.filter(
                groups=self.group,
                role__in=[User.Role.ADMIN, User.Role.PORTFOLIO_MANAGER]
            ).first()
            
            if not self.default_user:
                raise CommandError(f"No admin or manager user found in group {self.group.name}")
            
            # Connect to HubSpot database
            self.connect_to_hubspot_db()
            
            # Import data
            if not options['contacts_only']:
                self.import_companies(options)
            
            if not options['companies_only']:
                self.import_contacts(options)
            
            # Print summary
            self.print_summary()
            
        except Exception as e:
            logger.error(f"Import failed: {str(e)}", exc_info=True)
            raise CommandError(f"Import failed: {str(e)}")
        finally:
            if self.hubspot_conn:
                self.hubspot_conn.close()
    
    def connect_to_hubspot_db(self):
        """Connect to the HubSpot PostgreSQL database."""
        try:
            # Get database URL from settings or environment
            database_url = getattr(settings, 'DATABASE_URL', None) or \
                          'postgresql://elandadmin:0ctavian@postgres01.tailb381ec.ts.net:5432/elanddata'
            
            self.hubspot_conn = psycopg2.connect(database_url)
            self.stdout.write("Connected to HubSpot database")
            
        except psycopg2.Error as e:
            raise CommandError(f"Failed to connect to HubSpot database: {str(e)}")
    
    def import_companies(self, options):
        """Import companies from HubSpot table."""
        self.stdout.write("\nImporting companies...")
        
        cur = self.hubspot_conn.cursor()
        
        try:
            # Count total companies
            cur.execute("""
                SELECT COUNT(*) 
                FROM external_data.hubspot_crm_exports_all_companies_2025_06_26
            """)
            total_count = cur.fetchone()[0]
            
            # Apply limit if specified
            limit_clause = f"LIMIT {options['limit']}" if options.get('limit') else ""
            
            # Fetch companies
            cur.execute(f"""
                SELECT 
                    "Record ID",
                    "Company name",
                    "Company owner",
                    "Create Date",
                    "Phone Number",
                    "Last Activity Date",
                    "city",
                    "Country/Region",
                    "industry"
                FROM external_data.hubspot_crm_exports_all_companies_2025_06_26
                ORDER BY "Record ID"
                {limit_clause}
            """)
            
            batch = []
            for row in cur:
                batch.append(row)
                
                if len(batch) >= options['batch_size']:
                    self.process_company_batch(batch, options)
                    batch = []
            
            # Process remaining records
            if batch:
                self.process_company_batch(batch, options)
                
        finally:
            cur.close()
    
    def process_company_batch(self, batch: List[Tuple], options):
        """Process a batch of company records."""
        for row in batch:
            self.stats['companies_processed'] += 1
            
            try:
                (record_id, company_name, owner, create_date, phone,
                 last_activity, city, country, industry) = row
                
                # Skip if no company name
                if not company_name:
                    self.stats['companies_skipped'] += 1
                    continue
                
                # Convert dates
                created_at = convert_excel_date(create_date) if create_date else timezone.now()
                last_activity_date = convert_excel_date(float(last_activity)) if last_activity else None
                
                # Map fields
                country_code = map_country_to_iso(country)
                business_model = map_industry_to_business_model(industry)
                
                # Prepare company data
                company_data = {
                    'company_name': company_name[:255],  # Ensure it fits in field
                    'headquarters_city': (city or '')[:100],
                    'headquarters_country': country_code,
                    'business_model': business_model,
                    'employee_count': None,  # Not in HubSpot data
                    'company_size': 'unknown',
                    'identified_by': self.default_user,
                    'enrichment_data': {
                        'hubspot_id': str(record_id),
                        'hubspot_owner': owner or '',
                        'original_create_date': str(create_date) if create_date else None,
                        'last_activity_date': last_activity_date.isoformat() if last_activity_date else None,
                        'phone': clean_phone_number(phone),
                        'industry': industry or '',
                        'import_date': timezone.now().isoformat(),
                        'import_source': 'hubspot_export'
                    }
                }
                
                if not options['dry_run']:
                    with transaction.atomic():
                        # Check if company already exists
                        existing = TargetCompany.objects.filter(
                            group=self.group,
                            company_name__iexact=company_name
                        ).first()
                        
                        if existing:
                            if options['update_existing']:
                                # Update existing company
                                for key, value in company_data.items():
                                    if key != 'enrichment_data':
                                        setattr(existing, key, value)
                                    else:
                                        # Merge enrichment data
                                        existing.enrichment_data.update(value)
                                
                                existing.updated_at = timezone.now()
                                existing.save()
                                self.stats['companies_updated'] += 1
                            else:
                                self.stats['companies_skipped'] += 1
                        else:
                            # Create new company
                            company = TargetCompany.objects.create(
                                group=self.group,
                                created_at=created_at,
                                **company_data
                            )
                            self.stats['companies_created'] += 1
                else:
                    # Dry run - just count what would happen
                    existing = TargetCompany.objects.filter(
                        group=self.group,
                        company_name__iexact=company_name
                    ).exists()
                    
                    if existing and not options['update_existing']:
                        self.stats['companies_skipped'] += 1
                    elif existing:
                        self.stats['companies_updated'] += 1
                    else:
                        self.stats['companies_created'] += 1
                
                # Progress indicator
                if self.stats['companies_processed'] % 100 == 0:
                    self.stdout.write(f"  Processed {self.stats['companies_processed']} companies...")
                    
            except Exception as e:
                error_msg = f"Error processing company {record_id}: {str(e)}"
                logger.error(error_msg)
                self.stats['errors'].append(error_msg)
    
    def import_contacts(self, options):
        """Import contacts from HubSpot table."""
        self.stdout.write("\nImporting contacts...")
        
        cur = self.hubspot_conn.cursor()
        
        try:
            # Count total contacts
            cur.execute("""
                SELECT COUNT(*) 
                FROM external_data.hubspot_crm_exports_all_contacts_2025_06_26
            """)
            total_count = cur.fetchone()[0]
            
            # Apply limit if specified
            limit_clause = f"LIMIT {options['limit']}" if options.get('limit') else ""
            
            # Fetch contacts
            cur.execute(f"""
                SELECT 
                    "Record ID",
                    "First Name",
                    "Last Name",
                    "city",
                    "Create Date",
                    "email",
                    "Next Step",
                    "Nick's comment",
                    "Country/Region",
                    "Company size"
                FROM external_data.hubspot_crm_exports_all_contacts_2025_06_26
                ORDER BY "Record ID"
                {limit_clause}
            """)
            
            batch = []
            for row in cur:
                batch.append(row)
                
                if len(batch) >= options['batch_size']:
                    self.process_contact_batch(batch, options)
                    batch = []
            
            # Process remaining records
            if batch:
                self.process_contact_batch(batch, options)
                
        finally:
            cur.close()
    
    def process_contact_batch(self, batch: List[Tuple], options):
        """Process a batch of contact records."""
        for row in batch:
            self.stats['contacts_processed'] += 1
            
            try:
                (record_id, first_name, last_name, city, create_date, email,
                 next_step, nicks_comment, country, company_size) = row
                
                # Skip if no email
                if not email:
                    self.stats['contacts_skipped'] += 1
                    continue
                
                # Convert dates
                created_at = convert_excel_date(create_date) if create_date else timezone.now()
                
                # Map fields
                country_code = map_country_to_iso(country)
                
                # Combine notes
                notes_parts = []
                if nicks_comment:
                    notes_parts.append(f"Nick's comment: {nicks_comment}")
                if next_step:
                    notes_parts.append(f"Next step: {next_step}")
                notes = "\n\n".join(notes_parts)
                
                # Prepare contact data
                contact_data = {
                    'email': email.lower()[:254],  # Ensure it fits in field
                    'first_name': (first_name or '')[:100],
                    'last_name': (last_name or '')[:100],
                    'city': (city or '')[:100],
                    'country': country_code,
                    'contact_type': ContactType.INDIVIDUAL,
                    'status': ContactStatus.LEAD,
                    'source': 'hubspot_import',
                    'notes': notes,
                    'assigned_to': self.default_user,
                    'custom_fields': {
                        'hubspot_id': str(record_id),
                        'company_size': company_size or '',
                        'original_create_date': str(create_date) if create_date else None,
                        'import_date': timezone.now().isoformat(),
                        'import_source': 'hubspot_export'
                    }
                }
                
                # If company size is provided, try to find or set company
                if company_size:
                    contact_data['company_name'] = company_size
                
                if not options['dry_run']:
                    with transaction.atomic():
                        # Check if contact already exists
                        existing = Contact.objects.filter(
                            group=self.group,
                            email__iexact=email
                        ).first()
                        
                        if existing:
                            if options['update_existing']:
                                # Update existing contact
                                for key, value in contact_data.items():
                                    if key == 'custom_fields':
                                        # Merge custom fields
                                        existing.custom_fields.update(value)
                                    elif key == 'notes':
                                        # Append notes if new
                                        if value and value not in existing.notes:
                                            existing.notes = f"{existing.notes}\n\n{value}".strip()
                                    else:
                                        setattr(existing, key, value)
                                
                                existing.updated_at = timezone.now()
                                existing.save()
                                self.stats['contacts_updated'] += 1
                            else:
                                self.stats['contacts_skipped'] += 1
                        else:
                            # Create new contact
                            contact = Contact.objects.create(
                                group=self.group,
                                created_at=created_at,
                                **contact_data
                            )
                            self.stats['contacts_created'] += 1
                else:
                    # Dry run - just count what would happen
                    existing = Contact.objects.filter(
                        group=self.group,
                        email__iexact=email
                    ).exists()
                    
                    if existing and not options['update_existing']:
                        self.stats['contacts_skipped'] += 1
                    elif existing:
                        self.stats['contacts_updated'] += 1
                    else:
                        self.stats['contacts_created'] += 1
                
                # Progress indicator
                if self.stats['contacts_processed'] % 100 == 0:
                    self.stdout.write(f"  Processed {self.stats['contacts_processed']} contacts...")
                    
            except Exception as e:
                error_msg = f"Error processing contact {record_id}: {str(e)}"
                logger.error(error_msg)
                self.stats['errors'].append(error_msg)
    
    def print_summary(self):
        """Print import summary."""
        self.stdout.write("\n" + "="*60)
        self.stdout.write("IMPORT SUMMARY")
        self.stdout.write("="*60)
        
        self.stdout.write(f"\nCompanies:")
        self.stdout.write(f"  Processed: {self.stats['companies_processed']}")
        self.stdout.write(f"  Created:   {self.stats['companies_created']}")
        self.stdout.write(f"  Updated:   {self.stats['companies_updated']}")
        self.stdout.write(f"  Skipped:   {self.stats['companies_skipped']}")
        
        self.stdout.write(f"\nContacts:")
        self.stdout.write(f"  Processed: {self.stats['contacts_processed']}")
        self.stdout.write(f"  Created:   {self.stats['contacts_created']}")
        self.stdout.write(f"  Updated:   {self.stats['contacts_updated']}")
        self.stdout.write(f"  Skipped:   {self.stats['contacts_skipped']}")
        
        if self.stats['errors']:
            self.stdout.write(f"\nErrors ({len(self.stats['errors'])}):")
            for error in self.stats['errors'][:10]:  # Show first 10 errors
                self.stdout.write(f"  - {error}")
            if len(self.stats['errors']) > 10:
                self.stdout.write(f"  ... and {len(self.stats['errors']) - 10} more errors")
        
        self.stdout.write("\n" + "="*60)