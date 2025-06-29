"""
Django management command to create demo geographic intelligence data.

Creates sample neighborhoods, POIs, and market analysis data for testing
and demonstration of the geographic intelligence system.
"""

import random
import logging
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.gis.geos import Point, Polygon
from django.utils import timezone

from accounts.models import Group
from geographic_intelligence.models import (
    PointOfInterest, University, Neighborhood, NeighborhoodMetrics,
    PBSAMarketAnalysis, POIType, UniversityType
)
from geographic_intelligence.services import NeighborhoodScoringService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create demo geographic intelligence data for testing and demonstration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--group',
            type=str,
            required=True,
            help='Group name to associate data with'
        )
        parser.add_argument(
            '--cities',
            type=str,
            nargs='+',
            default=['London', 'Manchester', 'Birmingham', 'Edinburgh'],
            help='Cities to create demo data for'
        )
        parser.add_argument(
            '--pois-per-city',
            type=int,
            default=50,
            help='Number of POIs to create per city'
        )
        parser.add_argument(
            '--neighborhoods-per-city',
            type=int,
            default=10,
            help='Number of neighborhoods to create per city'
        )

    def handle(self, *args, **options):
        group_name = options['group']
        cities = options['cities']
        pois_per_city = options['pois_per_city']
        neighborhoods_per_city = options['neighborhoods_per_city']

        self.stdout.write(f"Creating demo geographic data for {len(cities)} cities...")

        try:
            # Get group
            group = Group.objects.get(name=group_name)
            
            stats = {
                'pois_created': 0,
                'neighborhoods_created': 0,
                'market_analyses_created': 0
            }

            for city in cities:
                city_stats = self.create_city_data(
                    city, group, pois_per_city, neighborhoods_per_city
                )
                
                for key in stats:
                    stats[key] += city_stats.get(key, 0)

            self.display_stats(stats)

        except Group.DoesNotExist:
            raise CommandError(f"Group '{group_name}' does not exist")
        except Exception as e:
            logger.error(f"Demo data creation failed: {str(e)}")
            raise CommandError(f"Demo data creation failed: {str(e)}")

    def create_city_data(self, 
                        city: str, 
                        group: Group, 
                        pois_per_city: int,
                        neighborhoods_per_city: int) -> Dict[str, int]:
        """Create demo data for a specific city."""
        
        self.stdout.write(f"\nCreating data for {city}...")
        
        # Get city coordinates and universities
        city_info = self.get_city_info(city)
        if not city_info:
            self.stdout.write(f"No city info found for {city}, skipping...")
            return {}

        universities = University.objects.filter(
            group=group,
            main_campus__address__icontains=city
        )

        if not universities.exists():
            self.stdout.write(f"No universities found for {city}, skipping...")
            return {}

        stats = {
            'pois_created': 0,
            'neighborhoods_created': 0,
            'market_analyses_created': 0
        }

        # Create POIs
        pois_created = self.create_city_pois(city, city_info, group, pois_per_city)
        stats['pois_created'] = pois_created

        # Create neighborhoods
        neighborhoods_created = self.create_city_neighborhoods(
            city, city_info, group, universities, neighborhoods_per_city
        )
        stats['neighborhoods_created'] = neighborhoods_created

        # Create market analysis
        if neighborhoods_created > 0:
            analysis = self.create_market_analysis(city, group, universities)
            if analysis:
                stats['market_analyses_created'] = 1

        self.stdout.write(
            f"  {city}: {stats['pois_created']} POIs, "
            f"{stats['neighborhoods_created']} neighborhoods, "
            f"{stats['market_analyses_created']} market analysis"
        )

        return stats

    def create_city_pois(self, 
                        city: str, 
                        city_info: Dict, 
                        group: Group, 
                        count: int) -> int:
        """Create sample POIs for a city."""
        
        center_lat, center_lng = city_info['coordinates']
        created_count = 0

        # POI templates for different types
        poi_templates = {
            'grocery': ['Tesco', 'Sainsbury\'s', 'ASDA', 'Morrisons', 'Lidl', 'Aldi', 'M&S Food'],
            'restaurant': ['Pizza Express', 'Nando\'s', 'Wagamama', 'Five Guys', 'KFC', 'McDonald\'s'],
            'shopping': ['Westfield', 'John Lewis', 'Next', 'H&M', 'Zara', 'Primark'],
            'transport': ['Central Station', 'Bus Station', 'Metro Station'],
            'metro': ['Underground Station', 'Tube Station', 'Metro Stop'],
            'bus': ['Bus Stop', 'Bus Terminal', 'Transport Hub'],
            'library': ['Central Library', 'Community Library', 'University Library'],
            'sports': ['Sports Centre', 'Gym', 'Swimming Pool', 'Tennis Club'],
            'healthcare': ['NHS Walk-in Centre', 'Medical Centre', 'Hospital'],
            'park': ['City Park', 'Community Garden', 'Recreation Ground'],
            'nightlife': ['Student Bar', 'Pub', 'Club', 'Entertainment Complex']
        }

        # Create POIs distributed around the city
        for i in range(count):
            poi_type = random.choice(list(poi_templates.keys()))
            template_name = random.choice(poi_templates[poi_type])
            
            # Generate random location within city bounds (roughly 10km radius)
            lat_offset = random.uniform(-0.05, 0.05)  # ~5km
            lng_offset = random.uniform(-0.05, 0.05)
            
            poi_lat = center_lat + lat_offset
            poi_lng = center_lng + lng_offset
            
            # Generate address
            street_names = ['High Street', 'Main Road', 'Victoria Street', 'Church Lane', 
                          'Mill Street', 'Queen Street', 'King Street', 'Market Square']
            address = f"{random.randint(1, 200)} {random.choice(street_names)}, {city}"
            
            try:
                poi = PointOfInterest.objects.create(
                    group=group,
                    name=f"{template_name} - {city}",
                    address=address,
                    location=Point(poi_lng, poi_lat, srid=4326),
                    poi_type=poi_type,
                    description=f"{template_name} located in {city}",
                    capacity=self.generate_poi_capacity(poi_type),
                    verified=random.choice([True, False]),
                    data_source='Demo Data Generator'
                )
                created_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to create POI: {str(e)}")

        return created_count

    def create_city_neighborhoods(self, 
                                 city: str, 
                                 city_info: Dict, 
                                 group: Group,
                                 universities: any,
                                 count: int) -> int:
        """Create sample neighborhoods for a city."""
        
        center_lat, center_lng = city_info['coordinates']
        created_count = 0

        # Neighborhood name templates
        neighborhood_suffixes = [
            'Central', 'North', 'South', 'East', 'West', 'Village', 'Quarter',
            'District', 'Gardens', 'Heights', 'Park', 'Common', 'Green'
        ]

        for i in range(count):
            # Generate neighborhood location
            lat_offset = random.uniform(-0.03, 0.03)  # ~3km radius
            lng_offset = random.uniform(-0.03, 0.03)
            
            neighborhood_lat = center_lat + lat_offset
            neighborhood_lng = center_lng + lng_offset
            
            # Create neighborhood boundary (approximate 1km square)
            boundary_size = 0.005  # ~0.5km
            boundary_coords = [
                (neighborhood_lng - boundary_size, neighborhood_lat - boundary_size),
                (neighborhood_lng + boundary_size, neighborhood_lat - boundary_size),
                (neighborhood_lng + boundary_size, neighborhood_lat + boundary_size),
                (neighborhood_lng - boundary_size, neighborhood_lat + boundary_size),
                (neighborhood_lng - boundary_size, neighborhood_lat - boundary_size)  # Close polygon
            ]
            
            boundary = Polygon(boundary_coords, srid=4326)
            
            # Generate neighborhood name
            base_names = [f"{city} {suffix}" for suffix in neighborhood_suffixes]
            if i < len(neighborhood_suffixes):
                name = f"{city} {neighborhood_suffixes[i]}"
            else:
                name = f"{city} Area {i+1}"

            try:
                # Create metrics first
                metrics = NeighborhoodMetrics.objects.create(
                    accessibility_score=random.uniform(40, 95),
                    university_proximity_score=random.uniform(50, 100),
                    amenities_score=random.uniform(45, 90),
                    affordability_score=random.uniform(30, 85),
                    safety_score=random.uniform(60, 95),
                    cultural_score=random.uniform(40, 90),
                    planning_feasibility_score=random.uniform(50, 95),
                    competition_score=random.uniform(30, 80),
                    overall_score=0.0,  # Will be calculated
                    transport_links_count=random.randint(2, 15),
                    amenities_count=random.randint(5, 25),
                    calculation_date=timezone.now(),
                    data_sources=['Demo Data Generator', 'Simulated POI Analysis']
                )
                
                # Calculate overall score
                metrics.calculate_overall_score()
                metrics.save()

                # Create neighborhood
                neighborhood = Neighborhood.objects.create(
                    group=group,
                    name=name,
                    description=f"Residential area in {city} with good student amenities",
                    boundaries=boundary,
                    area_sqkm=random.uniform(0.5, 2.5),
                    metrics=metrics,
                    historic_district=random.choice([True, False]) if random.random() < 0.2 else False,
                    planning_constraints=self.generate_planning_constraints(),
                    zoning_classification=random.choice(['R1', 'R2', 'R3', 'MU1', 'MU2']),
                    max_building_height_m=random.choice([15, 20, 25, 30, 45, 60]),
                    investment_rationale=self.generate_investment_rationale(name, metrics),
                    development_opportunities=random.randint(0, 5),
                    average_land_price_psf=Decimal(str(random.uniform(50, 200))),
                    primary_university=random.choice(universities) if universities and random.random() < 0.7 else None
                )
                
                created_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to create neighborhood: {str(e)}")

        return created_count

    def create_market_analysis(self, 
                              city: str, 
                              group: Group, 
                              universities: any) -> Optional[PBSAMarketAnalysis]:
        """Create a market analysis for the city."""
        
        try:
            # Calculate market metrics
            total_students = sum(uni.total_students for uni in universities)
            international_percentage = sum(
                uni.international_students or 0 for uni in universities
            ) / total_students * 100 if total_students > 0 else 20.0

            # Estimate existing beds
            existing_beds = random.randint(int(total_students * 0.1), int(total_students * 0.4))
            estimated_demand = int(total_students * 0.35)  # 35% need accommodation
            
            analysis = PBSAMarketAnalysis.objects.create(
                group=group,
                city=city,
                country='GB',
                total_student_population=total_students,
                international_student_percentage=international_percentage,
                existing_pbsa_beds=existing_beds,
                estimated_demand=estimated_demand,
                supply_demand_ratio=existing_beds / estimated_demand if estimated_demand > 0 else 1.0,
                average_rent_per_week=Decimal(str(random.uniform(120, 180))),
                market_summary=f"PBSA market analysis for {city} showing strong student demand.",
                key_trends=[
                    "Growing international student population",
                    "Limited supply of purpose-built accommodation",
                    "Strong rental demand in city center"
                ],
                opportunities=[
                    f"Develop {estimated_demand - existing_beds} additional beds",
                    "Target international student market",
                    "Focus on premium accommodation offerings"
                ],
                risks=[
                    "Competition from private rental market",
                    "Planning permission challenges",
                    "Economic uncertainty affecting student numbers"
                ],
                methodology="Simulated analysis based on university enrollment data",
                data_sources=[
                    "University enrollment databases",
                    "Student accommodation surveys",
                    "Market research reports"
                ]
            )
            
            return analysis
            
        except Exception as e:
            logger.warning(f"Failed to create market analysis for {city}: {str(e)}")
            return None

    def get_city_info(self, city: str) -> Optional[Dict]:
        """Get city information including coordinates."""
        
        city_data = {
            'London': {
                'coordinates': (51.5074, -0.1278),
                'region': 'Greater London'
            },
            'Manchester': {
                'coordinates': (53.4808, -2.2426),
                'region': 'Greater Manchester'
            },
            'Birmingham': {
                'coordinates': (52.4862, -1.8904),
                'region': 'West Midlands'
            },
            'Edinburgh': {
                'coordinates': (55.9533, -3.1883),
                'region': 'Scotland'
            },
            'Leeds': {
                'coordinates': (53.8008, -1.5491),
                'region': 'West Yorkshire'
            },
            'Glasgow': {
                'coordinates': (55.8642, -4.2518),
                'region': 'Scotland'
            },
            'Bristol': {
                'coordinates': (51.4545, -2.5879),
                'region': 'South West England'
            },
            'Liverpool': {
                'coordinates': (53.4084, -2.9916),
                'region': 'Merseyside'
            },
            'Newcastle': {
                'coordinates': (54.9783, -1.6178),
                'region': 'Tyne and Wear'
            },
            'Sheffield': {
                'coordinates': (53.3811, -1.4701),
                'region': 'South Yorkshire'
            }
        }
        
        return city_data.get(city)

    def generate_poi_capacity(self, poi_type: str) -> Optional[int]:
        """Generate realistic capacity for POI types."""
        
        capacities = {
            'university': random.randint(5000, 30000),
            'dormitory': random.randint(200, 800),
            'shopping': random.randint(50, 200),
            'restaurant': random.randint(30, 150),
            'library': random.randint(100, 500),
            'sports': random.randint(50, 300),
            'nightlife': random.randint(100, 500),
        }
        
        return capacities.get(poi_type)

    def generate_planning_constraints(self) -> List[str]:
        """Generate realistic planning constraints."""
        
        possible_constraints = [
            'Height restrictions',
            'Historic preservation requirements',
            'Parking requirements',
            'Green space requirements',
            'Noise restrictions',
            'Conservation area restrictions'
        ]
        
        num_constraints = random.randint(0, 3)
        return random.sample(possible_constraints, num_constraints)

    def generate_investment_rationale(self, name: str, metrics: NeighborhoodMetrics) -> str:
        """Generate investment rationale based on neighborhood metrics."""
        
        rationales = []
        
        if metrics.university_proximity_score > 80:
            rationales.append("Excellent proximity to major universities")
        
        if metrics.accessibility_score > 75:
            rationales.append("Strong transport connectivity")
            
        if metrics.amenities_score > 70:
            rationales.append("Rich amenity infrastructure")
            
        if metrics.safety_score > 80:
            rationales.append("High safety ratings")
            
        if metrics.planning_feasibility_score > 75:
            rationales.append("Favorable planning environment")
        
        if not rationales:
            rationales = ["Emerging area with development potential"]
        
        return f"{name} offers {', '.join(rationales[:3])}. Overall score: {metrics.overall_score:.1f}/100."

    def display_stats(self, stats: Dict[str, int]):
        """Display creation statistics."""
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write("DEMO DATA CREATION COMPLETE")
        self.stdout.write("="*60)
        
        self.stdout.write(f"POIs created: {stats['pois_created']:,}")
        self.stdout.write(f"Neighborhoods created: {stats['neighborhoods_created']:,}")
        self.stdout.write(f"Market analyses created: {stats['market_analyses_created']:,}")
        
        self.stdout.write(f"\n{self.style.SUCCESS('Demo data creation completed successfully!')}")