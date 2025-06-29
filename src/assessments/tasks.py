
from celery import shared_task
from django.utils import timezone
from datetime import date, timedelta
import requests
from decimal import Decimal
import logging

from .models import FXRate, Currency

logger = logging.getLogger(__name__)

@shared_task
def update_fx_rates():
    """Update foreign exchange rates from external API"""
    try:
        # Yahoo Finance API (free tier)
        base_url = "https://query1.finance.yahoo.com/v8/finance/chart/"
        
        # Currency pairs to fetch
        currency_pairs = [
            ('USD', 'EUR'), ('USD', 'GBP'), ('USD', 'AED'), ('USD', 'SAR'),
            ('EUR', 'GBP'), ('EUR', 'AED'), ('EUR', 'SAR'),
            ('GBP', 'AED'), ('GBP', 'SAR'),
            ('AED', 'SAR')
        ]
        
        today = date.today()
        
        for base, target in currency_pairs:
            try:
                # Yahoo Finance format: USDEUR=X
                symbol = f"{base}{target}=X"
                url = f"{base_url}{symbol}"
                
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                result = data['chart']['result'][0]
                
                # Get the latest close price
                close_prices = result['indicators']['quote'][0]['close']
                latest_price = close_prices[-1]
                
                if latest_price:
                    rate = Decimal(str(latest_price))
                    
                    # Create or update FX rate
                    fx_rate, created = FXRate.objects.update_or_create(
                        base_currency=base,
                        target_currency=target,
                        date=today,
                        defaults={'rate': rate}
                    )
                    
                    # Also create the inverse rate
                    inverse_rate = Decimal('1') / rate
                    FXRate.objects.update_or_create(
                        base_currency=target,
                        target_currency=base,
                        date=today,
                        defaults={'rate': inverse_rate}
                    )
                    
                    logger.info(f"Updated FX rate {base}/{target}: {rate}")
                
            except Exception as e:
                logger.error(f"Failed to update FX rate {base}/{target}: {str(e)}")
                continue
        
        # Add same-currency rates (1.0)
        for currency in Currency.values:
            FXRate.objects.update_or_create(
                base_currency=currency,
                target_currency=currency,
                date=today,
                defaults={'rate': Decimal('1.0')}
            )
        
        logger.info("FX rates update completed")
        
    except Exception as e:
        logger.error(f"FX rates update failed: {str(e)}")
        raise

@shared_task
def cleanup_old_fx_rates():
    """Clean up FX rates older than 1 year"""
    cutoff_date = timezone.now().date() - timedelta(days=365)
    deleted_count = FXRate.objects.filter(date__lt=cutoff_date).delete()[0]
    logger.info(f"Cleaned up {deleted_count} old FX rates")
    return deleted_count

@shared_task
def calculate_assessment_scores():
    """Recalculate assessment scores for all assessments"""
    from .models import Assessment
    
    updated_count = 0
    
    for assessment in Assessment.objects.all():
        old_score = assessment.total_score
        new_score = sum(metric.weighted_score for metric in assessment.metrics.all())
        
        if old_score != new_score:
            assessment.total_score = new_score
            assessment.save()
            updated_count += 1
    
    logger.info(f"Updated scores for {updated_count} assessments")
    return updated_count

@shared_task
def generate_assessment_report(assessment_id, format='json'):
    """Generate assessment report in specified format"""
    from .models import Assessment
    from .serializers import AssessmentSerializer
    import json
    import csv
    from io import StringIO
    
    try:
        assessment = Assessment.objects.get(id=assessment_id)
        
        if format == 'json':
            serializer = AssessmentSerializer(assessment)
            return json.dumps(serializer.data, indent=2, default=str)
        
        elif format == 'csv':
            output = StringIO()
            writer = csv.writer(output)
            
            # Write headers
            writer.writerow([
                'Assessment ID', 'Type', 'Partner', 'Scheme', 'Status',
                'Decision', 'Total Score', 'Created At', 'Created By'
            ])
            
            # Write data
            writer.writerow([
                str(assessment.id),
                assessment.assessment_type,
                assessment.partner.company_name if assessment.partner else '',
                assessment.scheme.scheme_name if assessment.scheme else '',
                assessment.status,
                assessment.decision,
                assessment.total_score,
                assessment.created_at.isoformat(),
                assessment.created_by.email
            ])
            
            return output.getvalue()
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    except Assessment.DoesNotExist:
        logger.error(f"Assessment {assessment_id} not found")
        raise
    except Exception as e:
        logger.error(f"Failed to generate report for assessment {assessment_id}: {str(e)}")
        raise
