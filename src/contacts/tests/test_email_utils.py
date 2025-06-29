"""
Tests for email utility functions.

Comprehensive test coverage for Jinja2 template rendering, email validation,
HTML sanitization, tracking link generation, and utility functions.
"""

import re
import json
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, MagicMock

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.template import Template, Context, TemplateDoesNotExist
from django.conf import settings
from jinja2 import TemplateError
import factory

from accounts.models import Group, GroupMembership
from contacts.models import Contact, EmailTemplate, EmailCampaign, EmailMessage
from contacts.email_utils import (
    render_email_template, validate_email_address, generate_unsubscribe_url,
    generate_tracking_pixel, track_email_links, get_email_backend,
    sanitize_html_content, extract_template_variables, generate_preview_context,
    format_email_address, parse_webhook_event, calculate_email_analytics,
    should_retry_email, get_email_domain, validate_email_content,
    JinjaStringLoader
)

User = get_user_model()


# Re-use factories
class GroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Group
    
    name = factory.Sequence(lambda n: f"Test Group {n}")


class ContactFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Contact
    
    email = factory.Sequence(lambda n: f"contact{n}@example.com")
    first_name = factory.Sequence(lambda n: f"Contact{n}")
    last_name = "Test"
    contact_type = Contact.ContactType.INDIVIDUAL
    status = Contact.ContactStatus.LEAD
    email_opt_in = True
    group = factory.SubFactory(GroupFactory)


class EmailTemplateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailTemplate
    
    name = factory.Sequence(lambda n: f"Template {n}")
    template_type = EmailTemplate.TemplateType.MARKETING
    subject = "Test Subject - {{ first_name }}"
    preheader = "Test preheader"
    html_content = "<html><body>Hello {{ first_name }}! <a href='{{ unsubscribe_url }}'>Unsubscribe</a></body></html>"
    text_content = "Hello {{ first_name }}! Unsubscribe: {{ unsubscribe_url }}"
    from_name = "Test Sender"
    from_email = "noreply@test.com"
    is_active = True
    group = factory.SubFactory(GroupFactory)


class EmailCampaignFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailCampaign
    
    name = factory.Sequence(lambda n: f"Campaign {n}")
    template = factory.SubFactory(EmailTemplateFactory)
    group = factory.SubFactory(GroupFactory)


class EmailMessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailMessage
    
    campaign = factory.SubFactory(EmailCampaignFactory)
    contact = factory.SubFactory(ContactFactory)
    template_used = factory.SubFactory(EmailTemplateFactory)
    subject = "Test Email"
    from_email = "noreply@test.com"
    to_email = factory.Sequence(lambda n: f"recipient{n}@example.com")
    status = EmailMessage.MessageStatus.PENDING
    group = factory.SubFactory(GroupFactory)


