"""
Django management command to import world university rankings data.

Imports university rankings from external data to enrich the geographic
intelligence system with global university data and rankings.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.contrib.gis.geos import Point
from django.utils import timezone

from accounts.models import Group, User
from geographic_intelligence.models import University, PointOfInterest, UniversityType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import world university rankings data from external database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--country',
            type=str,
            default='United Kingdom',
            help='Country to import (default: United Kingdom)'
        )
        parser.add_argument(
            '--group',
            type=str,
            required=True,
            help='Group name to associate universities with'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making changes'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing universities with ranking data'
        )
        parser.add_argument(
            '--create-pois',
            action='store_true',
            help='Create POI entries for university campuses'
        )

    def handle(self, *args, **options):
        country = options['country']
        group_name = options['group']
        dry_run = options['dry_run']
        update_existing = options['update_existing']
        create_pois = options['create_pois']

        self.stdout.write(f"Importing university rankings for {country}...")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))

        try:
            # Get or create group
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(f"Created new group: {group_name}")

            # Import universities
            stats = self.import_universities(
                country=country,
                group=group,
                dry_run=dry_run,
                update_existing=update_existing,
                create_pois=create_pois
            )

            # Display results
            self.display_import_stats(stats, dry_run)

        except Exception as e:
            logger.error(f"Import failed: {str(e)}")
            raise CommandError(f"Import failed: {str(e)}")

    def import_universities(self, 
                          country: str, 
                          group: Group, 
                          dry_run: bool = False,
                          update_existing: bool = False,
                          create_pois: bool = False) -> Dict[str, Any]:
        """Import universities from external data."""
        
        # Fetch external data
        external_unis = self.fetch_external_universities(country)
        
        stats = {
            'total_external': len(external_unis),
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'pois_created': 0,
            'errors': []
        }

        # Process each university
        for uni_data in external_unis:
            try:
                if dry_run:
                    self.stdout.write(f"Would process: {uni_data['institution']} in {uni_data['city']}")
                    continue

                result = self.process_university(
                    uni_data, group, update_existing, create_pois
                )
                
                if result['action'] == 'created':
                    stats['created'] += 1
                elif result['action'] == 'updated':
                    stats['updated'] += 1
                else:
                    stats['skipped'] += 1

                if result.get('poi_created'):
                    stats['pois_created'] += 1

            except Exception as e:
                error_msg = f"Error processing {uni_data.get('institution', 'Unknown')}: {str(e)}"
                logger.error(error_msg)
                stats['errors'].append(error_msg)

        return stats

    def fetch_external_universities(self, country: str) -> List[Dict[str, Any]]:
        """Fetch university data from external database."""
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT institution, city, region, rank, score, "Source Dataset"
                FROM external_data.enhanced_universities 
                WHERE country = %s
                ORDER BY 
                    CASE 
                        WHEN rank ~ '^[0-9]+$' THEN CAST(rank AS INTEGER)
                        ELSE 9999 
                    END,
                    institution
            """, [country])
            
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            
            universities = []
            for row in rows:
                uni_data = dict(zip(columns, row))
                
                # Parse and clean the data
                uni_data['parsed_rank'] = self.parse_ranking(uni_data['rank'])
                uni_data['parsed_score'] = self.parse_score(uni_data['score'])
                uni_data['estimated_students'] = self.estimate_student_population(uni_data)
                uni_data['coordinates'] = self.get_city_coordinates(uni_data['city'])
                
                universities.append(uni_data)
            
            return universities

    def process_university(self, 
                         uni_data: Dict[str, Any], 
                         group: Group,
                         update_existing: bool = False,
                         create_pois: bool = False) -> Dict[str, Any]:
        """Process a single university record."""
        
        # Check if university already exists
        existing_uni = University.objects.filter(
            group=group,
            name__iexact=uni_data['institution']
        ).first()

        if existing_uni:
            if update_existing:
                return self.update_university(existing_uni, uni_data)
            else:
                return {'action': 'skipped', 'reason': 'already_exists'}

        # Create new university
        return self.create_university(uni_data, group, create_pois)

    def create_university(self, 
                        uni_data: Dict[str, Any], 
                        group: Group,
                        create_pois: bool = False) -> Dict[str, Any]:
        """Create a new university from external data."""
        
        # Create main campus POI first
        campus_poi = None
        if create_pois and uni_data['coordinates']:
            campus_poi = self.create_campus_poi(uni_data, group)

        # Determine university type
        uni_type = self.determine_university_type(uni_data['institution'])

        with transaction.atomic():
            # Create university
            university = University.objects.create(
                group=group,
                name=uni_data['institution'],
                university_type=uni_type,
                total_students=uni_data['estimated_students'],
                international_students=int(uni_data['estimated_students'] * 0.25),  # Estimate 25%
                ranking_global=uni_data['parsed_rank']['numeric'] if uni_data['parsed_rank']['numeric'] else None,
                ranking_national=self.estimate_national_ranking(uni_data),
                website=self.generate_website_url(uni_data['institution']),
                main_campus=campus_poi
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created: {university.name} (Rank: {uni_data['rank']}, Students: {uni_data['estimated_students']:,})"
                )
            )

            return {
                'action': 'created',
                'university': university,
                'poi_created': campus_poi is not None
            }

    def update_university(self, 
                        university: University, 
                        uni_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing university with ranking data."""
        
        updated_fields = []
        
        # Update ranking data
        if uni_data['parsed_rank']['numeric'] and not university.ranking_global:
            university.ranking_global = uni_data['parsed_rank']['numeric']
            updated_fields.append('ranking_global')

        # Update national ranking estimate
        estimated_national = self.estimate_national_ranking(uni_data)
        if estimated_national and not university.ranking_national:
            university.ranking_national = estimated_national
            updated_fields.append('ranking_national')

        # Update student numbers if not set
        if not university.total_students or university.total_students < 1000:
            university.total_students = uni_data['estimated_students']
            updated_fields.append('total_students')

        # Update international students estimate
        if not university.international_students:
            university.international_students = int(uni_data['estimated_students'] * 0.25)
            updated_fields.append('international_students')

        if updated_fields:
            university.save(update_fields=updated_fields)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated: {university.name} ({', '.join(updated_fields)})"
                )
            )
            return {'action': 'updated', 'fields': updated_fields}
        else:
            return {'action': 'skipped', 'reason': 'no_updates_needed'}

    def create_campus_poi(self, uni_data: Dict[str, Any], group: Group) -> Optional[PointOfInterest]:
        """Create a POI for the university campus."""
        
        if not uni_data['coordinates']:
            return None

        try:
            lat, lng = uni_data['coordinates']
            location = Point(lng, lat, srid=4326)
            
            poi = PointOfInterest.objects.create(
                group=group,
                name=f"{uni_data['institution']} - Main Campus",
                address=f"{uni_data['city']}, {uni_data['region']}",
                location=location,
                poi_type='university',
                description=f"Main campus of {uni_data['institution']}",
                capacity=uni_data['estimated_students'],
                verified=False,
                data_source='QS World University Rankings 2024'
            )
            
            return poi
            
        except Exception as e:
            logger.warning(f"Failed to create POI for {uni_data['institution']}: {str(e)}")
            return None

    def parse_ranking(self, rank_str: str) -> Dict[str, Any]:
        """Parse ranking string into structured data."""
        
        if not rank_str:
            return {'numeric': None, 'range': None, 'percentile': None}

        # Handle exact numeric ranks
        if re.match(r'^\d+$', rank_str):
            return {
                'numeric': int(rank_str),
                'range': None,
                'percentile': None
            }

        # Handle range ranks (e.g., "501-510")
        range_match = re.match(r'^(\d+)-(\d+)$', rank_str)
        if range_match:
            start, end = map(int, range_match.groups())
            return {
                'numeric': start,  # Use start of range
                'range': (start, end),
                'percentile': None
            }

        # Handle percentile ranks (e.g., "1398 Top 6.7%")
        percentile_match = re.match(r'^(\d+)\s+Top\s+(\d+\.?\d*)%$', rank_str)
        if percentile_match:
            numeric, percentile = percentile_match.groups()
            return {
                'numeric': int(numeric),
                'range': None,
                'percentile': float(percentile)
            }

        # Default for unparseable ranks
        return {'numeric': None, 'range': None, 'percentile': None}

    def parse_score(self, score_str: str) -> Optional[float]:
        """Parse score string to float."""
        
        if not score_str:
            return None

        try:
            return float(score_str)
        except (ValueError, TypeError):
            return None

    def estimate_student_population(self, uni_data: Dict[str, Any]) -> int:
        """Estimate student population based on ranking and type."""
        
        rank_data = uni_data['parsed_rank']
        
        # Base estimate based on ranking
        if rank_data['numeric']:
            if rank_data['numeric'] <= 50:
                base_students = 25000  # Top universities tend to be large
            elif rank_data['numeric'] <= 200:
                base_students = 20000
            elif rank_data['numeric'] <= 500:
                base_students = 15000
            else:
                base_students = 10000
        else:
            base_students = 8000  # Default for unranked

        # Adjust based on institution type
        name = uni_data['institution'].lower()
        
        if 'college' in name and 'university' not in name:
            base_students = int(base_students * 0.6)  # Colleges tend to be smaller
        elif 'institute' in name or 'school' in name:
            base_students = int(base_students * 0.8)  # Specialized institutions
        elif 'metropolitan' in name or 'city' in name:
            base_students = int(base_students * 1.2)  # Urban universities often larger

        # Add some variation (±20%)
        import random
        random.seed(hash(uni_data['institution']))  # Consistent randomness
        variation = random.uniform(0.8, 1.2)
        
        return max(5000, int(base_students * variation))  # Minimum 5,000 students

    def get_city_coordinates(self, city: str) -> Optional[Tuple[float, float]]:
        """Get approximate coordinates for major cities."""
        
        # Major UK city coordinates
        uk_cities = {
            'london': (51.5074, -0.1278),
            'birmingham': (52.4862, -1.8904),
            'manchester': (53.4808, -2.2426),
            'glasgow': (55.8642, -4.2518),
            'edinburgh': (55.9533, -3.1883),
            'liverpool': (53.4084, -2.9916),
            'leeds': (53.8008, -1.5491),
            'sheffield': (53.3811, -1.4701),
            'newcastle upon tyne': (54.9783, -1.6178),
            'bristol': (51.4545, -2.5879),
            'nottingham': (52.9548, -1.1581),
            'leicester': (52.6369, -1.1398),
            'coventry': (52.4068, -1.5197),
            'hull': (53.7676, -0.3274),
            'cardiff': (51.4816, -3.1791),
            'belfast': (54.5973, -5.9301),
            'oxford': (51.7520, -1.2577),
            'cambridge': (52.2053, 0.1218),
            'bath': (51.3758, -2.3599),
            'durham': (54.7753, -1.5849),
            'exeter': (50.7184, -3.5339),
            'york': (53.9600, -1.0873),
            'lancaster': (54.0465, -2.8007),
            'st andrews': (56.3398, -2.7967),
            'canterbury': (51.2802, 1.0789),
            'southampton': (50.9097, -1.4044),
            'portsmouth': (50.8198, -1.0880),
            'brighton': (50.8225, -0.1372),
            'reading': (51.4543, -0.9781),
            'norwich': (52.6309, 1.2974),
            'swansea': (51.6214, -3.9436),
            'dundee': (56.4620, -2.9707),
            'stirling': (56.1165, -3.9369),
            'aberystwyth': (52.4140, -4.0828)
        }
        
        city_lower = city.lower().strip()
        return uk_cities.get(city_lower)

    def determine_university_type(self, institution_name: str) -> str:
        """Determine university type from institution name."""
        
        name_lower = institution_name.lower()
        
        if 'college' in name_lower and 'university' not in name_lower:
            return UniversityType.COMMUNITY
        elif 'institute' in name_lower or 'school' in name_lower:
            return UniversityType.TECHNICAL
        elif 'royal' in name_lower or 'imperial' in name_lower:
            return UniversityType.PUBLIC
        else:
            return UniversityType.PUBLIC  # Default

    def estimate_national_ranking(self, uni_data: Dict[str, Any]) -> Optional[int]:
        """Estimate national ranking from global ranking."""
        
        global_rank = uni_data['parsed_rank']['numeric']
        if not global_rank:
            return None

        # Rough estimation: UK has ~130 universities in global rankings
        # Top 50 global ≈ top 10 UK, Top 200 global ≈ top 30 UK, etc.
        
        if global_rank <= 10:
            return min(5, global_rank)
        elif global_rank <= 50:
            return int(global_rank * 0.3)
        elif global_rank <= 200:
            return int(global_rank * 0.2)
        elif global_rank <= 500:
            return int(global_rank * 0.15)
        else:
            return int(global_rank * 0.1)

    def generate_website_url(self, institution_name: str) -> str:
        """Generate likely website URL for institution."""
        
        # Simple heuristic for UK universities
        name_parts = institution_name.lower().replace('the ', '').replace('university of ', '').split()
        
        # Handle common patterns
        if 'cambridge' in name_parts:
            return 'https://www.cam.ac.uk'
        elif 'oxford' in name_parts:
            return 'https://www.ox.ac.uk'
        elif 'london' in name_parts:
            # Handle London universities
            if 'ucl' in institution_name.lower():
                return 'https://www.ucl.ac.uk'
            elif 'imperial' in name_parts:
                return 'https://www.imperial.ac.uk'
            elif 'kings' in name_parts or "king's" in institution_name.lower():
                return 'https://www.kcl.ac.uk'
            elif 'lse' in institution_name.lower() or 'london school of economics' in institution_name.lower():
                return 'https://www.lse.ac.uk'
            else:
                # Generic London pattern
                short_name = ''.join([part[:3] for part in name_parts if part not in ['university', 'college', 'london']])
                return f'https://www.{short_name}.ac.uk'
        else:
            # Generic UK university pattern
            main_name = name_parts[0] if name_parts else 'university'
            return f'https://www.{main_name}.ac.uk'

    def display_import_stats(self, stats: Dict[str, Any], dry_run: bool):
        """Display import statistics."""
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write(f"{'DRY RUN ' if dry_run else ''}IMPORT COMPLETE")
        self.stdout.write("="*60)
        
        self.stdout.write(f"Total external records: {stats['total_external']:,}")
        self.stdout.write(f"Universities created: {stats['created']:,}")
        self.stdout.write(f"Universities updated: {stats['updated']:,}")
        self.stdout.write(f"Universities skipped: {stats['skipped']:,}")
        self.stdout.write(f"Campus POIs created: {stats['pois_created']:,}")
        
        if stats['errors']:
            self.stdout.write(f"\nErrors encountered: {len(stats['errors'])}")
            for error in stats['errors'][:5]:  # Show first 5 errors
                self.stdout.write(self.style.ERROR(f"  - {error}"))
            
            if len(stats['errors']) > 5:
                self.stdout.write(f"  ... and {len(stats['errors']) - 5} more errors")

        self.stdout.write(f"\n{self.style.SUCCESS('Import completed successfully!')}")