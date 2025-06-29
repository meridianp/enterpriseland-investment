"""
Comprehensive unit tests for the CASA Due Diligence Platform models.

Tests all Django models created in phases 1-6 including:
- Partner models (DevelopmentPartner, OfficeLocation, FinancialPartner, KeyShareholder)
- Scheme models (PBSAScheme, SchemeLocationInformation, SchemeSiteInformation, TargetUniversity)
- Assessment models (Assessment, AssessmentMetric, AssessmentTemplate, MetricTemplate)
- Advanced models (RegulatoryCompliance, PerformanceMetric, ESGAssessment, AuditTrail)
- Root aggregate models (DueDiligenceCase, CaseChecklistItem, CaseTimeline)
"""

from decimal import Decimal
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Group
# Import from models.py to avoid conflicts with modular files
from assessments.models import (
    DevelopmentPartner, OfficeLocation, FinancialPartner, KeyShareholder,
    GeneralInformation, OperationalInformation, StakeholderInformation,
    FinancialInformation, CreditInformation,
    PBSAScheme, SchemeLocationInformation, SchemeSiteInformation, TargetUniversity,
    SchemeEconomicInformation, AccommodationUnit, SchemeOperationalInformation,
    Assessment, AssessmentMetric, AssessmentTemplate, MetricTemplate,
    RegulatoryCompliance, PerformanceMetric, ESGAssessment,
    AuditTrail, DueDiligenceCase, CaseChecklistItem, CaseTimeline,
    AssessmentStatus, Currency, RiskLevel, AreaUnit,
    DevelopmentStage, UniversityType, PlanningStatus,
    AccommodationType, AssessmentType, MetricCategory, DecisionBand,
    ComplianceType, ComplianceStatus, MetricType, MetricFrequency,
    ESGCategory, RelationshipType, CaseStatus, ChecklistItemStatus, CaseEventType
)

User = get_user_model()


class DevelopmentPartnerModelTest(TestCase):
    """Test the DevelopmentPartner model and its related models."""
    
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
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
    
    def test_partner_creation(self):
        """Test basic partner creation."""
        self.assertEqual(self.partner.company_name, 'Test Developer Ltd')
        self.assertTrue(self.partner.is_active)
        self.assertEqual(self.partner.assessment_priority, 'medium')
        self.assertEqual(str(self.partner), 'Test Developer Ltd')
    
    def test_partner_cached_fields(self):
        """Test cached field updates."""
        # Initially should have default values
        self.assertEqual(self.partner._total_countries, 0)
        self.assertFalse(self.partner._has_pbsa_experience)
        
        # Add general information with headquarters
        GeneralInformation.objects.create(
            group=self.group,
            partner=self.partner,
            headquarter_city='London',
            headquarter_country='GB'
        )
        
        # Add office location
        OfficeLocation.objects.create(
            group=self.group,
            partner=self.partner,
            city='Berlin',
            country='DE',
            is_headquarters=False
        )
        
        # Add operational info with PBSA experience
        OperationalInformation.objects.create(
            group=self.group,
            partner=self.partner,
            completed_pbsa_schemes=5,
            total_pbsa_beds_delivered=1000
        )
        
        # Update cached fields
        self.partner.update_cached_fields()
        self.partner.refresh_from_db()
        
        self.assertEqual(self.partner._total_countries, 2)  # GB and DE
        self.assertTrue(self.partner._has_pbsa_experience)
    
    def test_partner_assessment_summary(self):
        """Test comprehensive assessment summary generation."""
        # Add operational information
        OperationalInformation.objects.create(
            group=self.group,
            partner=self.partner,
            completed_pbsa_schemes=10,
            total_pbsa_beds_delivered=2500,
            schemes_in_development=5,
            pbsa_schemes_in_development=4
        )
        
        # Add credit information
        CreditInformation.objects.create(
            group=self.group,
            partner=self.partner,
            total_debt_amount=Decimal('10000000'),
            total_debt_currency=Currency.GBP,
            interest_coverage_ratio=Decimal('3.5')
        )
        
        summary = self.partner.get_assessment_summary()
        
        self.assertEqual(summary['company_name'], 'Test Developer Ltd')
        self.assertEqual(summary['pbsa_schemes_completed'], 10)
        self.assertEqual(summary['total_beds_delivered'], 2500)
        self.assertEqual(summary['pbsa_specialization'], 80.0)  # 4/5 * 100
        self.assertEqual(summary['avg_scheme_size'], 250)  # 2500/10
        self.assertEqual(summary['interest_coverage'], Decimal('3.5'))


class OfficeLocationModelTest(TestCase):
    """Test the OfficeLocation model."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.office = OfficeLocation.objects.create(
            group=self.group,
            partner=self.partner,
            city='London',
            country='GB',
            is_headquarters=True,
            employee_count=150
        )
    
    def test_office_creation(self):
        """Test office location creation."""
        self.assertEqual(self.office.city, 'London')
        self.assertEqual(self.office.country, 'GB')
        self.assertTrue(self.office.is_headquarters)
        self.assertEqual(self.office.employee_count, 150)
    
    def test_office_string_representation(self):
        """Test string representation."""
        self.assertEqual(str(self.office), 'London, GB')
    
    def test_country_name_property(self):
        """Test country name resolution."""
        self.assertEqual(self.office.country_name, 'United Kingdom')
    
    def test_unique_constraint(self):
        """Test unique constraint on partner, city, country."""
        with self.assertRaises(Exception):
            OfficeLocation.objects.create(
                group=self.group,
                partner=self.partner,
                city='London',
                country='GB'
            )


class FinancialPartnerModelTest(TestCase):
    """Test the FinancialPartner model."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.financial_partner = FinancialPartner.objects.create(
            group=self.group,
            partner=self.partner,
            name='Blackstone Capital',
            relationship_type=RelationshipType.EQUITY_PARTNER,
            commitment_amount=Decimal('50000000'),
            commitment_currency=Currency.GBP,
            relationship_start_date=date(2020, 1, 1)
        )
    
    def test_financial_partner_creation(self):
        """Test financial partner creation."""
        self.assertEqual(self.financial_partner.name, 'Blackstone Capital')
        self.assertEqual(self.financial_partner.relationship_type, RelationshipType.EQUITY_PARTNER)
        self.assertEqual(self.financial_partner.commitment_amount, Decimal('50000000'))
        self.assertTrue(self.financial_partner.is_active)
    
    def test_formatted_commitment(self):
        """Test formatted commitment display."""
        self.assertEqual(self.financial_partner.formatted_commitment, '£50,000,000.00')
    
    def test_string_representation(self):
        """Test string representation."""
        self.assertEqual(str(self.financial_partner), 'Blackstone Capital (Equity Partner)')


