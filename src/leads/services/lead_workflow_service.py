"""
Lead Workflow Service.

Automated workflow management for lead progression, status updates,
activity tracking, and conversion management.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, F
from django.core.exceptions import ValidationError

from assessments.services.base import BaseService
from ..models import Lead, LeadActivity, LeadScoringModel

logger = logging.getLogger(__name__)


class LeadWorkflowService(BaseService):
    """
    Service for managing lead workflow automation, status progression,
    activity management, and conversion tracking.
    """
    
    def __init__(self, user=None, group=None):
        super().__init__(user=user, group=group)
        self.model = Lead
    
    # Lead Creation and Management
    
    def create_lead(self, lead_data: Dict[str, Any]) -> Lead:
        """Create a new lead with initial scoring and activity."""
        self._check_permission('create_lead')
        
        # Validate required fields
        required_fields = ['company_name']
        self._validate_required_fields(lead_data, required_fields)
        
        # Ensure group context
        if not self.group:
            raise ValidationError("Group context required for lead creation")
        
        try:
            with transaction.atomic():
                # Create lead
                lead = Lead.objects.create(
                    group=self.group,
                    identified_by=self.user,
                    **lead_data
                )
                
                # Calculate initial score
                self._calculate_initial_score(lead)
                
                # Create initial activity
                self._create_lead_activity(
                    lead=lead,
                    activity_type=LeadActivity.ActivityType.SYSTEM_UPDATE,
                    title="Lead created",
                    description=f"Lead created from {lead.get_source_display()}",
                    is_automated=True
                )
                
                # Apply automatic status updates based on score
                self._apply_automatic_status_updates(lead)
                
                logger.info(f"Created lead: {lead.company_name}")
                return lead
                
        except Exception as e:
            logger.error(f"Error creating lead: {str(e)}")
            raise ValidationError(f"Failed to create lead: {str(e)}")
    
    def update_lead_status(self, lead_id: str, new_status: str, notes: str = None) -> Lead:
        """Update lead status with workflow validation and activity tracking."""
        self._check_permission('update_lead_status')
        
        try:
            lead = Lead.objects.get(id=lead_id, group=self.group)
            
            # Validate status transition
            self._validate_status_transition(lead.status, new_status)
            
            # Store previous status
            previous_status = lead.status
            
            # Update status
            lead.status = new_status
            
            # Handle status-specific updates
            if new_status == Lead.LeadStatus.CONVERTED:
                lead.converted_at = timezone.now()
            
            lead.save()
            
            # Create status change activity
            self._create_lead_activity(
                lead=lead,
                activity_type=LeadActivity.ActivityType.STATUS_CHANGE,
                title=f"Status changed to {lead.get_status_display()}",
                description=notes or f"Status updated from {Lead.LeadStatus(previous_status).label} to {lead.get_status_display()}",
                activity_data={
                    'previous_status': previous_status,
                    'new_status': new_status,
                    'status_change_reason': notes
                }
            )
            
            # Trigger any automated actions based on new status
            self._trigger_status_based_actions(lead, new_status)
            
            logger.info(f"Updated lead {lead.company_name} status to {new_status}")
            return lead
            
        except Lead.DoesNotExist:
            raise ValidationError(f"Lead {lead_id} not found")
    
    def assign_lead(self, lead_id: str, assigned_to_id: str, notes: str = None) -> Lead:
        """Assign lead to a user with activity tracking."""
        self._check_permission('assign_lead')
        
        try:
            lead = Lead.objects.get(id=lead_id, group=self.group)
            
            # Get assigned user (validate they're in the same group)
            from django.contrib.auth import get_user_model
            User = get_user_model()
            assigned_user = User.objects.get(id=assigned_to_id)
            
            # Validate user is in the group
            if not assigned_user.groups.filter(id=self.group.id).exists():
                raise ValidationError("User is not a member of this group")
            
            # Store previous assignee
            previous_assignee = lead.assigned_to
            
            # Update assignment
            lead.assigned_to = assigned_user
            lead.save()
            
            # Create assignment activity
            self._create_lead_activity(
                lead=lead,
                activity_type=LeadActivity.ActivityType.SYSTEM_UPDATE,
                title=f"Lead assigned to {assigned_user.get_full_name() or assigned_user.username}",
                description=notes or f"Lead assigned from {previous_assignee.get_full_name() if previous_assignee else 'unassigned'} to {assigned_user.get_full_name()}",
                activity_data={
                    'previous_assignee_id': str(previous_assignee.id) if previous_assignee else None,
                    'new_assignee_id': str(assigned_user.id),
                    'assignment_reason': notes
                }
            )
            
            logger.info(f"Assigned lead {lead.company_name} to {assigned_user.username}")
            return lead
            
        except Lead.DoesNotExist:
            raise ValidationError(f"Lead {lead_id} not found")
        except User.DoesNotExist:
            raise ValidationError(f"User {assigned_to_id} not found")
    
    def convert_lead_to_partner(self, lead_id: str, conversion_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Convert qualified lead to development partner."""
        self._check_permission('convert_lead_to_partner')
        
        try:
            lead = Lead.objects.get(id=lead_id, group=self.group)
            
            # Validate lead is qualified for conversion
            if not lead.is_qualified:
                raise ValidationError("Lead must be qualified before conversion")
            
            # This would integrate with the assessments app to create DevelopmentPartner
            # For now, we'll update the lead status and create activity
            
            with transaction.atomic():
                # Update lead status
                lead.status = Lead.LeadStatus.CONVERTED
                lead.converted_at = timezone.now()
                lead.save()
                
                # Create conversion activity
                self._create_lead_activity(
                    lead=lead,
                    activity_type=LeadActivity.ActivityType.SYSTEM_UPDATE,
                    title="Lead converted to development partner",
                    description="Lead successfully converted to development partner",
                    is_milestone=True,
                    activity_data={
                        'conversion_score': lead.current_score,
                        'conversion_data': conversion_data or {},
                        'days_in_pipeline': lead.days_in_pipeline
                    }
                )
                
                result = {
                    'lead_id': str(lead.id),
                    'company_name': lead.company_name,
                    'converted_at': lead.converted_at.isoformat(),
                    'final_score': lead.current_score,
                    'days_in_pipeline': lead.days_in_pipeline,
                    'conversion_data': conversion_data or {}
                }
                
                logger.info(f"Converted lead {lead.company_name} to partner")
                return result
                
        except Lead.DoesNotExist:
            raise ValidationError(f"Lead {lead_id} not found")
    
    # Activity Management
    
    def create_activity(self, activity_data: Dict[str, Any]) -> LeadActivity:
        """Create a new lead activity."""
        self._check_permission('create_activity')
        
        # Validate required fields
        required_fields = ['lead_id', 'activity_type', 'title']
        self._validate_required_fields(activity_data, required_fields)
        
        try:
            lead = Lead.objects.get(id=activity_data['lead_id'], group=self.group)
            
            # Remove lead_id from activity_data and pass lead object
            activity_data_copy = activity_data.copy()
            del activity_data_copy['lead_id']
            
            activity = self._create_lead_activity(
                lead=lead,
                performed_by=self.user,
                **activity_data_copy
            )
            
            # Update lead's last activity timestamp implicitly handled by model
            
            logger.info(f"Created activity for lead {lead.company_name}: {activity.title}")
            return activity
            
        except Lead.DoesNotExist:
            raise ValidationError(f"Lead {activity_data['lead_id']} not found")
    
    def get_lead_timeline(self, lead_id: str) -> List[Dict[str, Any]]:
        """Get complete timeline of activities for a lead."""
        self._check_permission('view_lead_activities')
        
        try:
            lead = Lead.objects.get(id=lead_id, group=self.group)
            
            activities = LeadActivity.objects.filter(
                lead=lead
            ).order_by('-activity_date', '-created_at')
            
            timeline = []
            for activity in activities:
                timeline_item = {
                    'id': str(activity.id),
                    'activity_type': activity.activity_type,
                    'activity_type_display': activity.get_activity_type_display(),
                    'title': activity.title,
                    'description': activity.description,
                    'activity_date': activity.activity_date.isoformat(),
                    'performed_by': {
                        'id': str(activity.performed_by.id) if activity.performed_by else None,
                        'name': activity.performed_by.get_full_name() if activity.performed_by else 'System',
                        'username': activity.performed_by.username if activity.performed_by else 'system'
                    },
                    'outcome': activity.outcome,
                    'next_action': activity.next_action,
                    'next_action_date': activity.next_action_date.isoformat() if activity.next_action_date else None,
                    'is_milestone': activity.is_milestone,
                    'is_automated': activity.is_automated,
                    'activity_data': activity.activity_data
                }
                timeline.append(timeline_item)
            
            return timeline
            
        except Lead.DoesNotExist:
            raise ValidationError(f"Lead {lead_id} not found")
    
    def get_overdue_actions(self, assigned_user_id: str = None) -> List[Dict[str, Any]]:
        """Get activities with overdue next actions."""
        self._check_permission('view_lead_activities')
        
        activities = LeadActivity.objects.filter(
            group=self.group,
            next_action_date__lt=timezone.now(),
            next_action_date__isnull=False
        ).select_related('lead', 'performed_by')
        
        if assigned_user_id:
            activities = activities.filter(lead__assigned_to_id=assigned_user_id)
        
        overdue_actions = []
        for activity in activities:
            overdue_actions.append({
                'activity_id': str(activity.id),
                'lead_id': str(activity.lead.id),
                'company_name': activity.lead.company_name,
                'next_action': activity.next_action,
                'next_action_date': activity.next_action_date.isoformat(),
                'days_overdue': (timezone.now().date() - activity.next_action_date.date()).days,
                'assigned_to': {
                    'id': str(activity.lead.assigned_to.id) if activity.lead.assigned_to else None,
                    'name': activity.lead.assigned_to.get_full_name() if activity.lead.assigned_to else None
                },
                'lead_status': activity.lead.status,
                'lead_score': activity.lead.current_score
            })
        
        return sorted(overdue_actions, key=lambda x: x['days_overdue'], reverse=True)
    
    # Workflow Automation
    
    def run_automated_workflows(self) -> Dict[str, Any]:
        """Execute automated workflow rules and updates."""
        self._check_permission('run_automated_workflows')
        
        results = {
            'stale_lead_updates': 0,
            'score_based_updates': 0,
            'follow_up_reminders': 0,
            'automatic_assignments': 0,
            'processing_errors': []
        }
        
        try:
            # Process stale leads
            results['stale_lead_updates'] = self._process_stale_leads()
            
            # Apply score-based status updates
            results['score_based_updates'] = self._apply_score_based_updates()
            
            # Generate follow-up reminders
            results['follow_up_reminders'] = self._generate_follow_up_reminders()
            
            # Apply automatic assignments
            results['automatic_assignments'] = self._apply_automatic_assignments()
            
            logger.info(f"Completed automated workflows: {results}")
            
        except Exception as e:
            logger.error(f"Error in automated workflows: {str(e)}")
            results['processing_errors'].append(str(e))
        
        return results
    
    def _process_stale_leads(self) -> int:
        """Process leads that have been inactive for too long."""
        stale_threshold = timezone.now() - timedelta(days=30)
        
        stale_leads = Lead.objects.filter(
            group=self.group,
            status__in=[Lead.LeadStatus.NEW, Lead.LeadStatus.QUALIFIED, Lead.LeadStatus.CONTACTED],
            created_at__lt=stale_threshold
        )
        
        # Filter to leads without recent activity
        leads_to_update = []
        for lead in stale_leads:
            if lead.is_stale:
                leads_to_update.append(lead)
        
        # Update to nurturing status
        updated_count = 0
        for lead in leads_to_update:
            try:
                lead.status = Lead.LeadStatus.NURTURING
                lead.save()
                
                self._create_lead_activity(
                    lead=lead,
                    activity_type=LeadActivity.ActivityType.SYSTEM_UPDATE,
                    title="Lead moved to nurturing",
                    description="Lead automatically moved to nurturing due to inactivity",
                    is_automated=True
                )
                
                updated_count += 1
                
            except Exception as e:
                logger.error(f"Error updating stale lead {lead.id}: {str(e)}")
        
        return updated_count
    
    def _apply_score_based_updates(self) -> int:
        """Apply automatic status updates based on lead scores."""
        updated_count = 0
        
        # Get leads that should be auto-qualified
        leads_to_qualify = Lead.objects.filter(
            group=self.group,
            status=Lead.LeadStatus.NEW,
            current_score__gte=70
        )
        
        for lead in leads_to_qualify:
            try:
                lead.status = Lead.LeadStatus.QUALIFIED
                lead.save()
                
                self._create_lead_activity(
                    lead=lead,
                    activity_type=LeadActivity.ActivityType.STATUS_CHANGE,
                    title="Lead automatically qualified",
                    description=f"Lead automatically qualified based on score: {lead.current_score}",
                    is_automated=True,
                    activity_data={'qualifying_score': lead.current_score}
                )
                
                updated_count += 1
                
            except Exception as e:
                logger.error(f"Error auto-qualifying lead {lead.id}: {str(e)}")
        
        return updated_count
    
    def _generate_follow_up_reminders(self) -> int:
        """Generate follow-up reminder activities."""
        # Find leads that need follow-up
        leads_needing_followup = Lead.objects.filter(
            group=self.group,
            status__in=[Lead.LeadStatus.CONTACTED, Lead.LeadStatus.MEETING_SCHEDULED],
            assigned_to__isnull=False
        )
        
        reminder_count = 0
        
        for lead in leads_needing_followup:
            try:
                # Check if there's been any activity in the last 7 days
                recent_activity = LeadActivity.objects.filter(
                    lead=lead,
                    created_at__gte=timezone.now() - timedelta(days=7)
                ).exists()
                
                if not recent_activity:
                    # Create follow-up reminder
                    self._create_lead_activity(
                        lead=lead,
                        activity_type=LeadActivity.ActivityType.FOLLOW_UP,
                        title="Follow-up reminder",
                        description="Automated reminder to follow up with lead",
                        next_action="Follow up with lead",
                        next_action_date=timezone.now() + timedelta(days=1),
                        is_automated=True
                    )
                    
                    reminder_count += 1
                    
            except Exception as e:
                logger.error(f"Error creating follow-up reminder for lead {lead.id}: {str(e)}")
        
        return reminder_count
    
    def _apply_automatic_assignments(self) -> int:
        """Apply automatic lead assignments based on rules."""
        # Get unassigned high-scoring leads
        unassigned_leads = Lead.objects.filter(
            group=self.group,
            assigned_to__isnull=True,
            current_score__gte=80,
            status__in=[Lead.LeadStatus.NEW, Lead.LeadStatus.QUALIFIED]
        )
        
        # This would implement assignment rules based on:
        # - User workload
        # - Geographic territory
        # - Specialization
        # For now, just assign to users with lowest workload
        
        assignment_count = 0
        
        for lead in unassigned_leads:
            try:
                # Find user with lowest lead count
                from django.contrib.auth import get_user_model
                User = get_user_model()
                
                available_users = User.objects.filter(
                    groups=self.group,
                    role__in=[User.Role.BUSINESS_ANALYST, User.Role.PORTFOLIO_MANAGER]
                ).annotate(
                    lead_count=Count('assigned_leads')
                ).order_by('lead_count')
                
                if available_users.exists():
                    assigned_user = available_users.first()
                    
                    lead.assigned_to = assigned_user
                    lead.save()
                    
                    self._create_lead_activity(
                        lead=lead,
                        activity_type=LeadActivity.ActivityType.SYSTEM_UPDATE,
                        title=f"Lead automatically assigned to {assigned_user.get_full_name()}",
                        description=f"High-scoring lead automatically assigned based on workload balancing",
                        is_automated=True,
                        activity_data={'assignment_score': lead.current_score}
                    )
                    
                    assignment_count += 1
                    
            except Exception as e:
                logger.error(f"Error auto-assigning lead {lead.id}: {str(e)}")
        
        return assignment_count
    
    # Workflow Analytics
    
    def get_workflow_analytics(self, days_back: int = 30) -> Dict[str, Any]:
        """Get comprehensive workflow analytics."""
        self._check_permission('view_workflow_analytics')
        
        cutoff_date = timezone.now() - timedelta(days=days_back)
        
        # Lead status distribution
        status_distribution = self._get_status_distribution()
        
        # Activity metrics
        activity_metrics = self._get_activity_metrics(cutoff_date)
        
        # Conversion funnel
        conversion_funnel = self._get_conversion_funnel()
        
        # Performance by assignee
        assignee_performance = self._get_assignee_performance(cutoff_date)
        
        # Lead velocity metrics
        velocity_metrics = self._get_velocity_metrics()
        
        result = {
            'status_distribution': status_distribution,
            'activity_metrics': activity_metrics,
            'conversion_funnel': conversion_funnel,
            'assignee_performance': assignee_performance,
            'velocity_metrics': velocity_metrics,
            'period_days': days_back,
            'generated_at': timezone.now().isoformat()
        }
        
        return result
    
    def _get_status_distribution(self) -> Dict[str, int]:
        """Get distribution of leads by status."""
        distribution = {}
        for status_choice in Lead.LeadStatus.choices:
            status_code = status_choice[0]
            count = Lead.objects.filter(group=self.group, status=status_code).count()
            distribution[status_code] = count
        
        return distribution
    
    def _get_activity_metrics(self, cutoff_date: datetime) -> Dict[str, Any]:
        """Get activity metrics for the period."""
        activities = LeadActivity.objects.filter(
            group=self.group,
            created_at__gte=cutoff_date
        )
        
        metrics = {
            'total_activities': activities.count(),
            'activities_by_type': {},
            'automated_activities': activities.filter(is_automated=True).count(),
            'milestone_activities': activities.filter(is_milestone=True).count(),
            'average_activities_per_lead': 0
        }
        
        # Activities by type
        for activity_type in LeadActivity.ActivityType.choices:
            type_code = activity_type[0]
            count = activities.filter(activity_type=type_code).count()
            metrics['activities_by_type'][type_code] = count
        
        # Average activities per lead
        total_leads = Lead.objects.filter(group=self.group).count()
        if total_leads > 0:
            metrics['average_activities_per_lead'] = metrics['total_activities'] / total_leads
        
        return metrics
    
    def _get_conversion_funnel(self) -> Dict[str, int]:
        """Get conversion funnel metrics."""
        leads = Lead.objects.filter(group=self.group)
        
        funnel = {
            'total_leads': leads.count(),
            'new_leads': leads.filter(status=Lead.LeadStatus.NEW).count(),
            'qualified_leads': leads.filter(status=Lead.LeadStatus.QUALIFIED).count(),
            'contacted_leads': leads.filter(status=Lead.LeadStatus.CONTACTED).count(),
            'meeting_scheduled': leads.filter(status=Lead.LeadStatus.MEETING_SCHEDULED).count(),
            'proposal_sent': leads.filter(status=Lead.LeadStatus.PROPOSAL_SENT).count(),
            'negotiating': leads.filter(status=Lead.LeadStatus.NEGOTIATING).count(),
            'converted': leads.filter(status=Lead.LeadStatus.CONVERTED).count(),
            'lost': leads.filter(status=Lead.LeadStatus.LOST).count()
        }
        
        # Calculate conversion rates
        if funnel['total_leads'] > 0:
            funnel['qualification_rate'] = (funnel['qualified_leads'] / funnel['total_leads']) * 100
            funnel['contact_rate'] = (funnel['contacted_leads'] / funnel['total_leads']) * 100
            funnel['conversion_rate'] = (funnel['converted'] / funnel['total_leads']) * 100
        
        return funnel
    
    def _get_assignee_performance(self, cutoff_date: datetime) -> List[Dict[str, Any]]:
        """Get performance metrics by assignee."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        assignees = User.objects.filter(
            groups=self.group,
            assigned_leads__isnull=False
        ).distinct().annotate(
            total_leads=Count('assigned_leads'),
            converted_leads=Count('assigned_leads', filter=Q(assigned_leads__status=Lead.LeadStatus.CONVERTED)),
            recent_activities=Count('lead_activities', filter=Q(lead_activities__created_at__gte=cutoff_date))
        )
        
        performance = []
        for assignee in assignees:
            conversion_rate = (assignee.converted_leads / assignee.total_leads * 100) if assignee.total_leads > 0 else 0
            
            performance.append({
                'assignee_id': str(assignee.id),
                'assignee_name': assignee.get_full_name() or assignee.username,
                'total_leads': assignee.total_leads,
                'converted_leads': assignee.converted_leads,
                'conversion_rate': conversion_rate,
                'recent_activities': assignee.recent_activities
            })
        
        return sorted(performance, key=lambda x: x['conversion_rate'], reverse=True)
    
    def _get_velocity_metrics(self) -> Dict[str, float]:
        """Get lead velocity metrics."""
        converted_leads = Lead.objects.filter(
            group=self.group,
            status=Lead.LeadStatus.CONVERTED,
            converted_at__isnull=False
        )
        
        if not converted_leads.exists():
            return {
                'average_days_to_conversion': 0,
                'median_days_to_conversion': 0,
                'fastest_conversion_days': 0,
                'slowest_conversion_days': 0
            }
        
        conversion_times = []
        for lead in converted_leads:
            days_to_conversion = (lead.converted_at.date() - lead.created_at.date()).days
            conversion_times.append(days_to_conversion)
        
        conversion_times.sort()
        
        avg_days = sum(conversion_times) / len(conversion_times)
        median_days = conversion_times[len(conversion_times) // 2]
        
        return {
            'average_days_to_conversion': avg_days,
            'median_days_to_conversion': median_days,
            'fastest_conversion_days': min(conversion_times),
            'slowest_conversion_days': max(conversion_times)
        }
    
    # Helper Methods
    
    def _calculate_initial_score(self, lead: Lead):
        """Calculate and set initial score for a new lead."""
        try:
            lead.calculate_score()
        except Exception as e:
            logger.warning(f"Could not calculate initial score for lead {lead.id}: {str(e)}")
    
    def _apply_automatic_status_updates(self, lead: Lead):
        """Apply automatic status updates based on initial score."""
        if lead.current_score >= 70:
            lead.status = Lead.LeadStatus.QUALIFIED
            lead.save()
            
            self._create_lead_activity(
                lead=lead,
                activity_type=LeadActivity.ActivityType.STATUS_CHANGE,
                title="Lead automatically qualified",
                description=f"Lead automatically qualified based on initial score: {lead.current_score}",
                is_automated=True
            )
    
    def _validate_status_transition(self, current_status: str, new_status: str):
        """Validate that status transition is allowed."""
        # Define allowed transitions
        allowed_transitions = {
            Lead.LeadStatus.NEW: [Lead.LeadStatus.QUALIFIED, Lead.LeadStatus.REJECTED, Lead.LeadStatus.NURTURING],
            Lead.LeadStatus.QUALIFIED: [Lead.LeadStatus.CONTACTED, Lead.LeadStatus.REJECTED, Lead.LeadStatus.NURTURING],
            Lead.LeadStatus.CONTACTED: [Lead.LeadStatus.MEETING_SCHEDULED, Lead.LeadStatus.REJECTED, Lead.LeadStatus.NURTURING],
            Lead.LeadStatus.MEETING_SCHEDULED: [Lead.LeadStatus.PROPOSAL_SENT, Lead.LeadStatus.REJECTED, Lead.LeadStatus.NURTURING],
            Lead.LeadStatus.PROPOSAL_SENT: [Lead.LeadStatus.NEGOTIATING, Lead.LeadStatus.REJECTED, Lead.LeadStatus.NURTURING],
            Lead.LeadStatus.NEGOTIATING: [Lead.LeadStatus.CONVERTED, Lead.LeadStatus.LOST, Lead.LeadStatus.NURTURING],
            Lead.LeadStatus.NURTURING: [Lead.LeadStatus.QUALIFIED, Lead.LeadStatus.CONTACTED, Lead.LeadStatus.REJECTED],
            Lead.LeadStatus.CONVERTED: [],  # Terminal state
            Lead.LeadStatus.LOST: [Lead.LeadStatus.NURTURING],  # Can be revived
            Lead.LeadStatus.REJECTED: []  # Terminal state
        }
        
        if new_status not in allowed_transitions.get(current_status, []):
            raise ValidationError(f"Invalid status transition from {current_status} to {new_status}")
    
    def _trigger_status_based_actions(self, lead: Lead, new_status: str):
        """Trigger automated actions based on status changes."""
        if new_status == Lead.LeadStatus.QUALIFIED and not lead.assigned_to:
            # Auto-assign high-scoring qualified leads
            if lead.current_score >= 85:
                # This would implement assignment logic
                pass
        
        elif new_status == Lead.LeadStatus.CONTACTED:
            # Schedule follow-up reminder
            follow_up_date = timezone.now() + timedelta(days=3)
            self._create_lead_activity(
                lead=lead,
                activity_type=LeadActivity.ActivityType.FOLLOW_UP,
                title="Schedule follow-up",
                description="Follow up on initial contact",
                next_action="Follow up with lead",
                next_action_date=follow_up_date,
                is_automated=True
            )
    
    def _create_lead_activity(self, lead: Lead, **activity_data) -> LeadActivity:
        """Helper method to create lead activity with proper defaults."""
        defaults = {
            'group': self.group,
            'performed_by': self.user,
            'activity_date': timezone.now(),
            'is_automated': False,
            'is_milestone': False
        }
        
        # Merge provided data with defaults
        activity_data = {**defaults, **activity_data}
        
        return LeadActivity.objects.create(lead=lead, **activity_data)