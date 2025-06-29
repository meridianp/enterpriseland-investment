"""
Tests for assessment Celery tasks.
"""
from django.test import TestCase
from unittest.mock import patch, Mock, MagicMock
from decimal import Decimal
from datetime import date, timedelta
import json
import requests
from django.utils import timezone

from tests.base import BaseTestCase
from tests.factories.assessment_factories import (
    AssessmentFactory, AssessmentMetricFactory, FXRateFactory
)
from assessments.tasks import (
    update_fx_rates, cleanup_old_fx_rates,
    calculate_assessment_scores, generate_assessment_report
)
from assessments.models import FXRate, Currency, Assessment


class UpdateFXRatesTaskTest(BaseTestCase):
    """Test update_fx_rates Celery task."""
    
    @patch('assessments.tasks.requests.get')
    def test_successful_fx_update(self, mock_get):
        """Test successful FX rates update from Yahoo Finance."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'chart': {
                'result': [{
                    'indicators': {
                        'quote': [{
                            'close': [1.2345, 1.2350, 1.2355]  # Sample close prices
                        }]
                    }
                }]
            }
        }
        mock_get.return_value = mock_response
        
        # Run the task
        update_fx_rates()
        
        # Verify API calls were made
        self.assertTrue(mock_get.called)
        
        # Verify FX rates were created
        self.assertTrue(FXRate.objects.filter(
            base_currency='USD',
            target_currency='EUR',
            date=date.today()
        ).exists())
        
        # Verify inverse rate was created
        usd_eur_rate = FXRate.objects.get(
            base_currency='USD',
            target_currency='EUR',
            date=date.today()
        )
        eur_usd_rate = FXRate.objects.get(
            base_currency='EUR',
            target_currency='USD',
            date=date.today()
        )
        
        # Check inverse relationship
        expected_inverse = Decimal('1') / usd_eur_rate.rate
        self.assertAlmostEqual(float(eur_usd_rate.rate), float(expected_inverse), places=4)
        
    @patch('assessments.tasks.requests.get')
    def test_api_failure_handling(self, mock_get):
        """Test handling of API failures."""
        # Mock API failure
        mock_get.side_effect = requests.RequestException("API unavailable")
        
        # Task should not crash
        try:
            update_fx_rates()
        except Exception as e:
            self.fail(f"Task should handle API failures gracefully, but raised: {e}")
            
    @patch('assessments.tasks.requests.get')
    def test_invalid_response_handling(self, mock_get):
        """Test handling of invalid API responses."""
        # Mock invalid response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'chart': {
                'result': [{
                    'indicators': {
                        'quote': [{
                            'close': [None, None, None]  # No valid prices
                        }]
                    }
                }]
            }
        }
        mock_get.return_value = mock_response
        
        # Task should handle gracefully
        update_fx_rates()
        
        # Should still create same-currency rates
        self.assertTrue(FXRate.objects.filter(
            base_currency='USD',
            target_currency='USD',
            rate=Decimal('1.0'),
            date=date.today()
        ).exists())
        
    @patch('assessments.tasks.requests.get')
    def test_same_currency_rates_creation(self, mock_get):
        """Test that same-currency rates (1.0) are created."""
        # Mock successful response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'chart': {
                'result': [{
                    'indicators': {
                        'quote': [{
                            'close': [1.0]
                        }]
                    }
                }]
            }
        }
        mock_get.return_value = mock_response
        
        update_fx_rates()
        
        # Check same-currency rates for all currencies
        for currency in Currency.values:
            self.assertTrue(FXRate.objects.filter(
                base_currency=currency,
                target_currency=currency,
                rate=Decimal('1.0'),
                date=date.today()
            ).exists())
            
    @patch('assessments.tasks.requests.get')
    def test_rate_update_not_duplicate(self, mock_get):
        """Test that running task twice updates existing rates."""
        # Create existing rate
        existing_rate = FXRateFactory(
            base_currency='USD',
            target_currency='EUR',
            rate=Decimal('1.1000'),
            date=date.today()
        )
        
        # Mock new rate
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'chart': {
                'result': [{
                    'indicators': {
                        'quote': [{
                            'close': [1.2500]  # New rate
                        }]
                    }
                }]
            }
        }
        mock_get.return_value = mock_response
        
        initial_count = FXRate.objects.count()
        
        update_fx_rates()
        
        # Should not create duplicate rates
        final_count = FXRate.objects.count()
        self.assertGreater(final_count, initial_count)  # New rates added, but no duplicates
        
        # Check rate was updated
        updated_rate = FXRate.objects.get(
            base_currency='USD',
            target_currency='EUR',
            date=date.today()
        )
        self.assertEqual(updated_rate.rate, Decimal('1.2500'))


class CleanupOldFXRatesTaskTest(BaseTestCase):
    """Test cleanup_old_fx_rates Celery task."""
    
    def test_cleanup_old_rates(self):
        """Test cleanup of old FX rates."""
        today = date.today()
        old_date = today - timedelta(days=400)  # Over 1 year old
        recent_date = today - timedelta(days=30)  # Recent
        
        # Create old and recent rates
        old_rate = FXRateFactory(date=old_date)
        recent_rate = FXRateFactory(date=recent_date)
        current_rate = FXRateFactory(date=today)
        
        # Run cleanup
        deleted_count = cleanup_old_fx_rates()
        
        # Verify old rate was deleted
        self.assertFalse(FXRate.objects.filter(id=old_rate.id).exists())
        
        # Verify recent rates still exist
        self.assertTrue(FXRate.objects.filter(id=recent_rate.id).exists())
        self.assertTrue(FXRate.objects.filter(id=current_rate.id).exists())
        
        # Verify return value
        self.assertEqual(deleted_count, 1)
        
    def test_cleanup_no_old_rates(self):
        """Test cleanup when no old rates exist."""
        # Create only recent rates
        FXRateFactory(date=date.today())
        FXRateFactory(date=date.today() - timedelta(days=30))
        
        deleted_count = cleanup_old_fx_rates()
        
        self.assertEqual(deleted_count, 0)


class CalculateAssessmentScoresTaskTest(BaseTestCase):
    """Test calculate_assessment_scores Celery task."""
    
    def test_score_calculation_update(self):
        """Test assessment scores are recalculated correctly."""
        # Create assessment with metrics
        assessment = AssessmentFactory(total_score=0)  # Incorrect initial score
        
        # Add metrics
        AssessmentMetricFactory(assessment=assessment, score=4, weight=5)  # 20 points
        AssessmentMetricFactory(assessment=assessment, score=3, weight=4)  # 12 points
        AssessmentMetricFactory(assessment=assessment, score=5, weight=3)  # 15 points
        # Expected total: 47 points
        
        # Run calculation task
        updated_count = calculate_assessment_scores()
        
        # Verify score was updated
        assessment.refresh_from_db()
        self.assertEqual(assessment.total_score, 47)
        self.assertEqual(updated_count, 1)
        
    def test_no_update_needed(self):
        """Test when scores are already correct."""
        # Create assessment with correct score
        assessment = AssessmentFactory(total_score=30)
        
        # Add metrics that total to 30
        AssessmentMetricFactory(assessment=assessment, score=5, weight=5)  # 25 points
        AssessmentMetricFactory(assessment=assessment, score=1, weight=5)  # 5 points
        
        updated_count = calculate_assessment_scores()
        
        # No updates needed
        self.assertEqual(updated_count, 0)
        
    def test_multiple_assessments(self):
        """Test calculation across multiple assessments."""
        # Create multiple assessments with wrong scores
        assessment1 = AssessmentFactory(total_score=0)
        assessment2 = AssessmentFactory(total_score=100)  # Way off
        assessment3 = AssessmentFactory(total_score=15)   # Correct
        
        # Add metrics
        AssessmentMetricFactory(assessment=assessment1, score=2, weight=3)  # 6 points
        AssessmentMetricFactory(assessment=assessment2, score=4, weight=4)  # 16 points
        AssessmentMetricFactory(assessment=assessment3, score=3, weight=5)  # 15 points (correct)
        
        updated_count = calculate_assessment_scores()
        
        # Check updates
        assessment1.refresh_from_db()
        assessment2.refresh_from_db()
        assessment3.refresh_from_db()
        
        self.assertEqual(assessment1.total_score, 6)
        self.assertEqual(assessment2.total_score, 16)
        self.assertEqual(assessment3.total_score, 15)  # Unchanged
        
        self.assertEqual(updated_count, 2)  # Only 2 were updated
        
    def test_assessment_without_metrics(self):
        """Test assessment without metrics."""
        assessment = AssessmentFactory(total_score=50)  # Wrong, should be 0
        
        updated_count = calculate_assessment_scores()
        
        assessment.refresh_from_db()
        self.assertEqual(assessment.total_score, 0)
        self.assertEqual(updated_count, 1)


class GenerateAssessmentReportTaskTest(BaseTestCase):
    """Test generate_assessment_report Celery task."""
    
    def test_json_report_generation(self):
        """Test JSON report generation."""
        assessment = AssessmentFactory()
        
        # Generate JSON report
        result = generate_assessment_report(assessment.id, format='json')
        
        # Verify it's valid JSON
        report_data = json.loads(result)
        
        self.assertIn('id', report_data)
        self.assertIn('assessment_type', report_data)
        self.assertIn('status', report_data)
        self.assertEqual(str(report_data['id']), str(assessment.id))
        
    def test_csv_report_generation(self):
        """Test CSV report generation."""
        partner = self.create_test_partner()
        assessment = AssessmentFactory(
            partner=partner,
            created_by=self.analyst_user
        )
        
        # Generate CSV report
        result = generate_assessment_report(assessment.id, format='csv')
        
        # Verify CSV format
        lines = result.strip().split('\n')
        self.assertGreater(len(lines), 1)  # Header + data
        
        # Check header
        headers = lines[0].split(',')
        expected_headers = [
            'Assessment ID', 'Type', 'Partner', 'Scheme', 'Status',
            'Decision', 'Total Score', 'Created At', 'Created By'
        ]
        self.assertEqual(headers, expected_headers)
        
        # Check data row
        data = lines[1].split(',')
        self.assertEqual(data[0], str(assessment.id))
        self.assertEqual(data[4], assessment.status)
        
    def test_invalid_format(self):
        """Test handling of invalid format."""
        assessment = AssessmentFactory()
        
        with self.assertRaises(ValueError) as context:
            generate_assessment_report(assessment.id, format='pdf')
            
        self.assertIn('Unsupported format', str(context.exception))
        
    def test_nonexistent_assessment(self):
        """Test handling of nonexistent assessment."""
        fake_id = '00000000-0000-0000-0000-000000000000'
        
        with self.assertRaises(Assessment.DoesNotExist):
            generate_assessment_report(fake_id, format='json')
            
    @patch('assessments.tasks.logger')
    def test_logging(self, mock_logger):
        """Test that errors are properly logged."""
        fake_id = '00000000-0000-0000-0000-000000000000'
        
        try:
            generate_assessment_report(fake_id, format='json')
        except Assessment.DoesNotExist:
            pass
            
        # Verify error was logged
        mock_logger.error.assert_called()
        
    def test_csv_with_scheme_assessment(self):
        """Test CSV generation for scheme-based assessment."""
        # This would require creating a PBSAScheme first
        # For now, just test with partner assessment
        assessment = AssessmentFactory(scheme=None)  # Partner assessment
        
        result = generate_assessment_report(assessment.id, format='csv')
        
        lines = result.strip().split('\n')
        data = lines[1].split(',')
        
        # Partner name should be included, scheme should be empty
        partner_name = data[2] if assessment.partner else ''
        scheme_name = data[3]  # Should be empty
        
        if assessment.partner:
            self.assertTrue(len(partner_name) > 0)
        self.assertEqual(scheme_name, '')
        
    def create_test_partner(self):
        """Helper method to create a test partner."""
        from tests.factories.assessment_factories import DevelopmentPartnerFactory
        return DevelopmentPartnerFactory(group=self.group)


class TaskErrorHandlingTest(BaseTestCase):
    """Test error handling across all tasks."""
    
    @patch('assessments.tasks.logger')
    def test_fx_rates_task_error_logging(self, mock_logger):
        """Test that FX rates task logs errors properly."""
        with patch('assessments.tasks.requests.get') as mock_get:
            mock_get.side_effect = Exception("Network error")
            
            with self.assertRaises(Exception):
                update_fx_rates()
                
            mock_logger.error.assert_called()
            
    @patch('assessments.tasks.logger')
    def test_calculation_task_logging(self, mock_logger):
        """Test that score calculation task logs results."""
        AssessmentFactory(total_score=0)
        
        calculate_assessment_scores()
        
        mock_logger.info.assert_called()
        
    @patch('assessments.tasks.logger')
    def test_cleanup_task_logging(self, mock_logger):
        """Test that cleanup task logs results."""
        cleanup_old_fx_rates()
        
        mock_logger.info.assert_called()