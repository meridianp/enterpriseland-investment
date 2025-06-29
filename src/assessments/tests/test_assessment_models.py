"""
Tests for the Gold-Standard Assessment Framework models.

Comprehensive test suite covering scoring calculations, decision logic,
automated recommendations, and assessment workflows.
"""

from decimal import Decimal
from datetime import date, datetime
from unittest.mock import patch

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from accounts.models import Group
from assessments.assessment_models import (
    Assessment, AssessmentMetric, AssessmentTemplate, MetricTemplate,
    AssessmentType, MetricCategory, DecisionBand
)
from assessments.enums import AssessmentStatus
from assessments.partner_models import DevelopmentPartner, GeneralInformation, OperationalInformation
from assessments.financial_models import FinancialInformation, CreditInformation

User = get_user_model()


class AssessmentModelTest(TestCase):
    """Test the main Assessment model functionality."""
    
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
        
        self.assessment = Assessment.objects.create(
            group=self.group,
            assessment_type=AssessmentType.PARTNER,
            assessment_name='Test Partner Assessment',
            partner=self.partner,
            assessor=self.user,
            assessment_purpose='Due diligence for potential partnership'
        )
    
    def test_assessment_creation(self):
        """Test basic assessment creation."""
        self.assertEqual(self.assessment.assessment_name, 'Test Partner Assessment')
        self.assertEqual(self.assessment.assessment_type, AssessmentType.PARTNER)
        self.assertEqual(self.assessment.status, AssessmentStatus.DRAFT)
        self.assertEqual(self.assessment.partner, self.partner)
        self.assertEqual(self.assessment.assessor, self.user)
    
    def test_calculate_scores_empty(self):
        """Test score calculation with no metrics."""
        scores = self.assessment.calculate_scores()
        
        self.assertEqual(scores['total_weighted_score'], 0)
        self.assertEqual(scores['max_possible_score'], 0)
        self.assertEqual(scores['score_percentage'], 0)
        self.assertEqual(scores['metric_count'], 0)
        self.assertEqual(scores['category_scores'], {})
    
    def test_calculate_scores_with_metrics(self):
        """Test score calculation with metrics."""
        # Create test metrics
        AssessmentMetric.objects.create(
            group=self.group,
            assessment=self.assessment,
            metric_name='Financial Strength',
            category=MetricCategory.FINANCIAL,
            score=4,
            weight=5,
            justification='Strong balance sheet and profitability'
        )
        
        AssessmentMetric.objects.create(
            group=self.group,
            assessment=self.assessment,
            metric_name='Team Capability',
            category=MetricCategory.OPERATIONAL,
            score=3,
            weight=4,
            justification='Adequate team size and experience'
        )
        
        AssessmentMetric.objects.create(
            group=self.group,
            assessment=self.assessment,
            metric_name='Track Record',
            category=MetricCategory.TRACK_RECORD,
            score=5,
            weight=4,
            justification='Excellent delivery history'
        )
        
        scores = self.assessment.calculate_scores()
        
        # Expected: (4*5) + (3*4) + (5*4) = 20 + 12 + 20 = 52
        # Max possible: (5*5) + (5*4) + (5*4) = 25 + 20 + 20 = 65
        # Percentage: 52/65 * 100 = 80%
        
        self.assertEqual(scores['total_weighted_score'], 52)
        self.assertEqual(scores['max_possible_score'], 65)
        self.assertEqual(scores['score_percentage'], 80.0)
        self.assertEqual(scores['metric_count'], 3)
        
        # Check category breakdowns
        financial_score = scores['category_scores'][MetricCategory.FINANCIAL]
        self.assertEqual(financial_score['weighted_score'], 20)
        self.assertEqual(financial_score['max_possible'], 25)
        self.assertEqual(financial_score['percentage'], 80.0)
        
        operational_score = scores['category_scores'][MetricCategory.OPERATIONAL]
        self.assertEqual(operational_score['weighted_score'], 12)
        self.assertEqual(operational_score['max_possible'], 20)
        self.assertEqual(operational_score['percentage'], 60.0)
    
    def test_decision_band_calculation(self):
        """Test decision band determination based on scores."""
        # Test Premium/Priority (>165)
        self.assessment.total_weighted_score = 180
        self.assertEqual(
            self.assessment.determine_decision_band(),
            DecisionBand.PREMIUM_PRIORITY
        )
        
        # Test Acceptable (125-165)
        self.assessment.total_weighted_score = 150
        self.assertEqual(
            self.assessment.determine_decision_band(),
            DecisionBand.ACCEPTABLE
        )
        
        # Test Reject (<125)
        self.assessment.total_weighted_score = 100
        self.assertEqual(
            self.assessment.determine_decision_band(),
            DecisionBand.REJECT
        )
        
        # Test None score
        self.assessment.total_weighted_score = None
        self.assertEqual(self.assessment.determine_decision_band(), '')
    
    def test_strongest_categories(self):
        """Test identification of strongest performing categories."""
        # Create metrics with varying performance
        AssessmentMetric.objects.create(
            group=self.group,
            assessment=self.assessment,
            metric_name='Financial Health',
            category=MetricCategory.FINANCIAL,
            score=5,
            weight=4,
            justification='Excellent financial position'
        )
        
        AssessmentMetric.objects.create(
            group=self.group,
            assessment=self.assessment,
            metric_name='Operational Capability',
            category=MetricCategory.OPERATIONAL,
            score=2,
            weight=3,
            justification='Limited operational experience'
        )
        
        AssessmentMetric.objects.create(
            group=self.group,
            assessment=self.assessment,
            metric_name='Market Position',
            category=MetricCategory.MARKET,
            score=4,
            weight=3,
            justification='Strong market presence'
        )
        
        strongest = self.assessment.get_strongest_categories(2)
        
        # Financial: 5*4 / (5*4) = 100%
        # Market: 4*3 / (5*3) = 80%
        # Operational: 2*3 / (5*3) = 40%
        
        self.assertEqual(len(strongest), 2)
        self.assertEqual(strongest[0]['category'], MetricCategory.FINANCIAL)
        self.assertEqual(strongest[0]['percentage'], 100.0)
        self.assertEqual(strongest[1]['category'], MetricCategory.MARKET)
        self.assertEqual(strongest[1]['percentage'], 80.0)
    
    def test_weakest_categories(self):
        """Test identification of weakest performing categories."""
        # Using same metrics as strongest_categories test
        AssessmentMetric.objects.create(
            group=self.group,
            assessment=self.assessment,
            metric_name='Financial Health',
            category=MetricCategory.FINANCIAL,
            score=5,
            weight=4,
            justification='Excellent financial position'
        )
        
        AssessmentMetric.objects.create(
            group=self.group,
            assessment=self.assessment,
            metric_name='Operational Capability',
            category=MetricCategory.OPERATIONAL,
            score=2,
            weight=3,
            justification='Limited operational experience'
        )
        
        AssessmentMetric.objects.create(
            group=self.group,
            assessment=self.assessment,
            metric_name='Market Position',
            category=MetricCategory.MARKET,
            score=4,
            weight=3,
            justification='Strong market presence'
        )
        
        weakest = self.assessment.get_weakest_categories(2)
        
        self.assertEqual(len(weakest), 2)
        self.assertEqual(weakest[0]['category'], MetricCategory.OPERATIONAL)
        self.assertEqual(weakest[0]['percentage'], 40.0)
        self.assertEqual(weakest[1]['category'], MetricCategory.MARKET)
        self.assertEqual(weakest[1]['percentage'], 80.0)
    
    def test_automated_recommendations_high_score(self):
        """Test automated recommendations for high-scoring assessment."""
        self.assessment.score_percentage = 90
        self.assessment.decision_band = DecisionBand.PREMIUM_PRIORITY
        
        recommendations = self.assessment.generate_automated_recommendations()
        
        self.assertIn('Excellent overall performance', recommendations[0])
        self.assertIn('premium/priority status', recommendations[1])
    
    def test_automated_recommendations_low_score(self):
        """Test automated recommendations for low-scoring assessment."""
        self.assessment.score_percentage = 45
        self.assessment.decision_band = DecisionBand.REJECT
        
        # Create weak financial metric
        AssessmentMetric.objects.create(
            group=self.group,
            assessment=self.assessment,
            metric_name='Financial Health',
            category=MetricCategory.FINANCIAL,
            score=1,
            weight=5,
            justification='Poor financial position'
        )
        
        recommendations = self.assessment.generate_automated_recommendations()
        
        # Should include general low performance warning
        low_perf_found = any('below acceptable thresholds' in rec for rec in recommendations)
        self.assertTrue(low_perf_found)
        
        # Should include rejection recommendation
        reject_found = any('suggests rejection' in rec for rec in recommendations)
        self.assertTrue(reject_found)
    
    def test_refresh_calculated_fields(self):
        """Test refreshing of calculated fields."""
        # Create metrics
        AssessmentMetric.objects.create(
            group=self.group,
            assessment=self.assessment,
            metric_name='Test Metric',
            category=MetricCategory.FINANCIAL,
            score=4,
            weight=5,
            justification='Test justification'
        )
        
        # Refresh calculated fields
        self.assessment.refresh_calculated_fields()
        
        # Reload from database
        self.assessment.refresh_from_db()
        
        # Check updated fields
        self.assertEqual(self.assessment.total_weighted_score, 20)
        self.assertEqual(self.assessment.max_possible_score, 25)
        self.assertEqual(self.assessment.score_percentage, 80.0)
        self.assertEqual(self.assessment.decision_band, DecisionBand.ACCEPTABLE)
        self.assertIsNotNone(self.assessment.recommendations)
    
    def test_workflow_transitions(self):
        """Test assessment workflow state transitions."""
        # Test submit for review
        self.assessment.submit_for_review(self.user)
        self.assertEqual(self.assessment.status, AssessmentStatus.IN_REVIEW)
        self.assertIsNotNone(self.assessment.submitted_at)
        
        # Test approve
        reviewer = User.objects.create_user(
            email='reviewer@example.com',
            password='testpass123',
            role='MANAGER'
        )
        reviewer.groups.add(self.group)
        
        self.assessment.approve(reviewer)
        self.assertEqual(self.assessment.status, AssessmentStatus.APPROVED)
        self.assertEqual(self.assessment.approver, reviewer)
        self.assertIsNotNone(self.assessment.approved_at)
    
    def test_workflow_transition_validation(self):
        """Test workflow transition validation."""
        # Cannot submit non-draft for review
        self.assessment.status = AssessmentStatus.APPROVED
        with self.assertRaises(ValidationError):
            self.assessment.submit_for_review(self.user)
        
        # Cannot approve non-review status
        self.assessment.status = AssessmentStatus.DRAFT
        with self.assertRaises(ValidationError):
            self.assessment.approve(self.user)


