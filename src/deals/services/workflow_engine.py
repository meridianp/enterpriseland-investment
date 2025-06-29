"""
Workflow engine for managing deal progression and automation.
"""

import logging
from typing import Dict, List, Optional, Tuple
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from ..models import (
    Deal, DealStage, DealTransition, WorkflowTemplate,
    DealActivity, ActivityType, DealMilestone
)

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """
    Engine for managing deal workflow progression and automation.
    """
    
    def __init__(self, deal: Deal):
        self.deal = deal
        self.workflow = self._get_workflow_template()
    
    def _get_workflow_template(self) -> Optional[WorkflowTemplate]:
        """Get the workflow template for the deal"""
        # First try to get from current stage
        if self.deal.current_stage:
            return self.deal.current_stage.workflow_template
        
        # Otherwise get default for deal type
        return WorkflowTemplate.objects.filter(
            deal_type=self.deal.deal_type,
            is_default=True,
            is_active=True
        ).first()
    
    def get_current_stage(self) -> Optional[DealStage]:
        """Get the current stage of the deal"""
        return self.deal.current_stage
    
    def get_available_transitions(self) -> List[Dict]:
        """
        Get available transitions from current state.
        
        Returns list of possible next stages with requirements.
        """
        if not self.deal.current_stage:
            # If no current stage, get first stage
            if self.workflow:
                first_stage = self.workflow.stages.order_by('order').first()
                if first_stage:
                    return [{
                        'stage': first_stage,
                        'status': Deal.Status.INITIAL_REVIEW,
                        'requirements': self._check_stage_requirements(first_stage),
                        'can_transition': True
                    }]
            return []
        
        current_stage = self.deal.current_stage
        transitions = []
        
        # Get next stages based on workflow
        next_stages = self.workflow.stages.filter(
            order__gt=current_stage.order
        ).order_by('order')
        
        for stage in next_stages:
            # Check if this is the immediate next stage
            is_next = not self.workflow.stages.filter(
                order__gt=current_stage.order,
                order__lt=stage.order
            ).exists()
            
            if is_next:
                requirements = self._check_stage_requirements(stage)
                can_transition = all(req['met'] for req in requirements)
                
                transitions.append({
                    'stage': stage,
                    'status': self._get_status_for_stage(stage),
                    'requirements': requirements,
                    'can_transition': can_transition
                })
        
        # Add rejection option
        if self.deal.status not in [Deal.Status.COMPLETED, Deal.Status.REJECTED]:
            transitions.append({
                'stage': None,
                'status': Deal.Status.REJECTED,
                'requirements': [],
                'can_transition': True
            })
        
        return transitions
    
    def _check_stage_requirements(self, stage: DealStage) -> List[Dict]:
        """Check requirements for entering a stage"""
        requirements = []
        
        # Check required documents
        for doc_type in stage.required_documents:
            has_doc = self.deal.files.filter(
                document_type=doc_type,
                is_active=True
            ).exists()
            requirements.append({
                'type': 'document',
                'name': doc_type,
                'met': has_doc,
                'description': f"Required document: {doc_type}"
            })
        
        # Check required tasks
        for task in stage.required_tasks:
            # This would check against task completion
            requirements.append({
                'type': 'task',
                'name': task,
                'met': False,  # Implement task checking
                'description': f"Complete task: {task}"
            })
        
        # Check blocking milestones
        blocking_milestones = self.deal.milestones.filter(
            stage=self.deal.current_stage,
            is_blocking=True,
            status__in=[DealMilestone.Status.PENDING, DealMilestone.Status.IN_PROGRESS]
        )
        for milestone in blocking_milestones:
            requirements.append({
                'type': 'milestone',
                'name': milestone.name,
                'met': milestone.status == DealMilestone.Status.COMPLETED,
                'description': f"Complete milestone: {milestone.name}"
            })
        
        # Check custom entry criteria
        if stage.entry_criteria:
            for criterion, config in stage.entry_criteria.items():
                met = self._evaluate_criterion(criterion, config)
                requirements.append({
                    'type': 'criterion',
                    'name': criterion,
                    'met': met,
                    'description': config.get('description', criterion)
                })
        
        return requirements
    
    def _evaluate_criterion(self, criterion: str, config: Dict) -> bool:
        """Evaluate a custom criterion"""
        # Implement custom criteria evaluation
        # Examples: minimum_irr, valuation_complete, legal_review_done
        
        if criterion == 'minimum_irr':
            target = config.get('value', 0)
            return (self.deal.irr_target or 0) >= target
        
        elif criterion == 'valuation_complete':
            return self.deal.post_money_valuation is not None
        
        elif criterion == 'has_deal_lead':
            return self.deal.deal_lead is not None
        
        # Default to True for unimplemented criteria
        return True
    
    def _get_status_for_stage(self, stage: DealStage) -> str:
        """Map stage to deal status"""
        stage_status_map = {
            DealStage.StageType.ORIGINATION: Deal.Status.PIPELINE,
            DealStage.StageType.SCREENING: Deal.Status.INITIAL_REVIEW,
            DealStage.StageType.ANALYSIS: Deal.Status.DUE_DILIGENCE,
            DealStage.StageType.APPROVAL: Deal.Status.NEGOTIATION,
            DealStage.StageType.EXECUTION: Deal.Status.DOCUMENTATION,
            DealStage.StageType.CLOSING: Deal.Status.CLOSING,
            DealStage.StageType.POST_CLOSING: Deal.Status.COMPLETED,
        }
        return stage_status_map.get(stage.stage_type, Deal.Status.PIPELINE)
    
    @transaction.atomic
    def transition_to_stage(
        self,
        target_stage: DealStage,
        performed_by,
        reason: str = '',
        force: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        Transition deal to a new stage.
        
        Returns (success, errors) tuple.
        """
        errors = []
        
        # Check if transition is allowed
        if not force:
            available = self.get_available_transitions()
            stage_ids = [t['stage'].id for t in available if t['stage'] and t['can_transition']]
            
            if target_stage.id not in stage_ids:
                requirements = self._check_stage_requirements(target_stage)
                unmet = [r for r in requirements if not r['met']]
                errors.extend([r['description'] for r in unmet])
                return False, errors
        
        # Get new status
        new_status = self._get_status_for_stage(target_stage)
        
        # Record transition
        transition = DealTransition.objects.create(
            deal=self.deal,
            from_stage=self.deal.current_stage,
            to_stage=target_stage,
            from_status=self.deal.status,
            to_status=new_status,
            performed_by=performed_by,
            reason=reason,
            group=self.deal.group
        )
        
        # Update deal
        old_stage = self.deal.current_stage
        self.deal.current_stage = target_stage
        self.deal.status = new_status
        self.deal.stage_entered_at = timezone.now()
        self.deal.save()
        
        # Create activity
        DealActivity.objects.create(
            deal=self.deal,
            activity_type=ActivityType.STAGE_CHANGED,
            performed_by=performed_by,
            description=f"Deal moved from {old_stage.name if old_stage else 'Start'} to {target_stage.name}",
            metadata={
                'from_stage': old_stage.name if old_stage else None,
                'to_stage': target_stage.name,
                'from_status': transition.from_status,
                'to_status': transition.to_status
            },
            group=self.deal.group
        )
        
        # Execute automation rules
        self._execute_stage_automation(target_stage)
        
        # Create milestones for new stage
        self._create_stage_milestones(target_stage)
        
        return True, []
    
    def _execute_stage_automation(self, stage: DealStage):
        """Execute automation rules for a stage"""
        if not stage.automation_rules:
            return
        
        rules = stage.automation_rules
        
        # Auto-assign team members
        if 'auto_assign' in rules:
            for role_code in rules['auto_assign']:
                # Implement auto-assignment logic
                pass
        
        # Create tasks
        if 'create_tasks' in rules:
            for task_config in rules['create_tasks']:
                # Implement task creation
                pass
        
        # Send notifications
        if 'notifications' in rules:
            for notification_config in rules['notifications']:
                # Implement notification sending
                pass
    
    def _create_stage_milestones(self, stage: DealStage):
        """Create milestones for a stage based on templates"""
        from ..models import MilestoneTemplate
        
        templates = MilestoneTemplate.objects.filter(
            stage=stage,
            is_active=True,
            deal_types=self.deal.deal_type
        )
        
        for template in templates:
            # Calculate due date
            if template.days_from_stage_start is not None:
                due_date = timezone.now().date() + timezone.timedelta(
                    days=template.days_from_stage_start
                )
            else:
                # Default to end of stage target duration
                due_date = timezone.now().date() + timezone.timedelta(
                    days=stage.target_duration_days or 30
                )
            
            DealMilestone.objects.create(
                deal=self.deal,
                template=template,
                name=template.name,
                description=template.description,
                due_date=due_date,
                stage=stage,
                is_blocking=template.is_blocking,
                required_documents=template.required_documents,
                checklist_items=template.checklist_items,
                group=self.deal.group
            )
    
    def check_stage_duration_alerts(self):
        """Check if current stage is exceeding target duration"""
        if not self.deal.current_stage or not self.deal.stage_entered_at:
            return
        
        stage = self.deal.current_stage
        days_in_stage = (timezone.now() - self.deal.stage_entered_at).days
        
        alerts = []
        
        # Check target duration
        if stage.target_duration_days and days_in_stage > stage.target_duration_days:
            alerts.append({
                'type': 'target_exceeded',
                'message': f"Deal has been in {stage.name} for {days_in_stage} days "
                          f"(target: {stage.target_duration_days} days)",
                'severity': 'warning'
            })
        
        # Check max duration
        if stage.max_duration_days and days_in_stage > stage.max_duration_days:
            alerts.append({
                'type': 'max_exceeded',
                'message': f"Deal has exceeded maximum duration for {stage.name} "
                          f"({days_in_stage} days > {stage.max_duration_days} days)",
                'severity': 'critical'
            })
        
        return alerts