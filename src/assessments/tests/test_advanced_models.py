"""
Tests for advanced features models - Phase 5.

Comprehensive test suite for version control, regulatory compliance,
performance monitoring, and ESG assessment capabilities.
"""

from decimal import Decimal
from datetime import date, datetime, timedelta
import json

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import Group
from assessments.partner_models import DevelopmentPartner
from assessments.scheme_models import PBSAScheme, DevelopmentStage
from assessments.assessment_models import Assessment, AssessmentType
from assessments.advanced_models import (
    VersionedEntity, RegulatoryCompliance, PerformanceMetric,
    ESGAssessment, AuditTrail
)
from assessments.enums import Currency, RiskLevel, AssessmentStatus

User = get_user_model()


class VersionedEntityTestCase(TestCase):
    """Test version control functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            email="test@example.com",
            role="admin",
            first_name="Test",
            last_name="User"
        )
        
        # Create a development partner to use as test entity
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name="Test Developer Ltd",
            assessment_priority="high"
        )
    
    def test_semantic_versioning(self):
        """Test semantic version string generation."""
        # Initial version
        self.assertEqual(self.partner.semver, "1.0.0")
        
        # Patch increment
        self.partner.increment_version('patch', 'Bug fix')
        self.assertEqual(self.partner.semver, "1.0.1")
        
        # Minor increment
        self.partner.increment_version('minor', 'New feature')
        self.assertEqual(self.partner.semver, "1.1.0")
        
        # Major increment
        self.partner.increment_version('major', 'Breaking change')
        self.assertEqual(self.partner.semver, "2.0.0")
    
    def test_version_increment_resets_approval(self):
        """Test that version increment resets approval status."""
        # Approve initial version
        self.partner.approve_version(self.user, "Initial approval")
        self.assertTrue(self.partner.is_approved)
        self.assertTrue(self.partner.is_published)
        
        # Increment version
        self.partner.increment_version('patch', 'Bug fix')
        self.assertFalse(self.partner.is_approved)
        self.assertFalse(self.partner.is_published)
        self.assertIsNone(self.partner.approved_by)
        self.assertIsNone(self.partner.approved_at)
    
    def test_approval_workflow(self):
        """Test version approval workflow."""
        self.assertFalse(self.partner.is_approved)
        
        # Approve version
        approval_time = timezone.now()
        self.partner.approve_version(self.user, "Approved for production")
        
        self.assertTrue(self.partner.is_approved)
        self.assertTrue(self.partner.is_published)
        self.assertEqual(self.partner.approved_by, self.user)
        self.assertIsNotNone(self.partner.approved_at)
        self.assertGreaterEqual(self.partner.approved_at, approval_time)


class RegulatoryComplianceTestCase(TestCase):
    """Test regulatory compliance tracking."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            email="test@example.com",
            role="admin"
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name="Test Developer Ltd",
            assessment_priority="medium"
        )
        
        self.scheme = PBSAScheme.objects.create(
            group=self.group,
            scheme_name="Test Scheme",
            scheme_reference="TS001",
            developer=self.partner,
            total_beds=200,
            development_stage=DevelopmentStage.PLANNING,
            total_development_cost_amount=Decimal('15000000'),
            total_development_cost_currency=Currency.GBP
        )
    
    def test_regulatory_compliance_creation(self):
        """Test creating regulatory compliance record."""
        compliance = RegulatoryCompliance.objects.create(
            group=self.group,
            partner=self.partner,
            jurisdiction='GB',
            regulatory_framework='Building Regulations 2010',
            regulatory_body='Local Planning Authority',
            compliance_category='building',
            requirement_title='Fire Safety Compliance',
            requirement_description='Compliance with fire safety regulations',
            compliance_status='compliant',
            compliance_date=date.today(),
            compliance_risk_level=RiskLevel.LOW
        )
        
        self.assertEqual(compliance.partner, self.partner)
        self.assertEqual(compliance.jurisdiction, 'GB')
        self.assertEqual(compliance.compliance_status, 'compliant')
        self.assertFalse(compliance.is_expiring_soon)
    
    def test_expiry_detection(self):
        """Test compliance expiry detection."""
        # Create compliance expiring in 30 days
        expiry_date = date.today() + timedelta(days=30)
        compliance = RegulatoryCompliance.objects.create(
            group=self.group,
            scheme=self.scheme,
            jurisdiction='GB',
            regulatory_framework='Planning Permission',
            regulatory_body='Local Council',
            compliance_category='planning',
            requirement_title='Planning Consent',
            requirement_description='Valid planning permission',
            compliance_status='compliant',
            expiry_date=expiry_date,
            compliance_risk_level=RiskLevel.MEDIUM
        )
        
        self.assertTrue(compliance.is_expiring_soon)
        self.assertEqual(compliance.days_until_expiry, 30)
    
    def test_compliance_scoring(self):
        """Test compliance score calculation."""
        # Test different compliance statuses
        statuses_scores = [
            ('compliant', 5),
            ('partial', 3),
            ('non_compliant', 1),
            ('pending', 2),
            ('exempt', 5),
            ('not_applicable', 5)
        ]
        
        for status, expected_score in statuses_scores:
            compliance = RegulatoryCompliance.objects.create(
                group=self.group,
                partner=self.partner,
                jurisdiction='GB',
                regulatory_framework=f'Framework {status}',
                regulatory_body='Test Authority',
                compliance_category='financial',
                requirement_title=f'Requirement {status}',
                requirement_description='Test requirement',
                compliance_status=status,
                compliance_risk_level=RiskLevel.LOW
            )
            
            self.assertEqual(compliance.compliance_score, expected_score)
    
    def test_expiry_impact_on_score(self):
        """Test that expiring compliance affects score."""
        # Create compliance expiring soon
        expiry_date = date.today() + timedelta(days=30)
        compliance = RegulatoryCompliance.objects.create(
            group=self.group,
            partner=self.partner,
            jurisdiction='GB',
            regulatory_framework='Test Framework',
            regulatory_body='Test Authority',
            compliance_category='environmental',
            requirement_title='Environmental Permit',
            requirement_description='Valid environmental permit',
            compliance_status='compliant',  # Normally would be score 5
            expiry_date=expiry_date,
            compliance_risk_level=RiskLevel.HIGH
        )
        
        # Score should be reduced due to expiry
        self.assertEqual(compliance.compliance_score, 4)  # 5 - 1 for expiry


