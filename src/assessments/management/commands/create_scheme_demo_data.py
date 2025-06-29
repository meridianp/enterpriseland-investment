"""
Management command to create demonstration PBSA scheme data.

Creates realistic demonstration schemes with comprehensive information
for testing and demonstration purposes.
"""

from decimal import Decimal
from datetime import date, datetime, timedelta
import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Group
from assessments.partner_models import DevelopmentPartner
from assessments.scheme_models import (
    PBSAScheme, SchemeLocationInformation, TargetUniversity, SchemeSiteInformation,
    DevelopmentStage, UniversityType, PlanningStatus
)
from assessments.scheme_economic_models import (
    SchemeEconomicInformation, AccommodationUnit, SchemeOperationalInformation,
    AccommodationType
)
from assessments.enums import Currency, RiskLevel, AreaUnit


class Command(BaseCommand):
    help = 'Create demonstration PBSA scheme data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--group-name',
            type=str,
            help='Name of the group to create schemes for (required)',
            required=True
        )
        
        parser.add_argument(
            '--scheme-count',
            type=int,
            default=3,
            help='Number of schemes to create (default: 3)'
        )
        
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Delete existing schemes before creating new ones'
        )
    
    def handle(self, *args, **options):
        group_name = options['group_name']
        scheme_count = options['scheme_count']
        clean = options['clean']
        
        try:
            group = Group.objects.get(name=group_name)
        except Group.DoesNotExist:
            raise CommandError(f'Group "{group_name}" does not exist')
        
        if clean:
            self.stdout.write('Cleaning existing schemes...')
            PBSAScheme.objects.filter(group=group).delete()
        
        # Ensure we have a developer
        developer, created = DevelopmentPartner.objects.get_or_create(
            group=group,
            company_name='Demo Student Developments Ltd',
            defaults={
                'assessment_priority': 'medium'
            }
        )
        
        if created:
            self.stdout.write(f'Created developer: {developer.company_name}')
        
        schemes_created = []
        
        try:
            with transaction.atomic():
                for i in range(scheme_count):
                    scheme = self._create_demo_scheme(group, developer, i + 1)
                    schemes_created.append(scheme)
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Created scheme: {scheme.scheme_name}')
                    )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Successfully created {len(schemes_created)} demonstration schemes'
                )
            )
            
            # Show summary
            self.stdout.write('\nScheme Summary:')
            for scheme in schemes_created:
                summary = scheme.get_scheme_summary()
                self.stdout.write(f'  • {scheme.scheme_name}:')
                self.stdout.write(f'    - {summary["total_beds"]} beds')
                self.stdout.write(f'    - {summary["development_stage"]}')
                self.stdout.write(f'    - Cost per bed: £{summary["cost_per_bed"]:,.0f}' if summary.get("cost_per_bed") else '    - Cost per bed: TBD')
        
        except Exception as e:
            raise CommandError(f'Error creating schemes: {str(e)}')
    
    def _create_demo_scheme(self, group, developer, index):
        """Create a single demonstration scheme with full information."""
        
        # Demo scheme configurations
        scheme_configs = [
            {
                'name': 'Cambridge Innovation Quarter',
                'city': 'Cambridge',
                'country': 'GB',
                'beds': 450,
                'units': 180,
                'stage': DevelopmentStage.CONSTRUCTION,
                'cost': Decimal('28000000'),
                'universities': [
                    {
                        'name': 'University of Cambridge',
                        'type': UniversityType.RUSSELL_GROUP,
                        'distance': Decimal('0.6'),
                        'students': 24000,
                        'international_pct': Decimal('38')
                    },
                    {
                        'name': 'Anglia Ruskin University',
                        'type': UniversityType.MODERN,
                        'distance': Decimal('1.2'),
                        'students': 17000,
                        'international_pct': Decimal('25')
                    }
                ],
                'location_type': 'city_centre',
                'planning': PlanningStatus.APPROVED,
                'avg_rent': Decimal('210')
            },
            {
                'name': 'Edinburgh Student Village',
                'city': 'Edinburgh',
                'country': 'GB',
                'beds': 600,
                'units': 240,
                'stage': DevelopmentStage.PLANNING,
                'cost': Decimal('35000000'),
                'universities': [
                    {
                        'name': 'University of Edinburgh',
                        'type': UniversityType.RUSSELL_GROUP,
                        'distance': Decimal('0.8'),
                        'students': 35000,
                        'international_pct': Decimal('42')
                    },
                    {
                        'name': 'Edinburgh Napier University',
                        'type': UniversityType.MODERN,
                        'distance': Decimal('1.5'),
                        'students': 19000,
                        'international_pct': Decimal('30')
                    }
                ],
                'location_type': 'campus_adjacent',
                'planning': PlanningStatus.UNDER_REVIEW,
                'avg_rent': Decimal('195')
            },
            {
                'name': 'Manchester Central Residences',
                'city': 'Manchester',
                'country': 'GB',
                'beds': 380,
                'units': 150,
                'stage': DevelopmentStage.OPERATIONAL,
                'cost': Decimal('22000000'),
                'universities': [
                    {
                        'name': 'University of Manchester',
                        'type': UniversityType.RUSSELL_GROUP,
                        'distance': Decimal('0.4'),
                        'students': 40000,
                        'international_pct': Decimal('35')
                    },
                    {
                        'name': 'Manchester Metropolitan University',
                        'type': UniversityType.MODERN,
                        'distance': Decimal('0.9'),
                        'students': 38000,
                        'international_pct': Decimal('22')
                    }
                ],
                'location_type': 'city_centre',
                'planning': PlanningStatus.APPROVED,
                'avg_rent': Decimal('175')
            }
        ]
        
        # Use config based on index, cycling through if needed
        config = scheme_configs[(index - 1) % len(scheme_configs)]
        
        # Adjust name if multiple schemes
        scheme_name = config['name']
        if index > len(scheme_configs):
            scheme_name += f' Phase {index - len(scheme_configs) + 1}'
        
        # Create main scheme
        scheme = PBSAScheme.objects.create(
            group=group,
            scheme_name=scheme_name,
            scheme_reference=f'DEMO-{index:03d}',
            developer=developer,
            total_beds=config['beds'],
            total_units=config['units'],
            development_stage=config['stage'],
            total_development_cost_amount=config['cost'],
            total_development_cost_currency=Currency.GBP,
            expected_completion_date=date.today() + timedelta(days=random.randint(180, 720)),
            construction_start_date=date.today() - timedelta(days=random.randint(30, 365)) if config['stage'] in [DevelopmentStage.CONSTRUCTION, DevelopmentStage.OPERATIONAL] else None,
            operational_start_date=date.today() - timedelta(days=random.randint(1, 180)) if config['stage'] == DevelopmentStage.OPERATIONAL else None
        )
        
        # Create location information
        location_info = SchemeLocationInformation.objects.create(
            group=group,
            scheme=scheme,
            address=f"University Quarter, {config['city']}",
            city=config['city'],
            region=self._get_region_for_city(config['city']),
            country=config['country'],
            postcode=self._generate_postcode(config['city']),
            location_type=config['location_type'],
            nearest_train_station=f"{config['city']} Central",
            train_station_distance_km=Decimal(str(random.uniform(0.3, 2.0))),
            public_transport_rating=random.randint(3, 5),
            competitive_schemes_nearby=random.randint(2, 6),
            total_student_population=sum(uni['students'] for uni in config['universities'])
        )
        
        # Create target universities
        for uni_config in config['universities']:
            TargetUniversity.objects.create(
                group=group,
                location_info=location_info,
                university_name=uni_config['name'],
                university_type=uni_config['type'],
                distance_to_campus_km=uni_config['distance'],
                walking_time_minutes=int(float(uni_config['distance']) * 12),  # ~12 min per km
                cycling_time_minutes=int(float(uni_config['distance']) * 4),   # ~4 min per km
                public_transport_time_minutes=int(float(uni_config['distance']) * 8) + 5,  # ~8 min per km + wait
                total_student_population=uni_config['students'],
                international_student_pct=uni_config['international_pct'],
                postgraduate_student_pct=Decimal(str(random.uniform(20, 40))),
                university_provided_beds=int(uni_config['students'] * random.uniform(0.15, 0.35)),
                accommodation_satisfaction_rating=random.randint(2, 4),
                estimated_demand_capture_pct=Decimal(str(random.uniform(8, 18)))
            )
        
        # Create site information
        SchemeSiteInformation.objects.create(
            group=group,
            scheme=scheme,
            site_area_value=Decimal(str(config['beds'] * random.uniform(8, 15))),  # 8-15 sqm per bed
            site_area_unit=AreaUnit.SQ_M,
            site_configuration=random.choice(['regular', 'corner', 'irregular']),
            plot_ratio=Decimal(str(random.uniform(1.5, 3.5))),
            building_coverage_pct=Decimal(str(random.uniform(30, 50))),
            max_height_stories=random.randint(6, 12),
            topography=random.choice(['flat', 'gentle_slope']),
            ground_conditions=random.choice(['good', 'excellent']),
            contamination_risk=random.choice([RiskLevel.LOW, RiskLevel.MEDIUM]),
            flood_risk=random.choice([RiskLevel.LOW, RiskLevel.MEDIUM]),
            planning_status=config['planning'],
            planning_reference=f"{config['city'][:2].upper()}/2024/{index:03d}",
            planning_submission_date=date.today() - timedelta(days=random.randint(90, 365)),
            planning_decision_date=date.today() - timedelta(days=random.randint(30, 180)) if config['planning'] in [PlanningStatus.APPROVED, PlanningStatus.CONDITIONS] else None,
            utilities_available={
                'electricity': True,
                'gas': True,
                'water': True,
                'drainage': True,
                'telecoms': True,
                'district_heating': random.choice([True, False])
            }
        )
        
        # Create economic information
        total_cost = config['cost']
        land_cost = total_cost * Decimal('0.25')  # ~25% for land
        construction_cost = total_cost * Decimal('0.65')  # ~65% for construction
        other_costs = total_cost * Decimal('0.10')  # ~10% for other costs
        
        SchemeEconomicInformation.objects.create(
            group=group,
            scheme=scheme,
            land_cost_amount=land_cost,
            land_cost_currency=Currency.GBP,
            construction_cost_amount=construction_cost,
            construction_cost_currency=Currency.GBP,
            professional_fees_amount=other_costs * Decimal('0.6'),
            professional_fees_currency=Currency.GBP,
            finance_costs_amount=other_costs * Decimal('0.3'),
            finance_costs_currency=Currency.GBP,
            contingency_amount=other_costs * Decimal('0.1'),
            contingency_currency=Currency.GBP,
            avg_rent_per_bed_per_week=config['avg_rent'],
            rent_currency=Currency.GBP,
            occupancy_rate_pct=Decimal(str(random.uniform(92, 98))),
            rental_growth_rate_pct=Decimal(str(random.uniform(2.5, 4.5))),
            ancillary_income_per_bed_per_year=Decimal(str(random.uniform(200, 400))),
            operating_cost_per_bed_per_year=Decimal(str(random.uniform(1000, 1800))),
            management_fee_pct=Decimal(str(random.uniform(6, 10))),
            maintenance_cost_per_bed_per_year=Decimal(str(random.uniform(600, 1200))),
            target_gross_yield_pct=Decimal(str(random.uniform(5.5, 7.5))),
            projected_irr_pct=Decimal(str(random.uniform(10, 16))),
            market_rent_per_bed_per_week=config['avg_rent'] * Decimal(str(random.uniform(0.95, 1.05)))
        )
        
        # Create accommodation units
        self._create_accommodation_units(group, scheme, config)
        
        # Create operational information
        SchemeOperationalInformation.objects.create(
            group=group,
            scheme=scheme,
            management_model=random.choice(['self_managed', 'third_party', 'hybrid']),
            management_company='Student Accommodation Management Ltd' if random.choice([True, False]) else '',
            on_site_staff_count=max(2, int(config['beds'] / 80)),  # ~1 staff per 80 beds
            has_24_7_reception=config['beds'] > 400,
            has_security=True,
            security_type=random.choice(['access_control', 'security_guard', 'full_security']),
            cleaning_service=random.choice(['common_areas', 'weekly_rooms']),
            laundry_facilities='shared_card',
            internet_provision=random.choice(['high_speed', 'premium']),
            has_gym=config['beds'] > 300,
            has_study_rooms=True,
            has_social_spaces=True,
            has_cinema_room=config['beds'] > 400,
            has_outdoor_space=random.choice([True, False]),
            smart_building_features=['keyless_entry', 'climate_control'] + (
                ['energy_monitoring'] if random.choice([True, False]) else []
            ),
            mobile_app_features=['booking', 'payments'] + (
                ['maintenance_requests', 'community'] if random.choice([True, False]) else []
            ),
            sustainability_features=['led_lighting', 'efficient_heating'] + (
                ['solar_panels'] if random.choice([True, False]) else []
            ),
            target_occupancy_rate_pct=Decimal(str(random.uniform(94, 98))),
            average_lease_length_months=random.choice([44, 52]),  # Academic year or full year
            student_satisfaction_target=random.randint(4, 5),
            estimated_operating_cost_per_bed=Decimal(str(random.uniform(1200, 2000))),
            utilities_included_in_rent=True
        )
        
        # Update cached fields
        scheme.update_cached_fields()
        
        return scheme
    
    def _create_accommodation_units(self, group, scheme, config):
        """Create diverse accommodation units for the scheme."""
        total_beds = config['beds']
        avg_rent = config['avg_rent']
        
        # Create different unit types with varying proportions
        units_config = [
            {
                'type': AccommodationType.STUDIO,
                'name': 'Premium Studio',
                'beds_per_unit': 1,
                'proportion': 0.4,  # 40% of beds
                'rent_multiplier': 1.2,
                'area_sqm': 25
            },
            {
                'type': AccommodationType.CLUSTER_FLAT,
                'name': '5-Bed Cluster',
                'beds_per_unit': 5,
                'proportion': 0.35,  # 35% of beds
                'rent_multiplier': 0.9,
                'area_sqm': 80
            },
            {
                'type': AccommodationType.ENSUITE,
                'name': 'En-suite Room',
                'beds_per_unit': 1,
                'proportion': 0.25,  # 25% of beds
                'rent_multiplier': 1.0,
                'area_sqm': 18
            }
        ]
        
        for unit_config in units_config:
            beds_for_type = int(total_beds * unit_config['proportion'])
            units_count = beds_for_type // unit_config['beds_per_unit']
            
            if units_count > 0:
                AccommodationUnit.objects.create(
                    group=group,
                    scheme=scheme,
                    unit_type=unit_config['type'],
                    unit_name=unit_config['name'],
                    bed_count=unit_config['beds_per_unit'],
                    bathroom_count=1 if unit_config['beds_per_unit'] <= 2 else 2,
                    gross_floor_area_sqm=Decimal(str(unit_config['area_sqm'])),
                    bedroom_size_sqm=Decimal(str(unit_config['area_sqm'] / unit_config['beds_per_unit'] * 0.7)),
                    has_kitchen=unit_config['type'] in [AccommodationType.STUDIO, AccommodationType.CLUSTER_FLAT],
                    kitchen_type='private' if unit_config['type'] == AccommodationType.STUDIO else 'shared',
                    has_study_space=True,
                    has_storage=True,
                    furnishing_level='fully_furnished',
                    number_of_units=units_count,
                    rent_per_bed_per_week=avg_rent * unit_config['rent_multiplier'],
                    rent_currency=Currency.GBP,
                    competitive_rent_per_week=avg_rent * unit_config['rent_multiplier'] * Decimal(str(random.uniform(0.95, 1.05)))
                )
    
    def _get_region_for_city(self, city):
        """Get region for a given city."""
        city_regions = {
            'Cambridge': 'Cambridgeshire',
            'Edinburgh': 'Scotland',
            'Manchester': 'Greater Manchester',
            'London': 'Greater London',
            'Birmingham': 'West Midlands',
            'Bristol': 'Somerset',
            'Leeds': 'West Yorkshire',
            'Liverpool': 'Merseyside'
        }
        return city_regions.get(city, 'Unknown Region')
    
    def _generate_postcode(self, city):
        """Generate realistic postcode for a city."""
        city_postcodes = {
            'Cambridge': f'CB{random.randint(1,4)} {random.randint(0,9)}{random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}{random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}',
            'Edinburgh': f'EH{random.randint(1,17)} {random.randint(0,9)}{random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}{random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}',
            'Manchester': f'M{random.randint(1,35)} {random.randint(0,9)}{random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}{random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}',
        }
        return city_postcodes.get(city, f'{city[:2].upper()}{random.randint(1,9)} {random.randint(0,9)}AB')