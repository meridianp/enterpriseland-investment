"""
Root Aggregate Models for CASA Due Diligence Platform - Phase 6.

Implements the root aggregate pattern to provide unified access to all
assessment models with comprehensive business logic, workflow orchestration,
and cross-cutting concerns management.
"""

from decimal import Decimal
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, date, timedelta
import json
from uuid import uuid4

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, Max, Min, F, Prefetch

from .base_models import BaseAssessmentModel, UUIDModel
from .partner_models import DevelopmentPartner
from .scheme_models import PBSAScheme, DevelopmentStage
from .assessment_models import Assessment, AssessmentType, AssessmentStatus, DecisionBand
from .advanced_models import RegulatoryCompliance, PerformanceMetric, ESGAssessment, AuditTrail
from .enums import RiskLevel, Currency

User = get_user_model()


class DueDiligenceCase(BaseAssessmentModel, UUIDModel):
    """
    Root aggregate for the entire due diligence process.
    
    Orchestrates all aspects of partner and scheme assessment, providing
    a unified interface for complex business workflows and cross-cutting concerns.
    """
    
    # Case identification
    case_reference = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique case reference number"
    )
    
    case_name = models.CharField(
        max_length=200,
        help_text="Descriptive name for the due diligence case"
    )
    
    case_type = models.CharField(
        max_length=20,
        choices=[
            ('partner_only', 'Partner Assessment Only'),
            ('scheme_only', 'Scheme Assessment Only'),
            ('full_dd', 'Full Due Diligence'),
            ('portfolio', 'Portfolio Assessment'),
        ],
        default='full_dd',
        help_text="Type of due diligence case"
    )
    
    # Primary entities
    primary_partner = models.ForeignKey(
        DevelopmentPartner,
        on_delete=models.PROTECT,
        related_name='due_diligence_cases',
        null=True,
        blank=True,
        help_text="Primary development partner being assessed"
    )
    
    schemes = models.ManyToManyField(
        PBSAScheme,
        related_name='due_diligence_cases',
        blank=True,
        help_text="Schemes included in this due diligence"
    )
    
    # Case status and workflow
    case_status = models.CharField(
        max_length=20,
        choices=[
            ('initiated', 'Initiated'),
            ('data_collection', 'Data Collection'),
            ('analysis', 'Analysis in Progress'),
            ('review', 'Under Review'),
            ('decision_pending', 'Decision Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('on_hold', 'On Hold'),
            ('completed', 'Completed'),
            ('archived', 'Archived'),
        ],
        default='initiated',
        help_text="Current status of the due diligence case"
    )
    
    # Case metadata
    priority = models.CharField(
        max_length=20,
        choices=[
            ('urgent', 'Urgent'),
            ('high', 'High'),
            ('medium', 'Medium'),
            ('low', 'Low'),
        ],
        default='medium',
        help_text="Priority level of the case"
    )
    
    target_completion_date = models.DateField(
        null=True,
        blank=True,
        help_text="Target date for completing due diligence"
    )
    
    actual_completion_date = models.DateField(
        null=True,
        blank=True,
        help_text="Actual completion date"
    )
    
    # Team assignments
    lead_assessor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='lead_cases',
        help_text="Lead assessor responsible for the case"
    )
    
    assessment_team = models.ManyToManyField(
        User,
        related_name='assessment_cases',
        help_text="Team members assigned to the case"
    )
    
    # Financial summary
    total_investment_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total investment amount under consideration"
    )
    
    total_investment_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        null=True,
        blank=True,
        help_text="Currency of total investment"
    )
    
    # Risk assessment summary
    overall_risk_level = models.CharField(
        max_length=20,
        choices=RiskLevel.choices,
        null=True,
        blank=True,
        help_text="Overall risk assessment for the case"
    )
    
    # Decision summary
    final_decision = models.CharField(
        max_length=20,
        choices=[
            ('proceed', 'Proceed with Investment'),
            ('conditional', 'Proceed with Conditions'),
            ('decline', 'Decline Investment'),
            ('defer', 'Defer Decision'),
        ],
        null=True,
        blank=True,
        help_text="Final investment decision"
    )
    
    decision_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of final decision"
    )
    
    decision_maker = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='case_decisions',
        null=True,
        blank=True,
        help_text="Person who made the final decision"
    )
    
    # Documentation
    executive_summary = models.TextField(
        blank=True,
        help_text="Executive summary of the due diligence findings"
    )
    
    key_findings = models.JSONField(
        default=list,
        help_text="List of key findings from the assessment"
    )
    
    conditions = models.JSONField(
        default=list,
        help_text="Conditions attached to the decision"
    )
    
    next_steps = models.JSONField(
        default=list,
        help_text="Recommended next steps"
    )
    
    # Workflow tracking
    workflow_state = models.JSONField(
        default=dict,
        help_text="Current workflow state and history"
    )
    
    # Metrics and scores
    aggregated_scores = models.JSONField(
        default=dict,
        help_text="Aggregated scores from all assessments"
    )
    
    class Meta:
        db_table = 'due_diligence_cases'
        verbose_name = 'Due Diligence Case'
        verbose_name_plural = 'Due Diligence Cases'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['case_reference']),
            models.Index(fields=['case_status', '-created_at']),
            models.Index(fields=['priority', 'target_completion_date']),
        ]
    
    def __str__(self) -> str:
        return f"{self.case_reference}: {self.case_name}"
    
    def save(self, *args, **kwargs):
        """Override save to generate case reference if not provided."""
        if not self.case_reference:
            self.case_reference = self.generate_case_reference()
        super().save(*args, **kwargs)
    
    def generate_case_reference(self) -> str:
        """Generate unique case reference."""
        prefix = 'DD'
        year = timezone.now().year
        
        # Get the next sequential number for this year
        last_case = DueDiligenceCase.objects.filter(
            case_reference__startswith=f'{prefix}{year}'
        ).order_by('-case_reference').first()
        
        if last_case:
            last_number = int(last_case.case_reference[-4:])
            next_number = last_number + 1
        else:
            next_number = 1
        
        return f'{prefix}{year}{next_number:04d}'
    
    @property
    def is_overdue(self) -> bool:
        """Check if case is overdue."""
        if not self.target_completion_date:
            return False
        
        if self.case_status in ['completed', 'archived', 'rejected']:
            return False
        
        return date.today() > self.target_completion_date
    
    @property
    def days_until_due(self) -> Optional[int]:
        """Calculate days until target completion."""
        if not self.target_completion_date:
            return None
        
        if self.case_status in ['completed', 'archived', 'rejected']:
            return None
        
        return (self.target_completion_date - date.today()).days
    
    @property
    def completion_percentage(self) -> int:
        """Calculate completion percentage based on workflow state."""
        status_weights = {
            'initiated': 10,
            'data_collection': 25,
            'analysis': 50,
            'review': 75,
            'decision_pending': 90,
            'approved': 100,
            'rejected': 100,
            'completed': 100,
            'archived': 100,
            'on_hold': None,  # Don't count on-hold in percentage
        }
        
        return status_weights.get(self.case_status, 0) or 0
    
    def get_all_assessments(self) -> models.QuerySet:
        """Get all assessments related to this case."""
        q = Q()
        
        if self.primary_partner:
            q |= Q(partner=self.primary_partner)
        
        scheme_ids = self.schemes.values_list('id', flat=True)
        if scheme_ids:
            q |= Q(scheme__in=scheme_ids)
        
        return Assessment.objects.filter(q).select_related(
            'partner', 'scheme', 'assessor', 'reviewer', 'approver'
        )
    
    def get_compliance_status(self) -> Dict[str, Any]:
        """Get aggregated compliance status for the case."""
        compliance_records = RegulatoryCompliance.objects.filter(
            Q(partner=self.primary_partner) | Q(scheme__in=self.schemes.all())
        )
        
        total = compliance_records.count()
        if total == 0:
            return {
                'total_requirements': 0,
                'compliant': 0,
                'non_compliant': 0,
                'pending': 0,
                'compliance_rate': 0,
                'high_risk_items': 0,
                'expiring_soon': 0
            }
        
        compliant = compliance_records.filter(compliance_status='compliant').count()
        non_compliant = compliance_records.filter(compliance_status='non_compliant').count()
        pending = compliance_records.filter(compliance_status='pending').count()
        
        high_risk = compliance_records.filter(
            Q(compliance_risk_level=RiskLevel.HIGH) | Q(compliance_status='non_compliant')
        ).count()
        
        # Expiring within 90 days
        expiry_date = date.today() + timedelta(days=90)
        expiring_soon = compliance_records.filter(
            expiry_date__lte=expiry_date,
            compliance_status='compliant'
        ).count()
        
        return {
            'total_requirements': total,
            'compliant': compliant,
            'non_compliant': non_compliant,
            'pending': pending,
            'compliance_rate': round((compliant / total) * 100, 1) if total > 0 else 0,
            'high_risk_items': high_risk,
            'expiring_soon': expiring_soon
        }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get aggregated performance metrics summary."""
        # Get latest metrics for each metric name
        metrics = PerformanceMetric.objects.filter(
            Q(partner=self.primary_partner) | Q(scheme__in=self.schemes.all())
        ).values('metric_name').annotate(
            latest_date=Max('measurement_date')
        )
        
        latest_metrics = []
        for metric_info in metrics:
            latest = PerformanceMetric.objects.filter(
                Q(partner=self.primary_partner) | Q(scheme__in=self.schemes.all()),
                metric_name=metric_info['metric_name'],
                measurement_date=metric_info['latest_date']
            ).first()
            if latest:
                latest_metrics.append(latest)
        
        # Calculate summary statistics
        meeting_targets = sum(1 for m in latest_metrics if m.is_meeting_target)
        total_metrics = len(latest_metrics)
        
        avg_data_quality = sum(m.data_quality_score for m in latest_metrics) / total_metrics if total_metrics > 0 else 0
        
        requiring_action = sum(1 for m in latest_metrics if m.action_required)
        
        return {
            'total_metrics': total_metrics,
            'meeting_targets': meeting_targets,
            'target_achievement_rate': round((meeting_targets / total_metrics) * 100, 1) if total_metrics > 0 else 0,
            'average_data_quality': round(avg_data_quality, 1),
            'requiring_action': requiring_action,
            'metrics_breakdown': {
                'improving': sum(1 for m in latest_metrics if m.trend_direction == 'improving'),
                'stable': sum(1 for m in latest_metrics if m.trend_direction == 'stable'),
                'declining': sum(1 for m in latest_metrics if m.trend_direction == 'declining'),
            }
        }
    
    def get_esg_summary(self) -> Dict[str, Any]:
        """Get latest ESG assessment summary."""
        # Get latest ESG assessments
        latest_esg = ESGAssessment.objects.filter(
            Q(partner=self.primary_partner) | Q(scheme__in=self.schemes.all())
        ).order_by('-assessment_period_end').first()
        
        if not latest_esg:
            return {
                'has_esg_assessment': False,
                'latest_assessment_date': None,
                'overall_score': None,
                'rating': None,
                'scores': {}
            }
        
        return {
            'has_esg_assessment': True,
            'latest_assessment_date': latest_esg.assessment_period_end,
            'overall_score': float(latest_esg.overall_esg_score) if latest_esg.overall_esg_score else None,
            'rating': latest_esg.esg_rating,
            'scores': {
                'environmental': latest_esg.environmental_score,
                'social': latest_esg.social_score,
                'governance': latest_esg.governance_score
            },
            'carbon_footprint': float(latest_esg.carbon_footprint_tonnes) if latest_esg.carbon_footprint_tonnes else None,
            'renewable_energy_pct': float(latest_esg.renewable_energy_pct) if latest_esg.renewable_energy_pct else None
        }
    
    def calculate_overall_risk(self) -> str:
        """Calculate overall risk level based on all factors."""
        risk_scores = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4
        }
        
        risk_factors = []
        
        # Compliance risk
        compliance_status = self.get_compliance_status()
        if compliance_status['non_compliant'] > 0:
            risk_factors.append(RiskLevel.HIGH)
        elif compliance_status['compliance_rate'] < 90:
            risk_factors.append(RiskLevel.MEDIUM)
        else:
            risk_factors.append(RiskLevel.LOW)
        
        # Performance risk
        performance = self.get_performance_summary()
        if performance['target_achievement_rate'] < 70:
            risk_factors.append(RiskLevel.HIGH)
        elif performance['target_achievement_rate'] < 85:
            risk_factors.append(RiskLevel.MEDIUM)
        else:
            risk_factors.append(RiskLevel.LOW)
        
        # ESG risk
        esg = self.get_esg_summary()
        if esg['has_esg_assessment']:
            if esg['rating'] in ['B', 'CCC']:
                risk_factors.append(RiskLevel.HIGH)
            elif esg['rating'] in ['BBB', 'BB']:
                risk_factors.append(RiskLevel.MEDIUM)
            else:
                risk_factors.append(RiskLevel.LOW)
        
        # Assessment risk
        assessments = self.get_all_assessments()
        high_risk_assessments = assessments.filter(
            decision_band=DecisionBand.REJECT
        ).count()
        
        if high_risk_assessments > 0:
            risk_factors.append(RiskLevel.HIGH)
        
        # Calculate average risk
        if not risk_factors:
            return RiskLevel.MEDIUM
        
        avg_risk_score = sum(risk_scores.get(risk, 2) for risk in risk_factors) / len(risk_factors)
        
        if avg_risk_score >= 3.5:
            return RiskLevel.CRITICAL
        elif avg_risk_score >= 2.5:
            return RiskLevel.HIGH
        elif avg_risk_score >= 1.5:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def update_aggregated_scores(self) -> None:
        """Update aggregated scores from all assessments."""
        assessments = self.get_all_assessments()
        
        if not assessments.exists():
            self.aggregated_scores = {}
            return
        
        # Calculate average scores by assessment type
        scores_by_type = {}
        
        for assessment_type in AssessmentType:
            type_assessments = assessments.filter(assessment_type=assessment_type)
            if type_assessments.exists():
                avg_score = type_assessments.aggregate(
                    avg_score=Avg('total_weighted_score')
                )['avg_score']
                
                scores_by_type[assessment_type] = {
                    'average_score': float(avg_score) if avg_score else 0,
                    'count': type_assessments.count(),
                    'latest_date': type_assessments.order_by('-assessment_date').first().assessment_date
                }
        
        # Overall statistics
        overall_stats = assessments.aggregate(
            total_count=Count('id'),
            avg_score=Avg('total_weighted_score'),
            max_score=Max('total_weighted_score'),
            min_score=Min('total_weighted_score')
        )
        
        # Decision band distribution
        decision_distribution = {}
        for band in DecisionBand:
            count = assessments.filter(decision_band=band).count()
            decision_distribution[band] = count
        
        self.aggregated_scores = {
            'by_type': scores_by_type,
            'overall': {
                'total_assessments': overall_stats['total_count'],
                'average_score': float(overall_stats['avg_score']) if overall_stats['avg_score'] else 0,
                'highest_score': float(overall_stats['max_score']) if overall_stats['max_score'] else 0,
                'lowest_score': float(overall_stats['min_score']) if overall_stats['min_score'] else 0,
            },
            'decision_distribution': decision_distribution,
            'last_updated': timezone.now().isoformat()
        }
        
        self.save(update_fields=['aggregated_scores'])
    
    @transaction.atomic
    def transition_status(self, new_status: str, user: User, notes: str = '') -> None:
        """Transition case to new status with validation and audit trail."""
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
            'archived': []  # No transitions from archived
        }
        
        if new_status not in valid_transitions.get(self.case_status, []):
            raise ValidationError(
                f"Invalid status transition from {self.case_status} to {new_status}"
            )
        
        old_status = self.case_status
        self.case_status = new_status
        
        # Update workflow state
        if 'history' not in self.workflow_state:
            self.workflow_state['history'] = []
        
        self.workflow_state['history'].append({
            'from_status': old_status,
            'to_status': new_status,
            'timestamp': timezone.now().isoformat(),
            'user': user.email,
            'notes': notes
        })
        
        # Update completion dates
        if new_status == 'completed':
            self.actual_completion_date = date.today()
        
        # Update overall risk when moving to decision
        if new_status == 'decision_pending':
            self.overall_risk_level = self.calculate_overall_risk()
            self.update_aggregated_scores()
        
        self.save()
        
        # Create audit trail
        AuditTrail.objects.create(
            group=self.group,
            entity_type='DueDiligenceCase',
            entity_id=self.id,
            action_type='update',
            changed_fields={
                'case_status': {
                    'old': old_status,
                    'new': new_status
                }
            },
            change_summary=f'Case status changed from {old_status} to {new_status}',
            user=user,
            business_justification=notes,
            risk_assessment=RiskLevel.LOW
        )
    
    def make_decision(self, decision: str, user: User, conditions: List[str] = None, notes: str = '') -> None:
        """Record final decision on the case."""
        if self.case_status != 'decision_pending':
            raise ValidationError("Case must be in 'decision_pending' status to make a decision")
        
        valid_decisions = ['proceed', 'conditional', 'decline', 'defer']
        if decision not in valid_decisions:
            raise ValidationError(f"Invalid decision: {decision}")
        
        self.final_decision = decision
        self.decision_date = date.today()
        self.decision_maker = user
        
        if conditions:
            self.conditions = conditions
        
        # Transition to appropriate status
        if decision in ['proceed', 'conditional']:
            new_status = 'approved'
        elif decision == 'decline':
            new_status = 'rejected'
        else:  # defer
            new_status = 'on_hold'
        
        self.save()
        
        # Transition status
        self.transition_status(new_status, user, notes)
        
        # Create audit trail
        AuditTrail.objects.create(
            group=self.group,
            entity_type='DueDiligenceCase',
            entity_id=self.id,
            action_type='approve' if decision in ['proceed', 'conditional'] else 'reject',
            change_summary=f'Final decision: {decision}',
            user=user,
            business_justification=notes,
            risk_assessment=RiskLevel.HIGH  # Decisions are high-risk actions
        )
    
    def get_comprehensive_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary of the entire case."""
        return {
            'case_info': {
                'reference': self.case_reference,
                'name': self.case_name,
                'type': self.case_type,
                'status': self.case_status,
                'priority': self.priority,
                'completion_percentage': self.completion_percentage,
                'is_overdue': self.is_overdue,
                'days_until_due': self.days_until_due,
            },
            'entities': {
                'primary_partner': self.primary_partner.company_name if self.primary_partner else None,
                'scheme_count': self.schemes.count(),
                'schemes': list(self.schemes.values_list('scheme_name', flat=True))
            },
            'assessments': {
                'total': self.get_all_assessments().count(),
                'by_status': dict(
                    self.get_all_assessments().values('status').annotate(
                        count=Count('id')
                    ).values_list('status', 'count')
                ),
                'aggregated_scores': self.aggregated_scores
            },
            'compliance': self.get_compliance_status(),
            'performance': self.get_performance_summary(),
            'esg': self.get_esg_summary(),
            'risk': {
                'overall_risk_level': self.overall_risk_level or self.calculate_overall_risk(),
                'risk_factors': self._identify_risk_factors()
            },
            'decision': {
                'final_decision': self.final_decision,
                'decision_date': self.decision_date,
                'decision_maker': self.decision_maker.get_full_name() if self.decision_maker else None,
                'conditions': self.conditions
            },
            'team': {
                'lead_assessor': self.lead_assessor.get_full_name(),
                'team_size': self.assessment_team.count(),
                'team_members': list(
                    self.assessment_team.values_list('email', flat=True)
                )
            }
        }
    
    def _identify_risk_factors(self) -> List[Dict[str, Any]]:
        """Identify specific risk factors for the case."""
        risk_factors = []
        
        # Compliance risks
        compliance = self.get_compliance_status()
        if compliance['non_compliant'] > 0:
            risk_factors.append({
                'category': 'Compliance',
                'risk': 'Non-compliant items',
                'severity': 'HIGH',
                'details': f"{compliance['non_compliant']} non-compliant requirements"
            })
        
        if compliance['expiring_soon'] > 0:
            risk_factors.append({
                'category': 'Compliance',
                'risk': 'Expiring compliance',
                'severity': 'MEDIUM',
                'details': f"{compliance['expiring_soon']} items expiring within 90 days"
            })
        
        # Performance risks
        performance = self.get_performance_summary()
        if performance['target_achievement_rate'] < 70:
            risk_factors.append({
                'category': 'Performance',
                'risk': 'Poor target achievement',
                'severity': 'HIGH',
                'details': f"Only {performance['target_achievement_rate']}% of targets met"
            })
        
        if performance['requiring_action'] > 3:
            risk_factors.append({
                'category': 'Performance',
                'risk': 'Multiple metrics requiring action',
                'severity': 'MEDIUM',
                'details': f"{performance['requiring_action']} metrics need attention"
            })
        
        # ESG risks
        esg = self.get_esg_summary()
        if esg['has_esg_assessment'] and esg['rating'] in ['B', 'CCC']:
            risk_factors.append({
                'category': 'ESG',
                'risk': 'Poor ESG rating',
                'severity': 'HIGH',
                'details': f"ESG rating of {esg['rating']}"
            })
        
        # Assessment risks
        assessments = self.get_all_assessments()
        rejected = assessments.filter(decision_band=DecisionBand.REJECT).count()
        if rejected > 0:
            risk_factors.append({
                'category': 'Assessment',
                'risk': 'Rejected assessments',
                'severity': 'CRITICAL',
                'details': f"{rejected} assessments rejected"
            })
        
        return risk_factors


