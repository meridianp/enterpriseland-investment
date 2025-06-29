"""
Tests for PBSA Scheme Information Models.

Comprehensive test suite covering scheme models, location analysis,
site characteristics, economic viability, and operational considerations.
"""

from decimal import Decimal
from datetime import date, datetime
from unittest.mock import patch

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from accounts.models import Group
from assessments.scheme_models import (
    PBSAScheme, SchemeLocationInformation, TargetUniversity, SchemeSiteInformation,
    DevelopmentStage, UniversityType, PlanningStatus
)
from assessments.scheme_economic_models import (
    SchemeEconomicInformation, AccommodationUnit, SchemeOperationalInformation,
    AccommodationType
)
from assessments.partner_models import DevelopmentPartner
from assessments.enums import Currency, RiskLevel, AreaUnit

User = get_user_model()


class PBSASchemeModelTest(TestCase):
    """Test the main PBSAScheme model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            role='ANALYST'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.user.groups.add(self.group)
        
        self.developer = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.scheme = PBSAScheme.objects.create(
            group=self.group,
            scheme_name='Test Student Village',
            developer=self.developer,
            total_beds=500,
            total_units=200,
            development_stage=DevelopmentStage.PLANNING,
            total_development_cost_amount=Decimal('25000000'),
            total_development_cost_currency=Currency.GBP,
            expected_completion_date=date(2025, 9, 1)
        )
    
    def test_scheme_creation(self):
        """Test basic scheme creation."""
        self.assertEqual(self.scheme.scheme_name, 'Test Student Village')
        self.assertEqual(self.scheme.total_beds, 500)
        self.assertEqual(self.scheme.developer, self.developer)
        self.assertEqual(self.scheme.development_stage, DevelopmentStage.PLANNING)
        self.assertTrue(self.scheme.is_active)
    
    def test_cost_per_bed_calculation(self):
        """Test development cost per bed calculation."""
        cost_per_bed = self.scheme.cost_per_bed
        
        # Expected: 25,000,000 / 500 = 50,000
        self.assertEqual(cost_per_bed, Decimal('50000.00'))
    
    def test_development_timeline_calculation(self):
        """Test development timeline calculation."""
        # Set construction start date
        self.scheme.construction_start_date = date(2024, 6, 1)
        self.scheme.save()
        
        timeline = self.scheme.development_timeline_months
        
        # Expected: June 2024 to September 2025 = ~15 months
        self.assertIsNotNone(timeline)
        self.assertGreater(timeline, 10)
        self.assertLess(timeline, 20)
    
    def test_beds_per_unit_calculation(self):
        """Test beds per unit ratio calculation."""
        beds_per_unit = self.scheme.beds_per_unit
        
        # Expected: 500 beds / 200 units = 2.5
        self.assertEqual(beds_per_unit, 2.5)
    
    def test_scheme_summary(self):
        """Test comprehensive scheme summary generation."""
        summary = self.scheme.get_scheme_summary()
        
        self.assertEqual(summary['scheme_name'], 'Test Student Village')
        self.assertEqual(summary['developer'], 'Test Developer Ltd')
        self.assertEqual(summary['total_beds'], 500)
        self.assertEqual(summary['development_stage'], 'Planning Application')
        self.assertEqual(summary['cost_per_bed'], Decimal('50000.00'))
    
    def test_update_cached_fields(self):
        """Test updating of cached performance fields."""
        # Create location info with universities
        location_info = SchemeLocationInformation.objects.create(
            group=self.group,
            scheme=self.scheme,
            address='123 University Street',
            city='Test City',
            country='GB',
            location_type='campus_adjacent'
        )
        
        # Add target universities
        TargetUniversity.objects.create(
            group=self.group,
            location_info=location_info,
            university_name='Test University',
            university_type=UniversityType.RUSSELL_GROUP,
            distance_to_campus_km=Decimal('0.5'),
            total_student_population=25000
        )
        
        # Update cached fields
        self.scheme.update_cached_fields()
        self.scheme.refresh_from_db()
        
        self.assertEqual(self.scheme._university_count, 1)


class SchemeLocationInformationTest(TestCase):
    """Test scheme location and market information."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            role='ANALYST'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.developer = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.scheme = PBSAScheme.objects.create(
            group=self.group,
            scheme_name='Test Student Village',
            developer=self.developer,
            total_beds=500
        )
        
        self.location_info = SchemeLocationInformation.objects.create(
            group=self.group,
            scheme=self.scheme,
            address='123 University Street, Test City',
            city='Test City',
            region='Test Region',
            country='GB',
            postcode='TC1 2AB',
            latitude=Decimal('51.5074'),
            longitude=Decimal('-0.1278'),
            location_type='city_centre',
            nearest_train_station='Test Central',
            train_station_distance_km=Decimal('0.8'),
            public_transport_rating=4,
            competitive_schemes_nearby=3,
            total_student_population=45000
        )
    
    def test_location_creation(self):
        """Test basic location information creation."""
        self.assertEqual(self.location_info.city, 'Test City')
        self.assertEqual(self.location_info.country, 'GB')
        self.assertEqual(self.location_info.location_type, 'city_centre')
        self.assertEqual(self.location_info.public_transport_rating, 4)
    
    def test_coordinates_property(self):
        """Test geographic coordinates property."""
        coordinates = self.location_info.coordinates
        
        self.assertIsNotNone(coordinates)
        self.assertEqual(coordinates.x, float(self.location_info.longitude))
        self.assertEqual(coordinates.y, float(self.location_info.latitude))
    
    def test_transport_accessibility_score(self):
        """Test transport accessibility scoring."""
        score = self.location_info.transport_accessibility_score
        
        # Should be a score between 1-5
        self.assertIsNotNone(score)
        self.assertGreaterEqual(score, 1)
        self.assertLessEqual(score, 5)
        
        # With good public transport (4/5) and close train station (0.8km),
        # should get a good score
        self.assertGreaterEqual(score, 3)


