"""
API serializers for Advanced Features Models.

Provides comprehensive serialization for regulatory compliance, performance metrics,
ESG assessments, and audit trails with proper validation and nested relationships.
"""

from decimal import Decimal
from typing import Dict, Any, Optional
from datetime import date, timedelta

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .advanced_models import (
    RegulatoryCompliance, PerformanceMetric, ESGAssessment, AuditTrail
)
from .partner_models import DevelopmentPartner
from .scheme_models import PBSAScheme
from .assessment_models import Assessment
from .enums import RiskLevel, AssessmentStatus

User = get_user_model()


class RegulatoryComplianceSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for regulatory compliance summaries and lists."""
    
    # Display fields
    jurisdiction_display = serializers.SerializerMethodField()
    compliance_category_display = serializers.CharField(
        source='get_compliance_category_display',
        read_only=True
    )
    compliance_status_display = serializers.CharField(
        source='get_compliance_status_display',
        read_only=True
    )
    compliance_risk_level_display = serializers.CharField(
        source='get_compliance_risk_level_display',
        read_only=True
    )
    
    # Related entity names
    partner_name = serializers.CharField(
        source='partner.company_name',
        read_only=True,
        allow_null=True
    )
    scheme_name = serializers.CharField(
        source='scheme.scheme_name',
        read_only=True,
        allow_null=True
    )
    
    # Calculated fields
    is_expiring_soon = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    compliance_score = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = RegulatoryCompliance
        fields = [
            'id', 'jurisdiction', 'jurisdiction_display',
            'regulatory_framework', 'regulatory_body',
            'compliance_category', 'compliance_category_display',
            'requirement_title', 'compliance_status',
            'compliance_status_display', 'compliance_date',
            'expiry_date', 'compliance_risk_level',
            'compliance_risk_level_display', 'partner_name',
            'scheme_name', 'is_expiring_soon', 'days_until_expiry',
            'compliance_score', 'next_review_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_jurisdiction_display(self, obj):
        """Get country name from ISO code."""
        # In a real implementation, you'd have a country code mapping
        # For now, return the code with a label
        return f"{obj.jurisdiction} (Country)"


class RegulatoryComplianceDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for full regulatory compliance information."""
    
    # Display fields
    jurisdiction_display = serializers.SerializerMethodField()
    compliance_category_display = serializers.CharField(
        source='get_compliance_category_display',
        read_only=True
    )
    compliance_status_display = serializers.CharField(
        source='get_compliance_status_display',
        read_only=True
    )
    compliance_risk_level_display = serializers.CharField(
        source='get_compliance_risk_level_display',
        read_only=True
    )
    
    # Related entity details
    partner_details = serializers.SerializerMethodField()
    scheme_details = serializers.SerializerMethodField()
    
    # Version information
    semver = serializers.CharField(read_only=True)
    is_approved = serializers.BooleanField(read_only=True)
    last_modified_by_name = serializers.CharField(
        source='last_modified_by.get_full_name',
        read_only=True
    )
    approved_by_name = serializers.CharField(
        source='approved_by.get_full_name',
        read_only=True
    )
    
    # Calculated fields
    is_expiring_soon = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    compliance_score = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = RegulatoryCompliance
        fields = [
            'id', 'partner', 'partner_details', 'scheme', 'scheme_details',
            'jurisdiction', 'jurisdiction_display', 'regulatory_framework',
            'regulatory_body', 'compliance_category', 'compliance_category_display',
            'requirement_title', 'requirement_description', 'compliance_status',
            'compliance_status_display', 'compliance_date', 'expiry_date',
            'compliance_risk_level', 'compliance_risk_level_display',
            'financial_impact_amount', 'evidence_documents', 'compliance_notes',
            'next_review_date', 'responsible_person', 'is_expiring_soon',
            'days_until_expiry', 'compliance_score',
            # Version fields
            'version_major', 'version_minor', 'version_patch', 'semver',
            'version_notes', 'last_modified_by', 'last_modified_by_name',
            'last_modified_at', 'change_reason', 'requires_approval',
            'approved_by', 'approved_by_name', 'approved_at',
            'is_published', 'is_approved',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'semver', 'is_approved', 'last_modified_at',
            'created_at', 'updated_at'
        ]
    
    def get_jurisdiction_display(self, obj):
        """Get country name from ISO code."""
        return f"{obj.jurisdiction} (Country)"
    
    def get_partner_details(self, obj):
        """Get partner summary information."""
        if not obj.partner:
            return None
        
        partner = obj.partner
        return {
            'id': partner.id,
            'company_name': partner.company_name,
            'headquarter_city': getattr(
                partner.general_info, 'headquarter_city', ''
            ) if hasattr(partner, 'general_info') else '',
            'headquarter_country': getattr(
                partner.general_info, 'headquarter_country', ''
            ) if hasattr(partner, 'general_info') else ''
        }
    
    def get_scheme_details(self, obj):
        """Get scheme summary information."""
        if not obj.scheme:
            return None
        
        scheme = obj.scheme
        return {
            'id': scheme.id,
            'scheme_name': scheme.scheme_name,
            'scheme_reference': scheme.scheme_reference,
            'city': getattr(
                scheme.location_info, 'city', ''
            ) if hasattr(scheme, 'location_info') else '',
            'country': getattr(
                scheme.location_info, 'country', ''
            ) if hasattr(scheme, 'location_info') else ''
        }


class RegulatoryComplianceCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating regulatory compliance records."""
    
    class Meta:
        model = RegulatoryCompliance
        fields = [
            'partner', 'scheme', 'jurisdiction', 'regulatory_framework',
            'regulatory_body', 'compliance_category', 'requirement_title',
            'requirement_description', 'compliance_status', 'compliance_date',
            'expiry_date', 'compliance_risk_level', 'financial_impact_amount',
            'evidence_documents', 'compliance_notes', 'next_review_date',
            'responsible_person', 'change_reason'
        ]
    
    def validate(self, data):
        """Validate compliance data."""
        # Ensure either partner or scheme is set, but not both
        if not data.get('partner') and not data.get('scheme'):
            raise serializers.ValidationError(
                "Either partner or scheme must be specified"
            )
        
        if data.get('partner') and data.get('scheme'):
            raise serializers.ValidationError(
                "Cannot specify both partner and scheme"
            )
        
        # Validate dates
        if data.get('compliance_date') and data.get('expiry_date'):
            if data['compliance_date'] > data['expiry_date']:
                raise serializers.ValidationError(
                    "Compliance date cannot be after expiry date"
                )
        
        if data.get('expiry_date'):
            if data['expiry_date'] < date.today():
                raise serializers.ValidationError(
                    "Expiry date cannot be in the past"
                )
        
        # Validate financial impact is positive
        if data.get('financial_impact_amount') is not None:
            if data['financial_impact_amount'] < 0:
                raise serializers.ValidationError(
                    "Financial impact amount cannot be negative"
                )
        
        return data
    
    def create(self, validated_data):
        """Create compliance record with version tracking."""
        user = self.context['request'].user
        validated_data['last_modified_by'] = user
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update compliance record with version increment."""
        user = self.context['request'].user
        validated_data['last_modified_by'] = user
        
        # Increment version if significant change
        if self._is_significant_change(instance, validated_data):
            instance.increment_version('minor', validated_data.get('change_reason', ''))
        
        return super().update(instance, validated_data)
    
    def _is_significant_change(self, instance, validated_data):
        """Check if the change is significant enough to increment version."""
        significant_fields = [
            'compliance_status', 'compliance_risk_level',
            'requirement_description', 'financial_impact_amount'
        ]
        
        for field in significant_fields:
            if field in validated_data and getattr(instance, field) != validated_data[field]:
                return True
        
        return False


class PerformanceMetricSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for performance metric summaries and lists."""
    
    # Display fields
    metric_category_display = serializers.CharField(
        source='get_metric_category_display',
        read_only=True
    )
    trend_direction_display = serializers.CharField(
        source='get_trend_direction_display',
        read_only=True
    )
    measurement_frequency_display = serializers.CharField(
        source='get_measurement_frequency_display',
        read_only=True
    )
    
    # Related entity names
    partner_name = serializers.CharField(
        source='partner.company_name',
        read_only=True,
        allow_null=True
    )
    scheme_name = serializers.CharField(
        source='scheme.scheme_name',
        read_only=True,
        allow_null=True
    )
    assessment_name = serializers.CharField(
        source='assessment.assessment_name',
        read_only=True,
        allow_null=True
    )
    
    # Calculated fields
    performance_rating = serializers.CharField(read_only=True)
    is_meeting_target = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = PerformanceMetric
        fields = [
            'id', 'metric_name', 'metric_category', 'metric_category_display',
            'measurement_date', 'metric_value', 'metric_unit',
            'target_value', 'benchmark_value', 'trend_direction',
            'trend_direction_display', 'variance_from_target_pct',
            'variance_from_benchmark_pct', 'data_quality_score',
            'measurement_frequency', 'measurement_frequency_display',
            'action_required', 'partner_name', 'scheme_name',
            'assessment_name', 'performance_rating', 'is_meeting_target',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PerformanceMetricDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for full performance metric information."""
    
    # Display fields
    metric_category_display = serializers.CharField(
        source='get_metric_category_display',
        read_only=True
    )
    trend_direction_display = serializers.CharField(
        source='get_trend_direction_display',
        read_only=True
    )
    measurement_frequency_display = serializers.CharField(
        source='get_measurement_frequency_display',
        read_only=True
    )
    
    # Related entity details
    partner_details = serializers.SerializerMethodField()
    scheme_details = serializers.SerializerMethodField()
    assessment_details = serializers.SerializerMethodField()
    
    # Version information
    semver = serializers.CharField(read_only=True)
    is_approved = serializers.BooleanField(read_only=True)
    last_modified_by_name = serializers.CharField(
        source='last_modified_by.get_full_name',
        read_only=True
    )
    approved_by_name = serializers.CharField(
        source='approved_by.get_full_name',
        read_only=True
    )
    
    # Calculated fields
    performance_rating = serializers.CharField(read_only=True)
    is_meeting_target = serializers.BooleanField(read_only=True)
    
    # Trend analysis
    historical_trend = serializers.SerializerMethodField()
    
    class Meta:
        model = PerformanceMetric
        fields = [
            'id', 'partner', 'partner_details', 'scheme', 'scheme_details',
            'assessment', 'assessment_details', 'metric_name',
            'metric_category', 'metric_category_display',
            'metric_description', 'measurement_date', 'metric_value',
            'metric_unit', 'target_value', 'benchmark_value',
            'trend_direction', 'trend_direction_display',
            'variance_from_target_pct', 'variance_from_benchmark_pct',
            'data_source', 'data_quality_score', 'measurement_frequency',
            'measurement_frequency_display', 'performance_notes',
            'action_required', 'performance_rating', 'is_meeting_target',
            'historical_trend',
            # Version fields
            'version_major', 'version_minor', 'version_patch', 'semver',
            'version_notes', 'last_modified_by', 'last_modified_by_name',
            'last_modified_at', 'change_reason', 'requires_approval',
            'approved_by', 'approved_by_name', 'approved_at',
            'is_published', 'is_approved',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'semver', 'is_approved', 'last_modified_at',
            'created_at', 'updated_at'
        ]
    
    def get_partner_details(self, obj):
        """Get partner summary information."""
        if not obj.partner:
            return None
        
        partner = obj.partner
        return {
            'id': partner.id,
            'company_name': partner.company_name
        }
    
    def get_scheme_details(self, obj):
        """Get scheme summary information."""
        if not obj.scheme:
            return None
        
        scheme = obj.scheme
        return {
            'id': scheme.id,
            'scheme_name': scheme.scheme_name,
            'scheme_reference': scheme.scheme_reference
        }
    
    def get_assessment_details(self, obj):
        """Get assessment summary information."""
        if not obj.assessment:
            return None
        
        assessment = obj.assessment
        return {
            'id': assessment.id,
            'assessment_name': assessment.assessment_name,
            'assessment_type': assessment.assessment_type,
            'status': assessment.status
        }
    
    def get_historical_trend(self, obj):
        """Get historical trend data for the metric."""
        # Get last 12 measurements of the same metric
        historical = PerformanceMetric.objects.filter(
            metric_name=obj.metric_name,
            metric_category=obj.metric_category
        ).exclude(
            id=obj.id
        ).order_by('-measurement_date')[:12]
        
        return [
            {
                'date': metric.measurement_date,
                'value': metric.metric_value,
                'target': metric.target_value,
                'benchmark': metric.benchmark_value
            }
            for metric in historical
        ]


class PerformanceMetricCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating performance metrics."""
    
    class Meta:
        model = PerformanceMetric
        fields = [
            'partner', 'scheme', 'assessment', 'metric_name',
            'metric_category', 'metric_description', 'measurement_date',
            'metric_value', 'metric_unit', 'target_value',
            'benchmark_value', 'trend_direction', 'variance_from_target_pct',
            'variance_from_benchmark_pct', 'data_source',
            'data_quality_score', 'measurement_frequency',
            'performance_notes', 'action_required', 'change_reason'
        ]
    
    def validate(self, data):
        """Validate metric data."""
        # Ensure at least one entity is set
        if not any([data.get('partner'), data.get('scheme'), data.get('assessment')]):
            raise serializers.ValidationError(
                "At least one of partner, scheme, or assessment must be specified"
            )
        
        # Calculate variances if not provided
        if data.get('metric_value') is not None and data.get('target_value') is not None:
            if 'variance_from_target_pct' not in data:
                if data['target_value'] != 0:
                    variance = ((data['metric_value'] - data['target_value']) / 
                               data['target_value'] * 100)
                    data['variance_from_target_pct'] = round(variance, 2)
        
        if data.get('metric_value') is not None and data.get('benchmark_value') is not None:
            if 'variance_from_benchmark_pct' not in data:
                if data['benchmark_value'] != 0:
                    variance = ((data['metric_value'] - data['benchmark_value']) / 
                               data['benchmark_value'] * 100)
                    data['variance_from_benchmark_pct'] = round(variance, 2)
        
        return data
    
    def create(self, validated_data):
        """Create metric with version tracking."""
        user = self.context['request'].user
        validated_data['last_modified_by'] = user
        return super().create(validated_data)


class ESGAssessmentSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for ESG assessment summaries and lists."""
    
    # Display fields
    assessment_framework_display = serializers.CharField(
        source='get_assessment_framework_display',
        read_only=True
    )
    energy_efficiency_rating_display = serializers.CharField(
        source='get_energy_efficiency_rating_display',
        read_only=True
    )
    esg_rating_display = serializers.CharField(
        source='get_esg_rating_display',
        read_only=True
    )
    
    # Related entity names
    partner_name = serializers.CharField(
        source='partner.company_name',
        read_only=True,
        allow_null=True
    )
    scheme_name = serializers.CharField(
        source='scheme.scheme_name',
        read_only=True,
        allow_null=True
    )
    
    # Calculated fields
    carbon_intensity = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    
    class Meta:
        model = ESGAssessment
        fields = [
            'id', 'assessment_name', 'assessment_framework',
            'assessment_framework_display', 'assessment_period_start',
            'assessment_period_end', 'environmental_score',
            'social_score', 'governance_score', 'overall_esg_score',
            'esg_rating', 'esg_rating_display',
            'energy_efficiency_rating', 'energy_efficiency_rating_display',
            'partner_name', 'scheme_name', 'carbon_intensity',
            'next_assessment_date', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ESGAssessmentDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for full ESG assessment information."""
    
    # Display fields
    assessment_framework_display = serializers.CharField(
        source='get_assessment_framework_display',
        read_only=True
    )
    energy_efficiency_rating_display = serializers.CharField(
        source='get_energy_efficiency_rating_display',
        read_only=True
    )
    esg_rating_display = serializers.CharField(
        source='get_esg_rating_display',
        read_only=True
    )
    
    # Related entity details
    partner_details = serializers.SerializerMethodField()
    scheme_details = serializers.SerializerMethodField()
    
    # Version information
    semver = serializers.CharField(read_only=True)
    is_approved = serializers.BooleanField(read_only=True)
    last_modified_by_name = serializers.CharField(
        source='last_modified_by.get_full_name',
        read_only=True
    )
    approved_by_name = serializers.CharField(
        source='approved_by.get_full_name',
        read_only=True
    )
    
    # Calculated fields
    carbon_intensity = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    
    # ESG score breakdown
    esg_score_breakdown = serializers.SerializerMethodField()
    
    class Meta:
        model = ESGAssessment
        fields = [
            'id', 'partner', 'partner_details', 'scheme', 'scheme_details',
            'assessment_name', 'assessment_framework',
            'assessment_framework_display', 'assessment_period_start',
            'assessment_period_end',
            # Environmental fields
            'environmental_score', 'carbon_footprint_tonnes',
            'energy_efficiency_rating', 'energy_efficiency_rating_display',
            'renewable_energy_pct', 'water_efficiency_score',
            'waste_diversion_rate_pct', 'environmental_certifications',
            # Social fields
            'social_score', 'community_investment_amount',
            'local_employment_pct', 'health_safety_incidents',
            'student_satisfaction_score', 'accessibility_compliance_score',
            # Governance fields
            'governance_score', 'board_diversity_pct',
            'ethics_training_completion_pct', 'transparency_score',
            'anti_corruption_policies',
            # Overall assessment
            'overall_esg_score', 'esg_rating', 'esg_rating_display',
            'improvement_areas', 'action_plan', 'next_assessment_date',
            'carbon_intensity', 'esg_score_breakdown',
            # Risk assessment fields
            'risk_level', 'risk_impact_score', 'risk_likelihood_score',
            'mitigation_measures', 'risk_notes',
            # Version fields
            'version_major', 'version_minor', 'version_patch', 'semver',
            'version_notes', 'last_modified_by', 'last_modified_by_name',
            'last_modified_at', 'change_reason', 'requires_approval',
            'approved_by', 'approved_by_name', 'approved_at',
            'is_published', 'is_approved',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'overall_esg_score', 'esg_rating', 'carbon_intensity',
            'semver', 'is_approved', 'last_modified_at',
            'created_at', 'updated_at'
        ]
    
    def get_partner_details(self, obj):
        """Get partner summary information."""
        if not obj.partner:
            return None
        
        partner = obj.partner
        return {
            'id': partner.id,
            'company_name': partner.company_name
        }
    
    def get_scheme_details(self, obj):
        """Get scheme summary information."""
        if not obj.scheme:
            return None
        
        scheme = obj.scheme
        return {
            'id': scheme.id,
            'scheme_name': scheme.scheme_name,
            'scheme_reference': scheme.scheme_reference,
            'total_beds': scheme.total_beds
        }
    
    def get_esg_score_breakdown(self, obj):
        """Get detailed breakdown of ESG scores."""
        return {
            'environmental': {
                'score': obj.environmental_score,
                'weight': 0.40,
                'weighted_score': float(obj.environmental_score * Decimal('0.40')),
                'components': {
                    'carbon_footprint': obj.carbon_footprint_tonnes,
                    'energy_efficiency': obj.energy_efficiency_rating,
                    'renewable_energy': obj.renewable_energy_pct,
                    'water_efficiency': obj.water_efficiency_score,
                    'waste_diversion': obj.waste_diversion_rate_pct
                }
            },
            'social': {
                'score': obj.social_score,
                'weight': 0.30,
                'weighted_score': float(obj.social_score * Decimal('0.30')),
                'components': {
                    'community_investment': obj.community_investment_amount,
                    'local_employment': obj.local_employment_pct,
                    'health_safety': obj.health_safety_incidents,
                    'student_satisfaction': obj.student_satisfaction_score,
                    'accessibility': obj.accessibility_compliance_score
                }
            },
            'governance': {
                'score': obj.governance_score,
                'weight': 0.30,
                'weighted_score': float(obj.governance_score * Decimal('0.30')),
                'components': {
                    'board_diversity': obj.board_diversity_pct,
                    'ethics_training': obj.ethics_training_completion_pct,
                    'transparency': obj.transparency_score,
                    'anti_corruption': obj.anti_corruption_policies
                }
            }
        }


class ESGAssessmentCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating ESG assessments."""
    
    class Meta:
        model = ESGAssessment
        fields = [
            'partner', 'scheme', 'assessment_name', 'assessment_framework',
            'assessment_period_start', 'assessment_period_end',
            # Environmental fields
            'environmental_score', 'carbon_footprint_tonnes',
            'energy_efficiency_rating', 'renewable_energy_pct',
            'water_efficiency_score', 'waste_diversion_rate_pct',
            'environmental_certifications',
            # Social fields
            'social_score', 'community_investment_amount',
            'local_employment_pct', 'health_safety_incidents',
            'student_satisfaction_score', 'accessibility_compliance_score',
            # Governance fields
            'governance_score', 'board_diversity_pct',
            'ethics_training_completion_pct', 'transparency_score',
            'anti_corruption_policies',
            # Action plans
            'improvement_areas', 'action_plan', 'next_assessment_date',
            # Risk assessment
            'risk_level', 'risk_impact_score', 'risk_likelihood_score',
            'mitigation_measures', 'risk_notes',
            'change_reason'
        ]
    
    def validate(self, data):
        """Validate ESG assessment data."""
        # Ensure either partner or scheme is set, but not both
        if not data.get('partner') and not data.get('scheme'):
            raise serializers.ValidationError(
                "Either partner or scheme must be specified"
            )
        
        if data.get('partner') and data.get('scheme'):
            raise serializers.ValidationError(
                "Cannot specify both partner and scheme"
            )
        
        # Validate assessment period
        if (data.get('assessment_period_start') and 
            data.get('assessment_period_end')):
            if data['assessment_period_start'] > data['assessment_period_end']:
                raise serializers.ValidationError(
                    "Assessment period start date cannot be after end date"
                )
        
        # Validate scores are within range
        score_fields = [
            'environmental_score', 'social_score', 'governance_score',
            'water_efficiency_score', 'transparency_score',
            'accessibility_compliance_score'
        ]
        
        for field in score_fields:
            if data.get(field) is not None:
                if not 1 <= data[field] <= 5:
                    raise serializers.ValidationError(
                        f"{field} must be between 1 and 5"
                    )
        
        # Validate percentages
        percentage_fields = [
            'renewable_energy_pct', 'waste_diversion_rate_pct',
            'local_employment_pct', 'board_diversity_pct',
            'ethics_training_completion_pct'
        ]
        
        for field in percentage_fields:
            if data.get(field) is not None:
                if not 0 <= data[field] <= 100:
                    raise serializers.ValidationError(
                        f"{field} must be between 0 and 100"
                    )
        
        return data
    
    def create(self, validated_data):
        """Create ESG assessment with auto-calculation."""
        user = self.context['request'].user
        validated_data['last_modified_by'] = user
        
        # Create assessment and let the model calculate overall scores
        assessment = super().create(validated_data)
        assessment.save()  # Trigger score calculation
        
        return assessment


class AuditTrailSerializer(serializers.ModelSerializer):
    """Serializer for audit trail entries."""
    
    # Display fields
    action_type_display = serializers.CharField(
        source='get_action_type_display',
        read_only=True
    )
    risk_assessment_display = serializers.CharField(
        source='get_risk_assessment_display',
        read_only=True
    )
    
    # User information
    user_name = serializers.CharField(
        source='user.get_full_name',
        read_only=True
    )
    user_email = serializers.CharField(
        source='user.email',
        read_only=True
    )
    
    # Formatted timestamps
    created_at_formatted = serializers.SerializerMethodField()
    
    # Related entity info
    entity_display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = AuditTrail
        fields = [
            'id', 'entity_type', 'entity_id', 'entity_display_name',
            'action_type', 'action_type_display', 'changed_fields',
            'change_summary', 'user', 'user_name', 'user_email',
            'ip_address', 'user_agent', 'business_justification',
            'risk_assessment', 'risk_assessment_display',
            'created_at', 'created_at_formatted'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_created_at_formatted(self, obj):
        """Get formatted creation timestamp."""
        return obj.created_at.strftime('%Y-%m-%d %H:%M:%S %Z')
    
    def get_entity_display_name(self, obj):
        """Get display name for the entity."""
        # Map entity types to their models and name fields
        entity_mapping = {
            'DevelopmentPartner': ('partner_models', 'company_name'),
            'PBSAScheme': ('scheme_models', 'scheme_name'),
            'Assessment': ('assessment_models', 'assessment_name'),
            'RegulatoryCompliance': ('advanced_models', 'requirement_title'),
            'PerformanceMetric': ('advanced_models', 'metric_name'),
            'ESGAssessment': ('advanced_models', 'assessment_name')
        }
        
        if obj.entity_type in entity_mapping:
            try:
                module_name, field_name = entity_mapping[obj.entity_type]
                # Dynamic import would be needed here in real implementation
                # For now, return a formatted string
                return f"{obj.entity_type} ({obj.entity_id})"
            except Exception:
                return f"{obj.entity_type} ({obj.entity_id})"
        
        return f"{obj.entity_type} ({obj.entity_id})"


class AuditTrailCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating audit trail entries."""
    
    class Meta:
        model = AuditTrail
        fields = [
            'entity_type', 'entity_id', 'action_type',
            'changed_fields', 'change_summary', 'ip_address',
            'user_agent', 'business_justification', 'risk_assessment'
        ]
    
    def create(self, validated_data):
        """Create audit trail entry with current user."""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ComplianceAnalyticsSerializer(serializers.Serializer):
    """Serializer for compliance analytics and reporting."""
    
    date_from = serializers.DateField(
        required=False,
        help_text="Start date for analytics period"
    )
    
    date_to = serializers.DateField(
        required=False,
        help_text="End date for analytics period"
    )
    
    jurisdiction = serializers.CharField(
        max_length=2,
        required=False,
        help_text="Filter by jurisdiction (ISO code)"
    )
    
    compliance_category = serializers.ChoiceField(
        choices=[
            ('financial', 'Financial Regulation'),
            ('planning', 'Planning and Development'),
            ('building', 'Building Standards'),
            ('fire_safety', 'Fire Safety'),
            ('environmental', 'Environmental'),
            ('data_protection', 'Data Protection'),
            ('consumer', 'Consumer Protection'),
            ('employment', 'Employment Law'),
            ('tax', 'Tax and Revenue'),
            ('licensing', 'Licensing and Permits'),
        ],
        required=False,
        help_text="Filter by compliance category"
    )
    
    compliance_status = serializers.ChoiceField(
        choices=[
            ('compliant', 'Fully Compliant'),
            ('partial', 'Partially Compliant'),
            ('non_compliant', 'Non-Compliant'),
            ('pending', 'Compliance Pending'),
            ('exempt', 'Exempt'),
            ('not_applicable', 'Not Applicable'),
        ],
        required=False,
        help_text="Filter by compliance status"
    )
    
    risk_level = serializers.ChoiceField(
        choices=RiskLevel.choices,
        required=False,
        help_text="Filter by risk level"
    )
    
    include_expiring = serializers.BooleanField(
        default=False,
        help_text="Include only expiring compliance items"
    )
    
    group_by = serializers.ChoiceField(
        choices=['jurisdiction', 'category', 'status', 'entity_type'],
        required=False,
        help_text="Group analytics by dimension"
    )


class PerformanceAnalyticsSerializer(serializers.Serializer):
    """Serializer for performance analytics and trend analysis."""
    
    metric_names = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of metric names to analyze"
    )
    
    metric_category = serializers.ChoiceField(
        choices=[
            ('financial', 'Financial Performance'),
            ('operational', 'Operational Performance'),
            ('market', 'Market Performance'),
            ('development', 'Development Performance'),
            ('compliance', 'Compliance Performance'),
            ('satisfaction', 'Customer Satisfaction'),
            ('efficiency', 'Operational Efficiency'),
            ('sustainability', 'ESG Performance'),
        ],
        required=False,
        help_text="Filter by metric category"
    )
    
    date_from = serializers.DateField(
        required=False,
        help_text="Start date for analysis period"
    )
    
    date_to = serializers.DateField(
        required=False,
        help_text="End date for analysis period"
    )
    
    entity_type = serializers.ChoiceField(
        choices=['partner', 'scheme', 'assessment'],
        required=False,
        help_text="Filter by entity type"
    )
    
    entity_id = serializers.UUIDField(
        required=False,
        help_text="Specific entity ID to analyze"
    )
    
    aggregation = serializers.ChoiceField(
        choices=['daily', 'weekly', 'monthly', 'quarterly', 'yearly'],
        default='monthly',
        help_text="Time aggregation period"
    )
    
    include_targets = serializers.BooleanField(
        default=True,
        help_text="Include target values in analysis"
    )
    
    include_benchmarks = serializers.BooleanField(
        default=True,
        help_text="Include benchmark values in analysis"
    )


class ESGComparisonSerializer(serializers.Serializer):
    """Serializer for comparing ESG assessments across entities."""
    
    entity_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=2,
        max_length=10,
        help_text="List of entity IDs to compare (2-10 entities)"
    )
    
    entity_type = serializers.ChoiceField(
        choices=['partner', 'scheme'],
        help_text="Type of entities being compared"
    )
    
    assessment_framework = serializers.ChoiceField(
        choices=[
            ('gri', 'Global Reporting Initiative (GRI)'),
            ('sasb', 'Sustainability Accounting Standards Board (SASB)'),
            ('tcfd', 'Task Force on Climate-related Financial Disclosures'),
            ('un_sdg', 'UN Sustainable Development Goals'),
            ('breeam', 'BREEAM Building Assessment'),
            ('leed', 'LEED Green Building'),
            ('custom', 'Custom Framework'),
        ],
        required=False,
        help_text="Filter by assessment framework"
    )
    
    date_range = serializers.ChoiceField(
        choices=['latest', 'last_year', 'last_2_years', 'all'],
        default='latest',
        help_text="Date range for assessments to include"
    )
    
    comparison_metrics = serializers.MultipleChoiceField(
        choices=[
            'overall_score', 'environmental', 'social', 'governance',
            'carbon_footprint', 'energy_efficiency', 'certifications'
        ],
        default=['overall_score', 'environmental', 'social', 'governance'],
        help_text="Metrics to include in comparison"
    )