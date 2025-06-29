"""
Management command to create default email templates with responsive design.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from contacts.models import EmailTemplate
from accounts.models import Group


class Command(BaseCommand):
    help = 'Creates default email templates with responsive design'

    def add_arguments(self, parser):
        parser.add_argument(
            '--group',
            type=str,
            help='Specific group name to create templates for (default: all groups)'
        )

    def handle(self, *args, **options):
        group_name = options.get('group')
        
        if group_name:
            groups = Group.objects.filter(name=group_name)
            if not groups.exists():
                self.stdout.write(self.style.ERROR(f'Group "{group_name}" not found'))
                return
        else:
            groups = Group.objects.all()

        for group in groups:
            self.stdout.write(f'Creating email templates for group: {group.name}')
            self._create_templates_for_group(group)
            
        self.stdout.write(self.style.SUCCESS('Successfully created email templates'))

    @transaction.atomic
    def _create_templates_for_group(self, group):
        """Create all default templates for a specific group."""
        templates = [
            self._get_welcome_template(),
            self._get_password_reset_template(),
            self._get_lead_notification_template(),
            self._get_assessment_update_template(),
            self._get_partner_invitation_template(),
            self._get_newsletter_template(),
            self._get_follow_up_template(),
        ]
        
        for template_data in templates:
            # Check if template already exists
            if EmailTemplate.objects.filter(
                group=group,
                name=template_data['name']
            ).exists():
                self.stdout.write(f'  - Template "{template_data["name"]}" already exists, skipping')
                continue
            
            # Create template
            template = EmailTemplate.objects.create(
                group=group,
                **template_data
            )
            self.stdout.write(f'  - Created template: {template.name}')

    def _get_base_css(self):
        """Get base responsive CSS for all email templates."""
        return """
        /* Base Reset */
        body, table, td, a { -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }
        table, td { mso-table-lspace: 0pt; mso-table-rspace: 0pt; }
        img { -ms-interpolation-mode: bicubic; border: 0; outline: none; text-decoration: none; }
        
        /* Mobile Styles */
        @media only screen and (max-width: 600px) {
            .mobile-hide { display: none !important; }
            .mobile-center { text-align: center !important; }
            .container { width: 100% !important; max-width: 100% !important; }
            .responsive-table { width: 100% !important; }
            .padding { padding: 10px 5% 15px 5% !important; }
            .padding-meta { padding: 30px 5% 0px 5% !important; text-align: center; }
            .no-padding { padding: 0 !important; }
            .section-padding { padding: 50px 15px 50px 15px !important; }
            .mobile-button { width: 100% !important; }
        }
        
        /* Brand Colors */
        .brand-blue { color: #215788; }
        .brand-turquoise { color: #00B7B2; }
        .brand-charcoal { color: #3C3C3B; }
        .brand-sand { background-color: #F4F1E9; }
        .brand-green { color: #BED600; }
        .brand-orange { color: #E37222; }
        """

    def _get_email_wrapper(self, content, title="EnterpriseLand"):
        """Get responsive email wrapper HTML."""
        css = self._get_base_css()
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>{title}</title>
    <style type="text/css">
        {css}
    </style>
</head>
<body style="margin: 0; padding: 0; background-color: #f6f6f6;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%">
        <tr>
            <td align="center" style="padding: 40px 0 30px 0;">
                <table border="0" cellpadding="0" cellspacing="0" width="600" class="container" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td align="center" style="padding: 40px 20px 20px 20px;">
                            <h1 style="margin: 0; font-family: Arial, sans-serif; font-size: 32px; font-weight: bold; color: #215788;">EnterpriseLand</h1>
                        </td>
                    </tr>
                    <!-- Content -->
                    {content}
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 30px 30px 30px; background-color: #F4F1E9; border-radius: 0 0 8px 8px;">
                            <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                <tr>
                                    <td style="font-family: Arial, sans-serif; font-size: 12px; color: #666666; text-align: center;">
                                        © {{{{ current_year }}}} EnterpriseLand. All rights reserved.<br>
                                        <a href="{{{{ unsubscribe_url }}}}" style="color: #00B7B2; text-decoration: none;">Unsubscribe</a> | 
                                        <a href="{{{{ preferences_url }}}}" style="color: #00B7B2; text-decoration: none;">Email Preferences</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        """

    def _get_welcome_template(self):
        """Get welcome email template."""
        content = """
        <tr>
            <td class="padding" style="padding: 20px 30px 20px 30px;">
                <h2 style="margin: 0 0 20px 0; font-family: Arial, sans-serif; font-size: 24px; color: #3C3C3B;">Welcome to EnterpriseLand, {{ first_name }}!</h2>
                <p style="margin: 0 0 20px 0; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #3C3C3B;">
                    We're thrilled to have you join our investment intelligence platform. EnterpriseLand streamlines your entire investment lifecycle, from market discovery to partnership management.
                </p>
                <table border="0" cellspacing="0" cellpadding="0" style="margin: 30px 0;">
                    <tr>
                        <td align="center">
                            <a href="{{ login_url }}" style="display: inline-block; padding: 15px 30px; font-family: Arial, sans-serif; font-size: 16px; color: #ffffff; background-color: #215788; text-decoration: none; border-radius: 5px;" class="mobile-button">Get Started</a>
                        </td>
                    </tr>
                </table>
                <h3 style="margin: 30px 0 15px 0; font-family: Arial, sans-serif; font-size: 18px; color: #3C3C3B;">What you can do with EnterpriseLand:</h3>
                <ul style="margin: 0 0 20px 0; padding-left: 20px; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.8; color: #3C3C3B;">
                    <li>Discover investment opportunities through AI-powered market intelligence</li>
                    <li>Track and score leads with advanced analytics</li>
                    <li>Streamline due diligence with automated workflows</li>
                    <li>Manage partnerships and portfolio performance</li>
                </ul>
                <p style="margin: 20px 0 0 0; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #3C3C3B;">
                    If you have any questions, our support team is here to help at <a href="mailto:{{ support_email }}" style="color: #00B7B2; text-decoration: none;">{{ support_email }}</a>.
                </p>
            </td>
        </tr>
        """
        
        return {
            'name': 'Welcome Email',
            'slug': 'welcome-email',
            'template_type': EmailTemplate.TemplateType.TRANSACTIONAL,
            'subject': 'Welcome to EnterpriseLand, {{ first_name }}!',
            'preheader': 'Get started with your investment intelligence platform',
            'html_content': self._get_email_wrapper(content, "Welcome to EnterpriseLand"),
            'text_content': """Welcome to EnterpriseLand, {{ first_name }}!

We're thrilled to have you join our investment intelligence platform. EnterpriseLand streamlines your entire investment lifecycle, from market discovery to partnership management.

Get Started: {{ login_url }}

What you can do with EnterpriseLand:
- Discover investment opportunities through AI-powered market intelligence
- Track and score leads with advanced analytics
- Streamline due diligence with automated workflows
- Manage partnerships and portfolio performance

If you have any questions, our support team is here to help at {{ support_email }}.

Best regards,
The EnterpriseLand Team

© {{ current_year }} EnterpriseLand. All rights reserved.
Unsubscribe: {{ unsubscribe_url }}
Email Preferences: {{ preferences_url }}""",
            'available_variables': ['first_name', 'last_name', 'email', 'login_url', 'support_email'],
            'is_active': True,
            'is_tested': True
        }

    def _get_password_reset_template(self):
        """Get password reset email template."""
        content = """
        <tr>
            <td class="padding" style="padding: 20px 30px 20px 30px;">
                <h2 style="margin: 0 0 20px 0; font-family: Arial, sans-serif; font-size: 24px; color: #3C3C3B;">Password Reset Request</h2>
                <p style="margin: 0 0 20px 0; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #3C3C3B;">
                    Hi {{ first_name }},
                </p>
                <p style="margin: 0 0 20px 0; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #3C3C3B;">
                    We received a request to reset the password for your EnterpriseLand account. Click the button below to create a new password:
                </p>
                <table border="0" cellspacing="0" cellpadding="0" style="margin: 30px 0;">
                    <tr>
                        <td align="center">
                            <a href="{{ reset_url }}" style="display: inline-block; padding: 15px 30px; font-family: Arial, sans-serif; font-size: 16px; color: #ffffff; background-color: #215788; text-decoration: none; border-radius: 5px;" class="mobile-button">Reset Password</a>
                        </td>
                    </tr>
                </table>
                <p style="margin: 20px 0 0 0; font-family: Arial, sans-serif; font-size: 14px; line-height: 1.5; color: #666666;">
                    This link will expire in {{ expiry_hours }} hours. If you didn't request a password reset, you can safely ignore this email.
                </p>
                <p style="margin: 20px 0 0 0; font-family: Arial, sans-serif; font-size: 14px; line-height: 1.5; color: #666666;">
                    For security reasons, this link can only be used once.
                </p>
            </td>
        </tr>
        """
        
        return {
            'name': 'Password Reset',
            'slug': 'password-reset',
            'template_type': EmailTemplate.TemplateType.TRANSACTIONAL,
            'subject': 'Reset your EnterpriseLand password',
            'preheader': 'Reset your password to regain access to your account',
            'html_content': self._get_email_wrapper(content, "Password Reset"),
            'text_content': """Password Reset Request

Hi {{ first_name }},

We received a request to reset the password for your EnterpriseLand account.

Reset your password: {{ reset_url }}

This link will expire in {{ expiry_hours }} hours. If you didn't request a password reset, you can safely ignore this email.

For security reasons, this link can only be used once.

Best regards,
The EnterpriseLand Team

© {{ current_year }} EnterpriseLand. All rights reserved.""",
            'available_variables': ['first_name', 'reset_url', 'expiry_hours'],
            'is_active': True,
            'is_tested': True
        }

    def _get_lead_notification_template(self):
        """Get lead notification email template."""
        content = """
        <tr>
            <td class="padding" style="padding: 20px 30px 20px 30px;">
                <h2 style="margin: 0 0 20px 0; font-family: Arial, sans-serif; font-size: 24px; color: #3C3C3B;">New Lead Alert: {{ lead_company }}</h2>
                <div style="background-color: #F4F1E9; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                    <h3 style="margin: 0 0 10px 0; font-family: Arial, sans-serif; font-size: 18px; color: #215788;">Lead Score: {{ lead_score }}/100</h3>
                    <p style="margin: 0; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #3C3C3B;">
                        <strong>Company:</strong> {{ lead_company }}<br>
                        <strong>Contact:</strong> {{ contact_name }} ({{ contact_title }})<br>
                        <strong>Source:</strong> {{ lead_source }}<br>
                        <strong>Priority:</strong> <span style="color: {{ priority_color }};">{{ lead_priority }}</span>
                    </p>
                </div>
                <p style="margin: 0 0 20px 0; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #3C3C3B;">
                    A new lead has been identified that matches your investment criteria. This opportunity has been automatically scored based on your preferences.
                </p>
                <table border="0" cellspacing="0" cellpadding="0" style="margin: 30px 0;">
                    <tr>
                        <td align="center">
                            <a href="{{ lead_url }}" style="display: inline-block; padding: 15px 30px; font-family: Arial, sans-serif; font-size: 16px; color: #ffffff; background-color: #00B7B2; text-decoration: none; border-radius: 5px;" class="mobile-button">View Lead Details</a>
                        </td>
                    </tr>
                </table>
                {% if key_insights %}
                <h3 style="margin: 30px 0 15px 0; font-family: Arial, sans-serif; font-size: 18px; color: #3C3C3B;">Key Insights:</h3>
                <ul style="margin: 0 0 20px 0; padding-left: 20px; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.8; color: #3C3C3B;">
                    {% for insight in key_insights %}
                    <li>{{ insight }}</li>
                    {% endfor %}
                </ul>
                {% endif %}
            </td>
        </tr>
        """
        
        return {
            'name': 'Lead Notification',
            'slug': 'lead-notification',
            'template_type': EmailTemplate.TemplateType.TRANSACTIONAL,
            'subject': 'New Lead: {{ lead_company }} - Score {{ lead_score }}/100',
            'preheader': 'A new high-scoring lead has been identified',
            'html_content': self._get_email_wrapper(content, "New Lead Alert"),
            'text_content': """New Lead Alert: {{ lead_company }}

Lead Score: {{ lead_score }}/100

Company: {{ lead_company }}
Contact: {{ contact_name }} ({{ contact_title }})
Source: {{ lead_source }}
Priority: {{ lead_priority }}

A new lead has been identified that matches your investment criteria. This opportunity has been automatically scored based on your preferences.

View Lead Details: {{ lead_url }}

{% if key_insights %}
Key Insights:
{% for insight in key_insights %}
- {{ insight }}
{% endfor %}
{% endif %}

Best regards,
The EnterpriseLand Team

© {{ current_year }} EnterpriseLand. All rights reserved.""",
            'available_variables': ['lead_company', 'lead_score', 'contact_name', 'contact_title', 'lead_source', 'lead_priority', 'priority_color', 'lead_url', 'key_insights'],
            'is_active': True,
            'is_tested': True
        }

    def _get_assessment_update_template(self):
        """Get assessment status update email template."""
        content = """
        <tr>
            <td class="padding" style="padding: 20px 30px 20px 30px;">
                <h2 style="margin: 0 0 20px 0; font-family: Arial, sans-serif; font-size: 24px; color: #3C3C3B;">Assessment Update: {{ partner_name }}</h2>
                <div style="background-color: #F4F1E9; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                    <table border="0" cellpadding="0" cellspacing="0" width="100%">
                        <tr>
                            <td style="font-family: Arial, sans-serif; font-size: 16px; color: #3C3C3B;">
                                <strong>Status:</strong>
                            </td>
                            <td style="font-family: Arial, sans-serif; font-size: 16px; color: {{ status_color }}; text-align: right;">
                                <strong>{{ assessment_status }}</strong>
                            </td>
                        </tr>
                        <tr>
                            <td style="font-family: Arial, sans-serif; font-size: 16px; color: #3C3C3B; padding-top: 10px;">
                                <strong>Assessment Type:</strong>
                            </td>
                            <td style="font-family: Arial, sans-serif; font-size: 16px; color: #3C3C3B; text-align: right; padding-top: 10px;">
                                {{ assessment_type }}
                            </td>
                        </tr>
                        <tr>
                            <td style="font-family: Arial, sans-serif; font-size: 16px; color: #3C3C3B; padding-top: 10px;">
                                <strong>Updated By:</strong>
                            </td>
                            <td style="font-family: Arial, sans-serif; font-size: 16px; color: #3C3C3B; text-align: right; padding-top: 10px;">
                                {{ updated_by }}
                            </td>
                        </tr>
                    </table>
                </div>
                <p style="margin: 0 0 20px 0; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #3C3C3B;">
                    {{ status_message }}
                </p>
                <table border="0" cellspacing="0" cellpadding="0" style="margin: 30px 0;">
                    <tr>
                        <td align="center">
                            <a href="{{ assessment_url }}" style="display: inline-block; padding: 15px 30px; font-family: Arial, sans-serif; font-size: 16px; color: #ffffff; background-color: #215788; text-decoration: none; border-radius: 5px;" class="mobile-button">View Assessment</a>
                        </td>
                    </tr>
                </table>
                {% if next_steps %}
                <h3 style="margin: 30px 0 15px 0; font-family: Arial, sans-serif; font-size: 18px; color: #3C3C3B;">Next Steps:</h3>
                <ul style="margin: 0 0 20px 0; padding-left: 20px; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.8; color: #3C3C3B;">
                    {% for step in next_steps %}
                    <li>{{ step }}</li>
                    {% endfor %}
                </ul>
                {% endif %}
            </td>
        </tr>
        """
        
        return {
            'name': 'Assessment Status Update',
            'slug': 'assessment-update',
            'template_type': EmailTemplate.TemplateType.TRANSACTIONAL,
            'subject': 'Assessment Update: {{ partner_name }} - {{ assessment_status }}',
            'preheader': 'Assessment status has been updated',
            'html_content': self._get_email_wrapper(content, "Assessment Update"),
            'text_content': """Assessment Update: {{ partner_name }}

Status: {{ assessment_status }}
Assessment Type: {{ assessment_type }}
Updated By: {{ updated_by }}

{{ status_message }}

View Assessment: {{ assessment_url }}

{% if next_steps %}
Next Steps:
{% for step in next_steps %}
- {{ step }}
{% endfor %}
{% endif %}

Best regards,
The EnterpriseLand Team

© {{ current_year }} EnterpriseLand. All rights reserved.""",
            'available_variables': ['partner_name', 'assessment_status', 'status_color', 'assessment_type', 'updated_by', 'status_message', 'assessment_url', 'next_steps'],
            'is_active': True,
            'is_tested': True
        }

    def _get_partner_invitation_template(self):
        """Get partner invitation email template."""
        content = """
        <tr>
            <td class="padding" style="padding: 20px 30px 20px 30px;">
                <h2 style="margin: 0 0 20px 0; font-family: Arial, sans-serif; font-size: 24px; color: #3C3C3B;">You're Invited to Join EnterpriseLand</h2>
                <p style="margin: 0 0 20px 0; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #3C3C3B;">
                    Hi {{ first_name }},
                </p>
                <p style="margin: 0 0 20px 0; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #3C3C3B;">
                    {{ inviter_name }} from {{ inviter_company }} has invited you to collaborate on EnterpriseLand, our investment intelligence platform.
                </p>
                <div style="background-color: #F4F1E9; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <p style="margin: 0; font-family: Arial, sans-serif; font-size: 16px; font-style: italic; color: #3C3C3B;">
                        "{{ invitation_message }}"
                    </p>
                    <p style="margin: 10px 0 0 0; font-family: Arial, sans-serif; font-size: 14px; color: #666666; text-align: right;">
                        — {{ inviter_name }}
                    </p>
                </div>
                <table border="0" cellspacing="0" cellpadding="0" style="margin: 30px 0;">
                    <tr>
                        <td align="center">
                            <a href="{{ invitation_url }}" style="display: inline-block; padding: 15px 30px; font-family: Arial, sans-serif; font-size: 16px; color: #ffffff; background-color: #00B7B2; text-decoration: none; border-radius: 5px;" class="mobile-button">Accept Invitation</a>
                        </td>
                    </tr>
                </table>
                <p style="margin: 20px 0 0 0; font-family: Arial, sans-serif; font-size: 14px; line-height: 1.5; color: #666666;">
                    This invitation will expire in {{ expiry_days }} days. If you have any questions, please contact {{ inviter_email }}.
                </p>
            </td>
        </tr>
        """
        
        return {
            'name': 'Partner Invitation',
            'slug': 'partner-invitation',
            'template_type': EmailTemplate.TemplateType.TRANSACTIONAL,
            'subject': '{{ inviter_name }} invited you to EnterpriseLand',
            'preheader': 'Join {{ inviter_company }} on EnterpriseLand',
            'html_content': self._get_email_wrapper(content, "Partner Invitation"),
            'text_content': """You're Invited to Join EnterpriseLand

Hi {{ first_name }},

{{ inviter_name }} from {{ inviter_company }} has invited you to collaborate on EnterpriseLand, our investment intelligence platform.

"{{ invitation_message }}"
— {{ inviter_name }}

Accept Invitation: {{ invitation_url }}

This invitation will expire in {{ expiry_days }} days. If you have any questions, please contact {{ inviter_email }}.

Best regards,
The EnterpriseLand Team

© {{ current_year }} EnterpriseLand. All rights reserved.""",
            'available_variables': ['first_name', 'inviter_name', 'inviter_company', 'inviter_email', 'invitation_message', 'invitation_url', 'expiry_days'],
            'is_active': True,
            'is_tested': True
        }

    def _get_newsletter_template(self):
        """Get newsletter email template."""
        content = """
        <tr>
            <td class="padding" style="padding: 20px 30px 20px 30px;">
                <h2 style="margin: 0 0 20px 0; font-family: Arial, sans-serif; font-size: 24px; color: #3C3C3B;">{{ newsletter_title }}</h2>
                <p style="margin: 0 0 20px 0; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #3C3C3B;">
                    {{ newsletter_intro }}
                </p>
                
                {% for section in sections %}
                <div style="margin: 30px 0; padding: 20px; background-color: #F4F1E9; border-radius: 8px;">
                    <h3 style="margin: 0 0 15px 0; font-family: Arial, sans-serif; font-size: 20px; color: #215788;">{{ section.title }}</h3>
                    <p style="margin: 0 0 15px 0; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #3C3C3B;">
                        {{ section.content }}
                    </p>
                    {% if section.cta_text %}
                    <a href="{{ section.cta_url }}" style="color: #00B7B2; text-decoration: none; font-weight: bold;">{{ section.cta_text }} →</a>
                    {% endif %}
                </div>
                {% endfor %}
                
                <div style="margin: 40px 0; padding: 20px; background-color: #215788; border-radius: 8px; text-align: center;">
                    <h3 style="margin: 0 0 10px 0; font-family: Arial, sans-serif; font-size: 20px; color: #ffffff;">{{ cta_section_title }}</h3>
                    <p style="margin: 0 0 20px 0; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #ffffff;">
                        {{ cta_section_text }}
                    </p>
                    <a href="{{ main_cta_url }}" style="display: inline-block; padding: 12px 25px; font-family: Arial, sans-serif; font-size: 16px; color: #215788; background-color: #ffffff; text-decoration: none; border-radius: 5px;" class="mobile-button">{{ main_cta_text }}</a>
                </div>
            </td>
        </tr>
        """
        
        return {
            'name': 'Monthly Newsletter',
            'slug': 'monthly-newsletter',
            'template_type': EmailTemplate.TemplateType.NEWSLETTER,
            'subject': '{{ newsletter_title }}',
            'preheader': '{{ newsletter_intro }}',
            'html_content': self._get_email_wrapper(content, "Newsletter"),
            'text_content': """{{ newsletter_title }}

{{ newsletter_intro }}

{% for section in sections %}
{{ section.title }}
{{ section.content }}
{% if section.cta_text %}
{{ section.cta_text }}: {{ section.cta_url }}
{% endif %}

{% endfor %}

{{ cta_section_title }}
{{ cta_section_text }}

{{ main_cta_text }}: {{ main_cta_url }}

Best regards,
The EnterpriseLand Team

© {{ current_year }} EnterpriseLand. All rights reserved.
Unsubscribe: {{ unsubscribe_url }}
Email Preferences: {{ preferences_url }}""",
            'available_variables': ['newsletter_title', 'newsletter_intro', 'sections', 'cta_section_title', 'cta_section_text', 'main_cta_text', 'main_cta_url'],
            'is_active': True,
            'is_tested': True
        }

    def _get_follow_up_template(self):
        """Get follow-up email template."""
        content = """
        <tr>
            <td class="padding" style="padding: 20px 30px 20px 30px;">
                <h2 style="margin: 0 0 20px 0; font-family: Arial, sans-serif; font-size: 24px; color: #3C3C3B;">Following up on {{ subject_line }}</h2>
                <p style="margin: 0 0 20px 0; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #3C3C3B;">
                    Hi {{ first_name }},
                </p>
                <p style="margin: 0 0 20px 0; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #3C3C3B;">
                    {{ follow_up_message }}
                </p>
                {% if reminder_points %}
                <div style="background-color: #F4F1E9; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin: 0 0 10px 0; font-family: Arial, sans-serif; font-size: 16px; color: #215788;">Quick Reminder:</h3>
                    <ul style="margin: 0; padding-left: 20px; font-family: Arial, sans-serif; font-size: 15px; line-height: 1.8; color: #3C3C3B;">
                        {% for point in reminder_points %}
                        <li>{{ point }}</li>
                        {% endfor %}
                    </ul>
                </div>
                {% endif %}
                <p style="margin: 20px 0; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #3C3C3B;">
                    {{ call_to_action_text }}
                </p>
                <table border="0" cellspacing="0" cellpadding="0" style="margin: 30px 0;">
                    <tr>
                        <td align="center">
                            <a href="{{ action_url }}" style="display: inline-block; padding: 15px 30px; font-family: Arial, sans-serif; font-size: 16px; color: #ffffff; background-color: #00B7B2; text-decoration: none; border-radius: 5px;" class="mobile-button">{{ action_button_text }}</a>
                        </td>
                    </tr>
                </table>
                <p style="margin: 20px 0 0 0; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #3C3C3B;">
                    {{ closing_message }}
                </p>
                <p style="margin: 10px 0 0 0; font-family: Arial, sans-serif; font-size: 16px; color: #3C3C3B;">
                    Best regards,<br>
                    {{ sender_name }}<br>
                    <span style="font-size: 14px; color: #666666;">{{ sender_title }}</span>
                </p>
            </td>
        </tr>
        """
        
        return {
            'name': 'General Follow-up',
            'slug': 'general-follow-up',
            'template_type': EmailTemplate.TemplateType.FOLLOW_UP,
            'subject': 'Following up: {{ subject_line }}',
            'preheader': '{{ follow_up_preview }}',
            'html_content': self._get_email_wrapper(content, "Follow-up"),
            'text_content': """Following up on {{ subject_line }}

Hi {{ first_name }},

{{ follow_up_message }}

{% if reminder_points %}
Quick Reminder:
{% for point in reminder_points %}
- {{ point }}
{% endfor %}
{% endif %}

{{ call_to_action_text }}

{{ action_button_text }}: {{ action_url }}

{{ closing_message }}

Best regards,
{{ sender_name }}
{{ sender_title }}

© {{ current_year }} EnterpriseLand. All rights reserved.""",
            'available_variables': ['first_name', 'subject_line', 'follow_up_preview', 'follow_up_message', 'reminder_points', 'call_to_action_text', 'action_url', 'action_button_text', 'closing_message', 'sender_name', 'sender_title'],
            'is_active': True,
            'is_tested': True
        }