class PerformanceMetricTestCase(TestCase):
    """Test performance monitoring functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            email="test@example.com",
            role="analyst"
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name="Performance Test Developer",
            assessment_priority="high"
        )
        
        self.scheme = PBSAScheme.objects.create(
            group=self.group,
            scheme_name="Performance Test Scheme",
            scheme_reference="PTS001",
            developer=self.partner,
            total_beds=300,
            development_stage=DevelopmentStage.OPERATIONAL,
            total_development_cost_amount=Decimal('20000000'),
            total_development_cost_currency=Currency.GBP
        )
    
    def test_performance_metric_creation(self):
        """Test creating performance metrics."""
        metric = PerformanceMetric.objects.create(
            group=self.group,
            scheme=self.scheme,
            metric_name='Occupancy Rate',
            metric_category='operational',
            metric_description='Percentage of beds occupied',
            measurement_date=date.today(),
            metric_value=Decimal('95.5'),
            metric_unit='%',
            target_value=Decimal('95.0'),
            benchmark_value=Decimal('92.0'),
            data_source='Property Management System',
            measurement_frequency='monthly'
        )
        
        self.assertEqual(metric.scheme, self.scheme)
        self.assertEqual(metric.metric_name, 'Occupancy Rate')
        self.assertEqual(metric.metric_value, Decimal('95.5'))
    
    def test_variance_calculations(self):
        """Test variance calculations from target and benchmark."""
        metric = PerformanceMetric.objects.create(
            group=self.group,
            partner=self.partner,
            metric_name='Cost per Bed',
            metric_category='financial',
            measurement_date=date.today(),
            metric_value=Decimal('65000'),
            metric_unit='£',
            target_value=Decimal('60000'),
            benchmark_value=Decimal('70000'),
            data_source='Financial System',
            measurement_frequency='annually'
        )
        
        # Calculate and set variances (would normally be done in save method or signal)
        target_variance = ((metric.metric_value - metric.target_value) / metric.target_value) * 100
        benchmark_variance = ((metric.metric_value - metric.benchmark_value) / metric.benchmark_value) * 100
        
        metric.variance_from_target_pct = round(target_variance, 2)
        metric.variance_from_benchmark_pct = round(benchmark_variance, 2)
        metric.save()
        
        self.assertEqual(metric.variance_from_target_pct, Decimal('8.33'))  # 5000/60000 * 100
        self.assertEqual(metric.variance_from_benchmark_pct, Decimal('-7.14'))  # -5000/70000 * 100
    
    def test_performance_rating(self):
        """Test performance rating based on target achievement."""
        # Test excellent performance (within 5% of target)
        metric = PerformanceMetric.objects.create(
            group=self.group,
            scheme=self.scheme,
            metric_name='Student Satisfaction',
            metric_category='satisfaction',
            measurement_date=date.today(),
            metric_value=Decimal('4.8'),
            target_value=Decimal('4.5'),
            variance_from_target_pct=Decimal('3.0'),
            data_source='Survey Results',
            measurement_frequency='quarterly'
        )
        
        self.assertEqual(metric.performance_rating, "Excellent")
        
        # Test poor performance (variance > 20%)
        metric.variance_from_target_pct = Decimal('25.0')
        self.assertEqual(metric.performance_rating, "Poor")
    
    def test_target_achievement_assessment(self):
        """Test target achievement for different metric types."""
        # Test occupancy rate (higher is better)
        occupancy_metric = PerformanceMetric.objects.create(
            group=self.group,
            scheme=self.scheme,
            metric_name='occupancy_rate',
            metric_category='operational',
            measurement_date=date.today(),
            metric_value=Decimal('96.0'),
            target_value=Decimal('95.0'),
            data_source='PMS',
            measurement_frequency='monthly'
        )
        
        self.assertTrue(occupancy_metric.is_meeting_target)
        
        # Test cost overrun (lower is better)
        cost_metric = PerformanceMetric.objects.create(
            group=self.group,
            scheme=self.scheme,
            metric_name='cost_overrun',
            metric_category='financial',
            measurement_date=date.today(),
            metric_value=Decimal('5.0'),
            target_value=Decimal('8.0'),
            data_source='Project Management',
            measurement_frequency='monthly'
        )
        
        self.assertTrue(cost_metric.is_meeting_target)


class ESGAssessmentTestCase(TestCase):
    """Test ESG assessment functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(name="ESG Test Group")
        self.user = User.objects.create_user(
            email="esg@example.com",
            role="assessor"
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name="Green Developer Ltd",
            assessment_priority="high"
        )
        
        self.scheme = PBSAScheme.objects.create(
            group=self.group,
            scheme_name="Eco Student Village",
            scheme_reference="ESV001",
            developer=self.partner,
            total_beds=400,
            development_stage=DevelopmentStage.OPERATIONAL,
            total_development_cost_amount=Decimal('25000000'),
            total_development_cost_currency=Currency.GBP
        )
    
    def test_esg_assessment_creation(self):
        """Test creating ESG assessment."""
        assessment = ESGAssessment.objects.create(
            group=self.group,
            scheme=self.scheme,
            assessment_name='Q4 2024 ESG Assessment',
            assessment_framework='gri',
            assessment_period_start=date(2024, 10, 1),
            assessment_period_end=date(2024, 12, 31),
            environmental_score=4,
            social_score=3,
            governance_score=4,
            carbon_footprint_tonnes=Decimal('150.50'),
            energy_efficiency_rating='B',
            renewable_energy_pct=Decimal('35.0'),
            community_investment_amount=Decimal('50000'),
            local_employment_pct=Decimal('65.0'),
            board_diversity_pct=Decimal('40.0')
        )
        
        self.assertEqual(assessment.scheme, self.scheme)
        self.assertEqual(assessment.environmental_score, 4)
        self.assertEqual(assessment.social_score, 3)
        self.assertEqual(assessment.governance_score, 4)
    
    def test_overall_score_calculation(self):
        """Test overall ESG score calculation."""
        assessment = ESGAssessment.objects.create(
            group=self.group,
            partner=self.partner,
            assessment_name='Partner ESG Assessment',
            assessment_framework='sasb',
            assessment_period_start=date(2024, 1, 1),
            assessment_period_end=date(2024, 12, 31),
            environmental_score=5,  # 40% weight
            social_score=3,         # 30% weight
            governance_score=4      # 30% weight
        )
        
        # Expected: (5 * 0.4) + (3 * 0.3) + (4 * 0.3) = 2.0 + 0.9 + 1.2 = 4.1
        expected_score = Decimal('4.10')
        calculated_score = assessment.calculate_overall_score()
        
        self.assertEqual(calculated_score, expected_score)
    
    def test_esg_rating_determination(self):
        """Test ESG rating classification."""
        test_cases = [
            (5, 4, 5, 'AAA'),    # Score: 4.7
            (4, 4, 4, 'AA'),     # Score: 4.0
            (3, 4, 4, 'A'),      # Score: 3.6
            (3, 3, 3, 'BBB'),    # Score: 3.0
            (2, 3, 3, 'BB'),     # Score: 2.6
            (2, 2, 2, 'B'),      # Score: 2.0
            (1, 1, 2, 'CCC'),    # Score: 1.3
        ]
        
        for env_score, social_score, gov_score, expected_rating in test_cases:
            assessment = ESGAssessment(
                environmental_score=env_score,
                social_score=social_score,
                governance_score=gov_score
            )
            
            actual_rating = assessment.determine_esg_rating()
            self.assertEqual(actual_rating, expected_rating,
                           f"E:{env_score}, S:{social_score}, G:{gov_score} should be {expected_rating}, got {actual_rating}")
    
    def test_carbon_intensity_calculation(self):
        """Test carbon intensity per bed calculation."""
        assessment = ESGAssessment.objects.create(
            group=self.group,
            scheme=self.scheme,
            assessment_name='Carbon Assessment',
            assessment_framework='tcfd',
            assessment_period_start=date(2024, 1, 1),
            assessment_period_end=date(2024, 12, 31),
            environmental_score=3,
            social_score=3,
            governance_score=3,
            carbon_footprint_tonnes=Decimal('200.0')  # 400 beds in scheme
        )
        
        # 200 tonnes / 400 beds = 0.5 tonnes per bed
        expected_intensity = Decimal('0.50')
        self.assertEqual(assessment.carbon_intensity, expected_intensity)
    
    def test_auto_calculation_on_save(self):
        """Test that overall score and rating are calculated on save."""
        assessment = ESGAssessment.objects.create(
            group=self.group,
            partner=self.partner,
            assessment_name='Auto Calc Test',
            assessment_framework='custom',
            assessment_period_start=date(2024, 1, 1),
            assessment_period_end=date(2024, 12, 31),
            environmental_score=4,
            social_score=4,
            governance_score=5
        )
        
        # Should auto-calculate: (4 * 0.4) + (4 * 0.3) + (5 * 0.3) = 4.3
        self.assertEqual(assessment.overall_esg_score, Decimal('4.30'))
        self.assertEqual(assessment.esg_rating, 'AA')


