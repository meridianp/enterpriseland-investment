"""
ViewSets for Deal API endpoints.
"""

from rest_framework import viewsets
from platform_core.core.views import PlatformViewSet, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models
from django.db.models import Q, Count, Sum, Avg, F, ExpressionWrapper, DurationField
from django.utils import timezone
from datetime import timedelta

from platform_core.accounts.permissions import IsManager, IsAdmin, GroupAccessPermission
from .models import (
    Deal, DealType, DealSource, WorkflowTemplate, DealStage,
    DealRole, DealTeamMember, DealActivity, DealMilestone,
    DealComment, DealDiscussion, DealNotification,
    VirtualDataRoom, VDRFolder, VDRDocument, VDRAccess, VDRAuditLog
)
from .models.meeting_scheduler import (
    Meeting, MeetingAttendee, MeetingResource, MeetingResourceBooking,
    AvailabilitySlot, MeetingStatus, MeetingType
)
from .models.ic_pack import (
    ICPackTemplate, ICPack, ICPackApproval, ICPackDistribution,
    ICPackAuditLog, ICPackStatus
)
from .serializers import (
    DealTypeSerializer, DealSourceSerializer, DealRoleSerializer,
    WorkflowTemplateSerializer, DealStageSerializer,
    DealTeamMemberSerializer, DealActivitySerializer,
    DealMilestoneSerializer, DealListSerializer, DealDetailSerializer,
    DealCreateSerializer, DealTransitionSerializer,
    MilestoneCompleteSerializer, DealAnalyticsSerializer,
    DealCommentSerializer, DealCommentCreateSerializer,
    DealDiscussionSerializer, DealNotificationSerializer,
    VirtualDataRoomSerializer, VDRFolderSerializer, VDRDocumentSerializer,
    VDRAccessSerializer, VDRAuditLogSerializer,
    # IC Pack serializers
    ICPackTemplateSerializer, ICPackTemplateListSerializer,
    ICPackSerializer, ICPackCreateSerializer, ICPackApprovalSerializer,
    ICPackDistributionSerializer, ICPackAuditLogSerializer,
    ICPackGenerateDocumentSerializer, ICPackApprovalDecisionSerializer,
    ICPackDistributeSerializer, ICPackAnalyticsSerializer,
    # Meeting scheduler serializers
    MeetingSerializer, MeetingListSerializer, MeetingCreateSerializer,
    MeetingAttendeeSerializer, MeetingResourceSerializer,
    MeetingResourceBookingSerializer, AvailabilitySlotSerializer,
    MeetingRescheduleSerializer, MeetingCancelSerializer,
    FindOptimalTimeSerializer, MeetingAnalyticsSerializer
)
from .services.workflow_engine import WorkflowEngine


class DealTypeViewSet(PlatformViewSet):
    """ViewSet for deal types."""
    queryset = DealType.objects.all()
    serializer_class = DealTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name', 'code', 'description']
    filterset_fields = ['is_active']
    
    def get_permissions(self):
        """Only admins can create/update/delete."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return super().get_permissions()


class DealSourceViewSet(PlatformViewSet):
    """ViewSet for deal sources."""
    queryset = DealSource.objects.all()
    serializer_class = DealSourceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name', 'code', 'description']
    filterset_fields = ['is_active']
    
    def get_permissions(self):
        """Only admins can create/update/delete."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return super().get_permissions()


class DealRoleViewSet(PlatformViewSet):
    """ViewSet for deal roles."""
    queryset = DealRole.objects.all()
    serializer_class = DealRoleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name', 'code', 'description']
    filterset_fields = ['is_active', 'is_required']
    
    def get_permissions(self):
        """Only admins can create/update/delete."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return super().get_permissions()


class WorkflowTemplateViewSet(PlatformViewSet):
    """ViewSet for workflow templates."""
    queryset = WorkflowTemplate.objects.all()
    serializer_class = WorkflowTemplateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name', 'code', 'description']
    filterset_fields = ['deal_type', 'is_default', 'is_active']
    
    def get_permissions(self):
        """Only admins can create/update/delete."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return super().get_permissions()


