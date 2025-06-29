"""
Email utility functions for the EnterpriseLand Due-Diligence Platform.

Provides helper functions for email rendering, validation, tracking,
and integration with email service providers.
"""

import re
import hashlib
import urllib.parse
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from django.template import Template, Context
from django.template.loader import render_to_string
from django.core.mail import get_connection
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils.crypto import get_random_string
from django.urls import reverse
from jinja2 import Environment, BaseLoader, TemplateError

from bs4 import BeautifulSoup


class JinjaStringLoader(BaseLoader):
    """Custom Jinja2 loader for string templates."""
    
    def get_source(self, environment, template):
        return template, None, lambda: True


def render_email_template(template_string: str, context: Dict[str, Any]) -> str:
    """
    Render an email template using Jinja2.
    
    Supports both Django and Jinja2 template syntax for compatibility.
    """
    try:
        # Try Jinja2 first (preferred)
        env = Environment(loader=JinjaStringLoader())
        template = env.from_string(template_string)
        return template.render(**context)
    except TemplateError:
        # Fall back to Django templates
        try:
            template = Template(template_string)
            return template.render(Context(context))
        except Exception as e:
            raise TemplateError(f"Template rendering failed: {str(e)}")


def validate_email_address(email: str) -> bool:
    """
    Validate an email address.
    
    Checks format and optionally verifies deliverability.
    """
    try:
        validate_email(email)
        
        # Additional validation
        if email.count('@') != 1:
            return False
        
        # Check for common typos
        domain = email.split('@')[1].lower()
        typo_domains = {
            'gmial.com': 'gmail.com',
            'gmai.com': 'gmail.com',
            'yahooo.com': 'yahoo.com',
            'outlok.com': 'outlook.com',
        }
        
        if domain in typo_domains:
            return False
        
        # In production, you might want to use a service like:
        # - email-validator library
        # - External API (SendGrid, Mailgun validation API)
        # - DNS/MX record checking
        
        return True
        
    except ValidationError:
        return False


def generate_unsubscribe_url(message) -> str:
    """
    Generate a unique unsubscribe URL for an email message.
    
    Includes security token to prevent unauthorized unsubscribes.
    """
    # Generate secure token
    token_data = f"{message.id}-{message.contact.id}-{message.contact.email}"
    token = hashlib.sha256(token_data.encode()).hexdigest()[:32]
    
    # Build URL
    base_url = settings.FRONTEND_URL.rstrip('/')
    params = {
        'message': str(message.id),
        'contact': str(message.contact.id),
        'token': token
    }
    
    return f"{base_url}/unsubscribe?{urllib.parse.urlencode(params)}"


def generate_tracking_pixel(message) -> str:
    """
    Generate an invisible tracking pixel for open tracking.
    """
    # Generate tracking URL
    base_url = settings.BACKEND_URL.rstrip('/')
    tracking_id = hashlib.sha256(
        f"{message.id}-{datetime.now().isoformat()}".encode()
    ).hexdigest()[:16]
    
    tracking_url = f"{base_url}/api/contacts/email-events/track/open/{message.id}/{tracking_id}/"
    
    # Return invisible image tag
    return f'<img src="{tracking_url}" width="1" height="1" style="display:none;" alt="" />'


def track_email_links(content: str, message, is_html: bool = True) -> str:
    """
    Replace links in email content with tracking URLs.
    
    Preserves original URLs while adding click tracking.
    """
    if not is_html:
        # For plain text, use regex
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        
        def replace_url(match):
            original_url = match.group(0)
            tracking_url = _create_tracking_url(original_url, message)
            return tracking_url
        
        return re.sub(url_pattern, replace_url, content)
    
    else:
        # For HTML, use BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')
        
        # Track all <a> tags
        for link in soup.find_all('a', href=True):
            original_url = link['href']
            
            # Skip mailto: and tel: links
            if original_url.startswith(('mailto:', 'tel:', '#')):
                continue
            
            # Skip unsubscribe links (don't want to track those)
            if 'unsubscribe' in original_url.lower():
                continue
            
            tracking_url = _create_tracking_url(original_url, message)
            link['href'] = tracking_url
        
        return str(soup)


def _create_tracking_url(original_url: str, message) -> str:
    """Create a tracking URL that redirects to the original URL."""
    # Generate tracking ID
    tracking_id = hashlib.sha256(
        f"{message.id}-{original_url}-{datetime.now().isoformat()}".encode()
    ).hexdigest()[:16]
    
    # Build tracking URL
    base_url = settings.BACKEND_URL.rstrip('/')
    params = {
        'url': original_url,
        'message': str(message.id),
        'id': tracking_id
    }
    
    return f"{base_url}/api/contacts/email-events/track/click/?{urllib.parse.urlencode(params)}"