class CaseChecklistItem(BaseAssessmentModel):
    """
    Checklist items for due diligence cases to ensure completeness.
    
    Provides a systematic way to track required tasks and documentation
    for each due diligence case.
    """
    
    case = models.ForeignKey(
        DueDiligenceCase,
        on_delete=models.CASCADE,
        related_name='checklist_items',
        help_text="Due diligence case this checklist item belongs to"
    )
    
    category = models.CharField(
        max_length=50,
        choices=[
            ('documentation', 'Documentation'),
            ('financial', 'Financial Analysis'),
            ('legal', 'Legal Review'),
            ('technical', 'Technical Assessment'),
            ('compliance', 'Compliance Check'),
            ('esg', 'ESG Assessment'),
            ('market', 'Market Analysis'),
            ('operational', 'Operational Review'),
        ],
        help_text="Category of checklist item"
    )
    
    item_name = models.CharField(
        max_length=200,
        help_text="Name of the checklist item"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Detailed description of what needs to be completed"
    )
    
    is_required = models.BooleanField(
        default=True,
        help_text="Whether this item is required for case completion"
    )
    
    is_completed = models.BooleanField(
        default=False,
        help_text="Whether this item has been completed"
    )
    
    completed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='completed_checklist_items',
        null=True,
        blank=True,
        help_text="User who completed this item"
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this item was completed"
    )
    
    due_date = models.DateField(
        null=True,
        blank=True,
        help_text="Due date for this checklist item"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this checklist item"
    )
    
    attachments = models.JSONField(
        default=list,
        help_text="List of attachment references"
    )
    
    class Meta:
        db_table = 'case_checklist_items'
        verbose_name = 'Case Checklist Item'
        verbose_name_plural = 'Case Checklist Items'
        ordering = ['category', 'item_name']
        unique_together = ['case', 'category', 'item_name']
    
    def __str__(self) -> str:
        return f"{self.case.case_reference} - {self.category}: {self.item_name}"
    
    def mark_complete(self, user: User, notes: str = '') -> None:
        """Mark checklist item as complete."""
        self.is_completed = True
        self.completed_by = user
        self.completed_at = timezone.now()
        if notes:
            self.notes = notes
        self.save()
        
        # Create audit trail
        AuditTrail.objects.create(
            group=self.case.group,
            entity_type='CaseChecklistItem',
            entity_id=self.id,
            action_type='update',
            change_summary=f'Checklist item "{self.item_name}" marked as complete',
            user=user,
            risk_assessment=RiskLevel.LOW
        )