class KeyShareholderModelTest(TestCase):
    """Test the KeyShareholder model."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.shareholder = KeyShareholder.objects.create(
            group=self.group,
            partner=self.partner,
            name='John Smith',
            ownership_percentage=Decimal('35.5'),
            shareholder_type='individual',
            is_controlling=True
        )
    
    def test_shareholder_creation(self):
        """Test shareholder creation."""
        self.assertEqual(self.shareholder.name, 'John Smith')
        self.assertEqual(self.shareholder.ownership_percentage, Decimal('35.5'))
        self.assertEqual(self.shareholder.shareholder_type, 'individual')
        self.assertTrue(self.shareholder.is_controlling)
    
    def test_ownership_percentage_validation(self):
        """Test ownership percentage validation."""
        # Test > 100%
        with self.assertRaises(ValidationError):
            shareholder = KeyShareholder(
                group=self.group,
                partner=self.partner,
                name='Invalid Shareholder',
                ownership_percentage=Decimal('101'),
                shareholder_type='individual'
            )
            shareholder.full_clean()
        
        # Test < 0%
        with self.assertRaises(ValidationError):
            shareholder = KeyShareholder(
                group=self.group,
                partner=self.partner,
                name='Invalid Shareholder',
                ownership_percentage=Decimal('-1'),
                shareholder_type='individual'
            )
            shareholder.full_clean()
    
    def test_string_representation(self):
        """Test string representation."""
        self.assertEqual(str(self.shareholder), 'John Smith (35.5%)')


class GeneralInformationModelTest(TestCase):
    """Test the GeneralInformation model."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.general_info = GeneralInformation.objects.create(
            group=self.group,
            partner=self.partner,
            trading_name='Test Dev',
            legal_structure='ltd',
            registration_number='12345678',
            headquarter_city='London',
            headquarter_country='GB',
            year_established=2010,
            website_url='https://testdev.com',
            primary_contact_email='info@testdev.com'
        )
    
    def test_general_info_creation(self):
        """Test general information creation."""
        self.assertEqual(self.general_info.trading_name, 'Test Dev')
        self.assertEqual(self.general_info.legal_structure, 'ltd')
        self.assertEqual(self.general_info.year_established, 2010)
        self.assertEqual(self.general_info.headquarter_country, 'GB')
    
    def test_company_age_calculation(self):
        """Test company age calculation."""
        current_year = datetime.now().year
        expected_age = current_year - 2010
        self.assertEqual(self.general_info.company_age, expected_age)
    
    def test_international_presence(self):
        """Test international presence detection."""
        # Initially only headquarters (GB)
        self.assertFalse(self.general_info.has_international_presence)
        
        # Add office in another country
        OfficeLocation.objects.create(
            group=self.group,
            partner=self.partner,
            city='Paris',
            country='FR'
        )
        
        self.assertTrue(self.general_info.has_international_presence)


class OperationalInformationModelTest(TestCase):
    """Test the OperationalInformation model."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.operational_info = OperationalInformation.objects.create(
            group=self.group,
            partner=self.partner,
            size_of_development_team=25,
            number_of_employees=150,
            completed_pbsa_schemes=15,
            years_of_pbsa_experience=8,
            total_pbsa_beds_delivered=3500,
            schemes_in_development=10,
            pbsa_schemes_in_development=8,
            beds_in_development=2000
        )
    
    def test_operational_info_creation(self):
        """Test operational information creation."""
        self.assertEqual(self.operational_info.size_of_development_team, 25)
        self.assertEqual(self.operational_info.completed_pbsa_schemes, 15)
        self.assertEqual(self.operational_info.total_pbsa_beds_delivered, 3500)
    
    def test_pbsa_specialization_calculation(self):
        """Test PBSA specialization percentage calculation."""
        # 8 PBSA schemes out of 10 total = 80%
        self.assertEqual(self.operational_info.pbsa_specialization_pct, 80.0)
    
    def test_average_scheme_size_calculation(self):
        """Test average PBSA scheme size calculation."""
        # 3500 beds / 15 schemes = 233.33, rounded to 233
        self.assertEqual(self.operational_info.avg_pbsa_scheme_size, 233)
    
    def test_development_team_ratio(self):
        """Test development team ratio calculation."""
        # 25 dev team / 150 total = 16.67%
        self.assertEqual(self.operational_info.development_team_ratio, 16.7)
    
    def test_none_values_handling(self):
        """Test handling of None values in calculations."""
        # Create operational info with None values
        op_info = OperationalInformation.objects.create(
            group=self.group,
            partner=DevelopmentPartner.objects.create(
                group=self.group,
                company_name='Another Developer'
            )
        )
        
        self.assertIsNone(op_info.pbsa_specialization_pct)
        self.assertIsNone(op_info.avg_pbsa_scheme_size)
        self.assertIsNone(op_info.development_team_ratio)


class StakeholderInformationModelTest(TestCase):
    """Test the StakeholderInformation model."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.stakeholder_info = StakeholderInformation.objects.create(
            group=self.group,
            partner=self.partner,
            shareholding_structure='Complex holding structure',
            ultimate_parent_company='Test Holdings Ltd',
            publicly_listed=True,
            stock_exchange='LSE',
            ticker_symbol='TDL'
        )
    
    def test_stakeholder_info_creation(self):
        """Test stakeholder information creation."""
        self.assertEqual(self.stakeholder_info.ultimate_parent_company, 'Test Holdings Ltd')
        self.assertTrue(self.stakeholder_info.publicly_listed)
        self.assertEqual(self.stakeholder_info.stock_exchange, 'LSE')
    
    def test_institutional_backing_detection(self):
        """Test detection of institutional financial backing."""
        # Initially no backing
        self.assertFalse(self.stakeholder_info.has_institutional_backing)
        
        # Add institutional financial partner
        FinancialPartner.objects.create(
            group=self.group,
            partner=self.partner,
            name='Goldman Sachs Asset Management',
            relationship_type=RelationshipType.EQUITY_PARTNER
        )
        
        self.assertTrue(self.stakeholder_info.has_institutional_backing)
        
        # Also test with institutional shareholder
        KeyShareholder.objects.create(
            group=self.group,
            partner=self.partner,
            name='Pension Fund X',
            ownership_percentage=Decimal('20'),
            shareholder_type='fund'
        )
        
        self.assertTrue(self.stakeholder_info.has_institutional_backing)
    
    def test_ownership_concentration(self):
        """Test ownership concentration categorization."""
        # Initially dispersed (no shareholders)
        self.assertEqual(self.stakeholder_info.ownership_concentration, 'Dispersed')
        
        # Add majority shareholder
        KeyShareholder.objects.create(
            group=self.group,
            partner=self.partner,
            name='Majority Owner',
            ownership_percentage=Decimal('75'),
            shareholder_type='individual'
        )
        
        self.assertEqual(self.stakeholder_info.ownership_concentration, 'Highly Concentrated')
    
    def test_total_ownership_validation(self):
        """Test validation of total ownership not exceeding 100%."""
        # Add shareholders totaling 100%
        KeyShareholder.objects.create(
            group=self.group,
            partner=self.partner,
            name='Owner 1',
            ownership_percentage=Decimal('60'),
            shareholder_type='individual'
        )
        
        KeyShareholder.objects.create(
            group=self.group,
            partner=self.partner,
            name='Owner 2',
            ownership_percentage=Decimal('40'),
            shareholder_type='individual'
        )
        
        # Should validate successfully
        self.stakeholder_info.clean()
        
        # Add another shareholder that would exceed 100%
        KeyShareholder.objects.create(
            group=self.group,
            partner=self.partner,
            name='Owner 3',
            ownership_percentage=Decimal('10'),
            shareholder_type='individual'
        )
        
        # Should raise validation error
        with self.assertRaises(ValidationError):
            self.stakeholder_info.clean()


