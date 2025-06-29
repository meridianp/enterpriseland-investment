"""
Refactored ViewSets using service layer architecture.

This demonstrates how to properly separate business logic from presentation logic
by delegating complex operations to service classes.
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from typing import Dict, Any

from accounts.permissions import RoleBasedPermission, GroupAccessPermission
from accounts.models import Group
from .models import Assessment, DevelopmentPartner, PBSAScheme
from .serializers import (
    AssessmentSerializer, AssessmentCreateSerializer, AssessmentApprovalSerializer,
    DevelopmentPartnerSerializer, DevelopmentPartnerCreateSerializer,
    PBSASchemeSerializer
)
from .services import AssessmentService, DevelopmentPartnerService, PBSASchemeService
from .services.base import (
    ServiceError, ValidationServiceError, PermissionServiceError, NotFoundServiceError
)
from .filters import AssessmentFilter, DevelopmentPartnerFilter


class ServiceMixin:
    """Mixin to handle service layer integration in ViewSets."""
    
    def get_service_context(self) -> Dict[str, Any]:
        """Get context for service initialization."""
        user = self.request.user
        
        # Get group from request context or user's groups
        group = None
        if hasattr(self.request, 'group'):
            group = self.request.group
        elif user.groups.exists():
            group = user.groups.first()  # Use first group for now
        
        return {
            'user': user,
            'group': group
        }
    
    def handle_service_error(self, error: ServiceError) -> Response:
        """Convert service errors to appropriate HTTP responses."""
        if isinstance(error, NotFoundServiceError):
            return Response(
                {'error': str(error)},
                status=status.HTTP_404_NOT_FOUND
            )
        elif isinstance(error, PermissionServiceError):
            return Response(
                {'error': str(error)},
                status=status.HTTP_403_FORBIDDEN
            )
        elif isinstance(error, ValidationServiceError):
            return Response(
                {'error': str(error)},
                status=status.HTTP_400_BAD_REQUEST
            )
        else:
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AssessmentViewSetRefactored(ServiceMixin, viewsets.ModelViewSet):
    """
    Refactored Assessment ViewSet using service layer.
    
    Demonstrates proper separation of concerns by delegating business logic
    to the AssessmentService while handling HTTP concerns in the ViewSet.
    """
    queryset = Assessment.objects.all()
    serializer_class = AssessmentSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AssessmentFilter
    search_fields = ['development_partner__company_name', 'pbsa_scheme__scheme_name']
    ordering_fields = ['created_at', 'status', 'approved_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return AssessmentCreateSerializer
        elif self.action == 'approve':
            return AssessmentApprovalSerializer
        return AssessmentSerializer
    
    def get_queryset(self):
        """Filter queryset using service layer."""
        try:
            service = AssessmentService(**self.get_service_context())
            # Use service to filter queryset instead of manual filtering
            user = self.request.user
            if user.role == user.Role.ADMIN:
                return Assessment.objects.all()
            
            user_groups = user.groups.all()
            return Assessment.objects.filter(group__in=user_groups)
        except ServiceError:
            return Assessment.objects.none()
    
    def create(self, request, *args, **kwargs):
        """Create assessment using service layer."""
        try:
            service = AssessmentService(**self.get_service_context())
            
            # Extract data from request
            data = request.data
            assessment = service.create_assessment(
                development_partner_id=data.get('development_partner'),
                pbsa_scheme_id=data.get('pbsa_scheme'),
                assessment_type=data.get('assessment_type'),
                initial_data={k: v for k, v in data.items() 
                            if k not in ['development_partner', 'pbsa_scheme', 'assessment_type']}
            )
            
            # Serialize and return
            serializer = self.get_serializer(assessment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except ServiceError as e:
            return self.handle_service_error(e)
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit assessment for review using service layer."""
        try:
            service = AssessmentService(**self.get_service_context())
            assessment = service.submit_assessment(pk)
            
            serializer = self.get_serializer(assessment)
            return Response({
                'message': 'Assessment submitted successfully',
                'assessment': serializer.data
            })
            
        except ServiceError as e:
            return self.handle_service_error(e)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve or reject assessment using service layer."""
        try:
            service = AssessmentService(**self.get_service_context())
            
            data = request.data
            assessment = service.approve_assessment(
                assessment_id=pk,
                decision=data.get('decision'),
                comments=data.get('comments')
            )
            
            serializer = self.get_serializer(assessment)
            return Response({
                'message': f'Assessment {assessment.decision.lower()}',
                'assessment': serializer.data
            })
            
        except ServiceError as e:
            return self.handle_service_error(e)
    
    @action(detail=True, methods=['get'])
    def score(self, request, pk=None):
        """Calculate assessment score using service layer."""
        try:
            service = AssessmentService(**self.get_service_context())
            scores = service.calculate_assessment_score(pk)
            
            return Response(scores)
            
        except ServiceError as e:
            return self.handle_service_error(e)
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get assessment analytics using service layer."""
        try:
            service = AssessmentService(**self.get_service_context())
            group_id = request.query_params.get('group_id')
            analytics = service.get_assessment_analytics(group_id)
            
            return Response(analytics)
            
        except ServiceError as e:
            return self.handle_service_error(e)