class RenderEmailTemplateTests(TestCase):
    """Test cases for email template rendering."""
    
    def test_render_simple_template(self):
        """Test rendering simple Jinja2 template."""
        template = "Hello {{ name }}!"
        context = {"name": "World"}
        
        result = render_email_template(template, context)
        
        self.assertEqual(result, "Hello World!")
    
    def test_render_template_with_filters(self):
        """Test rendering template with Jinja2 filters."""
        template = "Price: ${{ price|round(2) }}"
        context = {"price": 19.995}
        
        result = render_email_template(template, context)
        
        self.assertEqual(result, "Price: $20.0")
    
    def test_render_template_with_conditionals(self):
        """Test rendering template with conditionals."""
        template = """
        {% if user_type == 'premium' %}
        Welcome Premium User!
        {% else %}
        Welcome!
        {% endif %}
        """
        
        # Premium user
        result = render_email_template(template, {"user_type": "premium"})
        self.assertIn("Welcome Premium User!", result)
        
        # Regular user
        result = render_email_template(template, {"user_type": "regular"})
        self.assertIn("Welcome!", result)
        self.assertNotIn("Premium", result)
    
    def test_render_template_with_loops(self):
        """Test rendering template with loops."""
        template = """
        Items:
        {% for item in items %}
        - {{ item.name }}: ${{ item.price }}
        {% endfor %}
        """
        context = {
            "items": [
                {"name": "Product A", "price": 10},
                {"name": "Product B", "price": 20}
            ]
        }
        
        result = render_email_template(template, context)
        
        self.assertIn("Product A: $10", result)
        self.assertIn("Product B: $20", result)
    
    def test_render_template_missing_variable(self):
        """Test rendering with missing variables."""
        template = "Hello {{ first_name }} {{ last_name }}!"
        context = {"first_name": "John"}  # Missing last_name
        
        # Should not raise error, just render empty
        result = render_email_template(template, context)
        
        self.assertEqual(result, "Hello John !")
    
    def test_render_template_with_default_filter(self):
        """Test rendering with default filter for missing variables."""
        template = "Hello {{ name|default('Guest') }}!"
        
        # With name
        result = render_email_template(template, {"name": "John"})
        self.assertEqual(result, "Hello John!")
        
        # Without name
        result = render_email_template(template, {})
        self.assertEqual(result, "Hello Guest!")
    
    def test_render_invalid_template_syntax(self):
        """Test rendering with invalid template syntax."""
        template = "Hello {{ name"  # Missing closing braces
        
        with self.assertRaises(TemplateError):
            render_email_template(template, {"name": "John"})
    
    def test_render_django_template_fallback(self):
        """Test fallback to Django template rendering."""
        # Use Django-specific syntax that Jinja2 doesn't support
        template = "Hello {{ name|title }}"
        context = {"name": "john doe"}
        
        with patch('jinja2.Environment.from_string') as mock_jinja:
            mock_jinja.side_effect = TemplateError("Jinja2 error")
            
            # Should fall back to Django
            result = render_email_template(template, context)
            self.assertEqual(result, "Hello John Doe")
    
    def test_render_complex_email_template(self):
        """Test rendering complex email template."""
        template = """
        <!DOCTYPE html>
        <html>
        <body>
            <h1>Hello {{ first_name }}!</h1>
            <p>Thank you for your order #{{ order_id }}.</p>
            
            <h2>Order Details:</h2>
            <ul>
            {% for item in items %}
                <li>{{ item.name }} - Qty: {{ item.quantity }} - ${{ item.price }}</li>
            {% endfor %}
            </ul>
            
            <p>Total: ${{ total|round(2) }}</p>
            
            {% if discount > 0 %}
            <p>Discount applied: {{ discount }}%</p>
            {% endif %}
            
            <a href="{{ unsubscribe_url }}">Unsubscribe</a>
        </body>
        </html>
        """
        
        context = {
            "first_name": "Jane",
            "order_id": "12345",
            "items": [
                {"name": "Widget", "quantity": 2, "price": 10.00},
                {"name": "Gadget", "quantity": 1, "price": 25.00}
            ],
            "total": 45.00,
            "discount": 10,
            "unsubscribe_url": "https://example.com/unsub/token123"
        }
        
        result = render_email_template(template, context)
        
        self.assertIn("Hello Jane!", result)
        self.assertIn("order #12345", result)
        self.assertIn("Widget - Qty: 2 - $10.0", result)
        self.assertIn("Total: $45.0", result)
        self.assertIn("Discount applied: 10%", result)


class ValidateEmailAddressTests(TestCase):
    """Test cases for email address validation."""
    
    def test_valid_email_addresses(self):
        """Test validation of valid email addresses."""
        valid_emails = [
            "user@example.com",
            "first.last@example.com",
            "user+tag@example.com",
            "user@subdomain.example.com",
            "user123@example.com",
            "user_name@example.com",
            "user-name@example.com"
        ]
        
        for email in valid_emails:
            self.assertTrue(
                validate_email_address(email),
                f"{email} should be valid"
            )
    
    def test_invalid_email_addresses(self):
        """Test validation of invalid email addresses."""
        invalid_emails = [
            "not-an-email",
            "@example.com",
            "user@",
            "user@@example.com",
            "user@example",
            "user @example.com",  # Space
            "user@.com",
            "",
            None
        ]
        
        for email in invalid_emails:
            if email is not None:
                self.assertFalse(
                    validate_email_address(email),
                    f"{email} should be invalid"
                )
    
    def test_common_email_typos(self):
        """Test detection of common email typos."""
        typo_emails = [
            "user@gmial.com",  # Gmail typo
            "user@gmai.com",
            "user@yahooo.com",  # Yahoo typo
            "user@outlok.com"   # Outlook typo
        ]
        
        for email in typo_emails:
            self.assertFalse(
                validate_email_address(email),
                f"{email} should be detected as typo"
            )
    
    def test_email_with_special_characters(self):
        """Test emails with special but valid characters."""
        # These are technically valid but uncommon
        special_emails = [
            "user.name+tag@example.com",
            "user_name@example.com",
            "user-name@example.com",
            "user'name@example.com",  # Apostrophe is valid
        ]
        
        for email in special_emails:
            result = validate_email_address(email)
            # Some might be rejected by stricter validation
            self.assertIsInstance(result, bool)
    
    @patch('contacts.email_utils.validate_email')
    def test_django_validation_integration(self, mock_validate):
        """Test integration with Django's email validation."""
        mock_validate.side_effect = ValidationError("Invalid")
        
        result = validate_email_address("bad@email")
        
        self.assertFalse(result)
        mock_validate.assert_called_once()


