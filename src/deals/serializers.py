"""
Serializers for Deal models.
"""

from rest_framework import serializers
from platform_core.core.serializers import PlatformSerializer
from django.contrib.auth import get_user_model
from django.db import transaction, models
from django.utils import timezone
from datetime import timedelta

from accounts.models import Group
from platform_core.accounts.serializers import UserSerializer
from .models import (
    Deal, DealType, DealSource, WorkflowTemplate, DealStage,
    DealRole, DealTeamMember, DealTransition, DealActivity,
    MilestoneTemplate, DealMilestone,
    DealComment, DealDiscussion, DealNotification,
    VirtualDataRoom, VDRFolder, VDRDocument, VDRAccess, VDRAuditLog
)
from .models.meeting_scheduler import (
    Meeting, MeetingAttendee, MeetingResource, MeetingResourceBooking,
    AvailabilitySlot, MeetingStatus, MeetingType, RecurrenceType
)
from .models.ic_pack import (
    ICPackTemplate, ICPack, ICPackApproval, ICPackDistribution,
    ICPackAuditLog, ICPackStatus
)
from .models.activity import ActivityType
from .services.workflow_engine import WorkflowEngine

User = get_user_model()


class DealTypeSerializer(serializers.ModelSerializer):
    """Serializer for deal types."""
    
    class Meta:
        model = DealType
        fields = [
            'id', 'name', 'code', 'description', 'configuration',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DealSourceSerializer(serializers.ModelSerializer):
    """Serializer for deal sources."""
    
    class Meta:
        model = DealSource
        fields = [
            'id', 'name', 'code', 'description', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DealRoleSerializer(serializers.ModelSerializer):
    """Serializer for deal roles."""
    
    class Meta:
        model = DealRole
        fields = [
            'id', 'name', 'code', 'description', 'permissions',
            'is_required', 'max_members', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DealStageSerializer(serializers.ModelSerializer):
    """Serializer for deal stages."""
    
    class Meta:
        model = DealStage
        fields = [
            'id', 'workflow_template', 'name', 'stage_type', 'order',
            'description', 'target_duration_days', 'max_duration_days',
            'required_documents', 'required_tasks', 'entry_criteria',
            'exit_criteria', 'automation_rules', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class WorkflowTemplateSerializer(serializers.ModelSerializer):
    """Serializer for workflow templates."""
    stages = DealStageSerializer(many=True, read_only=True)
    
    class Meta:
        model = WorkflowTemplate
        fields = [
            'id', 'name', 'code', 'description', 'deal_type',
            'is_default', 'is_active', 'configuration', 'stages',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DealTeamMemberSerializer(serializers.ModelSerializer):
    """Serializer for deal team members."""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)
    
    class Meta:
        model = DealTeamMember
        fields = [
            'id', 'deal', 'user', 'user_email', 'user_name',
            'role', 'role_name', 'involvement_level', 'can_edit',
            'can_approve', 'notify_on_updates', 'added_at',
            'removed_at', 'removal_reason'
        ]
        read_only_fields = ['id', 'added_at']
    
    def validate(self, attrs):
        """Validate team member data."""
        deal = attrs.get('deal')
        user = attrs.get('user')
        role = attrs.get('role')
        
        # Check if user is already on the team
        if DealTeamMember.objects.filter(
            deal=deal,
            user=user,
            removed_at__isnull=True
        ).exists():
            raise serializers.ValidationError(
                "User is already a member of this deal team"
            )
        
        # Check max members for role
        if role.max_members:
            current_count = DealTeamMember.objects.filter(
                deal=deal,
                role=role,
                removed_at__isnull=True
            ).count()
            if current_count >= role.max_members:
                raise serializers.ValidationError(
                    f"Maximum {role.max_members} members allowed for role {role.name}"
                )
        
        return attrs


class DealActivitySerializer(serializers.ModelSerializer):
    """Serializer for deal activities."""
    performed_by_name = serializers.CharField(
        source='performed_by.get_full_name',
        read_only=True
    )
    activity_type_display = serializers.CharField(
        source='get_activity_type_display',
        read_only=True
    )
    
    class Meta:
        model = DealActivity
        fields = [
            'id', 'deal', 'activity_type', 'activity_type_display',
            'performed_by', 'performed_by_name', 'title', 'description',
            'metadata', 'is_important', 'is_private', 'created_at'
        ]
        read_only_fields = [
            'id', 'title', 'is_important', 'created_at'
        ]


class DealMilestoneSerializer(serializers.ModelSerializer):
    """Serializer for deal milestones."""
    assigned_to_name = serializers.CharField(
        source='assigned_to.get_full_name',
        read_only=True,
        allow_null=True
    )
    stage_name = serializers.CharField(
        source='stage.name',
        read_only=True,
        allow_null=True
    )
    is_overdue = serializers.BooleanField(read_only=True)
    days_until_due = serializers.IntegerField(read_only=True)
    checklist_progress = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = DealMilestone
        fields = [
            'id', 'deal', 'template', 'name', 'description',
            'status', 'priority', 'due_date', 'reminder_date',
            'completed_date', 'assigned_to', 'assigned_to_name',
            'stage', 'stage_name', 'is_blocking', 'progress_percentage',
            'checklist_items', 'completed_items', 'required_documents',
            'completed_by', 'completion_notes', 'is_overdue',
            'days_until_due', 'checklist_progress', 'created_at'
        ]
        read_only_fields = [
            'id', 'completed_date', 'completed_by', 'created_at'
        ]


class DealListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for deal lists."""
    deal_type_name = serializers.CharField(source='deal_type.name', read_only=True)
    partner_name = serializers.CharField(source='partner.get_full_name', read_only=True)
    deal_lead_name = serializers.CharField(
        source='deal_lead.get_full_name',
        read_only=True,
        allow_null=True
    )
    current_stage_name = serializers.CharField(
        source='current_stage.name',
        read_only=True,
        allow_null=True
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Deal
        fields = [
            'id', 'name', 'code', 'deal_type', 'deal_type_name',
            'partner', 'partner_name', 'status', 'status_display',
            'investment_amount', 'equity_percentage', 'deal_lead',
            'deal_lead_name', 'current_stage', 'current_stage_name',
            'expected_close_date', 'created_at'
        ]
        read_only_fields = ['id', 'code', 'created_at']


class DealDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for individual deals."""
    deal_type_name = serializers.CharField(source='deal_type.name', read_only=True)
    partner_name = serializers.CharField(source='partner.get_full_name', read_only=True)
    deal_lead_name = serializers.CharField(
        source='deal_lead.get_full_name',
        read_only=True,
        allow_null=True
    )
    originator_name = serializers.CharField(
        source='originator.get_full_name',
        read_only=True,
        allow_null=True
    )
    current_stage_detail = DealStageSerializer(
        source='current_stage',
        read_only=True
    )
    ownership_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        read_only=True
    )
    investment_multiple = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    team_members_count = serializers.SerializerMethodField()
    active_milestones_count = serializers.SerializerMethodField()
    recent_activities = serializers.SerializerMethodField()
    
    class Meta:
        model = Deal
        fields = [
            'id', 'name', 'code', 'deal_type', 'deal_type_name',
            'partner', 'partner_name', 'partner_contact', 'source',
            'status', 'get_status_display', 'investment_amount',
            'pre_money_valuation', 'post_money_valuation',
            'equity_percentage', 'ownership_percentage',
            'investment_multiple', 'irr_target', 'exit_valuation',
            'deal_lead', 'deal_lead_name', 'originator',
            'originator_name', 'current_stage', 'current_stage_detail',
            'stage_entered_at', 'description', 'investment_thesis',
            'key_risks', 'key_opportunities', 'rejection_reason',
            'origination_date', 'expected_close_date', 'actual_close_date',
            'closed_date', 'team_members_count', 'active_milestones_count',
            'recent_activities', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'code', 'stage_entered_at', 'created_at', 'updated_at'
        ]
    
    def get_team_members_count(self, obj):
        """Get count of active team members."""
        return obj.team_members.filter(removed_at__isnull=True).count()
    
    def get_active_milestones_count(self, obj):
        """Get count of active milestones."""
        return obj.milestones.exclude(
            status__in=[DealMilestone.Status.COMPLETED, DealMilestone.Status.CANCELLED]
        ).count()
    
    def get_recent_activities(self, obj):
        """Get recent activities."""
        activities = obj.activities.filter(is_private=False)[:5]
        return DealActivitySerializer(activities, many=True).data


class DealCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating deals."""
    
    class Meta:
        model = Deal
        fields = [
            'name', 'deal_type', 'partner', 'partner_contact',
            'source', 'investment_amount', 'pre_money_valuation',
            'post_money_valuation', 'equity_percentage', 'irr_target',
            'deal_lead', 'originator', 'description',
            'investment_thesis', 'expected_close_date'
        ]
    
    def validate(self, attrs):
        """Validate deal creation data."""
        # Validate investment amount within deal type limits
        deal_type = attrs.get('deal_type')
        investment_amount = attrs.get('investment_amount')
        
        if deal_type and deal_type.configuration:
            min_amount = deal_type.configuration.get('min_investment')
            max_amount = deal_type.configuration.get('max_investment')
            
            if min_amount and investment_amount < min_amount:
                raise serializers.ValidationError(
                    f"Investment amount must be at least {min_amount}"
                )
            
            if max_amount and investment_amount > max_amount:
                raise serializers.ValidationError(
                    f"Investment amount cannot exceed {max_amount}"
                )
        
        # Validate valuations
        pre_money = attrs.get('pre_money_valuation')
        post_money = attrs.get('post_money_valuation')
        
        if pre_money and post_money and post_money <= pre_money:
            raise serializers.ValidationError(
                "Post-money valuation must be greater than pre-money valuation"
            )
        
        return attrs
    
    def create(self, validated_data):
        """Create deal with initial setup."""
        with transaction.atomic():
            # Create the deal
            deal = Deal.objects.create(**validated_data)
            
            # Create initial activity
            DealActivity.objects.create(
                deal=deal,
                activity_type=ActivityType.DEAL_CREATED,
                performed_by=self.context['request'].user,
                description=f"Deal created: {deal.name}",
                metadata={
                    'investment_amount': str(deal.investment_amount),
                    'deal_type': deal.deal_type.name
                },
                group=deal.group
            )
            
            # Add creator as team member if they have a deal_lead role
            if deal.deal_lead:
                lead_role = DealRole.objects.filter(
                    code='deal_lead',
                    group=deal.group
                ).first()
                
                if lead_role:
                    DealTeamMember.objects.create(
                        deal=deal,
                        user=deal.deal_lead,
                        role=lead_role,
                        involvement_level=DealTeamMember.InvolvementLevel.LEAD,
                        can_edit=True,
                        can_approve=True,
                        group=deal.group
                    )
            
            return deal


class DealTransitionSerializer(serializers.Serializer):
    """Serializer for deal stage transitions."""
    target_stage = serializers.PrimaryKeyRelatedField(
        queryset=DealStage.objects.all()
    )
    reason = serializers.CharField(required=False, allow_blank=True)
    force = serializers.BooleanField(default=False)
    
    def validate_target_stage(self, value):
        """Validate target stage."""
        deal = self.context.get('deal')
        
        if not deal:
            raise serializers.ValidationError("Deal context required")
        
        # Check if stage belongs to deal's workflow
        if deal.current_stage and value.workflow_template != deal.current_stage.workflow_template:
            raise serializers.ValidationError(
                "Target stage must belong to the same workflow"
            )
        
        return value
    
    def save(self):
        """Perform the stage transition."""
        deal = self.context['deal']
        user = self.context['request'].user
        
        engine = WorkflowEngine(deal)
        success, errors = engine.transition_to_stage(
            target_stage=self.validated_data['target_stage'],
            performed_by=user,
            reason=self.validated_data.get('reason', ''),
            force=self.validated_data.get('force', False)
        )
        
        if not success:
            raise serializers.ValidationError({
                'non_field_errors': errors
            })
        
        return deal


class MilestoneCompleteSerializer(serializers.Serializer):
    """Serializer for completing milestones."""
    completion_notes = serializers.CharField(required=False, allow_blank=True)
    attached_documents = serializers.ListField(
        child=serializers.UUIDField(),
        required=False
    )
    
    def save(self):
        """Complete the milestone."""
        milestone = self.context['milestone']
        user = self.context['request'].user
        
        milestone.complete(
            completed_by=user,
            notes=self.validated_data.get('completion_notes', '')
        )
        
        # Attach documents if provided
        document_ids = self.validated_data.get('attached_documents', [])
        if document_ids:
            # This would integrate with the files app
            # milestone.attached_documents.add(*document_ids)
            pass
        
        return milestone


class DealAnalyticsSerializer(serializers.Serializer):
    """Serializer for deal analytics data."""
    total_deals = serializers.IntegerField()
    total_investment = serializers.DecimalField(max_digits=20, decimal_places=2)
    average_deal_size = serializers.DecimalField(max_digits=20, decimal_places=2)
    average_irr = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    by_status = serializers.DictField()
    by_stage = serializers.DictField()
    by_deal_type = serializers.DictField()
    
    pipeline_value = serializers.DecimalField(max_digits=20, decimal_places=2)
    closed_value = serializers.DecimalField(max_digits=20, decimal_places=2)
    
    average_time_to_close = serializers.IntegerField()
    deals_at_risk = serializers.IntegerField()
    overdue_milestones = serializers.IntegerField()


# ============================================================================
# COLLABORATION SERIALIZERS
# ============================================================================

class DealCommentSerializer(serializers.ModelSerializer):
    """Serializer for deal comments."""
    author = UserSerializer(read_only=True)
    mentioned_users = UserSerializer(many=True, read_only=True)
    reply_count = serializers.ReadOnlyField()
    is_thread_starter = serializers.ReadOnlyField()
    
    class Meta:
        model = DealComment
        fields = [
            'id', 'deal', 'author', 'content_type', 'object_id',
            'comment_type', 'content', 'parent', 'is_private',
            'is_resolved', 'resolved_by', 'resolved_at',
            'mentioned_users', 'edited_at', 'edit_count',
            'reply_count', 'is_thread_starter', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'author', 'mentioned_users', 'resolved_by', 'resolved_at',
            'edited_at', 'edit_count', 'reply_count', 'is_thread_starter',
            'created_at', 'updated_at'
        ]
    
    def create(self, validated_data):
        """Create comment with current user as author."""
        validated_data['author'] = self.context['request'].user
        validated_data['group'] = self.context['request'].user.groups.first()
        return super().create(validated_data)


class DealCommentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating deal comments."""
    
    class Meta:
        model = DealComment
        fields = [
            'deal', 'content_type', 'object_id', 'comment_type',
            'content', 'parent', 'is_private'
        ]
    
    def validate(self, attrs):
        """Validate comment creation."""
        deal = attrs['deal']
        user = self.context['request'].user
        
        # Check if user is on deal team
        if not deal.team_members.filter(user=user, removed_at__isnull=True).exists():
            raise serializers.ValidationError("Only deal team members can comment")
        
        return attrs
    
    def create(self, validated_data):
        """Create comment with current user as author."""
        validated_data['author'] = self.context['request'].user
        validated_data['group'] = self.context['request'].user.groups.first()
        return super().create(validated_data)


class DealDiscussionSerializer(serializers.ModelSerializer):
    """Serializer for deal discussions."""
    created_by = UserSerializer(read_only=True)
    participants = UserSerializer(many=True, read_only=True)
    resolved_by = UserSerializer(read_only=True)
    comment_count = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    
    class Meta:
        model = DealDiscussion
        fields = [
            'id', 'deal', 'title', 'description', 'discussion_type',
            'status', 'created_by', 'participants', 'resolved_by',
            'resolved_at', 'resolution_summary', 'related_stage',
            'related_milestone', 'priority', 'due_date',
            'comment_count', 'is_overdue', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_by', 'participants', 'resolved_by', 'resolved_at',
            'comment_count', 'is_overdue', 'created_at', 'updated_at'
        ]
    
    def create(self, validated_data):
        """Create discussion with current user as creator."""
        validated_data['created_by'] = self.context['request'].user
        validated_data['group'] = self.context['request'].user.groups.first()
        return super().create(validated_data)


class DealNotificationSerializer(serializers.ModelSerializer):
    """Serializer for deal notifications."""
    sender = UserSerializer(read_only=True)
    
    class Meta:
        model = DealNotification
        fields = [
            'id', 'deal', 'recipient', 'sender', 'notification_type',
            'title', 'message', 'content_type', 'object_id',
            'is_read', 'read_at', 'is_dismissed', 'dismissed_at',
            'action_url', 'action_text', 'created_at'
        ]
        read_only_fields = [
            'id', 'sender', 'read_at', 'dismissed_at', 'created_at'
        ]


# ============================================================================
# IC PACK AUTOMATION SERIALIZERS
# ============================================================================

class ICPackTemplateListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for IC pack template lists."""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    sections_count = serializers.SerializerMethodField()
    approval_stages_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ICPackTemplate
        fields = [
            'id', 'name', 'description', 'is_active', 'is_default',
            'output_format', 'created_by_name', 'sections_count',
            'approval_stages_count', 'tags', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_sections_count(self, obj):
        """Get number of sections in template."""
        return len(obj.sections) if obj.sections else 0
    
    def get_approval_stages_count(self, obj):
        """Get number of approval stages."""
        return len(obj.approval_stages) if obj.approval_stages else 0


class ICPackTemplateSerializer(serializers.ModelSerializer):
    """Full serializer for IC pack templates with validation."""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    validation_errors = serializers.SerializerMethodField()
    packs_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ICPackTemplate
        fields = [
            'id', 'name', 'description', 'is_active', 'is_default',
            'sections', 'required_documents', 'approval_stages',
            'output_format', 'created_by', 'created_by_name', 'tags',
            'validation_errors', 'packs_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def get_validation_errors(self, obj):
        """Get template validation errors."""
        return obj.validate_sections()
    
    def get_packs_count(self, obj):
        """Get number of packs using this template."""
        return obj.packs.count()
    
    def validate_sections(self, value):
        """Validate sections configuration."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Sections must be a list")
        
        section_ids = set()
        for idx, section in enumerate(value):
            if not isinstance(section, dict):
                raise serializers.ValidationError(f"Section {idx} must be a dictionary")
            
            # Required fields
            required_fields = ['id', 'title', 'order']
            for field in required_fields:
                if field not in section:
                    raise serializers.ValidationError(f"Section {idx} missing required field: {field}")
            
            # Check for duplicate IDs
            section_id = section['id']
            if section_id in section_ids:
                raise serializers.ValidationError(f"Duplicate section ID: {section_id}")
            section_ids.add(section_id)
            
            # Validate order is numeric
            if not isinstance(section['order'], int):
                raise serializers.ValidationError(f"Section {idx} order must be an integer")
        
        return value
    
    def validate_approval_stages(self, value):
        """Validate approval stages configuration."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Approval stages must be a list")
        
        for idx, stage in enumerate(value):
            if not isinstance(stage, dict):
                raise serializers.ValidationError(f"Stage {idx} must be a dictionary")
            
            # Required fields
            required_fields = ['stage', 'name', 'required_role', 'order']
            for field in required_fields:
                if field not in stage:
                    raise serializers.ValidationError(f"Stage {idx} missing required field: {field}")
        
        return value
    
    def create(self, validated_data):
        """Create template with current user as creator."""
        validated_data['created_by'] = self.context['request'].user
        validated_data['group'] = self.context['request'].user.groups.first()
        return super().create(validated_data)


class ICPackSerializer(serializers.ModelSerializer):
    """Serializer for IC packs with nested relationships."""
    deal_name = serializers.CharField(source='deal.name', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    last_modified_by_name = serializers.CharField(
        source='last_modified_by.get_full_name',
        read_only=True,
        allow_null=True
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Computed fields
    can_edit = serializers.SerializerMethodField()
    can_approve = serializers.SerializerMethodField()
    can_distribute = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    days_until_meeting = serializers.SerializerMethodField()
    approval_progress = serializers.SerializerMethodField()
    
    # Related data
    approvals = serializers.SerializerMethodField()
    distributions_count = serializers.SerializerMethodField()
    recent_activities = serializers.SerializerMethodField()
    
    class Meta:
        model = ICPack
        fields = [
            'id', 'deal', 'deal_name', 'template', 'template_name',
            'title', 'meeting_date', 'version', 'status', 'status_display',
            'sections_data', 'custom_content', 'generated_document',
            'created_by', 'created_by_name', 'last_modified_by',
            'last_modified_by_name', 'current_approval_stage',
            'approval_deadline', 'distribution_list', 'distributed_at',
            'generation_time_seconds', 'times_viewed',
            'can_edit', 'can_approve', 'can_distribute', 'is_overdue',
            'days_until_meeting', 'approval_progress', 'approvals',
            'distributions_count', 'recent_activities',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'version', 'status', 'generated_document',
            'distributed_at', 'generation_time_seconds', 'times_viewed',
            'created_at', 'updated_at'
        ]
    
    def get_can_edit(self, obj):
        """Check if current user can edit the pack."""
        user = self.context['request'].user
        return (
            obj.status == ICPackStatus.DRAFT and
            (user == obj.created_by or user.is_superuser or
             obj.deal.team_members.filter(
                 user=user,
                 can_edit=True,
                 removed_at__isnull=True
             ).exists())
        )
    
    def get_can_approve(self, obj):
        """Check if current user can approve the pack."""
        user = self.context['request'].user
        if obj.status != ICPackStatus.IN_REVIEW:
            return False
        
        # Check if user is an approver for current stage
        current_approval = obj.approvals.filter(
            stage=obj.current_approval_stage,
            decision=ICPackApproval.ApprovalDecision.PENDING
        ).first()
        
        if not current_approval:
            return False
        
        # Check role permissions
        stage_config = next(
            (s for s in obj.template.approval_stages 
             if s['stage'] == obj.current_approval_stage), None
        )
        
        if stage_config:
            required_role = stage_config.get('required_role')
            return user.role == required_role or user.is_superuser
        
        return False
    
    def get_can_distribute(self, obj):
        """Check if current user can distribute the pack."""
        user = self.context['request'].user
        return (
            obj.status == ICPackStatus.APPROVED and
            (user == obj.created_by or user.is_superuser or
             obj.deal.team_members.filter(
                 user=user,
                 can_approve=True,
                 removed_at__isnull=True
             ).exists())
        )
    
    def get_is_overdue(self, obj):
        """Check if pack is overdue."""
        if not obj.approval_deadline:
            return False
        return timezone.now() > obj.approval_deadline
    
    def get_days_until_meeting(self, obj):
        """Get days until IC meeting."""
        if not obj.meeting_date:
            return None
        
        delta = obj.meeting_date.date() - timezone.now().date()
        return delta.days
    
    def get_approval_progress(self, obj):
        """Get approval progress summary."""
        total_stages = len(obj.template.approval_stages)
        if total_stages == 0:
            return {'completed': 0, 'total': 0, 'percentage': 100}
        
        completed_stages = obj.approvals.filter(
            decision=ICPackApproval.ApprovalDecision.APPROVED
        ).count()
        
        return {
            'completed': completed_stages,
            'total': total_stages,
            'percentage': int((completed_stages / total_stages) * 100)
        }
    
    def get_approvals(self, obj):
        """Get approval records."""
        approvals = obj.approvals.order_by('created_at')
        return ICPackApprovalSerializer(approvals, many=True).data
    
    def get_distributions_count(self, obj):
        """Get count of distributions."""
        return obj.distributions.count()
    
    def get_recent_activities(self, obj):
        """Get recent audit activities."""
        activities = obj.audit_logs.order_by('-created_at')[:5]
        return ICPackAuditLogSerializer(activities, many=True).data


class ICPackCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new IC packs."""
    
    class Meta:
        model = ICPack
        fields = [
            'deal', 'template', 'title', 'meeting_date',
            'custom_content', 'distribution_list'
        ]
    
    def validate(self, attrs):
        """Validate IC pack creation."""
        deal = attrs['deal']
        template = attrs['template']
        
        # Check if user has access to the deal
        user = self.context['request'].user
        if not (deal.deal_lead == user or
                deal.team_members.filter(user=user, removed_at__isnull=True).exists() or
                user.is_superuser):
            raise serializers.ValidationError(
                "You don't have permission to create IC packs for this deal"
            )
        
        # Check template is active
        if not template.is_active:
            raise serializers.ValidationError("Selected template is not active")
        
        # Check for existing draft
        existing_draft = ICPack.objects.filter(
            deal=deal,
            status=ICPackStatus.DRAFT
        ).exists()
        
        if existing_draft:
            raise serializers.ValidationError(
                "A draft IC pack already exists for this deal. Please complete or delete the existing draft first."
            )
        
        return attrs
    
    def create(self, validated_data):
        """Create IC pack using the service."""
        from .services.ic_pack_service import ICPackService
        
        user = self.context['request'].user
        service = ICPackService()
        
        # Extract data
        deal = validated_data['deal']
        template = validated_data['template']
        meeting_date = validated_data.get('meeting_date')
        
        # Create IC pack
        ic_pack = service.create_ic_pack(
            deal=deal,
            template=template,
            created_by=user,
            meeting_date=meeting_date
        )
        
        # Update additional fields
        if 'title' in validated_data:
            ic_pack.title = validated_data['title']
        if 'custom_content' in validated_data:
            ic_pack.custom_content = validated_data['custom_content']
        if 'distribution_list' in validated_data:
            ic_pack.distribution_list = validated_data['distribution_list']
        
        ic_pack.save()
        return ic_pack


class ICPackApprovalSerializer(serializers.ModelSerializer):
    """Serializer for IC pack approvals."""
    decided_by_name = serializers.CharField(
        source='decided_by.get_full_name',
        read_only=True,
        allow_null=True
    )
    delegated_to_name = serializers.CharField(
        source='delegated_to.get_full_name',
        read_only=True,
        allow_null=True
    )
    decision_display = serializers.CharField(source='get_decision_display', read_only=True)
    can_decide = serializers.SerializerMethodField()
    is_pending = serializers.SerializerMethodField()
    
    class Meta:
        model = ICPackApproval
        fields = [
            'id', 'stage', 'stage_name', 'decision', 'decision_display',
            'decided_by', 'decided_by_name', 'decided_at', 'comments',
            'conditions', 'delegated_to', 'delegated_to_name',
            'delegated_at', 'can_decide', 'is_pending', 'created_at'
        ]
        read_only_fields = [
            'id', 'decided_by', 'decided_at', 'delegated_at', 'created_at'
        ]
    
    def get_can_decide(self, obj):
        """Check if current user can make decision."""
        user = self.context['request'].user
        if obj.decision != ICPackApproval.ApprovalDecision.PENDING:
            return False
        
        # Check role permissions
        stage_config = next(
            (s for s in obj.ic_pack.template.approval_stages 
             if s['stage'] == obj.stage), None
        )
        
        if stage_config:
            required_role = stage_config.get('required_role')
            return user.role == required_role or user.is_superuser
        
        return False
    
    def get_is_pending(self, obj):
        """Check if approval is pending."""
        return obj.decision == ICPackApproval.ApprovalDecision.PENDING


class ICPackDistributionSerializer(serializers.ModelSerializer):
    """Serializer for IC pack distributions."""
    sent_by_name = serializers.CharField(source='sent_by.get_full_name', read_only=True)
    recipient_user_name = serializers.CharField(
        source='recipient_user.get_full_name',
        read_only=True,
        allow_null=True
    )
    is_expired = serializers.BooleanField(read_only=True)
    has_viewed = serializers.SerializerMethodField()
    engagement_score = serializers.SerializerMethodField()
    
    class Meta:
        model = ICPackDistribution
        fields = [
            'id', 'ic_pack', 'recipient_email', 'recipient_name',
            'recipient_user', 'recipient_user_name', 'sent_at',
            'sent_by', 'sent_by_name', 'first_viewed_at',
            'last_viewed_at', 'view_count', 'download_count',
            'access_token', 'expires_at', 'is_expired',
            'has_viewed', 'engagement_score'
        ]
        read_only_fields = [
            'id', 'sent_at', 'sent_by', 'first_viewed_at',
            'last_viewed_at', 'view_count', 'download_count',
            'access_token'
        ]
    
    def get_has_viewed(self, obj):
        """Check if recipient has viewed the pack."""
        return obj.view_count > 0
    
    def get_engagement_score(self, obj):
        """Calculate engagement score based on views and downloads."""
        if obj.view_count == 0:
            return 0
        
        # Simple scoring: views * 1 + downloads * 5
        return obj.view_count + (obj.download_count * 5)


class ICPackAuditLogSerializer(serializers.ModelSerializer):
    """Serializer for IC pack audit logs (read-only)."""
    actor_name = serializers.CharField(source='actor.get_full_name', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = ICPackAuditLog
        fields = [
            'id', 'action', 'action_display', 'actor', 'actor_name',
            'description', 'metadata', 'changes', 'ip_address',
            'user_agent', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


# Additional action serializers for specific operations

class ICPackGenerateDocumentSerializer(serializers.Serializer):
    """Serializer for generating IC pack documents."""
    force_regenerate = serializers.BooleanField(default=False)
    include_appendices = serializers.BooleanField(default=True)
    
    def validate(self, attrs):
        """Validate document generation request."""
        ic_pack = self.context.get('ic_pack')
        
        if not ic_pack:
            raise serializers.ValidationError("IC pack context required")
        
        if ic_pack.status not in [ICPackStatus.DRAFT, ICPackStatus.READY_FOR_REVIEW]:
            raise serializers.ValidationError(
                "Documents can only be generated for draft or ready-for-review packs"
            )
        
        return attrs


class ICPackApprovalDecisionSerializer(serializers.Serializer):
    """Serializer for making approval decisions."""
    decision = serializers.ChoiceField(
        choices=[
            (ICPackApproval.ApprovalDecision.APPROVED, 'Approved'),
            (ICPackApproval.ApprovalDecision.REJECTED, 'Rejected'),
            (ICPackApproval.ApprovalDecision.CONDITIONAL, 'Conditionally Approved')
        ]
    )
    comments = serializers.CharField(required=False, allow_blank=True)
    conditions = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )
    
    def validate(self, attrs):
        """Validate approval decision."""
        decision = attrs['decision']
        conditions = attrs.get('conditions', [])
        
        if decision == ICPackApproval.ApprovalDecision.CONDITIONAL and not conditions:
            raise serializers.ValidationError(
                "Conditions are required for conditional approval"
            )
        
        return attrs


class ICPackDistributeSerializer(serializers.Serializer):
    """Serializer for distributing IC packs."""
    recipient_emails = serializers.ListField(
        child=serializers.EmailField(),
        min_length=1
    )
    message = serializers.CharField(required=False, allow_blank=True)
    expires_days = serializers.IntegerField(default=30, min_value=1, max_value=365)
    
    def validate_recipient_emails(self, value):
        """Validate recipient emails."""
        # Remove duplicates while preserving order
        seen = set()
        unique_emails = []
        for email in value:
            if email.lower() not in seen:
                seen.add(email.lower())
                unique_emails.append(email)
        
        return unique_emails


class ICPackAnalyticsSerializer(serializers.Serializer):
    """Serializer for IC pack analytics data."""
    total_packs = serializers.IntegerField()
    latest_version = serializers.IntegerField()
    status_distribution = serializers.DictField()
    average_generation_time = serializers.FloatField()
    average_approval_time = serializers.FloatField(allow_null=True)
    total_distributions = serializers.IntegerField()
    engagement_metrics = serializers.DictField()
    
    # Time series data
    creation_timeline = serializers.ListField(child=serializers.DictField())
    approval_timeline = serializers.ListField(child=serializers.DictField())
    distribution_metrics = serializers.ListField(child=serializers.DictField())


# ============================================================================
# MEETING SCHEDULER SERIALIZERS
# ============================================================================

class MeetingAttendeeSerializer(serializers.ModelSerializer):
    """Serializer for meeting attendees with response tracking."""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True, allow_null=True)
    response_status_display = serializers.CharField(source='get_response_status_display', read_only=True)
    attendee_type_display = serializers.CharField(source='get_attendee_type_display', read_only=True)
    is_external = serializers.SerializerMethodField()
    
    class Meta:
        model = MeetingAttendee
        fields = [
            'id', 'meeting', 'user', 'user_name', 'email', 'name', 'organization',
            'attendee_type', 'attendee_type_display', 'can_edit_agenda', 'can_invite_guests',
            'response_status', 'response_status_display', 'response_notes', 'responded_at',
            'joined_at', 'left_at', 'attended', 'send_invitations', 'send_reminders',
            'is_external', 'created_at'
        ]
        read_only_fields = ['id', 'responded_at', 'joined_at', 'left_at', 'attended', 'created_at']
    
    def get_is_external(self, obj):
        """Check if attendee is external (no internal user account)."""
        return obj.user is None
    
    def validate(self, attrs):
        """Validate attendee data."""
        # Ensure either user or email/name is provided
        user = attrs.get('user')
        email = attrs.get('email')
        name = attrs.get('name')
        
        if not user and not (email and name):
            raise serializers.ValidationError(
                "Either user or both email and name must be provided"
            )
        
        # If user is provided, use their email and name
        if user:
            attrs['email'] = user.email
            attrs['name'] = user.get_full_name()
        
        return attrs


class MeetingResourceSerializer(serializers.ModelSerializer):
    """Serializer for meeting resources."""
    resource_type_display = serializers.CharField(source='get_resource_type_display', read_only=True)
    current_availability = serializers.SerializerMethodField()
    
    class Meta:
        model = MeetingResource
        fields = [
            'id', 'name', 'resource_type', 'resource_type_display', 'description',
            'capacity', 'location', 'specifications', 'is_active', 'requires_approval',
            'hourly_cost', 'setup_cost', 'current_availability', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_current_availability(self, obj):
        """Get current availability status."""
        now = timezone.now()
        end_of_day = now.replace(hour=23, minute=59, second=59)
        
        if not obj.is_active:
            return 'unavailable'
        
        # Check for current bookings
        current_booking = obj.bookings.filter(
            start_time__lte=now,
            end_time__gte=now,
            status__in=[MeetingResourceBooking.BookingStatus.CONFIRMED, MeetingResourceBooking.BookingStatus.IN_USE]
        ).first()
        
        if current_booking:
            return 'in_use'
        
        return 'available'


class MeetingResourceBookingSerializer(serializers.ModelSerializer):
    """Serializer for meeting resource bookings."""
    resource_name = serializers.CharField(source='resource.name', read_only=True)
    meeting_title = serializers.CharField(source='meeting.title', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    total_duration_minutes = serializers.ReadOnlyField()
    calculated_cost = serializers.SerializerMethodField()
    
    class Meta:
        model = MeetingResourceBooking
        fields = [
            'id', 'meeting', 'meeting_title', 'resource', 'resource_name',
            'start_time', 'end_time', 'status', 'status_display',
            'setup_minutes', 'breakdown_minutes', 'estimated_cost', 'actual_cost',
            'booking_notes', 'total_duration_minutes', 'calculated_cost',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_calculated_cost(self, obj):
        """Get calculated cost for the booking."""
        return obj.calculate_cost()
    
    def validate(self, attrs):
        """Validate booking data."""
        start_time = attrs['start_time']
        end_time = attrs['end_time']
        resource = attrs['resource']
        
        if end_time <= start_time:
            raise serializers.ValidationError("End time must be after start time")
        
        # Check resource availability (excluding current booking if updating)
        instance_id = self.instance.id if self.instance else None
        overlapping_bookings = resource.bookings.filter(
            models.Q(start_time__lt=end_time) & models.Q(end_time__gt=start_time),
            status__in=[
                MeetingResourceBooking.BookingStatus.CONFIRMED,
                MeetingResourceBooking.BookingStatus.IN_USE
            ]
        )
        
        if instance_id:
            overlapping_bookings = overlapping_bookings.exclude(id=instance_id)
        
        if overlapping_bookings.exists():
            raise serializers.ValidationError(
                f"Resource '{resource.name}' is not available for the requested time"
            )
        
        return attrs


class AvailabilitySlotSerializer(serializers.ModelSerializer):
    """Serializer for user availability slots."""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    slot_type_display = serializers.CharField(source='get_slot_type_display', read_only=True)
    duration_minutes = serializers.ReadOnlyField()
    is_available_for_new_meeting = serializers.SerializerMethodField()
    
    class Meta:
        model = AvailabilitySlot
        fields = [
            'id', 'user', 'user_name', 'start_time', 'end_time',
            'slot_type', 'slot_type_display', 'is_recurring', 'recurrence_pattern',
            'title', 'notes', 'preferred_meeting_types', 'max_meetings_per_slot',
            'duration_minutes', 'is_available_for_new_meeting', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_is_available_for_new_meeting(self, obj):
        """Check if slot can accommodate a new meeting."""
        return obj.is_available_for_meeting(60)  # Default 60-minute meeting


class MeetingListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for meeting lists."""
    meeting_type_display = serializers.CharField(source='get_meeting_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    organizer_name = serializers.CharField(source='organizer.get_full_name', read_only=True)
    deal_name = serializers.CharField(source='deal.name', read_only=True, allow_null=True)
    attendee_count = serializers.SerializerMethodField()
    confirmed_attendees = serializers.SerializerMethodField()
    duration_minutes = serializers.ReadOnlyField()
    is_virtual = serializers.ReadOnlyField()
    is_recurring = serializers.ReadOnlyField()
    is_past = serializers.ReadOnlyField()
    is_today = serializers.ReadOnlyField()
    
    class Meta:
        model = Meeting
        fields = [
            'id', 'title', 'meeting_type', 'meeting_type_display', 'deal', 'deal_name',
            'start_time', 'end_time', 'timezone_name', 'location', 'virtual_meeting_url',
            'status', 'status_display', 'organizer', 'organizer_name',
            'attendee_count', 'confirmed_attendees', 'duration_minutes',
            'is_virtual', 'is_recurring', 'is_past', 'is_today', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_attendee_count(self, obj):
        """Get total number of attendees."""
        return obj.attendees.count()
    
    def get_confirmed_attendees(self, obj):
        """Get number of confirmed attendees."""
        return obj.attendees.filter(
            response_status=MeetingAttendee.ResponseStatus.ACCEPTED
        ).count()


class MeetingSerializer(serializers.ModelSerializer):
    """Full serializer for meetings with nested attendees and resources."""
    meeting_type_display = serializers.CharField(source='get_meeting_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    organizer_name = serializers.CharField(source='organizer.get_full_name', read_only=True)
    deal_name = serializers.CharField(source='deal.name', read_only=True, allow_null=True)
    
    # Nested relationships
    attendees = MeetingAttendeeSerializer(many=True, read_only=True)
    resource_bookings = MeetingResourceBookingSerializer(many=True, read_only=True)
    
    # Computed fields
    duration_minutes = serializers.ReadOnlyField()
    is_virtual = serializers.ReadOnlyField()
    is_recurring = serializers.ReadOnlyField()
    is_past = serializers.ReadOnlyField()
    is_today = serializers.ReadOnlyField()
    can_edit = serializers.SerializerMethodField()
    can_start = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    
    # Response summary
    response_summary = serializers.SerializerMethodField()
    attendance_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = Meeting
        fields = [
            'id', 'title', 'description', 'meeting_type', 'meeting_type_display',
            'deal', 'deal_name', 'start_time', 'end_time', 'timezone_name',
            'location', 'virtual_meeting_url', 'meeting_room', 'status', 'status_display',
            'organizer', 'organizer_name', 'recurrence_type', 'recurrence_interval',
            'recurrence_end_date', 'parent_meeting', 'calendar_provider',
            'external_calendar_id', 'calendar_sync_enabled', 'requires_confirmation',
            'allow_guests', 'send_reminders', 'agenda', 'preparation_notes',
            'meeting_notes', 'action_items', 'next_steps', 'actual_start_time',
            'actual_end_time', 'attendee_count', 'attendees', 'resource_bookings',
            'duration_minutes', 'is_virtual', 'is_recurring', 'is_past', 'is_today',
            'can_edit', 'can_start', 'can_cancel', 'response_summary',
            'attendance_summary', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'external_calendar_id', 'actual_start_time', 'actual_end_time',
            'attendee_count', 'created_at', 'updated_at'
        ]
    
    def get_can_edit(self, obj):
        """Check if current user can edit the meeting."""
        user = self.context['request'].user
        return (
            user == obj.organizer or
            user.is_superuser or
            obj.attendees.filter(
                user=user,
                can_edit_agenda=True
            ).exists()
        )
    
    def get_can_start(self, obj):
        """Check if current user can start the meeting."""
        user = self.context['request'].user
        return (
            obj.status in [MeetingStatus.SCHEDULED, MeetingStatus.CONFIRMED] and
            (user == obj.organizer or user.is_superuser)
        )
    
    def get_can_cancel(self, obj):
        """Check if current user can cancel the meeting."""
        user = self.context['request'].user
        return (
            obj.status in [MeetingStatus.SCHEDULED, MeetingStatus.CONFIRMED] and
            (user == obj.organizer or user.is_superuser)
        )
    
    def get_response_summary(self, obj):
        """Get attendee response summary."""
        attendees = obj.attendees.all()
        total = attendees.count()
        
        if total == 0:
            return {'total': 0}
        
        summary = {
            'total': total,
            'accepted': attendees.filter(response_status=MeetingAttendee.ResponseStatus.ACCEPTED).count(),
            'declined': attendees.filter(response_status=MeetingAttendee.ResponseStatus.DECLINED).count(),
            'tentative': attendees.filter(response_status=MeetingAttendee.ResponseStatus.TENTATIVE).count(),
            'pending': attendees.filter(response_status=MeetingAttendee.ResponseStatus.PENDING).count(),
            'no_response': attendees.filter(response_status=MeetingAttendee.ResponseStatus.NO_RESPONSE).count(),
        }
        
        summary['response_rate'] = int(((total - summary['pending'] - summary['no_response']) / total) * 100)
        return summary
    
    def get_attendance_summary(self, obj):
        """Get attendance summary for completed meetings."""
        if obj.status != MeetingStatus.COMPLETED:
            return None
        
        attendees = obj.attendees.all()
        total = attendees.count()
        
        if total == 0:
            return {'total': 0, 'attended': 0, 'attendance_rate': 0}
        
        attended = attendees.filter(attended=True).count()
        
        return {
            'total': total,
            'attended': attended,
            'attendance_rate': int((attended / total) * 100)
        }


class MeetingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating meetings with validation."""
    attendees_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="List of attendees to add to the meeting"
    )
    resources_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="List of resources to book for the meeting"
    )
    
    class Meta:
        model = Meeting
        fields = [
            'title', 'description', 'meeting_type', 'deal', 'start_time', 'end_time',
            'timezone_name', 'location', 'virtual_meeting_url', 'meeting_room',
            'recurrence_type', 'recurrence_interval', 'recurrence_end_date',
            'calendar_provider', 'calendar_sync_enabled', 'requires_confirmation',
            'allow_guests', 'send_reminders', 'agenda', 'preparation_notes',
            'attendees_data', 'resources_data'
        ]
    
    def validate(self, attrs):
        """Validate meeting creation data."""
        start_time = attrs['start_time']
        end_time = attrs['end_time']
        
        if end_time <= start_time:
            raise serializers.ValidationError("End time must be after start time")
        
        # Check for reasonable meeting duration (max 8 hours)
        duration = end_time - start_time
        if duration > timedelta(hours=8):
            raise serializers.ValidationError("Meeting duration cannot exceed 8 hours")
        
        # Validate recurrence settings
        recurrence_type = attrs.get('recurrence_type', RecurrenceType.NONE)
        if recurrence_type != RecurrenceType.NONE:
            recurrence_end_date = attrs.get('recurrence_end_date')
            if recurrence_end_date and recurrence_end_date <= start_time:
                raise serializers.ValidationError(
                    "Recurrence end date must be after meeting start time"
                )
        
        return attrs
    
    def create(self, validated_data):
        """Create meeting with attendees and resources."""
        attendees_data = validated_data.pop('attendees_data', [])
        resources_data = validated_data.pop('resources_data', [])
        
        # Set organizer and group
        validated_data['organizer'] = self.context['request'].user
        validated_data['group'] = self.context['request'].user.groups.first()
        
        with transaction.atomic():
            meeting = Meeting.objects.create(**validated_data)
            
            # Add attendees
            for attendee_data in attendees_data:
                attendee_data['meeting'] = meeting
                attendee_data['group'] = meeting.group
                MeetingAttendee.objects.create(**attendee_data)
            
            # Book resources
            for resource_data in resources_data:
                resource_data['meeting'] = meeting
                resource_data['group'] = meeting.group
                MeetingResourceBooking.objects.create(**resource_data)
            
            return meeting


class MeetingRescheduleSerializer(serializers.Serializer):
    """Serializer for rescheduling meetings."""
    new_start_time = serializers.DateTimeField()
    new_end_time = serializers.DateTimeField()
    reason = serializers.CharField(required=False, allow_blank=True)
    notify_attendees = serializers.BooleanField(default=True)
    check_availability = serializers.BooleanField(default=True)
    
    def validate(self, attrs):
        """Validate reschedule data."""
        new_start_time = attrs['new_start_time']
        new_end_time = attrs['new_end_time']
        
        if new_end_time <= new_start_time:
            raise serializers.ValidationError("New end time must be after new start time")
        
        # Check for reasonable meeting duration
        duration = new_end_time - new_start_time
        if duration > timedelta(hours=8):
            raise serializers.ValidationError("Meeting duration cannot exceed 8 hours")
        
        return attrs


class MeetingCancelSerializer(serializers.Serializer):
    """Serializer for canceling meetings."""
    reason = serializers.CharField(required=False, allow_blank=True)
    notify_attendees = serializers.BooleanField(default=True)
    cancel_resources = serializers.BooleanField(default=True)


class FindOptimalTimeSerializer(serializers.Serializer):
    """Serializer for finding optimal meeting times."""
    attendee_emails = serializers.ListField(
        child=serializers.EmailField(),
        min_length=1,
        help_text="List of attendee email addresses"
    )
    duration_minutes = serializers.IntegerField(
        min_value=15,
        max_value=480,
        default=60,
        help_text="Meeting duration in minutes"
    )
    preferred_date_range = serializers.DictField(
        required=False,
        help_text="Preferred date range with 'start_date' and 'end_date'"
    )
    preferred_times = serializers.DictField(
        required=False,
        help_text="Preferred time range with 'start_time' and 'end_time'"
    )
    timezone_name = serializers.CharField(
        default='UTC',
        help_text="Timezone for the suggestions"
    )
    exclude_weekends = serializers.BooleanField(default=True)
    max_suggestions = serializers.IntegerField(
        min_value=1,
        max_value=20,
        default=5,
        help_text="Maximum number of time suggestions to return"
    )
    
    def validate_preferred_date_range(self, value):
        """Validate preferred date range."""
        if not value:
            return value
        
        start_date = value.get('start_date')
        end_date = value.get('end_date')
        
        if start_date and end_date:
            if end_date <= start_date:
                raise serializers.ValidationError("End date must be after start date")
        
        return value


class MeetingAnalyticsSerializer(serializers.Serializer):
    """Serializer for meeting analytics data."""
    total_meetings = serializers.IntegerField()
    meetings_by_status = serializers.DictField()
    meetings_by_type = serializers.DictField()
    average_duration_minutes = serializers.FloatField()
    average_attendees = serializers.FloatField()
    
    # Response and attendance metrics
    overall_response_rate = serializers.FloatField()
    overall_attendance_rate = serializers.FloatField()
    
    # Resource utilization
    resource_utilization = serializers.DictField()
    most_used_resources = serializers.ListField(child=serializers.DictField())
    
    # Time-based metrics
    meetings_by_day_of_week = serializers.DictField()
    meetings_by_hour = serializers.DictField()
    
    # Trends
    monthly_trends = serializers.ListField(child=serializers.DictField())
    
    # Top organizers
    top_organizers = serializers.ListField(child=serializers.DictField())


# ============================================================================
# VIRTUAL DATA ROOM SERIALIZERS
# ============================================================================

class VDRFolderSerializer(serializers.ModelSerializer):
    """Serializer for VDR folders."""
    full_path = serializers.ReadOnlyField(source='get_full_path')
    depth = serializers.ReadOnlyField()
    
    class Meta:
        model = VDRFolder
        fields = [
            'id', 'data_room', 'parent', 'name', 'description',
            'order', 'restricted_access', 'access_roles',
            'full_path', 'depth', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'full_path', 'depth', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        """Create folder with group from data room."""
        data_room = validated_data['data_room']
        validated_data['group'] = data_room.group
        return super().create(validated_data)


class VDRDocumentSerializer(serializers.ModelSerializer):
    """Serializer for VDR documents."""
    uploaded_by = UserSerializer(read_only=True)
    file_size_mb = serializers.ReadOnlyField()
    
    class Meta:
        model = VDRDocument
        fields = [
            'id', 'folder', 'name', 'description', 'file_attachment',
            'file_size', 'file_size_mb', 'file_type', 'version',
            'checksum', 'status', 'is_featured', 'order',
            'uploaded_by', 'upload_completed_at', 'restricted_access',
            'access_roles', 'previous_version', 'is_current_version',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'file_size', 'file_size_mb', 'file_type', 'version',
            'checksum', 'uploaded_by', 'upload_completed_at',
            'previous_version', 'is_current_version', 'created_at', 'updated_at'
        ]
    
    def create(self, validated_data):
        """Create document with metadata from file attachment."""
        file_attachment = validated_data['file_attachment']
        validated_data.update({
            'file_size': file_attachment.file_size,
            'file_type': file_attachment.content_type,
            'uploaded_by': self.context['request'].user,
            'group': validated_data['folder'].group
        })
        return super().create(validated_data)


class VDRAccessSerializer(serializers.ModelSerializer):
    """Serializer for VDR access records."""
    user = UserSerializer(read_only=True)
    granted_by = UserSerializer(read_only=True)
    revoked_by = UserSerializer(read_only=True)
    accessible_folders = VDRFolderSerializer(many=True, read_only=True)
    is_active = serializers.ReadOnlyField()
    is_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = VDRAccess
        fields = [
            'id', 'data_room', 'user', 'access_type', 'access_level',
            'can_download', 'can_upload', 'can_comment', 'can_view_audit_log',
            'accessible_folders', 'granted_by', 'granted_at', 'expires_at',
            'revoked_at', 'revoked_by', 'invitation_email', 'invitation_message',
            'invitation_accepted_at', 'is_active', 'is_expired'
        ]
        read_only_fields = [
            'id', 'user', 'granted_by', 'granted_at', 'revoked_at', 'revoked_by',
            'invitation_accepted_at', 'is_active', 'is_expired'
        ]


class VirtualDataRoomSerializer(serializers.ModelSerializer):
    """Serializer for Virtual Data Rooms."""
    created_by = UserSerializer(read_only=True)
    administrators = UserSerializer(many=True, read_only=True)
    notification_recipients = UserSerializer(many=True, read_only=True)
    document_count = serializers.ReadOnlyField()
    total_size_mb = serializers.ReadOnlyField()
    is_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = VirtualDataRoom
        fields = [
            'id', 'deal', 'name', 'description', 'status', 'created_by',
            'administrators', 'password_protected', 'ip_restrictions',
            'track_downloads', 'track_views', 'watermark_documents',
            'disable_printing', 'disable_screenshots', 'expires_at',
            'auto_extend_expiry', 'notify_on_access', 'notify_on_download',
            'notification_recipients', 'document_count', 'total_size_mb',
            'is_expired', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_by', 'administrators', 'notification_recipients',
            'document_count', 'total_size_mb', 'is_expired',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'password_hash': {'write_only': True}
        }
    
    def create(self, validated_data):
        """Create VDR with current user as creator."""
        validated_data['created_by'] = self.context['request'].user
        validated_data['group'] = self.context['request'].user.groups.first()
        return super().create(validated_data)


class VDRAuditLogSerializer(serializers.ModelSerializer):
    """Serializer for VDR audit logs."""
    user = UserSerializer(read_only=True)
    document = VDRDocumentSerializer(read_only=True)
    folder = VDRFolderSerializer(read_only=True)
    
    class Meta:
        model = VDRAuditLog
        fields = [
            'id', 'data_room', 'user', 'action_type', 'description',
            'ip_address', 'user_agent', 'document', 'folder',
            'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']