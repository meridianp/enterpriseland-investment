"""
Celery tasks for email campaign processing.

Handles async email sending, tracking, and analytics for the
EnterpriseLand Due-Diligence Platform.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from celery import shared_task, group, chord
from celery.exceptions import MaxRetriesExceededError
from django.utils import timezone
from django.template import Template, Context
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.db import transaction
from django.db.models import F

from .models import (
    EmailTemplate, EmailCampaign, EmailMessage, EmailEvent,
    Contact, ContactActivity, ActivityType
)
from django.db.models import Q
from .email_utils import (
    render_email_template, validate_email_address,
    generate_unsubscribe_url, generate_tracking_pixel,
    track_email_links, get_email_backend
)
from notifications.models import Notification
from accounts.models import User

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def send_campaign_emails(self, campaign_id: str) -> Dict[str, Any]:
    """
    Main task to send emails for a campaign.
    
    Processes recipients in batches according to send rate limits.
    """
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        
        # Check campaign status
        if campaign.status not in [
            EmailCampaign.CampaignStatus.SENDING,
            EmailCampaign.CampaignStatus.SCHEDULED
        ]:
            logger.warning(f"Campaign {campaign_id} not in sendable status: {campaign.status}")
            return {'status': 'skipped', 'reason': 'Invalid campaign status'}
        
        # Update status to sending
        if campaign.status == EmailCampaign.CampaignStatus.SCHEDULED:
            campaign.status = EmailCampaign.CampaignStatus.SENDING
            campaign.started_at = timezone.now()
            campaign.save()
        
        # Get recipients
        recipients = _get_campaign_recipients(campaign)
        total_recipients = len(recipients)
        
        if total_recipients == 0:
            campaign.status = EmailCampaign.CampaignStatus.SENT
            campaign.completed_at = timezone.now()
            campaign.save()
            return {'status': 'completed', 'sent': 0}
        
        # Calculate batch size based on send rate
        batch_size = max(1, campaign.send_rate_per_hour // 60)  # Per minute
        
        # Process recipients in batches
        sent_count = 0
        failed_count = 0
        
        for i in range(0, total_recipients, batch_size):
            # Check if campaign was paused or cancelled
            campaign.refresh_from_db()
            if campaign.status == EmailCampaign.CampaignStatus.PAUSED:
                return {'status': 'paused', 'sent': sent_count}
            elif campaign.status == EmailCampaign.CampaignStatus.CANCELLED:
                return {'status': 'cancelled', 'sent': sent_count}
            
            batch = recipients[i:i + batch_size]
            
            # Send emails in parallel using chord
            email_tasks = []
            for contact in batch:
                # Create or get message record
                message, created = EmailMessage.objects.get_or_create(
                    campaign=campaign,
                    contact=contact,
                    defaults={
                        'group': campaign.group,
                        'template_used': campaign.template,
                        'subject': campaign.template.subject,
                        'from_email': campaign.template.from_email,
                        'to_email': contact.email,
                        'status': EmailMessage.MessageStatus.PENDING
                    }
                )
                
                if created or message.status in [
                    EmailMessage.MessageStatus.PENDING,
                    EmailMessage.MessageStatus.FAILED
                ]:
                    email_tasks.append(send_single_email.s(str(message.id)))
            
            if email_tasks:
                # Execute batch in parallel
                job = group(email_tasks)
                results = job.apply_async().get()
                
                # Count results
                for result in results:
                    if result['status'] == 'sent':
                        sent_count += 1
                    else:
                        failed_count += 1
                
                # Update campaign stats
                campaign.emails_sent = F('emails_sent') + len(results)
                campaign.save()
            
            # Rate limiting pause
            if i + batch_size < total_recipients:
                import time
                time.sleep(60 / (campaign.send_rate_per_hour / batch_size))
        
        # Mark campaign as completed
        campaign.refresh_from_db()
        campaign.status = EmailCampaign.CampaignStatus.SENT
        campaign.completed_at = timezone.now()
        campaign.save()
        
        # Send completion notification
        _send_campaign_completion_notification(campaign, sent_count, failed_count)
        
        return {
            'status': 'completed',
            'sent': sent_count,
            'failed': failed_count,
            'total': total_recipients
        }
        
    except EmailCampaign.DoesNotExist:
        logger.error(f"Campaign {campaign_id} not found")
        return {'status': 'error', 'error': 'Campaign not found'}
    except Exception as e:
        logger.error(f"Error sending campaign {campaign_id}: {str(e)}")
        self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_single_email(self, message_id: str) -> Dict[str, str]:
    """
    Send a single email message.
    
    Handles rendering, personalization, and tracking setup.
    """
    try:
        message = EmailMessage.objects.select_related(
            'campaign', 'contact', 'template_used'
        ).get(id=message_id)
        
        # Skip if already sent
        if message.status in [
            EmailMessage.MessageStatus.SENT,
            EmailMessage.MessageStatus.DELIVERED,
            EmailMessage.MessageStatus.BOUNCED
        ]:
            return {'status': 'skipped', 'reason': 'Already sent'}
        
        # Validate email address
        if not validate_email_address(message.to_email):
            message.status = EmailMessage.MessageStatus.FAILED
            message.failed_reason = "Invalid email address"
            message.save()
            return {'status': 'failed', 'reason': 'Invalid email'}
        
        # Check contact opt-in status
        if not message.contact.email_opt_in:
            message.status = EmailMessage.MessageStatus.FAILED
            message.failed_reason = "Contact opted out"
            message.save()
            return {'status': 'failed', 'reason': 'Opted out'}
        
        # Prepare template context
        context_data = _prepare_email_context(message)
        
        # Render email content
        try:
            subject = render_email_template(
                message.template_used.subject,
                context_data
            )
            html_content = render_email_template(
                message.template_used.html_content,
                context_data
            )
            text_content = render_email_template(
                message.template_used.text_content,
                context_data
            )
        except Exception as e:
            logger.error(f"Template rendering error for message {message_id}: {str(e)}")
            message.status = EmailMessage.MessageStatus.FAILED
            message.failed_reason = f"Template error: {str(e)}"
            message.save()
            return {'status': 'failed', 'reason': 'Template error'}
        
        # Add tracking
        if message.campaign.track_opens:
            html_content = _add_tracking_pixel(html_content, message)
        
        if message.campaign.track_clicks:
            html_content = track_email_links(html_content, message)
            text_content = track_email_links(text_content, message, is_html=False)
        
        # Create email message
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=f"{message.template_used.from_name} <{message.template_used.from_email}>",
            to=[message.to_email],
            reply_to=[message.template_used.reply_to_email] if message.template_used.reply_to_email else None
        )
        email.attach_alternative(html_content, "text/html")
        
        # Add headers for tracking
        email.extra_headers['X-Campaign-ID'] = str(message.campaign.id)
        email.extra_headers['X-Message-ID'] = str(message.id)
        
        # Send email
        try:
            backend = get_email_backend()
            backend.send_messages([email])
            
            # Update message status
            message.status = EmailMessage.MessageStatus.SENT
            message.sent_at = timezone.now()
            message.queued_at = timezone.now()
            message.subject = subject  # Store rendered subject
            message.save()
            
            # Update campaign stats
            message.campaign.emails_sent = F('emails_sent') + 1
            message.campaign.save()
            
            # Create activity record
            ContactActivity.objects.create(
                group=message.campaign.group,
                contact=message.contact,
                activity_type=ActivityType.EMAIL_SENT,
                subject=f"Campaign: {message.campaign.name}",
                description=f"Email sent with subject: {subject}",
                metadata={
                    'campaign_id': str(message.campaign.id),
                    'message_id': str(message.id)
                }
            )
            
            # Update contact's last email sent timestamp
            message.contact.last_email_sent_at = timezone.now()
            message.contact.save(update_fields=['last_email_sent_at'])
            
            # Log event
            EmailEvent.objects.create(
                message=message,
                event_type=EmailEvent.EventType.SENT,
                timestamp=timezone.now()
            )
            
            return {'status': 'sent', 'message_id': str(message.id)}
            
        except Exception as e:
            logger.error(f"Error sending email {message_id}: {str(e)}")
            message.status = EmailMessage.MessageStatus.FAILED
            message.failed_reason = str(e)
            message.save()
            
            # Log failed event
            EmailEvent.objects.create(
                message=message,
                event_type=EmailEvent.EventType.FAILED,
                timestamp=timezone.now(),
                metadata={'error': str(e)}
            )
            
            raise
            
    except EmailMessage.DoesNotExist:
        logger.error(f"Message {message_id} not found")
        return {'status': 'error', 'error': 'Message not found'}
    except Exception as e:
        logger.error(f"Unexpected error sending email {message_id}: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {'status': 'failed', 'reason': str(e)}


@shared_task
def send_test_email(
    template_id: str,
    recipient_email: str,
    test_data: Dict[str, Any],
    sender_id: str
) -> Dict[str, str]:
    """
    Send a test email for template preview.
    """
    try:
        template = EmailTemplate.objects.get(id=template_id)
        sender = User.objects.get(id=sender_id)
        
        # Prepare test context
        context_data = template.get_preview_data()
        context_data.update(test_data)
        
        # Render content
        subject = render_email_template(template.subject, context_data)
        html_content = render_email_template(template.html_content, context_data)
        text_content = render_email_template(template.text_content, context_data)
        
        # Add test banner
        test_banner = """
        <div style="background-color: #ff0; padding: 10px; text-align: center; font-weight: bold;">
            TEST EMAIL - This is a test of the email template
        </div>
        """
        html_content = test_banner + html_content
        
        # Create and send email
        email = EmailMultiAlternatives(
            subject=f"[TEST] {subject}",
            body=text_content,
            from_email=f"{template.from_name} <{template.from_email}>",
            to=[recipient_email],
            reply_to=[template.reply_to_email] if template.reply_to_email else None
        )
        email.attach_alternative(html_content, "text/html")
        
        backend = get_email_backend()
        backend.send_messages([email])
        
        # Create notification for sender
        Notification.objects.create(
            user=sender,
            notification_type='email_test_sent',
            title="Test Email Sent",
            message=f"Test email sent to {recipient_email} using template '{template.name}'",
            metadata={
                'template_id': str(template.id),
                'recipient': recipient_email
            }
        )
        
        return {'status': 'sent', 'recipient': recipient_email}
        
    except Exception as e:
        logger.error(f"Error sending test email: {str(e)}")
        
        # Create error notification
        if 'sender' in locals():
            Notification.objects.create(
                user=sender,
                notification_type='email_test_failed',
                title="Test Email Failed",
                message=f"Failed to send test email: {str(e)}",
                metadata={
                    'template_id': template_id,
                    'recipient': recipient_email,
                    'error': str(e)
                }
            )
        
        return {'status': 'failed', 'error': str(e)}


@shared_task
def schedule_campaign(campaign_id: str) -> Dict[str, str]:
    """
    Task to be executed at the scheduled time to start a campaign.
    """
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        
        if campaign.status != EmailCampaign.CampaignStatus.SCHEDULED:
            return {'status': 'skipped', 'reason': 'Campaign not scheduled'}
        
        # Trigger sending
        send_campaign_emails.delay(campaign_id)
        
        return {'status': 'started', 'campaign_id': campaign_id}
        
    except EmailCampaign.DoesNotExist:
        logger.error(f"Scheduled campaign {campaign_id} not found")
        return {'status': 'error', 'error': 'Campaign not found'}


@shared_task
def process_email_event(event_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Process incoming email events from ESP webhooks.
    
    Handles events like delivered, opened, clicked, bounced, etc.
    """
    try:
        # Extract message ID from event data
        # This varies by ESP - adjust based on your provider
        message_id = event_data.get('message_id') or event_data.get('X-Message-ID')
        event_type = event_data.get('event', '').lower()
        timestamp = event_data.get('timestamp', timezone.now())
        
        if not message_id:
            logger.warning(f"No message ID in event data: {event_data}")
            return {'status': 'skipped', 'reason': 'No message ID'}
        
        # Get message
        try:
            message = EmailMessage.objects.get(message_id=message_id)
        except EmailMessage.DoesNotExist:
            # Try by our internal ID
            message = EmailMessage.objects.get(id=message_id)
        
        # Map ESP event types to our event types
        event_type_map = {
            'delivered': EmailEvent.EventType.DELIVERED,
            'open': EmailEvent.EventType.OPENED,
            'opened': EmailEvent.EventType.OPENED,
            'click': EmailEvent.EventType.CLICKED,
            'clicked': EmailEvent.EventType.CLICKED,
            'bounce': EmailEvent.EventType.BOUNCED,
            'bounced': EmailEvent.EventType.BOUNCED,
            'dropped': EmailEvent.EventType.FAILED,
            'spam': EmailEvent.EventType.COMPLAINED,
            'complaint': EmailEvent.EventType.COMPLAINED,
            'unsubscribe': EmailEvent.EventType.UNSUBSCRIBED,
        }
        
        mapped_event_type = event_type_map.get(event_type)
        if not mapped_event_type:
            logger.warning(f"Unknown event type: {event_type}")
            return {'status': 'skipped', 'reason': 'Unknown event type'}
        
        # Create event record
        event = EmailEvent.objects.create(
            message=message,
            event_type=mapped_event_type,
            timestamp=timestamp,
            ip_address=event_data.get('ip'),
            user_agent=event_data.get('user_agent', ''),
            metadata=event_data,
            link_url=event_data.get('url', ''),
            link_text=event_data.get('link_text', '')
        )
        
        # Update message status and stats
        with transaction.atomic():
            if mapped_event_type == EmailEvent.EventType.DELIVERED:
                message.status = EmailMessage.MessageStatus.DELIVERED
                message.delivered_at = timestamp
                message.save()
                
                # Update campaign stats
                message.campaign.emails_delivered = F('emails_delivered') + 1
                message.campaign.save()
                
            elif mapped_event_type == EmailEvent.EventType.OPENED:
                message.status = EmailMessage.MessageStatus.OPENED
                if not message.first_opened_at:
                    message.first_opened_at = timestamp
                    
                    # Update campaign stats for unique opens
                    message.campaign.emails_opened = F('emails_opened') + 1
                    message.campaign.save()
                    
                    # Update contact
                    message.contact.last_email_opened_at = timestamp
                    message.contact.save(update_fields=['last_email_opened_at'])
                    
                    # Create activity
                    ContactActivity.objects.create(
                        group=message.campaign.group,
                        contact=message.contact,
                        activity_type=ActivityType.EMAIL_OPENED,
                        subject=f"Opened: {message.subject}",
                        metadata={
                            'campaign_id': str(message.campaign.id),
                            'message_id': str(message.id)
                        }
                    )
                
                message.last_opened_at = timestamp
                message.open_count = F('open_count') + 1
                message.ip_address = event_data.get('ip', message.ip_address)
                message.user_agent = event_data.get('user_agent', message.user_agent)
                message.save()
                
            elif mapped_event_type == EmailEvent.EventType.CLICKED:
                message.status = EmailMessage.MessageStatus.CLICKED
                if not message.first_clicked_at:
                    message.first_clicked_at = timestamp
                    
                    # Update campaign stats for unique clicks
                    message.campaign.emails_clicked = F('emails_clicked') + 1
                    message.campaign.save()
                    
                    # Create activity
                    ContactActivity.objects.create(
                        group=message.campaign.group,
                        contact=message.contact,
                        activity_type=ActivityType.EMAIL_CLICKED,
                        subject=f"Clicked link in: {message.subject}",
                        description=f"Clicked: {event_data.get('url', 'Unknown URL')}",
                        metadata={
                            'campaign_id': str(message.campaign.id),
                            'message_id': str(message.id),
                            'url': event_data.get('url', '')
                        }
                    )
                
                message.last_clicked_at = timestamp
                message.click_count = F('click_count') + 1
                message.save()
                
            elif mapped_event_type == EmailEvent.EventType.BOUNCED:
                message.status = EmailMessage.MessageStatus.BOUNCED
                message.bounce_type = event_data.get('bounce_type', 'unknown')
                message.bounce_reason = event_data.get('reason', '')
                message.save()
                
                # Update campaign stats
                message.campaign.emails_bounced = F('emails_bounced') + 1
                message.campaign.save()
                
                # Mark contact as having bad email if hard bounce
                if event_data.get('bounce_type') == 'hard':
                    message.contact.email_opt_in = False
                    message.contact.save(update_fields=['email_opt_in'])
                    
            elif mapped_event_type == EmailEvent.EventType.UNSUBSCRIBED:
                message.status = EmailMessage.MessageStatus.UNSUBSCRIBED
                message.save()
                
                # Update campaign stats
                message.campaign.emails_unsubscribed = F('emails_unsubscribed') + 1
                message.campaign.save()
                
                # Update contact opt-in status
                message.contact.unsubscribe()
                message.contact.save()
                
                # Create activity
                ContactActivity.objects.create(
                    group=message.campaign.group,
                    contact=message.contact,
                    activity_type=ActivityType.EMAIL_CLICKED,
                    subject="Unsubscribed from emails",
                    metadata={
                        'campaign_id': str(message.campaign.id),
                        'message_id': str(message.id)
                    }
                )
                
            elif mapped_event_type == EmailEvent.EventType.COMPLAINED:
                message.status = EmailMessage.MessageStatus.COMPLAINED
                message.save()
                
                # Mark contact as opted out
                message.contact.email_opt_in = False
                message.contact.save(update_fields=['email_opt_in'])
        
        return {'status': 'processed', 'event_id': str(event.id)}
        
    except Exception as e:
        logger.error(f"Error processing email event: {str(e)}")
        return {'status': 'error', 'error': str(e)}