class TargetUniversityTest(TestCase):
    """Test target university analysis functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            role='ANALYST'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.developer = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.scheme = PBSAScheme.objects.create(
            group=self.group,
            scheme_name='Test Student Village',
            developer=self.developer,
            total_beds=500
        )
        
        self.location_info = SchemeLocationInformation.objects.create(
            group=self.group,
            scheme=self.scheme,
            address='123 University Street',
            city='Test City',
            country='GB',
            location_type='campus_adjacent'
        )
        
        self.university = TargetUniversity.objects.create(
            group=self.group,
            location_info=self.location_info,
            university_name='Prestigious University',
            university_type=UniversityType.RUSSELL_GROUP,
            distance_to_campus_km=Decimal('0.3'),
            walking_time_minutes=5,
            cycling_time_minutes=2,
            public_transport_time_minutes=8,
            total_student_population=30000,
            international_student_pct=Decimal('22.5'),
            postgraduate_student_pct=Decimal('35.0'),
            university_provided_beds=8000,
            accommodation_satisfaction_rating=2,
            estimated_demand_capture_pct=Decimal('12.5')
        )
    
    def test_university_creation(self):
        """Test target university creation."""
        self.assertEqual(self.university.university_name, 'Prestigious University')
        self.assertEqual(self.university.university_type, UniversityType.RUSSELL_GROUP)
        self.assertEqual(self.university.distance_to_campus_km, Decimal('0.3'))
        self.assertEqual(self.university.total_student_population, 30000)
    
    def test_proximity_score(self):
        """Test proximity scoring based on distance and transport."""
        score = self.university.proximity_score
        
        # Very close distance (0.3km) and short walking time (5 min)
        # should give excellent proximity score
        self.assertEqual(score, 5)
    
    def test_market_attractiveness(self):
        """Test market attractiveness calculation."""
        attractiveness = self.university.market_attractiveness
        
        self.assertIsNotNone(attractiveness)
        self.assertGreaterEqual(attractiveness, 1.0)
        self.assertLessEqual(attractiveness, 5.0)
        
        # Large university (30k students), high international % (22.5%),
        # excellent proximity (5), poor accommodation satisfaction (2)
        # should give strong attractiveness score
        self.assertGreaterEqual(attractiveness, 3.5)
    
    def test_university_string_representation(self):
        """Test string representation of university."""
        expected = "Prestigious University (0.3km)"
        self.assertEqual(str(self.university), expected)


class SchemeSiteInformationTest(TestCase):
    """Test site characteristics and development constraints."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            role='ANALYST'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.developer = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.scheme = PBSAScheme.objects.create(
            group=self.group,
            scheme_name='Test Student Village',
            developer=self.developer,
            total_beds=500
        )
        
        self.site_info = SchemeSiteInformation.objects.create(
            group=self.group,
            scheme=self.scheme,
            site_area_value=Decimal('5000'),
            site_area_unit=AreaUnit.SQ_M,
            site_configuration='regular',
            plot_ratio=Decimal('2.5'),
            building_coverage_pct=Decimal('40'),
            max_height_stories=8,
            topography='flat',
            ground_conditions='good',
            contamination_risk=RiskLevel.LOW,
            flood_risk=RiskLevel.LOW,
            planning_status=PlanningStatus.APPROVED,
            planning_reference='TC/2024/001',
            planning_submission_date=date(2024, 3, 15),
            planning_decision_date=date(2024, 6, 20),
            utilities_available={
                'electricity': True,
                'gas': True,
                'water': True,
                'drainage': True,
                'telecoms': True
            }
        )
    
    def test_site_creation(self):
        """Test basic site information creation."""
        self.assertEqual(self.site_info.site_area_value, Decimal('5000'))
        self.assertEqual(self.site_info.site_area_unit, AreaUnit.SQ_M)
        self.assertEqual(self.site_info.planning_status, PlanningStatus.APPROVED)
        self.assertEqual(self.site_info.ground_conditions, 'good')
    
    def test_site_area_conversion(self):
        """Test site area conversion to square meters."""
        area_sq_m = self.site_info.site_area_sq_m
        self.assertEqual(area_sq_m, Decimal('5000'))  # Already in sq m
        
        # Test conversion from square feet
        self.site_info.site_area_unit = AreaUnit.SQ_FT
        self.site_info.site_area_value = Decimal('53820')  # ~5000 sq m
        area_sq_m = self.site_info.site_area_sq_m
        
        # Should convert to approximately 5000 sq m
        self.assertAlmostEqual(float(area_sq_m), 5000, delta=100)
    
    def test_beds_per_hectare_calculation(self):
        """Test bed density calculation."""
        density = self.site_info.beds_per_hectare
        
        # Expected: 500 beds / 0.5 hectares = 1000 beds/hectare
        self.assertEqual(density, Decimal('1000.0'))
    
    def test_development_feasibility_score(self):
        """Test development feasibility scoring."""
        score = self.site_info.development_feasibility_score
        
        # With approved planning, good ground conditions, low risks,
        # should get a high feasibility score
        self.assertGreaterEqual(score, 4)
        self.assertLessEqual(score, 5)
    
    def test_planning_risk_assessment(self):
        """Test planning risk assessment."""
        risk_assessment = self.site_info.planning_risk_assessment
        
        self.assertIn('risk_level', risk_assessment)
        self.assertIn('timeline_estimate', risk_assessment)
        self.assertIn('planning_status', risk_assessment)
        
        # Approved planning should have low risk
        self.assertEqual(risk_assessment['risk_level'], RiskLevel.LOW)
        self.assertIn('0-3 months', risk_assessment['timeline_estimate'])


