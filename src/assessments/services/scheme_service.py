"""
PBSA Scheme business logic service.

Handles scheme-related operations including creation, validation,
financial analysis, and performance metrics.
"""

from typing import Dict, Any, Optional, List
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Count, Avg, Sum, Max, Min
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta

from accounts.models import User, Group
from ..models import PBSAScheme, DevelopmentPartner, Assessment
from .base import BaseService, ValidationServiceError, PermissionServiceError, NotFoundServiceError


class PBSASchemeService(BaseService):
    """Service for PBSA scheme business logic."""
    
    def create_scheme(self, scheme_data: Dict[str, Any]) -> PBSAScheme:
        """
        Create a new PBSA scheme with validation.
        
        Args:
            scheme_data: Dictionary containing scheme information
            
        Returns:
            Created PBSAScheme instance
            
        Raises:
            ValidationServiceError: If validation fails
            PermissionServiceError: If user lacks permission
            NotFoundServiceError: If developer not found
        """
        self._check_permission('create_scheme')
        
        # Validate required fields
        required_fields = ['scheme_name', 'developer', 'total_beds', 'target_location', 'total_investment']
        for field in required_fields:
            if not scheme_data.get(field):
                raise ValidationServiceError(f"Field '{field}' is required")
        
        # Get and validate developer
        try:
            if isinstance(scheme_data['developer'], str):
                developer = DevelopmentPartner.objects.get(id=scheme_data['developer'])
                scheme_data['developer'] = developer
            else:
                developer = scheme_data['developer']
            
            self._validate_group_context(developer)
        except DevelopmentPartner.DoesNotExist:
            raise NotFoundServiceError(f"Developer {scheme_data['developer']} not found")
        
        # Business rule validation
        self._validate_scheme_data(scheme_data)
        
        # Add group context
        scheme_data['group'] = self.group
        
        try:
            scheme = PBSAScheme.objects.create(**scheme_data)
            
            self._log_operation('create_scheme', {
                'scheme_id': str(scheme.id),
                'scheme_name': scheme.scheme_name,
                'developer': developer.company_name
            })
            
            return scheme
            
        except ValidationError as e:
            self._handle_validation_error(e)
    
    def update_scheme(self, scheme_id: str, update_data: Dict[str, Any]) -> PBSAScheme:
        """
        Update PBSA scheme with validation.
        
        Args:
            scheme_id: ID of scheme to update
            update_data: Dictionary containing fields to update
            
        Returns:
            Updated PBSAScheme instance
            
        Raises:
            NotFoundServiceError: If scheme not found
            PermissionServiceError: If user lacks permission
            ValidationServiceError: If validation fails
        """
        try:
            scheme = PBSAScheme.objects.get(id=scheme_id)
            self._validate_group_context(scheme)
            self._check_permission('update_scheme', scheme)
            
            # Validate update data
            self._validate_scheme_data(update_data, is_update=True)
            
            # Check if scheme has active assessments
            if self._has_active_assessments(scheme):
                restricted_fields = ['total_beds', 'total_investment', 'developer']
                for field in restricted_fields:
                    if field in update_data:
                        raise ValidationServiceError(
                            f"Cannot modify '{field}' while scheme has active assessments"
                        )
            
            # Update fields
            for field, value in update_data.items():
                if hasattr(scheme, field):
                    setattr(scheme, field, value)
            
            scheme.save()
            
            self._log_operation('update_scheme', {
                'scheme_id': str(scheme.id),
                'updated_fields': list(update_data.keys())
            })
            
            return scheme
            
        except PBSAScheme.DoesNotExist:
            raise NotFoundServiceError(f"PBSA scheme {scheme_id} not found")
        except ValidationError as e:
            self._handle_validation_error(e)
    
    def get_scheme_analysis(self, scheme_id: str) -> Dict[str, Any]:
        """
        Get comprehensive scheme analysis.
        
        Args:
            scheme_id: ID of scheme to analyze
            
        Returns:
            Dictionary with analysis data
            
        Raises:
            NotFoundServiceError: If scheme not found
        """
        try:
            scheme = PBSAScheme.objects.get(id=scheme_id)
            self._validate_group_context(scheme)
            self._check_permission('view_scheme', scheme)
            
            analysis = {
                'basic_info': self._get_basic_scheme_info(scheme),
                'financial_analysis': self._analyze_scheme_financials(scheme),
                'market_analysis': self._analyze_market_position(scheme),
                'risk_assessment': self._assess_scheme_risk(scheme),
                'benchmarking': self._benchmark_scheme(scheme),
                'assessment_history': self._get_assessment_history(scheme),
            }
            
            self._log_operation('get_scheme_analysis', {
                'scheme_id': str(scheme.id),
                'scheme_name': scheme.scheme_name
            })
            
            return analysis
            
        except PBSAScheme.DoesNotExist:
            raise NotFoundServiceError(f"PBSA scheme {scheme_id} not found")
    
    def calculate_scheme_metrics(self, scheme_id: str) -> Dict[str, Any]:
        """
        Calculate key performance metrics for scheme.
        
        Args:
            scheme_id: ID of scheme to analyze
            
        Returns:
            Dictionary with calculated metrics
            
        Raises:
            NotFoundServiceError: If scheme not found
        """
        try:
            scheme = PBSAScheme.objects.get(id=scheme_id)
            self._validate_group_context(scheme)
            self._check_permission('view_scheme', scheme)
            
            metrics = {
                'financial_metrics': self._calculate_financial_metrics(scheme),
                'operational_metrics': self._calculate_operational_metrics(scheme),
                'market_metrics': self._calculate_market_metrics(scheme),
                'performance_score': self._calculate_performance_score(scheme),
            }
            
            self._log_operation('calculate_scheme_metrics', {
                'scheme_id': str(scheme.id),
                'performance_score': metrics['performance_score']
            })
            
            return metrics
            
        except PBSAScheme.DoesNotExist:
            raise NotFoundServiceError(f"PBSA scheme {scheme_id} not found")
    
    def get_scheme_recommendations(self, scheme_id: str) -> List[Dict[str, Any]]:
        """
        Get recommendations for scheme improvement.
        
        Args:
            scheme_id: ID of scheme to analyze
            
        Returns:
            List of recommendation dictionaries
            
        Raises:
            NotFoundServiceError: If scheme not found
        """
        try:
            scheme = PBSAScheme.objects.get(id=scheme_id)
            self._validate_group_context(scheme)
            self._check_permission('view_scheme', scheme)
            
            recommendations = []
            
            # Size-based recommendations
            if scheme.total_beds < 50:
                recommendations.append({
                    'type': 'scale',
                    'priority': 'medium',
                    'title': 'Consider scheme scale optimization',
                    'description': 'Small schemes may have higher per-bed costs.',
                    'action_items': [
                        'Analyze economies of scale opportunities',
                        'Consider phased development approach',
                        'Review local demand studies'
                    ]
                })
            
            # Investment efficiency recommendations
            cost_per_bed = scheme.total_investment / scheme.total_beds if scheme.total_beds > 0 else 0
            market_benchmark = self._get_market_benchmark_cost_per_bed(scheme.target_location)
            
            if cost_per_bed > market_benchmark * 1.2:  # 20% above market
                recommendations.append({
                    'type': 'cost_optimization',
                    'priority': 'high',
                    'title': 'Cost optimization required',
                    'description': f'Cost per bed (£{cost_per_bed:,.0f}) is above market benchmark.',
                    'action_items': [
                        'Review construction specifications',
                        'Seek alternative suppliers',
                        'Consider value engineering options'
                    ]
                })
            
            # Location-based recommendations
            location_analysis = self._analyze_location_factors(scheme)
            if location_analysis['risk_level'] == 'HIGH':
                recommendations.append({
                    'type': 'location',
                    'priority': 'high',
                    'title': 'Location risk mitigation',
                    'description': 'Location presents higher than average risks.',
                    'action_items': location_analysis['mitigation_strategies']
                })
            
            # Developer track record recommendations
            developer_performance = self._assess_developer_track_record(scheme.developer)
            if developer_performance['experience_score'] < 50:
                recommendations.append({
                    'type': 'developer',
                    'priority': 'medium',
                    'title': 'Developer support needed',
                    'description': 'Developer may benefit from additional support.',
                    'action_items': [
                        'Provide mentorship or consulting',
                        'Consider joint venture partnerships',
                        'Implement enhanced monitoring'
                    ]
                })
            
            self._log_operation('get_scheme_recommendations', {
                'scheme_id': str(scheme.id),
                'recommendation_count': len(recommendations)
            })
            
            return recommendations
            
        except PBSAScheme.DoesNotExist:
            raise NotFoundServiceError(f"PBSA scheme {scheme_id} not found")
    
    def search_schemes(self,
                      search_term: str = None,
                      filters: Dict[str, Any] = None,
                      page_size: int = 50) -> Dict[str, Any]:
        """
        Search and filter PBSA schemes.
        
        Args:
            search_term: Optional search term
            filters: Optional filters dictionary
            page_size: Number of results per page
            
        Returns:
            Dictionary with search results and metadata
        """
        self._check_permission('view_schemes')
        
        # Build base queryset with group filtering
        queryset = self._filter_by_group_access(PBSAScheme.objects.all())
        
        # Apply search
        if search_term:
            queryset = queryset.filter(
                Q(scheme_name__icontains=search_term) |
                Q(target_location__icontains=search_term) |
                Q(developer__company_name__icontains=search_term)
            )
        
        # Apply filters
        if filters:
            queryset = self._apply_scheme_filters(queryset, filters)
        
        # Get results with related data
        queryset = queryset.select_related('developer')
        total_count = queryset.count()
        schemes = list(queryset[:page_size])
        
        results = {
            'schemes': [self._serialize_scheme_summary(s) for s in schemes],
            'total_count': total_count,
            'has_more': total_count > page_size,
            'search_term': search_term,
            'filters_applied': filters or {}
        }
        
        self._log_operation('search_schemes', {
            'search_term': search_term,
            'total_results': total_count
        })
        
        return results
    
    # Private helper methods
    
    def _validate_scheme_data(self, data: Dict[str, Any], is_update: bool = False):
        """Validate scheme data according to business rules."""
        
        # Total beds validation
        if 'total_beds' in data:
            if data['total_beds'] < 1:
                raise ValidationServiceError("Total beds must be at least 1")
            if data['total_beds'] > 10000:
                raise ValidationServiceError("Total beds seems unreasonably high")
        
        # Investment validation
        if 'total_investment' in data:
            if data['total_investment'] < 10000:
                raise ValidationServiceError("Total investment must be at least £10,000")
            if data['total_investment'] > 1000000000:  # £1B
                raise ValidationServiceError("Total investment seems unreasonably high")
        
        # Cost per bed validation
        if 'total_beds' in data and 'total_investment' in data:
            cost_per_bed = data['total_investment'] / data['total_beds']
            if cost_per_bed < 1000:
                raise ValidationServiceError("Cost per bed seems unreasonably low")
            if cost_per_bed > 200000:
                raise ValidationServiceError("Cost per bed seems unreasonably high")
        
        # Timeline validation
        if 'expected_start_date' in data and 'expected_completion_date' in data:
            if data['expected_start_date'] and data['expected_completion_date']:
                if data['expected_start_date'] >= data['expected_completion_date']:
                    raise ValidationServiceError("Start date must be before completion date")
    
    def _has_active_assessments(self, scheme: PBSAScheme) -> bool:
        """Check if scheme has active assessments."""
        return Assessment.objects.filter(
            pbsa_scheme=scheme,
            status__in=[Assessment.AssessmentStatus.DRAFT, Assessment.AssessmentStatus.IN_REVIEW]
        ).exists()
    
    def _get_basic_scheme_info(self, scheme: PBSAScheme) -> Dict[str, Any]:
        """Get basic scheme information."""
        return {
            'scheme_name': scheme.scheme_name,
            'developer': scheme.developer.company_name,
            'total_beds': scheme.total_beds,
            'target_location': scheme.target_location,
            'total_investment': float(scheme.total_investment),
            'cost_per_bed': float(scheme.total_investment / scheme.total_beds) if scheme.total_beds > 0 else 0,
            'expected_start_date': scheme.expected_start_date.isoformat() if scheme.expected_start_date else None,
            'expected_completion_date': scheme.expected_completion_date.isoformat() if scheme.expected_completion_date else None,
        }
    
    def _analyze_scheme_financials(self, scheme: PBSAScheme) -> Dict[str, Any]:
        """Analyze scheme financial metrics."""
        cost_per_bed = scheme.total_investment / scheme.total_beds if scheme.total_beds > 0 else 0
        market_benchmark = self._get_market_benchmark_cost_per_bed(scheme.target_location)
        
        return {
            'total_investment': float(scheme.total_investment),
            'cost_per_bed': cost_per_bed,
            'market_benchmark_cost_per_bed': market_benchmark,
            'cost_variance_pct': ((cost_per_bed - market_benchmark) / market_benchmark * 100) if market_benchmark > 0 else 0,
            'investment_efficiency_score': self._calculate_investment_efficiency(scheme),
            'roi_projection': self._calculate_roi_projection(scheme),
        }
    
    def _analyze_market_position(self, scheme: PBSAScheme) -> Dict[str, Any]:
        """Analyze scheme market position."""
        # This would integrate with market data
        return {
            'location_attractiveness': self._score_location_attractiveness(scheme.target_location),
            'competition_density': self._assess_competition_density(scheme.target_location),
            'demand_supply_ratio': self._calculate_demand_supply_ratio(scheme.target_location),
            'market_growth_rate': self._get_market_growth_rate(scheme.target_location),
        }
    
    def _assess_scheme_risk(self, scheme: PBSAScheme) -> Dict[str, Any]:
        """Assess overall scheme risk."""
        risk_factors = []
        risk_score = 50  # Neutral start
        
        # Size risk
        if scheme.total_beds < 50:
            risk_factors.append("Small scheme size may impact economies of scale")
            risk_score += 10
        elif scheme.total_beds > 500:
            risk_factors.append("Large scheme size increases execution complexity")
            risk_score += 15
        
        # Investment risk
        cost_per_bed = scheme.total_investment / scheme.total_beds if scheme.total_beds > 0 else 0
        market_benchmark = self._get_market_benchmark_cost_per_bed(scheme.target_location)
        
        if cost_per_bed > market_benchmark * 1.3:
            risk_factors.append("High cost per bed compared to market")
            risk_score += 20
        
        # Developer risk
        developer_risk = self._assess_developer_risk(scheme.developer)
        risk_score += developer_risk['risk_adjustment']
        risk_factors.extend(developer_risk['risk_factors'])
        
        # Location risk
        location_risk = self._assess_location_risk(scheme.target_location)
        risk_score += location_risk['risk_adjustment']
        risk_factors.extend(location_risk['risk_factors'])
        
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
            'mitigation_strategies': self._get_risk_mitigation_strategies(risk_factors)
        }
    
    def _benchmark_scheme(self, scheme: PBSAScheme) -> Dict[str, Any]:
        """Benchmark scheme against similar projects."""
        # Find similar schemes for comparison
        similar_schemes = PBSAScheme.objects.filter(
            target_location=scheme.target_location,
            total_beds__range=(scheme.total_beds * 0.7, scheme.total_beds * 1.3)
        ).exclude(id=scheme.id)
        
        if not similar_schemes.exists():
            return {'similar_schemes_found': 0, 'benchmarks': {}}
        
        # Calculate benchmarks
        benchmarks = {
            'avg_cost_per_bed': similar_schemes.aggregate(
                avg=Avg(models.F('total_investment') / models.F('total_beds'))
            )['avg'] or 0,
            'avg_scheme_size': similar_schemes.aggregate(avg=Avg('total_beds'))['avg'] or 0,
            'avg_investment': similar_schemes.aggregate(avg=Avg('total_investment'))['avg'] or 0,
        }
        
        # Compare to scheme
        scheme_cost_per_bed = scheme.total_investment / scheme.total_beds if scheme.total_beds > 0 else 0
        
        return {
            'similar_schemes_found': similar_schemes.count(),
            'benchmarks': benchmarks,
            'comparisons': {
                'cost_per_bed_vs_benchmark': scheme_cost_per_bed - benchmarks['avg_cost_per_bed'],
                'size_vs_benchmark': scheme.total_beds - benchmarks['avg_scheme_size'],
                'investment_vs_benchmark': float(scheme.total_investment) - benchmarks['avg_investment'],
            }
        }
    
    def _get_assessment_history(self, scheme: PBSAScheme) -> Dict[str, Any]:
        """Get assessment history for scheme."""
        assessments = Assessment.objects.filter(pbsa_scheme=scheme).order_by('-created_at')
        
        return {
            'total_assessments': assessments.count(),
            'latest_status': assessments.first().status if assessments.exists() else None,
            'approved_count': assessments.filter(status=Assessment.AssessmentStatus.APPROVED).count(),
            'rejected_count': assessments.filter(status=Assessment.AssessmentStatus.REJECTED).count(),
            'pending_count': assessments.filter(
                status__in=[Assessment.AssessmentStatus.DRAFT, Assessment.AssessmentStatus.IN_REVIEW]
            ).count(),
        }
    
    # Placeholder methods for complex calculations
    # These would be implemented with actual business logic and data
    
    def _get_market_benchmark_cost_per_bed(self, location: str) -> float:
        """Get market benchmark cost per bed for location."""
        # This would query market data
        location_benchmarks = {
            'london': 75000,
            'manchester': 55000,
            'birmingham': 50000,
            'leeds': 45000,
            'default': 60000
        }
        return location_benchmarks.get(location.lower(), location_benchmarks['default'])
    
    def _score_location_attractiveness(self, location: str) -> int:
        """Score location attractiveness (0-100)."""
        # This would use market data, demographics, etc.
        return 75  # Placeholder
    
    def _assess_competition_density(self, location: str) -> str:
        """Assess competition density in location."""
        # This would analyze competitor presence
        return 'MEDIUM'  # Placeholder
    
    def _calculate_demand_supply_ratio(self, location: str) -> float:
        """Calculate demand/supply ratio for location."""
        # This would use market research data
        return 1.2  # Placeholder
    
    def _get_market_growth_rate(self, location: str) -> float:
        """Get market growth rate for location."""
        # This would use market data
        return 5.5  # Placeholder percentage
    
    def _calculate_financial_metrics(self, scheme: PBSAScheme) -> Dict[str, Any]:
        """Calculate financial metrics for scheme."""
        cost_per_bed = scheme.total_investment / scheme.total_beds if scheme.total_beds > 0 else 0
        
        return {
            'cost_per_bed': cost_per_bed,
            'investment_density': float(scheme.total_investment) / 1000000,  # Investment in millions
            'scale_efficiency': min(scheme.total_beds / 100, 2.0),  # Efficiency based on scale
        }
    
    def _calculate_operational_metrics(self, scheme: PBSAScheme) -> Dict[str, Any]:
        """Calculate operational metrics for scheme."""
        return {
            'bed_capacity': scheme.total_beds,
            'development_complexity': 'MEDIUM',  # Would be calculated based on various factors
            'timeline_feasibility': 'GOOD',  # Would analyze timeline vs. scope
        }
    
    def _calculate_market_metrics(self, scheme: PBSAScheme) -> Dict[str, Any]:
        """Calculate market-related metrics for scheme."""
        return {
            'market_position_score': self._score_location_attractiveness(scheme.target_location),
            'competition_level': self._assess_competition_density(scheme.target_location),
            'demand_strength': 'STRONG',  # Would be calculated from market data
        }
    
    def _calculate_performance_score(self, scheme: PBSAScheme) -> int:
        """Calculate overall performance score for scheme."""
        financial_score = self._calculate_financial_metrics(scheme)['scale_efficiency'] * 30
        market_score = self._score_location_attractiveness(scheme.target_location) * 0.4
        developer_score = self._assess_developer_track_record(scheme.developer)['experience_score'] * 0.3
        
        return min(int(financial_score + market_score + developer_score), 100)
    
    def _assess_developer_track_record(self, developer: DevelopmentPartner) -> Dict[str, Any]:
        """Assess developer track record."""
        experience_score = min(developer.years_of_pbsa_experience * 10, 50) if developer.years_of_pbsa_experience else 0
        portfolio_score = min(developer.completed_pbsa_schemes * 5, 30) if developer.completed_pbsa_schemes else 0
        
        return {
            'experience_score': experience_score + portfolio_score,
            'track_record': 'GOOD' if (experience_score + portfolio_score) > 60 else 'MODERATE'
        }
    
    def _apply_scheme_filters(self, queryset, filters: Dict[str, Any]):
        """Apply filters to scheme queryset."""
        if 'min_beds' in filters:
            queryset = queryset.filter(total_beds__gte=filters['min_beds'])
        
        if 'max_beds' in filters:
            queryset = queryset.filter(total_beds__lte=filters['max_beds'])
        
        if 'min_investment' in filters:
            queryset = queryset.filter(total_investment__gte=filters['min_investment'])
        
        if 'max_investment' in filters:
            queryset = queryset.filter(total_investment__lte=filters['max_investment'])
        
        if 'location' in filters:
            queryset = queryset.filter(target_location__icontains=filters['location'])
        
        if 'developer_id' in filters:
            queryset = queryset.filter(developer_id=filters['developer_id'])
        
        return queryset
    
    def _serialize_scheme_summary(self, scheme: PBSAScheme) -> Dict[str, Any]:
        """Serialize scheme for summary display."""
        return {
            'id': str(scheme.id),
            'scheme_name': scheme.scheme_name,
            'developer': scheme.developer.company_name,
            'total_beds': scheme.total_beds,
            'target_location': scheme.target_location,
            'total_investment': float(scheme.total_investment),
            'cost_per_bed': float(scheme.total_investment / scheme.total_beds) if scheme.total_beds > 0 else 0,
            'created_at': scheme.created_at.isoformat() if scheme.created_at else None
        }