def get_email_backend(connection_name: Optional[str] = None):
    """
    Get configured email backend.
    
    Supports multiple backends for different email types.
    """
    # Use specified connection or default
    connection_config = None
    
    if connection_name and hasattr(settings, 'EMAIL_CONNECTIONS'):
        connection_config = settings.EMAIL_CONNECTIONS.get(connection_name)
    
    if connection_config:
        return get_connection(**connection_config)
    
    # Use default connection
    return get_connection()


def parse_email_headers(headers: str) -> Dict[str, str]:
    """Parse email headers into a dictionary."""
    header_dict = {}
    
    for line in headers.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            header_dict[key.strip()] = value.strip()
    
    return header_dict


def calculate_email_reputation(contact) -> float:
    """
    Calculate email reputation score for a contact.
    
    Used to prioritize sending and identify potential issues.
    """
    score = 100.0
    
    # Check email engagement history
    from .models import EmailMessage, EmailEvent
    
    recent_messages = EmailMessage.objects.filter(
        contact=contact,
        sent_at__gte=datetime.now() - timedelta(days=90)
    ).order_by('-sent_at')[:10]
    
    if recent_messages:
        # Calculate engagement rate
        opened = sum(1 for m in recent_messages if m.open_count > 0)
        clicked = sum(1 for m in recent_messages if m.click_count > 0)
        bounced = sum(1 for m in recent_messages if m.status == 'bounced')
        
        open_rate = opened / len(recent_messages)
        click_rate = clicked / len(recent_messages)
        bounce_rate = bounced / len(recent_messages)
        
        # Adjust score based on engagement
        score -= (1 - open_rate) * 30  # Up to -30 for low opens
        score -= (1 - click_rate) * 20  # Up to -20 for low clicks
        score -= bounce_rate * 50       # Up to -50 for bounces
        
        # Check for spam complaints
        complaints = EmailEvent.objects.filter(
            message__contact=contact,
            event_type='complained'
        ).count()
        
        score -= complaints * 25  # -25 per complaint
    
    # Ensure score stays in valid range
    return max(0, min(100, score))


def generate_email_preview(html_content: str, max_length: int = 200) -> str:
    """
    Generate a text preview from HTML email content.
    
    Used for email client preview text.
    """
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.decompose()
    
    # Get text
    text = soup.get_text(separator=' ', strip=True)
    
    # Clean up whitespace
    text = ' '.join(text.split())
    
    # Truncate if needed
    if len(text) > max_length:
        text = text[:max_length - 3] + '...'
    
    return text


def create_email_signature(user) -> str:
    """
    Create a professional email signature for a user.
    """
    signature_html = f"""
    <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
        <p style="margin: 0; font-weight: bold;">{user.get_full_name()}</p>
        <p style="margin: 0; color: #666;">{user.job_title or 'Team Member'}</p>
        <p style="margin: 0; color: #215788;">EnterpriseLand Due-Diligence Platform</p>
        <p style="margin: 5px 0 0 0; font-size: 12px; color: #999;">
            This email and any attachments are confidential and intended solely for the addressee.
        </p>
    </div>
    """
    
    signature_text = f"""

--
{user.get_full_name()}
{user.job_title or 'Team Member'}
EnterpriseLand Due-Diligence Platform

This email and any attachments are confidential and intended solely for the addressee.
"""
    
    return {
        'html': signature_html,
        'text': signature_text
    }


def sanitize_html_content(html_content: str) -> str:
    """
    Sanitize HTML content to prevent XSS and ensure email compatibility.
    """
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove dangerous tags
    dangerous_tags = ['script', 'iframe', 'object', 'embed', 'form']
    for tag in dangerous_tags:
        for element in soup.find_all(tag):
            element.decompose()
    
    # Remove dangerous attributes
    dangerous_attrs = ['onclick', 'onload', 'onerror', 'onmouseover']
    for attr in dangerous_attrs:
        for element in soup.find_all(attrs={attr: True}):
            del element[attr]
    
    # Ensure all links open in new window
    for link in soup.find_all('a'):
        link['target'] = '_blank'
        link['rel'] = 'noopener noreferrer'
    
    return str(soup)


def estimate_email_size(html_content: str, text_content: str) -> Dict[str, Any]:
    """
    Estimate the size of an email message.
    
    Large emails may be clipped by email clients.
    """
    # Calculate sizes
    html_size = len(html_content.encode('utf-8'))
    text_size = len(text_content.encode('utf-8'))
    total_size = html_size + text_size
    
    # Gmail clips messages larger than 102KB
    gmail_limit = 102 * 1024
    
    return {
        'html_size': html_size,
        'text_size': text_size,
        'total_size': total_size,
        'will_be_clipped': total_size > gmail_limit,
        'size_limit': gmail_limit,
        'percentage_of_limit': round((total_size / gmail_limit) * 100, 2)
    }


