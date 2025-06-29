"""
Email analytics module for the EnterpriseLand Due-Diligence Platform.

Provides comprehensive analytics and reporting for email campaigns,
including performance metrics, engagement tracking, and insights.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

from django.db.models import Count, Sum, Avg, Q, F, Case, When, Value, IntegerField, Min
from django.db.models.functions import TruncDate, TruncHour, ExtractHour, Cast
from django.utils import timezone

from .models import (
    EmailCampaign, EmailMessage, EmailEvent, EmailTemplate,
    Contact, ContactList, ContactActivity
)


class EmailAnalytics:
    """
    Main analytics class for email campaign performance analysis.
    """
    
    def __init__(self, group=None, start_date=None, end_date=None):
        self.group = group
        self.start_date = start_date or timezone.now() - timedelta(days=30)
        self.end_date = end_date or timezone.now()
    
    def get_campaign_metrics(self, campaign: EmailCampaign) -> Dict[str, Any]:
        """
        Get comprehensive metrics for a single campaign.
        """
        messages = campaign.messages.all()
        
        # Basic metrics
        metrics = {
            'campaign_id': str(campaign.id),
            'campaign_name': campaign.name,
            'status': campaign.status,
            'started_at': campaign.started_at,
            'completed_at': campaign.completed_at,
            
            # Volume metrics
            'total_recipients': campaign.total_recipients,
            'emails_sent': campaign.emails_sent,
            'emails_delivered': campaign.emails_delivered,
            'emails_bounced': campaign.emails_bounced,
            'emails_failed': messages.filter(status='failed').count(),
            
            # Engagement metrics
            'unique_opens': messages.filter(open_count__gt=0).count(),
            'total_opens': messages.aggregate(total=Sum('open_count'))['total'] or 0,
            'unique_clicks': messages.filter(click_count__gt=0).count(),
            'total_clicks': messages.aggregate(total=Sum('click_count'))['total'] or 0,
            
            # Negative metrics
            'unsubscribes': campaign.emails_unsubscribed,
            'complaints': messages.filter(status='complained').count(),
            
            # Calculated rates
            'delivery_rate': self._calculate_rate(campaign.emails_delivered, campaign.emails_sent),
            'open_rate': campaign.open_rate,
            'click_rate': campaign.click_rate,
            'bounce_rate': campaign.bounce_rate,
            'unsubscribe_rate': self._calculate_rate(campaign.emails_unsubscribed, campaign.emails_delivered),
            'complaint_rate': self._calculate_rate(
                messages.filter(status='complained').count(),
                campaign.emails_delivered
            ),
            
            # Advanced metrics
            'click_to_open_rate': self._calculate_rate(
                messages.filter(click_count__gt=0).count(),
                messages.filter(open_count__gt=0).count()
            ),
            'average_opens_per_recipient': self._calculate_average(
                messages.aggregate(total=Sum('open_count'))['total'] or 0,
                messages.filter(open_count__gt=0).count()
            ),
            'average_clicks_per_recipient': self._calculate_average(
                messages.aggregate(total=Sum('click_count'))['total'] or 0,
                messages.filter(click_count__gt=0).count()
            ),
        }
        
        # Time-based metrics
        if campaign.started_at:
            metrics['time_metrics'] = self._get_time_based_metrics(campaign)
        
        # Device and client metrics
        metrics['device_metrics'] = self._get_device_metrics(campaign)
        
        # Link performance
        metrics['link_metrics'] = self._get_link_metrics(campaign)
        
        # Recipient engagement distribution
        metrics['engagement_distribution'] = self._get_engagement_distribution(campaign)
        
        return metrics
    
    def get_template_performance(self, template: EmailTemplate) -> Dict[str, Any]:
        """
        Analyze performance across all campaigns using a template.
        """
        campaigns = EmailCampaign.objects.filter(
            template=template,
            status='sent'
        )
        
        if not campaigns.exists():
            return {
                'template_id': str(template.id),
                'template_name': template.name,
                'times_used': 0,
                'metrics': {}
            }
        
        # Aggregate metrics across campaigns
        total_sent = campaigns.aggregate(total=Sum('emails_sent'))['total'] or 0
        total_delivered = campaigns.aggregate(total=Sum('emails_delivered'))['total'] or 0
        total_opened = campaigns.aggregate(total=Sum('emails_opened'))['total'] or 0
        total_clicked = campaigns.aggregate(total=Sum('emails_clicked'))['total'] or 0
        
        return {
            'template_id': str(template.id),
            'template_name': template.name,
            'times_used': campaigns.count(),
            'metrics': {
                'total_sent': total_sent,
                'average_open_rate': self._calculate_rate(total_opened, total_delivered),
                'average_click_rate': self._calculate_rate(total_clicked, total_delivered),
                'best_performing_campaign': self._get_best_campaign(campaigns),
                'performance_trend': self._get_template_trend(template)
            }
        }
    
    def get_contact_engagement_score(self, contact: Contact) -> Dict[str, Any]:
        """
        Calculate engagement score for a contact based on email interactions.
        """
        # Get recent messages
        messages = EmailMessage.objects.filter(
            contact=contact,
            sent_at__gte=timezone.now() - timedelta(days=90)
        )
        
        if not messages.exists():
            return {
                'contact_id': str(contact.id),
                'engagement_score': 0,
                'metrics': {}
            }
        
        # Calculate engagement metrics
        total_sent = messages.count()
        total_opened = messages.filter(open_count__gt=0).count()
        total_clicked = messages.filter(click_count__gt=0).count()
        total_bounced = messages.filter(status='bounced').count()
        
        # Calculate score (0-100)
        score = 0
        if total_sent > 0:
            open_rate = total_opened / total_sent
            click_rate = total_clicked / total_sent
            bounce_rate = total_bounced / total_sent
            
            # Weight different factors
            score += open_rate * 40  # 40 points for opens
            score += click_rate * 40  # 40 points for clicks
            score -= bounce_rate * 20  # -20 points for bounces
            
            # Recency bonus
            last_open = messages.filter(open_count__gt=0).order_by('-last_opened_at').first()
            if last_open and last_open.last_opened_at:
                days_since_open = (timezone.now() - last_open.last_opened_at).days
                if days_since_open < 7:
                    score += 20
                elif days_since_open < 30:
                    score += 10
        
        return {
            'contact_id': str(contact.id),
            'engagement_score': round(max(0, min(100, score)), 2),
            'metrics': {
                'total_sent': total_sent,
                'total_opened': total_opened,
                'total_clicked': total_clicked,
                'open_rate': self._calculate_rate(total_opened, total_sent),
                'click_rate': self._calculate_rate(total_clicked, total_sent),
                'last_engagement': self._get_last_engagement(contact)
            }
        }
    
    def get_list_performance(self, contact_list: ContactList) -> Dict[str, Any]:
        """
        Analyze email performance for a contact list.
        """
        # Get campaigns that included this list
        campaigns = EmailCampaign.objects.filter(
            contact_lists=contact_list,
            status='sent'
        )
        
        if not campaigns.exists():
            return {
                'list_id': str(contact_list.id),
                'list_name': contact_list.name,
                'campaigns_used': 0,
                'metrics': {}
            }
        
        # Get messages sent to contacts in this list
        list_contacts = contact_list.contacts.all()
        messages = EmailMessage.objects.filter(
            campaign__in=campaigns,
            contact__in=list_contacts
        )
        
        total_sent = messages.count()
        total_opened = messages.filter(open_count__gt=0).count()
        total_clicked = messages.filter(click_count__gt=0).count()
        total_unsubscribed = messages.filter(status='unsubscribed').count()
        
        return {
            'list_id': str(contact_list.id),
            'list_name': contact_list.name,
            'campaigns_used': campaigns.count(),
            'metrics': {
                'total_sent': total_sent,
                'open_rate': self._calculate_rate(total_opened, total_sent),
                'click_rate': self._calculate_rate(total_clicked, total_sent),
                'unsubscribe_rate': self._calculate_rate(total_unsubscribed, total_sent),
                'engagement_trend': self._get_list_trend(contact_list, campaigns)
            }
        }
    
    def get_organization_overview(self) -> Dict[str, Any]:
        """
        Get high-level email analytics for the entire organization.
        """
        # Filter by group if specified
        campaign_filter = Q()
        if self.group:
            campaign_filter &= Q(group=self.group)
        
        # Date range filter
        campaign_filter &= Q(created_at__gte=self.start_date, created_at__lte=self.end_date)
        
        campaigns = EmailCampaign.objects.filter(campaign_filter)
        
        # Calculate aggregate metrics
        total_campaigns = campaigns.count()
        total_sent = campaigns.aggregate(total=Sum('emails_sent'))['total'] or 0
        total_delivered = campaigns.aggregate(total=Sum('emails_delivered'))['total'] or 0
        total_opened = campaigns.aggregate(total=Sum('emails_opened'))['total'] or 0
        total_clicked = campaigns.aggregate(total=Sum('emails_clicked'))['total'] or 0
        
        # Get active templates
        active_templates = EmailTemplate.objects.filter(
            is_active=True,
            group=self.group
        ).count() if self.group else EmailTemplate.objects.filter(is_active=True).count()
        
        # Get growth metrics
        growth_metrics = self._calculate_growth_metrics(campaigns)
        
        return {
            'period': {
                'start': self.start_date,
                'end': self.end_date
            },
            'summary': {
                'total_campaigns': total_campaigns,
                'total_emails_sent': total_sent,
                'active_templates': active_templates,
                'average_open_rate': self._calculate_rate(total_opened, total_delivered),
                'average_click_rate': self._calculate_rate(total_clicked, total_delivered),
            },
            'growth': growth_metrics,
            'top_campaigns': self._get_top_campaigns(campaigns),
            'campaign_status_distribution': self._get_status_distribution(campaigns),
            'hourly_engagement_pattern': self._get_hourly_pattern(),
            'weekly_trend': self._get_weekly_trend(campaigns)
        }
    
    def get_ab_test_results(self, campaign: EmailCampaign) -> Dict[str, Any]:
        """
        Analyze A/B test results for campaigns with variants.
        """
        if not campaign.is_ab_test:
            return {
                'campaign_id': str(campaign.id),
                'is_ab_test': False,
                'results': None
            }
        
        # Get messages by template variant
        variants = [campaign.template] + list(campaign.variant_templates.all())
        variant_results = []
        
        for idx, template in enumerate(variants):
            messages = campaign.messages.filter(template_used=template)
            sent = messages.count()
            opened = messages.filter(open_count__gt=0).count()
            clicked = messages.filter(click_count__gt=0).count()
            
            variant_results.append({
                'variant': chr(65 + idx),  # A, B, C, etc.
                'template_id': str(template.id),
                'template_name': template.name,
                'subject': template.subject,
                'sent': sent,
                'open_rate': self._calculate_rate(opened, sent),
                'click_rate': self._calculate_rate(clicked, sent),
                'conversion_rate': self._calculate_conversion_rate(messages)
            })
        
        # Determine winner
        winner = max(variant_results, key=lambda x: x['click_rate'])
        
        # Calculate statistical significance
        significance = self._calculate_statistical_significance(variant_results)
        
        return {
            'campaign_id': str(campaign.id),
            'is_ab_test': True,
            'results': {
                'variants': variant_results,
                'winner': winner,
                'statistical_significance': significance,
                'recommendation': self._get_ab_recommendation(variant_results, significance)
            }
        }
    
    # Helper methods
    
    def _calculate_rate(self, numerator: int, denominator: int) -> float:
        """Calculate percentage rate."""
        if denominator == 0:
            return 0.0
        return round((numerator / denominator) * 100, 2)
    
    def _calculate_average(self, total: int, count: int) -> float:
        """Calculate average."""
        if count == 0:
            return 0.0
        return round(total / count, 2)
    
    def _get_time_based_metrics(self, campaign: EmailCampaign) -> Dict[str, Any]:
        """Get time-based engagement metrics."""
        events = EmailEvent.objects.filter(message__campaign=campaign)
        
        # Time to first open
        first_opens = events.filter(
            event_type='opened'
        ).values('message_id').annotate(
            first_open=Min('timestamp')
        )
        
        time_to_open_data = []
        for fo in first_opens:
            message = EmailMessage.objects.get(id=fo['message_id'])
            if message.sent_at and fo['first_open']:
                delta = (fo['first_open'] - message.sent_at).total_seconds() / 3600
                time_to_open_data.append(delta)
        
        avg_time_to_open = sum(time_to_open_data) / len(time_to_open_data) if time_to_open_data else 0
        
        # Best time of day
        hourly_opens = events.filter(
            event_type='opened'
        ).annotate(
            hour=ExtractHour('timestamp')
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('-count')
        
        best_hour = hourly_opens[0]['hour'] if hourly_opens else None
        
        return {
            'average_time_to_open_hours': round(avg_time_to_open, 2),
            'best_hour_for_opens': best_hour,
            'engagement_timeline': self._get_engagement_timeline(campaign)
        }
    
    def _get_device_metrics(self, campaign: EmailCampaign) -> Dict[str, Any]:
        """Analyze device and email client usage."""
        events = EmailEvent.objects.filter(
            message__campaign=campaign,
            event_type='opened'
        ).exclude(user_agent='')
        
        # Simple device detection (in production, use a proper user agent parser)
        device_counts = {
            'mobile': events.filter(
                Q(user_agent__icontains='mobile') | 
                Q(user_agent__icontains='android') |
                Q(user_agent__icontains='iphone')
            ).count(),
            'desktop': events.filter(
                Q(user_agent__icontains='windows') |
                Q(user_agent__icontains='macintosh') |
                Q(user_agent__icontains='linux')
            ).exclude(
                Q(user_agent__icontains='mobile') |
                Q(user_agent__icontains='android')
            ).count(),
            'tablet': events.filter(
                Q(user_agent__icontains='ipad') |
                Q(user_agent__icontains='tablet')
            ).count()
        }
        
        total = sum(device_counts.values())
        
        return {
            'device_distribution': {
                device: self._calculate_rate(count, total)
                for device, count in device_counts.items()
            },
            'top_email_clients': self._get_top_email_clients(events)
        }
    
    def _get_link_metrics(self, campaign: EmailCampaign) -> List[Dict[str, Any]]:
        """Get click metrics for links in the campaign."""
        link_clicks = EmailEvent.objects.filter(
            message__campaign=campaign,
            event_type='clicked'
        ).values('link_url').annotate(
            clicks=Count('id'),
            unique_clicks=Count('message_id', distinct=True)
        ).order_by('-clicks')[:10]
        
        return [
            {
                'url': click['link_url'],
                'total_clicks': click['clicks'],
                'unique_clicks': click['unique_clicks']
            }
            for click in link_clicks
        ]
    
    def _get_engagement_distribution(self, campaign: EmailCampaign) -> Dict[str, int]:
        """Get distribution of engagement levels."""
        messages = campaign.messages.all()
        
        return {
            'not_opened': messages.filter(open_count=0).count(),
            'opened_not_clicked': messages.filter(
                open_count__gt=0,
                click_count=0
            ).count(),
            'clicked': messages.filter(click_count__gt=0).count(),
            'highly_engaged': messages.filter(
                open_count__gte=3,
                click_count__gte=2
            ).count()
        }
    
    def _get_best_campaign(self, campaigns) -> Optional[Dict[str, Any]]:
        """Find the best performing campaign."""
        best = None
        best_score = 0
        
        for campaign in campaigns:
            # Simple scoring: weight opens and clicks
            score = (campaign.open_rate * 0.4) + (campaign.click_rate * 0.6)
            if score > best_score:
                best_score = score
                best = {
                    'id': str(campaign.id),
                    'name': campaign.name,
                    'open_rate': campaign.open_rate,
                    'click_rate': campaign.click_rate
                }
        
        return best
    
    def _get_template_trend(self, template: EmailTemplate) -> List[Dict[str, Any]]:
        """Get performance trend for a template over time."""
        campaigns = EmailCampaign.objects.filter(
            template=template,
            status='sent'
        ).order_by('completed_at')[:10]
        
        return [
            {
                'date': campaign.completed_at,
                'campaign_name': campaign.name,
                'open_rate': campaign.open_rate,
                'click_rate': campaign.click_rate
            }
            for campaign in campaigns
        ]
    
    def _get_last_engagement(self, contact: Contact) -> Optional[Dict[str, Any]]:
        """Get last engagement activity for a contact."""
        last_activity = ContactActivity.objects.filter(
            contact=contact,
            activity_type__in=['email_opened', 'email_clicked']
        ).order_by('-created_at').first()
        
        if last_activity:
            return {
                'type': last_activity.activity_type,
                'date': last_activity.created_at,
                'subject': last_activity.subject
            }
        return None
    
    def _get_list_trend(self, contact_list: ContactList, campaigns) -> List[Dict[str, Any]]:
        """Get engagement trend for a contact list."""
        trend_data = []
        
        for campaign in campaigns.order_by('completed_at')[:5]:
            messages = EmailMessage.objects.filter(
                campaign=campaign,
                contact__in=contact_list.contacts.all()
            )
            
            sent = messages.count()
            opened = messages.filter(open_count__gt=0).count()
            clicked = messages.filter(click_count__gt=0).count()
            
            trend_data.append({
                'campaign': campaign.name,
                'date': campaign.completed_at,
                'open_rate': self._calculate_rate(opened, sent),
                'click_rate': self._calculate_rate(clicked, sent)
            })
        
        return trend_data
    
    def _calculate_growth_metrics(self, campaigns) -> Dict[str, Any]:
        """Calculate growth metrics for campaigns."""
        # Get previous period
        period_length = (self.end_date - self.start_date).days
        previous_start = self.start_date - timedelta(days=period_length)
        previous_end = self.start_date
        
        previous_campaigns = EmailCampaign.objects.filter(
            created_at__gte=previous_start,
            created_at__lt=previous_end
        )
        
        if self.group:
            previous_campaigns = previous_campaigns.filter(group=self.group)
        
        # Calculate growth
        current_sent = campaigns.aggregate(total=Sum('emails_sent'))['total'] or 0
        previous_sent = previous_campaigns.aggregate(total=Sum('emails_sent'))['total'] or 0
        
        growth_rate = 0
        if previous_sent > 0:
            growth_rate = ((current_sent - previous_sent) / previous_sent) * 100
        
        return {
            'emails_sent_growth': round(growth_rate, 2),
            'campaign_count_growth': self._calculate_rate(
                campaigns.count() - previous_campaigns.count(),
                previous_campaigns.count() or 1
            )
        }
    
    def _get_top_campaigns(self, campaigns, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top performing campaigns."""
        # Score campaigns by engagement
        scored_campaigns = []
        
        for campaign in campaigns.filter(status='sent'):
            score = (campaign.open_rate * 0.3) + (campaign.click_rate * 0.5) + \
                   ((100 - campaign.bounce_rate) * 0.1) + ((100 - (campaign.emails_unsubscribed / (campaign.emails_delivered or 1) * 100)) * 0.1)
            
            scored_campaigns.append({
                'campaign': campaign,
                'score': score
            })
        
        # Sort by score and return top campaigns
        scored_campaigns.sort(key=lambda x: x['score'], reverse=True)
        
        return [
            {
                'id': str(item['campaign'].id),
                'name': item['campaign'].name,
                'sent_at': item['campaign'].completed_at,
                'open_rate': item['campaign'].open_rate,
                'click_rate': item['campaign'].click_rate,
                'score': round(item['score'], 2)
            }
            for item in scored_campaigns[:limit]
        ]
    
    def _get_status_distribution(self, campaigns) -> Dict[str, int]:
        """Get distribution of campaign statuses."""
        return {
            status: campaigns.filter(status=status).count()
            for status in ['draft', 'scheduled', 'sending', 'sent', 'paused', 'cancelled']
        }
    
    def _get_hourly_pattern(self) -> List[Dict[str, Any]]:
        """Get average engagement by hour of day."""
        # Get all opens and clicks in the period
        events = EmailEvent.objects.filter(
            event_type__in=['opened', 'clicked'],
            timestamp__gte=self.start_date,
            timestamp__lte=self.end_date
        )
        
        if self.group:
            events = events.filter(message__campaign__group=self.group)
        
        hourly_data = events.annotate(
            hour=ExtractHour('timestamp')
        ).values('hour', 'event_type').annotate(
            count=Count('id')
        ).order_by('hour')
        
        # Organize by hour
        pattern = defaultdict(lambda: {'opens': 0, 'clicks': 0})
        for item in hourly_data:
            if item['event_type'] == 'opened':
                pattern[item['hour']]['opens'] = item['count']
            elif item['event_type'] == 'clicked':
                pattern[item['hour']]['clicks'] = item['count']
        
        return [
            {
                'hour': hour,
                'opens': data['opens'],
                'clicks': data['clicks']
            }
            for hour, data in sorted(pattern.items())
        ]
    
    def _get_weekly_trend(self, campaigns) -> List[Dict[str, Any]]:
        """Get weekly trend of email performance."""
        # Group campaigns by week
        weekly_data = campaigns.annotate(
            week=TruncDate('created_at')
        ).values('week').annotate(
            campaigns=Count('id'),
            emails_sent=Sum('emails_sent'),
            emails_opened=Sum('emails_opened'),
            emails_clicked=Sum('emails_clicked')
        ).order_by('week')
        
        return [
            {
                'week': item['week'],
                'campaigns': item['campaigns'],
                'emails_sent': item['emails_sent'],
                'open_rate': self._calculate_rate(
                    item['emails_opened'],
                    item['emails_sent']
                ),
                'click_rate': self._calculate_rate(
                    item['emails_clicked'],
                    item['emails_sent']
                )
            }
            for item in weekly_data
        ]
    
    def _get_engagement_timeline(self, campaign: EmailCampaign) -> List[Dict[str, Any]]:
        """Get timeline of engagement after campaign send."""
        if not campaign.started_at:
            return []
        
        # Get events in first 48 hours
        end_time = campaign.started_at + timedelta(hours=48)
        events = EmailEvent.objects.filter(
            message__campaign=campaign,
            event_type__in=['opened', 'clicked'],
            timestamp__gte=campaign.started_at,
            timestamp__lte=end_time
        )
        
        # Group by hour
        hourly_events = events.annotate(
            hours_after=Cast(
                (F('timestamp') - campaign.started_at),
                output_field=IntegerField()
            ) / 3600
        ).values('hours_after', 'event_type').annotate(
            count=Count('id')
        ).order_by('hours_after')
        
        timeline = defaultdict(lambda: {'opens': 0, 'clicks': 0})
        for event in hourly_events:
            hour = int(event['hours_after'])
            if hour <= 48:
                if event['event_type'] == 'opened':
                    timeline[hour]['opens'] = event['count']
                elif event['event_type'] == 'clicked':
                    timeline[hour]['clicks'] = event['count']
        
        return [
            {
                'hours_after_send': hour,
                'opens': data['opens'],
                'clicks': data['clicks']
            }
            for hour, data in sorted(timeline.items())
        ]
    
    def _get_top_email_clients(self, events, limit: int = 5) -> List[Dict[str, Any]]:
        """Detect and rank email clients from user agent strings."""
        client_patterns = {
            'gmail': ['gmail', 'googlemail'],
            'outlook': ['outlook', 'office365'],
            'apple_mail': ['apple mail', 'applemail'],
            'yahoo': ['yahoo'],
            'thunderbird': ['thunderbird'],
            'other': []
        }
        
        client_counts = defaultdict(int)
        
        for event in events:
            user_agent = event.user_agent.lower()
            detected = False
            
            for client, patterns in client_patterns.items():
                if any(pattern in user_agent for pattern in patterns):
                    client_counts[client] += 1
                    detected = True
                    break
            
            if not detected:
                client_counts['other'] += 1
        
        total = sum(client_counts.values())
        
        return [
            {
                'client': client,
                'count': count,
                'percentage': self._calculate_rate(count, total)
            }
            for client, count in sorted(
                client_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:limit]
        ]
    
    def _calculate_conversion_rate(self, messages) -> float:
        """Calculate conversion rate for messages."""
        # This is a placeholder - in a real implementation,
        # you'd track actual conversions (purchases, signups, etc.)
        # For now, we'll use clicks as a proxy
        clicked = messages.filter(click_count__gt=0).count()
        total = messages.count()
        
        return self._calculate_rate(clicked, total)
    
    def _calculate_statistical_significance(self, variants: List[Dict]) -> float:
        """
        Calculate statistical significance for A/B test results.
        
        This is a simplified calculation - in production, use proper
        statistical tests like Chi-squared or T-test.
        """
        if len(variants) < 2:
            return 0.0
        
        # Get the top two variants
        sorted_variants = sorted(variants, key=lambda x: x['click_rate'], reverse=True)
        control = sorted_variants[0]
        challenger = sorted_variants[1]
        
        # Simple significance calculation based on difference
        rate_difference = abs(control['click_rate'] - challenger['click_rate'])
        sample_size = min(control['sent'], challenger['sent'])
        
        # Rough approximation of significance
        if sample_size < 100:
            significance = min(rate_difference * 2, 95)
        elif sample_size < 1000:
            significance = min(rate_difference * 4, 95)
        else:
            significance = min(rate_difference * 6, 95)
        
        return round(significance, 2)
    
    def _get_ab_recommendation(self, variants: List[Dict], significance: float) -> str:
        """Get recommendation based on A/B test results."""
        if significance < 80:
            return "Continue testing - results are not yet statistically significant"
        
        sorted_variants = sorted(variants, key=lambda x: x['click_rate'], reverse=True)
        winner = sorted_variants[0]
        
        improvement = winner['click_rate'] - sorted_variants[-1]['click_rate']
        
        return f"Variant {winner['variant']} is the winner with {improvement:.1f}% higher click rate. " \
               f"Consider using template '{winner['template_name']}' for future campaigns."


