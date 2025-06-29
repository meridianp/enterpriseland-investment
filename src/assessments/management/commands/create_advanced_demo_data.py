"""
Management command to create demonstration data for advanced features.

Creates realistic demonstration data for version control, regulatory compliance,
performance monitoring, and ESG assessments for testing and demonstration purposes.
"""

from decimal import Decimal
from datetime import date, datetime, timedelta
import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model

from accounts.models import Group
from assessments.partner_models import DevelopmentPartner
from assessments.scheme_models import PBSAScheme, DevelopmentStage
from assessments.assessment_models import Assessment, AssessmentType
from assessments.advanced_models import (
    RegulatoryCompliance, PerformanceMetric, ESGAssessment, AuditTrail
)
from assessments.enums import Currency, RiskLevel

User = get_user_model()


class Command(BaseCommand):
    help = 'Create demonstration data for advanced features'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--group-name',
            type=str,
            help='Name of the group to create data for (required)',
            required=True
        )
        
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Delete existing advanced feature data before creating new ones'
        )
    
    def handle(self, *args, **options):
        group_name = options['group_name']
        clean = options['clean']
        
        try:
            group = Group.objects.get(name=group_name)
        except Group.DoesNotExist:
            raise CommandError(f'Group "{group_name}" does not exist')
        
        if clean:
            self.stdout.write('Cleaning existing advanced feature data...')
            RegulatoryCompliance.objects.filter(group=group).delete()
            PerformanceMetric.objects.filter(group=group).delete()
            ESGAssessment.objects.filter(group=group).delete()
            AuditTrail.objects.filter(group=group).delete()
        
        # Get or create admin user for audit trails
        admin_user, created = User.objects.get_or_create(
            email=f'admin@{group.name.lower().replace(" ", "")}.com',
            defaults={
                'first_name': 'Admin',
                'last_name': 'User',
                'role': 'admin'
            }
        )
        
        if created:
            self.stdout.write(f'Created admin user: {admin_user.email}')
        
        # Get existing partners and schemes, or create them
        partners = list(DevelopmentPartner.objects.filter(group=group)[:3])
        schemes = list(PBSAScheme.objects.filter(group=group)[:3])
        
        if not partners:
            self.stdout.write('No partners found. Creating demo partners...')
            partners = self._create_demo_partners(group)
        
        if not schemes:
            self.stdout.write('No schemes found. Creating demo schemes...')
            schemes = self._create_demo_schemes(group, partners)
        
        created_data = {}
        
        try:
            with transaction.atomic():
                # Create regulatory compliance data
                compliance_records = self._create_regulatory_compliance(group, partners, schemes)
                created_data['compliance'] = len(compliance_records)
                
                # Create performance metrics
                performance_metrics = self._create_performance_metrics(group, partners, schemes)
                created_data['metrics'] = len(performance_metrics)
                
                # Create ESG assessments
                esg_assessments = self._create_esg_assessments(group, partners, schemes)
                created_data['esg'] = len(esg_assessments)
                
                # Create audit trail entries
                audit_entries = self._create_audit_trail(group, admin_user, partners, schemes)
                created_data['audit'] = len(audit_entries)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Successfully created demonstration data:\n'
                    f'  • {created_data["compliance"]} compliance records\n'
                    f'  • {created_data["metrics"]} performance metrics\n'
                    f'  • {created_data["esg"]} ESG assessments\n'
                    f'  • {created_data["audit"]} audit trail entries'
                )
            )
        
        except Exception as e:
            raise CommandError(f'Error creating advanced demo data: {str(e)}')
    
    def _create_demo_partners(self, group):
        """Create basic demo partners if none exist."""
        partners = []
        partner_names = [
            "Advanced Developer Ltd",
            "Sustainable Property Group",
            "Innovation Student Living"
        ]
        
        for name in partner_names:
            partner = DevelopmentPartner.objects.create(
                group=group,
                company_name=name,
                assessment_priority=random.choice(['high', 'medium', 'low'])
            )
            partners.append(partner)
        
        return partners
    
    def _create_demo_schemes(self, group, partners):
        """Create basic demo schemes if none exist."""
        schemes = []
        scheme_configs = [
            {
                'name': 'Advanced Student Hub',
                'reference': 'ASH001',
                'beds': 350,
                'cost': Decimal('22000000')
            },
            {
                'name': 'Green Campus Residences',
                'reference': 'GCR001',
                'beds': 420,
                'cost': Decimal('28000000')
            },
            {
                'name': 'Innovation Quarter',
                'reference': 'IQ001',
                'beds': 280,
                'cost': Decimal('18000000')
            }
        ]
        
        for i, config in enumerate(scheme_configs):
            scheme = PBSAScheme.objects.create(
                group=group,
                scheme_name=config['name'],
                scheme_reference=config['reference'],
                developer=partners[i % len(partners)],
                total_beds=config['beds'],
                development_stage=DevelopmentStage.OPERATIONAL,
                total_development_cost_amount=config['cost'],
                total_development_cost_currency=Currency.GBP
            )
            schemes.append(scheme)
        
        return schemes
    
    def _create_regulatory_compliance(self, group, partners, schemes):
        """Create regulatory compliance records."""
        compliance_records = []
        
        # Compliance frameworks and requirements
        compliance_configs = [
            {
                'jurisdiction': 'GB',
                'framework': 'Building Safety Act 2022',
                'body': 'Building Safety Regulator',
                'category': 'building',
                'requirements': [
                    {
                        'title': 'Building Safety Case',
                        'description': 'Mandatory safety case for high-rise residential buildings',
                        'status': 'compliant',
                        'risk': RiskLevel.HIGH
                    },
                    {
                        'title': 'Fire Safety Compliance',
                        'description': 'Compliance with fire safety regulations',
                        'status': 'compliant',
                        'risk': RiskLevel.MEDIUM
                    }
                ]
            },
            {
                'jurisdiction': 'GB',
                'framework': 'GDPR 2018',
                'body': 'Information Commissioner\'s Office',
                'category': 'data_protection',
                'requirements': [
                    {
                        'title': 'Data Protection Registration',
                        'description': 'Registration as data controller with ICO',
                        'status': 'compliant',
                        'risk': RiskLevel.MEDIUM
                    },
                    {
                        'title': 'Privacy Impact Assessment',
                        'description': 'DPIA for student data processing',
                        'status': 'partial',
                        'risk': RiskLevel.MEDIUM
                    }
                ]
            },
            {
                'jurisdiction': 'GB',
                'framework': 'Companies House Requirements',
                'body': 'Companies House',
                'category': 'financial',
                'requirements': [
                    {
                        'title': 'Annual Return Filing',
                        'description': 'Annual confirmation statement filing',
                        'status': 'compliant',
                        'risk': RiskLevel.LOW
                    },
                    {
                        'title': 'Financial Statements',
                        'description': 'Annual financial statements submission',
                        'status': 'compliant',
                        'risk': RiskLevel.LOW
                    }
                ]
            }
        ]
        
        # Create compliance records for partners and schemes
        for config in compliance_configs:
            for requirement in config['requirements']:
                # Create for partners
                for partner in partners:
                    compliance = RegulatoryCompliance.objects.create(
                        group=group,
                        partner=partner,
                        jurisdiction=config['jurisdiction'],
                        regulatory_framework=config['framework'],
                        regulatory_body=config['body'],
                        compliance_category=config['category'],
                        requirement_title=requirement['title'],
                        requirement_description=requirement['description'],
                        compliance_status=requirement['status'],
                        compliance_date=date.today() - timedelta(days=random.randint(30, 365)),
                        expiry_date=date.today() + timedelta(days=random.randint(180, 1095)),
                        compliance_risk_level=requirement['risk'],
                        responsible_person=f"{partner.company_name} Compliance Officer",
                        next_review_date=date.today() + timedelta(days=random.randint(90, 180))
                    )
                    compliance_records.append(compliance)
                
                # Create for schemes (building and environmental only)
                if config['category'] in ['building', 'environmental']:
                    for scheme in schemes:
                        compliance = RegulatoryCompliance.objects.create(
                            group=group,
                            scheme=scheme,
                            jurisdiction=config['jurisdiction'],
                            regulatory_framework=config['framework'],
                            regulatory_body=config['body'],
                            compliance_category=config['category'],
                            requirement_title=requirement['title'],
                            requirement_description=requirement['description'],
                            compliance_status=requirement['status'],
                            compliance_date=date.today() - timedelta(days=random.randint(30, 365)),
                            expiry_date=date.today() + timedelta(days=random.randint(180, 1095)),
                            compliance_risk_level=requirement['risk'],
                            responsible_person=f"{scheme.scheme_name} Site Manager",
                            next_review_date=date.today() + timedelta(days=random.randint(90, 180))
                        )
                        compliance_records.append(compliance)
        
        return compliance_records
    
    def _create_performance_metrics(self, group, partners, schemes):
        """Create performance metrics data."""
        performance_metrics = []
        
        # Partner performance metrics
        partner_metrics = [
            {
                'name': 'Project Delivery Success Rate',
                'category': 'operational',
                'unit': '%',
                'target': Decimal('95.0'),
                'benchmark': Decimal('88.0')
            },
            {
                'name': 'Cost Overrun Rate',
                'category': 'financial',
                'unit': '%',
                'target': Decimal('5.0'),
                'benchmark': Decimal('12.0')
            },
            {
                'name': 'ESG Score',
                'category': 'sustainability',
                'unit': 'score',
                'target': Decimal('4.0'),
                'benchmark': Decimal('3.2')
            }
        ]
        
        # Scheme performance metrics
        scheme_metrics = [
            {
                'name': 'Occupancy Rate',
                'category': 'operational',
                'unit': '%',
                'target': Decimal('95.0'),
                'benchmark': Decimal('92.0')
            },
            {
                'name': 'Student Satisfaction',
                'category': 'satisfaction',
                'unit': 'score',
                'target': Decimal('4.0'),
                'benchmark': Decimal('3.8')
            },
            {
                'name': 'Energy Efficiency',
                'category': 'sustainability',
                'unit': 'kWh/m²',
                'target': Decimal('85.0'),
                'benchmark': Decimal('95.0')
            },
            {
                'name': 'Maintenance Cost per Bed',
                'category': 'financial',
                'unit': '£',
                'target': Decimal('800.0'),
                'benchmark': Decimal('950.0')
            }
        ]
        
        # Create historical data (last 12 months)
        for month_offset in range(12):
            measurement_date = date.today() - timedelta(days=30 * month_offset)
            
            # Partner metrics
            for partner in partners:
                for metric_config in partner_metrics:
                    # Generate realistic values with some variance
                    target = metric_config['target']
                    variance = random.uniform(-15, 10)  # More likely to be under target
                    value = target * (1 + variance / 100)
                    
                    # Calculate variances
                    target_variance = ((value - target) / target) * 100
                    benchmark_variance = ((value - metric_config['benchmark']) / metric_config['benchmark']) * 100
                    
                    metric = PerformanceMetric.objects.create(
                        group=group,
                        partner=partner,
                        metric_name=metric_config['name'],
                        metric_category=metric_config['category'],
                        measurement_date=measurement_date,
                        metric_value=round(value, 2),
                        metric_unit=metric_config['unit'],
                        target_value=target,
                        benchmark_value=metric_config['benchmark'],
                        variance_from_target_pct=round(target_variance, 2),
                        variance_from_benchmark_pct=round(benchmark_variance, 2),
                        data_source='Management Information System',
                        data_quality_score=random.randint(3, 5),
                        measurement_frequency='monthly',
                        trend_direction=random.choice(['improving', 'stable', 'declining']),
                        performance_notes=f'Monthly measurement for {measurement_date.strftime("%B %Y")}'
                    )
                    performance_metrics.append(metric)
            
            # Scheme metrics
            for scheme in schemes:
                for metric_config in scheme_metrics:
                    target = metric_config['target']
                    # Different variance pattern for different metrics
                    if metric_config['name'] in ['Occupancy Rate', 'Student Satisfaction']:
                        variance = random.uniform(-5, 8)  # Generally good performance
                    else:
                        variance = random.uniform(-12, 15)
                    
                    value = target * (1 + variance / 100)
                    
                    # Calculate variances
                    target_variance = ((value - target) / target) * 100
                    benchmark_variance = ((value - metric_config['benchmark']) / metric_config['benchmark']) * 100
                    
                    metric = PerformanceMetric.objects.create(
                        group=group,
                        scheme=scheme,
                        metric_name=metric_config['name'],
                        metric_category=metric_config['category'],
                        measurement_date=measurement_date,
                        metric_value=round(value, 2),
                        metric_unit=metric_config['unit'],
                        target_value=target,
                        benchmark_value=metric_config['benchmark'],
                        variance_from_target_pct=round(target_variance, 2),
                        variance_from_benchmark_pct=round(benchmark_variance, 2),
                        data_source='Property Management System',
                        data_quality_score=random.randint(4, 5),
                        measurement_frequency='monthly',
                        trend_direction=random.choice(['improving', 'stable']),
                        performance_notes=f'Monthly measurement for {measurement_date.strftime("%B %Y")}',
                        action_required=abs(target_variance) > 10
                    )
                    performance_metrics.append(metric)
        
        return performance_metrics
    
    def _create_esg_assessments(self, group, partners, schemes):
        """Create ESG assessment data."""
        esg_assessments = []
        
        # Create quarterly ESG assessments for the last year
        quarters = [
            (date(2024, 3, 31), 'Q1 2024'),
            (date(2024, 6, 30), 'Q2 2024'),
            (date(2024, 9, 30), 'Q3 2024'),
            (date(2024, 12, 31), 'Q4 2024'),
        ]
        
        frameworks = ['gri', 'sasb', 'tcfd', 'un_sdg']
        
        for quarter_end, quarter_name in quarters:
            quarter_start = quarter_end - timedelta(days=90)
            
            # Partner ESG assessments
            for partner in partners:
                assessment = ESGAssessment.objects.create(
                    group=group,
                    partner=partner,
                    assessment_name=f'{partner.company_name} ESG Assessment {quarter_name}',
                    assessment_framework=random.choice(frameworks),
                    assessment_period_start=quarter_start,
                    assessment_period_end=quarter_end,
                    
                    # Environmental scores (with some improvement over time)
                    environmental_score=random.randint(3, 5),
                    renewable_energy_pct=Decimal(str(random.uniform(20, 60))),
                    carbon_footprint_tonnes=Decimal(str(random.uniform(500, 2000))),
                    energy_efficiency_rating=random.choice(['A', 'B', 'C']),
                    water_efficiency_score=random.randint(3, 5),
                    waste_diversion_rate_pct=Decimal(str(random.uniform(60, 90))),
                    environmental_certifications=['ISO14001', 'BREEAM'],
                    
                    # Social scores
                    social_score=random.randint(3, 5),
                    community_investment_amount=Decimal(str(random.uniform(25000, 100000))),
                    local_employment_pct=Decimal(str(random.uniform(60, 85))),
                    health_safety_incidents=random.randint(0, 3),
                    accessibility_compliance_score=random.randint(4, 5),
                    
                    # Governance scores
                    governance_score=random.randint(3, 5),
                    board_diversity_pct=Decimal(str(random.uniform(30, 60))),
                    ethics_training_completion_pct=Decimal(str(random.uniform(85, 100))),
                    transparency_score=random.randint(3, 5),
                    anti_corruption_policies=True,
                    
                    # Improvement planning
                    improvement_areas=['energy efficiency', 'waste reduction', 'community engagement'],
                    action_plan=f'Quarterly action plan for {quarter_name}',
                    next_assessment_date=quarter_end + timedelta(days=90)
                )
                esg_assessments.append(assessment)
            
            # Scheme ESG assessments
            for scheme in schemes:
                assessment = ESGAssessment.objects.create(
                    group=group,
                    scheme=scheme,
                    assessment_name=f'{scheme.scheme_name} ESG Assessment {quarter_name}',
                    assessment_framework=random.choice(frameworks),
                    assessment_period_start=quarter_start,
                    assessment_period_end=quarter_end,
                    
                    # Environmental scores
                    environmental_score=random.randint(3, 5),
                    carbon_footprint_tonnes=Decimal(str(random.uniform(100, 400))),
                    energy_efficiency_rating=random.choice(['A', 'B', 'C']),
                    renewable_energy_pct=Decimal(str(random.uniform(30, 70))),
                    water_efficiency_score=random.randint(3, 5),
                    waste_diversion_rate_pct=Decimal(str(random.uniform(70, 95))),
                    environmental_certifications=['BREEAM Excellent', 'LEED Gold'],
                    
                    # Social scores
                    social_score=random.randint(4, 5),
                    student_satisfaction_score=Decimal(str(random.uniform(3.8, 4.8))),
                    accessibility_compliance_score=5,
                    community_investment_amount=Decimal(str(random.uniform(10000, 50000))),
                    local_employment_pct=Decimal(str(random.uniform(70, 90))),
                    health_safety_incidents=random.randint(0, 2),
                    
                    # Governance scores
                    governance_score=random.randint(3, 4),
                    transparency_score=random.randint(3, 5),
                    anti_corruption_policies=True,
                    
                    # Improvement planning
                    improvement_areas=['carbon reduction', 'student wellbeing', 'biodiversity'],
                    action_plan=f'Scheme improvement plan for {quarter_name}',
                    next_assessment_date=quarter_end + timedelta(days=90)
                )
                esg_assessments.append(assessment)
        
        return esg_assessments
    
    def _create_audit_trail(self, group, admin_user, partners, schemes):
        """Create audit trail entries."""
        audit_entries = []
        
        # Audit events for the last 30 days
        for days_ago in range(30):
            audit_date = datetime.now() - timedelta(days=days_ago)
            
            # Random audit events
            events = [
                {
                    'entity_type': 'DevelopmentPartner',
                    'entity_id': random.choice(partners).id,
                    'action': 'update',
                    'summary': 'Updated partner information',
                    'risk': RiskLevel.LOW
                },
                {
                    'entity_type': 'PBSAScheme',
                    'entity_id': random.choice(schemes).id,
                    'action': 'update',
                    'summary': 'Updated scheme details',
                    'risk': RiskLevel.LOW
                },
                {
                    'entity_type': 'ESGAssessment',
                    'entity_id': random.choice(schemes).id,
                    'action': 'create',
                    'summary': 'Created new ESG assessment',
                    'risk': RiskLevel.MEDIUM
                },
                {
                    'entity_type': 'RegulatoryCompliance',
                    'entity_id': random.choice(partners).id,
                    'action': 'approve',
                    'summary': 'Approved compliance status',
                    'risk': RiskLevel.LOW
                }
            ]
            
            # Create 1-3 random events per day
            for _ in range(random.randint(1, 3)):
                event = random.choice(events)
                
                audit = AuditTrail.objects.create(
                    group=group,
                    entity_type=event['entity_type'],
                    entity_id=event['entity_id'],
                    action_type=event['action'],
                    changed_fields={
                        'example_field': {
                            'old': 'old_value',
                            'new': 'new_value'
                        }
                    },
                    change_summary=event['summary'],
                    user=admin_user,
                    ip_address='192.168.1.100',
                    business_justification=f'Regular {event["action"]} operation',
                    risk_assessment=event['risk'],
                    created_at=audit_date
                )
                audit_entries.append(audit)
        
        return audit_entries