"""
Serializers for outreach sequence models.

This module provides Django REST Framework serializers for all outreach
sequence related models and operations.
"""

from typing import List, Dict, Any
from rest_framework import serializers
from django.db import transaction
from django.utils import timezone

from accounts.serializers import UserSerializer
from .models_outreach import (
    OutreachSequence,
    SequenceStep,
    SequenceEnrollment,
    SequenceStepExecution,
    SequenceTemplate
)
from .models import Contact, EmailTemplate
from .serializers import ContactSerializer, EmailTemplateSerializer


class SequenceStepSerializer(serializers.ModelSerializer):
    """Serializer for sequence steps."""
    email_template_details = EmailTemplateSerializer(
        source='email_template',
        read_only=True
    )
    total_delay_hours = serializers.SerializerMethodField()
    
    class Meta:
        model = SequenceStep
        fields = [
            'id', 'sequence', 'step_type', 'order', 'name',
            'delay_days', 'delay_hours', 'day_type',
            'email_template', 'email_template_details', 'email_subject',
            'condition_type', 'condition_config',
            'action_type', 'action_config',
            'is_variant', 'variant_group', 'variant_percentage',
            'total_sent', 'total_opened', 'total_clicked', 'total_replied',
            'total_delay_hours', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'total_sent', 'total_opened', 'total_clicked',
            'total_replied', 'created_at', 'updated_at'
        ]
    
    def get_total_delay_hours(self, obj):
        return obj.get_total_delay_hours()
    
    def validate(self, data):
        """Validate step configuration based on type."""
        step_type = data.get('step_type', self.instance.step_type if self.instance else None)
        
        if step_type == SequenceStep.StepType.EMAIL:
            if not data.get('email_template') and not (self.instance and self.instance.email_template):
                raise serializers.ValidationError({
                    'email_template': 'Email template is required for email steps'
                })
                
        elif step_type == SequenceStep.StepType.CONDITION:
            if not data.get('condition_type') and not (self.instance and self.instance.condition_type):
                raise serializers.ValidationError({
                    'condition_type': 'Condition type is required for condition steps'
                })
                
        elif step_type == SequenceStep.StepType.ACTION:
            if not data.get('action_type') and not (self.instance and self.instance.action_type):
                raise serializers.ValidationError({
                    'action_type': 'Action type is required for action steps'
                })
        
        return data


class OutreachSequenceSerializer(serializers.ModelSerializer):
    """Basic serializer for outreach sequences."""
    created_by_details = UserSerializer(source='created_by', read_only=True)
    step_count = serializers.SerializerMethodField()
    active_enrollments = serializers.SerializerMethodField()
    
    class Meta:
        model = OutreachSequence
        fields = [
            'id', 'name', 'description', 'status', 'trigger_type',
            'trigger_conditions', 'skip_weekends', 'timezone_optimized',
            'optimal_send_hour', 'exit_on_reply', 'exit_on_click',
            'exit_on_conversion', 'exit_tags', 'goal_description',
            'conversion_url_pattern', 'created_by', 'created_by_details',
            'total_enrolled', 'total_completed', 'total_converted',
            'step_count', 'active_enrollments', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'created_by', 'total_enrolled',
            'total_completed', 'total_converted', 'created_at', 'updated_at'
        ]
    
    def get_step_count(self, obj):
        return obj.steps.count()
    
    def get_active_enrollments(self, obj):
        return obj.enrollments.filter(
            status=SequenceEnrollment.Status.ACTIVE
        ).count()


class OutreachSequenceDetailSerializer(OutreachSequenceSerializer):
    """Detailed serializer for outreach sequences with steps."""
    steps = SequenceStepSerializer(many=True, read_only=True)
    
    class Meta(OutreachSequenceSerializer.Meta):
        fields = OutreachSequenceSerializer.Meta.fields + ['steps']


class SequenceEnrollmentSerializer(serializers.ModelSerializer):
    """Basic serializer for sequence enrollments."""
    contact_details = ContactSerializer(source='contact', read_only=True)
    sequence_name = serializers.CharField(source='sequence.name', read_only=True)
    current_step_name = serializers.CharField(
        source='current_step.name',
        read_only=True,
        allow_null=True
    )
    
    class Meta:
        model = SequenceEnrollment
        fields = [
            'id', 'sequence', 'sequence_name', 'contact', 'contact_details',
            'status', 'current_step', 'current_step_name', 'current_step_index',
            'next_step_at', 'exited_at', 'exit_reason', 'exit_details',
            'converted', 'converted_at', 'conversion_value',
            'enrollment_context', 'custom_variables', 'variant_assignments',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'current_step', 'current_step_index',
            'next_step_at', 'exited_at', 'exit_reason', 'exit_details',
            'created_at', 'updated_at'
        ]