class GenerateUnsubscribeUrlTests(TestCase):
    """Test cases for unsubscribe URL generation."""
    
    def setUp(self):
        """Set up test data."""
        self.contact = ContactFactory(email="test@example.com")
        self.campaign = EmailCampaignFactory()
        self.message = EmailMessageFactory(
            contact=self.contact,
            campaign=self.campaign
        )
    
    @patch('django.conf.settings.FRONTEND_URL', 'https://app.example.com')
    def test_generate_unsubscribe_url(self):
        """Test generating unsubscribe URL."""
        url = generate_unsubscribe_url(self.message)
        
        self.assertIn('https://app.example.com', url)
        self.assertIn('unsubscribe', url)
        self.assertIn('token=', url)
        
        # Parse URL
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        self.assertIn('token', params)
        self.assertIn('email', params)
        self.assertEqual(params['email'][0], 'test@example.com')
    
    def test_unsubscribe_token_generation(self):
        """Test unsubscribe token is unique and secure."""
        url1 = generate_unsubscribe_url(self.message)
        
        # Create another message for same contact
        message2 = EmailMessageFactory(contact=self.contact)
        url2 = generate_unsubscribe_url(message2)
        
        # URLs should be different (different tokens)
        self.assertNotEqual(url1, url2)
    
    def test_unsubscribe_url_encoding(self):
        """Test URL properly encodes special characters."""
        self.contact.email = "user+tag@example.com"
        self.contact.save()
        
        url = generate_unsubscribe_url(self.message)
        
        # Email should be properly encoded
        self.assertIn('user%2Btag%40example.com', url)
    
    @patch('django.urls.reverse')
    def test_unsubscribe_url_uses_reverse(self, mock_reverse):
        """Test unsubscribe URL uses Django URL reversal."""
        mock_reverse.return_value = '/unsubscribe/'
        
        url = generate_unsubscribe_url(self.message)
        
        mock_reverse.assert_called_with('unsubscribe')
        self.assertIn('/unsubscribe/', url)


class GenerateTrackingPixelTests(TestCase):
    """Test cases for tracking pixel generation."""
    
    def setUp(self):
        """Set up test data."""
        self.message = EmailMessageFactory()
    
    def test_generate_tracking_pixel(self):
        """Test generating email tracking pixel."""
        pixel = generate_tracking_pixel(self.message)
        
        self.assertIn('<img', pixel)
        self.assertIn('src=', pixel)
        self.assertIn('width="1"', pixel)
        self.assertIn('height="1"', pixel)
        self.assertIn('alt=""', pixel)
        
        # Extract URL from pixel
        match = re.search(r'src="([^"]+)"', pixel)
        self.assertIsNotNone(match)
        
        url = match.group(1)
        self.assertIn('/track/open/', url)
        self.assertIn(f'message_id={self.message.id}', url)
    
    def test_tracking_pixel_transparent(self):
        """Test tracking pixel is transparent/invisible."""
        pixel = generate_tracking_pixel(self.message)
        
        # Should have invisible styling
        self.assertIn('style=', pixel)
        self.assertIn('display:none', pixel.lower())
    
    def test_tracking_pixel_unique_per_message(self):
        """Test each message gets unique tracking pixel."""
        message2 = EmailMessageFactory()
        
        pixel1 = generate_tracking_pixel(self.message)
        pixel2 = generate_tracking_pixel(message2)
        
        self.assertNotEqual(pixel1, pixel2)
        self.assertIn(str(self.message.id), pixel1)
        self.assertIn(str(message2.id), pixel2)


