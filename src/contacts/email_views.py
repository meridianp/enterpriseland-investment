"""
Email campaign ViewSets for the EnterpriseLand Due-Diligence Platform.

Provides comprehensive email campaign management including templates, campaigns,
messages, and analytics with proper multi-tenant support and role-based permissions.
"""

from django.db.models import Q, Count, Sum, Avg, F, Prefetch, Min
from django.db.models.functions import Cast
from django.db.models.fields import IntegerField
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from .models import (
    EmailTemplate, EmailCampaign, EmailMessage, EmailEvent,
    Contact, ContactList
)
from .email_serializers import (
    EmailTemplateSerializer, EmailTemplateListSerializer,
    EmailCampaignSerializer, EmailCampaignListSerializer,
    EmailMessageSerializer, EmailEventSerializer,
    CampaignStatsSerializer, SendTestEmailSerializer
)
from .email_tasks import (
    send_campaign_emails, schedule_campaign,
    send_test_email, process_email_event
)
from accounts.models import GroupMembership


class GroupFilteredEmailMixin:
    """Mixin to filter email querysets by user's group for multi-tenant support."""
    
    def get_queryset(self):
        """Filter queryset by user's group."""
        if hasattr(self, 'model'):
            queryset = self.model.objects.all()
        else:
            queryset = super().get_queryset()
        
        # Filter by user's group if authenticated
        if self.request.user.is_authenticated:
            user_groups = self.request.user.groups.all()
            if user_groups.exists():
                queryset = queryset.filter(group__in=user_groups)
            else:
                queryset = queryset.none()
        else:
            queryset = queryset.none()
        
        return queryset