class PBSASchemeModelTest(TestCase):
    """Test the PBSAScheme model."""
    
    def setUp(self):
        """Set up test data."""
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
            scheme_name='University Heights',
            developer=self.developer,
            total_beds=600,
            total_units=250,
            development_stage=DevelopmentStage.CONSTRUCTION,
            total_development_cost_amount=Decimal('30000000'),
            total_development_cost_currency=Currency.GBP,
            expected_completion_date=date(2025, 9, 1),
            construction_start_date=date(2024, 3, 1)
        )
    
    def test_scheme_creation(self):
        """Test scheme creation."""
        self.assertEqual(self.scheme.scheme_name, 'University Heights')
        self.assertEqual(self.scheme.total_beds, 600)
        self.assertEqual(self.scheme.development_stage, DevelopmentStage.CONSTRUCTION)
        self.assertTrue(self.scheme.is_active)
    
    def test_cost_per_bed_calculation(self):
        """Test cost per bed calculation."""
        # 30,000,000 / 600 = 50,000
        self.assertEqual(self.scheme.cost_per_bed, Decimal('50000.00'))
    
    def test_development_timeline_calculation(self):
        """Test development timeline calculation."""
        timeline = self.scheme.development_timeline_months
        # March 2024 to September 2025 = ~18 months
        self.assertIsNotNone(timeline)
        self.assertGreater(timeline, 15)
        self.assertLess(timeline, 20)
    
    def test_beds_per_unit_calculation(self):
        """Test beds per unit calculation."""
        # 600 beds / 250 units = 2.4
        self.assertEqual(self.scheme.beds_per_unit, 2.4)
    
    def test_scheme_summary(self):
        """Test scheme summary generation."""
        summary = self.scheme.get_scheme_summary()
        
        self.assertEqual(summary['scheme_name'], 'University Heights')
        self.assertEqual(summary['developer'], 'Test Developer Ltd')
        self.assertEqual(summary['total_beds'], 600)
        self.assertEqual(summary['development_stage'], 'Under Construction')
        self.assertEqual(summary['cost_per_bed'], Decimal('50000.00'))


class SchemeLocationInformationModelTest(TestCase):
    """Test the SchemeLocationInformation model."""
    
    def setUp(self):
        """Set up test data."""
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
            scheme_name='Campus Living',
            developer=self.developer,
            total_beds=400
        )
        
        self.location = SchemeLocationInformation.objects.create(
            group=self.group,
            scheme=self.scheme,
            address='123 University Road',
            city='Oxford',
            region='Oxfordshire',
            country='GB',
            postcode='OX1 2AB',
            latitude=Decimal('51.7520'),
            longitude=Decimal('-1.2577'),
            location_type='campus_adjacent',
            nearest_train_station='Oxford Station',
            train_station_distance_km=Decimal('1.5'),
            public_transport_rating=5,
            competitive_schemes_nearby=3,
            total_student_population=30000
        )
    
    def test_location_creation(self):
        """Test location information creation."""
        self.assertEqual(self.location.city, 'Oxford')
        self.assertEqual(self.location.location_type, 'campus_adjacent')
        self.assertEqual(self.location.public_transport_rating, 5)
    
    def test_coordinates_property(self):
        """Test geographic coordinates property."""
        coords = self.location.coordinates
        self.assertIsNotNone(coords)
        self.assertEqual(coords.x, float(self.location.longitude))
        self.assertEqual(coords.y, float(self.location.latitude))
    
    def test_transport_accessibility_score(self):
        """Test transport accessibility scoring."""
        score = self.location.transport_accessibility_score
        # With excellent public transport (5/5) and reasonable station distance
        self.assertGreaterEqual(score, 4)
        self.assertLessEqual(score, 5)


class TargetUniversityModelTest(TestCase):
    """Test the TargetUniversity model."""
    
    def setUp(self):
        """Set up test data."""
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
            scheme_name='Student Quarter',
            developer=self.developer,
            total_beds=350
        )
        
        self.location = SchemeLocationInformation.objects.create(
            group=self.group,
            scheme=self.scheme,
            address='Near Campus',
            city='Cambridge',
            country='GB'
        )
        
        self.university = TargetUniversity.objects.create(
            group=self.group,
            location_info=self.location,
            university_name='University of Cambridge',
            university_type=UniversityType.RUSSELL_GROUP,
            distance_to_campus_km=Decimal('0.8'),
            walking_time_minutes=12,
            cycling_time_minutes=4,
            public_transport_time_minutes=6,
            total_student_population=24000,
            international_student_pct=Decimal('35'),
            postgraduate_student_pct=Decimal('45'),
            university_provided_beds=7000,
            accommodation_satisfaction_rating=3,
            estimated_demand_capture_pct=Decimal('15')
        )
    
    def test_university_creation(self):
        """Test university creation."""
        self.assertEqual(self.university.university_name, 'University of Cambridge')
        self.assertEqual(self.university.university_type, UniversityType.RUSSELL_GROUP)
        self.assertEqual(self.university.total_student_population, 24000)
    
    def test_proximity_score(self):
        """Test proximity scoring."""
        score = self.university.proximity_score
        # Good proximity (0.8km, 12 min walk) should give high score
        self.assertGreaterEqual(score, 4)
    
    def test_market_attractiveness(self):
        """Test market attractiveness calculation."""
        attractiveness = self.university.market_attractiveness
        # Russell Group, high international %, good proximity
        self.assertGreaterEqual(attractiveness, 4.0)
    
    def test_string_representation(self):
        """Test string representation."""
        self.assertEqual(str(self.university), 'University of Cambridge (0.8km)')