class AssessmentMetricTest(TestCase):
    """Test the AssessmentMetric model functionality."""
    
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
        
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Test Developer Ltd'
        )
        
        self.assessment = Assessment.objects.create(
            group=self.group,
            assessment_type=AssessmentType.PARTNER,
            assessment_name='Test Assessment',
            partner=self.partner,
            assessor=self.user
        )
    
    def test_metric_creation(self):
        """Test basic metric creation."""
        metric = AssessmentMetric.objects.create(
            group=self.group,
            assessment=self.assessment,
            metric_name='Financial Strength',
            category=MetricCategory.FINANCIAL,
            score=4,
            weight=5,
            justification='Strong financial position with good liquidity'
        )
        
        self.assertEqual(metric.metric_name, 'Financial Strength')
        self.assertEqual(metric.score, 4)
        self.assertEqual(metric.weight, 5)
        self.assertEqual(metric.weighted_score, 20)
        self.assertEqual(metric.max_weighted_score, 25)
        self.assertEqual(metric.score_percentage, 80.0)
    
    def test_performance_levels(self):
        """Test performance level descriptions."""
        metric = AssessmentMetric.objects.create(
            group=self.group,
            assessment=self.assessment,
            metric_name='Test Metric',
            category=MetricCategory.FINANCIAL,
            score=5,
            weight=3,
            justification='Test'
        )
        
        # Test all performance levels
        metric.score = 5
        self.assertEqual(metric.performance_level, "Excellent")
        
        metric.score = 4
        self.assertEqual(metric.performance_level, "Good")
        
        metric.score = 3
        self.assertEqual(metric.performance_level, "Satisfactory")
        
        metric.score = 2
        self.assertEqual(metric.performance_level, "Needs Improvement")
        
        metric.score = 1
        self.assertEqual(metric.performance_level, "Poor")
    
    def test_importance_levels(self):
        """Test importance level descriptions."""
        metric = AssessmentMetric.objects.create(
            group=self.group,
            assessment=self.assessment,
            metric_name='Test Metric',
            category=MetricCategory.FINANCIAL,
            score=3,
            weight=5,
            justification='Test'
        )
        
        # Test all importance levels
        metric.weight = 5
        self.assertEqual(metric.importance_level, "Critical")
        
        metric.weight = 4
        self.assertEqual(metric.importance_level, "Very Important")
        
        metric.weight = 3
        self.assertEqual(metric.importance_level, "Important")
        
        metric.weight = 2
        self.assertEqual(metric.importance_level, "Moderate")
        
        metric.weight = 1
        self.assertEqual(metric.importance_level, "Minor")
    
    def test_metric_validation(self):
        """Test metric validation rules."""
        # Test score validation
        with self.assertRaises(ValidationError):
            metric = AssessmentMetric(
                group=self.group,
                assessment=self.assessment,
                metric_name='Invalid Score',
                category=MetricCategory.FINANCIAL,
                score=6,  # Invalid - must be 1-5
                weight=3,
                justification='Test'
            )
            metric.full_clean()
        
        # Test weight validation
        with self.assertRaises(ValidationError):
            metric = AssessmentMetric(
                group=self.group,
                assessment=self.assessment,
                metric_name='Invalid Weight',
                category=MetricCategory.FINANCIAL,
                score=3,
                weight=0,  # Invalid - must be 1-5
                justification='Test'
            )
            metric.full_clean()
    
    def test_duplicate_metric_name_validation(self):
        """Test that metric names must be unique within an assessment."""
        # Create first metric
        AssessmentMetric.objects.create(
            group=self.group,
            assessment=self.assessment,
            metric_name='Financial Strength',
            category=MetricCategory.FINANCIAL,
            score=4,
            weight=5,
            justification='Test'
        )
        
        # Try to create duplicate
        duplicate_metric = AssessmentMetric(
            group=self.group,
            assessment=self.assessment,
            metric_name='Financial Strength',  # Duplicate name
            category=MetricCategory.OPERATIONAL,
            score=3,
            weight=4,
            justification='Another test'
        )
        
        with self.assertRaises(ValidationError):
            duplicate_metric.clean()


