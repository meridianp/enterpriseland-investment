# Generated migration for email campaign models

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0001_initial'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailTemplate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(help_text='Internal template name', max_length=200)),
                ('template_type', models.CharField(choices=[('marketing', 'Marketing'), ('transactional', 'Transactional'), ('newsletter', 'Newsletter'), ('announcement', 'Announcement'), ('follow_up', 'Follow-up')], default='marketing', max_length=20)),
                ('subject', models.CharField(help_text='Email subject line. Supports Jinja2 variables like {{ first_name }}', max_length=200)),
                ('preheader', models.CharField(blank=True, help_text='Preview text shown in email clients', max_length=200)),
                ('html_content', models.TextField(help_text='HTML email content with Jinja2 templating')),
                ('text_content', models.TextField(help_text='Plain text version of the email')),
                ('from_name', models.CharField(default='EnterpriseLand', max_length=100)),
                ('from_email', models.EmailField(default='noreply@enterpriseland.com', max_length=254)),
                ('reply_to_email', models.EmailField(blank=True, max_length=254)),
                ('available_variables', models.JSONField(blank=True, default=list, help_text='List of available template variables')),
                ('is_active', models.BooleanField(default=True)),
                ('is_tested', models.BooleanField(default=False)),
                ('times_used', models.PositiveIntegerField(default=0)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_email_templates', to='accounts.user')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_templates', to='accounts.group')),
            ],
            options={
                'verbose_name': 'Email Template',
                'verbose_name_plural': 'Email Templates',
                'db_table': 'email_templates',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='EmailCampaign',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('scheduled', 'Scheduled'), ('sending', 'Sending'), ('sent', 'Sent'), ('paused', 'Paused'), ('cancelled', 'Cancelled')], default='draft', max_length=20)),
                ('sending_strategy', models.CharField(choices=[('immediate', 'Send Immediately'), ('scheduled', 'Scheduled'), ('drip', 'Drip Campaign'), ('timezone', 'Timezone Optimized')], default='immediate', max_length=20)),
                ('scheduled_at', models.DateTimeField(blank=True, null=True)),
                ('send_rate_per_hour', models.PositiveIntegerField(default=1000, help_text='Maximum emails to send per hour')),
                ('track_opens', models.BooleanField(default=True)),
                ('track_clicks', models.BooleanField(default=True)),
                ('include_unsubscribe_link', models.BooleanField(default=True)),
                ('is_ab_test', models.BooleanField(default=False)),
                ('ab_test_percentage', models.PositiveSmallIntegerField(default=10, help_text='Percentage of recipients for A/B test')),
                ('total_recipients', models.PositiveIntegerField(default=0)),
                ('emails_sent', models.PositiveIntegerField(default=0)),
                ('emails_delivered', models.PositiveIntegerField(default=0)),
                ('emails_opened', models.PositiveIntegerField(default=0)),
                ('emails_clicked', models.PositiveIntegerField(default=0)),
                ('emails_bounced', models.PositiveIntegerField(default=0)),
                ('emails_unsubscribed', models.PositiveIntegerField(default=0)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_campaigns', to='accounts.user')),
                ('contact_lists', models.ManyToManyField(blank=True, related_name='email_campaigns', to='contacts.contactlist')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_campaigns', to='accounts.user')),
                ('excluded_contacts', models.ManyToManyField(blank=True, related_name='excluded_from_campaigns', to='contacts.contact')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_campaigns', to='accounts.group')),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='campaigns', to='contacts.emailtemplate')),
                ('variant_templates', models.ManyToManyField(blank=True, related_name='ab_test_campaigns', to='contacts.emailtemplate')),
            ],
            options={
                'verbose_name': 'Email Campaign',
                'verbose_name_plural': 'Email Campaigns',
                'db_table': 'email_campaigns',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='EmailMessage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('subject', models.CharField(max_length=200)),
                ('from_email', models.EmailField(max_length=254)),
                ('to_email', models.EmailField(max_length=254)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('queued', 'Queued'), ('sent', 'Sent'), ('delivered', 'Delivered'), ('opened', 'Opened'), ('clicked', 'Clicked'), ('bounced', 'Bounced'), ('failed', 'Failed'), ('unsubscribed', 'Unsubscribed'), ('complained', 'Complained')], default='pending', max_length=20)),
                ('message_id', models.CharField(blank=True, help_text='Email service provider message ID', max_length=255)),
                ('queued_at', models.DateTimeField(blank=True, null=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('first_opened_at', models.DateTimeField(blank=True, null=True)),
                ('last_opened_at', models.DateTimeField(blank=True, null=True)),
                ('open_count', models.PositiveIntegerField(default=0)),
                ('first_clicked_at', models.DateTimeField(blank=True, null=True)),
                ('last_clicked_at', models.DateTimeField(blank=True, null=True)),
                ('click_count', models.PositiveIntegerField(default=0)),
                ('bounce_type', models.CharField(blank=True, max_length=50)),
                ('bounce_reason', models.TextField(blank=True)),
                ('failed_reason', models.TextField(blank=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='contacts.emailcampaign')),
                ('contact', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_messages', to='contacts.contact')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_messages', to='accounts.group')),
                ('template_used', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='contacts.emailtemplate')),
            ],
            options={
                'verbose_name': 'Email Message',
                'verbose_name_plural': 'Email Messages',
                'db_table': 'email_messages',
                'ordering': ['-created_at'],
                'unique_together': {('campaign', 'contact')},
            },
        ),
        migrations.CreateModel(
            name='EmailEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event_type', models.CharField(choices=[('queued', 'Queued'), ('sent', 'Sent'), ('delivered', 'Delivered'), ('opened', 'Opened'), ('clicked', 'Clicked'), ('bounced', 'Bounced'), ('failed', 'Failed'), ('unsubscribed', 'Unsubscribed'), ('complained', 'Spam Complaint')], max_length=20)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional event-specific data')),
                ('link_url', models.URLField(blank=True)),
                ('link_text', models.CharField(blank=True, max_length=200)),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='contacts.emailmessage')),
            ],
            options={
                'verbose_name': 'Email Event',
                'verbose_name_plural': 'Email Events',
                'db_table': 'email_events',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='emailtemplate',
            index=models.Index(fields=['group', 'template_type', 'is_active'], name='email_templ_group_i_6a7d0b_idx'),
        ),
        migrations.AddIndex(
            model_name='emailtemplate',
            index=models.Index(fields=['group', 'created_at'], name='email_templ_group_i_f3d8a3_idx'),
        ),
        migrations.AddIndex(
            model_name='emailcampaign',
            index=models.Index(fields=['group', 'status', 'scheduled_at'], name='email_campa_group_i_4c6f9e_idx'),
        ),
        migrations.AddIndex(
            model_name='emailcampaign',
            index=models.Index(fields=['group', 'created_at'], name='email_campa_group_i_8e6a7b_idx'),
        ),
        migrations.AddIndex(
            model_name='emailmessage',
            index=models.Index(fields=['group', 'campaign', 'status'], name='email_messa_group_i_9d2c8f_idx'),
        ),
        migrations.AddIndex(
            model_name='emailmessage',
            index=models.Index(fields=['group', 'contact', 'sent_at'], name='email_messa_group_i_3e7f2a_idx'),
        ),
        migrations.AddIndex(
            model_name='emailmessage',
            index=models.Index(fields=['group', 'status', 'created_at'], name='email_messa_group_i_7b9c1e_idx'),
        ),
        migrations.AddIndex(
            model_name='emailevent',
            index=models.Index(fields=['message', 'event_type'], name='email_event_message_5f8d3b_idx'),
        ),
        migrations.AddIndex(
            model_name='emailevent',
            index=models.Index(fields=['timestamp'], name='email_event_timesta_2c9f7e_idx'),
        ),
    ]