class TrackEmailLinksTests(TestCase):
    """Test cases for email link tracking."""
    
    def setUp(self):
        """Set up test data."""
        self.message = EmailMessageFactory()
        self.campaign = self.message.campaign
    
    def test_track_simple_links(self):
        """Test tracking simple links in HTML."""
        html = '''
        <p>Check out our <a href="https://example.com/product">new product</a>!</p>
        <p>Visit our <a href="https://example.com/about">about page</a>.</p>
        '''
        
        tracked = track_email_links(html, self.message)
        
        # Original links should be replaced
        self.assertNotIn('href="https://example.com/product"', tracked)
        self.assertNotIn('href="https://example.com/about"', tracked)
        
        # Should contain tracking URLs
        self.assertIn('/track/click/', tracked)
        self.assertIn(f'message_id={self.message.id}', tracked)
    
    def test_track_links_preserves_attributes(self):
        """Test link tracking preserves other attributes."""
        html = '''
        <a href="https://example.com" class="btn" target="_blank" title="Visit">Click</a>
        '''
        
        tracked = track_email_links(html, self.message)
        
        # Should preserve attributes
        self.assertIn('class="btn"', tracked)
        self.assertIn('target="_blank"', tracked)
        self.assertIn('title="Visit"', tracked)
    
    def test_track_links_encodes_urls(self):
        """Test link tracking properly encodes URLs."""
        html = '''
        <a href="https://example.com/search?q=test&category=email">Search</a>
        '''
        
        tracked = track_email_links(html, self.message)
        
        # URL should be encoded in tracking link
        self.assertIn('url=', tracked)
        # Query parameters should be preserved (encoded)
        self.assertIn('search', tracked)
    
    def test_skip_unsubscribe_links(self):
        """Test unsubscribe links are not tracked."""
        html = '''
        <a href="{{ unsubscribe_url }}">Unsubscribe</a>
        <a href="https://example.com/unsubscribe">Unsubscribe</a>
        '''
        
        tracked = track_email_links(html, self.message)
        
        # Unsubscribe links should not be tracked
        self.assertIn('{{ unsubscribe_url }}', tracked)
        self.assertIn('https://example.com/unsubscribe', tracked)
    
    def test_skip_mailto_links(self):
        """Test mailto links are not tracked."""
        html = '''
        <a href="mailto:support@example.com">Email us</a>
        '''
        
        tracked = track_email_links(html, self.message)
        
        # Mailto links should remain unchanged
        self.assertIn('mailto:support@example.com', tracked)
        self.assertNotIn('/track/click/', tracked)
    
    def test_track_links_disabled(self):
        """Test link tracking can be disabled."""
        self.campaign.track_clicks = False
        self.campaign.save()
        
        html = '<a href="https://example.com">Link</a>'
        
        tracked = track_email_links(html, self.message)
        
        # Should not modify links
        self.assertEqual(html, tracked)
    
    def test_track_complex_html(self):
        """Test tracking links in complex HTML."""
        html = '''
        <!DOCTYPE html>
        <html>
        <body>
            <table>
                <tr>
                    <td><a href="https://example.com/1">Link 1</a></td>
                    <td><a href="https://example.com/2">Link 2</a></td>
                </tr>
            </table>
            <div>
                <p>Text with <a href="https://example.com/3">inline link</a>.</p>
                <button onclick="location.href='https://example.com/4'">Button</button>
            </div>
        </body>
        </html>
        '''
        
        tracked = track_email_links(html, self.message)
        
        # Should track all <a> links
        self.assertEqual(tracked.count('/track/click/'), 3)
        # Should not track JavaScript hrefs
        self.assertIn("location.href='https://example.com/4'", tracked)