class CaseTimeline(BaseAssessmentModel):
    """
    Timeline events for due diligence cases.
    
    Tracks all significant events and milestones in the due diligence process
    for audit and review purposes.
    """
    
    case = models.ForeignKey(
        DueDiligenceCase,
        on_delete=models.CASCADE,
        related_name='timeline_events',
        help_text="Due diligence case this event belongs to"
    )
    
    event_type = models.CharField(
        max_length=50,
        choices=[
            ('created', 'Case Created'),
            ('status_change', 'Status Changed'),
            ('assessment_added', 'Assessment Added'),
            ('document_uploaded', 'Document Uploaded'),
            ('team_change', 'Team Changed'),
            ('milestone', 'Milestone Reached'),
            ('issue_raised', 'Issue Raised'),
            ('issue_resolved', 'Issue Resolved'),
            ('decision', 'Decision Made'),
            ('note', 'Note Added'),
        ],
        help_text="Type of timeline event"
    )
    
    event_title = models.CharField(
        max_length=200,
        help_text="Title of the event"
    )
    
    event_description = models.TextField(
        help_text="Detailed description of the event"
    )
    
    event_date = models.DateTimeField(
        default=timezone.now,
        help_text="When the event occurred"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='timeline_events_created',
        help_text="User who created this timeline entry"
    )
    
    is_significant = models.BooleanField(
        default=False,
        help_text="Whether this is a significant milestone event"
    )
    
    metadata = models.JSONField(
        default=dict,
        help_text="Additional metadata about the event"
    )
    
    class Meta:
        db_table = 'case_timeline_events'
        verbose_name = 'Case Timeline Event'
        verbose_name_plural = 'Case Timeline Events'
        ordering = ['-event_date']
    
    def __str__(self) -> str:
        return f"{self.case.case_reference} - {self.event_date}: {self.event_title}"