class SchemeSiteInformationModelTest(TestCase):
    """Test the SchemeSiteInformation model."""
    
    def setUp(self):
        """Set up test data."""
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
            scheme_name='Modern Student Living',
            developer=self.developer,
            total_beds=500
        )
        
        self.site_info = SchemeSiteInformation.objects.create(
            group=self.group,
            scheme=self.scheme,
            site_area_value=Decimal('6000'),
            site_area_unit=AreaUnit.SQ_M,
            site_configuration='regular',
            plot_ratio=Decimal('3.0'),
            building_coverage_pct=Decimal('45'),
            max_height_stories=10,
            topography='flat',
            ground_conditions='excellent',
            contamination_risk=RiskLevel.LOW,
            flood_risk=RiskLevel.LOW,
            planning_status=PlanningStatus.APPROVED,
            planning_reference='REF/2024/123',
            planning_submission_date=date(2024, 1, 15),
            planning_decision_date=date(2024, 4, 20)
        )
    
    def test_site_info_creation(self):
        """Test site information creation."""
        self.assertEqual(self.site_info.site_area_value, Decimal('6000'))
        self.assertEqual(self.site_info.planning_status, PlanningStatus.APPROVED)
        self.assertEqual(self.site_info.ground_conditions, 'excellent')
    
    def test_site_area_conversion(self):
        """Test site area conversion to square meters."""
        # Already in square meters
        self.assertEqual(self.site_info.site_area_sq_m, Decimal('6000'))
        
        # Test conversion from hectares
        self.site_info.site_area_unit = AreaUnit.HECTARE
        self.site_info.site_area_value = Decimal('0.6')
        self.assertEqual(self.site_info.site_area_sq_m, Decimal('6000'))
    
    def test_beds_per_hectare_calculation(self):
        """Test bed density calculation."""
        # 500 beds / 0.6 hectares = 833.33
        density = self.site_info.beds_per_hectare
        self.assertAlmostEqual(float(density), 833.33, places=1)
    
    def test_development_feasibility_score(self):
        """Test development feasibility scoring."""
        score = self.site_info.development_feasibility_score
        # Approved planning, excellent conditions, low risks = high score
        self.assertGreaterEqual(score, 4.5)
    
    def test_planning_risk_assessment(self):
        """Test planning risk assessment."""
        assessment = self.site_info.planning_risk_assessment
        
        self.assertEqual(assessment['risk_level'], RiskLevel.LOW)
        self.assertEqual(assessment['planning_status'], PlanningStatus.APPROVED)
        self.assertIn('0-3 months', assessment['timeline_estimate'])


class SchemeEconomicInformationModelTest(TestCase):
    """Test the SchemeEconomicInformation model."""
    
    def setUp(self):
        """Set up test data."""
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
            scheme_name='Premium Student Residence',
            developer=self.developer,
            total_beds=400
        )
        
        self.economic_info = SchemeEconomicInformation.objects.create(
            group=self.group,
            scheme=self.scheme,
            land_cost_amount=Decimal('4000000'),
            land_cost_currency=Currency.GBP,
            construction_cost_amount=Decimal('16000000'),
            construction_cost_currency=Currency.GBP,
            professional_fees_amount=Decimal('1200000'),
            professional_fees_currency=Currency.GBP,
            finance_costs_amount=Decimal('600000'),
            finance_costs_currency=Currency.GBP,
            contingency_amount=Decimal('600000'),
            contingency_currency=Currency.GBP,
            avg_rent_per_bed_per_week=Decimal('190'),
            rent_currency=Currency.GBP,
            occupancy_rate_pct=Decimal('96'),
            rental_growth_rate_pct=Decimal('3.0'),
            ancillary_income_per_bed_per_year=Decimal('200'),
            operating_cost_per_bed_per_year=Decimal('1100'),
            management_fee_pct=Decimal('7'),
            maintenance_cost_per_bed_per_year=Decimal('700'),
            target_gross_yield_pct=Decimal('6.5'),
            projected_irr_pct=Decimal('13.5'),
            market_rent_per_bed_per_week=Decimal('185')
        )
    
    def test_economic_info_creation(self):
        """Test economic information creation."""
        self.assertEqual(self.economic_info.land_cost_amount, Decimal('4000000'))
        self.assertEqual(self.economic_info.avg_rent_per_bed_per_week, Decimal('190'))
        self.assertEqual(self.economic_info.occupancy_rate_pct, Decimal('96'))
    
    def test_total_development_cost_calculation(self):
        """Test total development cost calculation."""
        total = self.economic_info.total_development_cost
        # 4M + 16M + 1.2M + 0.6M + 0.6M = 22.4M
        self.assertEqual(total, Decimal('22400000'))
    
    def test_cost_per_bed_calculation(self):
        """Test cost per bed calculation."""
        cost_per_bed = self.economic_info.cost_per_bed
        # 22,400,000 / 400 = 56,000
        self.assertEqual(cost_per_bed, Decimal('56000.00'))
    
    def test_gross_annual_rental_income(self):
        """Test gross annual rental income calculation."""
        income = self.economic_info.gross_annual_rental_income
        # 190 * 400 * 0.96 * 52 = 3,793,920
        expected = Decimal('190') * 400 * Decimal('0.96') * 52
        self.assertEqual(income, expected)
    
    def test_net_annual_income(self):
        """Test net annual income calculation."""
        net_income = self.economic_info.net_annual_income
        self.assertIsNotNone(net_income)
        self.assertGreater(net_income, 0)
    
    def test_gross_yield_calculation(self):
        """Test gross yield percentage calculation."""
        yield_pct = self.economic_info.estimated_gross_yield_pct
        self.assertIsNotNone(yield_pct)
        # Should be reasonable yield (5-8%)
        self.assertGreater(yield_pct, 5)
        self.assertLess(yield_pct, 8)
    
    def test_rent_vs_market_analysis(self):
        """Test rent positioning analysis."""
        analysis = self.economic_info.rent_vs_market_analysis
        
        self.assertEqual(analysis['scheme_rent'], Decimal('190'))
        self.assertEqual(analysis['market_rent'], Decimal('185'))
        self.assertEqual(analysis['variance_amount'], Decimal('5.00'))
        self.assertEqual(analysis['positioning'], 'Above Market')
    
    def test_investment_viability_score(self):
        """Test investment viability scoring."""
        viability = self.economic_info.investment_viability_score
        
        self.assertIn('score', viability)
        self.assertIn('factors', viability)
        # Good returns should give good score
        self.assertGreaterEqual(viability['score'], 3)