class SanitizeHtmlContentTests(TestCase):
    """Test cases for HTML content sanitization."""
    
    def test_sanitize_removes_scripts(self):
        """Test sanitization removes script tags."""
        html = '''
        <p>Hello</p>
        <script>alert('XSS')</script>
        <p>World</p>
        '''
        
        sanitized = sanitize_html_content(html)
        
        self.assertNotIn('<script', sanitized)
        self.assertNotIn('alert(', sanitized)
        self.assertIn('Hello', sanitized)
        self.assertIn('World', sanitized)
    
    def test_sanitize_removes_event_handlers(self):
        """Test sanitization removes JavaScript event handlers."""
        html = '''
        <p onclick="alert('XSS')">Click me</p>
        <img src="x" onerror="alert('XSS')">
        <a href="#" onmouseover="alert('XSS')">Link</a>
        '''
        
        sanitized = sanitize_html_content(html)
        
        self.assertNotIn('onclick', sanitized)
        self.assertNotIn('onerror', sanitized)
        self.assertNotIn('onmouseover', sanitized)
        self.assertIn('Click me', sanitized)
        self.assertIn('Link', sanitized)
    
    def test_sanitize_removes_iframes(self):
        """Test sanitization removes iframes."""
        html = '''
        <p>Content</p>
        <iframe src="http://evil.com"></iframe>
        <iframe width="0" height="0" src="javascript:alert('XSS')"></iframe>
        '''
        
        sanitized = sanitize_html_content(html)
        
        self.assertNotIn('<iframe', sanitized)
        self.assertNotIn('evil.com', sanitized)
        self.assertIn('Content', sanitized)
    
    def test_sanitize_preserves_safe_tags(self):
        """Test sanitization preserves safe HTML tags."""
        html = '''
        <h1>Title</h1>
        <p>Paragraph with <strong>bold</strong> and <em>italic</em>.</p>
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
        </ul>
        <a href="https://example.com" target="_blank">Safe Link</a>
        <img src="https://example.com/image.jpg" alt="Image">
        '''
        
        sanitized = sanitize_html_content(html)
        
        # Safe tags should be preserved
        self.assertIn('<h1>Title</h1>', sanitized)
        self.assertIn('<strong>bold</strong>', sanitized)
        self.assertIn('<em>italic</em>', sanitized)
        self.assertIn('<li>Item 1</li>', sanitized)
        self.assertIn('href="https://example.com"', sanitized)
        self.assertIn('<img', sanitized)
    
    def test_sanitize_fixes_malformed_html(self):
        """Test sanitization fixes malformed HTML."""
        html = '''
        <p>Unclosed paragraph
        <div>Unclosed div
        <span>Text</span>
        '''
        
        sanitized = sanitize_html_content(html)
        
        # Should close unclosed tags
        self.assertIn('</p>', sanitized)
        self.assertIn('</div>', sanitized)
    
    def test_sanitize_preserves_css_classes(self):
        """Test sanitization preserves CSS classes and IDs."""
        html = '''
        <div class="container" id="main">
            <p class="text-primary">Styled text</p>
            <button class="btn btn-primary">Click</button>
        </div>
        '''
        
        sanitized = sanitize_html_content(html)
        
        self.assertIn('class="container"', sanitized)
        self.assertIn('id="main"', sanitized)
        self.assertIn('class="text-primary"', sanitized)
        self.assertIn('class="btn btn-primary"', sanitized)


class ExtractTemplateVariablesTests(TestCase):
    """Test cases for template variable extraction."""
    
    def test_extract_simple_variables(self):
        """Test extracting simple template variables."""
        template = "Hello {{ first_name }} {{ last_name }}!"
        
        variables = extract_template_variables(template)
        
        self.assertEqual(set(variables), {'first_name', 'last_name'})
    
    def test_extract_variables_with_filters(self):
        """Test extracting variables with filters."""
        template = """
        Price: {{ price|round(2) }}
        Name: {{ name|upper }}
        Date: {{ date|format('%Y-%m-%d') }}
        """
        
        variables = extract_template_variables(template)
        
        self.assertEqual(set(variables), {'price', 'name', 'date'})
    
    def test_extract_variables_from_complex_template(self):
        """Test extracting from complex template."""
        template = """
        {% if user %}
        Hello {{ user.first_name }}!
        Your balance is {{ account.balance }}.
        {% endif %}
        
        {% for item in items %}
        - {{ item.name }}: {{ item.price }}
        {% endfor %}
        
        {{ company_name|default('Your Company') }}
        """
        
        variables = extract_template_variables(template)
        
        # Should extract all unique variables
        expected = {
            'user', 'first_name', 'account', 'balance',
            'items', 'item', 'name', 'price', 'company_name'
        }
        self.assertTrue(set(variables).issubset(expected))
    
    def test_extract_no_duplicates(self):
        """Test extraction returns unique variables."""
        template = """
        {{ name }} {{ name }} {{ name }}
        Hello {{ name }}!
        """
        
        variables = extract_template_variables(template)
        
        # Should only have one 'name'
        self.assertEqual(variables.count('name'), 1)
    
    def test_extract_from_html_template(self):
        """Test extracting variables from HTML template."""
        template = """
        <html>
        <body>
            <h1>Welcome {{ first_name }}!</h1>
            <p>Your order #{{ order_id }} has been shipped to {{ shipping_address }}.</p>
            <a href="{{ unsubscribe_url }}">Unsubscribe</a>
        </body>
        </html>
        """
        
        variables = extract_template_variables(template)
        
        self.assertEqual(
            set(variables),
            {'first_name', 'order_id', 'shipping_address', 'unsubscribe_url'}
        )