class DevelopmentPartnerViewSetRefactored(ServiceMixin, viewsets.ModelViewSet):
    """
    Refactored Development Partner ViewSet using service layer.
    """
    queryset = DevelopmentPartner.objects.all()
    serializer_class = DevelopmentPartnerSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = DevelopmentPartnerFilter
    search_fields = ['company_name', 'trading_name', 'headquarter_city']
    ordering_fields = ['company_name', 'year_established', 'created_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return DevelopmentPartnerCreateSerializer
        return DevelopmentPartnerSerializer
    
    def get_queryset(self):
        """Filter queryset using service layer."""
        try:
            service = DevelopmentPartnerService(**self.get_service_context())
            user = self.request.user
            if user.role == user.Role.ADMIN:
                return DevelopmentPartner.objects.all()
            
            user_groups = user.groups.all()
            return DevelopmentPartner.objects.filter(group__in=user_groups)
        except ServiceError:
            return DevelopmentPartner.objects.none()
    
    def create(self, request, *args, **kwargs):
        """Create partner using service layer."""
        try:
            service = DevelopmentPartnerService(**self.get_service_context())
            partner = service.create_partner(request.data)
            
            serializer = self.get_serializer(partner)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except ServiceError as e:
            return self.handle_service_error(e)
    
    def update(self, request, *args, **kwargs):
        """Update partner using service layer."""
        try:
            service = DevelopmentPartnerService(**self.get_service_context())
            partner = service.update_partner(kwargs['pk'], request.data)
            
            serializer = self.get_serializer(partner)
            return Response(serializer.data)
            
        except ServiceError as e:
            return self.handle_service_error(e)
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get partner performance metrics using service layer."""
        try:
            service = DevelopmentPartnerService(**self.get_service_context())
            performance = service.get_partner_performance(pk)
            
            return Response(performance)
            
        except ServiceError as e:
            return self.handle_service_error(e)
    
    @action(detail=True, methods=['get'])
    def recommendations(self, request, pk=None):
        """Get partner recommendations using service layer."""
        try:
            service = DevelopmentPartnerService(**self.get_service_context())
            recommendations = service.get_partner_recommendations(pk)
            
            return Response({
                'recommendations': recommendations,
                'count': len(recommendations)
            })
            
        except ServiceError as e:
            return self.handle_service_error(e)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search partners using service layer."""
        try:
            service = DevelopmentPartnerService(**self.get_service_context())
            
            search_term = request.query_params.get('q')
            filters = {
                'min_experience': request.query_params.get('min_experience'),
                'min_schemes': request.query_params.get('min_schemes'),
                'country': request.query_params.get('country'),
                'min_employees': request.query_params.get('min_employees'),
            }
            # Remove None values
            filters = {k: v for k, v in filters.items() if v is not None}
            
            page_size = int(request.query_params.get('page_size', 50))
            
            results = service.search_partners(search_term, filters, page_size)
            return Response(results)
            
        except ServiceError as e:
            return self.handle_service_error(e)


class PBSASchemeViewSetRefactored(ServiceMixin, viewsets.ModelViewSet):
    """
    Refactored PBSA Scheme ViewSet using service layer.
    """
    queryset = PBSAScheme.objects.all()
    serializer_class = PBSASchemeSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['scheme_name', 'target_location', 'developer__company_name']
    ordering_fields = ['scheme_name', 'total_beds', 'total_investment', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset using service layer."""
        try:
            service = PBSASchemeService(**self.get_service_context())
            user = self.request.user
            if user.role == user.Role.ADMIN:
                return PBSAScheme.objects.all()
            
            user_groups = user.groups.all()
            return PBSAScheme.objects.filter(group__in=user_groups)
        except ServiceError:
            return PBSAScheme.objects.none()
    
    def create(self, request, *args, **kwargs):
        """Create scheme using service layer."""
        try:
            service = PBSASchemeService(**self.get_service_context())
            scheme = service.create_scheme(request.data)
            
            serializer = self.get_serializer(scheme)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except ServiceError as e:
            return self.handle_service_error(e)
    
    def update(self, request, *args, **kwargs):
        """Update scheme using service layer."""
        try:
            service = PBSASchemeService(**self.get_service_context())
            scheme = service.update_scheme(kwargs['pk'], request.data)
            
            serializer = self.get_serializer(scheme)
            return Response(serializer.data)
            
        except ServiceError as e:
            return self.handle_service_error(e)
    
    @action(detail=True, methods=['get'])
    def analysis(self, request, pk=None):
        """Get comprehensive scheme analysis using service layer."""
        try:
            service = PBSASchemeService(**self.get_service_context())
            analysis = service.get_scheme_analysis(pk)
            
            return Response(analysis)
            
        except ServiceError as e:
            return self.handle_service_error(e)
    
    @action(detail=True, methods=['get'])
    def metrics(self, request, pk=None):
        """Get scheme metrics using service layer."""
        try:
            service = PBSASchemeService(**self.get_service_context())
            metrics = service.calculate_scheme_metrics(pk)
            
            return Response(metrics)
            
        except ServiceError as e:
            return self.handle_service_error(e)
    
    @action(detail=True, methods=['get'])
    def recommendations(self, request, pk=None):
        """Get scheme recommendations using service layer."""
        try:
            service = PBSASchemeService(**self.get_service_context())
            recommendations = service.get_scheme_recommendations(pk)
            
            return Response({
                'recommendations': recommendations,
                'count': len(recommendations)
            })
            
        except ServiceError as e:
            return self.handle_service_error(e)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search schemes using service layer."""
        try:
            service = PBSASchemeService(**self.get_service_context())
            
            search_term = request.query_params.get('q')
            filters = {
                'min_beds': request.query_params.get('min_beds'),
                'max_beds': request.query_params.get('max_beds'),
                'min_investment': request.query_params.get('min_investment'),
                'max_investment': request.query_params.get('max_investment'),
                'location': request.query_params.get('location'),
                'developer_id': request.query_params.get('developer_id'),
            }
            # Remove None values
            filters = {k: v for k, v in filters.items() if v is not None}
            
            page_size = int(request.query_params.get('page_size', 50))
            
            results = service.search_schemes(search_term, filters, page_size)
            return Response(results)
            
        except ServiceError as e:
            return self.handle_service_error(e)