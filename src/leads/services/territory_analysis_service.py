"""
Territory Analysis Service.

Provides intelligent territory analysis and lead assignment optimization using
geographic intelligence, workload balancing, and performance analytics.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Avg, Count, F, Max, Min, Sum, Case, When, IntegerField
from django.core.exceptions import ValidationError
from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.measure import Distance
from django.contrib.auth import get_user_model

from assessments.services.base import BaseService
from ..models import Lead, LeadScoringModel, LeadActivity
from geographic_intelligence.models import Neighborhood, University, PointOfInterest
from geographic_intelligence.services import GeographicIntelligenceService

User = get_user_model()
logger = logging.getLogger(__name__)


class TerritoryAnalysisService(BaseService):
    """
    Service for territory analysis and optimal lead assignment.
    
    Provides advanced algorithms for territory planning, workload balancing,
    and performance optimization based on geographic intelligence.
    """
    
    def __init__(self, user=None, group=None):
        super().__init__(user=user, group=group)
        self.model = Lead
    
    def analyze_territory_coverage(self, 
                                 assigned_user_id: str = None) -> Dict[str, Any]:
        """Analyze territory coverage and identify gaps."""
        self._check_permission('view_leads')
        
        try:
            # Get leads with geographic data
            leads_with_location = Lead.objects.filter(
                group=self.group,
                headquarters_location__isnull=False,
                geographic_analysis_date__isnull=False
            ).select_related('assigned_to', 'target_neighborhood')
            
            if assigned_user_id:
                user_leads = leads_with_location.filter(assigned_to_id=assigned_user_id)
            else:
                user_leads = leads_with_location
            
            # Territory coverage analysis
            coverage_analysis = self._calculate_territory_coverage(user_leads)
            
            # Geographic distribution
            geographic_distribution = self._analyze_geographic_distribution(user_leads)
            
            # Performance metrics by territory
            performance_metrics = self._calculate_territory_performance(user_leads)
            
            # Coverage gaps and opportunities
            coverage_gaps = self._identify_coverage_gaps(leads_with_location, user_leads)
            
            return {
                'assigned_user_id': assigned_user_id,
                'total_leads': user_leads.count(),
                'coverage_analysis': coverage_analysis,
                'geographic_distribution': geographic_distribution,
                'performance_metrics': performance_metrics,
                'coverage_gaps': coverage_gaps,
                'analysis_date': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f'Error analyzing territory coverage: {str(e)}')
            raise ValidationError(f'Failed to analyze territory: {str(e)}')
    
    def optimize_lead_assignments(self, 
                                optimization_criteria: Dict[str, Any] = None) -> Dict[str, Any]:
        """Optimize lead assignments across territories."""
        self._check_permission('assign_leads')
        
        criteria = optimization_criteria or {}
        
        try:
            # Get unassigned leads with geographic data
            unassigned_leads = Lead.objects.filter(
                group=self.group,
                assigned_to__isnull=True,
                headquarters_location__isnull=False,
                geographic_analysis_date__isnull=False
            ).select_related('target_neighborhood')
            
            # Get available team members
            team_members = self._get_available_team_members()
            
            if not team_members:
                return {
                    'message': 'No available team members for assignment',
                    'unassigned_leads': unassigned_leads.count()
                }
            
            # Calculate optimal assignments
            assignments = self._calculate_optimal_assignments(
                unassigned_leads, team_members, criteria
            )
            
            # Generate assignment recommendations
            recommendations = self._generate_assignment_recommendations(assignments)
            
            # Calculate assignment impact
            impact_analysis = self._calculate_assignment_impact(assignments, team_members)
            
            return {
                'unassigned_leads': unassigned_leads.count(),
                'available_team_members': len(team_members),
                'optimization_criteria': criteria,
                'recommended_assignments': recommendations,
                'assignment_impact': impact_analysis,
                'optimization_score': self._calculate_optimization_score(assignments),
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f'Error optimizing lead assignments: {str(e)}')
            raise ValidationError(f'Failed to optimize assignments: {str(e)}')
    
    def execute_assignment_optimization(self, 
                                      assignments: List[Dict[str, Any]],
                                      create_activities: bool = True) -> Dict[str, Any]:
        """Execute the recommended lead assignments."""
        self._check_permission('assign_leads')
        
        try:
            executed_assignments = []
            failed_assignments = []
            
            with transaction.atomic():
                for assignment in assignments:
                    try:
                        lead_id = assignment['lead_id']
                        user_id = assignment['assigned_to_id']
                        reason = assignment.get('reason', 'Territory optimization')
                        
                        # Get lead and user
                        lead = Lead.objects.get(id=lead_id, group=self.group)
                        user = User.objects.get(id=user_id)
                        
                        # Update assignment
                        lead.assigned_to = user
                        lead.save()
                        
                        # Create activity record if requested
                        if create_activities:
                            self._create_assignment_activity(lead, user, reason)
                        
                        executed_assignments.append({
                            'lead_id': lead_id,
                            'company_name': lead.company_name,
                            'assigned_to': user.get_full_name() or user.username,
                            'reason': reason
                        })
                        
                    except Exception as e:
                        failed_assignments.append({
                            'lead_id': assignment.get('lead_id'),
                            'error': str(e)
                        })
                        logger.warning(f"Failed to assign lead {assignment.get('lead_id')}: {str(e)}")
            
            return {
                'total_assignments': len(assignments),
                'successful_assignments': len(executed_assignments),
                'failed_assignments': len(failed_assignments),
                'executed_assignments': executed_assignments,
                'failures': failed_assignments,
                'executed_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f'Error executing assignments: {str(e)}')
            raise ValidationError(f'Failed to execute assignments: {str(e)}')
    
    def get_territory_performance_analysis(self, 
                                         time_period_days: int = 30) -> Dict[str, Any]:
        """Get comprehensive territory performance analysis."""
        self._check_permission('view_analytics')
        
        cutoff_date = timezone.now() - timedelta(days=time_period_days)
        
        try:
            # Get team members with leads
            team_performance = []
            team_members = User.objects.filter(
                groups=self.group,
                assigned_leads__isnull=False
            ).distinct()
            
            for member in team_members:
                member_leads = Lead.objects.filter(
                    group=self.group,
                    assigned_to=member,
                    headquarters_location__isnull=False
                )
                
                recent_activities = LeadActivity.objects.filter(
                    group=self.group,
                    lead__assigned_to=member,
                    created_at__gte=cutoff_date
                )
                
                # Calculate performance metrics
                performance = {
                    'user_id': str(member.id),
                    'name': member.get_full_name() or member.username,
                    'total_leads': member_leads.count(),
                    'geographic_leads': member_leads.filter(geographic_analysis_date__isnull=False).count(),
                    'avg_geographic_score': member_leads.aggregate(
                        avg=Avg('geographic_score')
                    )['avg'] or 0,
                    'avg_lead_score': member_leads.aggregate(
                        avg=Avg('current_score')
                    )['avg'] or 0,
                    'qualified_leads': member_leads.filter(current_score__gte=70).count(),
                    'converted_leads': member_leads.filter(status=Lead.LeadStatus.CONVERTED).count(),
                    'recent_activities': recent_activities.count(),
                    'territory_coverage': self._calculate_member_territory_coverage(member, member_leads),
                    'workload_balance': self._calculate_workload_balance(member, member_leads)
                }
                
                team_performance.append(performance)
            
            # Calculate team averages and rankings
            team_averages = self._calculate_team_averages(team_performance)
            territory_rankings = self._calculate_territory_rankings(team_performance)
            
            return {
                'time_period_days': time_period_days,
                'team_performance': team_performance,
                'team_averages': team_averages,
                'territory_rankings': territory_rankings,
                'recommendations': self._generate_performance_recommendations(team_performance),
                'analysis_date': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f'Error analyzing territory performance: {str(e)}')
            raise ValidationError(f'Failed to analyze performance: {str(e)}')
    
    def get_workload_balancing_recommendations(self) -> Dict[str, Any]:
        """Get recommendations for balancing workload across territories."""
        self._check_permission('view_analytics')
        
        try:
            # Get current workload distribution
            team_members = User.objects.filter(groups=self.group).annotate(
                lead_count=Count('assigned_leads', filter=Q(assigned_leads__group=self.group)),
                avg_score=Avg('assigned_leads__current_score', filter=Q(assigned_leads__group=self.group)),
                geographic_leads=Count('assigned_leads', filter=Q(
                    assigned_leads__group=self.group,
                    assigned_leads__geographic_analysis_date__isnull=False
                ))
            )
            
            # Calculate workload metrics
            workload_analysis = []
            total_leads = 0
            total_members = 0
            
            for member in team_members:
                if member.lead_count > 0:  # Only include members with leads
                    workload_analysis.append({
                        'user_id': str(member.id),
                        'name': member.get_full_name() or member.username,
                        'lead_count': member.lead_count,
                        'avg_score': round(member.avg_score or 0, 1),
                        'geographic_leads': member.geographic_leads,
                        'geographic_coverage': round(
                            (member.geographic_leads / member.lead_count * 100) if member.lead_count > 0 else 0, 1
                        )
                    })
                    total_leads += member.lead_count
                    total_members += 1
            
            if total_members == 0:
                return {
                    'message': 'No team members with assigned leads found',
                    'workload_analysis': []
                }
            
            # Calculate balance metrics
            avg_leads_per_member = total_leads / total_members
            
            # Identify imbalances
            overloaded_members = []
            underloaded_members = []
            
            for member_data in workload_analysis:
                lead_count = member_data['lead_count']
                variance = lead_count - avg_leads_per_member
                variance_percent = (variance / avg_leads_per_member) * 100
                
                member_data['variance_from_average'] = round(variance, 1)
                member_data['variance_percent'] = round(variance_percent, 1)
                
                if variance_percent > 20:  # More than 20% above average
                    overloaded_members.append(member_data)
                elif variance_percent < -20:  # More than 20% below average
                    underloaded_members.append(member_data)
            
            # Generate balancing recommendations
            balancing_recommendations = self._generate_balancing_recommendations(
                overloaded_members, underloaded_members, avg_leads_per_member
            )
            
            return {
                'total_leads': total_leads,
                'total_members': total_members,
                'avg_leads_per_member': round(avg_leads_per_member, 1),
                'workload_analysis': workload_analysis,
                'overloaded_members': overloaded_members,
                'underloaded_members': underloaded_members,
                'balancing_recommendations': balancing_recommendations,
                'balance_score': self._calculate_balance_score(workload_analysis, avg_leads_per_member),
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f'Error analyzing workload balance: {str(e)}')
            raise ValidationError(f'Failed to analyze workload: {str(e)}')
    
    # Private helper methods
    
    def _calculate_territory_coverage(self, leads) -> Dict[str, Any]:
        """Calculate territory coverage metrics."""
        total_leads = leads.count()
        if total_leads == 0:
            return {'message': 'No leads with location data'}
        
        # Geographic spread
        neighborhoods_covered = leads.filter(
            target_neighborhood__isnull=False
        ).values('target_neighborhood').distinct().count()
        
        universities_covered = leads.filter(
            target_universities__isnull=False
        ).values('target_universities').distinct().count()
        
        # Score distribution
        score_distribution = {
            'high_score': leads.filter(geographic_score__gte=80).count(),
            'medium_score': leads.filter(geographic_score__gte=60, geographic_score__lt=80).count(),
            'low_score': leads.filter(geographic_score__lt=60).count()
        }
        
        return {
            'total_leads': total_leads,
            'neighborhoods_covered': neighborhoods_covered,
            'universities_covered': universities_covered,
            'avg_geographic_score': leads.aggregate(avg=Avg('geographic_score'))['avg'] or 0,
            'score_distribution': score_distribution,
            'coverage_density': round(total_leads / max(neighborhoods_covered, 1), 2)
        }
    
    def _analyze_geographic_distribution(self, leads) -> Dict[str, Any]:
        """Analyze geographic distribution of leads."""
        # Distribution by neighborhood
        neighborhood_distribution = leads.filter(
            target_neighborhood__isnull=False
        ).values(
            'target_neighborhood__name'
        ).annotate(
            lead_count=Count('id'),
            avg_score=Avg('geographic_score')
        ).order_by('-lead_count')[:10]
        
        # Distribution by city (from headquarters)
        city_distribution = leads.values(
            'headquarters_city'
        ).annotate(
            lead_count=Count('id'),
            avg_score=Avg('current_score')
        ).order_by('-lead_count')[:10]
        
        return {
            'top_neighborhoods': list(neighborhood_distribution),
            'top_cities': list(city_distribution),
            'geographic_spread': leads.values('headquarters_city').distinct().count()
        }
    
    def _calculate_territory_performance(self, leads) -> Dict[str, Any]:
        """Calculate performance metrics for territory."""
        if not leads.exists():
            return {'message': 'No leads for performance calculation'}
        
        # Conversion metrics
        total_leads = leads.count()
        qualified_leads = leads.filter(current_score__gte=70).count()
        converted_leads = leads.filter(status=Lead.LeadStatus.CONVERTED).count()
        
        # Geographic performance
        geographic_leads = leads.filter(geographic_analysis_date__isnull=False).count()
        
        return {
            'total_leads': total_leads,
            'qualified_leads': qualified_leads,
            'converted_leads': converted_leads,
            'qualification_rate': round((qualified_leads / total_leads * 100) if total_leads > 0 else 0, 1),
            'conversion_rate': round((converted_leads / total_leads * 100) if total_leads > 0 else 0, 1),
            'geographic_coverage': round((geographic_leads / total_leads * 100) if total_leads > 0 else 0, 1),
            'avg_lead_score': round(leads.aggregate(avg=Avg('current_score'))['avg'] or 0, 1),
            'avg_geographic_score': round(leads.aggregate(avg=Avg('geographic_score'))['avg'] or 0, 1)
        }
    
    def _identify_coverage_gaps(self, all_leads, user_leads) -> Dict[str, Any]:
        """Identify coverage gaps in territory."""
        # Neighborhoods with no coverage
        covered_neighborhoods = user_leads.filter(
            target_neighborhood__isnull=False
        ).values_list('target_neighborhood', flat=True)
        
        uncovered_neighborhoods = all_leads.filter(
            target_neighborhood__isnull=False
        ).exclude(
            target_neighborhood__in=covered_neighborhoods
        ).values(
            'target_neighborhood__name',
            'target_neighborhood__id'
        ).annotate(
            lead_count=Count('id'),
            avg_score=Avg('geographic_score')
        ).order_by('-avg_score')[:5]
        
        # High-scoring leads not covered
        high_scoring_uncovered = all_leads.exclude(
            id__in=user_leads.values_list('id', flat=True)
        ).filter(
            geographic_score__gte=80
        ).count()
        
        return {
            'uncovered_neighborhoods': list(uncovered_neighborhoods),
            'high_scoring_uncovered_leads': high_scoring_uncovered,
            'coverage_efficiency': round(
                (user_leads.count() / max(all_leads.count(), 1) * 100), 1
            )
        }
    
    def _get_available_team_members(self) -> List[User]:
        """Get available team members for lead assignment."""
        return User.objects.filter(
            groups=self.group,
            is_active=True
        ).annotate(
            current_lead_count=Count('assigned_leads', filter=Q(assigned_leads__group=self.group))
        ).order_by('current_lead_count')
    
    def _calculate_optimal_assignments(self, leads, team_members, criteria) -> List[Dict[str, Any]]:
        """Calculate optimal lead assignments."""
        assignments = []
        
        for lead in leads:
            best_match = self._find_best_team_member_match(lead, team_members, criteria)
            if best_match:
                assignments.append({
                    'lead_id': str(lead.id),
                    'company_name': lead.company_name,
                    'assigned_to_id': str(best_match['user'].id),
                    'assigned_to_name': best_match['user'].get_full_name() or best_match['user'].username,
                    'match_score': best_match['score'],
                    'reason': best_match['reason']
                })
        
        return assignments
    
    def _find_best_team_member_match(self, lead, team_members, criteria) -> Optional[Dict[str, Any]]:
        """Find the best team member match for a lead."""
        best_match = None
        best_score = 0
        
        for member in team_members:
            # Calculate match score
            match_score = 0
            reasons = []
            
            # Geographic proximity (if lead has location)
            if lead.headquarters_location and hasattr(member, 'geographic_focus'):
                # This would calculate geographic proximity
                match_score += 20
                reasons.append("Geographic proximity")
            
            # Workload balance
            current_leads = getattr(member, 'current_lead_count', 0)
            if current_leads < 10:  # Arbitrary threshold
                match_score += 30
                reasons.append("Balanced workload")
            
            # Experience/expertise (placeholder)
            match_score += 25
            reasons.append("Team member availability")
            
            # Lead complexity matching
            if lead.current_score >= 80:  # High-value lead
                match_score += 25
                reasons.append("High-value lead match")
            
            if match_score > best_score:
                best_score = match_score
                best_match = {
                    'user': member,
                    'score': match_score,
                    'reason': '; '.join(reasons)
                }
        
        return best_match
    
    def _generate_assignment_recommendations(self, assignments) -> List[Dict[str, Any]]:
        """Generate assignment recommendations with reasoning."""
        recommendations = []
        
        # Group by assigned user
        user_assignments = {}
        for assignment in assignments:
            user_id = assignment['assigned_to_id']
            if user_id not in user_assignments:
                user_assignments[user_id] = []
            user_assignments[user_id].append(assignment)
        
        for user_id, user_assignments_list in user_assignments.items():
            recommendations.append({
                'assigned_to_id': user_id,
                'assigned_to_name': user_assignments_list[0]['assigned_to_name'],
                'lead_count': len(user_assignments_list),
                'assignments': user_assignments_list,
                'avg_match_score': sum(a['match_score'] for a in user_assignments_list) / len(user_assignments_list),
                'recommendation': f"Assign {len(user_assignments_list)} leads with average match score of {sum(a['match_score'] for a in user_assignments_list) / len(user_assignments_list):.1f}"
            })
        
        return recommendations
    
    def _calculate_assignment_impact(self, assignments, team_members) -> Dict[str, Any]:
        """Calculate the impact of proposed assignments."""
        if not assignments:
            return {'message': 'No assignments to analyze'}
        
        # Calculate workload distribution after assignments
        workload_after = {}
        for member in team_members:
            workload_after[str(member.id)] = getattr(member, 'current_lead_count', 0)
        
        for assignment in assignments:
            user_id = assignment['assigned_to_id']
            workload_after[user_id] = workload_after.get(user_id, 0) + 1
        
        # Calculate balance metrics
        workloads = list(workload_after.values())
        avg_workload = sum(workloads) / len(workloads) if workloads else 0
        workload_variance = sum((w - avg_workload) ** 2 for w in workloads) / len(workloads) if workloads else 0
        
        return {
            'total_assignments': len(assignments),
            'affected_team_members': len(set(a['assigned_to_id'] for a in assignments)),
            'workload_distribution': workload_after,
            'avg_workload_after': round(avg_workload, 1),
            'workload_variance': round(workload_variance, 2),
            'balance_improvement': self._calculate_balance_improvement(team_members, workload_after)
        }
    
    def _calculate_optimization_score(self, assignments) -> float:
        """Calculate overall optimization score for assignments."""
        if not assignments:
            return 0.0
        
        total_score = sum(assignment['match_score'] for assignment in assignments)
        avg_score = total_score / len(assignments)
        return round(avg_score, 1)
    
    def _create_assignment_activity(self, lead: Lead, user: User, reason: str):
        """Create activity record for assignment."""
        try:
            LeadActivity.objects.create(
                group=self.group,
                lead=lead,
                activity_type=LeadActivity.ActivityType.ASSIGNMENT,
                title=f"Lead assigned to {user.get_full_name() or user.username}",
                description=f"Automated assignment: {reason}",
                performed_by=self.user,
                is_automated=True,
                activity_data={
                    'assigned_to_id': str(user.id),
                    'assigned_to_name': user.get_full_name() or user.username,
                    'assignment_reason': reason,
                    'assignment_method': 'Territory optimization'
                }
            )
        except Exception as e:
            logger.warning(f"Failed to create assignment activity: {str(e)}")
    
    def _calculate_member_territory_coverage(self, member: User, member_leads) -> Dict[str, Any]:
        """Calculate territory coverage for a specific member."""
        if not member_leads.exists():
            return {'neighborhoods': 0, 'geographic_spread': 0}
        
        neighborhoods = member_leads.filter(
            target_neighborhood__isnull=False
        ).values('target_neighborhood').distinct().count()
        
        cities = member_leads.values('headquarters_city').distinct().count()
        
        return {
            'neighborhoods': neighborhoods,
            'cities': cities,
            'geographic_spread': round(neighborhoods / max(member_leads.count(), 1) * 100, 1)
        }
    
    def _calculate_workload_balance(self, member: User, member_leads) -> Dict[str, Any]:
        """Calculate workload balance metrics for a member."""
        lead_count = member_leads.count()
        high_priority = member_leads.filter(current_score__gte=85).count()
        
        return {
            'total_leads': lead_count,
            'high_priority_leads': high_priority,
            'workload_intensity': round((high_priority / max(lead_count, 1)) * 100, 1)
        }
    
    def _calculate_team_averages(self, team_performance) -> Dict[str, float]:
        """Calculate team average metrics."""
        if not team_performance:
            return {}
        
        team_size = len(team_performance)
        return {
            'avg_leads_per_member': round(sum(p['total_leads'] for p in team_performance) / team_size, 1),
            'avg_geographic_score': round(sum(p['avg_geographic_score'] for p in team_performance) / team_size, 1),
            'avg_lead_score': round(sum(p['avg_lead_score'] for p in team_performance) / team_size, 1),
            'avg_qualified_leads': round(sum(p['qualified_leads'] for p in team_performance) / team_size, 1),
            'avg_conversion_rate': round(sum(p['converted_leads'] for p in team_performance) / team_size, 1)
        }
    
    def _calculate_territory_rankings(self, team_performance) -> Dict[str, List[Dict]]:
        """Calculate territory rankings by different metrics."""
        rankings = {
            'by_lead_count': sorted(team_performance, key=lambda x: x['total_leads'], reverse=True),
            'by_geographic_score': sorted(team_performance, key=lambda x: x['avg_geographic_score'], reverse=True),
            'by_conversion': sorted(team_performance, key=lambda x: x['converted_leads'], reverse=True),
            'by_activity': sorted(team_performance, key=lambda x: x['recent_activities'], reverse=True)
        }
        
        # Add rank numbers
        for ranking_type, ranking_list in rankings.items():
            for i, member in enumerate(ranking_list):
                member[f'rank_{ranking_type}'] = i + 1
        
        return rankings
    
    def _generate_performance_recommendations(self, team_performance) -> List[str]:
        """Generate performance improvement recommendations."""
        recommendations = []
        
        if not team_performance:
            return ["No team performance data available"]
        
        # Low geographic coverage
        low_geo_members = [p for p in team_performance if p['geographic_leads'] / max(p['total_leads'], 1) < 0.5]
        if low_geo_members:
            recommendations.append(f"{len(low_geo_members)} team members need improved geographic analysis coverage")
        
        # Workload imbalance
        lead_counts = [p['total_leads'] for p in team_performance]
        if max(lead_counts) - min(lead_counts) > 5:
            recommendations.append("Consider rebalancing lead distribution across team members")
        
        # Low activity
        low_activity = [p for p in team_performance if p['recent_activities'] == 0]
        if low_activity:
            recommendations.append(f"{len(low_activity)} team members need increased activity engagement")
        
        return recommendations
    
    def _generate_balancing_recommendations(self, overloaded, underloaded, avg_leads) -> List[Dict[str, Any]]:
        """Generate workload balancing recommendations."""
        recommendations = []
        
        for overloaded_member in overloaded:
            excess_leads = overloaded_member['lead_count'] - avg_leads
            recommendations.append({
                'type': 'redistribute_from',
                'member_id': overloaded_member['user_id'],
                'member_name': overloaded_member['name'],
                'current_leads': overloaded_member['lead_count'],
                'suggested_leads': int(avg_leads),
                'leads_to_redistribute': int(excess_leads),
                'reason': f"Reduce workload by {int(excess_leads)} leads to achieve balance"
            })
        
        for underloaded_member in underloaded:
            deficit_leads = avg_leads - underloaded_member['lead_count']
            recommendations.append({
                'type': 'redistribute_to',
                'member_id': underloaded_member['user_id'],
                'member_name': underloaded_member['name'],
                'current_leads': underloaded_member['lead_count'],
                'suggested_leads': int(avg_leads),
                'leads_to_receive': int(deficit_leads),
                'reason': f"Increase workload by {int(deficit_leads)} leads to achieve balance"
            })
        
        return recommendations
    
    def _calculate_balance_score(self, workload_analysis, avg_leads) -> float:
        """Calculate workload balance score (0-100)."""
        if not workload_analysis:
            return 0.0
        
        # Calculate variance from average
        variances = [abs(member['lead_count'] - avg_leads) for member in workload_analysis]
        avg_variance = sum(variances) / len(variances)
        
        # Convert to balance score (lower variance = higher score)
        balance_score = max(0, 100 - (avg_variance * 10))  # Arbitrary scaling
        return round(balance_score, 1)
    
    def _calculate_balance_improvement(self, team_members, workload_after) -> str:
        """Calculate balance improvement description."""
        # Current workload variance
        current_workloads = [getattr(member, 'current_lead_count', 0) for member in team_members]
        current_avg = sum(current_workloads) / len(current_workloads) if current_workloads else 0
        current_variance = sum((w - current_avg) ** 2 for w in current_workloads) / len(current_workloads) if current_workloads else 0
        
        # Future workload variance
        future_workloads = list(workload_after.values())
        future_avg = sum(future_workloads) / len(future_workloads) if future_workloads else 0
        future_variance = sum((w - future_avg) ** 2 for w in future_workloads) / len(future_workloads) if future_workloads else 0
        
        if future_variance < current_variance:
            improvement = ((current_variance - future_variance) / current_variance) * 100
            return f"Improves workload balance by {improvement:.1f}%"
        else:
            return "No significant balance improvement"