"""
Market Analysis Service for PBSA investment analysis.

Provides comprehensive market analysis, competitive analysis, and investment
opportunity identification for Purpose-Built Student Accommodation.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime, date

from django.db.models import QuerySet, Count, Avg, Sum, Max, Min, Q
from django.utils import timezone
from django.contrib.gis.measure import Distance

from accounts.models import Group
from ..models import (
    PBSAMarketAnalysis, University, Neighborhood, PointOfInterest,
    MarketAnalysisNeighborhood, MarketAnalysisUniversity
)

logger = logging.getLogger(__name__)


class MarketAnalysisService:
    """
    Service for comprehensive PBSA market analysis and reporting.
    
    Provides market sizing, competitive analysis, opportunity identification,
    and investment recommendations.
    """
    
    def __init__(self, group: Group):
        """Initialize service for a specific group."""
        self.group = group
    
    def create_market_analysis(self, 
                             city: str,
                             country: str = 'GB',
                             version: str = '1.0') -> PBSAMarketAnalysis:
        """
        Create comprehensive market analysis for a city.
        
        Args:
            city: Target city name
            country: Country code (default: GB for UK)
            version: Analysis version
            
        Returns:
            Created PBSAMarketAnalysis instance
        """
        # Get universities in the city
        universities = University.objects.filter(
            group=self.group,
            main_campus__address__icontains=city
        )
        
        if not universities.exists():
            raise ValueError(f"No universities found for city: {city}")
        
        # Calculate market metrics
        market_data = self._calculate_market_metrics(universities)
        
        # Get neighborhoods in the area
        neighborhoods = self._get_city_neighborhoods(city, universities)
        
        # Create analysis
        analysis = PBSAMarketAnalysis.objects.create(
            group=self.group,
            city=city,
            country=country,
            version=version,
            total_student_population=market_data['total_students'],
            international_student_percentage=market_data['international_percentage'],
            existing_pbsa_beds=market_data['existing_beds'],
            estimated_demand=market_data['estimated_demand'],
            supply_demand_ratio=market_data['supply_demand_ratio'],
            average_rent_per_week=market_data['average_rent'],
            market_summary=self._generate_market_summary(city, market_data),
            key_trends=self._identify_market_trends(market_data, universities),
            opportunities=self._identify_opportunities(market_data, neighborhoods),
            risks=self._identify_risks(market_data, universities),
            methodology=self._get_methodology_description(),
            data_sources=self._get_data_sources()
        )
        
        # Add universities to analysis
        for university in universities:
            MarketAnalysisUniversity.objects.create(
                market_analysis=analysis,
                university=university
            )
        
        # Add top neighborhoods
        if neighborhoods.exists():
            ranked_neighborhoods = neighborhoods.order_by('-metrics__overall_score')
            for rank, neighborhood in enumerate(ranked_neighborhoods[:20], 1):
                MarketAnalysisNeighborhood.objects.create(
                    market_analysis=analysis,
                    neighborhood=neighborhood,
                    rank=rank
                )
        
        # Update calculated fields
        analysis.calculate_top_neighborhoods()
        
        return analysis
    
    def update_market_analysis(self, analysis: PBSAMarketAnalysis) -> PBSAMarketAnalysis:
        """
        Update existing market analysis with latest data.
        
        Args:
            analysis: Existing analysis to update
            
        Returns:
            Updated analysis
        """
        # Get current universities
        universities = University.objects.filter(
            market_analyses__market_analysis=analysis
        )
        
        # Recalculate metrics
        market_data = self._calculate_market_metrics(universities)
        
        # Update fields
        analysis.total_student_population = market_data['total_students']
        analysis.international_student_percentage = market_data['international_percentage']
        analysis.existing_pbsa_beds = market_data['existing_beds']
        analysis.estimated_demand = market_data['estimated_demand']
        analysis.supply_demand_ratio = market_data['supply_demand_ratio']
        analysis.average_rent_per_week = market_data['average_rent']
        analysis.analysis_date = timezone.now().date()
        
        # Update analysis content
        neighborhoods = Neighborhood.objects.filter(
            market_analyses__market_analysis=analysis
        )
        
        analysis.market_summary = self._generate_market_summary(analysis.city, market_data)
        analysis.key_trends = self._identify_market_trends(market_data, universities)
        analysis.opportunities = self._identify_opportunities(market_data, neighborhoods)
        analysis.risks = self._identify_risks(market_data, universities)
        
        analysis.save()
        analysis.calculate_top_neighborhoods()
        
        return analysis
    
    def compare_markets(self, analysis_ids: List[str]) -> Dict[str, Any]:
        """
        Compare multiple market analyses.
        
        Args:
            analysis_ids: List of analysis IDs to compare
            
        Returns:
            Comparative analysis data
        """
        analyses = PBSAMarketAnalysis.objects.filter(
            group=self.group,
            id__in=analysis_ids
        ).prefetch_related('universities__university')
        
        if len(analyses) < 2:
            raise ValueError("At least 2 market analyses required for comparison")
        
        comparison = {
            'markets': [],
            'comparative_metrics': {},
            'rankings': {},
            'recommendations': []
        }
        
        # Collect market data
        for analysis in analyses:
            market_data = {
                'id': str(analysis.id),
                'city': analysis.city,
                'country': analysis.country,
                'total_students': analysis.total_student_population,
                'international_percentage': analysis.international_student_percentage,
                'supply_demand_ratio': analysis.supply_demand_ratio,
                'average_rent': float(analysis.average_rent_per_week),
                'market_maturity': analysis.market_maturity,
                'supply_shortage': analysis.supply_shortage,
                'university_count': analysis.universities.count(),
                'top_neighborhood_score': 0.0
            }
            
            # Get top neighborhood score
            if analysis.neighborhoods.exists():
                top_neighborhood = analysis.neighborhoods.select_related(
                    'neighborhood__metrics'
                ).order_by('rank').first()
                if top_neighborhood:
                    market_data['top_neighborhood_score'] = top_neighborhood.neighborhood.metrics.overall_score
            
            comparison['markets'].append(market_data)
        
        # Calculate comparative metrics
        metrics = ['total_students', 'international_percentage', 'supply_demand_ratio', 
                  'average_rent', 'supply_shortage', 'top_neighborhood_score']
        
        for metric in metrics:
            values = [m[metric] for m in comparison['markets']]
            comparison['comparative_metrics'][metric] = {
                'min': min(values),
                'max': max(values),
                'average': sum(values) / len(values)
            }
        
        # Create rankings
        comparison['rankings'] = {
            'by_demand': sorted(comparison['markets'], key=lambda x: x['supply_shortage'], reverse=True),
            'by_student_population': sorted(comparison['markets'], key=lambda x: x['total_students'], reverse=True),
            'by_neighborhood_quality': sorted(comparison['markets'], key=lambda x: x['top_neighborhood_score'], reverse=True),
            'by_rent_potential': sorted(comparison['markets'], key=lambda x: x['average_rent'], reverse=True)
        }
        
        # Generate recommendations
        comparison['recommendations'] = self._generate_comparison_recommendations(comparison)
        
        return comparison
    
    def identify_expansion_opportunities(self, 
                                       current_city: str,
                                       radius_km: float = 100.0) -> List[Dict[str, Any]]:
        """
        Identify expansion opportunities near current market.
        
        Args:
            current_city: Current city with operations
            radius_km: Search radius for expansion
            
        Returns:
            List of expansion opportunities
        """
        # Get current market analysis
        current_analysis = PBSAMarketAnalysis.objects.filter(
            group=self.group,
            city__iexact=current_city,
            is_published=True
        ).first()
        
        if not current_analysis:
            raise ValueError(f"No published analysis found for {current_city}")
        
        # Get universities in expansion radius
        current_unis = current_analysis.universities.all()
        if not current_unis.exists():
            return []
        
        # Use first university as center point
        center_location = current_unis.first().university.main_campus.location
        
        # Find universities within radius that aren't in current analysis
        expansion_unis = University.objects.filter(
            group=self.group,
            main_campus__location__distance_lte=(center_location, Distance(km=radius_km))
        ).exclude(
            id__in=current_unis.values_list('university_id', flat=True)
        )
        
        opportunities = []
        
        # Group universities by city/area
        cities = {}
        for uni in expansion_unis:
            # Extract city from address (simplified)
            city_name = self._extract_city_from_address(uni.main_campus.address)
            if city_name not in cities:
                cities[city_name] = []
            cities[city_name].append(uni)
        
        # Analyze each potential market
        for city_name, universities in cities.items():
            if len(universities) < 1:  # Minimum threshold
                continue
                
            market_potential = self._assess_expansion_potential(
                city_name, universities, current_analysis
            )
            
            if market_potential['opportunity_score'] > 60:  # Threshold for viable opportunity
                opportunities.append(market_potential)
        
        # Sort by opportunity score
        opportunities.sort(key=lambda x: x['opportunity_score'], reverse=True)
        
        return opportunities[:10]  # Top 10 opportunities
    
    def _calculate_market_metrics(self, universities: QuerySet) -> Dict[str, Any]:
        """Calculate key market metrics from university data."""
        total_students = universities.aggregate(
            total=Sum('total_students')
        )['total'] or 0
        
        total_international = universities.aggregate(
            total=Sum('international_students')
        )['total'] or 0
        
        international_percentage = (total_international / total_students * 100) if total_students > 0 else 0
        
        # Estimate PBSA demand (30% of students need accommodation)
        estimated_demand = int(total_students * 0.3)
        
        # Estimate existing PBSA beds (from dormitory POIs)
        existing_beds = PointOfInterest.objects.filter(
            group=self.group,
            poi_type='dormitory'
        ).aggregate(
            total=Sum('capacity')
        )['total'] or 0
        
        # Calculate supply/demand ratio
        supply_demand_ratio = existing_beds / estimated_demand if estimated_demand > 0 else 0
        
        # Estimate average rent (placeholder - would come from market data)
        average_rent = Decimal('150.00')  # £150 per week baseline
        
        return {
            'total_students': total_students,
            'total_international': total_international,
            'international_percentage': round(international_percentage, 1),
            'estimated_demand': estimated_demand,
            'existing_beds': existing_beds,
            'supply_demand_ratio': round(supply_demand_ratio, 2),
            'average_rent': average_rent
        }
    
    def _get_city_neighborhoods(self, city: str, universities: QuerySet) -> QuerySet:
        """Get neighborhoods relevant to the city analysis."""
        # For now, get neighborhoods within 10km of any university
        neighborhood_ids = set()
        
        for university in universities:
            nearby_neighborhoods = Neighborhood.objects.filter(
                group=self.group,
                boundaries__distance_lte=(
                    university.main_campus.location,
                    Distance(km=10)
                )
            ).values_list('id', flat=True)
            
            neighborhood_ids.update(nearby_neighborhoods)
        
        return Neighborhood.objects.filter(id__in=neighborhood_ids)
    
    def _generate_market_summary(self, city: str, market_data: Dict) -> str:
        """Generate executive summary of the market."""
        summary = f"""
{city} PBSA Market Analysis Summary