@shared_task
def update_campaign_analytics(campaign_id: str) -> Dict[str, Any]:
    """
    Recalculate campaign analytics from message data.
    
    Used for periodic updates or after bulk operations.
    """
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        
        # Get aggregated stats from messages
        stats = campaign.messages.aggregate(
            sent=Count('id', filter=Q(status__in=[
                EmailMessage.MessageStatus.SENT,
                EmailMessage.MessageStatus.DELIVERED,
                EmailMessage.MessageStatus.OPENED,
                EmailMessage.MessageStatus.CLICKED
            ])),
            delivered=Count('id', filter=Q(status__in=[
                EmailMessage.MessageStatus.DELIVERED,
                EmailMessage.MessageStatus.OPENED,
                EmailMessage.MessageStatus.CLICKED
            ])),
            opened=Count('id', filter=Q(open_count__gt=0)),
            clicked=Count('id', filter=Q(click_count__gt=0)),
            bounced=Count('id', filter=Q(status=EmailMessage.MessageStatus.BOUNCED)),
            unsubscribed=Count('id', filter=Q(status=EmailMessage.MessageStatus.UNSUBSCRIBED))
        )
        
        # Update campaign
        campaign.emails_sent = stats['sent']
        campaign.emails_delivered = stats['delivered']
        campaign.emails_opened = stats['opened']
        campaign.emails_clicked = stats['clicked']
        campaign.emails_bounced = stats['bounced']
        campaign.emails_unsubscribed = stats['unsubscribed']
        campaign.save()
        
        return {
            'status': 'updated',
            'campaign_id': campaign_id,
            'stats': stats
        }
        
    except EmailCampaign.DoesNotExist:
        logger.error(f"Campaign {campaign_id} not found")
        return {'status': 'error', 'error': 'Campaign not found'}


