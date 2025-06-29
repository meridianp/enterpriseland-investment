
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
import json
import os

from .models import Assessment, AssessmentAuditLog_Legacy
from notifications.tasks import create_notification, send_webhook_event

@receiver(post_save, sender=Assessment)
def assessment_post_save(sender, instance, created, **kwargs):
    """Handle assessment creation and updates"""
    # Skip if signals are disabled
    if os.environ.get('DISABLE_SIGNALS'):
        return
        
    if created:
        # Create notification for assessment creation
        create_notification.delay(
            recipient_id=str(instance.created_by.id),
            notification_type='assessment_created',
            title=f'Assessment Created: {instance}',
            message=f'New assessment has been created for {instance}',
            assessment_id=str(instance.id)
        )
        
        # Send webhook event
        send_webhook_event.delay('assessment.created', {
            'assessment_id': str(instance.id),
            'assessment_type': instance.assessment_type,
            'status': instance.status,
            'created_by': instance.created_by.email,
            'created_at': instance.created_at.isoformat()
        })
    
    else:
        # Handle status changes
        if hasattr(instance, '_previous_status') and instance._previous_status != instance.status:
            if instance.status == Assessment.AssessmentStatus.APPROVED:
                create_notification.delay(
                    recipient_id=str(instance.created_by.id),
                    notification_type='assessment_approved',
                    title=f'Assessment Approved: {instance}',
                    message=f'Your assessment has been approved with decision: {instance.decision}',
                    assessment_id=str(instance.id),
                    sender_id=str(instance.approved_by.id) if instance.approved_by else None
                )
                
                send_webhook_event.delay('assessment.approved', {
                    'assessment_id': str(instance.id),
                    'decision': instance.decision,
                    'approved_by': instance.approved_by.email if instance.approved_by else None,
                    'approved_at': instance.approved_at.isoformat() if instance.approved_at else None
                })
            
            elif instance.status == Assessment.AssessmentStatus.REJECTED:
                create_notification.delay(
                    recipient_id=str(instance.created_by.id),
                    notification_type='assessment_rejected',
                    title=f'Assessment Rejected: {instance}',
                    message=f'Your assessment has been rejected',
                    assessment_id=str(instance.id),
                    sender_id=str(instance.approved_by.id) if instance.approved_by else None
                )
                
                send_webhook_event.delay('assessment.rejected', {
                    'assessment_id': str(instance.id),
                    'approved_by': instance.approved_by.email if instance.approved_by else None,
                    'approved_at': instance.approved_at.isoformat() if instance.approved_at else None
                })

@receiver(pre_save, sender=Assessment)
def assessment_pre_save(sender, instance, **kwargs):
    """Store previous status for comparison"""
    if instance.pk:
        try:
            previous = Assessment.objects.get(pk=instance.pk)
            instance._previous_status = previous.status
        except Assessment.DoesNotExist:
            instance._previous_status = None

def create_audit_log(sender, instance, action, old_values=None, new_values=None, user=None):
    """Create audit log entry"""
    try:
        # Get user from thread local storage or other means
        if not user and hasattr(instance, '_audit_user'):
            user = instance._audit_user
        
        if user:
            AssessmentAuditLog_Legacy.objects.create(
                user=user,
                table_name=sender._meta.db_table,
                record_id=instance.pk,
                action=action,
                old_values=old_values,
                new_values=new_values,
                timestamp=timezone.now()
            )
    except Exception as e:
        # Don't let audit logging break the main operation
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to create audit log: {str(e)}")

@receiver(post_save)
def generic_post_save_audit(sender, instance, created, **kwargs):
    """Generic audit logging for all model saves"""
    # Only audit specific models
    audited_models = ['Assessment', 'DevelopmentPartner', 'PBSAScheme', 'FinancialInformation', 'CreditInformation']
    
    if sender.__name__ in audited_models:
        action = 'CREATE' if created else 'UPDATE'
        
        # Serialize instance data
        try:
            from django.core import serializers
            serialized = serializers.serialize('json', [instance])
            new_values = json.loads(serialized)[0]['fields']
        except:
            new_values = {'id': str(instance.pk)}
        
        create_audit_log(sender, instance, action, new_values=new_values)

@receiver(post_delete)
def generic_post_delete_audit(sender, instance, **kwargs):
    """Generic audit logging for all model deletions"""
    # Only audit specific models
    audited_models = ['Assessment', 'DevelopmentPartner', 'PBSAScheme', 'FinancialInformation', 'CreditInformation']
    
    if sender.__name__ in audited_models:
        try:
            from django.core import serializers
            serialized = serializers.serialize('json', [instance])
            old_values = json.loads(serialized)[0]['fields']
        except:
            old_values = {'id': str(instance.pk)}
        
        create_audit_log(sender, instance, 'DELETE', old_values=old_values)
