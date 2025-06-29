app_name = 'investment_assessments'


from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import (
    DevelopmentPartnerViewSet, PBSASchemeViewSet, AssessmentViewSet,
    FXRateViewSet, AuditLogViewSet
)
# from .advanced_viewsets import (
#     RegulatoryComplianceViewSet, PerformanceMetricViewSet,
#     ESGAssessmentViewSet, AuditTrailViewSet
# )

router = DefaultRouter()
router.register(r'partners', DevelopmentPartnerViewSet)
router.register(r'schemes', PBSASchemeViewSet)
router.register(r'assessments', AssessmentViewSet)
router.register(r'fx-rates', FXRateViewSet)
router.register(r'audit-logs', AuditLogViewSet)

# Advanced features endpoints
# router.register(r'regulatory-compliance', RegulatoryComplianceViewSet, basename='regulatorycompliance')
# router.register(r'performance-metrics', PerformanceMetricViewSet, basename='performancemetric')
# router.register(r'esg-assessments', ESGAssessmentViewSet, basename='esgassessment')
# router.register(r'audit-trail', AuditTrailViewSet, basename='audittrail')

urlpatterns = [
    path('', include(router.urls)),
]
