"""
IC Pack generation and automation service.

Handles automated document generation, data collection, template rendering,
and approval workflow orchestration.
"""

import io
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, BinaryIO
from django.db import transaction, models
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from django.utils import timezone
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, Image, KeepTogether
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_JUSTIFY
    REPORTLAB_AVAILABLE = True
except ImportError:
    # Mock reportlab objects for testing when not available
    REPORTLAB_AVAILABLE = False
    
    class MockColors:
        class HexColor:
            def __init__(self, color): pass
    
    class MockParagraphStyle:
        def __init__(self, name, parent=None, **kwargs): pass
    
    class MockSampleStyleSheet:
        def __init__(self):
            self._styles = {}
        def add(self, style): pass
        def __getitem__(self, key): return MockParagraphStyle(key)
    
    colors = MockColors()
    A4 = (595.27, 841.89)
    SimpleDocTemplate = None
    Paragraph = None
    Spacer = None
    PageBreak = None
    getSampleStyleSheet = MockSampleStyleSheet
    ParagraphStyle = MockParagraphStyle
    inch = 72

from accounts.models import User
from files.models import FileAttachment
from notifications.models import Notification
from ..models import (
    ICPackTemplate, ICPack, ICPackApproval, ICPackDistribution,
    ICPackAuditLog, ICPackStatus, Deal
)

logger = logging.getLogger(__name__)


class ICPackGenerationError(Exception):
    """Exception raised during IC pack generation."""
    pass


