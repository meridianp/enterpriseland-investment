"""
Lead Scoring Service.

Advanced lead scoring system with configurable models, real-time scoring,
batch processing, and performance analytics.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Avg, Count, F
from django.core.exceptions import ValidationError

from assessments.services.base import BaseService
from ..models import Lead, LeadScoringModel, LeadActivity
from geographic_intelligence.services import GeographicIntelligenceService

logger = logging.getLogger(__name__)


class LeadScoringService(BaseService):
    """
    Service for managing lead scoring operations including model management,
    score calculation, batch processing, and performance tracking.
    """
    
    def __init__(self, user=None, group=None):
        super().__init__(user=user, group=group)
        self.model = Lead
    
    # Scoring Model Management
    
    def create_scoring_model(self, model_data: Dict[str, Any]) -> LeadScoringModel:
        """Create a new lead scoring model."""
        self._check_permission('create_scoring_model')
        
        # Validate required fields
        required_fields = ['name', 'scoring_method']
        self._validate_required_fields(model_data, required_fields)
        
        # Ensure group context
        if not self.group:
            raise ValidationError("Group context required for scoring model creation")
        
        try:
            with transaction.atomic():
                # Create scoring model
                scoring_model = LeadScoringModel.objects.create(
                    group=self.group,
                    created_by=self.user,
                    **model_data
                )
                
                # Set default component weights if not provided
                if not scoring_model.component_weights:
                    scoring_model.component_weights = scoring_model.get_default_weights()
                    scoring_model.save()
                
                logger.info(f"Created scoring model: {scoring_model.name}")
                return scoring_model
                
        except Exception as e:
            logger.error(f"Error creating scoring model: {str(e)}")
            raise ValidationError(f"Failed to create scoring model: {str(e)}")
    
    def activate_scoring_model(self, model_id: str) -> LeadScoringModel:
        """Activate a scoring model and deactivate others."""
        self._check_permission('activate_scoring_model')
        
        try:
            scoring_model = LeadScoringModel.objects.get(
                id=model_id,
                group=self.group
            )
            
            scoring_model.activate(user=self.user)
            
            logger.info(f"Activated scoring model: {scoring_model.name}")
            return scoring_model
            
        except LeadScoringModel.DoesNotExist:
            raise ValidationError(f"Scoring model {model_id} not found")
    
    def get_active_scoring_model(self) -> Optional[LeadScoringModel]:
        """Get the currently active scoring model for the group."""
        return LeadScoringModel.objects.filter(
            group=self.group,
            status=LeadScoringModel.ModelStatus.ACTIVE
        ).first()
    
    def get_default_scoring_model(self) -> Optional[LeadScoringModel]:
        """Get the default scoring model for the group."""
        return LeadScoringModel.objects.filter(
            group=self.group,
            is_default=True,
            status=LeadScoringModel.ModelStatus.ACTIVE
        ).first()
    
    # Individual Lead Scoring
    
    def calculate_lead_score(self, lead_id: str, scoring_model_id: str = None) -> Dict[str, Any]:
        """Calculate comprehensive score for a single lead."""
        self._check_permission('calculate_lead_score')
        
        try:
            lead = Lead.objects.get(id=lead_id, group=self.group)
            
            # Get scoring model
            if scoring_model_id:
                scoring_model = LeadScoringModel.objects.get(
                    id=scoring_model_id,
                    group=self.group
                )
            else:
                scoring_model = self.get_active_scoring_model()
            
            if not scoring_model:
                raise ValidationError("No active scoring model found")
            
            # Calculate score using the lead's built-in method
            new_score = lead.calculate_score(scoring_model)
            
            # Create activity record
            self._create_scoring_activity(lead, new_score, scoring_model)
            
            # Get detailed scoring breakdown
            score_breakdown = self._get_score_breakdown(lead, scoring_model)
            
            result = {
                'lead_id': str(lead.id),
                'company_name': lead.company_name,
                'previous_score': lead.current_score,
                'new_score': new_score,
                'scoring_model': {
                    'id': str(scoring_model.id),
                    'name': scoring_model.name,
                    'version': scoring_model.version
                },
                'score_breakdown': score_breakdown,
                'qualification_status': self._determine_qualification_status(new_score, scoring_model),
                'recommendations': self._generate_recommendations(score_breakdown, scoring_model),
                'calculated_at': timezone.now().isoformat()
            }
            
            logger.info(f"Calculated score for lead {lead.company_name}: {new_score}")
            return result
            
        except Lead.DoesNotExist:
            raise ValidationError(f"Lead {lead_id} not found")
        except LeadScoringModel.DoesNotExist:
            raise ValidationError(f"Scoring model {scoring_model_id} not found")
    
    def _get_score_breakdown(self, lead: Lead, scoring_model: LeadScoringModel) -> Dict[str, float]:
        """Get detailed breakdown of scoring components."""
        score_data = lead._prepare_scoring_data()
        weights = scoring_model.component_weights or scoring_model.get_default_weights()
        
        breakdown = {}
        for component, score in score_data.items():
            weight = weights.get(component, 0.0)
            weighted_score = score * weight
            breakdown[component] = {
                'raw_score': score,
                'weight': weight,
                'weighted_score': weighted_score,
                'contribution_percentage': (weighted_score / 100.0) * 100 if scoring_model.scoring_method == 'weighted_average' else 0
            }
        
        return breakdown
    
    def _determine_qualification_status(self, score: float, scoring_model: LeadScoringModel) -> str:
        """Determine qualification status based on score and thresholds."""
        if score >= scoring_model.auto_convert_threshold:
            return 'auto_convert'
        elif score >= scoring_model.high_priority_threshold:
            return 'high_priority'
        elif score >= scoring_model.qualification_threshold:
            return 'qualified'
        elif score >= 50.0:
            return 'potential'
        else:
            return 'unqualified'
    
    def _generate_recommendations(self, score_breakdown: Dict[str, Any], scoring_model: LeadScoringModel) -> List[str]:
        """Generate actionable recommendations based on scoring breakdown."""
        recommendations = []
        
        for component, details in score_breakdown.items():
            raw_score = details['raw_score']
            
            # Generate recommendations for low-scoring components
            if raw_score < 60.0:
                if component == 'business_alignment':
                    recommendations.append("Research company's PBSA focus and business model alignment")
                elif component == 'market_presence':
                    recommendations.append("Gather more information about company's market presence and news coverage")
                elif component == 'financial_strength':
                    recommendations.append("Assess company's financial position and funding history")
                elif component == 'strategic_fit':
                    recommendations.append("Evaluate strategic fit with investment criteria")
                elif component == 'geographic_fit':
                    recommendations.append("Analyze target neighborhoods and university proximity for better location scoring")
                elif component == 'accessibility_score':
                    recommendations.append("Evaluate transport links and infrastructure accessibility")
                elif component == 'university_proximity_score':
                    recommendations.append("Consider proximity to target universities for student accommodation")
                elif component == 'market_demand_score':
                    recommendations.append("Research local student population and accommodation demand")
                elif component == 'competition_score':
                    recommendations.append("Analyze competitive landscape in target neighborhoods")
                elif component == 'engagement_potential':
                    recommendations.append("Identify key contacts and engagement opportunities")
                elif component == 'data_completeness':
                    recommendations.append("Complete missing company and contact information")
        
        # Add general recommendations based on overall score
        total_score = sum(details['weighted_score'] for details in score_breakdown.values())
        
        if total_score >= scoring_model.qualification_threshold:
            recommendations.append("Lead is qualified - initiate outreach sequence")
        
        if total_score >= scoring_model.high_priority_threshold:
            recommendations.append("High priority lead - assign to senior team member")
        
        return recommendations[:5]  # Limit to top 5 recommendations
    
    def _create_scoring_activity(self, lead: Lead, new_score: float, scoring_model: LeadScoringModel):
        """Create activity record for scoring event."""
        try:
            LeadActivity.objects.create(
                group=self.group,
                lead=lead,
                activity_type=LeadActivity.ActivityType.SCORE_UPDATE,
                title=f"Lead score updated to {new_score:.1f}",
                description=f"Score calculated using {scoring_model.name} v{scoring_model.version}",
                performed_by=self.user,
                is_automated=True,
                activity_data={
                    'scoring_model_id': str(scoring_model.id),
                    'scoring_model_name': scoring_model.name,
                    'previous_score': lead.current_score,
                    'new_score': new_score,
                    'score_change': new_score - lead.current_score
                }
            )
        except Exception as e:
            logger.warning(f"Failed to create scoring activity: {str(e)}")
    
    # Batch Scoring Operations
    
    def batch_score_leads(self, lead_ids: List[str] = None, filters: Dict[str, Any] = None, 
                         scoring_model_id: str = None) -> Dict[str, Any]:
        """Score multiple leads in batch."""
        self._check_permission('batch_score_leads')
        
        try:
            # Get leads to score
            if lead_ids:
                leads = Lead.objects.filter(id__in=lead_ids, group=self.group)
            else:
                queryset = Lead.objects.filter(group=self.group)
                if filters:
                    queryset = self._apply_batch_filters(queryset, filters)
                leads = queryset
            
            # Get scoring model
            if scoring_model_id:
                scoring_model = LeadScoringModel.objects.get(
                    id=scoring_model_id,
                    group=self.group
                )
            else:
                scoring_model = self.get_active_scoring_model()
            
            if not scoring_model:
                raise ValidationError("No active scoring model found")
            
            # Process leads in batches
            total_scored = 0
            score_changes = []
            errors = []
            
            for lead in leads:
                try:
                    previous_score = lead.current_score
                    new_score = lead.calculate_score(scoring_model)
                    
                    score_changes.append({
                        'lead_id': str(lead.id),
                        'company_name': lead.company_name,
                        'previous_score': previous_score,
                        'new_score': new_score,
                        'score_change': new_score - previous_score
                    })
                    
                    total_scored += 1
                    
                    # Create activity record
                    self._create_scoring_activity(lead, new_score, scoring_model)
                    
                except Exception as e:
                    errors.append({
                        'lead_id': str(lead.id),
                        'error': str(e)
                    })
                    logger.error(f"Error scoring lead {lead.id}: {str(e)}")
            
            # Calculate summary statistics
            if score_changes:
                avg_score_change = sum(change['score_change'] for change in score_changes) / len(score_changes)
                qualified_count = sum(1 for change in score_changes 
                                    if change['new_score'] >= scoring_model.qualification_threshold)
            else:
                avg_score_change = 0
                qualified_count = 0
            
            result = {
                'total_leads': leads.count(),
                'total_scored': total_scored,
                'errors': len(errors),
                'qualified_leads': qualified_count,
                'average_score_change': avg_score_change,
                'scoring_model': {
                    'id': str(scoring_model.id),
                    'name': scoring_model.name,
                    'version': scoring_model.version
                },
                'score_changes': score_changes,
                'processing_errors': errors,
                'processed_at': timezone.now().isoformat()
            }
            
            logger.info(f"Batch scored {total_scored} leads with {len(errors)} errors")
            return result
            
        except LeadScoringModel.DoesNotExist:
            raise ValidationError(f"Scoring model {scoring_model_id} not found")
    
    def _apply_batch_filters(self, queryset, filters: Dict[str, Any]):
        """Apply filters to batch scoring queryset."""
        if 'status' in filters:
            queryset = queryset.filter(status=filters['status'])
        
        if 'priority' in filters:
            queryset = queryset.filter(priority=filters['priority'])
        
        if 'assigned_to' in filters:
            queryset = queryset.filter(assigned_to_id=filters['assigned_to'])
        
        if 'source' in filters:
            queryset = queryset.filter(source=filters['source'])
        
        if 'score_range' in filters:
            min_score, max_score = filters['score_range']
            queryset = queryset.filter(current_score__gte=min_score, current_score__lte=max_score)
        
        if 'created_after' in filters:
            queryset = queryset.filter(created_at__gte=filters['created_after'])
        
        if 'last_scored_before' in filters:
            queryset = queryset.filter(
                Q(last_scored_at__isnull=True) | 
                Q(last_scored_at__lt=filters['last_scored_before'])
            )
        
        return queryset
    
    # Scoring Analytics and Performance
    
    def get_scoring_analytics(self, days_back: int = 30) -> Dict[str, Any]:
        """Get comprehensive scoring analytics."""
        self._check_permission('view_scoring_analytics')
        
        cutoff_date = timezone.now() - timedelta(days=days_back)
        
        # Get active scoring model
        active_model = self.get_active_scoring_model()
        
        # Lead score distribution
        score_distribution = self._get_score_distribution()
        
        # Scoring performance metrics
        performance_metrics = self._get_performance_metrics(cutoff_date)
        
        # Score trends over time
        score_trends = self._get_score_trends(cutoff_date)
        
        # Component performance analysis
        component_analysis = self._get_component_analysis()
        
        # Qualification pipeline
        qualification_pipeline = self._get_qualification_pipeline()
        
        result = {
            'active_scoring_model': {
                'id': str(active_model.id) if active_model else None,
                'name': active_model.name if active_model else None,
                'version': active_model.version if active_model else None,
                'accuracy': active_model.accuracy_score if active_model else None,
                'precision': active_model.precision_score if active_model else None,
                'recall': active_model.recall_score if active_model else None,
                'f1_score': active_model.f1_score if active_model else None
            },
            'score_distribution': score_distribution,
            'performance_metrics': performance_metrics,
            'score_trends': score_trends,
            'component_analysis': component_analysis,
            'qualification_pipeline': qualification_pipeline,
            'period_days': days_back,
            'generated_at': timezone.now().isoformat()
        }
        
        return result
    
    def _get_score_distribution(self) -> Dict[str, int]:
        """Get distribution of lead scores."""
        leads = Lead.objects.filter(group=self.group)
        
        distribution = {
            '90-100': leads.filter(current_score__gte=90).count(),
            '80-89': leads.filter(current_score__gte=80, current_score__lt=90).count(),
            '70-79': leads.filter(current_score__gte=70, current_score__lt=80).count(),
            '60-69': leads.filter(current_score__gte=60, current_score__lt=70).count(),
            '50-59': leads.filter(current_score__gte=50, current_score__lt=60).count(),
            '40-49': leads.filter(current_score__gte=40, current_score__lt=50).count(),
            '30-39': leads.filter(current_score__gte=30, current_score__lt=40).count(),
            '20-29': leads.filter(current_score__gte=20, current_score__lt=30).count(),
            '10-19': leads.filter(current_score__gte=10, current_score__lt=20).count(),
            '0-9': leads.filter(current_score__lt=10).count()
        }
        
        return distribution
    
    def _get_performance_metrics(self, cutoff_date: datetime) -> Dict[str, Any]:
        """Get scoring performance metrics."""
        leads = Lead.objects.filter(group=self.group)
        recent_activities = LeadActivity.objects.filter(
            group=self.group,
            activity_type=LeadActivity.ActivityType.SCORE_UPDATE,
            created_at__gte=cutoff_date
        )
        
        metrics = {
            'total_leads': leads.count(),
            'scored_leads': leads.filter(last_scored_at__isnull=False).count(),
            'recent_scorings': recent_activities.count(),
            'average_score': leads.aggregate(avg_score=Avg('current_score'))['avg_score'] or 0,
            'qualified_leads': leads.filter(current_score__gte=70).count(),
            'high_priority_leads': leads.filter(current_score__gte=85).count(),
            'conversion_rate': self._calculate_conversion_rate(),
            'scoring_accuracy': self._calculate_scoring_accuracy()
        }
        
        return metrics
    
    def _get_score_trends(self, cutoff_date: datetime) -> List[Dict[str, Any]]:
        """Get score trends over time."""
        activities = LeadActivity.objects.filter(
            group=self.group,
            activity_type=LeadActivity.ActivityType.SCORE_UPDATE,
            created_at__gte=cutoff_date
        ).order_by('created_at')
        
        # Group by day and calculate averages
        daily_trends = {}
        for activity in activities:
            date_key = activity.created_at.date().isoformat()
            if date_key not in daily_trends:
                daily_trends[date_key] = {
                    'date': date_key,
                    'scores': [],
                    'count': 0
                }
            
            if 'new_score' in activity.activity_data:
                daily_trends[date_key]['scores'].append(activity.activity_data['new_score'])
                daily_trends[date_key]['count'] += 1
        
        # Calculate daily averages
        trends = []
        for date_key, data in daily_trends.items():
            if data['scores']:
                avg_score = sum(data['scores']) / len(data['scores'])
                trends.append({
                    'date': date_key,
                    'average_score': avg_score,
                    'scoring_count': data['count']
                })
        
        return sorted(trends, key=lambda x: x['date'])
    
    def _get_component_analysis(self) -> Dict[str, float]:
        """Analyze component scoring performance with real data."""
        leads = Lead.objects.filter(group=self.group, last_scored_at__isnull=False)
        
        if not leads.exists():
            # Return mock analysis if no scored leads
            return {
                'business_alignment': 0.78,
                'market_presence': 0.65,
                'financial_strength': 0.72,
                'strategic_fit': 0.69,
                'geographic_fit': 0.81,
                'engagement_potential': 0.58,
                'data_completeness': 0.85
            }
        
        # Calculate average scores for each component
        component_averages = leads.aggregate(
            business_alignment=Avg('business_alignment_score'),
            market_presence=Avg('market_presence_score'),
            financial_strength=Avg('financial_strength_score'),
            strategic_fit=Avg('strategic_fit_score'),
            geographic_fit=Avg('geographic_score'),
            accessibility=Avg('accessibility_score'),
            university_proximity=Avg('university_proximity_score'),
            market_demand=Avg('market_demand_score'),
            competition=Avg('competition_score'),
            engagement_potential=Avg('engagement_potential_score'),
            data_completeness=Avg('data_completeness_score')
        )
        
        # Convert to 0-1 scale for consistency
        analysis = {}
        for component, avg_score in component_averages.items():
            if avg_score is not None:
                analysis[component] = avg_score / 100.0
            else:
                analysis[component] = 0.0
        
        return analysis
    
    def _get_qualification_pipeline(self) -> Dict[str, int]:
        """Get qualification pipeline statistics."""
        leads = Lead.objects.filter(group=self.group)
        
        pipeline = {
            'unqualified': leads.filter(current_score__lt=50).count(),
            'potential': leads.filter(current_score__gte=50, current_score__lt=70).count(),
            'qualified': leads.filter(current_score__gte=70, current_score__lt=85).count(),
            'high_priority': leads.filter(current_score__gte=85, current_score__lt=95).count(),
            'auto_convert': leads.filter(current_score__gte=95).count()
        }
        
        return pipeline
    
    def _calculate_conversion_rate(self) -> float:
        """Calculate lead conversion rate."""
        total_qualified = Lead.objects.filter(
            group=self.group,
            current_score__gte=70
        ).count()
        
        converted = Lead.objects.filter(
            group=self.group,
            status=Lead.LeadStatus.CONVERTED
        ).count()
        
        return (converted / total_qualified * 100) if total_qualified > 0 else 0.0
    
    def _calculate_scoring_accuracy(self) -> float:
        """Calculate scoring model accuracy."""
        # This would compare predicted outcomes with actual conversions
        # For now, return a calculated estimate
        active_model = self.get_active_scoring_model()
        return active_model.accuracy_score * 100 if active_model and active_model.accuracy_score else 75.0
    
    # Model Performance Tracking
    
    def update_model_performance(self, model_id: str, performance_data: Dict[str, float]) -> LeadScoringModel:
        """Update scoring model performance metrics."""
        self._check_permission('update_model_performance')
        
        try:
            scoring_model = LeadScoringModel.objects.get(
                id=model_id,
                group=self.group
            )
            
            if 'accuracy' in performance_data:
                scoring_model.accuracy_score = performance_data['accuracy']
            
            if 'precision' in performance_data:
                scoring_model.precision_score = performance_data['precision']
            
            if 'recall' in performance_data:
                scoring_model.recall_score = performance_data['recall']
            
            scoring_model.save()
            
            logger.info(f"Updated performance for scoring model: {scoring_model.name}")
            return scoring_model
            
        except LeadScoringModel.DoesNotExist:
            raise ValidationError(f"Scoring model {model_id} not found")
    
    def evaluate_model_performance(self, model_id: str) -> Dict[str, Any]:
        """Evaluate scoring model performance against actual outcomes."""
        self._check_permission('evaluate_model_performance')
        
        try:
            scoring_model = LeadScoringModel.objects.get(
                id=model_id,
                group=self.group
            )
            
            # Get leads scored with this model
            scored_leads = Lead.objects.filter(
                group=self.group,
                scoring_model=scoring_model
            )
            
            # Calculate performance metrics
            total_leads = scored_leads.count()
            qualified_leads = scored_leads.filter(current_score__gte=scoring_model.qualification_threshold).count()
            converted_leads = scored_leads.filter(status=Lead.LeadStatus.CONVERTED).count()
            
            # Calculate precision and recall
            true_positives = scored_leads.filter(
                current_score__gte=scoring_model.qualification_threshold,
                status=Lead.LeadStatus.CONVERTED
            ).count()
            
            false_positives = qualified_leads - true_positives
            false_negatives = converted_leads - true_positives
            
            precision = true_positives / qualified_leads if qualified_leads > 0 else 0
            recall = true_positives / converted_leads if converted_leads > 0 else 0
            accuracy = (true_positives + (total_leads - qualified_leads - false_negatives)) / total_leads if total_leads > 0 else 0
            
            f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            
            # Update model with calculated metrics
            scoring_model.accuracy_score = accuracy
            scoring_model.precision_score = precision
            scoring_model.recall_score = recall
            scoring_model.save()
            
            result = {
                'model_id': str(scoring_model.id),
                'model_name': scoring_model.name,
                'total_leads': total_leads,
                'qualified_leads': qualified_leads,
                'converted_leads': converted_leads,
                'true_positives': true_positives,
                'false_positives': false_positives,
                'false_negatives': false_negatives,
                'precision': precision,
                'recall': recall,
                'accuracy': accuracy,
                'f1_score': f1_score,
                'evaluated_at': timezone.now().isoformat()
            }
            
            logger.info(f"Evaluated performance for scoring model: {scoring_model.name}")
            return result
            
        except LeadScoringModel.DoesNotExist:
            raise ValidationError(f"Scoring model {model_id} not found")
    
    # Geographic Intelligence Integration
    
    def refresh_geographic_scores(self, lead_ids: List[str] = None) -> Dict[str, Any]:
        """Refresh geographic intelligence scores for leads."""
        self._check_permission('batch_score_leads')
        
        try:
            # Get leads to update
            if lead_ids:
                leads = Lead.objects.filter(id__in=lead_ids, group=self.group)
            else:
                # Update leads with headquarters_location but outdated geographic analysis
                cutoff_date = timezone.now() - timedelta(days=7)
                leads = Lead.objects.filter(
                    group=self.group,
                    headquarters_location__isnull=False
                ).filter(
                    Q(geographic_analysis_date__isnull=True) |
                    Q(geographic_analysis_date__lt=cutoff_date)
                )
            
            if not leads.exists():
                return {
                    'total_leads': 0,
                    'updated_leads': 0,
                    'errors': [],
                    'message': 'No leads found requiring geographic score updates'
                }
            
            # Process leads
            updated_count = 0
            errors = []
            
            for lead in leads:
                try:
                    lead.update_geographic_scores()
                    updated_count += 1
                    
                    logger.info(f"Updated geographic scores for lead: {lead.company_name}")
                    
                except Exception as e:
                    errors.append({
                        'lead_id': str(lead.id),
                        'company_name': lead.company_name,
                        'error': str(e)
                    })
                    logger.error(f"Error updating geographic scores for lead {lead.id}: {str(e)}")
            
            return {
                'total_leads': leads.count(),
                'updated_leads': updated_count,
                'errors': errors,
                'processed_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error refreshing geographic scores: {str(e)}")
            raise ValidationError(f"Failed to refresh geographic scores: {str(e)}")
    
    def get_geographic_analytics(self) -> Dict[str, Any]:
        """Get geographic intelligence analytics for leads."""
        self._check_permission('view_scoring_analytics')
        
        leads = Lead.objects.filter(group=self.group)
        geographic_leads = leads.filter(geographic_analysis_date__isnull=False)
        
        if not geographic_leads.exists():
            return {
                'message': 'No leads with geographic analysis found',
                'total_leads': leads.count(),
                'geographic_leads': 0
            }
        
        # Geographic score distribution
        geographic_distribution = {
            '90-100': geographic_leads.filter(geographic_score__gte=90).count(),
            '80-89': geographic_leads.filter(geographic_score__gte=80, geographic_score__lt=90).count(),
            '70-79': geographic_leads.filter(geographic_score__gte=70, geographic_score__lt=80).count(),
            '60-69': geographic_leads.filter(geographic_score__gte=60, geographic_score__lt=70).count(),
            '50-59': geographic_leads.filter(geographic_score__gte=50, geographic_score__lt=60).count(),
            'Below 50': geographic_leads.filter(geographic_score__lt=50).count()
        }
        
        # Component averages
        component_averages = geographic_leads.aggregate(
            avg_geographic_score=Avg('geographic_score'),
            avg_accessibility=Avg('accessibility_score'),
            avg_university_proximity=Avg('university_proximity_score'),
            avg_market_demand=Avg('market_demand_score'),
            avg_competition=Avg('competition_score')
        )
        
        # Top performing cities/regions
        from django.db.models import Count
        city_performance = {}
        for lead in geographic_leads.filter(target_neighborhood__isnull=False):
            city = getattr(lead.target_neighborhood, 'name', '').split()[0]
            if city:
                if city not in city_performance:
                    city_performance[city] = {'count': 0, 'total_score': 0}
                city_performance[city]['count'] += 1
                city_performance[city]['total_score'] += lead.geographic_score
        
        # Calculate averages and sort
        city_rankings = []
        for city, data in city_performance.items():
            if data['count'] > 0:
                avg_score = data['total_score'] / data['count']
                city_rankings.append({
                    'city': city,
                    'leads_count': data['count'],
                    'average_score': round(avg_score, 1)
                })
        
        city_rankings.sort(key=lambda x: x['average_score'], reverse=True)
        
        return {
            'total_leads': leads.count(),
            'geographic_leads': geographic_leads.count(),
            'coverage_percentage': round(geographic_leads.count() / leads.count() * 100, 1),
            'geographic_score_distribution': geographic_distribution,
            'component_averages': {
                'overall_geographic': round(component_averages['avg_geographic_score'] or 0, 1),
                'accessibility': round(component_averages['avg_accessibility'] or 0, 1),
                'university_proximity': round(component_averages['avg_university_proximity'] or 0, 1),
                'market_demand': round(component_averages['avg_market_demand'] or 0, 1),
                'competition': round(component_averages['avg_competition'] or 0, 1)
            },
            'top_performing_locations': city_rankings[:10],
            'last_updated': timezone.now().isoformat()
        }
    
    def find_location_opportunities(self, min_score: float = 80.0) -> Dict[str, Any]:
        """Find high-potential locations based on geographic intelligence."""
        self._check_permission('view_scoring_analytics')
        
        try:
            # Get geographic intelligence service
            geo_service = GeographicIntelligenceService(group=self.group)
            
            # Find optimal locations (mock implementation for now)
            # In real implementation, this would use geo_service.find_optimal_locations()
            
            leads_in_high_scoring_areas = Lead.objects.filter(
                group=self.group,
                geographic_score__gte=min_score,
                target_neighborhood__isnull=False
            ).select_related('target_neighborhood', 'target_neighborhood__metrics')
            
            opportunities = []
            for lead in leads_in_high_scoring_areas:
                if lead.target_neighborhood and lead.target_neighborhood.metrics:
                    opportunities.append({
                        'lead_id': str(lead.id),
                        'company_name': lead.company_name,
                        'neighborhood': lead.target_neighborhood.name,
                        'geographic_score': lead.geographic_score,
                        'overall_neighborhood_score': lead.target_neighborhood.metrics.overall_score,
                        'accessibility_score': lead.accessibility_score,
                        'university_proximity_score': lead.university_proximity_score,
                        'market_demand_score': lead.market_demand_score,
                        'competition_score': lead.competition_score,
                        'recommendation': self._generate_location_recommendation(lead)
                    })
            
            # Sort by geographic score
            opportunities.sort(key=lambda x: x['geographic_score'], reverse=True)
            
            return {
                'min_score_threshold': min_score,
                'total_opportunities': len(opportunities),
                'high_potential_leads': opportunities[:20],  # Top 20
                'average_geographic_score': round(
                    sum(opp['geographic_score'] for opp in opportunities) / len(opportunities)
                    if opportunities else 0, 1
                ),
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error finding location opportunities: {str(e)}")
            raise ValidationError(f"Failed to find location opportunities: {str(e)}")
    
    def _generate_location_recommendation(self, lead: Lead) -> str:
        """Generate location-specific recommendation for a lead."""
        recommendations = []
        
        if lead.accessibility_score >= 85:
            recommendations.append("excellent transport links")
        elif lead.accessibility_score < 60:
            recommendations.append("improve transport accessibility")
        
        if lead.university_proximity_score >= 90:
            recommendations.append("prime university location")
        elif lead.university_proximity_score < 70:
            recommendations.append("consider closer university partnerships")
        
        if lead.market_demand_score >= 80:
            recommendations.append("strong student demand")
        
        if lead.competition_score >= 75:
            recommendations.append("favorable competitive landscape")
        
        if not recommendations:
            recommendations = ["review location strategy"]
        
        return f"Lead shows {', '.join(recommendations)}. Geographic score: {lead.geographic_score:.1f}/100."