Market Size: {market_data['total_students']:,} total students with {market_data['international_percentage']:.1f}% international students.

Supply/Demand: Current supply of {market_data['existing_beds']:,} beds against estimated demand of {market_data['estimated_demand']:,} beds (ratio: {market_data['supply_demand_ratio']:.2f}).

Market Opportunity: {'Undersupplied' if market_data['supply_demand_ratio'] < 0.8 else 'Balanced' if market_data['supply_demand_ratio'] < 1.2 else 'Oversupplied'} market with {'significant' if market_data['supply_demand_ratio'] < 0.6 else 'moderate' if market_data['supply_demand_ratio'] < 0.9 else 'limited'} investment potential.

Average Rent: £{market_data['average_rent']}/week provides competitive positioning in the market.
        """.strip()
        
        return summary
    
    def _identify_market_trends(self, market_data: Dict, universities: QuerySet) -> List[str]:
        """Identify key market trends."""
        trends = []
        
        if market_data['international_percentage'] > 25:
            trends.append("High international student population drives premium accommodation demand")
        
        if market_data['supply_demand_ratio'] < 0.7:
            trends.append("Significant supply shortage creates strong rental demand")
        
        # Check for university growth
        growing_unis = universities.filter(student_growth_rate__gt=2.0)
        if growing_unis.exists():
            trends.append("University expansion plans indicate growing student population")
        
        if market_data['total_students'] > 50000:
            trends.append("Large student population supports multiple PBSA developments")
        
        return trends
    
    def _identify_opportunities(self, market_data: Dict, neighborhoods: QuerySet) -> List[str]:
        """Identify investment opportunities."""
        opportunities = []
        
        if market_data['supply_demand_ratio'] < 0.8:
            shortage = market_data['estimated_demand'] - market_data['existing_beds']
            opportunities.append(f"Market shortage of {shortage:,} beds creates immediate opportunity")
        
        # Check for high-scoring neighborhoods
        high_scoring = neighborhoods.filter(metrics__overall_score__gte=80)
        if high_scoring.exists():
            opportunities.append(f"{high_scoring.count()} high-quality neighborhoods identified for development")
        
        if market_data['international_percentage'] > 20:
            opportunities.append("International student demand supports premium pricing strategy")
        
        return opportunities
    
    def _identify_risks(self, market_data: Dict, universities: QuerySet) -> List[str]:
        """Identify market risks."""
        risks = []
        
        if market_data['supply_demand_ratio'] > 1.2:
            risks.append("Market oversupply may pressure rents and occupancy rates")
        
        if universities.count() < 2:
            risks.append("Single university dependency creates concentration risk")
        
        # Check for declining universities
        declining_unis = universities.filter(student_growth_rate__lt=-2.0)
        if declining_unis.exists():
            risks.append("Some universities showing declining enrollment trends")
        
        return risks
    
    def _get_methodology_description(self) -> str:
        """Get standardized methodology description."""
        return """
