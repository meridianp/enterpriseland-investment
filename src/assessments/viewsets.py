
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Avg, Count
from django.utils import timezone
from datetime import timedelta

from accounts.permissions import RoleBasedPermission, GroupAccessPermission, CanApproveAssessments
from .models import (
    DevelopmentPartner, PBSAScheme, Assessment, AssessmentStatus, FinancialInformation,
    CreditInformation, AssessmentMetric, FXRate, AssessmentAuditLog_Legacy
)
from .serializers import (
    DevelopmentPartnerSerializer, DevelopmentPartnerCreateSerializer,
    PBSASchemeSerializer, AssessmentSerializer, AssessmentCreateSerializer,
    AssessmentApprovalSerializer, FXRateSerializer, AssessmentAuditLog_LegacySerializer,
    DashboardKPISerializer
)
from .filters import AssessmentFilter, DevelopmentPartnerFilter

class DevelopmentPartnerViewSet(viewsets.ModelViewSet):
    """ViewSet for development partners"""
    queryset = DevelopmentPartner.objects.all()
    permission_classes = [IsAuthenticated, RoleBasedPermission, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = DevelopmentPartnerFilter
    search_fields = ['company_name', 'trading_name', 'headquarter_city']
    ordering_fields = ['company_name', 'year_established', 'created_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return DevelopmentPartnerCreateSerializer
        return DevelopmentPartnerSerializer
    
    def get_queryset(self):
        """Filter queryset by user's groups"""
        user = self.request.user
        if user.role == user.Role.ADMIN:
            return DevelopmentPartner.objects.all()
        
        user_groups = user.groups.all()
        return DevelopmentPartner.objects.filter(group__in=user_groups)
    
    @action(detail=True, methods=['get'])
    def assessments(self, request, pk=None):
        """Get all assessments for this partner"""
        partner = self.get_object()
        assessments = partner.assessments.all()
        serializer = AssessmentSerializer(assessments, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def contacts(self, request, pk=None):
        """Get all contacts associated with this partner"""
        partner = self.get_object()
        
        # Import here to avoid circular imports
        from ..contacts.models import ContactPartner
        from ..contacts.serializers import ContactSerializer
        
        # Get contacts through the ContactPartner relationship
        contact_partners = ContactPartner.objects.filter(
            partner=partner,
            group__in=request.user.groups.all()
        ).select_related('contact')
        
        contacts = [cp.contact for cp in contact_partners]
        serializer = ContactSerializer(contacts, many=True, context={'request': request})
        
        return Response({
            'count': len(contacts),
            'results': serializer.data
        })

class PBSASchemeViewSet(viewsets.ModelViewSet):
    """ViewSet for PBSA schemes"""
    queryset = PBSAScheme.objects.all()
    serializer_class = PBSASchemeSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['scheme_name', 'location_city']
    ordering_fields = ['scheme_name', 'total_beds', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset by user's groups"""
        user = self.request.user
        if user.role == user.Role.ADMIN:
            return PBSAScheme.objects.all()
        
        user_groups = user.groups.all()
        return PBSAScheme.objects.filter(group__in=user_groups)
    
    def perform_create(self, serializer):
        """Set group when creating scheme"""
        group = self.request.user.groups.first()
        serializer.save(group=group)
    
    @action(detail=True, methods=['get'])
    def assessments(self, request, pk=None):
        """Get all assessments for this scheme"""
        scheme = self.get_object()
        assessments = scheme.assessments.all()
        serializer = AssessmentSerializer(assessments, many=True)
        return Response(serializer.data)

class AssessmentViewSet(viewsets.ModelViewSet):
    """ViewSet for assessments"""
    queryset = Assessment.objects.all()
    permission_classes = [IsAuthenticated, RoleBasedPermission, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AssessmentFilter
    search_fields = ['partner__company_name', 'scheme__scheme_name']
    ordering_fields = ['created_at', 'updated_at', 'total_score', 'status']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return AssessmentCreateSerializer
        elif self.action == 'approve':
            return AssessmentApprovalSerializer
        return AssessmentSerializer
    
    def get_queryset(self):
        """Filter queryset by user's groups"""
        user = self.request.user
        if user.role == user.Role.ADMIN:
            return Assessment.objects.select_related(
                'partner', 'scheme', 'created_by', 'updated_by', 'approved_by'
            ).prefetch_related('metrics', 'financial_info', 'credit_info')
        
        user_groups = user.groups.all()
        return Assessment.objects.filter(group__in=user_groups).select_related(
            'partner', 'scheme', 'created_by', 'updated_by', 'approved_by'
        ).prefetch_related('metrics', 'financial_info', 'credit_info')
    
    def perform_update(self, serializer):
        """Update assessment with version tracking"""
        assessment = self.get_object()
        user = self.request.user
        
        # Increment patch version for updates
        assessment.increment_patch(user)
        serializer.save(updated_by=user)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanApproveAssessments])
    def approve(self, request, pk=None):
        """Approve or reject an assessment"""
        assessment = self.get_object()
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            decision = serializer.validated_data['decision']
            comments = serializer.validated_data.get('comments', '')
            
            assessment.decision = decision
            assessment.status = Assessment.AssessmentStatus.APPROVED if decision != 'Reject' else Assessment.AssessmentStatus.REJECTED
            assessment.approved_by = request.user
            assessment.approved_at = timezone.now()
            assessment.save()
            
            # Create notification (handled by signals)
            
            return Response({
                'status': 'success',
                'message': f'Assessment {decision.lower()}',
                'assessment': AssessmentSerializer(assessment).data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """Clone an existing assessment"""
        original = self.get_object()
        
        # Create new assessment
        new_assessment = Assessment.objects.create(
            group=original.group,
            assessment_type=original.assessment_type,
            partner=original.partner,
            scheme=original.scheme,
            status=Assessment.AssessmentStatus.DRAFT,
            created_by=request.user
        )
        
        # Clone financial info
        if hasattr(original, 'financial_info'):
            financial_info = original.financial_info
            financial_info.pk = None
            financial_info.assessment = new_assessment
            financial_info.save()
        
        # Clone credit info
        if hasattr(original, 'credit_info'):
            credit_info = original.credit_info
            credit_info.pk = None
            credit_info.assessment = new_assessment
            credit_info.save()
        
        # Clone metrics
        for metric in original.metrics.all():
            metric.pk = None
            metric.assessment = new_assessment
            metric.save()
        
        # Calculate total score
        total_score = sum(metric.weighted_score for metric in new_assessment.metrics.all())
        new_assessment.total_score = total_score
        new_assessment.save()
        
        serializer = AssessmentSerializer(new_assessment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get dashboard KPI data"""
        user = request.user
        
        # Filter assessments by user's groups
        if user.role == user.Role.ADMIN:
            assessments = Assessment.objects.all()
        else:
            user_groups = user.groups.all()
            assessments = Assessment.objects.filter(group__in=user_groups)
        
        # Calculate KPIs
        active_assessments = assessments.filter(
            status__in=[AssessmentStatus.DRAFT, AssessmentStatus.IN_REVIEW]
        ).count()
        
        avg_risk_score = assessments.exclude(total_score__isnull=True).aggregate(
            avg_score=Avg('total_score')
        )['avg_score'] or 0
        
        high_risk_schemes = assessments.filter(total_score__lt=120).count()
        
        # Currency exposure
        currency_exposure = {}
        for assessment in assessments.filter(financial_info__isnull=False):
            if hasattr(assessment, 'financial_info') and assessment.financial_info.net_assets_currency:
                currency = assessment.financial_info.net_assets_currency
                amount = assessment.financial_info.net_assets_amount or 0
                currency_exposure[currency] = currency_exposure.get(currency, 0) + float(amount)
        
        # Average turnaround time
        completed_assessments = assessments.filter(
            status__in=[AssessmentStatus.APPROVED, AssessmentStatus.REJECTED],
            approved_at__isnull=False
        )
        
        turnaround_times = []
        for assessment in completed_assessments:
            if assessment.approved_at and assessment.created_at:
                delta = assessment.approved_at - assessment.created_at
                turnaround_times.append(delta.days)
        
        avg_turnaround = sum(turnaround_times) / len(turnaround_times) if turnaround_times else 0
        
        data = {
            'active_assessments': active_assessments,
            'avg_risk_score': round(avg_risk_score, 1),
            'high_risk_schemes': high_risk_schemes,
            'currency_exposure': currency_exposure,
            'turnaround_time_days': round(avg_turnaround, 1)
        }
        
        serializer = DashboardKPISerializer(data)
        return Response(serializer.data)

class FXRateViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for FX rates (read-only)"""
    queryset = FXRate.objects.all()
    serializer_class = FXRateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['base_currency', 'target_currency', 'date']
    ordering = ['-date', 'base_currency', 'target_currency']
    
    @action(detail=False, methods=['post'])
    def refresh(self, request):
        """Manually refresh FX rates"""
        # This would trigger the FX rate update task
        from .tasks import update_fx_rates
        update_fx_rates.delay()
        
        return Response({
            'status': 'success',
            'message': 'FX rate update initiated'
        })

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for legacy audit logs (read-only) - TO BE MIGRATED"""
    queryset = AssessmentAuditLog_Legacy.objects.all()
    serializer_class = AssessmentAuditLog_LegacySerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['table_name', 'action', 'user']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        """Only auditors and admins can view audit logs"""
        user = self.request.user
        if user.role not in [user.Role.AUDITOR, user.Role.ADMIN]:
            return AssessmentAuditLog_Legacy.objects.none()
        
        return AssessmentAuditLog_Legacy.objects.select_related('user')
