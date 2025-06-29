"""
Lead Management Serializers.

Serializers for lead scoring models, leads, and lead activities
with proper validation and nested relationships.
"""

from rest_framework import serializers
from platform_core.core.serializers import PlatformSerializer
from django.contrib.auth import get_user_model

from .models import LeadScoringModel, Lead, LeadActivity

User = get_user_model()


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user serializer for nested relationships."""
    
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'email']
        read_only_fields = ['id', 'username', 'full_name', 'email']


class LeadScoringModelSerializer(serializers.ModelSerializer):
    """Serializer for LeadScoringModel."""
    
    created_by = UserBasicSerializer(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    f1_score = serializers.FloatField(read_only=True)
    scored_leads_count = serializers.SerializerMethodField()
    
    class Meta:
        model = LeadScoringModel
        fields = [
            'id', 'name', 'description', 'scoring_method', 'status',
            'component_weights', 'qualification_threshold', 'high_priority_threshold',
            'auto_convert_threshold', 'accuracy_score', 'precision_score',
            'recall_score', 'version', 'is_default', 'created_by',
            'activated_at', 'deactivated_at', 'created_at', 'updated_at',
            'is_active', 'f1_score', 'scored_leads_count'
        ]
        read_only_fields = [
            'id', 'created_by', 'activated_at', 'deactivated_at',
            'created_at', 'updated_at', 'is_active', 'f1_score',
            'scored_leads_count'
        ]
    
    def get_scored_leads_count(self, obj):
        """Get count of leads scored with this model."""
        return obj.scored_leads.count()
    
    def validate_component_weights(self, value):
        """Validate component weights sum to 1.0 for weighted average method."""
        if value and self.initial_data.get('scoring_method') == 'weighted_average':
            total_weight = sum(value.values())
            if abs(total_weight - 1.0) > 0.01:  # Allow small floating point errors
                raise serializers.ValidationError(
                    "Component weights must sum to 1.0 for weighted average method"
                )
        return value


class MarketIntelligenceTargetBasicSerializer(serializers.Serializer):
    """Basic serializer for market intelligence target."""
    
    id = serializers.UUIDField(read_only=True)
    company_name = serializers.CharField(read_only=True)
    focus_sectors = serializers.ListField(read_only=True)
    business_model = serializers.CharField(read_only=True)


class LeadSerializer(serializers.ModelSerializer):
    """Serializer for Lead."""
    
    assigned_to = UserBasicSerializer(read_only=True)
    identified_by = UserBasicSerializer(read_only=True)
    scoring_model = serializers.StringRelatedField(read_only=True)
    market_intelligence_target = MarketIntelligenceTargetBasicSerializer(read_only=True)
    
    # Computed properties
    is_qualified = serializers.BooleanField(read_only=True)
    is_high_priority = serializers.BooleanField(read_only=True)
    days_in_pipeline = serializers.IntegerField(read_only=True)
    is_stale = serializers.BooleanField(read_only=True)
    
    # Activity summary
    latest_activity = serializers.SerializerMethodField()
    activity_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Lead
        fields = [
            'id', 'company_name', 'trading_name', 'primary_contact_name',
            'primary_contact_email', 'primary_contact_phone', 'primary_contact_title',
            'domain', 'linkedin_url', 'headquarters_city', 'headquarters_country',
            'status', 'source', 'priority', 'current_score', 'scoring_model',
            'last_scored_at', 'qualification_notes', 'assigned_to', 'identified_by',
            'market_intelligence_target', 'converted_at', 'converted_to_partner',
            'tags', 'custom_fields', 'estimated_deal_value', 'estimated_timeline_months',
            'created_at', 'updated_at', 'is_qualified', 'is_high_priority',
            'days_in_pipeline', 'is_stale', 'latest_activity', 'activity_count'
        ]
        read_only_fields = [
            'id', 'current_score', 'scoring_model', 'last_scored_at',
            'converted_at', 'converted_to_partner', 'created_at', 'updated_at',
            'is_qualified', 'is_high_priority', 'days_in_pipeline', 'is_stale',
            'latest_activity', 'activity_count'
        ]
    
    def get_latest_activity(self, obj):
        """Get the latest activity for this lead."""
        latest = obj.get_latest_activity()
        if latest:
            return {
                'id': str(latest.id),
                'activity_type': latest.activity_type,
                'title': latest.title,
                'activity_date': latest.activity_date.isoformat()
            }
        return None
    
    def get_activity_count(self, obj):
        """Get total activity count for this lead."""
        return obj.activities.count()


class LeadCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating leads."""
    
    assigned_to_id = serializers.UUIDField(required=False, allow_null=True)
    market_intelligence_target_id = serializers.UUIDField(required=False, allow_null=True)
    
    class Meta:
        model = Lead
        fields = [
            'company_name', 'trading_name', 'primary_contact_name',
            'primary_contact_email', 'primary_contact_phone', 'primary_contact_title',
            'domain', 'linkedin_url', 'headquarters_city', 'headquarters_country',
            'source', 'priority', 'qualification_notes', 'assigned_to_id',
            'market_intelligence_target_id', 'tags', 'custom_fields',
            'estimated_deal_value', 'estimated_timeline_months'
        ]
    
    def validate_assigned_to_id(self, value):
        """Validate assigned_to_id belongs to the same group."""
        if value:
            try:
                user = User.objects.get(id=value)
                request = self.context.get('request')
                if request and not user.groups.filter(id=request.user.current_group.id).exists():
                    raise serializers.ValidationError("User is not a member of this group")
            except User.DoesNotExist:
                raise serializers.ValidationError("User not found")
        return value
    
    def validate_market_intelligence_target_id(self, value):
        """Validate market intelligence target exists and belongs to group."""
        if value:
            from market_intelligence.models import TargetCompany
            try:
                request = self.context.get('request')
                if request:
                    TargetCompany.objects.get(
                        id=value,
                        group=request.user.current_group
                    )
            except TargetCompany.DoesNotExist:
                raise serializers.ValidationError("Market intelligence target not found")
        return value


class LeadUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating leads."""
    
    assigned_to_id = serializers.UUIDField(required=False, allow_null=True)
    
    class Meta:
        model = Lead
        fields = [
            'trading_name', 'primary_contact_name', 'primary_contact_email',
            'primary_contact_phone', 'primary_contact_title', 'domain',
            'linkedin_url', 'headquarters_city', 'headquarters_country',
            'priority', 'qualification_notes', 'assigned_to_id', 'tags',
            'custom_fields', 'estimated_deal_value', 'estimated_timeline_months'
        ]
    
    def validate_assigned_to_id(self, value):
        """Validate assigned_to_id belongs to the same group."""
        if value:
            try:
                user = User.objects.get(id=value)
                request = self.context.get('request')
                if request and not user.groups.filter(id=request.user.current_group.id).exists():
                    raise serializers.ValidationError("User is not a member of this group")
            except User.DoesNotExist:
                raise serializers.ValidationError("User not found")
        return value


class LeadActivitySerializer(serializers.ModelSerializer):
    """Serializer for LeadActivity."""
    
    lead = serializers.StringRelatedField(read_only=True)
    lead_id = serializers.UUIDField(write_only=True)
    performed_by = UserBasicSerializer(read_only=True)
    
    # Computed properties
    is_overdue = serializers.BooleanField(read_only=True)
    days_until_next_action = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = LeadActivity
        fields = [
            'id', 'lead', 'lead_id', 'activity_type', 'title', 'description',
            'performed_by', 'activity_date', 'outcome', 'next_action',
            'next_action_date', 'email_message_id', 'document_ids',
            'external_reference', 'activity_data', 'is_milestone',
            'is_automated', 'created_at', 'updated_at', 'is_overdue',
            'days_until_next_action'
        ]
        read_only_fields = [
            'id', 'lead', 'performed_by', 'created_at', 'updated_at',
            'is_overdue', 'days_until_next_action'
        ]
    
    def validate_lead_id(self, value):
        """Validate lead_id belongs to the same group."""
        try:
            request = self.context.get('request')
            if request:
                Lead.objects.get(id=value, group=request.user.current_group)
        except Lead.DoesNotExist:
            raise serializers.ValidationError("Lead not found")
        return value


class LeadSummarySerializer(serializers.ModelSerializer):
    """Summary serializer for lead listings."""
    
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    
    class Meta:
        model = Lead
        fields = [
            'id', 'company_name', 'status', 'current_score', 'priority',
            'assigned_to_name', 'headquarters_city', 'headquarters_country',
            'created_at', 'last_scored_at'
        ]
        read_only_fields = fields


class LeadAnalyticsSerializer(serializers.Serializer):
    """Serializer for lead analytics data."""
    
    total_leads = serializers.IntegerField()
    qualified_leads = serializers.IntegerField()
    high_priority_leads = serializers.IntegerField()
    converted_leads = serializers.IntegerField()
    average_score = serializers.FloatField()
    conversion_rate = serializers.FloatField()
    
    # Status distribution
    status_distribution = serializers.DictField()
    
    # Score distribution
    score_distribution = serializers.DictField()
    
    # Performance by assignee
    assignee_performance = serializers.ListField()
    
    # Time-based metrics
    average_days_to_conversion = serializers.FloatField()
    activity_metrics = serializers.DictField()


class BatchScoringResultSerializer(serializers.Serializer):
    """Serializer for batch scoring results."""
    
    total_leads = serializers.IntegerField()
    total_scored = serializers.IntegerField()
    errors = serializers.IntegerField()
    qualified_leads = serializers.IntegerField()
    average_score_change = serializers.FloatField()
    
    scoring_model = serializers.DictField()
    score_changes = serializers.ListField()
    processing_errors = serializers.ListField()
    processed_at = serializers.DateTimeField()