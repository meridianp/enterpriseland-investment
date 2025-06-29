"""
URL configuration for Deal endpoints.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    DealTypeViewSet, DealSourceViewSet, DealRoleViewSet,
    WorkflowTemplateViewSet, DealStageViewSet, DealViewSet,
    DealTeamMemberViewSet, DealActivityViewSet, DealMilestoneViewSet,
    DealCommentViewSet, DealDiscussionViewSet, DealNotificationViewSet,
    VirtualDataRoomViewSet, VDRFolderViewSet, VDRDocumentViewSet, VDRAccessViewSet,
    # IC Pack views
    ICPackTemplateViewSet, ICPackViewSet, ICPackApprovalViewSet,
    ICPackDistributionViewSet,
    # Meeting scheduler views
    MeetingViewSet, MeetingAttendeeViewSet, MeetingResourceViewSet,
    MeetingResourceBookingViewSet, AvailabilitySlotViewSet
)

app_name = 'deals'

router = DefaultRouter()
router.register(r'types', DealTypeViewSet, basename='dealtype')
router.register(r'sources', DealSourceViewSet, basename='dealsource')
router.register(r'roles', DealRoleViewSet, basename='dealrole')
router.register(r'workflows', WorkflowTemplateViewSet, basename='workflowtemplate')
router.register(r'stages', DealStageViewSet, basename='dealstage')
router.register(r'deals', DealViewSet, basename='deal')
router.register(r'team-members', DealTeamMemberViewSet, basename='dealteammember')
router.register(r'activities', DealActivityViewSet, basename='dealactivity')
router.register(r'milestones', DealMilestoneViewSet, basename='dealmilestone')

# Collaboration endpoints
router.register(r'comments', DealCommentViewSet, basename='dealcomment')
router.register(r'discussions', DealDiscussionViewSet, basename='dealdiscussion')
router.register(r'notifications', DealNotificationViewSet, basename='dealnotification')

# Virtual Data Room endpoints
router.register(r'vdr', VirtualDataRoomViewSet, basename='virtualdataroom')
router.register(r'vdr-folders', VDRFolderViewSet, basename='vdrfolder')
router.register(r'vdr-documents', VDRDocumentViewSet, basename='vdrdocument')
router.register(r'vdr-access', VDRAccessViewSet, basename='vdraccess')

# IC Pack automation endpoints
router.register(r'ic-pack-templates', ICPackTemplateViewSet, basename='icpacktemplate')
router.register(r'ic-packs', ICPackViewSet, basename='icpack')
router.register(r'ic-pack-approvals', ICPackApprovalViewSet, basename='icpackapproval')
router.register(r'ic-pack-distributions', ICPackDistributionViewSet, basename='icpackdistribution')

# Meeting scheduler endpoints
router.register(r'meetings', MeetingViewSet, basename='meeting')
router.register(r'meeting-attendees', MeetingAttendeeViewSet, basename='meetingattendee')
router.register(r'meeting-resources', MeetingResourceViewSet, basename='meetingresource')
router.register(r'meeting-resource-bookings', MeetingResourceBookingViewSet, basename='meetingresourcebooking')
router.register(r'availability-slots', AvailabilitySlotViewSet, basename='availabilityslot')

urlpatterns = [
    path('', include(router.urls)),
]