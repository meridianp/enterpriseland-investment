"""
API views for outreach sequence management.

This module provides REST API endpoints for creating, managing, and monitoring
outreach sequences, including enrollment management and analytics.
"""

from typing import Dict, Any
from django.db.models import Q, Count, Avg, Sum, F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters import rest_framework as filters

from accounts.permissions import (
    IsOwnerOrReadOnly,
    GroupAccessPermission
)
from .models_outreach import (
    OutreachSequence,
    SequenceStep,
    SequenceEnrollment,
    SequenceStepExecution,
    SequenceTemplate
)
from .models import Contact
from .serializers_outreach import (
    OutreachSequenceSerializer,
    OutreachSequenceDetailSerializer,
    SequenceStepSerializer,
    SequenceEnrollmentSerializer,
    SequenceEnrollmentDetailSerializer,
    SequenceTemplateSerializer,
    SequenceAnalyticsSerializer,
    EnrollmentCreateSerializer
)
from .tasks_outreach import start_sequence_enrollment


class OutreachSequenceFilter(filters.FilterSet):
    """Filter for outreach sequences."""
    status = filters.ChoiceFilter(choices=OutreachSequence.Status.choices)
    trigger_type = filters.ChoiceFilter(choices=OutreachSequence.TriggerType.choices)
    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    search = filters.CharFilter(method='search_filter')
    
    def search_filter(self, queryset, name, value):
        """Search in name and description."""
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value)
        )
    
    class Meta:
        model = OutreachSequence
        fields = ['status', 'trigger_type', 'created_by']


class OutreachSequenceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing outreach sequences.
    
    Provides CRUD operations and additional actions for sequence management.
    """
    queryset = OutreachSequence.objects.all()
    serializer_class = OutreachSequenceSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filterset_class = OutreachSequenceFilter
    ordering_fields = ['created_at', 'name', 'total_enrolled']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return OutreachSequenceDetailSerializer
        return super().get_serializer_class()
    
    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            group=self.request.user.group
        )
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a sequence."""
        sequence = self.get_object()
        
        # Validate sequence has steps
        if not sequence.steps.exists():
            return Response(
                {"error": "Cannot activate sequence without steps"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            sequence.activate()
            sequence.save()
            return Response(
                OutreachSequenceDetailSerializer(sequence).data
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause an active sequence."""
        sequence = self.get_object()
        
        try:
            sequence.pause()
            sequence.save()
            
            # Pause all active enrollments
            sequence.enrollments.filter(
                status=SequenceEnrollment.Status.ACTIVE
            ).update(status=SequenceEnrollment.Status.PAUSED)
            
            return Response(
                OutreachSequenceDetailSerializer(sequence).data
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Resume a paused sequence."""
        sequence = self.get_object()
        
        try:
            sequence.resume()
            sequence.save()
            
            # Resume paused enrollments
            sequence.enrollments.filter(
                status=SequenceEnrollment.Status.PAUSED
            ).update(status=SequenceEnrollment.Status.ACTIVE)
            
            return Response(
                OutreachSequenceDetailSerializer(sequence).data
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate a sequence with all its steps."""
        sequence = self.get_object()
        
        # Create new sequence
        new_sequence = OutreachSequence.objects.create(
            name=f"{sequence.name} (Copy)",
            description=sequence.description,
            group=request.user.group,
            created_by=request.user,
            trigger_type=sequence.trigger_type,
            trigger_conditions=sequence.trigger_conditions,
            skip_weekends=sequence.skip_weekends,
            timezone_optimized=sequence.timezone_optimized,
            optimal_send_hour=sequence.optimal_send_hour,
            exit_on_reply=sequence.exit_on_reply,
            exit_on_click=sequence.exit_on_click,
            exit_on_conversion=sequence.exit_on_conversion,
            exit_tags=sequence.exit_tags,
            goal_description=sequence.goal_description,
            conversion_url_pattern=sequence.conversion_url_pattern
        )
        
        # Duplicate steps
        for step in sequence.steps.all():
            SequenceStep.objects.create(
                sequence=new_sequence,
                group=request.user.group,
                step_type=step.step_type,
                order=step.order,
                name=step.name,
                delay_days=step.delay_days,
                delay_hours=step.delay_hours,
                day_type=step.day_type,
                email_template=step.email_template,
                email_subject=step.email_subject,
                condition_type=step.condition_type,
                condition_config=step.condition_config,
                action_type=step.action_type,
                action_config=step.action_config,
                is_variant=step.is_variant,
                variant_group=step.variant_group,
                variant_percentage=step.variant_percentage
            )
        
        return Response(
            OutreachSequenceDetailSerializer(new_sequence).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get sequence analytics."""
        sequence = self.get_object()
        
        # Calculate analytics
        enrollments = sequence.enrollments.all()
        active_enrollments = enrollments.filter(
            status=SequenceEnrollment.Status.ACTIVE
        )
        
        # Step performance
        step_performance = []
        for step in sequence.steps.filter(step_type=SequenceStep.StepType.EMAIL):
            if step.total_sent > 0:
                open_rate = (step.total_opened / step.total_sent) * 100
                click_rate = (step.total_clicked / step.total_sent) * 100
            else:
                open_rate = 0
                click_rate = 0
                
            step_performance.append({
                'step_id': step.id,
                'step_name': step.name,
                'step_order': step.order,
                'total_sent': step.total_sent,
                'total_opened': step.total_opened,
                'total_clicked': step.total_clicked,
                'total_replied': step.total_replied,
                'open_rate': round(open_rate, 2),
                'click_rate': round(click_rate, 2)
            })
        
        # Conversion funnel
        total_enrolled = sequence.total_enrolled
        conversion_funnel = []
        
        if total_enrolled > 0:
            for step in sequence.steps.order_by('order'):
                reached = enrollments.filter(
                    current_step_index__gte=step.order
                ).count()
                
                conversion_funnel.append({
                    'step_name': step.name,
                    'step_order': step.order,
                    'contacts_reached': reached,
                    'percentage': round((reached / total_enrolled) * 100, 2)
                })
        
        # Exit reasons breakdown
        exit_reasons = enrollments.exclude(
            exit_reason=''
        ).values('exit_reason').annotate(
            count=Count('id')
        ).order_by('-count')
        
        analytics_data = {
            'sequence_id': sequence.id,
            'sequence_name': sequence.name,
            'total_enrolled': total_enrolled,
            'total_active': active_enrollments.count(),
            'total_completed': sequence.total_completed,
            'total_converted': sequence.total_converted,
            'conversion_rate': round(
                (sequence.total_converted / total_enrolled * 100) if total_enrolled > 0 else 0,
                2
            ),
            'average_days_to_complete': enrollments.filter(
                status=SequenceEnrollment.Status.COMPLETED
            ).aggregate(
                avg_days=Avg(F('exited_at') - F('created_at'))
            )['avg_days'],
            'step_performance': step_performance,
            'conversion_funnel': conversion_funnel,
            'exit_reasons': list(exit_reasons)
        }
        
        return Response(analytics_data)
    
    @action(detail=True, methods=['post'])
    def enroll_contacts(self, request, pk=None):
        """Enroll multiple contacts in the sequence."""
        sequence = self.get_object()
        
        # Validate sequence is active
        if sequence.status != OutreachSequence.Status.ACTIVE:
            return Response(
                {"error": "Can only enroll contacts in active sequences"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = EnrollmentCreateSerializer(
            data=request.data,
            context={'request': request, 'sequence': sequence}
        )
        serializer.is_valid(raise_exception=True)
        
        contact_ids = serializer.validated_data['contact_ids']
        custom_variables = serializer.validated_data.get('custom_variables', {})
        
        # Get contacts
        contacts = Contact.objects.filter(
            id__in=contact_ids,
            group=request.user.group
        )
        
        # Check for existing enrollments
        existing_enrollments = SequenceEnrollment.objects.filter(
            sequence=sequence,
            contact__in=contacts
        ).values_list('contact_id', flat=True)
        
        # Create new enrollments
        created_enrollments = []
        skipped_contacts = []
        
        for contact in contacts:
            if contact.id in existing_enrollments:
                skipped_contacts.append(str(contact.id))
                continue
                
            enrollment = SequenceEnrollment.objects.create(
                sequence=sequence,
                contact=contact,
                group=request.user.group,
                custom_variables=custom_variables,
                enrollment_context={
                    'enrolled_by': request.user.get_full_name(),
                    'enrolled_at': timezone.now().isoformat(),
                    'enrollment_method': 'manual'
                }
            )
            created_enrollments.append(enrollment)
            
            # Start enrollment asynchronously
            start_sequence_enrollment.delay(str(enrollment.id))
        
        return Response({
            'enrolled_count': len(created_enrollments),
            'skipped_count': len(skipped_contacts),
            'skipped_contact_ids': skipped_contacts,
            'enrollments': SequenceEnrollmentSerializer(
                created_enrollments,
                many=True
            ).data
        }, status=status.HTTP_201_CREATED)


class SequenceStepViewSet(viewsets.ModelViewSet):
    """ViewSet for managing sequence steps."""
    queryset = SequenceStep.objects.all()
    serializer_class = SequenceStepSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by sequence if provided
        sequence_id = self.request.query_params.get('sequence')
        if sequence_id:
            queryset = queryset.filter(sequence_id=sequence_id)
            
        return queryset.order_by('sequence', 'order')
    
    def perform_create(self, serializer):
        serializer.save(group=self.request.user.group)
    
    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Reorder steps within a sequence."""
        step_ids = request.data.get('step_ids', [])
        
        if not step_ids:
            return Response(
                {"error": "step_ids required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update order for each step
        for index, step_id in enumerate(step_ids):
            SequenceStep.objects.filter(
                id=step_id,
                group=request.user.group
            ).update(order=index)
        
        return Response({"success": True})


class SequenceEnrollmentFilter(filters.FilterSet):
    """Filter for sequence enrollments."""
    status = filters.ChoiceFilter(choices=SequenceEnrollment.Status.choices)
    sequence = filters.UUIDFilter(field_name='sequence__id')
    contact = filters.UUIDFilter(field_name='contact__id')
    converted = filters.BooleanFilter()
    enrolled_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    enrolled_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    class Meta:
        model = SequenceEnrollment
        fields = ['status', 'sequence', 'contact', 'converted']


class SequenceEnrollmentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing sequence enrollments."""
    queryset = SequenceEnrollment.objects.all()
    serializer_class = SequenceEnrollmentSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    filterset_class = SequenceEnrollmentFilter
    ordering_fields = ['created_at', 'next_step_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return SequenceEnrollmentDetailSerializer
        return super().get_serializer_class()
    
    def get_queryset(self):
        return super().get_queryset().select_related(
            'sequence',
            'contact',
            'current_step'
        )
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause an enrollment."""
        enrollment = self.get_object()
        
        try:
            enrollment.pause()
            enrollment.save()
            return Response(
                SequenceEnrollmentDetailSerializer(enrollment).data
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Resume an enrollment."""
        enrollment = self.get_object()
        
        try:
            enrollment.resume()
            enrollment.save()
            return Response(
                SequenceEnrollmentDetailSerializer(enrollment).data
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def exit(self, request, pk=None):
        """Manually exit an enrollment."""
        enrollment = self.get_object()
        
        reason = request.data.get('reason', SequenceEnrollment.ExitReason.MANUAL)
        details = request.data.get('details', '')
        
        try:
            enrollment.exit(reason=reason, details=details)
            enrollment.save()
            return Response(
                SequenceEnrollmentDetailSerializer(enrollment).data
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def mark_converted(self, request, pk=None):
        """Mark an enrollment as converted."""
        enrollment = self.get_object()
        
        enrollment.converted = True
        enrollment.converted_at = timezone.now()
        enrollment.conversion_value = request.data.get('value')
        enrollment.save()
        
        # Update sequence conversion count
        sequence = enrollment.sequence
        sequence.total_converted += 1
        sequence.save()
        
        # Exit if configured
        if sequence.exit_on_conversion:
            enrollment.exit(
                reason=SequenceEnrollment.ExitReason.CONVERTED,
                details="Marked as converted"
            )
            enrollment.save()
        
        return Response(
            SequenceEnrollmentDetailSerializer(enrollment).data
        )
    
    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        """Get execution timeline for an enrollment."""
        enrollment = self.get_object()
        
        executions = enrollment.step_executions.select_related(
            'step'
        ).order_by('scheduled_at')
        
        timeline = []
        for execution in executions:
            timeline.append({
                'id': execution.id,
                'step_name': execution.step.name,
                'step_type': execution.step.step_type,
                'status': execution.status,
                'scheduled_at': execution.scheduled_at,
                'executed_at': execution.executed_at,
                'result': execution.result,
                'error_message': execution.error_message
            })
        
        return Response({
            'enrollment_id': enrollment.id,
            'contact_email': enrollment.contact.email,
            'sequence_name': enrollment.sequence.name,
            'timeline': timeline
        })


class SequenceTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for sequence templates."""
    queryset = SequenceTemplate.objects.all()
    serializer_class = SequenceTemplateSerializer
    permission_classes = [IsAuthenticated, GroupAccessPermission]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Include public templates
        if self.request.user.is_authenticated:
            queryset = queryset.filter(
                Q(group=self.request.user.group) |
                Q(is_public=True)
            )
            
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
            
        return queryset.order_by('-times_used', 'name')
    
    def perform_create(self, serializer):
        serializer.save(
            group=self.request.user.group,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def create_sequence(self, request, pk=None):
        """Create a new sequence from template."""
        template = self.get_object()
        
        # Create sequence from template configuration
        config = template.configuration
        
        sequence = OutreachSequence.objects.create(
            name=request.data.get('name', config.get('name', template.name)),
            description=config.get('description', template.description),
            group=request.user.group,
            created_by=request.user,
            **{k: v for k, v in config.items() if k not in ['name', 'description', 'steps']}
        )
        
        # Create steps from template
        for step_config in config.get('steps', []):
            SequenceStep.objects.create(
                sequence=sequence,
                group=request.user.group,
                **step_config
            )
        
        # Update template usage
        template.times_used += 1
        template.save()
        
        return Response(
            OutreachSequenceDetailSerializer(sequence).data,
            status=status.HTTP_201_CREATED
        )