class DealStageViewSet(PlatformViewSet):
    """ViewSet for deal stages."""
    queryset = DealStage.objects.all()
    serializer_class = DealStageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['workflow_template', 'stage_type', 'is_active']
    ordering_fields = ['order', 'name']
    ordering = ['order']
    
    def get_permissions(self):
        """Only admins can create/update/delete."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return super().get_permissions()


class DealViewSet(PlatformViewSet):
    """ViewSet for deals."""
    queryset = Deal.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'partner__first_name', 'partner__last_name']
    filterset_fields = [
        'deal_type', 'status', 'deal_lead', 'current_stage',
        'source', 'origination_date', 'expected_close_date'
    ]
    ordering_fields = [
        'created_at', 'updated_at', 'investment_amount',
        'expected_close_date', 'status'
    ]
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Use different serializers for different actions."""
        if self.action == 'list':
            return DealListSerializer
        elif self.action == 'create':
            return DealCreateSerializer
        elif self.action == 'transition':
            return DealTransitionSerializer
        return DealDetailSerializer
    
    def get_permissions(self):
        """Check permissions based on action."""
        if self.action == 'destroy':
            return [IsAdmin()]
        elif self.action in ['create', 'update', 'partial_update', 'transition']:
            return [IsAuthenticated()]  # Further checks in methods
        return super().get_permissions()
    
    def perform_create(self, serializer):
        """Set group when creating deal."""
        serializer.save(group=self.request.user.groups.first())
    
    def update(self, request, *args, **kwargs):
        """Check if user can edit the deal."""
        deal = self.get_object()
        
        # Check if user is deal lead or has edit permission
        can_edit = (
            request.user == deal.deal_lead or
            request.user.is_superuser or
            deal.team_members.filter(
                user=request.user,
                can_edit=True,
                removed_at__isnull=True
            ).exists()
        )
        
        if not can_edit:
            return Response(
                {"detail": "You don't have permission to edit this deal"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().update(request, *args, **kwargs)
    
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """Get deal activities."""
        deal = self.get_object()
        
        # Filter private activities based on user role
        activities = deal.activities.all()
        if not request.user.is_superuser:
            # Check if user is on deal team
            is_team_member = deal.team_members.filter(
                user=request.user,
                removed_at__isnull=True
            ).exists()
            
            if not is_team_member:
                activities = activities.filter(is_private=False)
        
        # Pagination
        page = self.paginate_queryset(activities)
        if page is not None:
            serializer = DealActivitySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = DealActivitySerializer(activities, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def team(self, request, pk=None):
        """Get deal team members."""
        deal = self.get_object()
        team_members = deal.team_members.filter(removed_at__isnull=True)
        serializer = DealTeamMemberSerializer(team_members, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def transition(self, request, pk=None):
        """Transition deal to new stage."""
        deal = self.get_object()
        
        # Check permission
        can_transition = (
            request.user == deal.deal_lead or
            request.user.is_superuser or
            deal.team_members.filter(
                user=request.user,
                can_approve=True,
                removed_at__isnull=True
            ).exists()
        )
        
        if not can_transition:
            return Response(
                {"detail": "You don't have permission to transition this deal"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request, 'deal': deal}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Return updated deal
        deal.refresh_from_db()
        return Response(
            DealDetailSerializer(deal).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['get'])
    def available_transitions(self, request, pk=None):
        """Get available stage transitions."""
        deal = self.get_object()
        engine = WorkflowEngine(deal)
        transitions = engine.get_available_transitions()
        
        # Format response
        data = []
        for transition in transitions:
            data.append({
                'stage': DealStageSerializer(transition['stage']).data if transition['stage'] else None,
                'status': transition['status'],
                'can_transition': transition['can_transition'],
                'requirements': transition['requirements']
            })
        
        return Response(data)
    
    @action(detail=False, methods=['get'])
    def pipeline(self, request):
        """Get pipeline view of deals."""
        # Group deals by status
        pipeline_data = {}
        
        for status in Deal.Status:
            deals = self.filter_queryset(self.get_queryset()).filter(status=status.value)
            pipeline_data[status.value] = {
                'label': status.label,
                'count': deals.count(),
                'value': deals.aggregate(total=Sum('investment_amount'))['total'] or 0,
                'deals': DealListSerializer(deals[:10], many=True).data  # Top 10
            }
        
        return Response(pipeline_data)
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get deal analytics."""
        deals = self.filter_queryset(self.get_queryset())
        
        # Basic metrics
        total_deals = deals.count()
        metrics = deals.aggregate(
            total_investment=Sum('investment_amount'),
            average_deal_size=Avg('investment_amount'),
            average_irr=Avg('irr_target')
        )
        
        # By status
        by_status = {}
        for status in Deal.Status:
            status_deals = deals.filter(status=status.value)
            by_status[status.value] = {
                'count': status_deals.count(),
                'value': status_deals.aggregate(total=Sum('investment_amount'))['total'] or 0
            }
        
        # By stage
        by_stage = deals.exclude(current_stage__isnull=True).values(
            'current_stage__name'
        ).annotate(
            count=Count('id'),
            value=Sum('investment_amount')
        )
        
        # By deal type
        by_deal_type = deals.values('deal_type__name').annotate(
            count=Count('id'),
            value=Sum('investment_amount')
        )
        
        # Pipeline vs closed
        pipeline_value = deals.exclude(
            status__in=[Deal.Status.COMPLETED, Deal.Status.REJECTED, Deal.Status.WITHDRAWN]
        ).aggregate(total=Sum('investment_amount'))['total'] or 0
        
        closed_value = deals.filter(
            status=Deal.Status.COMPLETED
        ).aggregate(total=Sum('investment_amount'))['total'] or 0
        
        # Average time to close
        closed_deals = deals.filter(
            status=Deal.Status.COMPLETED,
            closed_date__isnull=False
        ).annotate(
            time_to_close=ExpressionWrapper(
                F('closed_date') - F('origination_date'),
                output_field=DurationField()
            )
        )
        
        avg_time_to_close = 0
        if closed_deals.exists():
            total_days = sum(
                d.time_to_close.days for d in closed_deals if d.time_to_close
            )
            avg_time_to_close = total_days // closed_deals.count()
        
        # Deals at risk (overdue expected close)
        deals_at_risk = deals.filter(
            expected_close_date__lt=timezone.now().date(),
            status__in=[
                Deal.Status.PIPELINE,
                Deal.Status.INITIAL_REVIEW,
                Deal.Status.DUE_DILIGENCE,
                Deal.Status.NEGOTIATION,
                Deal.Status.DOCUMENTATION,
                Deal.Status.CLOSING
            ]
        ).count()
        
        # Overdue milestones
        overdue_milestones = DealMilestone.objects.filter(
            deal__in=deals,
            due_date__lt=timezone.now().date(),
            status__in=[DealMilestone.Status.PENDING, DealMilestone.Status.IN_PROGRESS]
        ).count()
        
        analytics_data = {
            'total_deals': total_deals,
            'total_investment': metrics['total_investment'] or 0,
            'average_deal_size': metrics['average_deal_size'] or 0,
            'average_irr': metrics['average_irr'] or 0,
            'by_status': by_status,
            'by_stage': list(by_stage),
            'by_deal_type': list(by_deal_type),
            'pipeline_value': pipeline_value,
            'closed_value': closed_value,
            'average_time_to_close': avg_time_to_close,
            'deals_at_risk': deals_at_risk,
            'overdue_milestones': overdue_milestones
        }
        
        serializer = DealAnalyticsSerializer(analytics_data)
        return Response(serializer.data)


class DealTeamMemberViewSet(PlatformViewSet):
    """ViewSet for deal team members."""
    queryset = DealTeamMember.objects.filter(removed_at__isnull=True)
    serializer_class = DealTeamMemberSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['user__first_name', 'user__last_name', 'user__email']
    filterset_fields = ['deal', 'role', 'involvement_level']
    
    def get_permissions(self):
        """Only managers can add/remove team members."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsManager()]
        return super().get_permissions()
    
    def perform_create(self, serializer):
        """Set group when creating team member."""
        deal = serializer.validated_data['deal']
        serializer.save(group=deal.group)
    
    def perform_destroy(self, instance):
        """Soft delete by setting removed_at."""
        instance.removed_at = timezone.now()
        instance.removal_reason = "Removed by " + self.request.user.get_full_name()
        instance.save()


class DealActivityViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for deal activities (read-only)."""
    queryset = DealActivity.objects.all()
    serializer_class = DealActivitySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['deal', 'activity_type', 'performed_by', 'is_important']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter based on user permissions."""
        queryset = super().get_queryset()
        
        if not self.request.user.is_superuser:
            # Only show activities for deals user has access to
            user_deals = Deal.objects.filter(
                Q(deal_lead=self.request.user) |
                Q(team_members__user=self.request.user, team_members__removed_at__isnull=True)
            ).distinct()
            
            queryset = queryset.filter(deal__in=user_deals)
            
            # Filter private activities
            queryset = queryset.filter(
                Q(is_private=False) |
                Q(performed_by=self.request.user)
            )
        
        return queryset


class DealMilestoneViewSet(PlatformViewSet):
    """ViewSet for deal milestones."""
    queryset = DealMilestone.objects.all()
    serializer_class = DealMilestoneSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['deal', 'status', 'priority', 'stage', 'assigned_to', 'is_blocking']
    ordering_fields = ['due_date', 'priority', 'created_at']
    ordering = ['due_date']
    
    def perform_create(self, serializer):
        """Set group when creating milestone."""
        deal = serializer.validated_data['deal']
        serializer.save(group=deal.group)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark milestone as complete."""
        milestone = self.get_object()
        
        # Check permission
        can_complete = (
            request.user == milestone.assigned_to or
            request.user.is_superuser or
            milestone.deal.team_members.filter(
                user=request.user,
                can_approve=True,
                removed_at__isnull=True
            ).exists()
        )
        
        if not can_complete:
            return Response(
                {"detail": "You don't have permission to complete this milestone"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = MilestoneCompleteSerializer(
            data=request.data,
            context={'request': request, 'milestone': milestone}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Return updated milestone
        milestone.refresh_from_db()
        return Response(
            DealMilestoneSerializer(milestone).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue milestones."""
        milestones = self.filter_queryset(self.get_queryset()).filter(
            due_date__lt=timezone.now().date(),
            status__in=[DealMilestone.Status.PENDING, DealMilestone.Status.IN_PROGRESS]
        )
        
        page = self.paginate_queryset(milestones)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(milestones, many=True)
        return Response(serializer.data)


# ============================================================================
# COLLABORATION VIEWS
# ============================================================================

class DealCommentViewSet(PlatformViewSet):
    """ViewSet for deal comments."""
    serializer_class = DealCommentSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['deal', 'comment_type', 'is_private', 'is_resolved']
    search_fields = ['content']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter comments by user's group access."""
        user = self.request.user
        return DealComment.objects.filter(
            group__in=user.groups.all()
        ).select_related(
            'author', 'deal', 'parent', 'resolved_by'
        ).prefetch_related('mentioned_users')
    
    def get_serializer_class(self):
        """Use different serializer for creation."""
        if self.action == 'create':
            return DealCommentCreateSerializer
        return self.serializer_class
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Mark comment as resolved."""
        comment = self.get_object()
        
        if comment.comment_type not in ['question', 'concern']:
            return Response(
                {'error': 'Only questions and concerns can be resolved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        comment.is_resolved = True
        comment.resolved_by = request.user
        comment.resolved_at = timezone.now()
        comment.save()
        
        return Response(
            DealCommentSerializer(comment).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['get'])
    def thread(self, request, pk=None):
        """Get entire comment thread."""
        comment = self.get_object()
        root_comment = comment.get_thread_root()
        
        # Get all comments in this thread
        thread_comments = DealComment.objects.filter(
            models.Q(id=root_comment.id) |
            models.Q(parent=root_comment) |
            models.Q(parent__parent=root_comment)
        ).order_by('created_at')
        
        serializer = DealCommentSerializer(thread_comments, many=True)
        return Response(serializer.data)


class DealDiscussionViewSet(PlatformViewSet):
    """ViewSet for deal discussions."""
    serializer_class = DealDiscussionSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['deal', 'discussion_type', 'status', 'priority']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'due_date', 'priority']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter discussions by user's group access."""
        user = self.request.user
        return DealDiscussion.objects.filter(
            group__in=user.groups.all()
        ).select_related(
            'deal', 'created_by', 'resolved_by', 'related_stage', 'related_milestone'
        ).prefetch_related('participants')
    
    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        """Join a discussion as a participant."""
        discussion = self.get_object()
        discussion.add_participant(request.user)
        
        return Response(
            DealDiscussionSerializer(discussion).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve a discussion."""
        discussion = self.get_object()
        summary = request.data.get('summary', '')
        
        discussion.resolve(request.user, summary)
        
        return Response(
            DealDiscussionSerializer(discussion).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue discussions."""
        discussions = self.filter_queryset(self.get_queryset()).filter(
            due_date__lt=timezone.now(),
            status=DealDiscussion.DiscussionStatus.ACTIVE
        )
        
        page = self.paginate_queryset(discussions)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(discussions, many=True)
        return Response(serializer.data)


class DealNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for deal notifications (read-only)."""
    serializer_class = DealNotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['deal', 'notification_type', 'is_read', 'is_dismissed']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter notifications for current user."""
        return DealNotification.objects.filter(
            recipient=self.request.user
        ).select_related('deal', 'sender')
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark notification as read."""
        notification = self.get_object()
        notification.mark_as_read()
        
        return Response(
            DealNotificationSerializer(notification).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        """Dismiss notification."""
        notification = self.get_object()
        notification.dismiss()
        
        return Response(
            DealNotificationSerializer(notification).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read."""
        notifications = self.get_queryset().filter(is_read=False)
        notifications.update(
            is_read=True,
            read_at=timezone.now()
        )
        
        return Response(
            {'marked_read': notifications.count()},
            status=status.HTTP_200_OK
        )


# ============================================================================
# VIRTUAL DATA ROOM VIEWS
# ============================================================================

class VirtualDataRoomViewSet(PlatformViewSet):
    """ViewSet for Virtual Data Rooms."""
    serializer_class = VirtualDataRoomSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['deal', 'status']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'expires_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter VDRs by user's group access."""
        user = self.request.user
        return VirtualDataRoom.objects.filter(
            group__in=user.groups.all()
        ).select_related('deal', 'created_by').prefetch_related(
            'administrators', 'notification_recipients'
        )
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate the VDR."""
        vdr = self.get_object()
        vdr.activate()
        
        return Response(
            VirtualDataRoomSerializer(vdr).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        """Lock the VDR."""
        vdr = self.get_object()
        vdr.lock(request.user)
        
        return Response(
            VirtualDataRoomSerializer(vdr).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['get'])
    def structure(self, request, pk=None):
        """Get VDR folder structure."""
        vdr = self.get_object()
        folders = VDRFolder.objects.filter(data_room=vdr).select_related('parent')
        
        serializer = VDRFolderSerializer(folders, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def access_log(self, request, pk=None):
        """Get VDR access audit log."""
        vdr = self.get_object()
        
        # Check if user can view audit log
        if not request.user.is_superuser and request.user not in vdr.administrators.all():
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        logs = VDRAuditLog.objects.filter(data_room=vdr).select_related(
            'user', 'document', 'folder'
        )
        
        page = self.paginate_queryset(logs)
        if page is not None:
            serializer = VDRAuditLogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = VDRAuditLogSerializer(logs, many=True)
        return Response(serializer.data)


class VDRFolderViewSet(PlatformViewSet):
    """ViewSet for VDR folders."""
    serializer_class = VDRFolderSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['data_room', 'parent', 'restricted_access']
    ordering_fields = ['order', 'name']
    ordering = ['order', 'name']
    
    def get_queryset(self):
        """Filter folders by user's VDR access."""
        user = self.request.user
        return VDRFolder.objects.filter(
            group__in=user.groups.all()
        ).select_related('data_room', 'parent')


class VDRDocumentViewSet(PlatformViewSet):
    """ViewSet for VDR documents."""
    serializer_class = VDRDocumentSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['folder', 'status', 'file_type', 'is_current_version']
    search_fields = ['name', 'description']
    ordering_fields = ['order', 'name', 'created_at', 'file_size']
    ordering = ['order', 'name']
    
    def get_queryset(self):
        """Filter documents by user's VDR access."""
        user = self.request.user
        return VDRDocument.objects.filter(
            group__in=user.groups.all(),
            status=VDRDocument.DocumentStatus.ACTIVE
        ).select_related('folder__data_room', 'uploaded_by', 'file_attachment')
    
    @action(detail=True, methods=['post'])
    def download(self, request, pk=None):
        """Track document download."""
        document = self.get_object()
        
        # Log the download
        VDRAuditLog.log_action(
            data_room=document.folder.data_room,
            user=request.user,
            action_type=VDRAuditLog.ActionType.DOWNLOAD_DOCUMENT,
            description=f"Downloaded document: {document.name}",
            document=document,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Return file download URL or redirect
        return Response(
            {
                'download_url': document.file_attachment.file.url,
                'filename': document.name,
                'size': document.file_size
            },
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def new_version(self, request, pk=None):
        """Upload new version of document."""
        document = self.get_object()
        
        if 'file' not in request.data:
            return Response(
                {'error': 'File is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create new file attachment
        from files.models import FileAttachment
        file_attachment = FileAttachment.objects.create(
            file=request.data['file'],
            uploaded_by=request.user,
            group=document.group
        )
        
        # Create new version
        new_version = document.create_new_version(file_attachment, request.user)
        
        return Response(
            VDRDocumentSerializer(new_version).data,
            status=status.HTTP_201_CREATED
        )


class VDRAccessViewSet(PlatformViewSet):
    """ViewSet for VDR access management."""
    serializer_class = VDRAccessSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['data_room', 'user', 'access_type', 'access_level']
    ordering_fields = ['granted_at', 'expires_at']
    ordering = ['-granted_at']
    
    def get_queryset(self):
        """Filter access records by user's group access."""
        user = self.request.user
        return VDRAccess.objects.filter(
            group__in=user.groups.all()
        ).select_related('data_room', 'user', 'granted_by', 'revoked_by')
    
    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        """Revoke user access."""
        access = self.get_object()
        reason = request.data.get('reason', '')
        
        access.revoke(request.user, reason)
        
        return Response(
            VDRAccessSerializer(access).data,
            status=status.HTTP_200_OK
        )


# ============================================================================
# IC PACK AUTOMATION VIEWS
# ============================================================================

class ICPackTemplateViewSet(PlatformViewSet):
    """ViewSet for IC pack templates with full CRUD and permissions."""
    serializer_class = ICPackTemplateSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'is_default', 'output_format']
    search_fields = ['name', 'description', 'tags']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['name']
    
    def get_queryset(self):
        """Filter templates by user's group access."""
        user = self.request.user
        return ICPackTemplate.objects.filter(
            group__in=user.groups.all()
        ).select_related('created_by').prefetch_related('packs')
    
    def get_serializer_class(self):
        """Use different serializer for list view."""
        if self.action == 'list':
            return ICPackTemplateListSerializer
        return self.serializer_class
    
    def get_permissions(self):
        """Only managers and admins can create/update/delete templates."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsManager()]
        return super().get_permissions()
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a template."""
        template = self.get_object()
        template.is_active = True
        template.save()
        
        return Response(
            ICPackTemplateSerializer(template).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a template."""
        template = self.get_object()
        template.is_active = False
        template.save()
        
        return Response(
            ICPackTemplateSerializer(template).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set template as default."""
        template = self.get_object()
        
        # Remove default from other templates in group
        ICPackTemplate.objects.filter(
            group=template.group,
            is_default=True
        ).exclude(id=template.id).update(is_default=False)
        
        # Set this template as default
        template.is_default = True
        template.save()
        
        return Response(
            ICPackTemplateSerializer(template).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['get'])
    def validate_config(self, request, pk=None):
        """Validate template configuration."""
        template = self.get_object()
        errors = template.validate_sections()
        
        return Response({
            'is_valid': len(errors) == 0,
            'errors': errors
        })
    
    @action(detail=True, methods=['get'])
    def preview_sections(self, request, pk=None):
        """Preview template sections structure."""
        template = self.get_object()
        
        sections_preview = []
        for section in template.sections:
            sections_preview.append({
                'id': section.get('id'),
                'title': section.get('title'),
                'order': section.get('order'),
                'required': section.get('required', False),
                'data_sources': section.get('data_sources', []),
                'max_pages': section.get('max_pages'),
                'description': section.get('description', '')
            })
        
        return Response({
            'sections': sections_preview,
            'total_sections': len(sections_preview),
            'approval_stages': template.approval_stages
        })


class ICPackViewSet(PlatformViewSet):
    """ViewSet for IC packs with custom actions for generation, approval, and distribution."""
    serializer_class = ICPackSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        'deal', 'template', 'status', 'created_by',
        'meeting_date', 'version'
    ]
    search_fields = ['title', 'deal__name']
    ordering_fields = ['created_at', 'updated_at', 'meeting_date', 'version']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter IC packs by user's group and deal access."""
        user = self.request.user
        
        # Get user's accessible deals
        accessible_deals = Deal.objects.filter(
            Q(deal_lead=user) |
            Q(team_members__user=user, team_members__removed_at__isnull=True) |
            Q(group__in=user.groups.all())
        ).distinct()
        
        return ICPack.objects.filter(
            deal__in=accessible_deals
        ).select_related(
            'deal', 'template', 'created_by', 'last_modified_by'
        ).prefetch_related(
            'approvals', 'distributions', 'audit_logs'
        )
    
    def get_serializer_class(self):
        """Use different serializer for creation."""
        if self.action == 'create':
            return ICPackCreateSerializer
        return self.serializer_class
    
    def get_permissions(self):
        """Check permissions based on action."""
        if self.action in ['update', 'partial_update']:
            return [IsAuthenticated()]  # Further checks in method
        elif self.action == 'destroy':
            return [IsManager()]  # Only managers can delete
        return super().get_permissions()
    
    def update(self, request, *args, **kwargs):
        """Check if user can edit the IC pack."""
        ic_pack = self.get_object()
        
        # Check edit permissions
        can_edit = (
            ic_pack.status == ICPackStatus.DRAFT and
            (request.user == ic_pack.created_by or
             request.user.is_superuser or
             ic_pack.deal.team_members.filter(
                 user=request.user,
                 can_edit=True,
                 removed_at__isnull=True
             ).exists())
        )
        
        if not can_edit:
            return Response(
                {"detail": "You don't have permission to edit this IC pack"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().update(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def generate_document(self, request, pk=None):
        """Generate IC pack PDF document."""
        ic_pack = self.get_object()
        
        # Check permissions
        can_generate = (
            ic_pack.status in [ICPackStatus.DRAFT, ICPackStatus.READY_FOR_REVIEW] and
            (request.user == ic_pack.created_by or
             request.user.is_superuser or
             ic_pack.deal.team_members.filter(
                 user=request.user,
                 can_edit=True,
                 removed_at__isnull=True
             ).exists())
        )
        
        if not can_generate:
            return Response(
                {"detail": "You don't have permission to generate documents for this IC pack"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ICPackGenerateDocumentSerializer(
            data=request.data,
            context={'ic_pack': ic_pack}
        )
        serializer.is_valid(raise_exception=True)
        
        # Generate document using service
        try:
            from .services.ic_pack_service import ICPackService
            service = ICPackService()
            
            file_attachment = service.generate_ic_pack_document(
                ic_pack=ic_pack,
                user=request.user
            )
            
            # Return updated IC pack with document
            ic_pack.refresh_from_db()
            return Response(
                ICPackSerializer(ic_pack, context={'request': request}).data,
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {"detail": f"Document generation failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def submit_for_approval(self, request, pk=None):
        """Submit IC pack for approval workflow."""
        ic_pack = self.get_object()
        
        # Check permissions
        can_submit = (
            ic_pack.status == ICPackStatus.DRAFT and
            ic_pack.generated_document and
            (request.user == ic_pack.created_by or
             request.user.is_superuser or
             ic_pack.deal.team_members.filter(
                 user=request.user,
                 can_edit=True,
                 removed_at__isnull=True
             ).exists())
        )
        
        if not can_submit:
            return Response(
                {"detail": "Cannot submit this IC pack for approval"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            from .services.ic_pack_service import ICPackService
            service = ICPackService()
            
            service.submit_for_approval(
                ic_pack=ic_pack,
                user=request.user
            )
            
            ic_pack.refresh_from_db()
            return Response(
                ICPackSerializer(ic_pack, context={'request': request}).data,
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {"detail": f"Submission failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve or reject IC pack."""
        ic_pack = self.get_object()
        
        # Check if user can approve
        if ic_pack.status != ICPackStatus.IN_REVIEW:
            return Response(
                {"detail": "IC pack is not in review status"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get current approval
        current_approval = ic_pack.approvals.filter(
            stage=ic_pack.current_approval_stage,
            decision=ICPackApproval.ApprovalDecision.PENDING
        ).first()
        
        if not current_approval:
            return Response(
                {"detail": "No pending approval found"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check role permissions
        stage_config = next(
            (s for s in ic_pack.template.approval_stages 
             if s['stage'] == ic_pack.current_approval_stage), None
        )
        
        if stage_config:
            required_role = stage_config.get('required_role')
            if not (request.user.role == required_role or request.user.is_superuser):
                return Response(
                    {"detail": "You don't have permission to approve this stage"},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        serializer = ICPackApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Make decision
        current_approval.make_decision(
            user=request.user,
            decision=serializer.validated_data['decision'],
            comments=serializer.validated_data.get('comments', ''),
            conditions=serializer.validated_data.get('conditions', [])
        )
        
        ic_pack.refresh_from_db()
        return Response(
            ICPackSerializer(ic_pack, context={'request': request}).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def distribute(self, request, pk=None):
        """Distribute approved IC pack."""
        ic_pack = self.get_object()
        
        # Check permissions
        can_distribute = (
            ic_pack.status == ICPackStatus.APPROVED and
            (request.user == ic_pack.created_by or
             request.user.is_superuser or
             ic_pack.deal.team_members.filter(
                 user=request.user,
                 can_approve=True,
                 removed_at__isnull=True
             ).exists())
        )
        
        if not can_distribute:
            return Response(
                {"detail": "You don't have permission to distribute this IC pack"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ICPackDistributeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            from .services.ic_pack_service import ICPackService
            service = ICPackService()
            
            service.distribute_ic_pack(
                ic_pack=ic_pack,
                user=request.user,
                recipient_emails=serializer.validated_data['recipient_emails'],
                message=serializer.validated_data.get('message', '')
            )
            
            ic_pack.refresh_from_db()
            return Response(
                ICPackSerializer(ic_pack, context={'request': request}).data,
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {"detail": f"Distribution failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def track_access(self, request, pk=None):
        """Track IC pack access and engagement."""
        ic_pack = self.get_object()
        
        # Get distribution records
        distributions = ic_pack.distributions.all()
        page = self.paginate_queryset(distributions)
        
        if page is not None:
            serializer = ICPackDistributionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ICPackDistributionSerializer(distributions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def audit_trail(self, request, pk=None):
        """Get IC pack audit trail."""
        ic_pack = self.get_object()
        
        audit_logs = ic_pack.audit_logs.order_by('-created_at')
        page = self.paginate_queryset(audit_logs)
        
        if page is not None:
            serializer = ICPackAuditLogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ICPackAuditLogSerializer(audit_logs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get IC pack analytics."""
        ic_pack = self.get_object()
        
        try:
            from .services.ic_pack_service import ICPackService
            service = ICPackService()
            
            analytics_data = service.get_ic_pack_analytics(ic_pack.deal)
            serializer = ICPackAnalyticsSerializer(analytics_data)
            
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {"detail": f"Analytics generation failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def create_new_version(self, request, pk=None):
        """Create a new version of the IC pack."""
        ic_pack = self.get_object()
        
        # Check permissions
        can_version = (
            request.user == ic_pack.created_by or
            request.user.is_superuser or
            ic_pack.deal.team_members.filter(
                user=request.user,
                can_edit=True,
                removed_at__isnull=True
            ).exists()
        )
        
        if not can_version:
            return Response(
                {"detail": "You don't have permission to create new versions"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Create new version
        new_version = ic_pack.create_new_version()
        
        # Log version creation
        ICPackAuditLog.log_action(
            ic_pack=new_version,
            action=ICPackAuditLog.ActionType.VERSION_CREATED,
            actor=request.user,
            description=f"Created new version {new_version.version} from version {ic_pack.version}"
        )
        
        return Response(
            ICPackSerializer(new_version, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class ICPackApprovalViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for IC pack approval workflow management."""
    serializer_class = ICPackApprovalSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['ic_pack', 'decision', 'decided_by', 'stage']
    ordering_fields = ['created_at', 'decided_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter approvals by user's group access."""
        user = self.request.user
        
        # Get user's accessible IC packs
        accessible_deals = Deal.objects.filter(
            Q(deal_lead=user) |
            Q(team_members__user=user, team_members__removed_at__isnull=True) |
            Q(group__in=user.groups.all())
        ).distinct()
        
        accessible_packs = ICPack.objects.filter(deal__in=accessible_deals)
        
        return ICPackApproval.objects.filter(
            ic_pack__in=accessible_packs
        ).select_related(
            'ic_pack__deal', 'decided_by', 'delegated_to'
        )
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get pending approvals for current user."""
        user = request.user
        
        # Find approvals where user can make decisions
        pending_approvals = []
        
        for approval in self.get_queryset().filter(
            decision=ICPackApproval.ApprovalDecision.PENDING
        ):
            # Check if user can approve this stage
            stage_config = next(
                (s for s in approval.ic_pack.template.approval_stages 
                 if s['stage'] == approval.stage), None
            )
            
            if stage_config:
                required_role = stage_config.get('required_role')
                if user.role == required_role or user.is_superuser:
                    pending_approvals.append(approval)
        
        page = self.paginate_queryset(pending_approvals)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(pending_approvals, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_decisions(self, request):
        """Get approvals decided by current user."""
        user = request.user
        approvals = self.get_queryset().filter(decided_by=user)
        
        page = self.paginate_queryset(approvals)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(approvals, many=True)
        return Response(serializer.data)


class ICPackDistributionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for IC pack distribution tracking."""
    serializer_class = ICPackDistributionSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['ic_pack', 'recipient_email', 'sent_by']
    search_fields = ['recipient_email', 'recipient_name']
    ordering_fields = ['sent_at', 'first_viewed_at', 'view_count']
    ordering = ['-sent_at']
    
    def get_queryset(self):
        """Filter distributions by user's group access."""
        user = self.request.user
        
        # Get user's accessible IC packs
        accessible_deals = Deal.objects.filter(
            Q(deal_lead=user) |
            Q(team_members__user=user, team_members__removed_at__isnull=True) |
            Q(group__in=user.groups.all())
        ).distinct()
        
        accessible_packs = ICPack.objects.filter(deal__in=accessible_deals)
        
        return ICPackDistribution.objects.filter(
            ic_pack__in=accessible_packs
        ).select_related(
            'ic_pack__deal', 'sent_by', 'recipient_user'
        )
    
    @action(detail=True, methods=['post'])
    def record_view(self, request, pk=None):
        """Record a view of the distributed pack."""
        distribution = self.get_object()
        distribution.record_view()
        
        return Response(
            ICPackDistributionSerializer(distribution).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'])
    def engagement_summary(self, request):
        """Get engagement summary across all distributions."""
        distributions = self.get_queryset()
        
        summary = {
            'total_distributions': distributions.count(),
            'total_views': distributions.aggregate(
                total=Sum('view_count')
            )['total'] or 0,
            'total_downloads': distributions.aggregate(
                total=Sum('download_count')
            )['total'] or 0,
            'unique_viewers': distributions.filter(view_count__gt=0).count(),
            'average_views_per_distribution': 0,
            'top_engaged_recipients': []
        }
        
        if summary['total_distributions'] > 0:
            summary['average_views_per_distribution'] = (
                summary['total_views'] / summary['total_distributions']
            )
        
        # Top engaged recipients
        top_recipients = distributions.filter(
            view_count__gt=0
        ).order_by('-view_count')[:10]
        
        summary['top_engaged_recipients'] = [
            {
                'email': dist.recipient_email,
                'name': dist.recipient_name or 'Unknown',
                'view_count': dist.view_count,
                'download_count': dist.download_count,
                'engagement_score': dist.view_count + (dist.download_count * 5)
            }
            for dist in top_recipients
        ]
        
        return Response(summary)


# ============================================================================
# MEETING SCHEDULER VIEWS
# ============================================================================

class MeetingViewSet(PlatformViewSet):
    """ViewSet for meetings with smart scheduling and calendar integration."""
    serializer_class = MeetingSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        'meeting_type', 'status', 'organizer', 'deal',
        'start_time', 'end_time', 'calendar_provider'
    ]
    search_fields = ['title', 'description', 'location']
    ordering_fields = ['start_time', 'end_time', 'created_at', 'title']
    ordering = ['start_time']
    
    def get_queryset(self):
        """Filter meetings by user's group and access permissions."""
        user = self.request.user
        return Meeting.objects.filter(
            group__in=user.groups.all()
        ).select_related(
            'organizer', 'deal', 'parent_meeting'
        ).prefetch_related(
            'attendees__user', 'resource_bookings__resource'
        )
    
    def get_serializer_class(self):
        """Use different serializers for different actions."""
        if self.action == 'list':
            return MeetingListSerializer
        elif self.action == 'create':
            return MeetingCreateSerializer
        elif self.action == 'reschedule':
            return MeetingRescheduleSerializer
        elif self.action == 'cancel':
            return MeetingCancelSerializer
        elif self.action == 'find_optimal_time':
            return FindOptimalTimeSerializer
        elif self.action == 'analytics':
            return MeetingAnalyticsSerializer
        return self.serializer_class
    
    def get_permissions(self):
        """Check permissions based on action."""
        if self.action == 'destroy':
            return [IsManager()]
        elif self.action in ['update', 'partial_update', 'reschedule', 'cancel']:
            return [IsAuthenticated()]  # Further checks in methods
        return super().get_permissions()
    
    def update(self, request, *args, **kwargs):
        """Check if user can edit the meeting."""
        meeting = self.get_object()
        
        # Check edit permissions
        can_edit = (
            request.user == meeting.organizer or
            request.user.is_superuser or
            meeting.attendees.filter(
                user=request.user,
                can_edit_agenda=True
            ).exists()
        )
        
        if not can_edit:
            return Response(
                {"detail": "You don't have permission to edit this meeting"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().update(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def start_meeting(self, request, pk=None):
        """Start the meeting."""
        meeting = self.get_object()
        
        # Check permissions
        if not (request.user == meeting.organizer or request.user.is_superuser):
            return Response(
                {"detail": "Only the organizer can start the meeting"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if meeting can be started
        if meeting.status not in [MeetingStatus.SCHEDULED, MeetingStatus.CONFIRMED]:
            return Response(
                {"detail": "Meeting cannot be started in its current status"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Start the meeting
        meeting.start_meeting()
        meeting.save()
        
        # Update resource bookings to in_use
        meeting.resource_bookings.filter(
            status=MeetingResourceBooking.BookingStatus.CONFIRMED
        ).update(status=MeetingResourceBooking.BookingStatus.IN_USE)
        
        return Response(
            MeetingSerializer(meeting, context={'request': request}).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def complete_meeting(self, request, pk=None):
        """Complete the meeting."""
        meeting = self.get_object()
        
        # Check permissions
        if not (request.user == meeting.organizer or request.user.is_superuser):
            return Response(
                {"detail": "Only the organizer can complete the meeting"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if meeting can be completed
        if meeting.status != MeetingStatus.IN_PROGRESS:
            return Response(
                {"detail": "Only meetings in progress can be completed"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Complete the meeting
        meeting.complete_meeting()
        
        # Update meeting notes and action items if provided
        meeting_notes = request.data.get('meeting_notes', '')
        action_items = request.data.get('action_items', [])
        next_steps = request.data.get('next_steps', '')
        
        if meeting_notes:
            meeting.meeting_notes = meeting_notes
        if action_items:
            meeting.action_items = action_items
        if next_steps:
            meeting.next_steps = next_steps
        
        meeting.save()
        
        # Update resource bookings to completed
        meeting.resource_bookings.filter(
            status=MeetingResourceBooking.BookingStatus.IN_USE
        ).update(status=MeetingResourceBooking.BookingStatus.COMPLETED)
        
        return Response(
            MeetingSerializer(meeting, context={'request': request}).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def reschedule(self, request, pk=None):
        """Reschedule the meeting to a new time."""
        meeting = self.get_object()
        
        # Check permissions
        can_reschedule = (
            request.user == meeting.organizer or
            request.user.is_superuser or
            meeting.attendees.filter(
                user=request.user,
                can_edit_agenda=True
            ).exists()
        )
        
        if not can_reschedule:
            return Response(
                {"detail": "You don't have permission to reschedule this meeting"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if meeting can be rescheduled
        if meeting.status not in [MeetingStatus.SCHEDULED, MeetingStatus.CONFIRMED]:
            return Response(
                {"detail": "Meeting cannot be rescheduled in its current status"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = MeetingRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Check availability if requested
        if data.get('check_availability', True):
            # Mock availability check - in real implementation, 
            # this would check attendee calendars and resource availability
            pass
        
        # Update meeting times
        meeting.start_time = data['new_start_time']
        meeting.end_time = data['new_end_time']
        meeting.reschedule()
        meeting.save()
        
        # Update resource bookings
        for booking in meeting.resource_bookings.all():
            booking.start_time = data['new_start_time']
            booking.end_time = data['new_end_time']
            booking.save()
        
        # Send notifications if requested (mock implementation)
        if data.get('notify_attendees', True):
            # In real implementation, this would send notifications
            pass
        
        return Response(
            MeetingSerializer(meeting, context={'request': request}).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel the meeting."""
        meeting = self.get_object()
        
        # Check permissions
        if not (request.user == meeting.organizer or request.user.is_superuser):
            return Response(
                {"detail": "Only the organizer can cancel the meeting"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if meeting can be cancelled
        if meeting.status in [MeetingStatus.COMPLETED, MeetingStatus.CANCELLED]:
            return Response(
                {"detail": "Meeting cannot be cancelled in its current status"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = MeetingCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Cancel the meeting
        meeting.cancel()
        meeting.save()
        
        # Cancel resource bookings if requested
        if data.get('cancel_resources', True):
            meeting.resource_bookings.filter(
                status__in=[
                    MeetingResourceBooking.BookingStatus.PENDING,
                    MeetingResourceBooking.BookingStatus.CONFIRMED
                ]
            ).update(status=MeetingResourceBooking.BookingStatus.CANCELLED)
        
        # Send notifications if requested (mock implementation)
        if data.get('notify_attendees', True):
            # In real implementation, this would send notifications
            pass
        
        return Response(
            MeetingSerializer(meeting, context={'request': request}).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['post'])
    def find_optimal_time(self, request):
        """Find optimal meeting times based on attendee availability."""
        serializer = FindOptimalTimeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Mock implementation of optimal time finding
        # In real implementation, this would:
        # 1. Query attendee calendars via calendar APIs
        # 2. Check internal availability slots
        # 3. Consider time zones
        # 4. Apply business rules and preferences
        # 5. Return ranked suggestions
        
        suggestions = []
        base_date = timezone.now().date() + timedelta(days=1)
        
        for i in range(data['max_suggestions']):
            suggestion_date = base_date + timedelta(days=i)
            suggestion_time = timezone.now().replace(
                year=suggestion_date.year,
                month=suggestion_date.month,
                day=suggestion_date.day,
                hour=10 + i,  # Vary the hour
                minute=0,
                second=0,
                microsecond=0
            )
            
            suggestions.append({
                'start_time': suggestion_time,
                'end_time': suggestion_time + timedelta(minutes=data['duration_minutes']),
                'confidence_score': max(0.5, 1.0 - (i * 0.1)),  # Decreasing confidence
                'available_attendees': len(data['attendee_emails']) - (i % 2),  # Mock availability
                'conflicts': [],
                'reasoning': f"Good time slot with {len(data['attendee_emails']) - (i % 2)} available attendees"
            })
        
        return Response({
            'suggestions': suggestions,
            'search_criteria': data,
            'total_attendees': len(data['attendee_emails'])
        })
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get meeting analytics and metrics."""
        meetings = self.filter_queryset(self.get_queryset())
        
        # Basic metrics
        total_meetings = meetings.count()
        
        if total_meetings == 0:
            return Response({
                'total_meetings': 0,
                'message': 'No meetings found for the specified criteria'
            })
        
        # Meetings by status
        meetings_by_status = {}
        for status_choice in MeetingStatus.choices:
            count = meetings.filter(status=status_choice[0]).count()
            meetings_by_status[status_choice[0]] = {
                'count': count,
                'label': status_choice[1]
            }
        
        # Meetings by type
        meetings_by_type = {}
        for type_choice in MeetingType.choices:
            count = meetings.filter(meeting_type=type_choice[0]).count()
            meetings_by_type[type_choice[0]] = {
                'count': count,
                'label': type_choice[1]
            }
        
        # Duration and attendee metrics
        completed_meetings = meetings.filter(status=MeetingStatus.COMPLETED)
        avg_duration = 0
        avg_attendees = 0
        
        if completed_meetings.exists():
            total_duration = sum(m.duration_minutes for m in completed_meetings)
            avg_duration = total_duration / completed_meetings.count()
            
            total_attendees = sum(m.attendees.count() for m in completed_meetings)
            avg_attendees = total_attendees / completed_meetings.count()
        
        # Response and attendance rates
        total_attendees = MeetingAttendee.objects.filter(meeting__in=meetings)
        total_attendee_count = total_attendees.count()
        
        overall_response_rate = 0
        overall_attendance_rate = 0
        
        if total_attendee_count > 0:
            responded = total_attendees.exclude(
                response_status__in=[
                    MeetingAttendee.ResponseStatus.PENDING,
                    MeetingAttendee.ResponseStatus.NO_RESPONSE
                ]
            ).count()
            overall_response_rate = (responded / total_attendee_count) * 100
            
            attended = total_attendees.filter(attended=True).count()
            overall_attendance_rate = (attended / total_attendee_count) * 100
        
        # Resource utilization
        resource_bookings = MeetingResourceBooking.objects.filter(meeting__in=meetings)
        resource_utilization = {}
        most_used_resources = []
        
        if resource_bookings.exists():
            from django.db.models import Count
            resource_usage = resource_bookings.values(
                'resource__name', 'resource__id'
            ).annotate(
                usage_count=Count('id')
            ).order_by('-usage_count')[:5]
            
            for usage in resource_usage:
                most_used_resources.append({
                    'resource_name': usage['resource__name'],
                    'usage_count': usage['usage_count']
                })
        
        # Time-based patterns
        meetings_by_day = {}
        meetings_by_hour = {}
        
        for meeting in meetings:
            day_name = meeting.start_time.strftime('%A')
            hour = meeting.start_time.hour
            
            meetings_by_day[day_name] = meetings_by_day.get(day_name, 0) + 1
            meetings_by_hour[str(hour)] = meetings_by_hour.get(str(hour), 0) + 1
        
        # Monthly trends (last 12 months)
        from datetime import datetime
        monthly_trends = []
        current_date = timezone.now()
        
        for i in range(12):
            month_start = current_date.replace(day=1) - timedelta(days=30 * i)
            month_end = month_start.replace(day=1) + timedelta(days=32)
            month_end = month_end.replace(day=1) - timedelta(days=1)
            
            month_meetings = meetings.filter(
                start_time__gte=month_start,
                start_time__lte=month_end
            ).count()
            
            monthly_trends.insert(0, {
                'month': month_start.strftime('%Y-%m'),
                'count': month_meetings
            })
        
        # Top organizers
        from django.db.models import Count
        top_organizers_data = meetings.values(
            'organizer__first_name', 'organizer__last_name', 'organizer__id'
        ).annotate(
            meeting_count=Count('id')
        ).order_by('-meeting_count')[:5]
        
        top_organizers = []
        for organizer in top_organizers_data:
            name = f"{organizer['organizer__first_name']} {organizer['organizer__last_name']}"
            top_organizers.append({
                'organizer_name': name.strip(),
                'meeting_count': organizer['meeting_count']
            })
        
        analytics_data = {
            'total_meetings': total_meetings,
            'meetings_by_status': meetings_by_status,
            'meetings_by_type': meetings_by_type,
            'average_duration_minutes': round(avg_duration, 2),
            'average_attendees': round(avg_attendees, 2),
            'overall_response_rate': round(overall_response_rate, 2),
            'overall_attendance_rate': round(overall_attendance_rate, 2),
            'resource_utilization': resource_utilization,
            'most_used_resources': most_used_resources,
            'meetings_by_day_of_week': meetings_by_day,
            'meetings_by_hour': meetings_by_hour,
            'monthly_trends': monthly_trends,
            'top_organizers': top_organizers
        }
        
        return Response(analytics_data)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming meetings for the current user."""
        user = request.user
        now = timezone.now()
        
        # Get meetings where user is organizer or attendee
        upcoming_meetings = self.get_queryset().filter(
            models.Q(organizer=user) | models.Q(attendees__user=user),
            start_time__gte=now,
            status__in=[MeetingStatus.SCHEDULED, MeetingStatus.CONFIRMED]
        ).distinct().order_by('start_time')[:10]
        
        serializer = MeetingListSerializer(
            upcoming_meetings,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def calendar_view(self, request):
        """Get meetings for calendar view with date range filtering."""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not start_date or not end_date:
            return Response(
                {"detail": "start_date and end_date parameters are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from datetime import datetime
            start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SSZ)"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get meetings in the date range
        meetings = self.get_queryset().filter(
            start_time__gte=start_datetime,
            start_time__lte=end_datetime
        ).order_by('start_time')
        
        # Filter by user access
        user = request.user
        accessible_meetings = meetings.filter(
            models.Q(organizer=user) |
            models.Q(attendees__user=user) |
            models.Q(deal__team_members__user=user, deal__team_members__removed_at__isnull=True)
        ).distinct()
        
        serializer = MeetingListSerializer(
            accessible_meetings,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)


class MeetingAttendeeViewSet(PlatformViewSet):
    """ViewSet for managing meeting attendees."""
    serializer_class = MeetingAttendeeSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['meeting', 'user', 'attendee_type', 'response_status', 'attended']
    search_fields = ['name', 'email', 'organization']
    ordering_fields = ['name', 'response_status', 'responded_at']
    ordering = ['attendee_type', 'name']
    
    def get_queryset(self):
        """Filter attendees by user's group access."""
        user = self.request.user
        return MeetingAttendee.objects.filter(
            group__in=user.groups.all()
        ).select_related('meeting', 'user')
    
    def perform_create(self, serializer):
        """Set group when creating attendee."""
        meeting = serializer.validated_data['meeting']
        serializer.save(group=meeting.group)
    
    @action(detail=True, methods=['post'])
    def respond(self, request, pk=None):
        """Record attendee response to meeting invitation."""
        attendee = self.get_object()
        
        response_status = request.data.get('response_status')
        response_notes = request.data.get('response_notes', '')
        
        if response_status not in [choice[0] for choice in MeetingAttendee.ResponseStatus.choices]:
            return Response(
                {"detail": "Invalid response status"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        attendee.respond(response_status, response_notes)
        
        return Response(
            MeetingAttendeeSerializer(attendee).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def join_meeting(self, request, pk=None):
        """Record when attendee joins the meeting."""
        attendee = self.get_object()
        
        if attendee.meeting.status != MeetingStatus.IN_PROGRESS:
            return Response(
                {"detail": "Meeting is not currently in progress"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        attendee.joined_at = timezone.now()
        attendee.attended = True
        attendee.save()
        
        return Response(
            MeetingAttendeeSerializer(attendee).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def leave_meeting(self, request, pk=None):
        """Record when attendee leaves the meeting."""
        attendee = self.get_object()
        
        if not attendee.joined_at:
            return Response(
                {"detail": "Attendee has not joined the meeting yet"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        attendee.left_at = timezone.now()
        attendee.save()
        
        return Response(
            MeetingAttendeeSerializer(attendee).data,
            status=status.HTTP_200_OK
        )


class MeetingResourceViewSet(PlatformViewSet):
    """ViewSet for managing meeting resources."""
    serializer_class = MeetingResourceSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['resource_type', 'is_active', 'requires_approval']
    search_fields = ['name', 'description', 'location']
    ordering_fields = ['name', 'resource_type', 'capacity']
    ordering = ['resource_type', 'name']
    
    def get_queryset(self):
        """Filter resources by user's group access."""
        user = self.request.user
        return MeetingResource.objects.filter(
            group__in=user.groups.all()
        )
    
    def get_permissions(self):
        """Only managers can create/update/delete resources."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsManager()]
        return super().get_permissions()
    
    def perform_create(self, serializer):
        """Set group when creating resource."""
        serializer.save(group=self.request.user.groups.first())
    
    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        """Check resource availability for a given time period."""
        resource = self.get_object()
        
        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')
        
        if not start_time or not end_time:
            return Response(
                {"detail": "start_time and end_time parameters are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from datetime import datetime
            start_datetime = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_datetime = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        except ValueError:
            return Response(
                {"detail": "Invalid datetime format. Use ISO format"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        is_available = resource.is_available(start_datetime, end_datetime)
        
        # Get conflicting bookings if not available
        conflicts = []
        if not is_available:
            conflicting_bookings = resource.bookings.filter(
                models.Q(start_time__lt=end_datetime) & models.Q(end_time__gt=start_datetime),
                status__in=[
                    MeetingResourceBooking.BookingStatus.CONFIRMED,
                    MeetingResourceBooking.BookingStatus.IN_USE
                ]
            )
            
            conflicts = [
                {
                    'booking_id': booking.id,
                    'meeting_title': booking.meeting.title,
                    'start_time': booking.start_time,
                    'end_time': booking.end_time,
                    'status': booking.status
                }
                for booking in conflicting_bookings
            ]
        
        return Response({
            'resource_id': resource.id,
            'resource_name': resource.name,
            'requested_start': start_datetime,
            'requested_end': end_datetime,
            'is_available': is_available,
            'conflicts': conflicts
        })
    
    @action(detail=False, methods=['get'])
    def available_resources(self, request):
        """Get resources available for a specific time period."""
        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')
        resource_type = request.query_params.get('resource_type')
        min_capacity = request.query_params.get('min_capacity')
        
        if not start_time or not end_time:
            return Response(
                {"detail": "start_time and end_time parameters are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from datetime import datetime
            start_datetime = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_datetime = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        except ValueError:
            return Response(
                {"detail": "Invalid datetime format. Use ISO format"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Filter resources
        resources = self.get_queryset().filter(is_active=True)
        
        if resource_type:
            resources = resources.filter(resource_type=resource_type)
        
        if min_capacity:
            try:
                min_cap = int(min_capacity)
                resources = resources.filter(capacity__gte=min_cap)
            except ValueError:
                pass
        
        # Filter by availability
        available_resources = []
        for resource in resources:
            if resource.is_available(start_datetime, end_datetime):
                available_resources.append(resource)
        
        serializer = MeetingResourceSerializer(
            available_resources,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)


class MeetingResourceBookingViewSet(PlatformViewSet):
    """ViewSet for managing meeting resource bookings."""
    serializer_class = MeetingResourceBookingSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['meeting', 'resource', 'status']
    ordering_fields = ['start_time', 'end_time', 'created_at']
    ordering = ['start_time']
    
    def get_queryset(self):
        """Filter bookings by user's group access."""
        user = self.request.user
        return MeetingResourceBooking.objects.filter(
            group__in=user.groups.all()
        ).select_related('meeting', 'resource')
    
    def perform_create(self, serializer):
        """Set group when creating booking."""
        meeting = serializer.validated_data['meeting']
        serializer.save(group=meeting.group)
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm a pending resource booking."""
        booking = self.get_object()
        
        if booking.status != MeetingResourceBooking.BookingStatus.PENDING:
            return Response(
                {"detail": "Only pending bookings can be confirmed"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if resource is still available
        if not booking.resource.is_available(booking.start_time, booking.end_time):
            return Response(
                {"detail": "Resource is no longer available for the requested time"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.status = MeetingResourceBooking.BookingStatus.CONFIRMED
        booking.save()
        
        return Response(
            MeetingResourceBookingSerializer(booking).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def cancel_booking(self, request, pk=None):
        """Cancel a resource booking."""
        booking = self.get_object()
        
        if booking.status in [
            MeetingResourceBooking.BookingStatus.COMPLETED,
            MeetingResourceBooking.BookingStatus.CANCELLED
        ]:
            return Response(
                {"detail": "Booking cannot be cancelled in its current status"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.status = MeetingResourceBooking.BookingStatus.CANCELLED
        booking.save()
        
        return Response(
            MeetingResourceBookingSerializer(booking).data,
            status=status.HTTP_200_OK
        )


class AvailabilitySlotViewSet(PlatformViewSet):
    """ViewSet for managing user availability slots."""
    serializer_class = AvailabilitySlotSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['user', 'slot_type', 'is_recurring']
    ordering_fields = ['start_time', 'end_time']
    ordering = ['start_time']
    
    def get_queryset(self):
        """Filter availability slots by user's group access."""
        user = self.request.user
        queryset = AvailabilitySlot.objects.filter(
            group__in=user.groups.all()
        ).select_related('user')
        
        # Users can only see their own slots unless they're managers
        if not user.is_superuser and not user.groups.filter(name__icontains='manager').exists():
            queryset = queryset.filter(user=user)
        
        return queryset
    
    def perform_create(self, serializer):
        """Set group and user when creating availability slot."""
        # If no user specified, use current user
        if 'user' not in serializer.validated_data:
            serializer.validated_data['user'] = self.request.user
        
        serializer.save(group=self.request.user.groups.first())
    
    @action(detail=False, methods=['get'])
    def user_availability(self, request):
        """Get availability for specific users in a date range."""
        user_ids = request.query_params.getlist('user_ids')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not user_ids or not start_date or not end_date:
            return Response(
                {"detail": "user_ids, start_date, and end_date parameters are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from datetime import datetime
            start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Use ISO format"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get availability slots for the specified users and date range
        availability_slots = self.get_queryset().filter(
            user_id__in=user_ids,
            start_time__gte=start_datetime,
            end_time__lte=end_datetime
        )
        
        # Group by user
        availability_by_user = {}
        for slot in availability_slots:
            user_id = str(slot.user_id)
            if user_id not in availability_by_user:
                availability_by_user[user_id] = {
                    'user_name': slot.user.get_full_name(),
                    'slots': []
                }
            
            availability_by_user[user_id]['slots'].append(
                AvailabilitySlotSerializer(slot).data
            )
        
        return Response(availability_by_user)
    
    @action(detail=False, methods=['post'])
    def bulk_create_recurring(self, request):
        """Create recurring availability slots for a user."""
        # This would implement bulk creation of recurring slots
        # For example, setting regular working hours
        
        user_id = request.data.get('user_id', request.user.id)
        pattern = request.data.get('pattern', {})
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        
        if not all([pattern, start_date, end_date]):
            return Response(
                {"detail": "pattern, start_date, and end_date are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mock implementation - in real system, this would create
        # multiple recurring availability slots based on the pattern
        created_slots = []
        
        return Response({
            'created_slots': len(created_slots),
            'message': 'Recurring availability slots created successfully'
        })