def create_standard_checklist(case: DueDiligenceCase) -> None:
    """Create standard checklist items for a new case."""
    checklist_templates = [
        # Documentation
        {
            'category': 'documentation',
            'item_name': 'Corporate Structure Documentation',
            'description': 'Obtain and review corporate structure, ownership, and governance documents',
            'is_required': True
        },
        {
            'category': 'documentation',
            'item_name': 'Financial Statements',
            'description': 'Collect 3 years of audited financial statements',
            'is_required': True
        },
        {
            'category': 'documentation',
            'item_name': 'Management Accounts',
            'description': 'Review latest management accounts and budgets',
            'is_required': True
        },
        
        # Financial
        {
            'category': 'financial',
            'item_name': 'Financial Analysis',
            'description': 'Complete financial ratio analysis and trend assessment',
            'is_required': True
        },
        {
            'category': 'financial',
            'item_name': 'Cash Flow Analysis',
            'description': 'Analyze cash flow projections and working capital',
            'is_required': True
        },
        {
            'category': 'financial',
            'item_name': 'Debt Review',
            'description': 'Review existing debt facilities and covenants',
            'is_required': True
        },
        
        # Legal
        {
            'category': 'legal',
            'item_name': 'Legal Due Diligence',
            'description': 'Complete legal review of contracts and agreements',
            'is_required': True
        },
        {
            'category': 'legal',
            'item_name': 'Litigation Check',
            'description': 'Review any ongoing or potential litigation',
            'is_required': True
        },
        
        # Compliance
        {
            'category': 'compliance',
            'item_name': 'Regulatory Compliance Review',
            'description': 'Verify compliance with all relevant regulations',
            'is_required': True
        },
        {
            'category': 'compliance',
            'item_name': 'License Verification',
            'description': 'Verify all required licenses and permits',
            'is_required': True
        },
        
        # ESG
        {
            'category': 'esg',
            'item_name': 'ESG Assessment',
            'description': 'Complete Environmental, Social, and Governance assessment',
            'is_required': case.case_type in ['full_dd', 'portfolio']
        },
        {
            'category': 'esg',
            'item_name': 'Sustainability Review',
            'description': 'Review sustainability policies and practices',
            'is_required': False
        },
        
        # Technical
        {
            'category': 'technical',
            'item_name': 'Technical Due Diligence',
            'description': 'Complete technical assessment of properties/assets',
            'is_required': case.case_type in ['scheme_only', 'full_dd']
        },
        {
            'category': 'technical',
            'item_name': 'Building Condition Survey',
            'description': 'Conduct building condition and maintenance review',
            'is_required': case.case_type in ['scheme_only', 'full_dd']
        },
        
        # Market
        {
            'category': 'market',
            'item_name': 'Market Analysis',
            'description': 'Complete market analysis and competitive positioning',
            'is_required': True
        },
        {
            'category': 'market',
            'item_name': 'Demand Assessment',
            'description': 'Assess demand dynamics and growth potential',
            'is_required': case.case_type in ['scheme_only', 'full_dd']
        },
        
        # Operational
        {
            'category': 'operational',
            'item_name': 'Management Team Assessment',
            'description': 'Evaluate management team capabilities and track record',
            'is_required': True
        },
        {
            'category': 'operational',
            'item_name': 'Operational Review',
            'description': 'Review operational processes and efficiency',
            'is_required': True
        },
    ]
    
    # Create checklist items
    for template in checklist_templates:
        CaseChecklistItem.objects.create(
            case=case,
            group=case.group,
            **template
        )
    
    # Create timeline event
    CaseTimeline.objects.create(
        case=case,
        group=case.group,
        event_type='created',
        event_title='Case Created',
        event_description=f'Due diligence case {case.case_reference} created with standard checklist',
        created_by=case.lead_assessor,
        is_significant=True
    )