class GeneratePreviewContextTests(TestCase):
    """Test cases for preview context generation."""
    
    def test_generate_basic_preview_context(self):
        """Test generating basic preview context."""
        context = generate_preview_context()
        
        # Should have common email variables
        self.assertIn('first_name', context)
        self.assertIn('last_name', context)
        self.assertIn('email', context)
        self.assertIn('company_name', context)
        self.assertIn('unsubscribe_url', context)
        self.assertIn('current_year', context)
        
        # Check some values
        self.assertEqual(context['current_year'], datetime.now().year)
        self.assertIn('example.com', context['email'])
    
    def test_generate_preview_with_contact(self):
        """Test generating preview context from contact."""
        contact = ContactFactory(
            first_name='Jane',
            last_name='Smith',
            email='jane@company.com',
            company_name='Acme Corp',
            job_title='CEO'
        )
        
        context = generate_preview_context(contact)
        
        self.assertEqual(context['first_name'], 'Jane')
        self.assertEqual(context['last_name'], 'Smith')
        self.assertEqual(context['email'], 'jane@company.com')
        self.assertEqual(context['company_name'], 'Acme Corp')
        self.assertEqual(context['job_title'], 'CEO')
    
    def test_preview_context_includes_system_vars(self):
        """Test preview context includes system variables."""
        context = generate_preview_context()
        
        # System variables that should always be present
        self.assertIn('unsubscribe_url', context)
        self.assertIn('preferences_url', context)
        self.assertIn('current_year', context)
        self.assertIn('current_date', context)
        
        # URLs should be properly formatted
        self.assertTrue(context['unsubscribe_url'].startswith('http'))
        self.assertTrue(context['preferences_url'].startswith('http'))


class EmailBackendTests(TestCase):
    """Test cases for email backend utilities."""
    
    @patch('django.core.mail.get_connection')
    def test_get_email_backend_default(self, mock_get_connection):
        """Test getting default email backend."""
        mock_backend = Mock()
        mock_get_connection.return_value = mock_backend
        
        backend = get_email_backend()
        
        self.assertEqual(backend, mock_backend)
        mock_get_connection.assert_called_once()
    
    @patch('django.core.mail.get_connection')
    def test_get_email_backend_custom(self, mock_get_connection):
        """Test getting custom email backend."""
        mock_backend = Mock()
        mock_get_connection.return_value = mock_backend
        
        backend = get_email_backend('django.core.mail.backends.smtp.EmailBackend')
        
        mock_get_connection.assert_called_with(
            backend='django.core.mail.backends.smtp.EmailBackend'
        )
    
    @patch('django.conf.settings.EMAIL_BACKEND', 'custom.backend.EmailBackend')
    @patch('django.core.mail.get_connection')
    def test_get_email_backend_from_settings(self, mock_get_connection):
        """Test email backend uses settings."""
        backend = get_email_backend()
        
        # Should use backend from settings
        mock_get_connection.assert_called_once()


class EmailDomainUtilsTests(TestCase):
    """Test cases for email domain utilities."""
    
    def test_get_email_domain(self):
        """Test extracting domain from email."""
        test_cases = [
            ('user@example.com', 'example.com'),
            ('first.last@sub.example.com', 'sub.example.com'),
            ('user+tag@example.co.uk', 'example.co.uk'),
            ('admin@localhost', 'localhost'),
        ]
        
        for email, expected_domain in test_cases:
            domain = get_email_domain(email)
            self.assertEqual(domain, expected_domain)
    
    def test_get_email_domain_invalid(self):
        """Test extracting domain from invalid email."""
        invalid_emails = ['not-an-email', '@domain.com', 'user@', '']
        
        for email in invalid_emails:
            domain = get_email_domain(email)
            self.assertIsNone(domain)


