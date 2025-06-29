"""
Development Partner business logic service.

Handles partner-related operations including creation, validation,
relationship management, and performance analytics.
"""

from typing import Dict, Any, Optional, List
from django.db import transaction
from django.db.models import Q, Count, Avg, Sum
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta

from accounts.models import User, Group
from ..models import DevelopmentPartner, Assessment, PBSAScheme
from .base import BaseService, ValidationServiceError, PermissionServiceError, NotFoundServiceError


class DevelopmentPartnerService(BaseService):
    """Service for development partner business logic."""
    
    def create_partner(self, partner_data: Dict[str, Any]) -> DevelopmentPartner:
        """
        Create a new development partner with validation.
        
        Args:
            partner_data: Dictionary containing partner information
            
        Returns:
            Created DevelopmentPartner instance
            
        Raises:
            ValidationServiceError: If validation fails
            PermissionServiceError: If user lacks permission
        """
        self._check_permission('create_partner')
        
        # Validate required fields
        required_fields = ['company_name', 'headquarter_city', 'headquarter_country']
        for field in required_fields:
            if not partner_data.get(field):
                raise ValidationServiceError(f"Field '{field}' is required")
        
        # Business rule validation
        self._validate_partner_data(partner_data)
        
        # Add group and audit info
        partner_data['group'] = self.group
        
        try:
            partner = DevelopmentPartner.objects.create(**partner_data)
            
            self._log_operation('create_partner', {
                'partner_id': str(partner.id),
                'company_name': partner.company_name
            })
            
            return partner
            
        except ValidationError as e:
            self._handle_validation_error(e)
    
    def update_partner(self, partner_id: str, update_data: Dict[str, Any]) -> DevelopmentPartner:
        """
        Update development partner with validation.
        
        Args:
            partner_id: ID of partner to update
            update_data: Dictionary containing fields to update
            
        Returns:
            Updated DevelopmentPartner instance
            
        Raises:
            NotFoundServiceError: If partner not found
            PermissionServiceError: If user lacks permission
            ValidationServiceError: If validation fails
        """
        try:
            partner = DevelopmentPartner.objects.get(id=partner_id)
            self._validate_group_context(partner)
            self._check_permission('update_partner', partner)
            
            # Validate update data
            self._validate_partner_data(update_data, is_update=True)
            
            # Update fields
            for field, value in update_data.items():
                if hasattr(partner, field):
                    setattr(partner, field, value)
            
            partner.save()
            
            self._log_operation('update_partner', {
                'partner_id': str(partner.id),
                'updated_fields': list(update_data.keys())
            })
            
            return partner
            
        except DevelopmentPartner.DoesNotExist:
            raise NotFoundServiceError(f"Development partner {partner_id} not found")
        except ValidationError as e:
            self._handle_validation_error(e)
    
    def get_partner_performance(self, partner_id: str) -> Dict[str, Any]:
        """
        Get comprehensive partner performance metrics.
        
        Args:
            partner_id: ID of partner to analyze
            
        Returns:
            Dictionary with performance metrics
            
        Raises:
            NotFoundServiceError: If partner not found
        """
        try:
            partner = DevelopmentPartner.objects.get(id=partner_id)
            self._validate_group_context(partner)
            self._check_permission('view_partner', partner)
            
            # Get related assessments
            assessments = Assessment.objects.filter(development_partner=partner)
            
            # Calculate metrics
            performance = {
                'basic_info': self._get_basic_partner_info(partner),
                'assessment_metrics': self._calculate_assessment_metrics(assessments),
                'scheme_metrics': self._calculate_scheme_metrics(partner),
                'financial_metrics': self._calculate_financial_metrics(partner),
                'risk_assessment': self._assess_partner_risk(partner, assessments),
                'performance_trends': self._calculate_performance_trends(partner),
            }
            
            self._log_operation('get_partner_performance', {
                'partner_id': str(partner.id),
                'total_assessments': assessments.count()
            })
            
            return performance
            
        except DevelopmentPartner.DoesNotExist:
            raise NotFoundServiceError(f"Development partner {partner_id} not found")
    
    def get_partner_recommendations(self, partner_id: str) -> List[Dict[str, Any]]:
        """
        Get recommendations for partner improvement.
        
        Args:
            partner_id: ID of partner to analyze
            
        Returns:
            List of recommendation dictionaries
            
        Raises:
            NotFoundServiceError: If partner not found
        """
        try:
            partner = DevelopmentPartner.objects.get(id=partner_id)
            self._validate_group_context(partner)
            self._check_permission('view_partner', partner)
            
            recommendations = []
            
            # Experience-based recommendations
            if partner.years_of_pbsa_experience < 3:
                recommendations.append({
                    'type': 'experience',
                    'priority': 'high',
                    'title': 'Gain more PBSA experience',
                    'description': 'Partner has limited PBSA experience. Consider mentorship or joint ventures.',
                    'action_items': [
                        'Complete additional PBSA projects',
                        'Partner with experienced developers',
                        'Attend PBSA industry training'
                    ]
                })
            
            # Financial recommendations
            if partner.completed_pbsa_schemes < 5:
                recommendations.append({
                    'type': 'portfolio',
                    'priority': 'medium',
                    'title': 'Expand project portfolio',
                    'description': 'Building a larger portfolio will improve assessment outcomes.',
                    'action_items': [
                        'Target smaller initial projects',
                        'Focus on successful delivery',
                        'Document project outcomes'
                    ]
                })
            
            # Location diversification
            schemes = PBSAScheme.objects.filter(developer=partner)
            unique_locations = schemes.values('target_location').distinct().count()
            
            if unique_locations < 3:
                recommendations.append({
                    'type': 'diversification',
                    'priority': 'low',
                    'title': 'Diversify geographic presence',
                    'description': 'Operating in multiple locations reduces risk.',
                    'action_items': [
                        'Research new markets',
                        'Build local partnerships',
                        'Understand regional regulations'
                    ]
                })
            
            self._log_operation('get_partner_recommendations', {
                'partner_id': str(partner.id),
                'recommendation_count': len(recommendations)
            })
            
            return recommendations
            
        except DevelopmentPartner.DoesNotExist:
            raise NotFoundServiceError(f"Development partner {partner_id} not found")
    
    def search_partners(self, 
                       search_term: str = None,
                       filters: Dict[str, Any] = None,
                       page_size: int = 50) -> Dict[str, Any]:
        """
        Search and filter development partners.
        
        Args:
            search_term: Optional search term
            filters: Optional filters dictionary
            page_size: Number of results per page
            
        Returns:
            Dictionary with search results and metadata
        """
        self._check_permission('view_partners')
        
        # Build base queryset with group filtering
        queryset = self._filter_by_group_access(DevelopmentPartner.objects.all())
        
        # Apply search
        if search_term:
            queryset = queryset.filter(
                Q(company_name__icontains=search_term) |
                Q(trading_name__icontains=search_term) |
                Q(headquarter_city__icontains=search_term)
            )
        
        # Apply filters
        if filters:
            queryset = self._apply_partner_filters(queryset, filters)
        
        # Get results
        total_count = queryset.count()
        partners = list(queryset[:page_size])
        
        results = {
            'partners': [self._serialize_partner_summary(p) for p in partners],
            'total_count': total_count,
            'has_more': total_count > page_size,
            'search_term': search_term,
            'filters_applied': filters or {}
        }
        
        self._log_operation('search_partners', {
            'search_term': search_term,
            'total_results': total_count
        })
        
        return results
    
    # Private helper methods
    
    def _validate_partner_data(self, data: Dict[str, Any], is_update: bool = False):
        """Validate partner data according to business rules."""
        
        # Company name validation
        if 'company_name' in data:
            if len(data['company_name']) < 2:
                raise ValidationServiceError("Company name must be at least 2 characters")
        
        # Year established validation
        if 'year_established' in data and data['year_established']:
            current_year = datetime.now().year
            if data['year_established'] > current_year:
                raise ValidationServiceError("Year established cannot be in the future")
            if data['year_established'] < 1800:
                raise ValidationServiceError("Year established seems too old")
        
        # Employee count validation
        if 'number_of_employees' in data and data['number_of_employees']:
            if data['number_of_employees'] < 1:
                raise ValidationServiceError("Number of employees must be positive")
        
        # PBSA experience validation
        if 'years_of_pbsa_experience' in data and data['years_of_pbsa_experience']:
            if data['years_of_pbsa_experience'] < 0:
                raise ValidationServiceError("PBSA experience cannot be negative")
            
            # Check consistency with year established
            if 'year_established' in data and data['year_established']:
                max_experience = current_year - data['year_established']
                if data['years_of_pbsa_experience'] > max_experience:
                    raise ValidationServiceError("PBSA experience cannot exceed company age")
    
    def _get_basic_partner_info(self, partner: DevelopmentPartner) -> Dict[str, Any]:
        """Get basic partner information."""
        return {
            'company_name': partner.company_name,
            'trading_name': partner.trading_name,
            'year_established': partner.year_established,
            'headquarter_location': f"{partner.headquarter_city}, {partner.headquarter_country}",
            'employees': partner.number_of_employees,
            'pbsa_experience_years': partner.years_of_pbsa_experience,
            'website': partner.website_url,
        }
    
    def _calculate_assessment_metrics(self, assessments) -> Dict[str, Any]:
        """Calculate assessment-related metrics."""
        total_assessments = assessments.count()
        
        if total_assessments == 0:
            return {
                'total_assessments': 0,
                'approval_rate': 0,
                'average_score': None,
                'recent_assessments': 0
            }
        
        approved_count = assessments.filter(
            status=Assessment.AssessmentStatus.APPROVED
        ).count()
        
        # Calculate approval rate
        approval_rate = (approved_count / total_assessments) * 100 if total_assessments > 0 else 0
        
        # Recent assessments (last 6 months)
        six_months_ago = datetime.now() - timedelta(days=180)
        recent_count = assessments.filter(created_at__gte=six_months_ago).count()
        
        return {
            'total_assessments': total_assessments,
            'approved_assessments': approved_count,
            'approval_rate': round(approval_rate, 2),
            'recent_assessments': recent_count,
        }
    
    def _calculate_scheme_metrics(self, partner: DevelopmentPartner) -> Dict[str, Any]:
        """Calculate scheme-related metrics."""
        schemes = PBSAScheme.objects.filter(developer=partner)
        
        if not schemes.exists():
            return {
                'total_schemes': 0,
                'total_beds': 0,
                'average_scheme_size': 0,
                'total_investment': 0
            }
        
        total_beds = schemes.aggregate(total=Sum('total_beds'))['total'] or 0
        total_investment = schemes.aggregate(total=Sum('total_investment'))['total'] or 0
        avg_size = schemes.aggregate(avg=Avg('total_beds'))['avg'] or 0
        
        return {
            'total_schemes': schemes.count(),
            'total_beds': total_beds,
            'average_scheme_size': round(avg_size, 1),
            'total_investment': float(total_investment),
            'unique_locations': schemes.values('target_location').distinct().count()
        }
    
    def _calculate_financial_metrics(self, partner: DevelopmentPartner) -> Dict[str, Any]:
        """Calculate financial metrics."""
        # This would integrate with actual financial data
        # For now, return basic computed fields
        return {
            'pbsa_specialization_pct': partner.pbsa_specialization_pct,
            'avg_scheme_size': partner.avg_pbsa_scheme_size,
            'completed_schemes': partner.completed_pbsa_schemes,
            'beds_delivered': partner.total_pbsa_beds_delivered,
        }
    
    def _assess_partner_risk(self, partner: DevelopmentPartner, assessments) -> Dict[str, Any]:
        """Assess overall partner risk."""
        risk_factors = []
        risk_score = 50  # Neutral start
        
        # Experience risk
        if partner.years_of_pbsa_experience < 2:
            risk_factors.append("Limited PBSA experience")
            risk_score += 20
        elif partner.years_of_pbsa_experience > 10:
            risk_score -= 10
        
        # Portfolio risk
        if partner.completed_pbsa_schemes < 3:
            risk_factors.append("Small project portfolio")
            risk_score += 15
        
        # Assessment history risk
        approval_rate = self._calculate_assessment_metrics(assessments)['approval_rate']
        if approval_rate < 50:
            risk_factors.append("Low assessment approval rate")
            risk_score += 25
        elif approval_rate > 80:
            risk_score -= 15
        
        # Determine risk level
        if risk_score >= 80:
            risk_level = 'HIGH'
        elif risk_score >= 60:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'LOW'
        
        return {
            'risk_level': risk_level,
            'risk_score': min(max(risk_score, 0), 100),
            'risk_factors': risk_factors,
            'mitigation_suggestions': self._get_risk_mitigation_suggestions(risk_factors)
        }
    
    def _calculate_performance_trends(self, partner: DevelopmentPartner) -> Dict[str, Any]:
        """Calculate performance trends over time."""
        # This would analyze trends in assessments, schemes, etc.
        # Simplified for now
        return {
            'assessment_trend': 'stable',
            'scheme_development_trend': 'growing',
            'geographic_expansion': 'moderate'
        }
    
    def _get_risk_mitigation_suggestions(self, risk_factors: List[str]) -> List[str]:
        """Get suggestions for mitigating identified risks."""
        suggestions = []
        
        if "Limited PBSA experience" in risk_factors:
            suggestions.append("Consider joint ventures with experienced developers")
            suggestions.append("Start with smaller, lower-risk projects")
        
        if "Small project portfolio" in risk_factors:
            suggestions.append("Focus on completing current projects successfully")
            suggestions.append("Document and showcase project outcomes")
        
        if "Low assessment approval rate" in risk_factors:
            suggestions.append("Review and address previous assessment feedback")
            suggestions.append("Improve financial documentation and processes")
        
        return suggestions
    
    def _apply_partner_filters(self, queryset, filters: Dict[str, Any]):
        """Apply filters to partner queryset."""
        
        if 'min_experience' in filters:
            queryset = queryset.filter(years_of_pbsa_experience__gte=filters['min_experience'])
        
        if 'min_schemes' in filters:
            queryset = queryset.filter(completed_pbsa_schemes__gte=filters['min_schemes'])
        
        if 'country' in filters:
            queryset = queryset.filter(headquarter_country=filters['country'])
        
        if 'min_employees' in filters:
            queryset = queryset.filter(number_of_employees__gte=filters['min_employees'])
        
        return queryset
    
    def _serialize_partner_summary(self, partner: DevelopmentPartner) -> Dict[str, Any]:
        """Serialize partner for summary display."""
        return {
            'id': str(partner.id),
            'company_name': partner.company_name,
            'trading_name': partner.trading_name,
            'location': f"{partner.headquarter_city}, {partner.headquarter_country}",
            'year_established': partner.year_established,
            'pbsa_experience': partner.years_of_pbsa_experience,
            'completed_schemes': partner.completed_pbsa_schemes,
            'created_at': partner.created_at.isoformat() if partner.created_at else None
        }