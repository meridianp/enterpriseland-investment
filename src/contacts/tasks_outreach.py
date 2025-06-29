"""
Celery tasks for outreach sequence execution.

This module handles the asynchronous execution of outreach sequences including:
- Step scheduling and execution
- Email sending through templates
- Condition evaluation
- Exit criteria checking
- Analytics tracking
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

from .models_outreach import (
    OutreachSequence,
    SequenceStep,
    SequenceEnrollment,
    SequenceStepExecution
)
from .models import EmailMessage, EmailTemplate
from integrations.services.email import email_service
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def execute_sequence_step(self, execution_id: str):
    """
    Execute a single sequence step.
    
    This task handles the execution of any step type including:
    - Sending emails
    - Checking conditions
    - Waiting periods
    - Performing actions
    """
    try:
        with transaction.atomic():
            execution = SequenceStepExecution.objects.select_for_update().get(
                id=execution_id
            )
            
            # Skip if already executed
            if execution.status in [
                SequenceStepExecution.Status.COMPLETED,
                SequenceStepExecution.Status.FAILED,
                SequenceStepExecution.Status.SKIPPED
            ]:
                logger.info(
                    f"Step execution {execution_id} already processed with status: {execution.status}"
                )
                return
            
            # Update status to executing
            execution.status = SequenceStepExecution.Status.EXECUTING
            execution.save()
        
        # Get related objects
        enrollment = execution.enrollment
        step = execution.step
        contact = enrollment.contact
        
        # Check exit conditions before executing
        if should_exit_sequence(enrollment):
            logger.info(
                f"Exit conditions met for enrollment {enrollment.id}, skipping step"
            )
            execution.status = SequenceStepExecution.Status.SKIPPED
            execution.result = {"reason": "Exit conditions met"}
            execution.save()
            
            # Exit the enrollment
            enrollment.exit(
                reason=SequenceEnrollment.ExitReason.CONDITION_MET,
                details="Exit conditions met during step execution"
            )
            enrollment.save()
            return
        
        # Execute based on step type
        result = None
        if step.step_type == SequenceStep.StepType.EMAIL:
            result = execute_email_step(execution, enrollment, step, contact)
        elif step.step_type == SequenceStep.StepType.WAIT:
            result = execute_wait_step(execution, enrollment, step)
        elif step.step_type == SequenceStep.StepType.CONDITION:
            result = execute_condition_step(execution, enrollment, step, contact)
        elif step.step_type == SequenceStep.StepType.ACTION:
            result = execute_action_step(execution, enrollment, step, contact)
        elif step.step_type == SequenceStep.StepType.AB_TEST:
            result = execute_ab_test_step(execution, enrollment, step, contact)
        else:
            raise ValueError(f"Unknown step type: {step.step_type}")
        
        # Update execution with result
        execution.status = SequenceStepExecution.Status.COMPLETED
        execution.executed_at = timezone.now()
        execution.result = result
        execution.save()
        
        # Update step analytics
        if step.step_type == SequenceStep.StepType.EMAIL and result.get("sent"):
            step.total_sent += 1
            step.save()
        
        # Schedule next step
        schedule_next_step(enrollment)
        
    except ObjectDoesNotExist:
        logger.error(f"Step execution {execution_id} not found")
    except Exception as e:
        logger.error(
            f"Error executing step {execution_id}: {str(e)}",
            exc_info=True
        )
        
        # Update execution as failed
        try:
            execution = SequenceStepExecution.objects.get(id=execution_id)
            execution.status = SequenceStepExecution.Status.FAILED
            execution.error_message = str(e)
            execution.save()
        except:
            pass
        
        # Retry if applicable
        if self.request.retries < self.max_retries:
            self.retry(countdown=60 * (self.request.retries + 1))


def execute_email_step(
    execution: SequenceStepExecution,
    enrollment: SequenceEnrollment,
    step: SequenceStep,
    contact
) -> Dict[str, Any]:
    """Execute an email step by sending the template."""
    try:
        # Get email template
        template = step.email_template
        if not template:
            raise ValueError(f"No email template configured for step {step.id}")
        
        # Build template data
        template_data = build_template_data(enrollment, contact)
        
        # Override subject if specified
        subject = step.email_subject or None
        if subject:
            # Replace variables in subject
            subject = replace_variables(subject, template_data)
        
        # Create email message record
        email_message = EmailMessage.objects.create(
            group=contact.group,
            from_email=template.from_email or "noreply@enterpriseland.com",
            to_email=contact.email,
            subject=subject or template.subject,
            template=template,
            template_data=template_data,
            contact=contact,
            metadata={
                "sequence_id": str(enrollment.sequence.id),
                "enrollment_id": str(enrollment.id),
                "step_id": str(step.id),
                "execution_id": str(execution.id)
            }
        )
        
        # Send email through service
        result = async_to_sync(email_service.send_email)(
            to=contact.email,
            subject=email_message.subject,
            template_id=template.slug,
            template_data=template_data,
            metadata={
                "email_message_id": str(email_message.id),
                "sequence_id": str(enrollment.sequence.id),
                "enrollment_id": str(enrollment.id)
            },
            tags=["sequence", "outreach", enrollment.sequence.name]
        )
        
        # Update email message with result
        if result.success:
            email_message.status = EmailMessage.Status.SENT
            email_message.sent_at = result.timestamp
            email_message.provider_message_id = result.message_id
            email_message.provider_used = result.provider
        else:
            email_message.status = EmailMessage.Status.FAILED
            email_message.error_message = result.error_message
        
        email_message.save()
        
        # Update execution with email message ID
        execution.email_message_id = email_message.id
        
        return {
            "sent": result.success,
            "email_message_id": str(email_message.id),
            "provider": result.provider if result.success else None,
            "error": result.error_message if not result.success else None
        }
        
    except Exception as e:
        logger.error(
            f"Error sending email for step {step.id}: {str(e)}",
            exc_info=True
        )
        return {
            "sent": False,
            "error": str(e)
        }


def execute_wait_step(
    execution: SequenceStepExecution,
    enrollment: SequenceEnrollment,
    step: SequenceStep
) -> Dict[str, Any]:
    """Execute a wait step (essentially a no-op)."""
    return {
        "waited": True,
        "delay_days": step.delay_days,
        "delay_hours": step.delay_hours
    }


def execute_condition_step(
    execution: SequenceStepExecution,
    enrollment: SequenceEnrollment,
    step: SequenceStep,
    contact
) -> Dict[str, Any]:
    """Execute a condition check step."""
    try:
        condition_type = step.condition_type
        condition_config = step.condition_config or {}
        
        # Evaluate different condition types
        result = False
        if condition_type == "has_tag":
            tag = condition_config.get("tag")
            result = tag in contact.tags if tag else False
            
        elif condition_type == "score_above":
            threshold = condition_config.get("threshold", 0)
            result = contact.lead_score >= threshold
            
        elif condition_type == "has_opened":
            # Check if contact opened previous emails
            from .models import EmailEvent
            result = EmailEvent.objects.filter(
                message__contact=contact,
                event_type=EmailEvent.EventType.OPENED
            ).exists()
            
        elif condition_type == "has_clicked":
            # Check if contact clicked in previous emails
            from .models import EmailEvent
            result = EmailEvent.objects.filter(
                message__contact=contact,
                event_type=EmailEvent.EventType.CLICKED
            ).exists()
            
        elif condition_type == "custom":
            # Custom condition evaluation
            # This would integrate with your custom logic
            result = False
        
        return {
            "condition_type": condition_type,
            "condition_met": result,
            "config": condition_config
        }
        
    except Exception as e:
        logger.error(
            f"Error evaluating condition for step {step.id}: {str(e)}",
            exc_info=True
        )
        return {
            "condition_type": step.condition_type,
            "condition_met": False,
            "error": str(e)
        }


def execute_action_step(
    execution: SequenceStepExecution,
    enrollment: SequenceEnrollment,
    step: SequenceStep,
    contact
) -> Dict[str, Any]:
    """Execute an action step."""
    try:
        action_type = step.action_type
        action_config = step.action_config or {}
        
        # Execute different action types
        if action_type == "add_tag":
            tag = action_config.get("tag")
            if tag and tag not in contact.tags:
                contact.tags.append(tag)
                contact.save()
                
        elif action_type == "update_score":
            delta = action_config.get("delta", 0)
            contact.lead_score += delta
            contact.save()
            
        elif action_type == "assign_to":
            user_id = action_config.get("user_id")
            if user_id:
                from accounts.models import User
                try:
                    user = User.objects.get(id=user_id)
                    contact.assigned_to = user
                    contact.save()
                except User.DoesNotExist:
                    pass
                    
        elif action_type == "create_task":
            # Create a task/activity
            from .models import ContactActivity
            ContactActivity.objects.create(
                contact=contact,
                activity_type=ContactActivity.ActivityType.TASK,
                subject=action_config.get("subject", "Follow-up task"),
                notes=action_config.get("notes", ""),
                due_date=timezone.now() + timedelta(
                    days=action_config.get("due_days", 1)
                ),
                assigned_to=contact.assigned_to
            )
            
        elif action_type == "webhook":
            # Call external webhook
            # This would integrate with your webhook system
            pass
        
        return {
            "action_type": action_type,
            "action_executed": True,
            "config": action_config
        }
        
    except Exception as e:
        logger.error(
            f"Error executing action for step {step.id}: {str(e)}",
            exc_info=True
        )
        return {
            "action_type": step.action_type,
            "action_executed": False,
            "error": str(e)
        }


def execute_ab_test_step(
    execution: SequenceStepExecution,
    enrollment: SequenceEnrollment,
    step: SequenceStep,
    contact
) -> Dict[str, Any]:
    """Execute an A/B test step."""
    # A/B test steps are containers - the actual variant steps handle execution
    return {
        "ab_test": True,
        "variant_group": step.variant_group
    }


def should_exit_sequence(enrollment: SequenceEnrollment) -> bool:
    """Check if enrollment should exit based on sequence exit conditions."""
    sequence = enrollment.sequence
    contact = enrollment.contact
    
    # Check unsubscribed
    if contact.email_preferences.get("unsubscribed", False):
        return True
    
    # Check exit tags
    if sequence.exit_tags:
        for tag in sequence.exit_tags:
            if tag in contact.tags:
                return True
    
    # Check reply (would need email tracking integration)
    if sequence.exit_on_reply:
        # Check if contact has replied to any sequence emails
        pass
    
    # Check click
    if sequence.exit_on_click:
        from .models import EmailEvent
        clicked = EmailEvent.objects.filter(
            message__metadata__enrollment_id=str(enrollment.id),
            event_type=EmailEvent.EventType.CLICKED
        ).exists()
        if clicked:
            return True
    
    # Check conversion
    if sequence.exit_on_conversion and enrollment.converted:
        return True
    
    return False


def build_template_data(
    enrollment: SequenceEnrollment,
    contact
) -> Dict[str, Any]:
    """Build template data for email personalization."""
    template_data = {
        # Contact data
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "email": contact.email,
        "company": contact.company,
        "title": contact.title,
        
        # Custom variables from enrollment
        **enrollment.custom_variables,
        
        # System data
        "sequence_name": enrollment.sequence.name,
        "unsubscribe_url": f"https://app.enterpriseland.com/unsubscribe/{contact.id}"
    }
    
    # Add partner data if contact is linked to partner
    if hasattr(contact, 'partner_relationships'):
        partner_rel = contact.partner_relationships.first()
        if partner_rel:
            template_data.update({
                "partner_name": partner_rel.partner.name,
                "partner_type": partner_rel.partner.partner_type
            })
    
    return template_data


def replace_variables(text: str, variables: Dict[str, Any]) -> str:
    """Replace {{variable}} placeholders in text."""
    import re
    
    def replacer(match):
        var_name = match.group(1).strip()
        return str(variables.get(var_name, match.group(0)))
    
    return re.sub(r'\{\{([^}]+)\}\}', replacer, text)


def schedule_next_step(enrollment: SequenceEnrollment):
    """Schedule the next step in the sequence."""
    try:
        # Get current sequence steps
        steps = enrollment.sequence.steps.order_by('order')
        
        # Find next step
        current_index = enrollment.current_step_index
        next_step = None
        
        for i, step in enumerate(steps):
            if i > current_index:
                next_step = step
                break
        
        if not next_step:
            # No more steps - complete enrollment
            enrollment.complete()
            enrollment.save()
            
            # Update sequence analytics
            sequence = enrollment.sequence
            sequence.total_completed += 1
            if enrollment.converted:
                sequence.total_converted += 1
            sequence.save()
            
            logger.info(f"Enrollment {enrollment.id} completed")
            return
        
        # Calculate next execution time
        next_execution_time = calculate_next_execution_time(
            enrollment,
            next_step
        )
        
        # Update enrollment
        enrollment.current_step = next_step
        enrollment.current_step_index += 1
        enrollment.next_step_at = next_execution_time
        enrollment.save()
        
        # Create step execution record
        execution = SequenceStepExecution.objects.create(
            enrollment=enrollment,
            step=next_step,
            scheduled_at=next_execution_time,
            status=SequenceStepExecution.Status.SCHEDULED
        )
        
        # Schedule execution task
        execute_sequence_step.apply_async(
            args=[str(execution.id)],
            eta=next_execution_time
        )
        
        logger.info(
            f"Scheduled next step {next_step.id} for enrollment {enrollment.id} "
            f"at {next_execution_time}"
        )
        
    except Exception as e:
        logger.error(
            f"Error scheduling next step for enrollment {enrollment.id}: {str(e)}",
            exc_info=True
        )


def calculate_next_execution_time(
    enrollment: SequenceEnrollment,
    step: SequenceStep
) -> datetime:
    """Calculate when to execute the next step."""
    sequence = enrollment.sequence
    
    # Start with current time
    next_time = timezone.now()
    
    # Add step delay
    if step.day_type == SequenceStep.DayType.BUSINESS:
        # Calculate business days
        days_added = 0
        while days_added < step.delay_days:
            next_time += timedelta(days=1)
            # Skip weekends if configured
            if sequence.skip_weekends and next_time.weekday() in [5, 6]:
                continue
            days_added += 1
    else:
        # Calendar days
        next_time += timedelta(days=step.delay_days)
    
    # Add hours
    next_time += timedelta(hours=step.delay_hours)
    
    # Optimize for timezone if configured
    if sequence.timezone_optimized:
        # Set to optimal hour in recipient timezone
        # This would require timezone detection for the contact
        next_time = next_time.replace(
            hour=sequence.optimal_send_hour,
            minute=0,
            second=0,
            microsecond=0
        )
        
        # If time has passed today, move to tomorrow
        if next_time <= timezone.now():
            next_time += timedelta(days=1)
            
            # Skip weekend if needed
            if sequence.skip_weekends and next_time.weekday() in [5, 6]:
                days_to_monday = 7 - next_time.weekday()
                next_time += timedelta(days=days_to_monday)
    
    return next_time


@shared_task
def start_sequence_enrollment(enrollment_id: str):
    """Start a sequence enrollment by scheduling the first step."""
    try:
        enrollment = SequenceEnrollment.objects.get(id=enrollment_id)
        
        # Update enrollment count
        sequence = enrollment.sequence
        sequence.total_enrolled += 1
        sequence.save()
        
        # Schedule first step
        schedule_next_step(enrollment)
        
    except ObjectDoesNotExist:
        logger.error(f"Enrollment {enrollment_id} not found")
    except Exception as e:
        logger.error(
            f"Error starting enrollment {enrollment_id}: {str(e)}",
            exc_info=True
        )


@shared_task
def process_sequence_triggers():
    """
    Process automatic sequence triggers.
    
    This task runs periodically to check for contacts that should be
    automatically enrolled in sequences based on trigger conditions.
    """
    try:
        # Get active sequences with automatic triggers
        sequences = OutreachSequence.objects.filter(
            status=OutreachSequence.Status.ACTIVE
        ).exclude(
            trigger_type=OutreachSequence.TriggerType.MANUAL
        )
        
        for sequence in sequences:
            process_sequence_trigger(sequence)
            
    except Exception as e:
        logger.error(
            f"Error processing sequence triggers: {str(e)}",
            exc_info=True
        )


def process_sequence_trigger(sequence: OutreachSequence):
    """Process triggers for a single sequence."""
    # Implementation would depend on trigger type and conditions
    # This is a placeholder for the trigger processing logic
    pass


@shared_task
def update_sequence_analytics():
    """
    Update sequence analytics from email events.
    
    This task runs periodically to update open/click rates for sequence steps.
    """
    try:
        from .models import EmailEvent
        
        # Get recent email events for sequence emails
        recent_events = EmailEvent.objects.filter(
            message__metadata__has_key='sequence_id',
            timestamp__gte=timezone.now() - timedelta(hours=24)
        ).select_related('message')
        
        # Group by step and update counts
        step_stats = {}
        for event in recent_events:
            step_id = event.message.metadata.get('step_id')
            if not step_id:
                continue
                
            if step_id not in step_stats:
                step_stats[step_id] = {
                    'opened': 0,
                    'clicked': 0
                }
            
            if event.event_type == EmailEvent.EventType.OPENED:
                step_stats[step_id]['opened'] += 1
            elif event.event_type == EmailEvent.EventType.CLICKED:
                step_stats[step_id]['clicked'] += 1
        
        # Update step statistics
        for step_id, stats in step_stats.items():
            try:
                step = SequenceStep.objects.get(id=step_id)
                step.total_opened += stats['opened']
                step.total_clicked += stats['clicked']
                step.save()
            except SequenceStep.DoesNotExist:
                pass
                
    except Exception as e:
        logger.error(
            f"Error updating sequence analytics: {str(e)}",
            exc_info=True
        )