class SequenceStepExecutionSerializer(serializers.ModelSerializer):
    """Serializer for step executions."""
    step_details = SequenceStepSerializer(source='step', read_only=True)
    
    class Meta:
        model = SequenceStepExecution
        fields = [
            'id', 'enrollment', 'step', 'step_details', 'status',
            'scheduled_at', 'executed_at', 'result', 'error_message',
            'email_message_id', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class SequenceEnrollmentDetailSerializer(SequenceEnrollmentSerializer):
    """Detailed serializer for enrollments with execution history."""
    sequence_details = OutreachSequenceSerializer(source='sequence', read_only=True)
    step_executions = SequenceStepExecutionSerializer(many=True, read_only=True)
    
    class Meta(SequenceEnrollmentSerializer.Meta):
        fields = SequenceEnrollmentSerializer.Meta.fields + [
            'sequence_details', 'step_executions'
        ]


class SequenceTemplateSerializer(serializers.ModelSerializer):
    """Serializer for sequence templates."""
    created_by_details = UserSerializer(source='created_by', read_only=True)
    
    class Meta:
        model = SequenceTemplate
        fields = [
            'id', 'name', 'description', 'category', 'configuration',
            'is_public', 'created_by', 'created_by_details',
            'times_used', 'average_conversion_rate',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_by', 'times_used', 'average_conversion_rate',
            'created_at', 'updated_at'
        ]
    
    def validate_configuration(self, value):
        """Validate template configuration structure."""
        required_fields = ['name', 'description', 'steps']
        
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(
                    f"Configuration must include '{field}'"
                )
        
        # Validate steps
        if not isinstance(value['steps'], list):
            raise serializers.ValidationError(
                "Steps must be a list"
            )
        
        for i, step in enumerate(value['steps']):
            if 'name' not in step:
                raise serializers.ValidationError(
                    f"Step {i} must have a name"
                )
            if 'step_type' not in step:
                raise serializers.ValidationError(
                    f"Step {i} must have a step_type"
                )
        
        return value


class EnrollmentCreateSerializer(serializers.Serializer):
    """Serializer for bulk enrollment creation."""
    contact_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=100,
        help_text="List of contact IDs to enroll"
    )
    custom_variables = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Custom variables for all enrollments"
    )
    
    def validate_contact_ids(self, value):
        """Validate contacts exist and belong to user's group."""
        request = self.context['request']
        
        # Check contacts exist
        existing_ids = Contact.objects.filter(
            id__in=value,
            group=request.user.group
        ).values_list('id', flat=True)
        
        missing_ids = set(value) - set(existing_ids)
        if missing_ids:
            raise serializers.ValidationError(
                f"The following contact IDs were not found: {list(missing_ids)}"
            )
        
        return value


class SequenceAnalyticsSerializer(serializers.Serializer):
    """Serializer for sequence analytics data."""
    sequence_id = serializers.UUIDField()
    sequence_name = serializers.CharField()
    total_enrolled = serializers.IntegerField()
    total_active = serializers.IntegerField()
    total_completed = serializers.IntegerField()
    total_converted = serializers.IntegerField()
    conversion_rate = serializers.FloatField()
    average_days_to_complete = serializers.DurationField(allow_null=True)
    
    step_performance = serializers.ListField(
        child=serializers.DictField()
    )
    conversion_funnel = serializers.ListField(
        child=serializers.DictField()
    )
    exit_reasons = serializers.ListField(
        child=serializers.DictField()
    )


class SequenceStepCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating multiple steps at once."""
    class Meta:
        model = SequenceStep
        fields = [
            'step_type', 'order', 'name', 'delay_days', 'delay_hours',
            'day_type', 'email_template', 'email_subject',
            'condition_type', 'condition_config',
            'action_type', 'action_config',
            'is_variant', 'variant_group', 'variant_percentage'
        ]


class OutreachSequenceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a sequence with steps."""
    steps = SequenceStepCreateSerializer(many=True, required=False)
    
    class Meta:
        model = OutreachSequence
        fields = [
            'name', 'description', 'trigger_type', 'trigger_conditions',
            'skip_weekends', 'timezone_optimized', 'optimal_send_hour',
            'exit_on_reply', 'exit_on_click', 'exit_on_conversion',
            'exit_tags', 'goal_description', 'conversion_url_pattern',
            'steps'
        ]
    
    def create(self, validated_data):
        """Create sequence with steps in a transaction."""
        steps_data = validated_data.pop('steps', [])
        
        with transaction.atomic():
            # Create sequence
            sequence = OutreachSequence.objects.create(**validated_data)
            
            # Create steps
            for step_data in steps_data:
                SequenceStep.objects.create(
                    sequence=sequence,
                    group=sequence.group,
                    **step_data
                )
        
        return sequence