class AccommodationUnitModelTest(TestCase):
    """Test the AccommodationUnit model."""
    
    def setUp(self):
        """Set up test data."""
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
            scheme_name='Student Village',
            developer=self.developer,
            total_beds=500
        )
        
        self.unit = AccommodationUnit.objects.create(
            group=self.group,
            scheme=self.scheme,
            unit_type=AccommodationType.STUDIO,
            unit_name='Deluxe Studio',
            bed_count=1,
            bathroom_count=1,
            gross_floor_area_sqm=Decimal('30'),
            bedroom_size_sqm=Decimal('20'),
            has_kitchen=True,
            kitchen_type='private',
            has_study_space=True,
            has_storage=True,
            furnishing_level='fully_furnished',
            number_of_units=80,
            rent_per_bed_per_week=Decimal('220'),
            rent_currency=Currency.GBP,
            competitive_rent_per_week=Decimal('200')
        )
    
    def test_unit_creation(self):
        """Test accommodation unit creation."""
        self.assertEqual(self.unit.unit_name, 'Deluxe Studio')
        self.assertEqual(self.unit.unit_type, AccommodationType.STUDIO)
        self.assertEqual(self.unit.number_of_units, 80)
        self.assertTrue(self.unit.has_kitchen)
    
    def test_total_beds_calculation(self):
        """Test total beds for unit type."""
        # 1 bed * 80 units = 80 beds
        self.assertEqual(self.unit.total_beds_for_unit_type, 80)
    
    def test_area_per_bed_calculation(self):
        """Test area per bed calculation."""
        # 30 sqm / 1 bed = 30 sqm per bed
        self.assertEqual(self.unit.area_per_bed_sqm, Decimal('30.00'))
    
    def test_annual_revenue_calculation(self):
        """Test annual revenue per unit."""
        revenue = self.unit.annual_revenue_per_unit
        # 220 * 1 * 52 * 0.95 = 10,868
        expected = Decimal('220') * 1 * 52 * Decimal('0.95')
        self.assertEqual(revenue, expected)
    
    def test_rent_premium_calculation(self):
        """Test rent premium vs competition."""
        premium = self.unit.rent_premium_vs_competition_pct
        # (220 - 200) / 200 * 100 = 10%
        self.assertEqual(premium, Decimal('10.00'))
    
    def test_unit_efficiency_score(self):
        """Test unit efficiency scoring."""
        score = self.unit.unit_efficiency_score
        # Good space, full amenities, reasonable premium
        self.assertGreaterEqual(score, 3)
        self.assertLessEqual(score, 5)


class SchemeOperationalInformationModelTest(TestCase):
    """Test the SchemeOperationalInformation model."""
    
    def setUp(self):
        """Set up test data."""
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
            scheme_name='Tech-Enabled Student Living',
            developer=self.developer,
            total_beds=450
        )
        
        self.operational_info = SchemeOperationalInformation.objects.create(
            group=self.group,
            scheme=self.scheme,
            management_model='third_party',
            management_company='Student Living Management Ltd',
            on_site_staff_count=10,
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
            smart_building_features=['keyless_entry', 'app_control', 'energy_monitoring'],
            mobile_app_features=['booking', 'payments', 'maintenance'],
            sustainability_features=['solar_panels', 'led_lighting', 'recycling'],
            target_occupancy_rate_pct=Decimal('97'),
            average_lease_length_months=44,
            student_satisfaction_target=4,
            estimated_operating_cost_per_bed=Decimal('1400'),
            utilities_included_in_rent=True
        )
    
    def test_operational_info_creation(self):
        """Test operational information creation."""
        self.assertEqual(self.operational_info.management_model, 'third_party')
        self.assertEqual(self.operational_info.on_site_staff_count, 10)
        self.assertTrue(self.operational_info.has_gym)
        self.assertEqual(len(self.operational_info.smart_building_features), 3)
    
    def test_amenity_score_calculation(self):
        """Test amenity provision scoring."""
        score = self.operational_info.amenity_score
        # Full amenities (gym, study, social, cinema, outdoor) + premium internet
        self.assertGreaterEqual(score, 4.5)
    
    def test_operational_efficiency_score(self):
        """Test operational efficiency scoring."""
        score = self.operational_info.operational_efficiency_score
        # Third-party management, smart features, good services
        self.assertGreaterEqual(score, 3.5)
    
    def test_operational_summary(self):
        """Test operational summary generation."""
        summary = self.operational_info.get_operational_summary()
        
        self.assertEqual(summary['management_model'], 'third_party')
        self.assertEqual(summary['management_company'], 'Student Living Management Ltd')
        self.assertGreaterEqual(summary['amenity_score'], 4)
        self.assertEqual(summary['technology_features'], 3)


class RegulatoryComplianceModelTest(TestCase):
    """Test the RegulatoryCompliance model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='compliance@example.com',
            password='testpass123',
            role='ANALYST'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.compliance = RegulatoryCompliance.objects.create(
            group=self.group,
            partner=self.partner,
            compliance_type=ComplianceType.AML,
            compliance_name='AML Policy Review 2024',
            description='Annual anti-money laundering policy review',
            status=ComplianceStatus.COMPLIANT,
            last_review_date=date.today(),
            next_review_date=date.today() + timedelta(days=365),
            reviewed_by=self.user,
            compliance_score=95
        )
    
    def test_compliance_creation(self):
        """Test compliance record creation."""
        self.assertEqual(self.compliance.compliance_name, 'AML Policy Review 2024')
        self.assertEqual(self.compliance.compliance_type, ComplianceType.AML)
        self.assertEqual(self.compliance.status, ComplianceStatus.COMPLIANT)
        self.assertEqual(self.compliance.compliance_score, 95)
    
    def test_is_due_for_review(self):
        """Test review due date checking."""
        # Not due yet (next review in 1 year)
        self.assertFalse(self.compliance.is_due_for_review())
        
        # Set next review to 20 days from now
        self.compliance.next_review_date = date.today() + timedelta(days=20)
        self.assertTrue(self.compliance.is_due_for_review())
    
    def test_days_until_review(self):
        """Test days until review calculation."""
        days = self.compliance.days_until_review
        # Should be approximately 365 days
        self.assertGreater(days, 360)
        self.assertLess(days, 370)
    
    def test_risk_level_property(self):
        """Test risk level determination."""
        # Compliant with high score = LOW risk
        self.assertEqual(self.compliance.risk_level, RiskLevel.LOW)
        
        # Non-compliant = HIGH risk
        self.compliance.status = ComplianceStatus.NON_COMPLIANT
        self.assertEqual(self.compliance.risk_level, RiskLevel.HIGH)
        
        # Under review = MEDIUM risk
        self.compliance.status = ComplianceStatus.UNDER_REVIEW
        self.assertEqual(self.compliance.risk_level, RiskLevel.MEDIUM)
    
    def test_update_status(self):
        """Test status update with review tracking."""
        self.compliance.update_status(
            ComplianceStatus.UNDER_REVIEW,
            self.user,
            'Concerns raised about documentation'
        )
        
        self.assertEqual(self.compliance.status, ComplianceStatus.UNDER_REVIEW)
        self.assertEqual(self.compliance.reviewed_by, self.user)
        self.assertEqual(self.compliance.last_review_date, date.today())


class PerformanceMetricModelTest(TestCase):
    """Test the PerformanceMetric model."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.metric = PerformanceMetric.objects.create(
            group=self.group,
            partner=self.partner,
            metric_type=MetricType.DELIVERY_TIMELINE,
            metric_name='On-Time Delivery Rate',
            description='Percentage of projects delivered on schedule',
            measurement_frequency=MetricFrequency.QUARTERLY,
            target_value=Decimal('95'),
            actual_value=Decimal('92'),
            unit_of_measure='%',
            measurement_date=date.today()
        )
    
    def test_metric_creation(self):
        """Test performance metric creation."""
        self.assertEqual(self.metric.metric_name, 'On-Time Delivery Rate')
        self.assertEqual(self.metric.metric_type, MetricType.DELIVERY_TIMELINE)
        self.assertEqual(self.metric.target_value, Decimal('95'))
        self.assertEqual(self.metric.actual_value, Decimal('92'))
    
    def test_performance_ratio(self):
        """Test performance ratio calculation."""
        # 92 / 95 = 0.9684
        ratio = self.metric.performance_ratio
        self.assertAlmostEqual(float(ratio), 0.9684, places=4)
    
    def test_is_meeting_target(self):
        """Test target achievement checking."""
        # 92 < 95, not meeting target
        self.assertFalse(self.metric.is_meeting_target)
        
        # Set actual to exceed target
        self.metric.actual_value = Decimal('98')
        self.assertTrue(self.metric.is_meeting_target)
    
    def test_performance_status(self):
        """Test performance status categorization."""
        # 92/95 = 96.8% = Good
        self.assertEqual(self.metric.performance_status, 'Good')
        
        # Test excellent (>= 100%)
        self.metric.actual_value = Decimal('100')
        self.assertEqual(self.metric.performance_status, 'Excellent')
        
        # Test poor (< 80%)
        self.metric.actual_value = Decimal('70')
        self.assertEqual(self.metric.performance_status, 'Poor')
    
    def test_create_snapshot(self):
        """Test metric snapshot creation."""
        snapshot = self.metric.create_snapshot()
        
        self.assertEqual(snapshot['metric_name'], 'On-Time Delivery Rate')
        self.assertEqual(snapshot['target_value'], Decimal('95'))
        self.assertEqual(snapshot['actual_value'], Decimal('92'))
        self.assertEqual(snapshot['performance_ratio'], self.metric.performance_ratio)
        self.assertEqual(snapshot['is_meeting_target'], False)


