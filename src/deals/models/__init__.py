"""
Deal management models for the EnterpriseLand platform.

This module provides comprehensive deal tracking and workflow management.
"""

from .deal import Deal, DealType, DealSource
from .workflow import DealStage, DealTransition, WorkflowTemplate
from .team import DealTeamMember, DealRole
from .milestone import DealMilestone, MilestoneTemplate
from .activity import DealActivity, ActivityType
from .collaboration import DealComment, DealDiscussion, DealNotification
from .vdr import VirtualDataRoom, VDRFolder, VDRDocument, VDRAccess, VDRAuditLog
from .ic_pack import (
    ICPackStatus, ICPackTemplate, ICPack, ICPackApproval,
    ICPackDistribution, ICPackAuditLog
)
from .meeting_scheduler import (
    MeetingType, MeetingStatus, RecurrenceType, CalendarProvider,
    Meeting, MeetingAttendee, MeetingResource, MeetingResourceBooking,
    AvailabilitySlot
)

__all__ = [
    'Deal',
    'DealType',
    'DealSource',
    'DealStage',
    'DealTransition',
    'WorkflowTemplate',
    'DealTeamMember',
    'DealRole',
    'DealMilestone',
    'MilestoneTemplate',
    'DealActivity',
    'ActivityType',
    'DealComment',
    'DealDiscussion',
    'DealNotification',
    'VirtualDataRoom',
    'VDRFolder',
    'VDRDocument',
    'VDRAccess',
    'VDRAuditLog',
    'ICPackStatus',
    'ICPackTemplate',
    'ICPack',
    'ICPackApproval',
    'ICPackDistribution',
    'ICPackAuditLog',
    'MeetingType',
    'MeetingStatus',
    'RecurrenceType',
    'CalendarProvider',
    'Meeting',
    'MeetingAttendee',
    'MeetingResource',
    'MeetingResourceBooking',
    'AvailabilitySlot',
]