class AssessmentTemplateTest(TestCase):
    """Test assessment template functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
    
    def test_template_creation(self):
        """Test basic template creation."""
        template = AssessmentTemplate.objects.create(
            group=self.group,
            template_name='Standard Partner Assessment',
            description='Standard template for partner due diligence',
            assessment_type=AssessmentType.PARTNER,
            version='1.0'
        )
        
        self.assertEqual(template.template_name, 'Standard Partner Assessment')
        self.assertEqual(template.assessment_type, AssessmentType.PARTNER)
        self.assertTrue(template.is_active)
        self.assertEqual(str(template), 'Standard Partner Assessment v1.0')
    
    def test_metric_template_creation(self):
        """Test metric template creation."""
        template = AssessmentTemplate.objects.create(
            group=self.group,
            template_name='Test Template',
            description='Test template',
            assessment_type=AssessmentType.PARTNER
        )
        
        metric_template = MetricTemplate.objects.create(
            group=self.group,
            template=template,
            metric_name='Financial Health',
            metric_description='Overall financial health assessment',
            category=MetricCategory.FINANCIAL,
            default_weight=5,
            assessment_guidelines='Assess balance sheet strength, profitability, and cash flow',
            scoring_criteria={
                '1': 'Poor financial health with significant concerns',
                '2': 'Weak financial position requiring attention',
                '3': 'Adequate financial health with some weaknesses',
                '4': 'Strong financial position with minor concerns',
                '5': 'Excellent financial health across all metrics'
            },
            is_mandatory=True,
            display_order=1
        )
        
        self.assertEqual(metric_template.metric_name, 'Financial Health')
        self.assertEqual(metric_template.default_weight, 5)
        self.assertTrue(metric_template.is_mandatory)
        self.assertEqual(metric_template.scoring_criteria['5'], 'Excellent financial health across all metrics')


class AssessmentIntegrationTest(TestCase):
    """Integration tests for the complete assessment framework."""
    
    def setUp(self):
        """Set up comprehensive test data."""
        self.user = User.objects.create_user(
            email='analyst@example.com',
            password='testpass123',
            role='ANALYST'
        )
        
        self.reviewer = User.objects.create_user(
            email='manager@example.com',
            password='testpass123',
            role='MANAGER'
        )
        
        self.group = Group.objects.create(
            name='Test Group',
            group_type='COMPANY'
        )
        
        self.user.groups.add(self.group)
        self.reviewer.groups.add(self.group)
        
        # Create partner with comprehensive information
        self.partner = DevelopmentPartner.objects.create(
            group=self.group,
            company_name='Premium Developments Ltd'
        )
        
        # Add general information
        GeneralInformation.objects.create(
            group=self.group,
            partner=self.partner,
            trading_name='Premium Dev',
            legal_structure='ltd',
            year_established=2010,
            headquarter_city='London',
            headquarter_country='GB'
        )
        
        # Add operational information
        OperationalInformation.objects.create(
            group=self.group,
            partner=self.partner,
            size_of_development_team=25,
            number_of_employees=150,
            completed_pbsa_schemes=15,
            years_of_pbsa_experience=8,
            total_pbsa_beds_delivered=3500,
            schemes_in_development=5,
            pbsa_schemes_in_development=4
        )
        
        # Add financial information
        FinancialInformation.objects.create(
            group=self.group,
            partner=self.partner,
            financial_year_end_date=date(2023, 12, 31),
            total_assets_amount=Decimal('50000000'),
            total_assets_currency='GBP',
            net_assets_amount=Decimal('25000000'),
            net_assets_currency='GBP',
            latest_annual_revenue_amount=Decimal('35000000'),
            latest_annual_revenue_currency='GBP',
            net_profit_before_tax_amount=Decimal('5250000'),
            net_profit_before_tax_currency='GBP',
            current_assets_amount=Decimal('15000000'),
            current_assets_currency='GBP',
            current_liabilities_amount=Decimal('8000000'),
            current_liabilities_currency='GBP'
        )
        
        # Add credit information
        CreditInformation.objects.create(
            group=self.group,
            partner=self.partner,
            main_banking_relationship='HSBC UK',
            total_debt_amount=Decimal('20000000'),
            total_debt_currency='GBP',
            short_term_debt_amount=Decimal('5000000'),
            short_term_debt_currency='GBP',
            interest_coverage_ratio=Decimal('4.5'),
            debt_service_coverage_ratio=Decimal('2.1')
        )
    
    def test_comprehensive_partner_assessment(self):
        """Test a complete partner assessment workflow."""
        # Create assessment
        assessment = Assessment.objects.create(
            group=self.group,
            assessment_type=AssessmentType.PARTNER,
            assessment_name='Premium Developments - Full Due Diligence',
            partner=self.partner,
            assessor=self.user,
            assessment_purpose='Partnership evaluation for new PBSA development program'
        )
        
        # Add comprehensive metrics
        metrics_data = [
            ('Financial Strength', MetricCategory.FINANCIAL, 5, 5, 'Excellent financial position with strong balance sheet'),
            ('Liquidity Position', MetricCategory.FINANCIAL, 4, 4, 'Good current ratio and cash flow management'),
            ('Development Team Size', MetricCategory.OPERATIONAL, 4, 4, 'Adequate team size for current pipeline'),
            ('PBSA Experience', MetricCategory.TRACK_RECORD, 5, 5, 'Extensive PBSA experience with 15 completed schemes'),
            ('Delivery Track Record', MetricCategory.TRACK_RECORD, 4, 4, 'Consistent delivery history'),
            ('Market Position', MetricCategory.MARKET, 4, 3, 'Strong regional presence'),
            ('Credit Risk', MetricCategory.RISK, 4, 4, 'Low credit risk with good coverage ratios'),
            ('Operational Risk', MetricCategory.RISK, 4, 3, 'Well-managed operational processes'),
        ]
        
        for metric_name, category, score, weight, justification in metrics_data:
            AssessmentMetric.objects.create(
                group=self.group,
                assessment=assessment,
                metric_name=metric_name,
                category=category,
                score=score,
                weight=weight,
                justification=justification
            )
        
        # Calculate scores and refresh fields
        assessment.refresh_calculated_fields()
        
        # Verify calculations
        # Expected total: (5*5)+(4*4)+(4*4)+(5*5)+(4*4)+(4*3)+(4*4)+(4*3) = 25+16+16+25+16+12+16+12 = 138
        self.assertEqual(assessment.total_weighted_score, 138)
        
        # Expected max: (5*5)+(5*4)+(5*4)+(5*5)+(5*4)+(5*3)+(5*4)+(5*3) = 25+20+20+25+20+15+20+15 = 160
        self.assertEqual(assessment.max_possible_score, 160)
        
        # Expected percentage: 138/160 * 100 = 86.25%
        self.assertEqual(assessment.score_percentage, 86.25)
        
        # Should be ACCEPTABLE band (125-165)
        self.assertEqual(assessment.decision_band, DecisionBand.ACCEPTABLE)
        
        # Test strongest/weakest categories
        strongest = assessment.get_strongest_categories(3)
        weakest = assessment.get_weakest_categories(3)
        
        # FINANCIAL and TRACK_RECORD should be strongest (both 100% for some metrics)
        strongest_categories = [cat['category'] for cat in strongest]
        self.assertIn(MetricCategory.FINANCIAL, strongest_categories)
        self.assertIn(MetricCategory.TRACK_RECORD, strongest_categories)
        
        # Test workflow
        assessment.submit_for_review(self.user)
        self.assertEqual(assessment.status, AssessmentStatus.IN_REVIEW)
        
        assessment.approve(self.reviewer)
        self.assertEqual(assessment.status, AssessmentStatus.APPROVED)
        self.assertEqual(assessment.approver, self.reviewer)
        
        # Test automated recommendations
        recommendations = assessment.generate_automated_recommendations()
        self.assertGreater(len(recommendations), 0)
        
        # Should include positive recommendation for good performance
        positive_found = any('Excellent candidate' in rec or 'Strong performance' in rec for rec in recommendations)
        self.assertTrue(positive_found)
    
    def test_low_scoring_assessment_workflow(self):
        """Test assessment with low scores requiring rejection."""
        assessment = Assessment.objects.create(
            group=self.group,
            assessment_type=AssessmentType.PARTNER,
            assessment_name='Weak Partner Assessment',
            partner=self.partner,
            assessor=self.user
        )
        
        # Add poor-performing metrics
        poor_metrics = [
            ('Financial Health', MetricCategory.FINANCIAL, 2, 5, 'Concerning financial position'),
            ('Team Capability', MetricCategory.OPERATIONAL, 1, 4, 'Insufficient team for scale'),
            ('Track Record', MetricCategory.TRACK_RECORD, 2, 5, 'Limited experience'),
            ('Risk Profile', MetricCategory.RISK, 1, 4, 'High risk across multiple areas'),
        ]
        
        for metric_name, category, score, weight, justification in poor_metrics:
            AssessmentMetric.objects.create(
                group=self.group,
                assessment=assessment,
                metric_name=metric_name,
                category=category,
                score=score,
                weight=weight,
                justification=justification
            )
        
        assessment.refresh_calculated_fields()
        
        # Expected total: (2*5)+(1*4)+(2*5)+(1*4) = 10+4+10+4 = 28
        # Should result in REJECT decision band (<125)
        self.assertEqual(assessment.decision_band, DecisionBand.REJECT)
        
        # Test rejection workflow
        assessment.submit_for_review(self.user)
        assessment.reject(self.reviewer, "Insufficient capability for partnership")
        
        self.assertEqual(assessment.status, AssessmentStatus.REJECTED)
        self.assertIn("REJECTION REASON", assessment.recommendations)