class ESGAssessmentModelTest(TestCase):
    """Test the ESGAssessment model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='esg@example.com',
            password='testpass123',
            role='ANALYST'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.esg_assessment = ESGAssessment.objects.create(
            group=self.group,
            partner=self.partner,
            assessment_date=date.today(),
            assessed_by=self.user,
            environmental_score=75,
            social_score=82,
            governance_score=88,
            category=ESGCategory.ENVIRONMENTAL,
            assessment_area='Carbon Footprint',
            findings='Above average carbon reduction initiatives',
            risk_level=RiskLevel.MEDIUM,
            recommendations='Implement renewable energy sources'
        )
    
    def test_esg_assessment_creation(self):
        """Test ESG assessment creation."""
        self.assertEqual(self.esg_assessment.assessment_area, 'Carbon Footprint')
        self.assertEqual(self.esg_assessment.environmental_score, 75)
        self.assertEqual(self.esg_assessment.social_score, 82)
        self.assertEqual(self.esg_assessment.governance_score, 88)
    
    def test_overall_esg_score(self):
        """Test overall ESG score calculation."""
        # (75 + 82 + 88) / 3 = 81.67
        score = self.esg_assessment.overall_esg_score
        self.assertAlmostEqual(float(score), 81.67, places=2)
    
    def test_esg_rating(self):
        """Test ESG rating categorization."""
        # 81.67 average = A- rating
        self.assertEqual(self.esg_assessment.esg_rating, 'A-')
        
        # Test different ratings
        self.esg_assessment.environmental_score = 95
        self.esg_assessment.social_score = 92
        self.esg_assessment.governance_score = 94
        self.assertEqual(self.esg_assessment.esg_rating, 'A+')
        
        self.esg_assessment.environmental_score = 45
        self.esg_assessment.social_score = 48
        self.esg_assessment.governance_score = 42
        self.assertEqual(self.esg_assessment.esg_rating, 'D')
    
    def test_has_critical_issues(self):
        """Test critical issues detection."""
        # Medium risk, no critical issues
        self.assertFalse(self.esg_assessment.has_critical_issues)
        
        # High risk = critical issue
        self.esg_assessment.risk_level = RiskLevel.HIGH
        self.assertTrue(self.esg_assessment.has_critical_issues)
        
        # Low score = critical issue
        self.esg_assessment.risk_level = RiskLevel.LOW
        self.esg_assessment.environmental_score = 45
        self.assertTrue(self.esg_assessment.has_critical_issues)
    
    def test_get_improvement_areas(self):
        """Test improvement areas identification."""
        areas = self.esg_assessment.get_improvement_areas()
        
        # Environmental score (75) is lowest, should be flagged
        self.assertIn('Environmental', areas)
        self.assertNotIn('Governance', areas)  # 88 is good


class AuditTrailModelTest(TestCase):
    """Test the AuditTrail model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='auditor@example.com',
            password='testpass123',
            role='MANAGER'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.audit = AuditTrail.objects.create(
            group=self.group,
            user=self.user,
            action='UPDATE',
            model_name='DevelopmentPartner',
            object_id=str(self.partner.id),
            field_name='company_name',
            old_value='Old Name Ltd',
            new_value='Test Developer Ltd',
            change_reason='Company rebranding',
            ip_address='192.168.1.100',
            user_agent='Mozilla/5.0'
        )
    
    def test_audit_creation(self):
        """Test audit trail creation."""
        self.assertEqual(self.audit.action, 'UPDATE')
        self.assertEqual(self.audit.model_name, 'DevelopmentPartner')
        self.assertEqual(self.audit.field_name, 'company_name')
        self.assertEqual(self.audit.change_reason, 'Company rebranding')
    
    def test_change_summary(self):
        """Test change summary generation."""
        summary = self.audit.change_summary
        expected = "Changed company_name from 'Old Name Ltd' to 'Test Developer Ltd'"
        self.assertEqual(summary, expected)
    
    def test_is_sensitive_change(self):
        """Test sensitive change detection."""
        # company_name is not sensitive
        self.assertFalse(self.audit.is_sensitive_change)
        
        # Test sensitive fields
        sensitive_fields = [
            'password', 'credit_score', 'bank_account',
            'financial_data', 'personal_information'
        ]
        
        for field in sensitive_fields:
            self.audit.field_name = field
            self.assertTrue(self.audit.is_sensitive_change)
    
    def test_get_recent_changes_for_object(self):
        """Test retrieving recent changes for an object."""
        # Create additional audit entries
        AuditTrail.objects.create(
            group=self.group,
            user=self.user,
            action='UPDATE',
            model_name='DevelopmentPartner',
            object_id=str(self.partner.id),
            field_name='is_active',
            old_value='True',
            new_value='False'
        )
        
        recent_changes = AuditTrail.get_recent_changes_for_object(
            'DevelopmentPartner',
            str(self.partner.id),
            days=7
        )
        
        self.assertEqual(recent_changes.count(), 2)


