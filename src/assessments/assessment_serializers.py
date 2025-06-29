"""
API serializers for the CASA Gold-Standard Assessment Framework.

Provides comprehensive serialization for assessments, metrics, templates,
and related functionality with proper validation and nested relationships.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from .assessment_models import (
    Assessment, AssessmentMetric, AssessmentTemplate, MetricTemplate,
    AssessmentType, MetricCategory, DecisionBand
)
from .enums import AssessmentStatus
from .partner_models import DevelopmentPartner

User = get_user_model()


class AssessmentMetricEnhancedSerializer(serializers.ModelSerializer):
    """Enhanced serializer for assessment metrics with validation and calculated fields."""
    
    weighted_score = serializers.ReadOnlyField()
    max_weighted_score = serializers.ReadOnlyField()
    score_percentage = serializers.ReadOnlyField()
    performance_level = serializers.ReadOnlyField()
    importance_level = serializers.ReadOnlyField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    assessment_method_display = serializers.CharField(source='get_assessment_method_display', read_only=True)
    confidence_level_display = serializers.CharField(source='get_confidence_level_display', read_only=True)
    
    class Meta:
        model = AssessmentMetric
        fields = [
            'id', 'metric_name', 'metric_description', 'category', 'category_display',
            'score', 'weight', 'justification', 'evidence_sources',
            'industry_benchmark', 'peer_comparison', 'assessment_method',
            'assessment_method_display', 'confidence_level', 'confidence_level_display',
            'weighted_score', 'max_weighted_score', 'score_percentage',
            'performance_level', 'importance_level', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate metric data including score and weight ranges."""
        if data.get('score') and (data['score'] < 1 or data['score'] > 5):
            raise serializers.ValidationError("Score must be between 1 and 5")
        
        if data.get('weight') and (data['weight'] < 1 or data['weight'] > 5):
            raise serializers.ValidationError("Weight must be between 1 and 5")
        
        if data.get('industry_benchmark') and (data['industry_benchmark'] < 1 or data['industry_benchmark'] > 5):
            raise serializers.ValidationError("Industry benchmark must be between 1 and 5")
        
        return data


class AssessmentSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for assessment summaries and lists."""
    
    assessment_type_display = serializers.CharField(source='get_assessment_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    decision_display = serializers.CharField(source='get_decision_display', read_only=True)
    decision_band_display = serializers.CharField(source='get_decision_band_display', read_only=True)
    partner_name = serializers.CharField(source='partner.company_name', read_only=True)
    scheme_name = serializers.CharField(source='scheme.scheme_name', read_only=True)
    assessor_name = serializers.CharField(source='assessor.get_full_name', read_only=True)
    metric_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Assessment
        fields = [
            'id', 'assessment_name', 'assessment_type', 'assessment_type_display',
            'status', 'status_display', 'decision', 'decision_display',
            'decision_band', 'decision_band_display', 'total_weighted_score',
            'max_possible_score', 'score_percentage', 'assessment_date',
            'partner_name', 'scheme_name', 'assessor_name', 'metric_count',
            'created_at', 'updated_at'
        ]
    
    def get_metric_count(self, obj):
        """Get the number of metrics in this assessment."""
        return obj.assessment_metrics.count()


class AssessmentDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for full assessment information with metrics."""
    
    assessment_type_display = serializers.CharField(source='get_assessment_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    decision_display = serializers.CharField(source='get_decision_display', read_only=True)
    decision_band_display = serializers.CharField(source='get_decision_band_display', read_only=True)
    
    # Nested relationships
    partner = serializers.PrimaryKeyRelatedField(
        queryset=DevelopmentPartner.objects.all(),
        required=False,
        allow_null=True
    )
    partner_details = serializers.SerializerMethodField()
    
    assessor = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all()
    )
    assessor_details = serializers.SerializerMethodField()
    
    reviewer_details = serializers.SerializerMethodField()
    approver_details = serializers.SerializerMethodField()
    
    # Assessment metrics
    assessment_metrics = AssessmentMetricEnhancedSerializer(many=True, read_only=True)
    
    # Calculated fields
    score_summary = serializers.SerializerMethodField()
    strongest_categories = serializers.SerializerMethodField()
    weakest_categories = serializers.SerializerMethodField()
    automated_recommendations = serializers.SerializerMethodField()
    
    # Version information
    version_string = serializers.SerializerMethodField()
    
    class Meta:
        model = Assessment
        fields = [
            'id', 'assessment_name', 'assessment_type', 'assessment_type_display',
            'partner', 'partner_details', 'scheme', 'status', 'status_display',
            'decision', 'decision_display', 'decision_band', 'decision_band_display',
            'total_weighted_score', 'max_possible_score', 'score_percentage',
            'assessment_date', 'assessment_purpose', 'key_strengths',
            'key_weaknesses', 'recommendations', 'executive_summary',
            'assessor', 'assessor_details', 'reviewer', 'reviewer_details',
            'approver', 'approver_details', 'submitted_at', 'reviewed_at',
            'approved_at', 'assessment_metrics', 'score_summary',
            'strongest_categories', 'weakest_categories', 'automated_recommendations',
            'version_major', 'version_minor', 'version_patch', 'version_string',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'total_weighted_score', 'max_possible_score', 'score_percentage',
            'decision_band', 'submitted_at', 'reviewed_at', 'approved_at',
            'created_at', 'updated_at'
        ]
    
    def get_partner_details(self, obj):
        """Get partner summary information."""
        if not obj.partner:
            return None
        
        partner = obj.partner
        return {
            'id': partner.id,
            'company_name': partner.company_name,
            'headquarter_city': getattr(partner.general_info, 'headquarter_city', '') if hasattr(partner, 'general_info') else '',
            'headquarter_country': getattr(partner.general_info, 'headquarter_country', '') if hasattr(partner, 'general_info') else '',
            'pbsa_experience': getattr(partner.operational_info, 'years_of_pbsa_experience', None) if hasattr(partner, 'operational_info') else None,
            'completed_schemes': getattr(partner.operational_info, 'completed_pbsa_schemes', None) if hasattr(partner, 'operational_info') else None
        }
    
    def get_assessor_details(self, obj):
        """Get assessor information."""
        if not obj.assessor:
            return None
        
        return {
            'id': obj.assessor.id,
            'name': obj.assessor.get_full_name(),
            'email': obj.assessor.email,
            'role': obj.assessor.role
        }
    
    def get_reviewer_details(self, obj):
        """Get reviewer information."""
        if not obj.reviewer:
            return None
        
        return {
            'id': obj.reviewer.id,
            'name': obj.reviewer.get_full_name(),
            'email': obj.reviewer.email,
            'role': obj.reviewer.role
        }
    
    def get_approver_details(self, obj):
        """Get approver information."""
        if not obj.approver:
            return None
        
        return {
            'id': obj.approver.id,
            'name': obj.approver.get_full_name(),
            'email': obj.approver.email,
            'role': obj.approver.role
        }
    
    def get_score_summary(self, obj):
        """Get comprehensive score summary."""
        return obj.calculate_scores()
    
    def get_strongest_categories(self, obj):
        """Get strongest performing categories."""
        return obj.get_strongest_categories(3)
    
    def get_weakest_categories(self, obj):
        """Get weakest performing categories."""
        return obj.get_weakest_categories(3)
    
    def get_automated_recommendations(self, obj):
        """Get automated recommendations."""
        return obj.generate_automated_recommendations()
    
    def get_version_string(self, obj):
        """Get semantic version string."""
        return obj.semver


class AssessmentCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating assessments."""
    
    class Meta:
        model = Assessment
        fields = [
            'assessment_name', 'assessment_type', 'partner', 'scheme',
            'assessment_purpose', 'key_strengths', 'key_weaknesses',
            'recommendations', 'executive_summary'
        ]
    
    def validate(self, data):
        """Validate assessment creation/update data."""
        assessment_type = data.get('assessment_type')
        partner = data.get('partner')
        scheme = data.get('scheme')
        
        if assessment_type == AssessmentType.PARTNER and not partner:
            raise serializers.ValidationError("Partner is required for partner assessments")
        
        if assessment_type == AssessmentType.SCHEME and not scheme:
            raise serializers.ValidationError("Scheme is required for scheme assessments")
        
        if assessment_type == AssessmentType.COMBINED and not (partner and scheme):
            raise serializers.ValidationError("Both partner and scheme are required for combined assessments")
        
        return data


class MetricTemplateSerializer(serializers.ModelSerializer):
    """Serializer for metric templates."""
    
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = MetricTemplate
        fields = [
            'id', 'metric_name', 'metric_description', 'category', 'category_display',
            'default_weight', 'assessment_guidelines', 'scoring_criteria',
            'is_mandatory', 'display_order', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AssessmentTemplateSerializer(serializers.ModelSerializer):
    """Serializer for assessment templates with metric templates."""
    
    assessment_type_display = serializers.CharField(source='get_assessment_type_display', read_only=True)
    metric_templates = MetricTemplateSerializer(many=True, read_only=True)
    template_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = AssessmentTemplate
        fields = [
            'id', 'template_name', 'description', 'assessment_type',
            'assessment_type_display', 'is_active', 'version',
            'metric_templates', 'template_summary', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_template_summary(self, obj):
        """Get template summary statistics."""
        from .standard_templates import TemplateManager
        return TemplateManager.get_template_summary(obj)


class AssessmentWorkflowSerializer(serializers.Serializer):
    """Serializer for assessment workflow actions."""
    
    action = serializers.ChoiceField(
        choices=['submit', 'approve', 'reject'],
        help_text="Workflow action to perform"
    )
    
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
        help_text="Reason for rejection (required for reject action)"
    )
    
    def validate(self, data):
        """Validate workflow action data."""
        if data.get('action') == 'reject' and not data.get('reason'):
            raise serializers.ValidationError("Reason is required for rejection")
        
        return data


class AssessmentMetricBulkCreateSerializer(serializers.Serializer):
    """Serializer for bulk creating metrics from template."""
    
    template_id = serializers.UUIDField(
        help_text="ID of the assessment template to use"
    )
    
    metric_overrides = serializers.DictField(
        child=serializers.DictField(),
        required=False,
        help_text="Override default weights or scores for specific metrics"
    )
    
    def validate_template_id(self, value):
        """Validate template exists and is accessible."""
        try:
            template = AssessmentTemplate.objects.get(id=value)
            if not template.is_active:
                raise serializers.ValidationError("Template is not active")
            return value
        except AssessmentTemplate.DoesNotExist:
            raise serializers.ValidationError("Template not found")


class AssessmentAnalyticsSerializer(serializers.Serializer):
    """Serializer for assessment analytics and reporting."""
    
    date_from = serializers.DateField(
        required=False,
        help_text="Start date for analytics period"
    )
    
    date_to = serializers.DateField(
        required=False,
        help_text="End date for analytics period"
    )
    
    assessment_type = serializers.ChoiceField(
        choices=AssessmentType.choices,
        required=False,
        help_text="Filter by assessment type"
    )
    
    group_by = serializers.ChoiceField(
        choices=['month', 'quarter', 'category', 'decision_band'],
        required=False,
        help_text="Group analytics by period or dimension"
    )