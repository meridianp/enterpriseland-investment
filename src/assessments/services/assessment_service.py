"""
Assessment business logic service.

Handles complex assessment operations including creation, approval workflows,
scoring calculations, and business rule validation.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Avg, Count, Max
from django.utils import timezone
from django.core.exceptions import ValidationError

from accounts.models import User, Group
from ..models import (
    Assessment, DevelopmentPartner, PBSAScheme, AssessmentStatus, 
    AssessmentDecision, FinancialInformation, CreditInformation
)
from .base import BaseService, ValidationServiceError, PermissionServiceError, NotFoundServiceError


class AssessmentService(BaseService):
    """Service for assessment business logic."""
    
    def create_assessment(self, 
                         development_partner_id: str,
                         pbsa_scheme_id: str,
                         assessment_type: str,
                         initial_data: Dict[str, Any] = None) -> Assessment:
        """
        Create a new assessment with business rule validation.
        
        Args:
            development_partner_id: ID of development partner
            pbsa_scheme_id: ID of PBSA scheme
            assessment_type: Type of assessment
            initial_data: Optional initial assessment data
            
        Returns:
            Created Assessment instance
            
        Raises:
            ValidationServiceError: If validation fails
            PermissionServiceError: If user lacks permission
            NotFoundServiceError: If related objects not found
        """
        self._check_permission('create_assessment')
        
        try:
            # Get related objects
            partner = DevelopmentPartner.objects.get(id=development_partner_id)
            scheme = PBSAScheme.objects.get(id=pbsa_scheme_id)
            
            # Validate group access
            self._validate_group_context(partner)
            self._validate_group_context(scheme)
            
            # Business rule validation
            self._validate_assessment_creation(partner, scheme, assessment_type)
            
            # Create assessment
            assessment_data = {
                'group': self.group,
                'development_partner': partner,
                'pbsa_scheme': scheme,
                'assessment_type': assessment_type,
                'status': AssessmentStatus.DRAFT,
                'created_by': self.user,
            }
            
            if initial_data:
                assessment_data.update(initial_data)
            
            assessment = Assessment.objects.create(**assessment_data)
            
            self._log_operation('create_assessment', {
                'assessment_id': str(assessment.id),
                'partner': partner.company_name,
                'scheme': scheme.scheme_name
            })
            
            return assessment
            
        except DevelopmentPartner.DoesNotExist:
            raise NotFoundServiceError(f"Development partner {development_partner_id} not found")
        except PBSAScheme.DoesNotExist:
            raise NotFoundServiceError(f"PBSA scheme {pbsa_scheme_id} not found")
        except ValidationError as e:
            self._handle_validation_error(e)
    
    def submit_assessment(self, assessment_id: str) -> Assessment:
        """
        Submit assessment for review with validation.
        
        Args:
            assessment_id: ID of assessment to submit
            
        Returns:
            Updated Assessment instance
            
        Raises:
            ValidationServiceError: If assessment is incomplete
            PermissionServiceError: If user lacks permission
            NotFoundServiceError: If assessment not found
        """
        try:
            assessment = Assessment.objects.get(id=assessment_id)
            self._validate_group_context(assessment)
            self._check_permission('submit_assessment', assessment)
            
            # Validate assessment is complete
            self._validate_assessment_completeness(assessment)
            
            # Business rules for submission
            if assessment.status != AssessmentStatus.DRAFT:
                raise ValidationServiceError("Only draft assessments can be submitted")
            
            # Update status
            assessment.status = AssessmentStatus.IN_REVIEW
            assessment.submitted_at = timezone.now()
            assessment.save()
            
            self._log_operation('submit_assessment', {
                'assessment_id': str(assessment.id),
                'status': assessment.status
            })
            
            return assessment
            
        except Assessment.DoesNotExist:
            raise NotFoundServiceError(f"Assessment {assessment_id} not found")
    
    def approve_assessment(self, 
                          assessment_id: str, 
                          decision: str,
                          comments: str = None) -> Assessment:
        """
        Approve or reject assessment.
        
        Args:
            assessment_id: ID of assessment to approve
            decision: Assessment decision
            comments: Optional approval comments
            
        Returns:
            Updated Assessment instance
            
        Raises:
            PermissionServiceError: If user lacks approval permission
            ValidationServiceError: If assessment cannot be approved
            NotFoundServiceError: If assessment not found
        """
        try:
            assessment = Assessment.objects.get(id=assessment_id)
            self._validate_group_context(assessment)
            self._check_permission('approve_assessment', assessment)
            
            # Validate user can approve
            if not self._can_user_approve(self.user):
                raise PermissionServiceError("User does not have approval authority")
            
            # Business rules for approval
            if assessment.status != AssessmentStatus.IN_REVIEW:
                raise ValidationServiceError("Only assessments in review can be approved/rejected")
            
            # Update assessment
            if decision in [AssessmentDecision.PREMIUM_PRIORITY, AssessmentDecision.ACCEPTABLE]:
                assessment.status = AssessmentStatus.APPROVED
            else:
                assessment.status = AssessmentStatus.REJECTED
            
            assessment.decision = decision
            assessment.approved_by = self.user
            assessment.approved_at = timezone.now()
            assessment.approval_comments = comments
            assessment.save()
            
            self._log_operation('approve_assessment', {
                'assessment_id': str(assessment.id),
                'decision': decision,
                'status': assessment.status
            })
            
            return assessment
            
        except Assessment.DoesNotExist:
            raise NotFoundServiceError(f"Assessment {assessment_id} not found")
    
    def calculate_assessment_score(self, assessment_id: str) -> Dict[str, Any]:
        """
        Calculate comprehensive assessment score.
        
        Args:
            assessment_id: ID of assessment to score
            
        Returns:
            Dictionary with score breakdown
            
        Raises:
            NotFoundServiceError: If assessment not found
        """
        try:
            assessment = Assessment.objects.get(id=assessment_id)
            self._validate_group_context(assessment)
            
            # Get related data
            financial_info = getattr(assessment, 'financial_information', None)
            credit_info = getattr(assessment, 'credit_information', None)
            
            # Calculate component scores
            scores = {
                'financial_score': self._calculate_financial_score(financial_info),
                'credit_score': self._calculate_credit_score(credit_info),
                'experience_score': self._calculate_experience_score(assessment.development_partner),
                'scheme_score': self._calculate_scheme_score(assessment.pbsa_scheme),
                'overall_score': 0,
                'risk_level': 'MEDIUM',
                'recommendation': 'REVIEW'
            }
            
            # Calculate weighted overall score
            weights = {
                'financial_score': 0.3,
                'credit_score': 0.25,
                'experience_score': 0.25,
                'scheme_score': 0.2
            }
            
            scores['overall_score'] = sum(
                scores[key] * weights[key] 
                for key in weights.keys()
            )
            
            # Determine risk level and recommendation
            scores['risk_level'] = self._determine_risk_level(scores['overall_score'])
            scores['recommendation'] = self._get_recommendation(scores['overall_score'])
            
            self._log_operation('calculate_score', {
                'assessment_id': str(assessment.id),
                'overall_score': scores['overall_score']
            })
            
            return scores
            
        except Assessment.DoesNotExist:
            raise NotFoundServiceError(f"Assessment {assessment_id} not found")
    
    def get_assessment_analytics(self, group_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get assessment analytics and metrics.
        
        Args:
            group_id: Optional group ID to filter by
            
        Returns:
            Dictionary with analytics data
        """
        self._check_permission('view_analytics')
        
        # Build queryset
        queryset = Assessment.objects.all()
        
        if group_id:
            queryset = queryset.filter(group_id=group_id)
        else:
            queryset = self._filter_by_group_access(queryset)
        
        # Calculate metrics
        total_assessments = queryset.count()
        
        status_breakdown = dict(
            queryset.values('status').annotate(count=Count('id'))
            .values_list('status', 'count')
        )
        
        decision_breakdown = dict(
            queryset.exclude(decision__isnull=True)
            .values('decision').annotate(count=Count('id'))
            .values_list('decision', 'count')
        )
        
        # Time-based metrics
        last_30_days = timezone.now() - timedelta(days=30)
        recent_assessments = queryset.filter(created_at__gte=last_30_days).count()
        
        avg_approval_time = self._calculate_average_approval_time(queryset)
        
        analytics = {
            'total_assessments': total_assessments,
            'recent_assessments': recent_assessments,
            'status_breakdown': status_breakdown,
            'decision_breakdown': decision_breakdown,
            'average_approval_time_days': avg_approval_time,
            'completion_rate': self._calculate_completion_rate(queryset),
        }
        
        self._log_operation('get_analytics', {'total_assessments': total_assessments})
        
        return analytics
    
    # Private helper methods
    
    def _validate_assessment_creation(self, partner: DevelopmentPartner, 
                                    scheme: PBSAScheme, assessment_type: str):
        """Validate business rules for assessment creation."""
        # Check if partner is eligible for assessment
        if partner.year_established and partner.year_established > datetime.now().year - 1:
            raise ValidationServiceError("Partner must be established for at least 1 year")
        
        # Check if scheme is ready for assessment
        if scheme.total_investment < 100000:
            raise ValidationServiceError("Scheme investment must be at least £100,000")
        
        # Check for duplicate assessments
        existing = Assessment.objects.filter(
            development_partner=partner,
            pbsa_scheme=scheme,
            status__in=[AssessmentStatus.DRAFT, AssessmentStatus.IN_REVIEW]
        ).exists()
        
        if existing:
            raise ValidationServiceError("An active assessment already exists for this partner and scheme")
    
    def _validate_assessment_completeness(self, assessment: Assessment):
        """Validate that assessment is complete enough for submission."""
        required_fields = ['assessment_type', 'development_partner', 'pbsa_scheme']
        
        for field in required_fields:
            if not getattr(assessment, field):
                raise ValidationServiceError(f"Field '{field}' is required for submission")
        
        # Check for required related data
        if assessment.assessment_type == Assessment.AssessmentType.FULL:
            if not hasattr(assessment, 'financial_information'):
                raise ValidationServiceError("Financial information required for full assessment")
    
    def _can_user_approve(self, user: User) -> bool:
        """Check if user has approval authority."""
        approval_roles = [User.Role.ADMIN, User.Role.PORTFOLIO_MANAGER]
        return user.role in approval_roles
    
    def _calculate_financial_score(self, financial_info: Optional[FinancialInformation]) -> float:
        """Calculate financial component score."""
        if not financial_info:
            return 0.0
        
        score = 50.0  # Base score
        
        # Revenue growth
        if financial_info.annual_revenue_current > financial_info.annual_revenue_previous:
            score += 20
        
        # Profitability
        if financial_info.ebitda_current > 0:
            score += 15
        
        # Debt ratio
        if hasattr(financial_info, 'debt_to_equity_ratio'):
            if financial_info.debt_to_equity_ratio < 0.3:
                score += 15
            elif financial_info.debt_to_equity_ratio < 0.6:
                score += 10
        
        return min(score, 100.0)
    
    def _calculate_credit_score(self, credit_info: Optional[CreditInformation]) -> float:
        """Calculate credit component score."""
        if not credit_info:
            return 50.0  # Neutral score if no credit info
        
        # This would integrate with actual credit scoring logic
        return 75.0  # Placeholder
    
    def _calculate_experience_score(self, partner: DevelopmentPartner) -> float:
        """Calculate experience component score."""
        score = 30.0  # Base score
        
        # Years of experience
        if partner.years_of_pbsa_experience:
            score += min(partner.years_of_pbsa_experience * 5, 30)
        
        # Completed schemes
        if partner.completed_pbsa_schemes:
            score += min(partner.completed_pbsa_schemes * 2, 20)
        
        # Beds delivered
        if partner.total_pbsa_beds_delivered:
            if partner.total_pbsa_beds_delivered > 1000:
                score += 20
            elif partner.total_pbsa_beds_delivered > 500:
                score += 15
            elif partner.total_pbsa_beds_delivered > 100:
                score += 10
        
        return min(score, 100.0)
    
    def _calculate_scheme_score(self, scheme: PBSAScheme) -> float:
        """Calculate scheme component score."""
        score = 40.0  # Base score
        
        # Scheme size
        if scheme.total_beds > 200:
            score += 20
        elif scheme.total_beds > 100:
            score += 15
        elif scheme.total_beds > 50:
            score += 10
        
        # Investment size
        if scheme.total_investment > 10000000:  # £10M+
            score += 25
        elif scheme.total_investment > 5000000:  # £5M+
            score += 20
        elif scheme.total_investment > 1000000:  # £1M+
            score += 15
        
        # Location (would need location scoring logic)
        score += 15  # Placeholder
        
        return min(score, 100.0)
    
    def _determine_risk_level(self, overall_score: float) -> str:
        """Determine risk level based on overall score."""
        if overall_score >= 80:
            return 'LOW'
        elif overall_score >= 60:
            return 'MEDIUM'
        else:
            return 'HIGH'
    
    def _get_recommendation(self, overall_score: float) -> str:
        """Get recommendation based on overall score."""
        if overall_score >= 85:
            return 'PREMIUM_PRIORITY'
        elif overall_score >= 70:
            return 'ACCEPTABLE'
        elif overall_score >= 50:
            return 'REVIEW'
        else:
            return 'REJECT'
    
    def _calculate_average_approval_time(self, queryset) -> Optional[float]:
        """Calculate average time from submission to approval."""
        approved = queryset.filter(
            status__in=[AssessmentStatus.APPROVED, AssessmentStatus.REJECTED],
            submitted_at__isnull=False,
            approved_at__isnull=False
        )
        
        if not approved.exists():
            return None
        
        total_time = sum(
            (assessment.approved_at - assessment.submitted_at).days
            for assessment in approved
            if assessment.approved_at and assessment.submitted_at
        )
        
        return total_time / approved.count() if approved.count() > 0 else None
    
    def _calculate_completion_rate(self, queryset) -> float:
        """Calculate assessment completion rate."""
        total = queryset.count()
        if total == 0:
            return 0.0
        
        completed = queryset.filter(
            status__in=[AssessmentStatus.APPROVED, AssessmentStatus.REJECTED]
        ).count()
        
        return (completed / total) * 100