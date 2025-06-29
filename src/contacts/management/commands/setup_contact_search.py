"""
Management command to set up PostgreSQL full-text search for contacts.

Creates necessary indexes and extensions for efficient contact searching.
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Set up PostgreSQL full-text search indexes for contacts'

    def handle(self, *args, **options):
        """Create GIN indexes for full-text search on contacts."""
        
        with connection.cursor() as cursor:
            # Enable pg_trgm extension if not already enabled
            self.stdout.write('Enabling pg_trgm extension...')
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
            
            # Create GIN index for full-text search on contacts
            self.stdout.write('Creating full-text search index on contacts...')
            
            # Drop existing index if it exists
            cursor.execute("""
                DROP INDEX IF EXISTS idx_contacts_search;
            """)
            
            # Create new GIN index
            cursor.execute("""
                CREATE INDEX idx_contacts_search ON contacts 
                USING gin(
                    to_tsvector('english', 
                        COALESCE(first_name, '') || ' ' || 
                        COALESCE(last_name, '') || ' ' || 
                        COALESCE(company_name, '') || ' ' || 
                        COALESCE(email, '') || ' ' ||
                        COALESCE(city, '') || ' ' ||
                        COALESCE(notes, '')
                    )
                );
            """)
            
            # Create trigram index for similarity search
            self.stdout.write('Creating trigram index for similarity search...')
            
            cursor.execute("""
                DROP INDEX IF EXISTS idx_contacts_trigram;
            """)
            
            cursor.execute("""
                CREATE INDEX idx_contacts_trigram ON contacts
                USING gin(
                    (COALESCE(first_name, '') || ' ' || 
                     COALESCE(last_name, '') || ' ' || 
                     COALESCE(company_name, '') || ' ' || 
                     COALESCE(email, '')) gin_trgm_ops
                );
            """)
            
            # Create composite indexes for multi-tenant queries
            self.stdout.write('Creating composite indexes for performance...')
            
            # These might already exist from migrations, so use IF NOT EXISTS
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_contacts_group_email 
                ON contacts(group_id, email);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_contacts_group_status 
                ON contacts(group_id, status);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_contacts_group_score 
                ON contacts(group_id, current_score);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_contacts_group_activity 
                ON contacts(group_id, last_activity_at DESC);
            """)
            
            # Analyze tables to update statistics
            self.stdout.write('Analyzing tables...')
            cursor.execute("ANALYZE contacts;")
            
        self.stdout.write(
            self.style.SUCCESS('Successfully set up PostgreSQL full-text search for contacts')
        )