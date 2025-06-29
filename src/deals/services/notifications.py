"""
Deal notification services.
"""
from celery import shared_task
from django.conf import settings


@shared_task
def send_deal_activity_notification(activity_id, user_id):
    """
    Send notification to team members about deal activity.
    
    Args:
        activity_id: UUID of the DealActivity
        user_id: UUID of the User to notify
    """
    # Skip notifications in test mode
    if getattr(settings, 'TESTING', False):
        return
    
    # For now, just a placeholder implementation
    # In a real implementation, this would integrate with the notification system
    pass

def send_deal_transition_notification(deal, transition, team_members):
    """
    Send notification about deal stage transition.
    
    Args:
        deal: Deal instance
        transition: DealTransition instance  
        team_members: QuerySet of DealTeamMember instances
    """
    pass

def send_milestone_notification(milestone, team_members, notification_type):
    """
    Send milestone-related notifications.
    
    Args:
        milestone: DealMilestone instance
        team_members: QuerySet of DealTeamMember instances
        notification_type: Type of notification (due, overdue, completed)
    """
    pass