class SchemeEconomicInformationTest(TestCase):
    """Test economic viability and financial modeling."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            role='ANALYST'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.developer = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.scheme = PBSAScheme.objects.create(
            group=self.group,
            scheme_name='Test Student Village',
            developer=self.developer,
            total_beds=500
        )
        
        self.economic_info = SchemeEconomicInformation.objects.create(
            group=self.group,
            scheme=self.scheme,
            land_cost_amount=Decimal('5000000'),
            land_cost_currency=Currency.GBP,
            construction_cost_amount=Decimal('18000000'),
            construction_cost_currency=Currency.GBP,
            professional_fees_amount=Decimal('1500000'),
            professional_fees_currency=Currency.GBP,
            finance_costs_amount=Decimal('800000'),
            finance_costs_currency=Currency.GBP,
            contingency_amount=Decimal('700000'),
            contingency_currency=Currency.GBP,
            avg_rent_per_bed_per_week=Decimal('180'),
            rent_currency=Currency.GBP,
            occupancy_rate_pct=Decimal('95'),
            rental_growth_rate_pct=Decimal('3.5'),
            ancillary_income_per_bed_per_year=Decimal('250'),
            operating_cost_per_bed_per_year=Decimal('1200'),
            management_fee_pct=Decimal('8'),
            maintenance_cost_per_bed_per_year=Decimal('800'),
            target_gross_yield_pct=Decimal('6.5'),
            projected_irr_pct=Decimal('12.5'),
            market_rent_per_bed_per_week=Decimal('175')
        )
    
    def test_economic_info_creation(self):
        """Test basic economic information creation."""
        self.assertEqual(self.economic_info.land_cost_amount, Decimal('5000000'))
        self.assertEqual(self.economic_info.avg_rent_per_bed_per_week, Decimal('180'))
        self.assertEqual(self.economic_info.occupancy_rate_pct, Decimal('95'))
    
    def test_total_development_cost_calculation(self):
        """Test total development cost calculation."""
        total_cost = self.economic_info.total_development_cost
        
        # Expected: 5M + 18M + 1.5M + 0.8M + 0.7M = 26M
        self.assertEqual(total_cost, Decimal('26000000'))
    
    def test_cost_per_bed_calculation(self):
        """Test development cost per bed calculation."""
        cost_per_bed = self.economic_info.cost_per_bed
        
        # Expected: 26,000,000 / 500 = 52,000
        self.assertEqual(cost_per_bed, Decimal('52000.00'))
    
    def test_gross_annual_rental_income_calculation(self):
        """Test gross annual rental income calculation."""
        gross_income = self.economic_info.gross_annual_rental_income
        
        # Expected: 180 * 500 * 0.95 * 52 = 4,446,000
        expected = Decimal('180') * 500 * Decimal('0.95') * 52
        self.assertEqual(gross_income, expected)
    
    def test_total_annual_income_calculation(self):
        """Test total annual income including ancillary."""
        total_income = self.economic_info.total_annual_income
        
        # Gross rental + ancillary income
        gross_rental = self.economic_info.gross_annual_rental_income
        ancillary = Decimal('250') * 500  # 250 per bed * 500 beds
        expected = gross_rental + ancillary
        
        self.assertEqual(total_income, expected)
    
    def test_net_annual_income_calculation(self):
        """Test net annual income after operating costs."""
        net_income = self.economic_info.net_annual_income
        
        self.assertIsNotNone(net_income)
        # Should be positive with reasonable assumptions
        self.assertGreater(net_income, 0)
    
    def test_gross_yield_calculation(self):
        """Test gross rental yield calculation."""
        gross_yield = self.economic_info.estimated_gross_yield_pct
        
        # Should be around 6-7% based on the numbers
        self.assertIsNotNone(gross_yield)
        self.assertGreater(gross_yield, 5)
        self.assertLess(gross_yield, 8)
    
    def test_rent_vs_market_analysis(self):
        """Test rent positioning vs market analysis."""
        analysis = self.economic_info.rent_vs_market_analysis
        
        self.assertIn('scheme_rent', analysis)
        self.assertIn('market_rent', analysis)
        self.assertIn('variance_amount', analysis)
        self.assertIn('variance_percentage', analysis)
        self.assertIn('positioning', analysis)
        
        # Scheme rent (180) vs market (175) = +5 difference
        self.assertEqual(analysis['variance_amount'], Decimal('5.00'))
        self.assertAlmostEqual(float(analysis['variance_percentage']), 2.86, places=1)
        self.assertEqual(analysis['positioning'], 'Above Market')
    
    def test_investment_viability_score(self):
        """Test investment viability scoring."""
        viability = self.economic_info.investment_viability_score
        
        self.assertIn('score', viability)
        self.assertIn('factors', viability)
        
        # Should get a good score with reasonable returns
        self.assertGreaterEqual(viability['score'], 3)
        self.assertLessEqual(viability['score'], 5)


class AccommodationUnitTest(TestCase):
    """Test individual accommodation unit specifications."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            role='ANALYST'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.developer = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.scheme = PBSAScheme.objects.create(
            group=self.group,
            scheme_name='Test Student Village',
            developer=self.developer,
            total_beds=500
        )
        
        self.unit = AccommodationUnit.objects.create(
            group=self.group,
            scheme=self.scheme,
            unit_type=AccommodationType.STUDIO,
            unit_name='Premium Studio',
            bed_count=1,
            bathroom_count=1,
            gross_floor_area_sqm=Decimal('25'),
            bedroom_size_sqm=Decimal('18'),
            has_kitchen=True,
            kitchen_type='private',
            has_study_space=True,
            has_storage=True,
            furnishing_level='fully_furnished',
            number_of_units=100,
            rent_per_bed_per_week=Decimal('200'),
            rent_currency=Currency.GBP,
            competitive_rent_per_week=Decimal('190')
        )
    
    def test_unit_creation(self):
        """Test accommodation unit creation."""
        self.assertEqual(self.unit.unit_name, 'Premium Studio')
        self.assertEqual(self.unit.unit_type, AccommodationType.STUDIO)
        self.assertEqual(self.unit.bed_count, 1)
        self.assertEqual(self.unit.number_of_units, 100)
    
    def test_total_beds_calculation(self):
        """Test total beds for unit type calculation."""
        total_beds = self.unit.total_beds_for_unit_type
        
        # Expected: 1 bed * 100 units = 100 beds
        self.assertEqual(total_beds, 100)
    
    def test_area_per_bed_calculation(self):
        """Test area per bed calculation."""
        area_per_bed = self.unit.area_per_bed_sqm
        
        # Expected: 25 sqm / 1 bed = 25 sqm per bed
        self.assertEqual(area_per_bed, Decimal('25.00'))
    
    def test_annual_revenue_calculation(self):
        """Test annual revenue per unit calculation."""
        annual_revenue = self.unit.annual_revenue_per_unit
        
        # Expected: 200 * 1 bed * 52 weeks * 95% occupancy
        expected = Decimal('200') * 1 * 52 * Decimal('0.95')
        self.assertEqual(annual_revenue, expected)
    
    def test_rent_premium_calculation(self):
        """Test rent premium vs competition calculation."""
        premium = self.unit.rent_premium_vs_competition_pct
        
        # Expected: (200 - 190) / 190 * 100 = 5.26%
        expected_premium = (Decimal('200') - Decimal('190')) / Decimal('190') * 100
        self.assertAlmostEqual(float(premium), float(expected_premium), places=2)
    
    def test_unit_efficiency_score(self):
        """Test unit efficiency scoring."""
        score = self.unit.unit_efficiency_score
        
        # Should get good score with spacious unit, full features, reasonable rent
        self.assertGreaterEqual(score, 3)
        self.assertLessEqual(score, 5)


