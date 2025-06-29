"""
Standard assessment templates for the CASA Due Diligence Platform.

Provides pre-configured assessment templates with standardized metrics
for consistent evaluation across development partners and PBSA schemes.
"""

from typing import Dict, List, Any
from django.db import transaction

from .assessment_models import (
    AssessmentTemplate, MetricTemplate, AssessmentType, MetricCategory
)
from accounts.models import Group


class TemplateManager:
    """Manager for creating and maintaining standard assessment templates."""
    
    @staticmethod
    @transaction.atomic
    def create_standard_partner_template(group: Group) -> AssessmentTemplate:
        """
        Create the standard development partner assessment template.
        
        Based on the CASA due diligence framework with comprehensive
        metrics across all assessment categories.
        """
        template = AssessmentTemplate.objects.create(
            group=group,
            template_name='CASA Standard Partner Assessment',
            description='''
            Comprehensive development partner assessment template based on 
            CASA's standardized due diligence framework. Evaluates partners 
            across financial health, operational capability, track record, 
            market position, risk profile, and ESG factors.
            ''',
            assessment_type=AssessmentType.PARTNER,
            version='1.0'
        )
        
        # Financial Health Metrics (Weight: 5 = Critical, 4 = Very Important, 3 = Important)
        financial_metrics = [
            {
                'name': 'Balance Sheet Strength',
                'description': 'Overall financial position including net assets, liquidity, and capital structure',
                'weight': 5,
                'guidelines': '''
                Assess net assets, current ratio, working capital, and debt levels.
                Consider trend analysis over 3+ years where available.
                ''',
                'criteria': {
                    '1': 'Poor financial position with significant balance sheet concerns',
                    '2': 'Weak balance sheet requiring careful monitoring',
                    '3': 'Adequate financial position with some areas for improvement',
                    '4': 'Strong balance sheet with good liquidity and capital structure',
                    '5': 'Excellent financial strength across all balance sheet metrics'
                }
            },
            {
                'name': 'Profitability & Performance',
                'description': 'Revenue growth, profit margins, and operational efficiency',
                'weight': 5,
                'guidelines': '''
                Evaluate profit margins, EBITDA performance, return on assets/equity.
                Consider consistency and sustainability of profitability.
                ''',
                'criteria': {
                    '1': 'Consistent losses or very poor profitability',
                    '2': 'Marginal profitability with volatility concerns',
                    '3': 'Moderate profitability meeting basic requirements',
                    '4': 'Good profitability with consistent performance',
                    '5': 'Excellent profitability demonstrating operational excellence'
                }
            },
            {
                'name': 'Cash Flow Management',
                'description': 'Operating cash flow generation and cash management practices',
                'weight': 4,
                'guidelines': '''
                Review operating cash flow trends, free cash flow, and cash conversion cycles.
                Assess cash management policies and liquidity planning.
                ''',
                'criteria': {
                    '1': 'Poor cash generation with significant cash flow concerns',
                    '2': 'Inconsistent cash flows requiring attention',
                    '3': 'Adequate cash flow management meeting basic needs',
                    '4': 'Strong cash generation with good management practices',
                    '5': 'Excellent cash flow generation and sophisticated management'
                }
            },
            {
                'name': 'Credit Profile & Debt Management',
                'description': 'Credit worthiness, debt levels, and banking relationships',
                'weight': 4,
                'guidelines': '''
                Assess debt-to-assets ratio, coverage ratios, credit ratings, banking relationships.
                Consider covenant compliance and refinancing requirements.
                ''',
                'criteria': {
                    '1': 'High credit risk with debt management concerns',
                    '2': 'Elevated credit risk requiring monitoring',
                    '3': 'Acceptable credit profile with manageable debt levels',
                    '4': 'Good credit standing with strong banking relationships',
                    '5': 'Excellent credit profile with optimal debt management'
                }
            }
        ]
        
        # Operational Capability Metrics
        operational_metrics = [
            {
                'name': 'Development Team Strength',
                'description': 'Size, experience, and capability of the development team',
                'weight': 5,
                'guidelines': '''
                Evaluate team size relative to pipeline, experience levels, key personnel.
                Consider organizational structure and succession planning.
                ''',
                'criteria': {
                    '1': 'Inadequate team size or significant capability gaps',
                    '2': 'Limited team capacity with some experience concerns',
                    '3': 'Adequate team meeting current pipeline requirements',
                    '4': 'Strong team with good depth and experience',
                    '5': 'Exceptional team with proven expertise and strong bench'
                }
            },
            {
                'name': 'Project Management Capability',
                'description': 'Project delivery processes, systems, and track record',
                'weight': 4,
                'guidelines': '''
                Assess project management methodologies, delivery systems, quality control.
                Review project delivery history for timeliness and budget performance.
                ''',
                'criteria': {
                    '1': 'Poor project management with systemic delivery issues',
                    '2': 'Basic project management with room for improvement',
                    '3': 'Adequate project management meeting standard requirements',
                    '4': 'Strong project management with good delivery record',
                    '5': 'Excellent project management with best-in-class processes'
                }
            },
            {
                'name': 'Organizational Infrastructure',
                'description': 'Corporate structure, systems, and operational processes',
                'weight': 3,
                'guidelines': '''
                Review organizational structure, IT systems, operational procedures.
                Consider scalability and process maturity.
                ''',
                'criteria': {
                    '1': 'Weak organizational infrastructure limiting effectiveness',
                    '2': 'Basic infrastructure with significant gaps',
                    '3': 'Adequate infrastructure supporting current operations',
                    '4': 'Strong infrastructure enabling effective operations',
                    '5': 'Sophisticated infrastructure supporting scale and growth'
                }
            }
        ]
        
        # Track Record & Experience Metrics
        track_record_metrics = [
            {
                'name': 'PBSA Development Experience',
                'description': 'Depth and breadth of student accommodation development experience',
                'weight': 5,
                'guidelines': '''
                Evaluate years in PBSA, number of schemes completed, total beds delivered.
                Consider specialization level and scheme types/scales delivered.
                ''',
                'criteria': {
                    '1': 'No or very limited PBSA experience',
                    '2': 'Basic PBSA experience with limited track record',
                    '3': 'Moderate PBSA experience demonstrating competence',
                    '4': 'Strong PBSA experience with good delivery history',
                    '5': 'Extensive PBSA specialization with exceptional track record'
                }
            },
            {
                'name': 'Location-Specific Experience',
                'description': 'Experience in target location/region for current assessment',
                'weight': 4,
                'guidelines': '''
                Assess experience in specific target location, local market knowledge.
                Consider local partnerships, regulatory familiarity, stakeholder relationships.
                ''',
                'criteria': {
                    '1': 'No experience in target location',
                    '2': 'Limited location experience requiring support',
                    '3': 'Some location experience with adequate market knowledge',
                    '4': 'Good location experience with strong local presence',
                    '5': 'Extensive location expertise with established local network'
                }
            },
            {
                'name': 'Delivery Track Record',
                'description': 'Historical performance on time, budget, and quality delivery',
                'weight': 4,
                'guidelines': '''
                Review completion statistics, budget performance, quality outcomes.
                Consider client satisfaction and repeat business indicators.
                ''',
                'criteria': {
                    '1': 'Poor delivery record with systemic issues',
                    '2': 'Mixed delivery performance with concerning patterns',
                    '3': 'Adequate delivery meeting basic standards',
                    '4': 'Good delivery record with consistent performance',
                    '5': 'Excellent delivery record exceeding expectations'
                }
            },
            {
                'name': 'Scale & Complexity Experience',
                'description': 'Experience with schemes of similar scale and complexity',
                'weight': 3,
                'guidelines': '''
                Evaluate experience with similar project scales, complexity levels.
                Consider scheme types, bed counts, development challenges handled.
                ''',
                'criteria': {
                    '1': 'No experience with comparable scale/complexity',
                    '2': 'Limited experience requiring significant support',
                    '3': 'Some relevant experience demonstrating capability',
                    '4': 'Good experience with similar scale projects',
                    '5': 'Extensive experience exceeding current requirements'
                }
            }
        ]
        
        # Market Position Metrics
        market_metrics = [
            {
                'name': 'Market Reputation',
                'description': 'Industry reputation and stakeholder relationships',
                'weight': 3,
                'guidelines': '''
                Assess industry standing, client references, stakeholder feedback.
                Consider market perception and competitive positioning.
                ''',
                'criteria': {
                    '1': 'Poor market reputation with significant concerns',
                    '2': 'Mixed reputation requiring careful consideration',
                    '3': 'Adequate market standing meeting basic requirements',
                    '4': 'Good reputation with positive market perception',
                    '5': 'Excellent reputation as preferred market participant'
                }
            },
            {
                'name': 'Competitive Position',
                'description': 'Market share, competitive advantages, and differentiation',
                'weight': 3,
                'guidelines': '''
                Evaluate market position relative to competitors, unique capabilities.
                Consider competitive advantages and market differentiation.
                ''',
                'criteria': {
                    '1': 'Weak competitive position with limited advantages',
                    '2': 'Basic competitive position requiring strengthening',
                    '3': 'Adequate competitive position in target market',
                    '4': 'Strong competitive position with clear advantages',
                    '5': 'Market-leading position with significant differentiation'
                }
            }
        ]
        
        # Risk Assessment Metrics
        risk_metrics = [
            {
                'name': 'Financial Risk Profile',
                'description': 'Overall financial risk including leverage, liquidity, and covenant risk',
                'weight': 4,
                'guidelines': '''
                Assess leverage levels, liquidity risk, covenant compliance risk.
                Consider financial stability and stress testing scenarios.
                ''',
                'criteria': {
                    '1': 'High financial risk with significant concerns',
                    '2': 'Elevated financial risk requiring monitoring',
                    '3': 'Moderate financial risk within acceptable parameters',
                    '4': 'Low financial risk with good risk management',
                    '5': 'Minimal financial risk with excellent risk controls'
                }
            },
            {
                'name': 'Operational Risk',
                'description': 'Key person risk, process risk, and operational vulnerabilities',
                'weight': 3,
                'guidelines': '''
                Evaluate key person dependencies, process risks, operational controls.
                Consider business continuity planning and risk mitigation measures.
                ''',
                'criteria': {
                    '1': 'High operational risk with limited mitigation',
                    '2': 'Elevated operational risk requiring attention',
                    '3': 'Moderate operational risk with adequate controls',
                    '4': 'Low operational risk with good risk management',
                    '5': 'Minimal operational risk with comprehensive controls'
                }
            },
            {
                'name': 'Market & External Risk',
                'description': 'Market cycle risk, regulatory risk, and external dependencies',
                'weight': 3,
                'guidelines': '''
                Assess exposure to market cycles, regulatory changes, external factors.
                Consider diversification and risk mitigation strategies.
                ''',
                'criteria': {
                    '1': 'High external risk with limited protection',
                    '2': 'Elevated external risk requiring monitoring',
                    '3': 'Moderate external risk with some mitigation',
                    '4': 'Low external risk with good risk management',
                    '5': 'Minimal external risk with comprehensive protection'
                }
            }
        ]
        
        # ESG (Environmental, Social, Governance) Metrics
        esg_metrics = [
            {
                'name': 'Environmental Compliance & Sustainability',
                'description': 'Environmental practices, sustainability initiatives, and compliance',
                'weight': 3,
                'guidelines': '''
                Evaluate environmental policies, sustainability practices, compliance record.
                Consider certifications, environmental management systems, green building practices.
                ''',
                'criteria': {
                    '1': 'Poor environmental practices with compliance concerns',
                    '2': 'Basic environmental compliance with limited initiatives',
                    '3': 'Adequate environmental practices meeting standards',
                    '4': 'Good environmental practices with proactive initiatives',
                    '5': 'Excellent environmental leadership with innovative practices'
                }
            },
            {
                'name': 'Corporate Governance',
                'description': 'Board structure, governance practices, and transparency',
                'weight': 3,
                'guidelines': '''
                Assess board composition, governance frameworks, transparency practices.
                Consider ethical standards, compliance systems, stakeholder engagement.
                ''',
                'criteria': {
                    '1': 'Poor governance with significant concerns',
                    '2': 'Basic governance meeting minimum requirements',
                    '3': 'Adequate governance with room for improvement',
                    '4': 'Good governance practices with strong frameworks',
                    '5': 'Excellent governance demonstrating best practices'
                }
            }
        ]
        
        # Create all metric templates
        all_metrics = [
            (MetricCategory.FINANCIAL, financial_metrics),
            (MetricCategory.OPERATIONAL, operational_metrics),
            (MetricCategory.TRACK_RECORD, track_record_metrics),
            (MetricCategory.MARKET, market_metrics),
            (MetricCategory.RISK, risk_metrics),
            (MetricCategory.ESG, esg_metrics)
        ]
        
        display_order = 1
        for category, metrics in all_metrics:
            for metric_data in metrics:
                MetricTemplate.objects.create(
                    group=group,
                    template=template,
                    metric_name=metric_data['name'],
                    metric_description=metric_data['description'],
                    category=category,
                    default_weight=metric_data['weight'],
                    assessment_guidelines=metric_data['guidelines'],
                    scoring_criteria=metric_data['criteria'],
                    is_mandatory=True,
                    display_order=display_order
                )
                display_order += 1
        
        return template
    
    @staticmethod
    @transaction.atomic
    def create_standard_scheme_template(group: Group) -> AssessmentTemplate:
        """
        Create the standard PBSA scheme assessment template.
        
        Focuses on location factors, site characteristics, economic viability,
        and operational considerations specific to PBSA developments.
        """
        template = AssessmentTemplate.objects.create(
            group=group,
            template_name='CASA Standard Scheme Assessment',
            description='''
            Comprehensive PBSA scheme assessment template evaluating location
            fundamentals, site characteristics, economic viability, operational
            considerations, and risk factors specific to student accommodation.
            ''',
            assessment_type=AssessmentType.SCHEME,
            version='1.0'
        )
        
        # Location & Market Fundamentals
        location_metrics = [
            {
                'name': 'University Proximity & Quality',
                'description': 'Distance to target university(ies) and institution quality/reputation',
                'weight': 5,
                'guidelines': '''
                Evaluate walking distance/transport links to campus, university ranking/reputation.
                Consider student population size and accommodation demand patterns.
                ''',
                'criteria': {
                    '1': 'Poor location relative to university with limited appeal',
                    '2': 'Suboptimal location requiring transport with moderate appeal',
                    '3': 'Acceptable location with reasonable access to campus',
                    '4': 'Good location with convenient campus access',
                    '5': 'Excellent location with premium campus proximity'
                }
            },
            {
                'name': 'Local Market Dynamics',
                'description': 'Student accommodation supply/demand balance and market trends',
                'weight': 4,
                'guidelines': '''
                Assess existing and planned PBSA supply, student demand trends.
                Consider occupancy rates, rental growth, competitive landscape.
                ''',
                'criteria': {
                    '1': 'Oversupplied market with poor demand fundamentals',
                    '2': 'Challenging market conditions with supply concerns',
                    '3': 'Balanced market with adequate demand support',
                    '4': 'Favorable market with good demand/supply dynamics',
                    '5': 'Exceptional market with strong demand and limited supply'
                }
            },
            {
                'name': 'Transport & Connectivity',
                'description': 'Public transport links, accessibility, and connectivity to key amenities',
                'weight': 3,
                'guidelines': '''
                Evaluate public transport access, walking/cycling infrastructure.
                Consider connectivity to city center, amenities, entertainment districts.
                ''',
                'criteria': {
                    '1': 'Poor transport links with limited connectivity',
                    '2': 'Basic transport access with some limitations',
                    '3': 'Adequate transport connectivity meeting student needs',
                    '4': 'Good transport links with convenient access',
                    '5': 'Excellent connectivity with multiple transport options'
                }
            }
        ]
        
        # Site Characteristics
        site_metrics = [
            {
                'name': 'Site Size & Configuration',
                'description': 'Site area, shape, and suitability for PBSA development',
                'weight': 4,
                'guidelines': '''
                Assess site size relative to development plans, shape/configuration efficiency.
                Consider development constraints and optimization opportunities.
                ''',
                'criteria': {
                    '1': 'Inadequate or poorly configured site for intended development',
                    '2': 'Constrained site with limited development potential',
                    '3': 'Adequate site meeting basic development requirements',
                    '4': 'Good site with efficient development potential',
                    '5': 'Excellent site optimally configured for development'
                }
            },
            {
                'name': 'Planning & Regulatory Environment',
                'description': 'Planning permissions, regulatory framework, and approval risks',
                'weight': 4,
                'guidelines': '''
                Evaluate planning status, local planning policies, approval timeline/risks.
                Consider local authority attitudes and regulatory requirements.
                ''',
                'criteria': {
                    '1': 'Significant planning risks with uncertain approvals',
                    '2': 'Planning challenges requiring careful management',
                    '3': 'Manageable planning process with standard requirements',
                    '4': 'Favorable planning environment with good prospects',
                    '5': 'Excellent planning position with minimal approval risk'
                }
            },
            {
                'name': 'Development Constraints & Opportunities',
                'description': 'Physical constraints, environmental factors, and development opportunities',
                'weight': 3,
                'guidelines': '''
                Assess ground conditions, environmental constraints, infrastructure requirements.
                Consider development optimization opportunities and efficiency potential.
                ''',
                'criteria': {
                    '1': 'Significant constraints limiting development potential',
                    '2': 'Notable constraints requiring expensive mitigation',
                    '3': 'Manageable constraints with standard solutions',
                    '4': 'Minor constraints with good development potential',
                    '5': 'Minimal constraints with excellent development opportunity'
                }
            }
        ]
        
        # Economic Viability
        economic_metrics = [
            {
                'name': 'Construction & Development Costs',
                'description': 'Total development costs including construction, fees, and financing',
                'weight': 5,
                'guidelines': '''
                Evaluate construction cost estimates, professional fees, finance costs.
                Consider cost benchmarking, contingencies, and cost certainty.
                ''',
                'criteria': {
                    '1': 'High costs with poor viability and significant uncertainties',
                    '2': 'Elevated costs with viability concerns',
                    '3': 'Market-level costs with acceptable viability',
                    '4': 'Competitive costs with good viability margins',
                    '5': 'Excellent cost efficiency with strong viability'
                }
            },
            {
                'name': 'Revenue Potential & Pricing',
                'description': 'Rental levels, occupancy prospects, and revenue optimization',
                'weight': 5,
                'guidelines': '''
                Assess achievable rental levels, occupancy rates, revenue growth potential.
                Consider market positioning, amenities premium, ancillary revenue.
                ''',
                'criteria': {
                    '1': 'Poor revenue potential with weak pricing power',
                    '2': 'Limited revenue potential requiring aggressive pricing',
                    '3': 'Market-level revenue potential with standard positioning',
                    '4': 'Good revenue potential with pricing advantages',
                    '5': 'Excellent revenue potential with premium positioning'
                }
            },
            {
                'name': 'Investment Returns & Viability',
                'description': 'Expected returns, payback periods, and overall investment attractiveness',
                'weight': 4,
                'guidelines': '''
                Evaluate projected IRR, yield on cost, payback period.
                Consider sensitivity analysis and downside protection.
                ''',
                'criteria': {
                    '1': 'Poor returns below investment thresholds',
                    '2': 'Marginal returns with limited attractiveness',
                    '3': 'Adequate returns meeting basic requirements',
                    '4': 'Good returns with attractive investment profile',
                    '5': 'Excellent returns with compelling investment case'
                }
            }
        ]
        
        # Operational Considerations
        operational_metrics = [
            {
                'name': 'Design & Amenities',
                'description': 'Building design quality, student amenities, and competitive positioning',
                'weight': 4,
                'guidelines': '''
                Assess architectural design, room specifications, common areas, amenities.
                Consider competitive positioning and student appeal factors.
                ''',
                'criteria': {
                    '1': 'Poor design with limited amenities and weak positioning',
                    '2': 'Basic design meeting minimum student expectations',
                    '3': 'Adequate design with standard amenities package',
                    '4': 'Good design with attractive amenities and positioning',
                    '5': 'Excellent design with premium amenities and strong appeal'
                }
            },
            {
                'name': 'Operational Efficiency',
                'description': 'Management efficiency, operating cost optimization, and service delivery',
                'weight': 3,
                'guidelines': '''
                Evaluate building efficiency, maintenance requirements, operating cost structure.
                Consider management systems and service delivery capabilities.
                ''',
                'criteria': {
                    '1': 'Poor operational efficiency with high cost structure',
                    '2': 'Below-average efficiency requiring optimization',
                    '3': 'Standard operational efficiency meeting benchmarks',
                    '4': 'Good efficiency with optimized operations',
                    '5': 'Excellent efficiency with best-in-class operations'
                }
            },
            {
                'name': 'Technology & Innovation',
                'description': 'Technology integration, innovation features, and future-proofing',
                'weight': 2,
                'guidelines': '''
                Assess technology systems, smart building features, innovation elements.
                Consider future-proofing and competitive differentiation through technology.
                ''',
                'criteria': {
                    '1': 'Limited technology with outdated systems',
                    '2': 'Basic technology meeting minimum requirements',
                    '3': 'Standard technology package with essential features',
                    '4': 'Good technology integration with innovative features',
                    '5': 'Cutting-edge technology with significant innovation'
                }
            }
        ]
        
        # Risk Assessment
        scheme_risk_metrics = [
            {
                'name': 'Development Risk',
                'description': 'Construction, timing, and delivery risks specific to the scheme',
                'weight': 4,
                'guidelines': '''
                Assess construction risks, timeline risks, contractor capability.
                Consider complexity factors and risk mitigation measures.
                ''',
                'criteria': {
                    '1': 'High development risk with significant delivery concerns',
                    '2': 'Elevated development risk requiring careful management',
                    '3': 'Standard development risk with adequate mitigation',
                    '4': 'Low development risk with good delivery prospects',
                    '5': 'Minimal development risk with excellent delivery certainty'
                }
            },
            {
                'name': 'Market Risk',
                'description': 'Demand volatility, competition risk, and market cycle exposure',
                'weight': 3,
                'guidelines': '''
                Assess student demand stability, competitive threats, market cycle sensitivity.
                Consider diversification and risk mitigation strategies.
                ''',
                'criteria': {
                    '1': 'High market risk with volatile demand and strong competition',
                    '2': 'Elevated market risk requiring active management',
                    '3': 'Moderate market risk with manageable exposures',
                    '4': 'Low market risk with stable demand fundamentals',
                    '5': 'Minimal market risk with strong defensive characteristics'
                }
            },
            {
                'name': 'Financial & Liquidity Risk',
                'description': 'Financing risks, cash flow timing, and liquidity considerations',
                'weight': 3,
                'guidelines': '''
                Assess financing structure, cash flow profile, liquidity requirements.
                Consider refinancing risks and exit strategy options.
                ''',
                'criteria': {
                    '1': 'High financial risk with significant liquidity concerns',
                    '2': 'Elevated financial risk requiring careful management',
                    '3': 'Moderate financial risk with adequate liquidity',
                    '4': 'Low financial risk with good liquidity management',
                    '5': 'Minimal financial risk with excellent liquidity position'
                }
            }
        ]
        
        # Create all scheme metric templates
        scheme_metrics = [
            (MetricCategory.LOCATION, location_metrics),
            (MetricCategory.OPERATIONAL, site_metrics),
            (MetricCategory.ECONOMIC, economic_metrics),
            (MetricCategory.OPERATIONAL, operational_metrics),
            (MetricCategory.RISK, scheme_risk_metrics)
        ]
        
        display_order = 1
        for category, metrics in scheme_metrics:
            for metric_data in metrics:
                MetricTemplate.objects.create(
                    group=group,
                    template=template,
                    metric_name=metric_data['name'],
                    metric_description=metric_data['description'],
                    category=category,
                    default_weight=metric_data['weight'],
                    assessment_guidelines=metric_data['guidelines'],
                    scoring_criteria=metric_data['criteria'],
                    is_mandatory=True,
                    display_order=display_order
                )
                display_order += 1
        
        return template
    
    @staticmethod
    def get_template_summary(template: AssessmentTemplate) -> Dict[str, Any]:
        """Get comprehensive summary of template structure and scoring."""
        metrics = template.metric_templates.all()
        
        # Calculate maximum possible scores
        total_max_score = sum(5 * metric.default_weight for metric in metrics)
        
        # Category breakdowns
        category_summaries = {}
        for category in MetricCategory.choices:
            category_metrics = metrics.filter(category=category[0])
            if category_metrics.exists():
                category_max = sum(5 * m.default_weight for m in category_metrics)
                category_summaries[category[0]] = {
                    'name': category[1],
                    'metric_count': category_metrics.count(),
                    'max_possible_score': category_max,
                    'weight_percentage': round((category_max / total_max_score * 100), 1) if total_max_score > 0 else 0
                }
        
        return {
            'template_name': template.template_name,
            'assessment_type': template.get_assessment_type_display(),
            'total_metrics': metrics.count(),
            'max_possible_score': total_max_score,
            'category_breakdown': category_summaries,
            'decision_thresholds': {
                'premium_priority': f"> {165} points ({round(165/total_max_score*100, 1)}%)" if total_max_score > 0 else "N/A",
                'acceptable': f"125-165 points ({round(125/total_max_score*100, 1)}-{round(165/total_max_score*100, 1)}%)" if total_max_score > 0 else "N/A",
                'reject': f"< 125 points ({round(125/total_max_score*100, 1)}%)" if total_max_score > 0 else "N/A"
            }
        }