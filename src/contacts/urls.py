"""
URL configuration for the contacts app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ContactViewSet, ContactActivityViewSet, 
    ContactListViewSet, ContactPartnerViewSet
)
from .email_views import (
    EmailTemplateViewSet, EmailCampaignViewSet,
    EmailMessageViewSet, EmailEventViewSet
)
from .views_outreach import (
    OutreachSequenceViewSet, SequenceStepViewSet,
    SequenceEnrollmentViewSet, SequenceTemplateViewSet
)

router = DefaultRouter()
router.register(r'contacts', ContactViewSet, basename='contact')
router.register(r'contact-activities', ContactActivityViewSet, basename='contactactivity')
router.register(r'contact-lists', ContactListViewSet, basename='contactlist')
router.register(r'contact-partners', ContactPartnerViewSet, basename='contactpartner')

# Email campaign endpoints
router.register(r'email-templates', EmailTemplateViewSet, basename='emailtemplate')
router.register(r'email-campaigns', EmailCampaignViewSet, basename='emailcampaign')
router.register(r'email-messages', EmailMessageViewSet, basename='emailmessage')
router.register(r'email-events', EmailEventViewSet, basename='emailevent')

# Outreach sequence endpoints
router.register(r'outreach-sequences', OutreachSequenceViewSet, basename='outreachsequence')
router.register(r'sequence-steps', SequenceStepViewSet, basename='sequencestep')
router.register(r'sequence-enrollments', SequenceEnrollmentViewSet, basename='sequenceenrollment')
router.register(r'sequence-templates', SequenceTemplateViewSet, basename='sequencetemplate')

app_name = 'contacts'

urlpatterns = [
    path('', include(router.urls)),
]