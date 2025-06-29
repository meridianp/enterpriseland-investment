"""
Management command to create demo data for testing the CASA Due Diligence Platform.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from accounts.models import Group, GroupMembership
from assessments.models import (
    DevelopmentPartner,
    PBSAScheme,
    Assessment,
    AssessmentMetric,
    DueDiligenceCase,
    CaseChecklistItem,
)
from assessments.partner_models import OfficeLocation, FinancialPartner, KeyShareholder
from assessments.scheme_models import SchemeLocationInformation, TargetUniversity
from assessments.advanced_models import RegulatoryCompliance, ESGAssessment

User = get_user_model()


class Command(BaseCommand):
    help = 'Creates demo data for testing the CASA Due Diligence Platform'

    def handle(self, *args, **options):
        self.stdout.write('Creating demo data...')
        
        # Get or create default group
        group, _ = Group.objects.get_or_create(
            name='Default Investment Fund',
            defaults={'description': 'Default group for testing'}
        )
        
        # Get admin user
        admin = User.objects.get(username='admin')
        analyst = User.objects.get(username='analyst')
        manager = User.objects.get(username='manager')
        
        # Create demo partners
        partners = []
        partner_data = [
            {
                'company_name': 'Premier Student Living Ltd',
                'trading_name': 'PSL',
                'headquarter_city': 'London',
                'headquarter_country': 'GB',
                'year_established': 2008,
                'website_url': 'https://premierstudentliving.com',
                'number_of_employees': 350,
                'completed_pbsa_schemes': 12,
                'schemes_in_development': 5,
                'total_pbsa_beds_delivered': 8500,
                'years_of_pbsa_experience': 15,
                'assessment_priority': 'high',
            },
            {
                'company_name': 'Urban Student Developments',
                'trading_name': 'USD',
                'headquarter_city': 'Manchester',
                'headquarter_country': 'GB',
                'year_established': 2012,
                'website_url': 'https://urbanstudent.co.uk',
                'number_of_employees': 180,
                'completed_pbsa_schemes': 8,
                'schemes_in_development': 3,
                'total_pbsa_beds_delivered': 4200,
                'years_of_pbsa_experience': 11,
                'assessment_priority': 'medium',
            },
            {
                'company_name': 'Campus Living Solutions',
                'trading_name': 'CLS',
                'headquarter_city': 'Birmingham',
                'headquarter_country': 'GB',
                'year_established': 2015,
                'website_url': 'https://campusliving.com',
                'number_of_employees': 95,
                'completed_pbsa_schemes': 4,
                'schemes_in_development': 2,
                'total_pbsa_beds_delivered': 2100,
                'years_of_pbsa_experience': 8,
                'assessment_priority': 'medium',
            },
        ]
        
        for data in partner_data:
            partner, created = DevelopmentPartner.objects.get_or_create(
                company_name=data['company_name'],
                group=group,
                defaults={**data, 'created_by': admin}
            )
            if created:
                partners.append(partner)
                self.stdout.write(f'✅ Created partner: {partner.company_name}')
                
                # Add office locations
                OfficeLocation.objects.create(
                    partner=partner,
                    city=data['headquarter_city'],
                    country=data['headquarter_country'],
                    is_headquarters=True,
                    employee_count=data['number_of_employees'] // 2
                )
                
                # Add financial partners
                FinancialPartner.objects.create(
                    partner=partner,
                    name=f'{partner.trading_name} Capital Partners',
                    relationship_type='equity',
                    commitment_amount=Decimal('50000000'),
                    commitment_currency='GBP',
                    is_active=True
                )
                
                # Add key shareholders
                KeyShareholder.objects.create(
                    partner=partner,
                    name=f'{partner.trading_name} Holdings Ltd',
                    ownership_percentage=Decimal('60'),
                    shareholder_type='corporation',
                    is_controlling=True
                )
        
        # Create demo schemes
        schemes = []
        scheme_data = [
            {
                'partner': partners[0] if partners else DevelopmentPartner.objects.first(),
                'scheme_name': 'University Quarter Birmingham',
                'development_stage': 'CONSTRUCTION',
                'location_city': 'Birmingham',
                'location_country': 'GB',
                'total_beds': 850,
                'total_units': 425,
                'site_area_value': Decimal('5000'),
                'site_area_unit': 'SQ_M',
                'total_development_cost_amount': Decimal('65000000'),
                'total_development_cost_currency': 'GBP',
                'expected_completion_date': date.today() + timedelta(days=365),
            },
            {
                'partner': partners[1] if len(partners) > 1 else DevelopmentPartner.objects.first(),
                'scheme_name': 'Riverside Student Village',
                'development_stage': 'PLANNING',
                'location_city': 'Manchester',
                'location_country': 'GB',
                'total_beds': 600,
                'total_units': 300,
                'site_area_value': Decimal('3500'),
                'site_area_unit': 'SQ_M',
                'total_development_cost_amount': Decimal('45000000'),
                'total_development_cost_currency': 'GBP',
                'expected_completion_date': date.today() + timedelta(days=730),
            },
            {
                'partner': partners[2] if len(partners) > 2 else DevelopmentPartner.objects.first(),
                'scheme_name': 'City Centre Studios',
                'development_stage': 'OPERATIONAL',
                'location_city': 'London',
                'location_country': 'GB',
                'total_beds': 420,
                'total_units': 420,
                'site_area_value': Decimal('2000'),
                'site_area_unit': 'SQ_M',
                'total_development_cost_amount': Decimal('55000000'),
                'total_development_cost_currency': 'GBP',
                'operational_start_date': date.today() - timedelta(days=180),
            },
        ]
        
        for data in scheme_data:
            partner = data.pop('partner')
            scheme, created = PBSAScheme.objects.get_or_create(
                scheme_name=data['scheme_name'],
                developer=partner,
                group=group,
                defaults={**data, 'created_by': admin}
            )
            if created:
                schemes.append(scheme)
                self.stdout.write(f'✅ Created scheme: {scheme.scheme_name}')
                
                # Add location information
                location = SchemeLocationInformation.objects.create(
                    scheme=scheme,
                    address=f'123 {scheme.location_city} Street',
                    city=scheme.location_city,
                    country=scheme.location_country,
                    postcode='AB1 2CD',
                    location_type='city_centre',
                    public_transport_rating=5,
                    total_student_population=45000
                )
                
                # Add target university
                TargetUniversity.objects.create(
                    location_info=location,
                    university_name=f'University of {scheme.location_city}',
                    university_type='RUSSELL_GROUP',
                    distance_to_campus_km=Decimal('0.5'),
                    walking_time_minutes=10,
                    total_student_population=35000,
                    international_student_pct=Decimal('30')
                )
        
        # Create demo cases
        cases = []
        case_data = [
            {
                'case_name': 'PSL New Partnership Assessment',
                'case_type': 'new_partner',
                'partner': partners[0] if partners else None,
                'priority': 'high',
                'case_status': 'analysis',
                'total_investment_amount': Decimal('15000000'),
                'total_investment_currency': 'GBP',
                'target_irr_percentage': Decimal('15.5'),
                'description': 'Initial partnership assessment for Premier Student Living',
            },
            {
                'case_name': 'University Quarter Investment',
                'case_type': 'new_scheme',
                'partner': partners[0] if partners else None,
                'scheme': schemes[0] if schemes else None,
                'priority': 'urgent',
                'case_status': 'review',
                'total_investment_amount': Decimal('20000000'),
                'total_investment_currency': 'GBP',
                'target_irr_percentage': Decimal('18.0'),
                'description': 'Investment opportunity in Birmingham student accommodation',
            },
            {
                'case_name': 'Riverside Village Planning Review',
                'case_type': 'new_scheme',
                'partner': partners[1] if len(partners) > 1 else None,
                'scheme': schemes[1] if len(schemes) > 1 else None,
                'priority': 'medium',
                'case_status': 'data_collection',
                'total_investment_amount': Decimal('10000000'),
                'total_investment_currency': 'GBP',
                'target_irr_percentage': Decimal('16.0'),
                'description': 'Early stage investment in Manchester development',
            },
        ]
        
        for data in case_data:
            case, created = DueDiligenceCase.objects.get_or_create(
                case_name=data['case_name'],
                group=group,
                defaults={
                    **data,
                    'created_by': analyst,
                    'assigned_to': analyst,
                    'target_completion_date': date.today() + timedelta(days=60)
                }
            )
            if created:
                cases.append(case)
                self.stdout.write(f'✅ Created case: {case.case_name}')
                
                # Add checklist items
                checklist_items = [
                    ('financial', 'Review audited financial statements', True),
                    ('financial', 'Analyze cash flow projections', True),
                    ('legal', 'Review corporate structure', True),
                    ('legal', 'Check regulatory compliance', True),
                    ('technical', 'Site visit and inspection', False),
                    ('commercial', 'Market analysis review', True),
                ]
                
                for category, item_name, is_required in checklist_items:
                    CaseChecklistItem.objects.create(
                        case=case,
                        category=category,
                        item_name=item_name,
                        is_required=is_required,
                        due_date=date.today() + timedelta(days=30) if is_required else None
                    )
        
        # Create demo assessments
        if partners and cases:
            assessment = Assessment.objects.create(
                assessment_name='PSL Partnership Assessment 2024',
                assessment_type='PARTNER',
                partner=partners[0],
                status='IN_REVIEW',
                group=group,
                assessor=analyst,
                submitted_at=timezone.now()
            )
            self.stdout.write(f'✅ Created assessment: {assessment.assessment_name}')
            
            # Add metrics
            metrics = [
                ('Financial Strength', 'FINANCIAL', 4, 5, 'Strong balance sheet and consistent profitability'),
                ('PBSA Track Record', 'TRACK_RECORD', 5, 5, 'Excellent track record with 12 completed schemes'),
                ('Management Team', 'OPERATIONAL', 4, 4, 'Experienced team with deep PBSA expertise'),
                ('Market Position', 'MARKET', 4, 3, 'Strong presence in key UK markets'),
                ('ESG Commitment', 'ESG', 3, 3, 'Developing ESG framework, room for improvement'),
            ]
            
            for metric_name, category, score, weight, justification in metrics:
                AssessmentMetric.objects.create(
                    assessment=assessment,
                    metric_name=metric_name,
                    category=category,
                    score=score,
                    weight=weight,
                    justification=justification,
                    confidence_level='HIGH'
                )
            
            # Link assessment to case
            cases[0].assessments.add(assessment)
        
        # Create demo regulatory compliance
        if partners:
            RegulatoryCompliance.objects.create(
                partner=partners[0],
                jurisdiction='GB',
                regulatory_framework='UK Financial Services',
                regulatory_body='FCA',
                compliance_category='financial',
                requirement_title='AML/KYC Compliance',
                requirement_description='Anti-money laundering and know your customer requirements',
                compliance_status='compliant',
                compliance_risk_level='LOW',
                group=group,
                created_by=admin
            )
            self.stdout.write('✅ Created regulatory compliance record')
        
        # Create demo ESG assessment
        if partners:
            ESGAssessment.objects.create(
                partner=partners[0],
                assessment_name='2024 Annual ESG Review',
                assessment_framework='custom',
                assessment_period_start=date.today() - timedelta(days=365),
                assessment_period_end=date.today(),
                environmental_score=4,
                social_score=4,
                governance_score=5,
                carbon_footprint_tonnes=Decimal('2500.50'),
                renewable_energy_pct=Decimal('35.0'),
                local_employment_pct=Decimal('85.0'),
                board_diversity_pct=Decimal('40.0'),
                anti_corruption_policies=True,
                group=group,
                created_by=admin
            )
            self.stdout.write('✅ Created ESG assessment')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Demo data creation complete!'))
        self.stdout.write('\nCreated:')
        self.stdout.write(f'  - {len(partners)} development partners')
        self.stdout.write(f'  - {len(schemes)} PBSA schemes')
        self.stdout.write(f'  - {len(cases)} due diligence cases')
        self.stdout.write('  - 1 assessment with metrics')
        self.stdout.write('  - Regulatory compliance records')
        self.stdout.write('  - ESG assessments')
        self.stdout.write('\nYou can now log in and explore the platform!')