@shared_task
def cleanup_old_events(days: int = 90) -> Dict[str, int]:
    """
    Clean up old email events to manage database size.
    
    Keeps events for the specified number of days.
    """
    cutoff_date = timezone.now() - timedelta(days=days)
    
    # Delete old events
    deleted_count = EmailEvent.objects.filter(
        timestamp__lt=cutoff_date
    ).delete()[0]
    
    logger.info(f"Deleted {deleted_count} email events older than {days} days")
    
    return {'deleted': deleted_count}


# Helper functions

def _get_campaign_recipients(campaign: EmailCampaign) -> List[Contact]:
    """Get unique list of recipients for a campaign."""
    contact_ids = set()
    
    # Get contacts from all lists
    for contact_list in campaign.contact_lists.all():
        if contact_list.is_dynamic:
            # TODO: Implement dynamic list logic
            # For now, skip dynamic lists
            continue
        else:
            contact_ids.update(
                contact_list.contacts.values_list('id', flat=True)
            )
    
    # Remove excluded contacts
    excluded_ids = campaign.excluded_contacts.values_list('id', flat=True)
    contact_ids -= set(excluded_ids)
    
    # Get only opted-in, active contacts
    contacts = Contact.objects.filter(
        id__in=contact_ids,
        email_opt_in=True,
        status__in=[
            Contact.ContactStatus.LEAD,
            Contact.ContactStatus.QUALIFIED,
            Contact.ContactStatus.OPPORTUNITY,
            Contact.ContactStatus.CUSTOMER
        ]
    ).order_by('email')
    
    return list(contacts)