This analysis employs a comprehensive methodology combining:
1. University enrollment data and growth projections
2. Geographic analysis of campus locations and neighborhoods
3. Supply analysis of existing PBSA and accommodation
4. Demand modeling based on student demographics
5. Competitive landscape assessment
6. Neighborhood scoring across 8 key metrics
7. Market trend analysis and risk assessment
        """.strip()
    
    def _get_data_sources(self) -> List[str]:
        """Get standardized data sources."""
        return [
            "University enrollment databases",
            "Geographic intelligence platform",
            "PBSA market surveys",
            "Student accommodation directories",
            "Planning and development records",
            "Commercial real estate databases"
        ]
    
    def _assess_expansion_potential(self, 
                                  city: str, 
                                  universities: List, 
                                  current_analysis: PBSAMarketAnalysis) -> Dict[str, Any]:
        """Assess expansion potential for a new city."""
        total_students = sum(uni.total_students for uni in universities)
        
        # Simple scoring model
        size_score = min(total_students / 10000 * 30, 30)  # Max 30 points for 10k+ students
        uni_count_score = min(len(universities) * 10, 20)   # Max 20 points for 2+ unis
        proximity_score = 25  # Base score for being in expansion radius
        
        # Competitive analysis
        existing_analyses = PBSAMarketAnalysis.objects.filter(
            group=self.group,
            city__iexact=city
        )
        competition_score = 25 if not existing_analyses.exists() else 10
        
        opportunity_score = size_score + uni_count_score + proximity_score + competition_score
        
        return {
            'city': city,
            'total_students': total_students,
            'university_count': len(universities),
            'opportunity_score': round(opportunity_score, 1),
            'universities': [uni.name for uni in universities],
            'rationale': f"Market with {total_students:,} students across {len(universities)} universities"
        }
    
    def _extract_city_from_address(self, address: str) -> str:
        """Extract city name from address (simplified)."""
        # Simple extraction - would be more sophisticated in production
        parts = address.split(',')
        if len(parts) >= 2:
            return parts[-2].strip()
        return address.split()[0]
    
    def _generate_comparison_recommendations(self, comparison: Dict) -> List[str]:
        """Generate recommendations from market comparison."""
        recommendations = []
        
        # Find best market by different criteria
        best_demand = comparison['rankings']['by_demand'][0]
        best_quality = comparison['rankings']['by_neighborhood_quality'][0]
        
        recommendations.append(
            f"Highest demand market: {best_demand['city']} with {best_demand['supply_shortage']:,} bed shortage"
        )
        
        recommendations.append(
            f"Best neighborhood quality: {best_quality['city']} with {best_quality['top_neighborhood_score']:.1f} score"
        )
        
        # Investment recommendations
        if best_demand['supply_shortage'] > 2000:
            recommendations.append(
                f"Consider priority investment in {best_demand['city']} due to significant supply shortage"
            )
        
        return recommendations