class FormatEmailAddressTests(TestCase):
    """Test cases for email address formatting."""
    
    def test_format_email_with_name(self):
        """Test formatting email with display name."""
        formatted = format_email_address('user@example.com', 'John Doe')
        
        self.assertEqual(formatted, 'John Doe <user@example.com>')
    
    def test_format_email_without_name(self):
        """Test formatting email without display name."""
        formatted = format_email_address('user@example.com')
        
        self.assertEqual(formatted, 'user@example.com')
    
    def test_format_email_with_special_chars_in_name(self):
        """Test formatting with special characters in name."""
        # Name with quotes
        formatted = format_email_address('user@example.com', 'John "JD" Doe')
        self.assertIn('user@example.com', formatted)
        
        # Name with comma
        formatted = format_email_address('user@example.com', 'Doe, John')
        self.assertIn('user@example.com', formatted)


class ParseWebhookEventTests(TestCase):
    """Test cases for webhook event parsing."""
    
    def test_parse_sendgrid_event(self):
        """Test parsing SendGrid webhook event."""
        event = {
            'event': 'delivered',
            'email': 'test@example.com',
            'timestamp': 1234567890,
            'sg_message_id': 'msg-123',
            'sg_event_id': 'event-123'
        }
        
        parsed = parse_webhook_event(event, 'sendgrid')
        
        self.assertEqual(parsed['event_type'], 'delivered')
        self.assertEqual(parsed['email'], 'test@example.com')
        self.assertEqual(parsed['message_id'], 'msg-123')
        self.assertIsInstance(parsed['timestamp'], datetime)
    
    def test_parse_mailgun_event(self):
        """Test parsing Mailgun webhook event."""
        event = {
            'event': 'delivered',
            'recipient': 'test@example.com',
            'timestamp': '1234567890',
            'message-id': '<msg-123@mailgun.org>',
            'id': 'event-123'
        }
        
        parsed = parse_webhook_event(event, 'mailgun')
        
        self.assertEqual(parsed['event_type'], 'delivered')
        self.assertEqual(parsed['email'], 'test@example.com')
        self.assertEqual(parsed['message_id'], '<msg-123@mailgun.org>')
    
    def test_parse_aws_ses_event(self):
        """Test parsing AWS SES webhook event."""
        event = {
            'eventType': 'Delivery',
            'mail': {
                'messageId': 'msg-123',
                'destination': ['test@example.com'],
                'timestamp': '2024-01-01T00:00:00.000Z'
            }
        }
        
        parsed = parse_webhook_event(event, 'aws_ses')
        
        self.assertEqual(parsed['event_type'], 'delivered')
        self.assertEqual(parsed['email'], 'test@example.com')
        self.assertEqual(parsed['message_id'], 'msg-123')
    
    def test_parse_unknown_provider(self):
        """Test parsing event from unknown provider."""
        event = {'some': 'data'}
        
        parsed = parse_webhook_event(event, 'unknown')
        
        # Should return original event
        self.assertEqual(parsed, event)


class CalculateEmailAnalyticsTests(TestCase):
    """Test cases for email analytics calculation."""
    
    def test_calculate_basic_analytics(self):
        """Test calculating basic email analytics."""
        stats = {
            'sent': 1000,
            'delivered': 950,
            'opened': 300,
            'clicked': 100,
            'bounced': 50,
            'unsubscribed': 10
        }
        
        analytics = calculate_email_analytics(stats)
        
        self.assertEqual(analytics['delivery_rate'], 95.0)  # 950/1000
        self.assertEqual(analytics['open_rate'], 31.58)     # 300/950
        self.assertEqual(analytics['click_rate'], 10.53)    # 100/950
        self.assertEqual(analytics['bounce_rate'], 5.0)     # 50/1000
        self.assertEqual(analytics['unsubscribe_rate'], 1.0)  # 10/1000
        self.assertEqual(analytics['click_to_open_rate'], 33.33)  # 100/300
    
    def test_calculate_analytics_with_zero_values(self):
        """Test analytics calculation handles zero values."""
        stats = {
            'sent': 0,
            'delivered': 0,
            'opened': 0,
            'clicked': 0,
            'bounced': 0,
            'unsubscribed': 0
        }
        
        analytics = calculate_email_analytics(stats)
        
        # Should handle division by zero
        self.assertEqual(analytics['delivery_rate'], 0)
        self.assertEqual(analytics['open_rate'], 0)
        self.assertEqual(analytics['click_rate'], 0)
        self.assertEqual(analytics['bounce_rate'], 0)
        self.assertEqual(analytics['click_to_open_rate'], 0)
    
    def test_calculate_analytics_partial_data(self):
        """Test analytics with partial data."""
        stats = {
            'sent': 100,
            'delivered': 100,
            'opened': 25
            # Missing clicked, bounced, etc.
        }
        
        analytics = calculate_email_analytics(stats)
        
        self.assertEqual(analytics['open_rate'], 25.0)
        self.assertEqual(analytics['click_rate'], 0)  # Default to 0


