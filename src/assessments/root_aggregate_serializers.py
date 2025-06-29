"""
API serializers for Root Aggregate Models.

Provides comprehensive serialization for due diligence cases, checklist items,
and timeline events with proper validation, nested relationships, and calculated fields.
"""

from decimal import Decimal
from typing import Dict, Any, Optional, List
from datetime import date, timedelta

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum

from .root_aggregate import (
    DueDiligenceCase, CaseChecklistItem, CaseTimeline,
    create_standard_checklist
)
from .partner_models import DevelopmentPartner
from .scheme_models import PBSAScheme
from .assessment_models import Assessment, AssessmentStatus, DecisionBand
from .advanced_models import RegulatoryCompliance, PerformanceMetric, ESGAssessment
from .enums import RiskLevel, Currency

User = get_user_model()


class CaseChecklistItemSerializer(serializers.ModelSerializer):
    """Serializer for case checklist items with completion tracking."""
    
    # Display fields
    category_display = serializers.CharField(
        source='get_category_display',
        read_only=True
    )
    
    # Related fields
    completed_by_name = serializers.CharField(
        source='completed_by.get_full_name',
        read_only=True,
        allow_null=True
    )
    
    # Calculated fields
    is_overdue = serializers.SerializerMethodField()
    days_until_due = serializers.SerializerMethodField()
    completion_status = serializers.SerializerMethodField()
    
    class Meta:
        model = CaseChecklistItem
        fields = [
            'id', 'case', 'category', 'category_display',
            'item_name', 'description', 'is_required',
            'is_completed', 'completed_by', 'completed_by_name',
            'completed_at', 'due_date', 'notes', 'attachments',
            'is_overdue', 'days_until_due', 'completion_status',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'case', 'completed_by', 'completed_at',
            'created_at', 'updated_at'
        ]
    
    def get_is_overdue(self, obj) -> bool:
        """Check if checklist item is overdue."""
        if not obj.due_date or obj.is_completed:
            return False
        return date.today() > obj.due_date
    
    def get_days_until_due(self, obj) -> Optional[int]:
        """Calculate days until due date."""
        if not obj.due_date or obj.is_completed:
            return None
        return (obj.due_date - date.today()).days
    
    def get_completion_status(self, obj) -> str:
        """Get completion status label."""
        if obj.is_completed:
            return 'Completed'
        elif self.get_is_overdue(obj):
            return 'Overdue'
        elif obj.due_date:
            days = self.get_days_until_due(obj)
            if days <= 3:
                return 'Due Soon'
            return 'Pending'
        return 'Pending'
    
    def validate_due_date(self, value):
        """Validate due date is in the future."""
        if value and value < date.today():
            raise serializers.ValidationError("Due date cannot be in the past")
        return value


class CaseTimelineSerializer(serializers.ModelSerializer):
    """Serializer for case timeline events for audit history."""
    
    # Display fields
    event_type_display = serializers.CharField(
        source='get_event_type_display',
        read_only=True
    )
    
    # Related fields
    created_by_name = serializers.CharField(
        source='created_by.get_full_name',
        read_only=True
    )
    
    # Calculated fields
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = CaseTimeline
        fields = [
            'id', 'case', 'event_type', 'event_type_display',
            'event_title', 'event_description', 'event_date',
            'created_by', 'created_by_name', 'is_significant',
            'metadata', 'time_ago', 'created_at'
        ]
        read_only_fields = ['id', 'case', 'created_by', 'created_at']
    
    def get_time_ago(self, obj) -> str:
        """Get human-readable time since event."""
        delta = timezone.now() - obj.event_date
        
        if delta.days == 0:
            if delta.seconds < 3600:
                minutes = delta.seconds // 60
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            else:
                hours = delta.seconds // 3600
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif delta.days == 1:
            return "Yesterday"
        elif delta.days < 7:
            return f"{delta.days} days ago"
        elif delta.days < 30:
            weeks = delta.days // 7
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        else:
            return obj.event_date.strftime("%b %d, %Y")


class DueDiligenceCaseSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for due diligence case summaries and lists."""
    
    # Display fields
    case_type_display = serializers.CharField(
        source='get_case_type_display',
        read_only=True
    )
    case_status_display = serializers.CharField(
        source='get_case_status_display',
        read_only=True
    )
    priority_display = serializers.CharField(
        source='get_priority_display',
        read_only=True
    )
    overall_risk_level_display = serializers.CharField(
        source='get_overall_risk_level_display',
        read_only=True,
        allow_null=True
    )
    final_decision_display = serializers.CharField(
        source='get_final_decision_display',
        read_only=True,
        allow_null=True
    )
    
    # Related entity names
    primary_partner_name = serializers.CharField(
        source='primary_partner.company_name',
        read_only=True,
        allow_null=True
    )
    lead_assessor_name = serializers.CharField(
        source='lead_assessor.get_full_name',
        read_only=True
    )
    decision_maker_name = serializers.CharField(
        source='decision_maker.get_full_name',
        read_only=True,
        allow_null=True
    )
    
    # Calculated fields
    is_overdue = serializers.BooleanField(read_only=True)
    days_until_due = serializers.IntegerField(read_only=True)
    completion_percentage = serializers.IntegerField(read_only=True)
    scheme_count = serializers.SerializerMethodField()
    assessment_count = serializers.SerializerMethodField()
    
    # Summary fields
    total_investment_display = serializers.SerializerMethodField()
    
    class Meta:
        model = DueDiligenceCase
        fields = [
            'id', 'case_reference', 'case_name', 'case_type',
            'case_type_display', 'case_status', 'case_status_display',
            'priority', 'priority_display', 'primary_partner',
            'primary_partner_name', 'lead_assessor', 'lead_assessor_name',
            'target_completion_date', 'actual_completion_date',
            'is_overdue', 'days_until_due', 'completion_percentage',
            'overall_risk_level', 'overall_risk_level_display',
            'final_decision', 'final_decision_display',
            'decision_date', 'decision_maker_name',
            'scheme_count', 'assessment_count',
            'total_investment_display', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_scheme_count(self, obj) -> int:
        """Get number of schemes in the case."""
        return obj.schemes.count()
    
    def get_assessment_count(self, obj) -> int:
        """Get number of assessments in the case."""
        return obj.get_all_assessments().count()
    
    def get_total_investment_display(self, obj) -> Optional[str]:
        """Get formatted total investment amount."""
        if obj.total_investment_amount and obj.total_investment_currency:
            return f"{obj.total_investment_currency} {obj.total_investment_amount:,.2f}"
        return None


class DueDiligenceCaseDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for full due diligence case information."""
    
    # Display fields
    case_type_display = serializers.CharField(
        source='get_case_type_display',
        read_only=True
    )
    case_status_display = serializers.CharField(
        source='get_case_status_display',
        read_only=True
    )
    priority_display = serializers.CharField(
        source='get_priority_display',
        read_only=True
    )
    overall_risk_level_display = serializers.CharField(
        source='get_overall_risk_level_display',
        read_only=True,
        allow_null=True
    )
    final_decision_display = serializers.CharField(
        source='get_final_decision_display',
        read_only=True,
        allow_null=True
    )
    total_investment_currency_display = serializers.CharField(
        source='get_total_investment_currency_display',
        read_only=True,
        allow_null=True
    )
    
    # Related entities
    primary_partner_details = serializers.SerializerMethodField()
    scheme_details = serializers.SerializerMethodField()
    lead_assessor_details = serializers.SerializerMethodField()
    assessment_team_details = serializers.SerializerMethodField()
    decision_maker_details = serializers.SerializerMethodField()
    
    # Calculated fields
    is_overdue = serializers.BooleanField(read_only=True)
    days_until_due = serializers.IntegerField(read_only=True)
    completion_percentage = serializers.IntegerField(read_only=True)
    
    # Summary data
    compliance_summary = serializers.SerializerMethodField()
    performance_summary = serializers.SerializerMethodField()
    esg_summary = serializers.SerializerMethodField()
    risk_factors = serializers.SerializerMethodField()
    assessment_summary = serializers.SerializerMethodField()
    checklist_summary = serializers.SerializerMethodField()
    
    # Nested relationships
    recent_timeline_events = serializers.SerializerMethodField()
    
    class Meta:
        model = DueDiligenceCase
        fields = [
            # Basic information
            'id', 'case_reference', 'case_name', 'case_type',
            'case_type_display', 'case_status', 'case_status_display',
            'priority', 'priority_display',
            
            # Entities
            'primary_partner', 'primary_partner_details',
            'schemes', 'scheme_details',
            
            # Team
            'lead_assessor', 'lead_assessor_details',
            'assessment_team', 'assessment_team_details',
            
            # Dates and progress
            'target_completion_date', 'actual_completion_date',
            'is_overdue', 'days_until_due', 'completion_percentage',
            
            # Financial
            'total_investment_amount', 'total_investment_currency',
            'total_investment_currency_display',
            
            # Risk and compliance
            'overall_risk_level', 'overall_risk_level_display',
            'compliance_summary', 'performance_summary', 'esg_summary',
            'risk_factors',
            
            # Decision
            'final_decision', 'final_decision_display',
            'decision_date', 'decision_maker', 'decision_maker_details',
            
            # Documentation
            'executive_summary', 'key_findings', 'conditions', 'next_steps',
            
            # Workflow and metrics
            'workflow_state', 'aggregated_scores',
            'assessment_summary', 'checklist_summary',
            
            # Timeline
            'recent_timeline_events',
            
            # Metadata
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'case_reference', 'aggregated_scores',
            'created_at', 'updated_at'
        ]
    
    def get_primary_partner_details(self, obj):
        """Get primary partner details."""
        if not obj.primary_partner:
            return None
        
        partner = obj.primary_partner
        return {
            'id': partner.id,
            'company_name': partner.company_name,
            'company_registration_number': partner.company_registration_number,
            'headquarter_city': getattr(
                partner.general_info, 'headquarter_city', ''
            ) if hasattr(partner, 'general_info') else '',
            'headquarter_country': getattr(
                partner.general_info, 'headquarter_country', ''
            ) if hasattr(partner, 'general_info') else '',
            'risk_rating': partner.risk_rating,
            'active_schemes_count': partner.schemes.filter(is_active=True).count()
        }
    
    def get_scheme_details(self, obj):
        """Get scheme details."""
        schemes = obj.schemes.all()
        return [
            {
                'id': scheme.id,
                'scheme_name': scheme.scheme_name,
                'scheme_reference': scheme.scheme_reference,
                'development_stage': scheme.development_stage,
                'development_stage_display': scheme.get_development_stage_display(),
                'total_beds': scheme.total_beds,
                'investment_amount': float(scheme.investment_amount) if scheme.investment_amount else None,
                'investment_currency': scheme.investment_currency,
                'city': getattr(
                    scheme.location_info, 'city', ''
                ) if hasattr(scheme, 'location_info') else '',
                'country': getattr(
                    scheme.location_info, 'country', ''
                ) if hasattr(scheme, 'location_info') else ''
            }
            for scheme in schemes
        ]
    
    def get_lead_assessor_details(self, obj):
        """Get lead assessor details."""
        user = obj.lead_assessor
        return {
            'id': user.id,
            'full_name': user.get_full_name(),
            'email': user.email,
            'is_active': user.is_active
        }
    
    def get_assessment_team_details(self, obj):
        """Get assessment team details."""
        return [
            {
                'id': user.id,
                'full_name': user.get_full_name(),
                'email': user.email,
                'is_active': user.is_active
            }
            for user in obj.assessment_team.all()
        ]
    
    def get_decision_maker_details(self, obj):
        """Get decision maker details."""
        if not obj.decision_maker:
            return None
        
        user = obj.decision_maker
        return {
            'id': user.id,
            'full_name': user.get_full_name(),
            'email': user.email,
            'is_active': user.is_active
        }
    
    def get_compliance_summary(self, obj):
        """Get compliance status summary."""
        return obj.get_compliance_status()
    
    def get_performance_summary(self, obj):
        """Get performance metrics summary."""
        return obj.get_performance_summary()
    
    def get_esg_summary(self, obj):
        """Get ESG assessment summary."""
        return obj.get_esg_summary()
    
    def get_risk_factors(self, obj):
        """Get identified risk factors."""
        return obj._identify_risk_factors()
    
    def get_assessment_summary(self, obj):
        """Get assessment summary statistics."""
        assessments = obj.get_all_assessments()
        
        # Status distribution
        status_dist = dict(
            assessments.values('status').annotate(
                count=Count('id')
            ).values_list('status', 'count')
        )
        
        # Decision band distribution
        decision_dist = dict(
            assessments.values('decision_band').annotate(
                count=Count('id')
            ).values_list('decision_band', 'count')
        )
        
        # Average scores
        avg_scores = assessments.aggregate(
            avg_score=Avg('total_weighted_score'),
            avg_risk_score=Avg('total_risk_score')
        )
        
        return {
            'total_assessments': assessments.count(),
            'status_distribution': status_dist,
            'decision_distribution': decision_dist,
            'average_score': float(avg_scores['avg_score']) if avg_scores['avg_score'] else None,
            'average_risk_score': float(avg_scores['avg_risk_score']) if avg_scores['avg_risk_score'] else None,
            'completed_count': assessments.filter(
                status=AssessmentStatus.COMPLETED
            ).count(),
            'in_progress_count': assessments.filter(
                status=AssessmentStatus.IN_PROGRESS
            ).count()
        }
    
    def get_checklist_summary(self, obj):
        """Get checklist completion summary."""
        checklist_items = obj.checklist_items.all()
        total = checklist_items.count()
        completed = checklist_items.filter(is_completed=True).count()
        required = checklist_items.filter(is_required=True)
        required_total = required.count()
        required_completed = required.filter(is_completed=True).count()
        
        # By category
        category_summary = {}
        for item in checklist_items.values('category').annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(is_completed=True))
        ):
            category_summary[item['category']] = {
                'total': item['total'],
                'completed': item['completed'],
                'percentage': round((item['completed'] / item['total']) * 100) if item['total'] > 0 else 0
            }
        
        return {
            'total_items': total,
            'completed_items': completed,
            'completion_percentage': round((completed / total) * 100) if total > 0 else 0,
            'required_items': required_total,
            'required_completed': required_completed,
            'required_completion_percentage': round(
                (required_completed / required_total) * 100
            ) if required_total > 0 else 0,
            'by_category': category_summary
        }
    
    def get_recent_timeline_events(self, obj):
        """Get recent timeline events."""
        recent_events = obj.timeline_events.order_by('-event_date')[:10]
        return CaseTimelineSerializer(recent_events, many=True).data


class DueDiligenceCaseCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating due diligence cases."""
    
    create_standard_checklist = serializers.BooleanField(
        default=True,
        write_only=True,
        help_text="Whether to create standard checklist items for the case"
    )
    
    class Meta:
        model = DueDiligenceCase
        fields = [
            'case_name', 'case_type', 'primary_partner', 'schemes',
            'priority', 'target_completion_date', 'lead_assessor',
            'assessment_team', 'total_investment_amount',
            'total_investment_currency', 'executive_summary',
            'create_standard_checklist'
        ]
    
    def validate(self, data):
        """Validate case data."""
        # Validate case type requirements
        case_type = data.get('case_type', self.instance.case_type if self.instance else 'full_dd')
        
        if case_type == 'partner_only':
            if not data.get('primary_partner') and not (self.instance and self.instance.primary_partner):
                raise serializers.ValidationError(
                    "Primary partner is required for partner-only assessments"
                )
        elif case_type == 'scheme_only':
            if not data.get('schemes') and not (self.instance and self.instance.schemes.exists()):
                raise serializers.ValidationError(
                    "At least one scheme is required for scheme-only assessments"
                )
        
        # Validate target completion date
        if data.get('target_completion_date'):
            if data['target_completion_date'] < date.today():
                raise serializers.ValidationError(
                    "Target completion date cannot be in the past"
                )
        
        # Validate investment amount
        if data.get('total_investment_amount') is not None:
            if data['total_investment_amount'] < 0:
                raise serializers.ValidationError(
                    "Total investment amount cannot be negative"
                )
            
            # Require currency if amount is specified
            if not data.get('total_investment_currency') and not (
                self.instance and self.instance.total_investment_currency
            ):
                raise serializers.ValidationError(
                    "Currency is required when investment amount is specified"
                )
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        """Create case with optional standard checklist."""
        create_checklist = validated_data.pop('create_standard_checklist', True)
        
        # Set group from context
        validated_data['group'] = self.context['request'].user.group
        
        case = super().create(validated_data)
        
        # Create standard checklist if requested
        if create_checklist:
            create_standard_checklist(case)
        
        # Create initial timeline event
        CaseTimeline.objects.create(
            case=case,
            group=case.group,
            event_type='created',
            event_title='Case Created',
            event_description=f'Due diligence case {case.case_reference} created',
            created_by=self.context['request'].user,
            is_significant=True
        )
        
        return case
    
    def update(self, instance, validated_data):
        """Update case with workflow tracking."""
        # Remove create_standard_checklist from update
        validated_data.pop('create_standard_checklist', None)
        
        # Track significant changes
        old_status = instance.case_status
        old_priority = instance.priority
        
        case = super().update(instance, validated_data)
        
        # Create timeline events for significant changes
        user = self.context['request'].user
        
        if 'priority' in validated_data and validated_data['priority'] != old_priority:
            CaseTimeline.objects.create(
                case=case,
                group=case.group,
                event_type='note',
                event_title='Priority Changed',
                event_description=f'Priority changed from {old_priority} to {case.priority}',
                created_by=user
            )
        
        if 'assessment_team' in validated_data:
            CaseTimeline.objects.create(
                case=case,
                group=case.group,
                event_type='team_change',
                event_title='Team Updated',
                event_description='Assessment team members updated',
                created_by=user
            )
        
        return case


class CaseWorkflowSerializer(serializers.Serializer):
    """Serializer for case workflow operations."""
    
    new_status = serializers.ChoiceField(
        choices=[
            ('data_collection', 'Data Collection'),
            ('analysis', 'Analysis in Progress'),
            ('review', 'Under Review'),
            ('decision_pending', 'Decision Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('on_hold', 'On Hold'),
            ('completed', 'Completed'),
            ('archived', 'Archived'),
        ]
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Notes about the status change"
    )
    
    def validate_new_status(self, value):
        """Validate status transition is allowed."""
        case = self.context['case']
        valid_transitions = {
            'initiated': ['data_collection', 'on_hold', 'archived'],
            'data_collection': ['analysis', 'on_hold', 'archived'],
            'analysis': ['review', 'on_hold', 'archived'],
            'review': ['decision_pending', 'analysis', 'on_hold', 'archived'],
            'decision_pending': ['approved', 'rejected', 'on_hold', 'archived'],
            'approved': ['completed', 'archived'],
            'rejected': ['completed', 'archived'],
            'on_hold': ['data_collection', 'analysis', 'review', 'archived'],
            'completed': ['archived'],
            'archived': []
        }
        
        if value not in valid_transitions.get(case.case_status, []):
            raise serializers.ValidationError(
                f"Cannot transition from {case.case_status} to {value}"
            )
        
        return value


class CaseDecisionSerializer(serializers.Serializer):
    """Serializer for recording case decisions."""
    
    decision = serializers.ChoiceField(
        choices=[
            ('proceed', 'Proceed with Investment'),
            ('conditional', 'Proceed with Conditions'),
            ('decline', 'Decline Investment'),
            ('defer', 'Defer Decision'),
        ]
    )
    conditions = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of conditions for conditional approval"
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Decision notes and justification"
    )
    
    def validate(self, data):
        """Validate decision data."""
        case = self.context['case']
        
        if case.case_status != 'decision_pending':
            raise serializers.ValidationError(
                "Case must be in 'decision_pending' status to make a decision"
            )
        
        # Require conditions for conditional approval
        if data['decision'] == 'conditional' and not data.get('conditions'):
            raise serializers.ValidationError(
                "Conditions are required for conditional approval"
            )
        
        return data


class CaseAnalyticsSerializer(serializers.Serializer):
    """Serializer for case analytics and reporting."""
    
    # Overview metrics
    total_cases = serializers.IntegerField()
    active_cases = serializers.IntegerField()
    completed_cases = serializers.IntegerField()
    overdue_cases = serializers.IntegerField()
    
    # Status distribution
    status_distribution = serializers.DictField(
        child=serializers.IntegerField()
    )
    
    # Decision distribution
    decision_distribution = serializers.DictField(
        child=serializers.IntegerField()
    )
    
    # Risk distribution
    risk_distribution = serializers.DictField(
        child=serializers.IntegerField()
    )
    
    # Performance metrics
    average_completion_time = serializers.FloatField()
    on_time_completion_rate = serializers.FloatField()
    approval_rate = serializers.FloatField()
    
    # Team performance
    cases_by_assessor = serializers.ListField(
        child=serializers.DictField()
    )
    
    # Investment summary
    total_investment_under_review = serializers.DictField()
    approved_investment_amount = serializers.DictField()
    
    # Trend data
    cases_by_month = serializers.ListField(
        child=serializers.DictField()
    )
    completion_trend = serializers.ListField(
        child=serializers.DictField()
    )


class CaseComprehensiveSummarySerializer(serializers.Serializer):
    """Serializer for comprehensive case summary."""
    
    case_info = serializers.DictField()
    entities = serializers.DictField()
    assessments = serializers.DictField()
    compliance = serializers.DictField()
    performance = serializers.DictField()
    esg = serializers.DictField()
    risk = serializers.DictField()
    decision = serializers.DictField()
    team = serializers.DictField()