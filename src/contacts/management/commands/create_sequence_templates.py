"""
Management command to create demo outreach sequence templates.

This command creates sample sequence templates for common use cases.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import User, Group
from contacts.models_outreach import SequenceTemplate


class Command(BaseCommand):
    help = 'Create demo outreach sequence templates'
    
    def handle(self, *args, **options):
        self.stdout.write('Creating demo sequence templates...')
        
        with transaction.atomic():
            # Get or create admin user and group
            admin_group, _ = Group.objects.get_or_create(name='admin_group')
            admin_user = User.objects.filter(is_superuser=True).first()
            
            if not admin_user:
                self.stdout.write(self.style.WARNING(
                    'No superuser found. Creating templates without user assignment.'
                ))
            
            # Create templates
            templates = [
                self._get_cold_outreach_template(),
                self._get_lead_nurture_template(),
                self._get_follow_up_template(),
                self._get_re_engagement_template(),
                self._get_event_invite_template(),
            ]
            
            created_count = 0
            for template_data in templates:
                template, created = SequenceTemplate.objects.get_or_create(
                    name=template_data['name'],
                    group=admin_group,
                    defaults={
                        **template_data,
                        'created_by': admin_user,
                        'is_public': True
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Created template: {template.name}')
                    )
                else:
                    self.stdout.write(
                        f'Template already exists: {template.name}'
                    )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created {created_count} sequence templates'
                )
            )
    
    def _get_cold_outreach_template(self):
        """Get cold outreach sequence template."""
        return {
            'name': 'Cold Outreach - Investment Opportunity',
            'description': 'Multi-touch sequence for reaching out to potential investment targets',
            'category': SequenceTemplate.Category.COLD_OUTREACH,
            'configuration': {
                'name': 'Cold Outreach - {Company Name}',
                'description': 'Reach out to potential investment target with personalized messaging',
                'trigger_type': 'manual',
                'skip_weekends': True,
                'timezone_optimized': True,
                'optimal_send_hour': 10,
                'exit_on_reply': True,
                'exit_on_click': False,
                'exit_on_conversion': True,
                'exit_tags': ['not-interested', 'competitor'],
                'goal_description': 'Schedule introductory meeting to discuss investment opportunity',
                'steps': [
                    {
                        'step_type': 'email',
                        'order': 0,
                        'name': 'Initial Outreach',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'day_type': 'business',
                        'email_template': 'investment-outreach',
                        'email_subject': 'Investment Opportunity with {{partner_name}}'
                    },
                    {
                        'step_type': 'wait',
                        'order': 1,
                        'name': 'Wait 3 days',
                        'delay_days': 3,
                        'delay_hours': 0,
                        'day_type': 'business'
                    },
                    {
                        'step_type': 'email',
                        'order': 2,
                        'name': 'First Follow-up',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'day_type': 'business',
                        'email_template': 'general-follow-up',
                        'email_subject': 'Re: Investment Opportunity with {{partner_name}}'
                    },
                    {
                        'step_type': 'wait',
                        'order': 3,
                        'name': 'Wait 5 days',
                        'delay_days': 5,
                        'delay_hours': 0,
                        'day_type': 'business'
                    },
                    {
                        'step_type': 'condition',
                        'order': 4,
                        'name': 'Check if opened',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'condition_type': 'has_opened',
                        'condition_config': {}
                    },
                    {
                        'step_type': 'email',
                        'order': 5,
                        'name': 'Final Follow-up',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'day_type': 'business',
                        'email_template': 'general-follow-up',
                        'email_subject': 'Final check-in regarding investment opportunity'
                    }
                ]
            }
        }
    
    def _get_lead_nurture_template(self):
        """Get lead nurturing sequence template."""
        return {
            'name': 'Lead Nurture - Educational Series',
            'description': 'Educational content series to nurture qualified leads',
            'category': SequenceTemplate.Category.LEAD_NURTURE,
            'configuration': {
                'name': 'Educational Series - {Segment}',
                'description': 'Nurture leads with valuable content about our investment approach',
                'trigger_type': 'lead_scored',
                'trigger_conditions': {
                    'min_score': 70,
                    'max_score': 90
                },
                'skip_weekends': True,
                'timezone_optimized': True,
                'optimal_send_hour': 9,
                'exit_on_reply': True,
                'exit_on_conversion': True,
                'exit_tags': ['customer', 'not-qualified'],
                'goal_description': 'Move lead to opportunity stage',
                'steps': [
                    {
                        'step_type': 'email',
                        'order': 0,
                        'name': 'Welcome to Educational Series',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'day_type': 'business',
                        'email_template': 'newsletter',
                        'email_subject': 'Welcome! Your guide to impact investing'
                    },
                    {
                        'step_type': 'wait',
                        'order': 1,
                        'name': 'Wait 7 days',
                        'delay_days': 7,
                        'delay_hours': 0,
                        'day_type': 'calendar'
                    },
                    {
                        'step_type': 'email',
                        'order': 2,
                        'name': 'Case Study #1',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'day_type': 'business',
                        'email_template': 'newsletter',
                        'email_subject': 'Case Study: How we helped Company X achieve 3x growth'
                    },
                    {
                        'step_type': 'action',
                        'order': 3,
                        'name': 'Increase lead score',
                        'delay_days': 0,
                        'delay_hours': 1,
                        'action_type': 'update_score',
                        'action_config': {
                            'delta': 5
                        }
                    },
                    {
                        'step_type': 'wait',
                        'order': 4,
                        'name': 'Wait 7 days',
                        'delay_days': 7,
                        'delay_hours': 0,
                        'day_type': 'calendar'
                    },
                    {
                        'step_type': 'email',
                        'order': 5,
                        'name': 'Investment Criteria Guide',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'day_type': 'business',
                        'email_template': 'newsletter',
                        'email_subject': 'Our Investment Criteria: What we look for'
                    },
                    {
                        'step_type': 'wait',
                        'order': 6,
                        'name': 'Wait 5 days',
                        'delay_days': 5,
                        'delay_hours': 0,
                        'day_type': 'business'
                    },
                    {
                        'step_type': 'email',
                        'order': 7,
                        'name': 'Schedule a Call',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'day_type': 'business',
                        'email_template': 'general-follow-up',
                        'email_subject': "Let's discuss your growth plans"
                    }
                ]
            }
        }
    
    def _get_follow_up_template(self):
        """Get meeting follow-up sequence template."""
        return {
            'name': 'Post-Meeting Follow-up',
            'description': 'Follow-up sequence after initial meetings',
            'category': SequenceTemplate.Category.FOLLOW_UP,
            'configuration': {
                'name': 'Follow-up - {Contact Name}',
                'description': 'Follow up after meeting to move deal forward',
                'trigger_type': 'manual',
                'skip_weekends': False,
                'timezone_optimized': True,
                'optimal_send_hour': 10,
                'exit_on_reply': True,
                'exit_on_conversion': True,
                'goal_description': 'Move to next stage of investment process',
                'steps': [
                    {
                        'step_type': 'wait',
                        'order': 0,
                        'name': 'Wait 1 day',
                        'delay_days': 1,
                        'delay_hours': 0,
                        'day_type': 'calendar'
                    },
                    {
                        'step_type': 'email',
                        'order': 1,
                        'name': 'Thank you email',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'day_type': 'business',
                        'email_template': 'general-follow-up',
                        'email_subject': 'Thank you for meeting - next steps'
                    },
                    {
                        'step_type': 'action',
                        'order': 2,
                        'name': 'Create follow-up task',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'action_type': 'create_task',
                        'action_config': {
                            'subject': 'Send materials discussed in meeting',
                            'due_days': 2
                        }
                    },
                    {
                        'step_type': 'wait',
                        'order': 3,
                        'name': 'Wait 5 days',
                        'delay_days': 5,
                        'delay_hours': 0,
                        'day_type': 'business'
                    },
                    {
                        'step_type': 'email',
                        'order': 4,
                        'name': 'Check-in email',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'day_type': 'business',
                        'email_template': 'general-follow-up',
                        'email_subject': 'Following up on our discussion'
                    }
                ]
            }
        }
    
    def _get_re_engagement_template(self):
        """Get re-engagement sequence template."""
        return {
            'name': 'Re-engagement Campaign',
            'description': 'Win back inactive or cold leads',
            'category': SequenceTemplate.Category.RE_ENGAGEMENT,
            'configuration': {
                'name': 'Re-engagement - {Segment}',
                'description': 'Re-engage leads that have gone cold',
                'trigger_type': 'manual',
                'skip_weekends': True,
                'timezone_optimized': True,
                'optimal_send_hour': 11,
                'exit_on_reply': True,
                'exit_on_click': True,
                'exit_tags': ['re-engaged', 'not-interested'],
                'goal_description': 'Re-engage inactive leads',
                'steps': [
                    {
                        'step_type': 'email',
                        'order': 0,
                        'name': 'We miss you',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'day_type': 'business',
                        'email_template': 'general-follow-up',
                        'email_subject': "It's been a while - here's what you've missed"
                    },
                    {
                        'step_type': 'wait',
                        'order': 1,
                        'name': 'Wait 7 days',
                        'delay_days': 7,
                        'delay_hours': 0,
                        'day_type': 'calendar'
                    },
                    {
                        'step_type': 'email',
                        'order': 2,
                        'name': 'Special offer',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'day_type': 'business',
                        'email_template': 'newsletter',
                        'email_subject': 'Exclusive: Priority access to our next fund'
                    },
                    {
                        'step_type': 'wait',
                        'order': 3,
                        'name': 'Wait 10 days',
                        'delay_days': 10,
                        'delay_hours': 0,
                        'day_type': 'calendar'
                    },
                    {
                        'step_type': 'email',
                        'order': 4,
                        'name': 'Last chance',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'day_type': 'business',
                        'email_template': 'general-follow-up',
                        'email_subject': 'Should we stay in touch?'
                    }
                ]
            }
        }
    
    def _get_event_invite_template(self):
        """Get event invitation sequence template."""
        return {
            'name': 'Event Invitation Series',
            'description': 'Multi-touch event invitation and reminder sequence',
            'category': SequenceTemplate.Category.EVENT_INVITE,
            'configuration': {
                'name': 'Event Invite - {Event Name}',
                'description': 'Invite contacts to webinar or conference',
                'trigger_type': 'tag_added',
                'trigger_conditions': {
                    'tag': 'event-invite'
                },
                'skip_weekends': True,
                'timezone_optimized': True,
                'optimal_send_hour': 10,
                'exit_on_conversion': True,
                'exit_tags': ['event-registered'],
                'conversion_url_pattern': '.*/event-registration/success.*',
                'goal_description': 'Get registrations for event',
                'steps': [
                    {
                        'step_type': 'email',
                        'order': 0,
                        'name': 'Save the date',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'day_type': 'business',
                        'email_template': 'newsletter',
                        'email_subject': 'Save the Date: {{event_name}}'
                    },
                    {
                        'step_type': 'wait',
                        'order': 1,
                        'name': 'Wait 7 days',
                        'delay_days': 7,
                        'delay_hours': 0,
                        'day_type': 'calendar'
                    },
                    {
                        'step_type': 'email',
                        'order': 2,
                        'name': 'Official invitation',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'day_type': 'business',
                        'email_template': 'partner-invitation',
                        'email_subject': "You're invited: {{event_name}}"
                    },
                    {
                        'step_type': 'wait',
                        'order': 3,
                        'name': 'Wait 5 days',
                        'delay_days': 5,
                        'delay_hours': 0,
                        'day_type': 'business'
                    },
                    {
                        'step_type': 'ab_test',
                        'order': 4,
                        'name': 'A/B Test Reminder',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'variant_group': 'reminder_test'
                    },
                    {
                        'step_type': 'email',
                        'order': 5,
                        'name': 'Reminder A - Urgency',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'day_type': 'business',
                        'email_template': 'general-follow-up',
                        'email_subject': 'Only 10 spots left for {{event_name}}',
                        'is_variant': True,
                        'variant_group': 'reminder_test',
                        'variant_percentage': 50
                    },
                    {
                        'step_type': 'email',
                        'order': 5,
                        'name': 'Reminder B - Value',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'day_type': 'business',
                        'email_template': 'general-follow-up',
                        'email_subject': "Don't miss these speakers at {{event_name}}",
                        'is_variant': True,
                        'variant_group': 'reminder_test',
                        'variant_percentage': 50
                    },
                    {
                        'step_type': 'wait',
                        'order': 6,
                        'name': 'Wait 3 days',
                        'delay_days': 3,
                        'delay_hours': 0,
                        'day_type': 'business'
                    },
                    {
                        'step_type': 'email',
                        'order': 7,
                        'name': 'Last chance',
                        'delay_days': 0,
                        'delay_hours': 0,
                        'day_type': 'business',
                        'email_template': 'general-follow-up',
                        'email_subject': 'Final reminder: {{event_name}} is tomorrow'
                    }
                ]
            }
        }
    }