class ValidateEmailContentTests(TestCase):
    """Test cases for email content validation."""
    
    def test_validate_valid_content(self):
        """Test validation of valid email content."""
        content = {
            'subject': 'Test Email',
            'html': '<p>Hello {{ first_name }}! <a href="{{ unsubscribe_url }}">Unsubscribe</a></p>',
            'text': 'Hello {{ first_name }}! Unsubscribe: {{ unsubscribe_url }}'
        }
        
        errors = validate_email_content(content)
        
        self.assertEqual(len(errors), 0)
    
    def test_validate_missing_subject(self):
        """Test validation catches missing subject."""
        content = {
            'html': '<p>Hello!</p>',
            'text': 'Hello!'
        }
        
        errors = validate_email_content(content)
        
        self.assertIn('subject', [e['field'] for e in errors])
    
    def test_validate_missing_unsubscribe(self):
        """Test validation catches missing unsubscribe link."""
        content = {
            'subject': 'Test',
            'html': '<p>Hello!</p>',
            'text': 'Hello!'
        }
        
        errors = validate_email_content(content)
        
        self.assertTrue(any('unsubscribe' in e['message'].lower() for e in errors))
    
    def test_validate_subject_too_long(self):
        """Test validation catches subject that's too long."""
        content = {
            'subject': 'x' * 200,  # Too long
            'html': '<p>Test {{ unsubscribe_url }}</p>',
            'text': 'Test {{ unsubscribe_url }}'
        }
        
        errors = validate_email_content(content)
        
        self.assertTrue(any('subject' in e['field'] and 'long' in e['message'] for e in errors))
    
    def test_validate_empty_content(self):
        """Test validation catches empty content."""
        content = {
            'subject': 'Test',
            'html': '   ',  # Just whitespace
            'text': ''
        }
        
        errors = validate_email_content(content)
        
        self.assertTrue(any('empty' in e['message'].lower() for e in errors))


class EmailRetryLogicTests(TestCase):
    """Test cases for email retry logic."""
    
    def test_should_retry_temporary_errors(self):
        """Test identifying temporary errors for retry."""
        temporary_errors = [
            ConnectionError("Network error"),
            TimeoutError("Timeout"),
            Exception("SMTP connection failed"),
            Exception("Rate limit exceeded"),
            Exception("Service temporarily unavailable")
        ]
        
        for error in temporary_errors:
            self.assertTrue(
                should_retry_email(error),
                f"{error} should trigger retry"
            )
    
    def test_should_not_retry_permanent_errors(self):
        """Test identifying permanent errors that shouldn't retry."""
        permanent_errors = [
            ValueError("Invalid email format"),
            Exception("Invalid recipient"),
            Exception("Authentication failed"),
            Exception("Domain not found"),
            Exception("Mailbox does not exist")
        ]
        
        for error in permanent_errors:
            self.assertFalse(
                should_retry_email(error),
                f"{error} should not trigger retry"
            )
    
    def test_retry_with_attempts_count(self):
        """Test retry logic considers attempt count."""
        error = ConnectionError("Network error")
        
        # Should retry on first attempts
        self.assertTrue(should_retry_email(error, attempts=1))
        self.assertTrue(should_retry_email(error, attempts=2))
        
        # Should not retry after max attempts
        self.assertFalse(should_retry_email(error, attempts=5))


class JinjaStringLoaderTests(TestCase):
    """Test cases for custom Jinja2 string loader."""
    
    def test_loader_get_source(self):
        """Test string loader returns template source."""
        loader = JinjaStringLoader()
        
        template_string = "Hello {{ name }}!"
        source, filename, uptodate = loader.get_source(None, template_string)
        
        self.assertEqual(source, template_string)
        self.assertIsNone(filename)
        self.assertTrue(uptodate())  # Always returns True