class DueDiligenceCaseModelTest(TestCase):
    """Test the DueDiligenceCase model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='case_manager@example.com',
            password='testpass123',
            role='MANAGER'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.user.groups.add(self.group)
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name='Test Developer - Q1 2024 Review',
            case_type='partner_assessment',
            partner=self.partner,
            lead_assessor=self.user,
            priority='high',
            target_completion_date=date.today() + timedelta(days=30),
            business_justification='Annual partner review required'
        )
    
    def test_case_creation(self):
        """Test due diligence case creation."""
        self.assertEqual(self.case.case_name, 'Test Developer - Q1 2024 Review')
        self.assertEqual(self.case.status, CaseStatus.DRAFT)
        self.assertEqual(self.case.priority, 'high')
        self.assertTrue(self.case.is_active)
    
    def test_case_reference_generation(self):
        """Test unique case reference generation."""
        self.assertIsNotNone(self.case.case_reference)
        self.assertTrue(self.case.case_reference.startswith('DD-'))
        self.assertEqual(len(self.case.case_reference), 13)  # DD-XXXXXXXXXX
    
    def test_days_remaining(self):
        """Test days remaining calculation."""
        days = self.case.days_remaining
        # Should be approximately 30 days
        self.assertGreater(days, 25)
        self.assertLess(days, 35)
    
    def test_is_overdue(self):
        """Test overdue status checking."""
        # Not overdue yet
        self.assertFalse(self.case.is_overdue)
        
        # Set target date to past
        self.case.target_completion_date = date.today() - timedelta(days=5)
        self.assertTrue(self.case.is_overdue)
    
    def test_completion_percentage(self):
        """Test completion percentage calculation."""
        # Initially 0% (no checklist items)
        self.assertEqual(self.case.completion_percentage, 0)
        
        # Add checklist items
        CaseChecklistItem.objects.create(
            group=self.group,
            case=self.case,
            item_name='Review financials',
            category='financial',
            is_mandatory=True,
            status=ChecklistItemStatus.COMPLETED
        )
        
        CaseChecklistItem.objects.create(
            group=self.group,
            case=self.case,
            item_name='Site visit',
            category='operational',
            is_mandatory=True,
            status=ChecklistItemStatus.IN_PROGRESS
        )
        
        # 1 completed out of 2 = 50%
        self.assertEqual(self.case.completion_percentage, 50)
    
    def test_workflow_transitions(self):
        """Test case workflow state transitions."""
        # Start assessment
        self.case.start_assessment(self.user)
        self.assertEqual(self.case.status, CaseStatus.IN_PROGRESS)
        self.assertIsNotNone(self.case.started_at)
        
        # Submit for review
        self.case.submit_for_review(self.user)
        self.assertEqual(self.case.status, CaseStatus.IN_REVIEW)
        self.assertIsNotNone(self.case.submitted_at)
        
        # Approve
        self.case.approve(self.user, 'All checks passed')
        self.assertEqual(self.case.status, CaseStatus.APPROVED)
        self.assertIsNotNone(self.case.approved_at)
        self.assertEqual(self.case.approver, self.user)
    
    def test_add_timeline_event(self):
        """Test timeline event addition."""
        event = self.case.add_timeline_event(
            CaseEventType.STATUS_CHANGE,
            self.user,
            'Case created and assigned'
        )
        
        self.assertEqual(event.event_type, CaseEventType.STATUS_CHANGE)
        self.assertEqual(event.description, 'Case created and assigned')
        self.assertEqual(event.created_by, self.user)
    
    def test_case_summary(self):
        """Test case summary generation."""
        # Add some data
        CaseChecklistItem.objects.create(
            group=self.group,
            case=self.case,
            item_name='Test item',
            category='general',
            status=ChecklistItemStatus.COMPLETED
        )
        
        summary = self.case.get_case_summary()
        
        self.assertEqual(summary['case_name'], self.case.case_name)
        self.assertEqual(summary['status'], CaseStatus.DRAFT)
        self.assertEqual(summary['priority'], 'high')
        self.assertEqual(summary['completion_percentage'], 100)
        self.assertEqual(summary['total_checklist_items'], 1)
        self.assertFalse(summary['is_overdue'])


class CaseChecklistItemModelTest(TestCase):
    """Test the CaseChecklistItem model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='analyst@example.com',
            password='testpass123',
            role='ANALYST'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name='Test Case',
            case_type='partner_assessment',
            partner=self.partner,
            lead_assessor=self.user
        )
        
        self.checklist_item = CaseChecklistItem.objects.create(
            group=self.group,
            case=self.case,
            item_name='Financial Statement Review',
            description='Review last 3 years of audited financials',
            category='financial',
            is_mandatory=True,
            assigned_to=self.user,
            due_date=date.today() + timedelta(days=7)
        )
    
    def test_checklist_item_creation(self):
        """Test checklist item creation."""
        self.assertEqual(self.checklist_item.item_name, 'Financial Statement Review')
        self.assertEqual(self.checklist_item.status, ChecklistItemStatus.PENDING)
        self.assertTrue(self.checklist_item.is_mandatory)
        self.assertEqual(self.checklist_item.assigned_to, self.user)
    
    def test_is_overdue(self):
        """Test overdue status checking."""
        # Not overdue (due in 7 days)
        self.assertFalse(self.checklist_item.is_overdue)
        
        # Set due date to past
        self.checklist_item.due_date = date.today() - timedelta(days=2)
        self.checklist_item.save()
        
        # Should be overdue if not completed
        self.assertTrue(self.checklist_item.is_overdue)
        
        # Not overdue if completed
        self.checklist_item.status = ChecklistItemStatus.COMPLETED
        self.assertFalse(self.checklist_item.is_overdue)
    
    def test_complete_item(self):
        """Test item completion."""
        self.checklist_item.complete(self.user, 'All financials reviewed and verified')
        
        self.assertEqual(self.checklist_item.status, ChecklistItemStatus.COMPLETED)
        self.assertEqual(self.checklist_item.completed_by, self.user)
        self.assertIsNotNone(self.checklist_item.completed_at)
        self.assertEqual(self.checklist_item.completion_notes, 'All financials reviewed and verified')
    
    def test_validation_mandatory_completion(self):
        """Test validation for mandatory item completion."""
        # Mandatory items must have completion notes
        self.checklist_item.status = ChecklistItemStatus.COMPLETED
        
        with self.assertRaises(ValidationError):
            self.checklist_item.clean()