def _prepare_email_context(message: EmailMessage) -> Dict[str, Any]:
    """Prepare template context data for an email message."""
    contact = message.contact
    campaign = message.campaign
    
    # Base context data
    context = {
        'first_name': contact.first_name or 'Friend',
        'last_name': contact.last_name or '',
        'full_name': contact.full_name or contact.email,
        'email': contact.email,
        'company_name': contact.company_name or '',
        'job_title': contact.job_title or '',
        'department': contact.department or '',
        'city': contact.city or '',
        'country': contact.country or '',
        
        # Campaign data
        'campaign_name': campaign.name,
        
        # System data
        'current_year': datetime.now().year,
        'current_date': datetime.now().strftime('%B %d, %Y'),
        
        # URLs
        'unsubscribe_url': generate_unsubscribe_url(message),
        'preferences_url': f"{settings.FRONTEND_URL}/preferences/{contact.id}",
        'view_online_url': f"{settings.FRONTEND_URL}/email/view/{message.id}",
    }
    
    # Add custom fields
    if contact.custom_fields:
        context.update(contact.custom_fields)
    
    return context


def _add_tracking_pixel(html_content: str, message: EmailMessage) -> str:
    """Add invisible tracking pixel to HTML content."""
    tracking_pixel = generate_tracking_pixel(message)
    
    # Insert before closing body tag
    if '</body>' in html_content:
        html_content = html_content.replace('</body>', f'{tracking_pixel}</body>')
    else:
        # If no body tag, append to end
        html_content += tracking_pixel
    
    return html_content


def _send_campaign_completion_notification(
    campaign: EmailCampaign,
    sent_count: int,
    failed_count: int
) -> None:
    """Send notification when campaign completes."""
    # Notify campaign creator
    Notification.objects.create(
        user=campaign.created_by,
        notification_type='campaign_completed',
        title=f"Campaign '{campaign.name}' Completed",
        message=f"Successfully sent {sent_count} emails. {failed_count} failed.",
        metadata={
            'campaign_id': str(campaign.id),
            'sent': sent_count,
            'failed': failed_count,
            'total': campaign.total_recipients
        }
    )
    
    # Also notify approver if different
    if campaign.approved_by and campaign.approved_by != campaign.created_by:
        Notification.objects.create(
            user=campaign.approved_by,
            notification_type='campaign_completed',
            title=f"Campaign '{campaign.name}' Completed",
            message=f"Campaign you approved has completed. Sent {sent_count} emails.",
            metadata={
                'campaign_id': str(campaign.id),
                'sent': sent_count,
                'failed': failed_count,
                'total': campaign.total_recipients
            }
        )