class EmailTemplateViewSet(GroupFilteredEmailMixin, viewsets.ModelViewSet):
    """
    ViewSet for EmailTemplate model with full CRUD operations.
    
    Supports:
    - Template creation with Jinja2 variables
    - Template preview with sample data
    - Template testing
    - Template duplication
    - Usage analytics
    """
    
    model = EmailTemplate
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'subject', 'html_content', 'text_content']
    ordering_fields = ['name', 'template_type', 'created_at', 'times_used']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Use lightweight serializer for list view."""
        if self.action == 'list':
            return EmailTemplateListSerializer
        return EmailTemplateSerializer
    
    def get_queryset(self):
        """Get templates with optimized queries."""
        queryset = super().get_queryset()
        
        # Filter by template type if specified
        template_type = self.request.query_params.get('template_type')
        if template_type:
            queryset = queryset.filter(template_type=template_type)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Add creator info for detail views
        if self.action != 'list':
            queryset = queryset.select_related('created_by')
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """
        Duplicate an existing template.
        
        Creates a copy with "(Copy)" appended to the name.
        """
        template = self.get_object()
        
        # Create duplicate
        new_template = EmailTemplate.objects.create(
            group=template.group,
            name=f"{template.name} (Copy)",
            template_type=template.template_type,
            subject=template.subject,
            preheader=template.preheader,
            html_content=template.html_content,
            text_content=template.text_content,
            from_name=template.from_name,
            from_email=template.from_email,
            reply_to_email=template.reply_to_email,
            available_variables=template.available_variables,
            is_active=False,  # New templates start inactive
            is_tested=False,
            created_by=request.user
        )
        
        serializer = EmailTemplateSerializer(new_template)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """
        Send a test email using this template.
        
        Expects recipient_email and optional test_data for variable substitution.
        """
        template = self.get_object()
        serializer = SendTestEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Trigger async task to send test email
        send_test_email.delay(
            template_id=str(template.id),
            recipient_email=serializer.validated_data['recipient_email'],
            test_data=serializer.validated_data.get('test_data', {}),
            sender_id=str(request.user.id)
        )
        
        # Mark template as tested
        template.is_tested = True
        template.save(update_fields=['is_tested'])
        
        return Response({
            'status': 'success',
            'message': f'Test email queued for delivery to {serializer.validated_data["recipient_email"]}'
        })
    
    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """
        Get rendered preview of the template with sample data.
        
        Optionally accepts custom preview_data in query params.
        """
        template = self.get_object()
        
        # Get preview data from request or use defaults
        preview_data = request.query_params.dict()
        if not preview_data:
            preview_data = template.get_preview_data()
        
        # Use serializer to generate previews
        serializer = EmailTemplateSerializer(template, context={'preview_data': preview_data})
        
        return Response({
            'preview_html': serializer.data['preview_html'],
            'preview_text': serializer.data['preview_text'],
            'preview_subject': serializer.data['preview_subject'],
            'preview_data': preview_data
        })
    
    @action(detail=True, methods=['post'])
    def validate_variables(self, request, pk=None):
        """
        Validate that all template variables are available in contact data.
        
        Returns list of missing variables if any.
        """
        template = self.get_object()
        
        # Extract variables from template content
        import re
        variable_pattern = r'\{\{\s*(\w+)\s*\}\}'
        
        all_content = f"{template.subject} {template.html_content} {template.text_content}"
        found_variables = set(re.findall(variable_pattern, all_content))
        
        # Check against available contact fields
        available_fields = {
            'first_name', 'last_name', 'email', 'company_name',
            'job_title', 'department', 'city', 'country',
            'unsubscribe_url', 'preferences_url', 'current_year'
        }
        
        missing_variables = found_variables - available_fields
        
        # Update template's available_variables
        template.available_variables = list(found_variables)
        template.save(update_fields=['available_variables'])
        
        return Response({
            'found_variables': list(found_variables),
            'available_fields': list(available_fields),
            'missing_variables': list(missing_variables),
            'is_valid': len(missing_variables) == 0
        })


class EmailCampaignViewSet(GroupFilteredEmailMixin, viewsets.ModelViewSet):
    """
    ViewSet for EmailCampaign model with comprehensive campaign management.
    
    Supports:
    - Campaign creation and scheduling
    - Recipient management
    - A/B testing configuration
    - Campaign sending and status management
    - Real-time analytics
    - Campaign duplication
    """
    
    model = EmailCampaign
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'status', 'scheduled_at', 'created_at', 'emails_sent']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Use lightweight serializer for list view."""
        if self.action == 'list':
            return EmailCampaignListSerializer
        return EmailCampaignSerializer
    
    def get_queryset(self):
        """Get campaigns with optimized queries."""
        queryset = super().get_queryset()
        
        # Filter by status if specified
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Optimize queries based on action
        if self.action == 'list':
            queryset = queryset.select_related('template', 'created_by')
        else:
            queryset = queryset.select_related(
                'template', 'created_by', 'approved_by'
            ).prefetch_related(
                'contact_lists', 'excluded_contacts', 'variant_templates'
            )
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """
        Send or schedule a campaign.
        
        Validates campaign is ready and triggers sending process.
        """
        campaign = self.get_object()
        
        # Validate campaign can be sent
        if campaign.status not in [campaign.CampaignStatus.DRAFT, campaign.CampaignStatus.SCHEDULED]:
            return Response(
                {'error': f'Campaign cannot be sent in {campaign.get_status_display()} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for recipients
        recipient_count = self._calculate_recipients(campaign)
        if recipient_count == 0:
            return Response(
                {'error': 'Campaign has no recipients'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check template is active and tested
        if not campaign.template.is_active:
            return Response(
                {'error': 'Campaign template is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not campaign.template.is_tested:
            return Response(
                {'error': 'Campaign template has not been tested'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update campaign status and approval
        campaign.approved_by = request.user
        campaign.total_recipients = recipient_count
        
        if campaign.sending_strategy == campaign.SendingStrategy.IMMEDIATE:
            # Send immediately
            campaign.status = campaign.CampaignStatus.SENDING
            campaign.started_at = timezone.now()
            campaign.save()
            
            # Trigger async task
            send_campaign_emails.delay(str(campaign.id))
            
            message = f'Campaign started sending to {recipient_count} recipients'
        else:
            # Schedule for later
            if not campaign.scheduled_at:
                return Response(
                    {'error': 'Scheduled campaigns must have a scheduled_at time'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            campaign.status = campaign.CampaignStatus.SCHEDULED
            campaign.save()
            
            # Schedule the task
            schedule_campaign.apply_async(
                args=[str(campaign.id)],
                eta=campaign.scheduled_at
            )
            
            message = f'Campaign scheduled for {campaign.scheduled_at.strftime("%Y-%m-%d %H:%M")} UTC'
        
        return Response({
            'status': 'success',
            'message': message,
            'recipient_count': recipient_count
        })
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause an active campaign."""
        campaign = self.get_object()
        
        if campaign.status != campaign.CampaignStatus.SENDING:
            return Response(
                {'error': 'Only sending campaigns can be paused'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        campaign.status = campaign.CampaignStatus.PAUSED
        campaign.save()
        
        return Response({
            'status': 'success',
            'message': 'Campaign paused'
        })
    
    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Resume a paused campaign."""
        campaign = self.get_object()
        
        if campaign.status != campaign.CampaignStatus.PAUSED:
            return Response(
                {'error': 'Only paused campaigns can be resumed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        campaign.status = campaign.CampaignStatus.SENDING
        campaign.save()
        
        # Resume sending
        send_campaign_emails.delay(str(campaign.id))
        
        return Response({
            'status': 'success',
            'message': 'Campaign resumed'
        })
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a scheduled or sending campaign."""
        campaign = self.get_object()
        
        if campaign.status in [campaign.CampaignStatus.SENT, campaign.CampaignStatus.CANCELLED]:
            return Response(
                {'error': f'Cannot cancel {campaign.get_status_display()} campaign'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        campaign.status = campaign.CampaignStatus.CANCELLED
        campaign.save()
        
        return Response({
            'status': 'success',
            'message': 'Campaign cancelled'
        })
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """
        Duplicate an existing campaign.
        
        Creates a copy in draft status with same configuration.
        """
        campaign = self.get_object()
        
        # Create duplicate
        new_campaign = EmailCampaign.objects.create(
            group=campaign.group,
            name=f"{campaign.name} (Copy)",
            description=campaign.description,
            template=campaign.template,
            status=EmailCampaign.CampaignStatus.DRAFT,
            sending_strategy=campaign.sending_strategy,
            send_rate_per_hour=campaign.send_rate_per_hour,
            track_opens=campaign.track_opens,
            track_clicks=campaign.track_clicks,
            include_unsubscribe_link=campaign.include_unsubscribe_link,
            is_ab_test=campaign.is_ab_test,
            ab_test_percentage=campaign.ab_test_percentage,
            created_by=request.user
        )
        
        # Copy relationships
        new_campaign.contact_lists.set(campaign.contact_lists.all())
        new_campaign.excluded_contacts.set(campaign.excluded_contacts.all())
        new_campaign.variant_templates.set(campaign.variant_templates.all())
        
        serializer = EmailCampaignSerializer(new_campaign)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def recipients(self, request, pk=None):
        """
        Get list of campaign recipients.
        
        Returns paginated list of contacts that will receive the campaign.
        """
        campaign = self.get_object()
        
        # Get all contacts from lists
        contact_ids = set()
        for contact_list in campaign.contact_lists.all():
            if contact_list.is_dynamic:
                # TODO: Apply dynamic list criteria
                pass
            else:
                contact_ids.update(contact_list.contacts.values_list('id', flat=True))
        
        # Remove excluded contacts
        excluded_ids = campaign.excluded_contacts.values_list('id', flat=True)
        contact_ids -= set(excluded_ids)
        
        # Get contacts with opt-in
        contacts = Contact.objects.filter(
            id__in=contact_ids,
            email_opt_in=True,
            status__in=[Contact.ContactStatus.LEAD, Contact.ContactStatus.QUALIFIED,
                       Contact.ContactStatus.OPPORTUNITY, Contact.ContactStatus.CUSTOMER]
        ).order_by('email')
        
        # Paginate
        page = self.paginate_queryset(contacts)
        if page is not None:
            from .serializers import ContactSerializer
            serializer = ContactSerializer(page, many=True, context={'exclude_activities': True})
            return self.get_paginated_response(serializer.data)
        
        return Response({'count': contacts.count()})
    
    @action(detail=True, methods=['post'])
    def add_excluded_contacts(self, request, pk=None):
        """Add contacts to exclusion list."""
        campaign = self.get_object()
        contact_ids = request.data.get('contact_ids', [])
        
        if campaign.status != campaign.CampaignStatus.DRAFT:
            return Response(
                {'error': 'Can only modify exclusions for draft campaigns'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        contacts = Contact.objects.filter(
            id__in=contact_ids,
            group=campaign.group
        )
        campaign.excluded_contacts.add(*contacts)
        
        return Response({
            'status': 'success',
            'excluded': contacts.count()
        })
    
    @action(detail=True, methods=['post'])
    def remove_excluded_contacts(self, request, pk=None):
        """Remove contacts from exclusion list."""
        campaign = self.get_object()
        contact_ids = request.data.get('contact_ids', [])
        
        if campaign.status != campaign.CampaignStatus.DRAFT:
            return Response(
                {'error': 'Can only modify exclusions for draft campaigns'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        campaign.excluded_contacts.remove(*contact_ids)
        
        return Response({
            'status': 'success',
            'removed': len(contact_ids)
        })
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """
        Get detailed analytics for a campaign.
        
        Returns performance metrics and engagement data.
        """
        campaign = self.get_object()
        
        # Calculate time-based metrics
        hourly_stats = []
        if campaign.started_at:
            # Get hourly breakdown of sends, opens, clicks
            messages = campaign.messages.all()
            
            # This is simplified - in production you'd want more efficient queries
            for hour in range(24):
                hour_start = campaign.started_at + timezone.timedelta(hours=hour)
                hour_end = hour_start + timezone.timedelta(hours=1)
                
                sent = messages.filter(sent_at__gte=hour_start, sent_at__lt=hour_end).count()
                opened = messages.filter(first_opened_at__gte=hour_start, first_opened_at__lt=hour_end).count()
                clicked = messages.filter(first_clicked_at__gte=hour_start, first_clicked_at__lt=hour_end).count()
                
                if sent > 0:
                    hourly_stats.append({
                        'hour': hour,
                        'sent': sent,
                        'opened': opened,
                        'clicked': clicked
                    })
        
        # Get top clicked links
        top_links = EmailEvent.objects.filter(
            message__campaign=campaign,
            event_type=EmailEvent.EventType.CLICKED
        ).values('link_url').annotate(
            click_count=Count('id')
        ).order_by('-click_count')[:10]
        
        # Get device/client stats
        device_stats = EmailEvent.objects.filter(
            message__campaign=campaign,
            event_type=EmailEvent.EventType.OPENED
        ).values('user_agent').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return Response({
            'summary': {
                'total_recipients': campaign.total_recipients,
                'emails_sent': campaign.emails_sent,
                'emails_delivered': campaign.emails_delivered,
                'emails_opened': campaign.emails_opened,
                'unique_opens': campaign.messages.filter(open_count__gt=0).count(),
                'emails_clicked': campaign.emails_clicked,
                'unique_clicks': campaign.messages.filter(click_count__gt=0).count(),
                'emails_bounced': campaign.emails_bounced,
                'emails_unsubscribed': campaign.emails_unsubscribed,
                'open_rate': campaign.open_rate,
                'click_rate': campaign.click_rate,
                'bounce_rate': campaign.bounce_rate,
                'click_to_open_rate': round((campaign.emails_clicked / campaign.emails_opened * 100) if campaign.emails_opened > 0 else 0, 2)
            },
            'hourly_stats': hourly_stats,
            'top_links': list(top_links),
            'device_stats': list(device_stats),
            'status': campaign.status,
            'started_at': campaign.started_at,
            'completed_at': campaign.completed_at
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get overall campaign statistics for the organization.
        
        Returns summary metrics and recent campaigns.
        """
        # Get user's group
        user_groups = request.user.groups.all()
        
        # Calculate stats
        campaigns = EmailCampaign.objects.filter(group__in=user_groups)
        
        total_campaigns = campaigns.count()
        active_campaigns = campaigns.filter(
            status__in=[EmailCampaign.CampaignStatus.SENDING, EmailCampaign.CampaignStatus.SCHEDULED]
        ).count()
        
        # Aggregate email stats
        stats = campaigns.aggregate(
            total_sent=Sum('emails_sent'),
            total_delivered=Sum('emails_delivered'),
            total_opened=Sum('emails_opened'),
            total_clicked=Sum('emails_clicked')
        )
        
        # Calculate average rates for completed campaigns
        completed = campaigns.filter(status=EmailCampaign.CampaignStatus.SENT)
        avg_open_rate = 0
        avg_click_rate = 0
        
        if completed.exists():
            rates = []
            for c in completed:
                if c.emails_delivered > 0:
                    rates.append({
                        'open_rate': c.open_rate,
                        'click_rate': c.click_rate
                    })
            
            if rates:
                avg_open_rate = sum(r['open_rate'] for r in rates) / len(rates)
                avg_click_rate = sum(r['click_rate'] for r in rates) / len(rates)
        
        # Get recent campaigns
        recent = campaigns.order_by('-created_at')[:5]
        
        serializer = CampaignStatsSerializer({
            'total_campaigns': total_campaigns,
            'active_campaigns': active_campaigns,
            'total_emails_sent': stats['total_sent'] or 0,
            'average_open_rate': round(avg_open_rate, 2),
            'average_click_rate': round(avg_click_rate, 2),
            'recent_campaigns': recent
        })
        
        return Response(serializer.data)
    
    def _calculate_recipients(self, campaign):
        """Calculate unique recipient count for a campaign."""
        contact_ids = set()
        
        for contact_list in campaign.contact_lists.all():
            if contact_list.is_dynamic:
                # TODO: Apply dynamic list criteria
                pass
            else:
                contact_ids.update(contact_list.contacts.values_list('id', flat=True))
        
        # Remove excluded contacts
        excluded_ids = campaign.excluded_contacts.values_list('id', flat=True)
        contact_ids -= set(excluded_ids)
        
        # Count only opted-in, active contacts
        return Contact.objects.filter(
            id__in=contact_ids,
            email_opt_in=True,
            status__in=[Contact.ContactStatus.LEAD, Contact.ContactStatus.QUALIFIED,
                       Contact.ContactStatus.OPPORTUNITY, Contact.ContactStatus.CUSTOMER]
        ).count()


class EmailMessageViewSet(GroupFilteredEmailMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for EmailMessage model (read-only).
    
    Provides access to individual email messages and their events.
    Messages are created by the campaign sending process.
    """
    
    model = EmailMessage
    serializer_class = EmailMessageSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get messages with related data."""
        queryset = super().get_queryset()
        
        # Filter by campaign if specified
        campaign_id = self.request.query_params.get('campaign_id')
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        
        # Filter by contact if specified
        contact_id = self.request.query_params.get('contact_id')
        if contact_id:
            queryset = queryset.filter(contact_id=contact_id)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Optimize queries
        queryset = queryset.select_related(
            'campaign', 'contact', 'template_used'
        ).prefetch_related(
            Prefetch(
                'events',
                queryset=EmailEvent.objects.order_by('-timestamp')
            )
        )
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def events(self, request, pk=None):
        """Get all events for a specific message."""
        message = self.get_object()
        events = message.events.order_by('-timestamp')
        
        page = self.paginate_queryset(events)
        if page is not None:
            serializer = EmailEventSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = EmailEventSerializer(events, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def resend(self, request, pk=None):
        """
        Resend a failed message.
        
        Only available for messages with failed status.
        """
        message = self.get_object()
        
        if message.status != EmailMessage.MessageStatus.FAILED:
            return Response(
                {'error': 'Can only resend failed messages'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Reset message status
        message.status = EmailMessage.MessageStatus.PENDING
        message.failed_reason = ''
        message.save()
        
        # Queue for sending
        from .email_tasks import send_single_email
        send_single_email.delay(str(message.id))
        
        return Response({
            'status': 'success',
            'message': 'Message queued for resending'
        })


class EmailEventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for EmailEvent model (read-only).
    
    Provides access to email tracking events.
    Note: Events are not group-filtered as they're system-wide tracking.
    """
    
    queryset = EmailEvent.objects.all()
    serializer_class = EmailEventSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering = ['-timestamp']
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter events based on user's access to campaigns."""
        # Get user's groups
        user_groups = self.request.user.groups.all()
        
        # Filter events by campaigns in user's groups
        queryset = self.queryset.filter(
            message__campaign__group__in=user_groups
        )
        
        # Filter by event type if specified
        event_type = self.request.query_params.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        # Optimize queries
        queryset = queryset.select_related(
            'message__campaign', 'message__contact'
        )
        
        return queryset
    
    @action(detail=False, methods=['post'])
    def webhook(self, request):
        """
        Webhook endpoint for email service provider events.
        
        Processes incoming events from SendGrid, AWS SES, etc.
        """
        # Validate webhook signature (implementation depends on provider)
        # For now, we'll accept all authenticated requests
        
        events = request.data if isinstance(request.data, list) else [request.data]
        
        for event_data in events:
            # Process each event asynchronously
            process_email_event.delay(event_data)
        
        return Response({'status': 'accepted'}, status=status.HTTP_202_ACCEPTED)