class CaseTimelineModelTest(TestCase):
    """Test the CaseTimeline model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='timeline@example.com',
            password='testpass123',
            role='ANALYST'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name='Test Case',
            case_type='partner_assessment',
            partner=self.partner,
            lead_assessor=self.user
        )
        
        self.timeline_event = CaseTimeline.objects.create(
            group=self.group,
            case=self.case,
            event_type=CaseEventType.STATUS_CHANGE,
            description='Case moved to in progress',
            created_by=self.user,
            metadata={
                'old_status': 'draft',
                'new_status': 'in_progress'
            }
        )
    
    def test_timeline_event_creation(self):
        """Test timeline event creation."""
        self.assertEqual(self.timeline_event.event_type, CaseEventType.STATUS_CHANGE)
        self.assertEqual(self.timeline_event.description, 'Case moved to in progress')
        self.assertEqual(self.timeline_event.created_by, self.user)
        self.assertIn('old_status', self.timeline_event.metadata)
    
    def test_event_icon(self):
        """Test event icon mapping."""
        # Status change icon
        self.assertEqual(self.timeline_event.event_icon, '🔄')
        
        # Test other event types
        self.timeline_event.event_type = CaseEventType.ASSESSMENT_ADDED
        self.assertEqual(self.timeline_event.event_icon, '📋')
        
        self.timeline_event.event_type = CaseEventType.DOCUMENT_UPLOADED
        self.assertEqual(self.timeline_event.event_icon, '📎')
    
    def test_event_ordering(self):
        """Test timeline events are ordered by creation time."""
        # Create additional events
        event2 = CaseTimeline.objects.create(
            group=self.group,
            case=self.case,
            event_type=CaseEventType.COMMENT,
            description='Added comment',
            created_by=self.user
        )
        
        events = CaseTimeline.objects.filter(case=self.case)
        # Should be ordered newest first
        self.assertEqual(events[0], event2)
        self.assertEqual(events[1], self.timeline_event)


class IntegrationTest(TestCase):
    """Integration tests for model interactions."""
    
    def setUp(self):
        """Set up comprehensive test data."""
        self.user = User.objects.create_user(
            email='integration@example.com',
            password='testpass123',
            role='MANAGER'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.user.groups.add(self.group)
    
    def test_complete_partner_assessment_workflow(self):
        """Test complete partner assessment workflow with all models."""
        # Create partner
        partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Integrated Developer Ltd'
        )
        
        # Add comprehensive partner information
        GeneralInformation.objects.create(
            group=self.group,
            partner=partner,
            trading_name='IDL',
            year_established=2015,
            headquarter_city='London',
            headquarter_country='GB'
        )
        
        OperationalInformation.objects.create(
            group=self.group,
            partner=partner,
            number_of_employees=200,
            completed_pbsa_schemes=20,
            total_pbsa_beds_delivered=5000
        )
        
        FinancialInformation.objects.create(
            group=self.group,
            partner=partner,
            net_assets_amount=Decimal('50000000'),
            net_assets_currency=Currency.GBP,
            latest_annual_revenue_amount=Decimal('75000000'),
            latest_annual_revenue_currency=Currency.GBP
        )
        
        # Create due diligence case
        case = DueDiligenceCase.objects.create(
            group=self.group,
            case_name=f'{partner.company_name} - Annual Review',
            case_type='partner_assessment',
            partner=partner,
            lead_assessor=self.user,
            priority='high'
        )
        
        # Add checklist items
        checklist_items = [
            ('Financial Review', 'financial', True),
            ('Operational Assessment', 'operational', True),
            ('Compliance Check', 'compliance', True),
            ('ESG Assessment', 'esg', False)
        ]
        
        for name, category, mandatory in checklist_items:
            CaseChecklistItem.objects.create(
                group=self.group,
                case=case,
                item_name=name,
                category=category,
                is_mandatory=mandatory,
                assigned_to=self.user
            )
        
        # Create assessment
        assessment = Assessment.objects.create(
            group=self.group,
            assessment_type=AssessmentType.PARTNER,
            assessment_name=f'{partner.company_name} Assessment',
            partner=partner,
            assessor=self.user,
            case=case
        )
        
        # Add metrics
        metrics = [
            ('Financial Strength', MetricCategory.FINANCIAL, 4, 5),
            ('Operational Capability', MetricCategory.OPERATIONAL, 5, 4),
            ('Track Record', MetricCategory.TRACK_RECORD, 5, 5),
            ('Market Position', MetricCategory.MARKET, 4, 3)
        ]
        
        for name, category, score, weight in metrics:
            AssessmentMetric.objects.create(
                group=self.group,
                assessment=assessment,
                metric_name=name,
                category=category,
                score=score,
                weight=weight,
                justification=f'Assessment for {name}'
            )
        
        # Add compliance records
        RegulatoryCompliance.objects.create(
            group=self.group,
            partner=partner,
            compliance_type=ComplianceType.AML,
            compliance_name='AML Compliance Check',
            status=ComplianceStatus.COMPLIANT,
            reviewed_by=self.user,
            compliance_score=92
        )
        
        # Add ESG assessment
        ESGAssessment.objects.create(
            group=self.group,
            partner=partner,
            assessed_by=self.user,
            environmental_score=80,
            social_score=85,
            governance_score=90,
            category=ESGCategory.GOVERNANCE,
            assessment_area='Board Composition',
            findings='Strong governance structure'
        )
        
        # Test workflow
        case.start_assessment(self.user)
        self.assertEqual(case.status, CaseStatus.IN_PROGRESS)
        
        # Complete checklist items
        for item in case.checklist_items.filter(is_mandatory=True):
            item.complete(self.user, f'{item.item_name} completed')
        
        # Calculate assessment scores
        assessment.refresh_calculated_fields()
        
        # Verify calculations
        self.assertIsNotNone(assessment.total_weighted_score)
        self.assertGreater(assessment.score_percentage, 80)
        self.assertEqual(assessment.decision_band, DecisionBand.ACCEPTABLE)
        
        # Submit and approve
        assessment.submit_for_review(self.user)
        assessment.approve(self.user)
        
        case.submit_for_review(self.user)
        case.approve(self.user, 'All assessments satisfactory')
        
        # Verify final state
        self.assertEqual(case.status, CaseStatus.APPROVED)
        self.assertEqual(assessment.status, AssessmentStatus.APPROVED)
        
        # Check audit trail
        audit_entries = AuditTrail.objects.filter(
            model_name='DueDiligenceCase',
            object_id=str(case.id)
        )
        self.assertGreater(audit_entries.count(), 0)
        
        # Verify partner summary includes all data
        summary = partner.get_assessment_summary()
        self.assertIn('pbsa_schemes_completed', summary)
        self.assertEqual(summary['pbsa_schemes_completed'], 20)