class ICPackService:
    """
    Service for managing IC pack lifecycle including generation,
    approval workflow, and distribution.
    """
    
    def __init__(self):
        if REPORTLAB_AVAILABLE:
            self.styles = getSampleStyleSheet()
            self._setup_custom_styles()
        else:
            self.styles = MockSampleStyleSheet()
    
    def _setup_custom_styles(self):
        """Setup custom PDF styles."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='ICTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#215788'),
            spaceAfter=30
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#215788'),
            spaceAfter=12
        ))
        
        # Subsection style
        self.styles.add(ParagraphStyle(
            name='SubsectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#3C3C3B'),
            spaceAfter=8
        ))
    
    @transaction.atomic
    def create_ic_pack(self, deal: Deal, template: ICPackTemplate, 
                       created_by: User, meeting_date: datetime = None) -> ICPack:
        """
        Create a new IC pack for a deal.
        
        Args:
            deal: The deal for which to create the pack
            template: The template to use
            created_by: User creating the pack
            meeting_date: Optional scheduled meeting date
            
        Returns:
            Created ICPack instance
        """
        # Check for existing drafts
        existing_draft = ICPack.objects.filter(
            deal=deal,
            status=ICPackStatus.DRAFT
        ).first()
        
        if existing_draft:
            # Create new version instead
            ic_pack = existing_draft.create_new_version()
            ic_pack.created_by = created_by
            ic_pack.save()
        else:
            # Create new pack
            ic_pack = ICPack.objects.create(
                group=deal.group,
                deal=deal,
                template=template,
                title=f"IC Pack - {deal.name}",
                meeting_date=meeting_date,
                created_by=created_by
            )
        
        # Log creation
        ICPackAuditLog.log_action(
            ic_pack=ic_pack,
            action=ICPackAuditLog.ActionType.CREATED,
            actor=created_by,
            description=f"Created IC pack v{ic_pack.version} for {deal.name}"
        )
        
        # Generate initial content
        self._collect_pack_data(ic_pack)
        
        return ic_pack
    
    def _collect_pack_data(self, ic_pack: ICPack):
        """
        Collect data from various sources for the IC pack.
        
        Gathers data from deal, partner, assessment, and other related models.
        """
        deal = ic_pack.deal
        sections_data = {}
        
        # Executive Summary
        sections_data['executive_summary'] = {
            'deal_name': deal.name,
            'deal_type': deal.get_deal_type_display(),
            'deal_stage': deal.current_stage.name if deal.current_stage else 'N/A',
            'partner': deal.partner.company_name if hasattr(deal, 'partner') else 'N/A',
            'total_investment': str(deal.total_investment_amount) if hasattr(deal, 'total_investment_amount') else 'TBD',
            'key_highlights': self._get_key_highlights(deal),
            'recommendation': self._generate_recommendation(deal)
        }
        
        # Deal Overview
        sections_data['deal_overview'] = {
            'description': deal.description or 'No description provided',
            'objectives': self._get_deal_objectives(deal),
            'timeline': self._get_deal_timeline(deal),
            'team_members': self._get_team_summary(deal)
        }
        
        # Financial Analysis
        sections_data['financial_analysis'] = {
            'investment_structure': self._get_investment_structure(deal),
            'financial_projections': self._get_financial_projections(deal),
            'sensitivity_analysis': self._get_sensitivity_analysis(deal),
            'returns_summary': self._calculate_returns_summary(deal)
        }
        
        # Risk Assessment
        sections_data['risk_assessment'] = {
            'key_risks': self._identify_key_risks(deal),
            'mitigation_strategies': self._get_mitigation_strategies(deal),
            'risk_matrix': self._generate_risk_matrix(deal)
        }
        
        # Due Diligence Summary
        sections_data['due_diligence'] = {
            'completed_items': self._get_completed_dd_items(deal),
            'outstanding_items': self._get_outstanding_dd_items(deal),
            'key_findings': self._get_dd_key_findings(deal)
        }
        
        # Market Analysis
        sections_data['market_analysis'] = {
            'market_overview': self._get_market_overview(deal),
            'competitive_landscape': self._get_competitive_analysis(deal),
            'growth_projections': self._get_market_growth_projections(deal)
        }
        
        # Store collected data
        ic_pack.sections_data = sections_data
        ic_pack.save()
    
    def _get_key_highlights(self, deal: Deal) -> List[str]:
        """Extract key highlights from the deal."""
        highlights = []
        
        # Add deal-specific highlights
        if hasattr(deal, 'expected_irr'):
            highlights.append(f"Expected IRR: {deal.expected_irr}%")
        
        if hasattr(deal, 'key_strengths'):
            highlights.extend(deal.key_strengths[:3])  # Top 3 strengths
        
        # Add milestone achievements
        completed_milestones = deal.milestones.filter(
            status='completed'
        ).count()
        total_milestones = deal.milestones.count()
        if total_milestones > 0:
            highlights.append(
                f"Milestone Progress: {completed_milestones}/{total_milestones} completed"
            )
        
        return highlights or ["Strategic investment opportunity", "Strong market position"]
    
    def _generate_recommendation(self, deal: Deal) -> str:
        """Generate investment recommendation based on deal analysis."""
        # This would be more sophisticated in production
        if hasattr(deal, 'recommendation'):
            return deal.recommendation
        
        # Simple rule-based recommendation
        if deal.current_stage and deal.current_stage.order >= 3:
            return "Proceed with investment subject to final due diligence completion"
        else:
            return "Continue evaluation and address outstanding items"
    
    def _get_deal_objectives(self, deal: Deal) -> List[str]:
        """Get deal objectives."""
        if hasattr(deal, 'objectives'):
            return deal.objectives
        
        return [
            "Achieve target returns",
            "Strategic market entry",
            "Portfolio diversification"
        ]
    
    def _get_deal_timeline(self, deal: Deal) -> Dict[str, Any]:
        """Get deal timeline information."""
        milestones = deal.milestones.order_by('target_date')
        
        return {
            'start_date': deal.created_at,
            'expected_close': deal.expected_close_date if hasattr(deal, 'expected_close_date') else None,
            'key_milestones': [
                {
                    'name': m.title,
                    'date': m.target_date,
                    'status': m.status
                }
                for m in milestones[:5]  # Top 5 milestones
            ]
        }
    
    def _get_team_summary(self, deal: Deal) -> List[Dict[str, str]]:
        """Get deal team summary."""
        team_members = deal.team_members.select_related('user').all()
        
        return [
            {
                'name': member.user.get_full_name(),
                'role': member.get_role_display(),
                'email': member.user.email
            }
            for member in team_members
        ]
    
    def _get_investment_structure(self, deal: Deal) -> Dict[str, Any]:
        """Get investment structure details."""
        # This would pull from actual financial models
        return {
            'total_investment': 'TBD',
            'equity_percentage': 'TBD',
            'investment_type': deal.get_deal_type_display(),
            'structure_details': 'To be finalized'
        }
    
    def _get_financial_projections(self, deal: Deal) -> Dict[str, Any]:
        """Get financial projections."""
        # Placeholder - would integrate with financial models
        return {
            'revenue_projections': [],
            'ebitda_projections': [],
            'cash_flow_projections': []
        }
    
    def _get_sensitivity_analysis(self, deal: Deal) -> Dict[str, Any]:
        """Get sensitivity analysis results."""
        return {
            'base_case_irr': 'TBD',
            'downside_case_irr': 'TBD',
            'upside_case_irr': 'TBD'
        }
    
    def _calculate_returns_summary(self, deal: Deal) -> Dict[str, Any]:
        """Calculate returns summary."""
        return {
            'projected_irr': 'TBD',
            'projected_multiple': 'TBD',
            'payback_period': 'TBD'
        }
    
    def _identify_key_risks(self, deal: Deal) -> List[Dict[str, str]]:
        """Identify key risks for the deal."""
        # This would integrate with risk assessment models
        return [
            {
                'category': 'Market Risk',
                'description': 'Market conditions may change',
                'impact': 'Medium',
                'likelihood': 'Medium'
            }
        ]
    
    def _get_mitigation_strategies(self, deal: Deal) -> List[str]:
        """Get risk mitigation strategies."""
        return [
            "Implement phased investment approach",
            "Establish clear governance structure",
            "Regular performance monitoring"
        ]
    
    def _generate_risk_matrix(self, deal: Deal) -> Dict[str, Any]:
        """Generate risk matrix data."""
        return {
            'high_impact_high_likelihood': [],
            'high_impact_low_likelihood': [],
            'low_impact_high_likelihood': [],
            'low_impact_low_likelihood': []
        }
    
    def _get_completed_dd_items(self, deal: Deal) -> List[str]:
        """Get completed due diligence items."""
        # Would integrate with DD tracking
        return ["Legal review", "Financial audit", "Technical assessment"]
    
    def _get_outstanding_dd_items(self, deal: Deal) -> List[str]:
        """Get outstanding due diligence items."""
        return ["Environmental assessment", "Final regulatory approvals"]
    
    def _get_dd_key_findings(self, deal: Deal) -> List[str]:
        """Get key due diligence findings."""
        return [
            "Strong financial performance",
            "Experienced management team",
            "Clear growth strategy"
        ]
    
    def _get_market_overview(self, deal: Deal) -> Dict[str, Any]:
        """Get market overview."""
        return {
            'market_size': 'TBD',
            'growth_rate': 'TBD',
            'key_trends': []
        }
    
    def _get_competitive_analysis(self, deal: Deal) -> Dict[str, Any]:
        """Get competitive analysis."""
        return {
            'main_competitors': [],
            'competitive_advantages': [],
            'market_position': 'TBD'
        }
    
    def _get_market_growth_projections(self, deal: Deal) -> Dict[str, Any]:
        """Get market growth projections."""
        return {
            'short_term_growth': 'TBD',
            'long_term_growth': 'TBD',
            'key_drivers': []
        }
    
    @transaction.atomic
    def generate_ic_pack_document(self, ic_pack: ICPack, user: User) -> FileAttachment:
        """
        Generate the IC pack PDF document.
        
        Args:
            ic_pack: The IC pack to generate
            user: User generating the document
            
        Returns:
            FileAttachment instance with the generated PDF
        """
        start_time = timezone.now()
        
        try:
            if not REPORTLAB_AVAILABLE:
                raise ICPackGenerationError("ReportLab is required for PDF generation")
            
            # Create PDF in memory
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )
            
            # Build document content
            story = self._build_pdf_content(ic_pack)
            
            # Generate PDF
            doc.build(story)
            
            # Save as FileAttachment
            buffer.seek(0)
            file_name = f"IC_Pack_{ic_pack.deal.name}_v{ic_pack.version}_{datetime.now().strftime('%Y%m%d')}.pdf"
            
            # Create assessment for file attachment if needed
            assessment = None
            if hasattr(ic_pack.deal, 'assessment'):
                assessment = ic_pack.deal.assessment
            
            file_attachment = FileAttachment.objects.create(
                file_name=file_name,
                file_type='application/pdf',
                file_size=buffer.getbuffer().nbytes,
                uploaded_by=user,
                assessment=assessment  # May be None
            )
            
            # Save file content
            file_attachment.file.save(file_name, ContentFile(buffer.getvalue()))
            
            # Update IC pack
            ic_pack.generated_document = file_attachment
            
            # Calculate generation time
            generation_time = (timezone.now() - start_time).total_seconds()
            ic_pack.generation_time_seconds = generation_time
            ic_pack.save()
            
            # Log generation
            ICPackAuditLog.log_action(
                ic_pack=ic_pack,
                action=ICPackAuditLog.ActionType.MODIFIED,
                actor=user,
                description=f"Generated PDF document in {generation_time:.2f} seconds"
            )
            
            return file_attachment
            
        except Exception as e:
            logger.error(f"Error generating IC pack: {str(e)}")
            raise ICPackGenerationError(f"Failed to generate IC pack: {str(e)}")
    
    def _build_pdf_content(self, ic_pack: ICPack) -> List:
        """Build PDF content from IC pack data."""
        story = []
        
        # Title page
        story.append(Paragraph(ic_pack.title, self.styles['ICTitle']))
        story.append(Spacer(1, 0.5*inch))
        
        # Meeting details
        if ic_pack.meeting_date:
            story.append(Paragraph(
                f"IC Meeting Date: {ic_pack.meeting_date.strftime('%B %d, %Y')}",
                self.styles['Normal']
            ))
        
        story.append(Paragraph(
            f"Version: {ic_pack.version}",
            self.styles['Normal']
        ))
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%B %d, %Y')}",
            self.styles['Normal']
        ))
        
        story.append(PageBreak())
        
        # Generate sections based on template
        for section_config in ic_pack.template.sections:
            section_id = section_config['id']
            section_title = section_config['title']
            
            if section_id in ic_pack.sections_data:
                story.extend(self._build_section(
                    section_title,
                    ic_pack.sections_data[section_id]
                ))
                
                # Add page break between major sections
                story.append(PageBreak())
        
        return story
    
    def _build_section(self, title: str, data: Dict[str, Any]) -> List:
        """Build a PDF section from data."""
        elements = []
        
        # Section header
        elements.append(Paragraph(title, self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.2*inch))
        
        # Process section data
        for key, value in data.items():
            # Convert key to readable format
            readable_key = key.replace('_', ' ').title()
            
            if isinstance(value, str):
                elements.append(Paragraph(f"<b>{readable_key}:</b> {value}", self.styles['Normal']))
                elements.append(Spacer(1, 0.1*inch))
            
            elif isinstance(value, list):
                elements.append(Paragraph(f"<b>{readable_key}:</b>", self.styles['Normal']))
                for item in value:
                    if isinstance(item, str):
                        elements.append(Paragraph(f"• {item}", self.styles['Normal']))
                    elif isinstance(item, dict):
                        # Handle complex list items
                        item_text = ', '.join([f"{k}: {v}" for k, v in item.items()])
                        elements.append(Paragraph(f"• {item_text}", self.styles['Normal']))
                elements.append(Spacer(1, 0.1*inch))
            
            elif isinstance(value, dict):
                elements.append(Paragraph(f"<b>{readable_key}:</b>", self.styles['Normal']))
                for sub_key, sub_value in value.items():
                    readable_sub_key = sub_key.replace('_', ' ').title()
                    elements.append(Paragraph(f"  {readable_sub_key}: {sub_value}", self.styles['Normal']))
                elements.append(Spacer(1, 0.1*inch))
        
        return elements
    
    @transaction.atomic
    def submit_for_approval(self, ic_pack: ICPack, user: User):
        """
        Submit IC pack for approval workflow.
        
        Args:
            ic_pack: The IC pack to submit
            user: User submitting the pack
        """
        # Validate pack is ready
        if not ic_pack.generated_document:
            raise ValueError("IC pack must have a generated document before submission")
        
        # Update status
        ic_pack.submit_for_review()
        ic_pack.save()
        
        # Start review process
        ic_pack.start_review()
        ic_pack.save()
        
        # Create first approval stage
        if ic_pack.template.approval_stages:
            first_stage = ic_pack.template.approval_stages[0]
            
            approval = ICPackApproval.objects.create(
                group=ic_pack.group,
                ic_pack=ic_pack,
                stage=first_stage['stage'],
                stage_name=first_stage['name']
            )
            
            # Find approvers for this stage
            approvers = self._find_approvers_for_stage(ic_pack, first_stage)
            
            # Send notifications
            for approver in approvers:
                Notification.objects.create(
                    user=approver,
                    title=f"IC Pack Approval Required: {ic_pack.title}",
                    message=f"Please review and approve the IC pack for {ic_pack.deal.name}",
                    notification_type='IC_PACK_APPROVAL',
                    related_object_id=str(ic_pack.id),
                    action_url=f"/deals/{ic_pack.deal.id}/ic-packs/{ic_pack.id}/"
                )
        
        # Log submission
        ICPackAuditLog.log_action(
            ic_pack=ic_pack,
            action=ICPackAuditLog.ActionType.SUBMITTED,
            actor=user,
            description="Submitted for approval"
        )
    
    def _find_approvers_for_stage(self, ic_pack: ICPack, stage_config: Dict) -> List[User]:
        """Find appropriate approvers for a stage."""
        required_role = stage_config.get('required_role')
        
        # Get users with required role in the same group
        approvers = User.objects.filter(
            groups=ic_pack.group,
            role=required_role,
            is_active=True
        )
        
        # Exclude the creator
        approvers = approvers.exclude(id=ic_pack.created_by.id)
        
        return list(approvers)
    
    @transaction.atomic
    def distribute_ic_pack(self, ic_pack: ICPack, user: User, 
                          recipient_emails: List[str], message: str = None):
        """
        Distribute approved IC pack to recipients.
        
        Args:
            ic_pack: The approved IC pack to distribute
            user: User distributing the pack
            recipient_emails: List of recipient email addresses
            message: Optional message to include
        """
        if ic_pack.status != ICPackStatus.APPROVED:
            raise ValueError("Only approved IC packs can be distributed")
        
        # Update status
        ic_pack.distribute()
        ic_pack.save()
        
        # Create distribution records
        for email in recipient_emails:
            distribution = ICPackDistribution.objects.create(
                group=ic_pack.group,
                ic_pack=ic_pack,
                recipient_email=email,
                sent_by=user,
                expires_at=timezone.now() + timedelta(days=30)  # 30-day expiry
            )
            
            # Send email notification
            self._send_distribution_email(distribution, message)
        
        # Log distribution
        ICPackAuditLog.log_action(
            ic_pack=ic_pack,
            action=ICPackAuditLog.ActionType.DISTRIBUTED,
            actor=user,
            description=f"Distributed to {len(recipient_emails)} recipients",
            metadata={'recipients': recipient_emails}
        )
    
    def _send_distribution_email(self, distribution: ICPackDistribution, 
                                message: str = None):
        """Send distribution email to recipient."""
        # This would integrate with the email service
        # For now, just log
        logger.info(
            f"Sending IC pack {distribution.ic_pack.title} to {distribution.recipient_email}"
        )
    
    def get_ic_pack_analytics(self, deal: Deal) -> Dict[str, Any]:
        """
        Get analytics for IC packs related to a deal.
        
        Args:
            deal: The deal to analyze
            
        Returns:
            Dictionary with analytics data
        """
        ic_packs = ICPack.objects.filter(deal=deal)
        
        analytics = {
            'total_packs': ic_packs.count(),
            'latest_version': ic_packs.order_by('-version').first().version if ic_packs.exists() else 0,
            'status_distribution': {},
            'average_generation_time': 0,
            'average_approval_time': None,
            'total_distributions': 0,
            'engagement_metrics': {
                'total_views': 0,
                'unique_viewers': 0,
                'average_view_time': None
            }
        }
        
        # Status distribution
        for status in ICPackStatus:
            count = ic_packs.filter(status=status).count()
            analytics['status_distribution'][status.label] = count
        
        # Generation time
        generation_times = ic_packs.exclude(
            generation_time_seconds__isnull=True
        ).values_list('generation_time_seconds', flat=True)
        
        if generation_times:
            analytics['average_generation_time'] = sum(generation_times) / len(generation_times)
        
        # Approval time (for approved packs)
        approved_packs = ic_packs.filter(status=ICPackStatus.APPROVED)
        approval_times = []
        
        for pack in approved_packs:
            first_submission = pack.audit_logs.filter(
                action=ICPackAuditLog.ActionType.SUBMITTED
            ).order_by('created_at').first()
            
            approval = pack.audit_logs.filter(
                action=ICPackAuditLog.ActionType.APPROVED
            ).order_by('created_at').first()
            
            if first_submission and approval:
                time_diff = (approval.created_at - first_submission.created_at).total_seconds() / 3600
                approval_times.append(time_diff)
        
        if approval_times:
            analytics['average_approval_time'] = sum(approval_times) / len(approval_times)
        
        # Distribution and engagement
        distributions = ICPackDistribution.objects.filter(
            ic_pack__in=ic_packs
        )
        analytics['total_distributions'] = distributions.count()
        
        # Engagement metrics
        total_views = distributions.aggregate(
            total=models.Sum('view_count')
        )['total'] or 0
        analytics['engagement_metrics']['total_views'] = total_views
        
        unique_viewers = distributions.filter(
            view_count__gt=0
        ).count()
        analytics['engagement_metrics']['unique_viewers'] = unique_viewers
        
        return analytics