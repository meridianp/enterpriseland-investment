"""
Management command to create standard assessment templates.

Creates the CASA standard partner and scheme assessment templates
with all predefined metrics and scoring criteria.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Group
from assessments.standard_templates import TemplateManager


class Command(BaseCommand):
    help = 'Create standard CASA assessment templates'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--group-name',
            type=str,
            help='Name of the group to create templates for (required)',
            required=True
        )
        
        parser.add_argument(
            '--partner-only',
            action='store_true',
            help='Create only the partner assessment template'
        )
        
        parser.add_argument(
            '--scheme-only',
            action='store_true',
            help='Create only the scheme assessment template'
        )
        
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing templates with the same name'
        )
    
    def handle(self, *args, **options):
        group_name = options['group_name']
        partner_only = options['partner_only']
        scheme_only = options['scheme_only']
        overwrite = options['overwrite']
        
        try:
            group = Group.objects.get(name=group_name)
        except Group.DoesNotExist:
            raise CommandError(f'Group "{group_name}" does not exist')
        
        if partner_only and scheme_only:
            raise CommandError('Cannot specify both --partner-only and --scheme-only')
        
        created_templates = []
        
        try:
            with transaction.atomic():
                # Create partner template
                if not scheme_only:
                    partner_template_name = 'CASA Standard Partner Assessment'
                    
                    # Check if template exists
                    existing_partner = group.assessment_templates.filter(
                        template_name=partner_template_name
                    ).first()
                    
                    if existing_partner:
                        if overwrite:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'Deleting existing partner template: {existing_partner}'
                                )
                            )
                            existing_partner.delete()
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'Partner template already exists: {existing_partner}. '
                                    f'Use --overwrite to replace it.'
                                )
                            )
                    
                    if not existing_partner or overwrite:
                        self.stdout.write('Creating standard partner assessment template...')
                        partner_template = TemplateManager.create_standard_partner_template(group)
                        created_templates.append(partner_template)
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ Created partner template: {partner_template}'
                            )
                        )
                        
                        # Show template summary
                        summary = TemplateManager.get_template_summary(partner_template)
                        self.stdout.write(f'  • Total metrics: {summary["total_metrics"]}')
                        self.stdout.write(f'  • Max possible score: {summary["max_possible_score"]}')
                        self.stdout.write('  • Category breakdown:')
                        for cat_code, cat_data in summary['category_breakdown'].items():
                            self.stdout.write(
                                f'    - {cat_data["name"]}: {cat_data["metric_count"]} metrics '
                                f'({cat_data["weight_percentage"]}% of total weight)'
                            )
                
                # Create scheme template
                if not partner_only:
                    scheme_template_name = 'CASA Standard Scheme Assessment'
                    
                    # Check if template exists
                    existing_scheme = group.assessment_templates.filter(
                        template_name=scheme_template_name
                    ).first()
                    
                    if existing_scheme:
                        if overwrite:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'Deleting existing scheme template: {existing_scheme}'
                                )
                            )
                            existing_scheme.delete()
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'Scheme template already exists: {existing_scheme}. '
                                    f'Use --overwrite to replace it.'
                                )
                            )
                    
                    if not existing_scheme or overwrite:
                        self.stdout.write('Creating standard scheme assessment template...')
                        scheme_template = TemplateManager.create_standard_scheme_template(group)
                        created_templates.append(scheme_template)
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ Created scheme template: {scheme_template}'
                            )
                        )
                        
                        # Show template summary
                        summary = TemplateManager.get_template_summary(scheme_template)
                        self.stdout.write(f'  • Total metrics: {summary["total_metrics"]}')
                        self.stdout.write(f'  • Max possible score: {summary["max_possible_score"]}')
                        self.stdout.write('  • Category breakdown:')
                        for cat_code, cat_data in summary['category_breakdown'].items():
                            self.stdout.write(
                                f'    - {cat_data["name"]}: {cat_data["metric_count"]} metrics '
                                f'({cat_data["weight_percentage"]}% of total weight)'
                            )
                
                if created_templates:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'\n✓ Successfully created {len(created_templates)} template(s) '
                            f'for group "{group_name}"'
                        )
                    )
                    
                    self.stdout.write('\nDecision Thresholds:')
                    self.stdout.write('  • Premium/Priority: > 165 points')
                    self.stdout.write('  • Acceptable: 125-165 points')
                    self.stdout.write('  • Reject: < 125 points')
                    
                else:
                    self.stdout.write(
                        self.style.WARNING('No templates were created.')
                    )
        
        except Exception as e:
            raise CommandError(f'Error creating templates: {str(e)}')