class AuditTrailTestCase(TestCase):
    """Test audit trail functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(name="Audit Test Group")
        self.user = User.objects.create_user(
            email="audit@example.com",
            role="admin"
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name="Audit Test Developer",
            assessment_priority="medium"
        )
    
    def test_audit_trail_creation(self):
        """Test creating audit trail entries."""
        trail = AuditTrail.objects.create(
            group=self.group,
            entity_type='DevelopmentPartner',
            entity_id=self.partner.id,
            action_type='update',
            changed_fields={
                'company_name': {
                    'old': 'Old Company Name',
                    'new': 'Audit Test Developer'
                },
                'assessment_priority': {
                    'old': 'low',
                    'new': 'medium'
                }
            },
            change_summary='Updated company details and priority',
            user=self.user,
            ip_address='192.168.1.100',
            business_justification='Rebranding and priority adjustment',
            risk_assessment=RiskLevel.LOW
        )
        
        self.assertEqual(trail.entity_type, 'DevelopmentPartner')
        self.assertEqual(trail.entity_id, self.partner.id)
        self.assertEqual(trail.action_type, 'update')
        self.assertEqual(trail.user, self.user)
        self.assertEqual(len(trail.changed_fields), 2)
    
    def test_audit_trail_querying(self):
        """Test querying audit trail by entity."""
        # Create multiple audit entries
        actions = ['create', 'update', 'approve']
        
        for action in actions:
            AuditTrail.objects.create(
                group=self.group,
                entity_type='DevelopmentPartner',
                entity_id=self.partner.id,
                action_type=action,
                change_summary=f'Partner {action}',
                user=self.user,
                risk_assessment=RiskLevel.LOW
            )
        
        # Query audit trail for this partner
        partner_audit = AuditTrail.objects.filter(
            entity_type='DevelopmentPartner',
            entity_id=self.partner.id
        ).order_by('-created_at')
        
        self.assertEqual(partner_audit.count(), 3)
        self.assertEqual(partner_audit[0].action_type, 'approve')  # Most recent
        self.assertEqual(partner_audit[2].action_type, 'create')   # Oldest
    
    def test_risk_assessment_tracking(self):
        """Test risk assessment in audit trails."""
        high_risk_change = AuditTrail.objects.create(
            group=self.group,
            entity_type='Assessment',
            entity_id=self.partner.id,  # Using partner ID as example
            action_type='delete',
            change_summary='Deleted critical assessment',
            user=self.user,
            business_justification='Data quality issues',
            risk_assessment=RiskLevel.HIGH
        )
        
        self.assertEqual(high_risk_change.risk_assessment, RiskLevel.HIGH)
        
        # Query high-risk changes
        high_risk_changes = AuditTrail.objects.filter(
            risk_assessment=RiskLevel.HIGH
        )
        
        self.assertEqual(high_risk_changes.count(), 1)


class IntegrationTestCase(TestCase):
    """Test integration between advanced features."""
    
    def setUp(self):
        """Set up comprehensive test data."""
        self.group = Group.objects.create(name="Integration Test Group")
        self.user = User.objects.create_user(
            email="integration@example.com",
            role="manager"
        )
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name="Integration Test Developer",
            assessment_priority="high"
        )
        
        self.scheme = PBSAScheme.objects.create(
            group=self.group,
            scheme_name="Integration Test Scheme",
            scheme_reference="ITS001",
            developer=self.partner,
            total_beds=500,
            development_stage=DevelopmentStage.OPERATIONAL,
            total_development_cost_amount=Decimal('30000000'),
            total_development_cost_currency=Currency.GBP
        )
    
    def test_comprehensive_monitoring_setup(self):
        """Test setting up comprehensive monitoring for a scheme."""
        # Create regulatory compliance
        compliance = RegulatoryCompliance.objects.create(
            group=self.group,
            scheme=self.scheme,
            jurisdiction='GB',
            regulatory_framework='Building Safety Act 2022',
            regulatory_body='Building Safety Regulator',
            compliance_category='building',
            requirement_title='Building Safety Case',
            requirement_description='Mandatory safety case for high-rise buildings',
            compliance_status='compliant',
            compliance_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            compliance_risk_level=RiskLevel.HIGH
        )
        
        # Create performance metrics
        metrics = [
            {
                'name': 'Occupancy Rate',
                'category': 'operational',
                'value': Decimal('97.5'),
                'target': Decimal('95.0'),
                'unit': '%'
            },
            {
                'name': 'Student Satisfaction',
                'category': 'satisfaction',
                'value': Decimal('4.2'),
                'target': Decimal('4.0'),
                'unit': 'score'
            },
            {
                'name': 'Energy Efficiency',
                'category': 'sustainability',
                'value': Decimal('85.0'),
                'target': Decimal('80.0'),
                'unit': 'kWh/m²'
            }
        ]
        
        created_metrics = []
        for metric_data in metrics:
            metric = PerformanceMetric.objects.create(
                group=self.group,
                scheme=self.scheme,
                metric_name=metric_data['name'],
                metric_category=metric_data['category'],
                measurement_date=date.today(),
                metric_value=metric_data['value'],
                target_value=metric_data['target'],
                metric_unit=metric_data['unit'],
                data_source='Integration Test',
                measurement_frequency='monthly'
            )
            created_metrics.append(metric)
        
        # Create ESG assessment
        esg_assessment = ESGAssessment.objects.create(
            group=self.group,
            scheme=self.scheme,
            assessment_name='Q4 2024 Comprehensive ESG',
            assessment_framework='gri',
            assessment_period_start=date(2024, 10, 1),
            assessment_period_end=date(2024, 12, 31),
            environmental_score=4,
            social_score=5,
            governance_score=4,
            carbon_footprint_tonnes=Decimal('180.0'),
            energy_efficiency_rating='A',
            renewable_energy_pct=Decimal('60.0'),
            community_investment_amount=Decimal('75000'),
            local_employment_pct=Decimal('80.0'),
            student_satisfaction_score=Decimal('4.3'),
            board_diversity_pct=Decimal('50.0')
        )
        
        # Verify all components are linked to scheme
        self.assertEqual(
            RegulatoryCompliance.objects.filter(scheme=self.scheme).count(),
            1
        )
        self.assertEqual(
            PerformanceMetric.objects.filter(scheme=self.scheme).count(),
            3
        )
        self.assertEqual(
            ESGAssessment.objects.filter(scheme=self.scheme).count(),
            1
        )
        
        # Test comprehensive scheme analysis
        scheme_compliance = RegulatoryCompliance.objects.filter(scheme=self.scheme)
        scheme_metrics = PerformanceMetric.objects.filter(scheme=self.scheme)
        scheme_esg = ESGAssessment.objects.filter(scheme=self.scheme).first()
        
        # All should be linked to the same scheme
        self.assertTrue(all(c.scheme == self.scheme for c in scheme_compliance))
        self.assertTrue(all(m.scheme == self.scheme for m in scheme_metrics))
        self.assertEqual(scheme_esg.scheme, self.scheme)
        
        # Verify performance quality
        self.assertEqual(compliance.compliance_score, 5)  # Compliant
        self.assertEqual(esg_assessment.overall_esg_score, Decimal('4.30'))
        self.assertEqual(esg_assessment.esg_rating, 'AA')
    
    def test_version_control_with_audit_trail(self):
        """Test version control integration with audit trail."""
        # Create initial ESG assessment
        esg = ESGAssessment.objects.create(
            group=self.group,
            partner=self.partner,
            assessment_name='Partner ESG v1.0',
            assessment_framework='gri',
            assessment_period_start=date(2024, 1, 1),
            assessment_period_end=date(2024, 12, 31),
            environmental_score=3,
            social_score=3,
            governance_score=3
        )
        
        # Record initial creation in audit trail
        creation_audit = AuditTrail.objects.create(
            group=self.group,
            entity_type='ESGAssessment',
            entity_id=esg.id,
            action_type='create',
            change_summary='Initial ESG assessment created',
            user=self.user,
            risk_assessment=RiskLevel.LOW
        )
        
        # Update ESG scores (version increment)
        original_version = esg.semver
        esg.environmental_score = 4
        esg.social_score = 4
        esg.increment_version('minor', 'Improved environmental and social scores')
        esg.save()
        
        # Record update in audit trail
        update_audit = AuditTrail.objects.create(
            group=self.group,
            entity_type='ESGAssessment',
            entity_id=esg.id,
            action_type='update',
            changed_fields={
                'environmental_score': {'old': 3, 'new': 4},
                'social_score': {'old': 3, 'new': 4},
                'version': {'old': original_version, 'new': esg.semver}
            },
            change_summary='Updated ESG scores and incremented version',
            user=self.user,
            risk_assessment=RiskLevel.LOW
        )
        
        # Approve new version
        esg.approve_version(self.user, 'Approved improved ESG scores')
        esg.save()
        
        # Record approval in audit trail
        approval_audit = AuditTrail.objects.create(
            group=self.group,
            entity_type='ESGAssessment',
            entity_id=esg.id,
            action_type='approve',
            change_summary=f'Approved version {esg.semver}',
            user=self.user,
            risk_assessment=RiskLevel.LOW
        )
        
        # Verify version progression and audit trail
        self.assertEqual(esg.semver, '1.1.0')
        self.assertTrue(esg.is_approved)
        
        audit_entries = AuditTrail.objects.filter(
            entity_type='ESGAssessment',
            entity_id=esg.id
        ).order_by('created_at')
        
        self.assertEqual(audit_entries.count(), 3)
        self.assertEqual(audit_entries[0].action_type, 'create')
        self.assertEqual(audit_entries[1].action_type, 'update')
        self.assertEqual(audit_entries[2].action_type, 'approve')