class SchemeOperationalInformationTest(TestCase):
    """Test operational management and service provision."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            role='ANALYST'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.developer = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.scheme = PBSAScheme.objects.create(
            group=self.group,
            scheme_name='Test Student Village',
            developer=self.developer,
            total_beds=500
        )
        
        self.operational_info = SchemeOperationalInformation.objects.create(
            group=self.group,
            scheme=self.scheme,
            management_model='third_party',
            management_company='Premium Student Management Ltd',
            on_site_staff_count=8,
            has_24_7_reception=True,
            has_security=True,
            security_type='full_security',
            cleaning_service='weekly_rooms',
            laundry_facilities='shared_card',
            internet_provision='premium',
            has_gym=True,
            has_study_rooms=True,
            has_social_spaces=True,
            has_cinema_room=True,
            has_outdoor_space=True,
            smart_building_features=['keyless_entry', 'climate_control', 'energy_monitoring'],
            mobile_app_features=['booking', 'payments', 'maintenance_requests'],
            sustainability_features=['solar_panels', 'led_lighting', 'water_recycling'],
            target_occupancy_rate_pct=Decimal('96'),
            average_lease_length_months=44,
            student_satisfaction_target=4,
            estimated_operating_cost_per_bed=Decimal('1500'),
            utilities_included_in_rent=True
        )
    
    def test_operational_info_creation(self):
        """Test operational information creation."""
        self.assertEqual(self.operational_info.management_model, 'third_party')
        self.assertEqual(self.operational_info.management_company, 'Premium Student Management Ltd')
        self.assertTrue(self.operational_info.has_gym)
        self.assertEqual(self.operational_info.internet_provision, 'premium')
    
    def test_amenity_score_calculation(self):
        """Test amenity provision scoring."""
        score = self.operational_info.amenity_score
        
        # With comprehensive amenities (gym, study rooms, social spaces, cinema, outdoor),
        # premium internet, and security, should get high score
        self.assertGreaterEqual(score, 4)
        self.assertLessEqual(score, 5)
    
    def test_operational_efficiency_score(self):
        """Test operational efficiency scoring."""
        score = self.operational_info.operational_efficiency_score
        
        # With third-party management, technology features, and good service provision,
        # should get good efficiency score
        self.assertGreaterEqual(score, 3)
        self.assertLessEqual(score, 5)
    
    def test_operational_summary(self):
        """Test operational summary generation."""
        summary = self.operational_info.get_operational_summary()
        
        self.assertIn('management_model', summary)
        self.assertIn('amenity_score', summary)
        self.assertIn('efficiency_score', summary)
        self.assertIn('technology_features', summary)
        
        self.assertEqual(summary['management_company'], 'Premium Student Management Ltd')
        self.assertEqual(summary['technology_features'], 3)  # 3 smart building features


class SchemeIntegrationTest(TestCase):
    """Integration tests for the complete scheme framework."""
    
    def setUp(self):
        """Set up comprehensive test data."""
        self.user = User.objects.create_user(
            email='analyst@example.com',
            password='testpass123',
            role='ANALYST'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.user.groups.add(self.group)
        
        # Create developer
        self.developer = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Premium Student Developments Ltd'
        )
        
        # Create comprehensive scheme
        self.scheme = PBSAScheme.objects.create(
            group=self.group,
            scheme_name='Cambridge Student Quarter',
            developer=self.developer,
            total_beds=600,
            total_units=250,
            development_stage=DevelopmentStage.CONSTRUCTION,
            total_development_cost_amount=Decimal('32000000'),
            total_development_cost_currency=Currency.GBP,
            expected_completion_date=date(2025, 9, 1),
            construction_start_date=date(2024, 9, 1)
        )
    
    def test_comprehensive_scheme_analysis(self):
        """Test complete scheme with all information models."""
        # Add location information
        location_info = SchemeLocationInformation.objects.create(
            group=self.group,
            scheme=self.scheme,
            address='Science Park Road, Cambridge',
            city='Cambridge',
            region='Cambridgeshire',
            country='GB',
            postcode='CB4 0GA',
            location_type='city_centre',
            train_station_distance_km=Decimal('1.2'),
            public_transport_rating=5,
            competitive_schemes_nearby=4,
            total_student_population=25000
        )
        
        # Add target university
        university = TargetUniversity.objects.create(
            group=self.group,
            location_info=location_info,
            university_name='University of Cambridge',
            university_type=UniversityType.RUSSELL_GROUP,
            distance_to_campus_km=Decimal('0.8'),
            walking_time_minutes=12,
            total_student_population=24000,
            international_student_pct=Decimal('35'),
            university_provided_beds=9500,
            accommodation_satisfaction_rating=3
        )
        
        # Add site information
        site_info = SchemeSiteInformation.objects.create(
            group=self.group,
            scheme=self.scheme,
            site_area_value=Decimal('8000'),
            site_area_unit=AreaUnit.SQ_M,
            site_configuration='regular',
            planning_status=PlanningStatus.APPROVED,
            ground_conditions='excellent',
            contamination_risk=RiskLevel.LOW,
            flood_risk=RiskLevel.LOW
        )
        
        # Add economic information
        economic_info = SchemeEconomicInformation.objects.create(
            group=self.group,
            scheme=self.scheme,
            land_cost_amount=Decimal('8000000'),
            construction_cost_amount=Decimal('22000000'),
            professional_fees_amount=Decimal('1500000'),
            finance_costs_amount=Decimal('500000'),
            avg_rent_per_bed_per_week=Decimal('220'),
            occupancy_rate_pct=Decimal('97'),
            operating_cost_per_bed_per_year=Decimal('1400'),
            target_gross_yield_pct=Decimal('6.8'),
            projected_irr_pct=Decimal('14.2'),
            market_rent_per_bed_per_week=Decimal('210')
        )
        
        # Add accommodation units
        studio_unit = AccommodationUnit.objects.create(
            group=self.group,
            scheme=self.scheme,
            unit_type=AccommodationType.STUDIO,
            unit_name='Premium Studio',
            bed_count=1,
            number_of_units=150,
            gross_floor_area_sqm=Decimal('28'),
            rent_per_bed_per_week=Decimal('240'),
            competitive_rent_per_week=Decimal('225')
        )
        
        cluster_unit = AccommodationUnit.objects.create(
            group=self.group,
            scheme=self.scheme,
            unit_type=AccommodationType.CLUSTER_FLAT,
            unit_name='6-Bed Cluster',
            bed_count=6,
            number_of_units=75,
            gross_floor_area_sqm=Decimal('120'),
            rent_per_bed_per_week=Decimal('200'),
            competitive_rent_per_week=Decimal('195')
        )
        
        # Add operational information
        operational_info = SchemeOperationalInformation.objects.create(
            group=self.group,
            scheme=self.scheme,
            management_model='third_party',
            has_gym=True,
            has_study_rooms=True,
            has_social_spaces=True,
            internet_provision='premium',
            target_occupancy_rate_pct=Decimal('97')
        )
        
        # Test comprehensive analysis
        scheme_summary = self.scheme.get_scheme_summary()
        self.assertEqual(scheme_summary['total_beds'], 600)
        self.assertEqual(scheme_summary['city'], 'Cambridge')
        
        # Test location analysis
        transport_score = location_info.transport_accessibility_score
        self.assertGreaterEqual(transport_score, 4)  # Should be high for Cambridge
        
        # Test university market attractiveness
        attractiveness = university.market_attractiveness
        self.assertGreaterEqual(attractiveness, 4)  # Cambridge should be very attractive
        
        # Test site feasibility
        feasibility = site_info.development_feasibility_score
        self.assertGreaterEqual(feasibility, 4)  # Approved planning, good conditions
        
        # Test economic viability
        gross_yield = economic_info.estimated_gross_yield_pct
        self.assertIsNotNone(gross_yield)
        self.assertGreater(gross_yield, 6)  # Should achieve target yield
        
        # Test unit analysis
        studio_efficiency = studio_unit.unit_efficiency_score
        cluster_efficiency = cluster_unit.unit_efficiency_score
        self.assertGreaterEqual(studio_efficiency, 3)
        self.assertGreaterEqual(cluster_efficiency, 3)
        
        # Test operational scoring
        amenity_score = operational_info.amenity_score
        self.assertGreaterEqual(amenity_score, 3)
        
        # Update cached fields and verify
        self.scheme.update_cached_fields()
        self.assertEqual(self.scheme._university_count, 1)
    
    def test_poor_performing_scheme_analysis(self):
        """Test scheme with poor performance indicators."""
        # Create a scheme with challenging characteristics
        poor_scheme = PBSAScheme.objects.create(
            group=self.group,
            scheme_name='Challenging Development',
            developer=self.developer,
            total_beds=200,
            development_stage=DevelopmentStage.CONCEPT,
            total_development_cost_amount=Decimal('15000000'),  # High cost per bed
            total_development_cost_currency=Currency.GBP
        )
        
        # Add poor location
        poor_location = SchemeLocationInformation.objects.create(
            group=self.group,
            scheme=poor_scheme,
            address='Remote Location',
            city='Small Town',
            country='GB',
            location_type='out_of_town',
            train_station_distance_km=Decimal('5.0'),
            public_transport_rating=2,
            competitive_schemes_nearby=8
        )
        
        # Add challenging site
        poor_site = SchemeSiteInformation.objects.create(
            group=self.group,
            scheme=poor_scheme,
            site_area_value=Decimal('2000'),
            site_area_unit=AreaUnit.SQ_M,
            planning_status=PlanningStatus.PRE_APPLICATION,
            ground_conditions='poor',
            contamination_risk=RiskLevel.HIGH,
            flood_risk=RiskLevel.HIGH
        )
        
        # Add poor economics
        poor_economics = SchemeEconomicInformation.objects.create(
            group=self.group,
            scheme=poor_scheme,
            total_development_cost=Decimal('15000000'),
            avg_rent_per_bed_per_week=Decimal('120'),  # Low rent
            occupancy_rate_pct=Decimal('85'),  # Poor occupancy
            projected_irr_pct=Decimal('6.5'),  # Poor returns
            market_rent_per_bed_per_week=Decimal('140')  # Below market
        )
        
        # Test that poor characteristics are detected
        transport_score = poor_location.transport_accessibility_score
        self.assertLessEqual(transport_score, 3)
        
        feasibility_score = poor_site.development_feasibility_score
        self.assertLessEqual(feasibility_score, 2)
        
        cost_per_bed = poor_scheme.cost_per_bed
        self.assertEqual(cost_per_bed, Decimal('75000.00'))  # Very high cost per bed