def create_calendar_invite(
    subject: str,
    description: str,
    start_time: datetime,
    end_time: datetime,
    attendees: List[str],
    location: Optional[str] = None
) -> str:
    """
    Create an iCalendar (.ics) file content for meeting invites.
    """
    # Generate unique ID
    uid = f"{get_random_string(32)}@enterpriseland.com"
    
    # Format times
    dtstart = start_time.strftime('%Y%m%dT%H%M%S')
    dtend = end_time.strftime('%Y%m%dT%H%M%S')
    dtstamp = datetime.now().strftime('%Y%m%dT%H%M%SZ')
    
    # Build attendee list
    attendee_lines = []
    for email in attendees:
        attendee_lines.append(f"ATTENDEE;RSVP=TRUE;CN={email}:mailto:{email}")
    
    # Build iCalendar content
    ical_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//EnterpriseLand//Due Diligence Platform//EN
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dtstamp}
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY:{subject}
DESCRIPTION:{description}
{f'LOCATION:{location}' if location else ''}
{''.join(attendee_lines)}
ORGANIZER;CN=EnterpriseLand:mailto:noreply@enterpriseland.com
STATUS:CONFIRMED
SEQUENCE:0
END:VEVENT
END:VCALENDAR"""
    
    return ical_content.strip()


def format_currency(amount: float, currency: str = 'USD') -> str:
    """Format currency for email display."""
    currency_symbols = {
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'JPY': '¥',
    }
    
    symbol = currency_symbols.get(currency, currency)
    formatted_amount = f"{amount:,.2f}"
    
    return f"{symbol}{formatted_amount}"


def create_email_report(campaign) -> Dict[str, Any]:
    """
    Create a comprehensive report for an email campaign.
    """
    from .models import EmailMessage, EmailEvent
    
    # Calculate metrics
    messages = campaign.messages.all()
    total_sent = messages.count()
    
    # Time-based analysis
    if campaign.started_at and campaign.completed_at:
        duration = campaign.completed_at - campaign.started_at
        send_rate = total_sent / (duration.total_seconds() / 3600) if duration.total_seconds() > 0 else 0
    else:
        duration = None
        send_rate = 0
    
    # Get best performing links
    top_links = EmailEvent.objects.filter(
        message__campaign=campaign,
        event_type='clicked'
    ).values('link_url').annotate(
        clicks=Count('id')
    ).order_by('-clicks')[:5]
    
    # Get engagement by hour
    hourly_engagement = []
    if campaign.started_at:
        for hour in range(24):
            hour_start = campaign.started_at.replace(hour=hour, minute=0, second=0)
            hour_end = hour_start + timedelta(hours=1)
            
            opens = EmailEvent.objects.filter(
                message__campaign=campaign,
                event_type='opened',
                timestamp__gte=hour_start,
                timestamp__lt=hour_end
            ).count()
            
            clicks = EmailEvent.objects.filter(
                message__campaign=campaign,
                event_type='clicked',
                timestamp__gte=hour_start,
                timestamp__lt=hour_end
            ).count()
            
            if opens > 0 or clicks > 0:
                hourly_engagement.append({
                    'hour': hour,
                    'opens': opens,
                    'clicks': clicks
                })
    
    return {
        'campaign': {
            'name': campaign.name,
            'subject': campaign.template.subject,
            'started_at': campaign.started_at,
            'completed_at': campaign.completed_at,
            'duration': str(duration) if duration else None,
            'send_rate_per_hour': round(send_rate, 2)
        },
        'metrics': {
            'total_recipients': campaign.total_recipients,
            'emails_sent': campaign.emails_sent,
            'emails_delivered': campaign.emails_delivered,
            'delivery_rate': round((campaign.emails_delivered / campaign.emails_sent * 100) if campaign.emails_sent > 0 else 0, 2),
            'emails_opened': campaign.emails_opened,
            'open_rate': campaign.open_rate,
            'emails_clicked': campaign.emails_clicked,
            'click_rate': campaign.click_rate,
            'click_to_open_rate': round((campaign.emails_clicked / campaign.emails_opened * 100) if campaign.emails_opened > 0 else 0, 2),
            'emails_bounced': campaign.emails_bounced,
            'bounce_rate': campaign.bounce_rate,
            'emails_unsubscribed': campaign.emails_unsubscribed,
            'unsubscribe_rate': round((campaign.emails_unsubscribed / campaign.emails_delivered * 100) if campaign.emails_delivered > 0 else 0, 2)
        },
        'engagement': {
            'top_links': list(top_links),
            'hourly_activity': hourly_engagement,
            'best_hour': max(hourly_engagement, key=lambda x: x['opens'] + x['clicks'])['hour'] if hourly_engagement else None
        }
    }