class EmailReportGenerator:
    """
    Generate formatted reports from analytics data.
    """
    
    def __init__(self, analytics: EmailAnalytics):
        self.analytics = analytics
    
    def generate_campaign_report(self, campaign: EmailCampaign) -> str:
        """Generate a formatted text report for a campaign."""
        metrics = self.analytics.get_campaign_metrics(campaign)
        
        report = f"""
EMAIL CAMPAIGN REPORT
====================

Campaign: {metrics['campaign_name']}
Status: {metrics['status']}
Sent: {metrics['started_at'].strftime('%Y-%m-%d %H:%M') if metrics['started_at'] else 'Not started'}
Completed: {metrics['completed_at'].strftime('%Y-%m-%d %H:%M') if metrics['completed_at'] else 'Not completed'}

DELIVERY METRICS
---------------
Total Recipients: {metrics['total_recipients']:,}
Emails Sent: {metrics['emails_sent']:,}
Emails Delivered: {metrics['emails_delivered']:,} ({metrics['delivery_rate']}%)
Emails Bounced: {metrics['emails_bounced']:,} ({metrics['bounce_rate']}%)

ENGAGEMENT METRICS
-----------------
Unique Opens: {metrics['unique_opens']:,} ({metrics['open_rate']}%)
Total Opens: {metrics['total_opens']:,}
Unique Clicks: {metrics['unique_clicks']:,} ({metrics['click_rate']}%)
Total Clicks: {metrics['total_clicks']:,}
Click-to-Open Rate: {metrics['click_to_open_rate']}%

NEGATIVE METRICS
---------------
Unsubscribes: {metrics['unsubscribes']:,} ({metrics['unsubscribe_rate']}%)
Complaints: {metrics['complaints']:,} ({metrics['complaint_rate']}%)

"""
        
        # Add top links if available
        if 'link_metrics' in metrics and metrics['link_metrics']:
            report += "\nTOP CLICKED LINKS\n-----------------\n"
            for idx, link in enumerate(metrics['link_metrics'][:5], 1):
                report += f"{idx}. {link['url'][:50]}{'...' if len(link['url']) > 50 else ''}\n"
                report += f"   Clicks: {link['total_clicks']} (Unique: {link['unique_clicks']})\n"
        
        return report
    
    def generate_weekly_summary(self) -> str:
        """Generate a weekly summary report."""
        overview = self.analytics.get_organization_overview()
        
        report = f"""
WEEKLY EMAIL SUMMARY
===================

Period: {overview['period']['start'].strftime('%Y-%m-%d')} to {overview['period']['end'].strftime('%Y-%m-%d')}

OVERVIEW
--------
Total Campaigns: {overview['summary']['total_campaigns']}
Total Emails Sent: {overview['summary']['total_emails_sent']:,}
Average Open Rate: {overview['summary']['average_open_rate']}%
Average Click Rate: {overview['summary']['average_click_rate']}%

GROWTH
------
Email Volume Growth: {overview['growth']['emails_sent_growth']}%
Campaign Count Growth: {overview['growth']['campaign_count_growth']}%

TOP PERFORMING CAMPAIGNS
-----------------------
"""
        
        for idx, campaign in enumerate(overview['top_campaigns'], 1):
            report += f"\n{idx}. {campaign['name']}\n"
            report += f"   Open Rate: {campaign['open_rate']}% | Click Rate: {campaign['click_rate']}%\n"
            report += f"   Performance Score: {campaign['score']}\n"
        
        return report