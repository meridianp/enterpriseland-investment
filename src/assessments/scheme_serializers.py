"""
API serializers for PBSA Scheme Models.

Provides comprehensive serialization for schemes, locations, economics,
operations, and related functionality with proper validation and nested relationships.
"""

from decimal import Decimal
from typing import Dict, Any, Optional

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction

from .scheme_models import (
    PBSAScheme, SchemeLocationInformation, TargetUniversity,
    SchemeSiteInformation, UniversityType, DevelopmentStage,
    AccommodationType, PlanningStatus
)
from .scheme_economic_models import (
    SchemeEconomicInformation, AccommodationUnit, SchemeOperationalInformation
)
from .partner_models import DevelopmentPartner
from .enums import Currency, RiskLevel, AreaUnit

User = get_user_model()


class TargetUniversitySerializer(serializers.ModelSerializer):
    """Serializer for target universities with calculated fields."""
    
    university_type_display = serializers.CharField(
        source='get_university_type_display', 
        read_only=True
    )
    proximity_score = serializers.IntegerField(read_only=True)
    market_attractiveness = serializers.FloatField(read_only=True)
    
    class Meta:
        model = TargetUniversity
        fields = [
            'id', 'university_name', 'university_type', 'university_type_display',
            'distance_to_campus_km', 'walking_time_minutes', 'cycling_time_minutes',
            'public_transport_time_minutes', 'total_student_population',
            'international_student_pct', 'postgraduate_student_pct',
            'university_provided_beds', 'accommodation_satisfaction_rating',
            'target_student_segment', 'estimated_demand_capture_pct',
            'proximity_score', 'market_attractiveness',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate university data."""
        if data.get('distance_to_campus_km', 0) < 0:
            raise serializers.ValidationError("Distance cannot be negative")
        
        if data.get('international_student_pct') is not None:
            if not 0 <= data['international_student_pct'] <= 100:
                raise serializers.ValidationError(
                    "International student percentage must be between 0 and 100"
                )
        
        if data.get('postgraduate_student_pct') is not None:
            if not 0 <= data['postgraduate_student_pct'] <= 100:
                raise serializers.ValidationError(
                    "Postgraduate student percentage must be between 0 and 100"
                )
        
        return data


class SchemeLocationInformationSerializer(serializers.ModelSerializer):
    """Serializer for scheme location information with nested universities."""
    
    country_display = serializers.SerializerMethodField()
    location_type_display = serializers.CharField(
        source='get_location_type_display',
        read_only=True
    )
    coordinates = serializers.SerializerMethodField()
    transport_accessibility_score = serializers.IntegerField(read_only=True)
    target_universities = TargetUniversitySerializer(many=True, read_only=True)
    
    class Meta:
        model = SchemeLocationInformation
        fields = [
            'id', 'address', 'city', 'region', 'country', 'country_display',
            'postcode', 'latitude', 'longitude', 'coordinates',
            'location_type', 'location_type_display',
            'nearest_train_station', 'train_station_distance_km',
            'airport_proximity', 'public_transport_rating',
            'local_market_description', 'competitive_schemes_nearby',
            'total_student_population', 'transport_accessibility_score',
            'target_universities', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_country_display(self, obj):
        """Get country name from ISO code."""
        # In a real implementation, you'd have a country code mapping
        # For now, return the code
        return obj.country
    
    def get_coordinates(self, obj):
        """Get coordinates as a GeoJSON point."""
        if obj.coordinates:
            return {
                'type': 'Point',
                'coordinates': [obj.coordinates.x, obj.coordinates.y]
            }
        return None
    
    def validate(self, data):
        """Validate location data."""
        if data.get('latitude') is not None:
            if not -90 <= data['latitude'] <= 90:
                raise serializers.ValidationError("Latitude must be between -90 and 90")
        
        if data.get('longitude') is not None:
            if not -180 <= data['longitude'] <= 180:
                raise serializers.ValidationError("Longitude must be between -180 and 180")
        
        if data.get('public_transport_rating') is not None:
            if not 1 <= data['public_transport_rating'] <= 5:
                raise serializers.ValidationError(
                    "Public transport rating must be between 1 and 5"
                )
        
        return data


class SchemeSiteInformationSerializer(serializers.ModelSerializer):
    """Serializer for scheme site information with calculated fields."""
    
    site_area_unit_display = serializers.CharField(
        source='get_site_area_unit_display',
        read_only=True
    )
    site_configuration_display = serializers.CharField(
        source='get_site_configuration_display',
        read_only=True
    )
    topography_display = serializers.CharField(
        source='get_topography_display',
        read_only=True
    )
    ground_conditions_display = serializers.CharField(
        source='get_ground_conditions_display',
        read_only=True
    )
    contamination_risk_display = serializers.CharField(
        source='get_contamination_risk_display',
        read_only=True
    )
    flood_risk_display = serializers.CharField(
        source='get_flood_risk_display',
        read_only=True
    )
    planning_status_display = serializers.CharField(
        source='get_planning_status_display',
        read_only=True
    )
    
    # Calculated fields
    site_area_sq_m = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        read_only=True
    )
    beds_per_hectare = serializers.DecimalField(
        max_digits=10,
        decimal_places=1,
        read_only=True
    )
    development_feasibility_score = serializers.IntegerField(read_only=True)
    planning_risk_assessment = serializers.DictField(read_only=True)
    
    class Meta:
        model = SchemeSiteInformation
        fields = [
            'id', 'site_area_value', 'site_area_unit', 'site_area_unit_display',
            'site_area_sq_m', 'site_configuration', 'site_configuration_display',
            'plot_ratio', 'building_coverage_pct', 'max_height_stories',
            'topography', 'topography_display', 'ground_conditions',
            'ground_conditions_display', 'contamination_risk', 'contamination_risk_display',
            'flood_risk', 'flood_risk_display', 'planning_status',
            'planning_status_display', 'planning_reference',
            'planning_submission_date', 'planning_decision_date',
            'planning_conditions', 'utilities_available',
            'infrastructure_upgrades_required', 'development_constraints',
            'design_opportunities', 'environmental_considerations',
            'beds_per_hectare', 'development_feasibility_score',
            'planning_risk_assessment', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate site information data."""
        if data.get('plot_ratio') is not None and data['plot_ratio'] < 0:
            raise serializers.ValidationError("Plot ratio cannot be negative")
        
        if data.get('building_coverage_pct') is not None:
            if not 0 <= data['building_coverage_pct'] <= 100:
                raise serializers.ValidationError(
                    "Building coverage must be between 0 and 100%"
                )
        
        return data


class SchemeEconomicInformationSerializer(serializers.ModelSerializer):
    """Serializer for scheme economic information with calculated fields."""
    
    # Currency displays
    land_cost_currency_display = serializers.CharField(
        source='get_land_cost_currency_display',
        read_only=True
    )
    construction_cost_currency_display = serializers.CharField(
        source='get_construction_cost_currency_display',
        read_only=True
    )
    rent_currency_display = serializers.CharField(
        source='get_rent_currency_display',
        read_only=True
    )
    
    # Calculated financial metrics
    total_development_cost = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        read_only=True
    )
    cost_per_bed = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        read_only=True
    )
    gross_annual_rental_income = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        read_only=True
    )
    total_annual_income = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        read_only=True
    )
    total_annual_operating_costs = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        read_only=True
    )
    net_annual_income = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        read_only=True
    )
    estimated_gross_yield_pct = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        read_only=True
    )
    estimated_net_yield_pct = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        read_only=True
    )
    rent_vs_market_analysis = serializers.DictField(read_only=True)
    investment_viability_score = serializers.DictField(read_only=True)
    
    class Meta:
        model = SchemeEconomicInformation
        fields = [
            'id', 'land_cost_amount', 'land_cost_currency', 'land_cost_currency_display',
            'construction_cost_amount', 'construction_cost_currency',
            'construction_cost_currency_display', 'professional_fees_amount',
            'professional_fees_currency', 'finance_costs_amount',
            'finance_costs_currency', 'contingency_amount', 'contingency_currency',
            'total_development_cost', 'cost_per_bed',
            'avg_rent_per_bed_per_week', 'rent_currency', 'rent_currency_display',
            'occupancy_rate_pct', 'rental_growth_rate_pct',
            'ancillary_income_per_bed_per_year', 'operating_cost_per_bed_per_year',
            'management_fee_pct', 'maintenance_cost_per_bed_per_year',
            'target_gross_yield_pct', 'target_net_yield_pct', 'projected_irr_pct',
            'exit_cap_rate_pct', 'market_rent_per_bed_per_week',
            'rent_premium_discount_pct', 'financial_year_end_month',
            'gross_annual_rental_income', 'total_annual_income',
            'total_annual_operating_costs', 'net_annual_income',
            'estimated_gross_yield_pct', 'estimated_net_yield_pct',
            'rent_vs_market_analysis', 'investment_viability_score',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate economic data."""
        # Validate percentage fields
        percentage_fields = [
            'occupancy_rate_pct', 'management_fee_pct',
            'target_gross_yield_pct', 'target_net_yield_pct',
            'exit_cap_rate_pct'
        ]
        
        for field in percentage_fields:
            if data.get(field) is not None:
                if field in ['occupancy_rate_pct'] and not 0 <= data[field] <= 100:
                    raise serializers.ValidationError(
                        f"{field} must be between 0 and 100"
                    )
                elif field in ['management_fee_pct'] and not 0 <= data[field] <= 50:
                    raise serializers.ValidationError(
                        f"{field} must be between 0 and 50"
                    )
        
        # Validate financial year end month
        if data.get('financial_year_end_month') is not None:
            if not 1 <= data['financial_year_end_month'] <= 12:
                raise serializers.ValidationError(
                    "Financial year end month must be between 1 and 12"
                )
        
        return data


class AccommodationUnitSerializer(serializers.ModelSerializer):
    """Serializer for accommodation units with calculated fields."""
    
    unit_type_display = serializers.CharField(
        source='get_unit_type_display',
        read_only=True
    )
    kitchen_type_display = serializers.CharField(
        source='get_kitchen_type_display',
        read_only=True
    )
    furnishing_level_display = serializers.CharField(
        source='get_furnishing_level_display',
        read_only=True
    )
    rent_currency_display = serializers.CharField(
        source='get_rent_currency_display',
        read_only=True
    )
    
    # Calculated fields
    total_beds_for_unit_type = serializers.IntegerField(read_only=True)
    area_per_bed_sqm = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        read_only=True
    )
    annual_revenue_per_unit = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        read_only=True
    )
    total_annual_revenue_for_unit_type = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        read_only=True
    )
    rent_premium_vs_competition_pct = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        read_only=True
    )
    unit_efficiency_score = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = AccommodationUnit
        fields = [
            'id', 'unit_type', 'unit_type_display', 'unit_name',
            'bed_count', 'bathroom_count', 'gross_floor_area_sqm',
            'bedroom_size_sqm', 'has_kitchen', 'kitchen_type',
            'kitchen_type_display', 'has_study_space', 'has_storage',
            'furnishing_level', 'furnishing_level_display',
            'number_of_units', 'rent_per_bed_per_week',
            'rent_currency', 'rent_currency_display',
            'target_market_segment', 'competitive_rent_per_week',
            'total_beds_for_unit_type', 'area_per_bed_sqm',
            'annual_revenue_per_unit', 'total_annual_revenue_for_unit_type',
            'rent_premium_vs_competition_pct', 'unit_efficiency_score',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate accommodation unit data."""
        if data.get('bed_count', 0) <= 0:
            raise serializers.ValidationError("Bed count must be positive")
        
        if data.get('bathroom_count', 0) <= 0:
            raise serializers.ValidationError("Bathroom count must be positive")
        
        if data.get('number_of_units', 0) <= 0:
            raise serializers.ValidationError("Number of units must be positive")
        
        return data


class SchemeOperationalInformationSerializer(serializers.ModelSerializer):
    """Serializer for scheme operational information with calculated fields."""
    
    management_model_display = serializers.CharField(
        source='get_management_model_display',
        read_only=True
    )
    security_type_display = serializers.CharField(
        source='get_security_type_display',
        read_only=True
    )
    cleaning_service_display = serializers.CharField(
        source='get_cleaning_service_display',
        read_only=True
    )
    laundry_facilities_display = serializers.CharField(
        source='get_laundry_facilities_display',
        read_only=True
    )
    internet_provision_display = serializers.CharField(
        source='get_internet_provision_display',
        read_only=True
    )
    
    # Calculated scores
    amenity_score = serializers.IntegerField(read_only=True)
    operational_efficiency_score = serializers.IntegerField(read_only=True)
    operational_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = SchemeOperationalInformation
        fields = [
            'id', 'management_model', 'management_model_display',
            'management_company', 'on_site_staff_count',
            'has_24_7_reception', 'has_security', 'security_type',
            'security_type_display', 'cleaning_service',
            'cleaning_service_display', 'laundry_facilities',
            'laundry_facilities_display', 'internet_provision',
            'internet_provision_display', 'has_gym', 'has_study_rooms',
            'has_social_spaces', 'has_cinema_room', 'has_outdoor_space',
            'smart_building_features', 'mobile_app_features',
            'sustainability_features', 'target_occupancy_rate_pct',
            'average_lease_length_months', 'student_satisfaction_target',
            'estimated_operating_cost_per_bed', 'utilities_included_in_rent',
            'amenity_score', 'operational_efficiency_score',
            'operational_summary', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_operational_summary(self, obj):
        """Get operational summary."""
        return obj.get_operational_summary()
    
    def validate(self, data):
        """Validate operational data."""
        if data.get('target_occupancy_rate_pct') is not None:
            if not 50 <= data['target_occupancy_rate_pct'] <= 100:
                raise serializers.ValidationError(
                    "Target occupancy rate must be between 50 and 100%"
                )
        
        if data.get('student_satisfaction_target') is not None:
            if not 1 <= data['student_satisfaction_target'] <= 5:
                raise serializers.ValidationError(
                    "Student satisfaction target must be between 1 and 5"
                )
        
        return data


class PBSASchemeSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for PBSA scheme summaries and lists."""
    
    development_stage_display = serializers.CharField(
        source='get_development_stage_display',
        read_only=True
    )
    developer_name = serializers.CharField(
        source='developer.company_name',
        read_only=True
    )
    assessment_priority_display = serializers.CharField(
        source='get_assessment_priority_display',
        read_only=True
    )
    
    # Quick access to key metrics
    city = serializers.CharField(
        source='location_info.city',
        read_only=True
    )
    country = serializers.CharField(
        source='location_info.country',
        read_only=True
    )
    university_count = serializers.IntegerField(
        source='_university_count',
        read_only=True
    )
    average_rent_per_bed = serializers.DecimalField(
        source='_average_rent_per_bed',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    
    # Calculated fields
    cost_per_bed = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        read_only=True
    )
    development_timeline_months = serializers.IntegerField(read_only=True)
    beds_per_unit = serializers.FloatField(read_only=True)
    
    class Meta:
        model = PBSAScheme
        fields = [
            'id', 'scheme_name', 'scheme_reference', 'development_stage',
            'development_stage_display', 'developer', 'developer_name',
            'total_beds', 'total_units', 'expected_completion_date',
            'construction_start_date', 'operational_start_date',
            'total_development_cost_amount', 'total_development_cost_currency',
            'is_active', 'assessment_priority', 'assessment_priority_display',
            'city', 'country', 'university_count', 'average_rent_per_bed',
            'cost_per_bed', 'development_timeline_months', 'beds_per_unit',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PBSASchemeDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for full PBSA scheme information."""
    
    development_stage_display = serializers.CharField(
        source='get_development_stage_display',
        read_only=True
    )
    total_development_cost_currency_display = serializers.CharField(
        source='get_total_development_cost_currency_display',
        read_only=True
    )
    estimated_gcd_currency_display = serializers.CharField(
        source='get_estimated_gcd_currency_display',
        read_only=True
    )
    assessment_priority_display = serializers.CharField(
        source='get_assessment_priority_display',
        read_only=True
    )
    
    # Developer information
    developer_details = serializers.SerializerMethodField()
    
    # Nested relationships
    location_info = SchemeLocationInformationSerializer(read_only=True)
    site_info = SchemeSiteInformationSerializer(read_only=True)
    economic_info = SchemeEconomicInformationSerializer(read_only=True)
    operational_info = SchemeOperationalInformationSerializer(read_only=True)
    accommodation_units = AccommodationUnitSerializer(many=True, read_only=True)
    
    # Calculated fields
    cost_per_bed = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        read_only=True
    )
    development_timeline_months = serializers.IntegerField(read_only=True)
    beds_per_unit = serializers.FloatField(read_only=True)
    scheme_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = PBSAScheme
        fields = [
            'id', 'scheme_name', 'scheme_reference', 'development_stage',
            'development_stage_display', 'developer', 'developer_details',
            'total_beds', 'total_units', 'expected_completion_date',
            'construction_start_date', 'operational_start_date',
            'total_development_cost_amount', 'total_development_cost_currency',
            'total_development_cost_currency_display', 'estimated_gcd_amount',
            'estimated_gcd_currency', 'estimated_gcd_currency_display',
            'is_active', 'assessment_priority', 'assessment_priority_display',
            'cost_per_bed', 'development_timeline_months', 'beds_per_unit',
            'location_info', 'site_info', 'economic_info', 'operational_info',
            'accommodation_units', 'scheme_summary',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_developer_details(self, obj):
        """Get developer summary information."""
        if not obj.developer:
            return None
        
        developer = obj.developer
        return {
            'id': developer.id,
            'company_name': developer.company_name,
            'headquarter_city': getattr(
                developer.general_info, 'headquarter_city', ''
            ) if hasattr(developer, 'general_info') else '',
            'headquarter_country': getattr(
                developer.general_info, 'headquarter_country', ''
            ) if hasattr(developer, 'general_info') else '',
            'pbsa_experience': getattr(
                developer.operational_info, 'years_of_pbsa_experience', None
            ) if hasattr(developer, 'operational_info') else None,
            'completed_schemes': getattr(
                developer.operational_info, 'completed_pbsa_schemes', None
            ) if hasattr(developer, 'operational_info') else None
        }
    
    def get_scheme_summary(self, obj):
        """Get comprehensive scheme summary."""
        return obj.get_scheme_summary()


class PBSASchemeCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating PBSA schemes."""
    
    class Meta:
        model = PBSAScheme
        fields = [
            'scheme_name', 'scheme_reference', 'development_stage',
            'developer', 'total_beds', 'total_units',
            'expected_completion_date', 'construction_start_date',
            'operational_start_date', 'total_development_cost_amount',
            'total_development_cost_currency', 'estimated_gcd_amount',
            'estimated_gcd_currency', 'is_active', 'assessment_priority'
        ]
    
    def validate(self, data):
        """Validate scheme data."""
        # Validate dates
        if (data.get('construction_start_date') and 
            data.get('expected_completion_date')):
            if data['construction_start_date'] > data['expected_completion_date']:
                raise serializers.ValidationError(
                    "Construction start date cannot be after completion date"
                )
        
        if (data.get('expected_completion_date') and 
            data.get('operational_start_date')):
            if data['expected_completion_date'] > data['operational_start_date']:
                raise serializers.ValidationError(
                    "Completion date cannot be after operational start date"
                )
        
        # Validate beds and units
        if data.get('total_beds', 0) <= 0:
            raise serializers.ValidationError("Total beds must be positive")
        
        if data.get('total_units') is not None and data['total_units'] <= 0:
            raise serializers.ValidationError("Total units must be positive")
        
        # Validate units don't exceed beds
        if (data.get('total_units') is not None and 
            data.get('total_beds') is not None):
            if data['total_units'] > data['total_beds']:
                raise serializers.ValidationError(
                    "Total units cannot exceed total beds"
                )
        
        return data


class SchemeLocationCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating scheme location information."""
    
    target_universities = TargetUniversitySerializer(many=True, required=False)
    
    class Meta:
        model = SchemeLocationInformation
        fields = [
            'address', 'city', 'region', 'country', 'postcode',
            'latitude', 'longitude', 'location_type',
            'nearest_train_station', 'train_station_distance_km',
            'airport_proximity', 'public_transport_rating',
            'local_market_description', 'competitive_schemes_nearby',
            'total_student_population', 'target_universities'
        ]
    
    def create(self, validated_data):
        """Create location information with nested universities."""
        universities_data = validated_data.pop('target_universities', [])
        location_info = super().create(validated_data)
        
        for university_data in universities_data:
            TargetUniversity.objects.create(
                location_info=location_info,
                **university_data
            )
        
        return location_info
    
    def update(self, instance, validated_data):
        """Update location information with nested universities."""
        universities_data = validated_data.pop('target_universities', None)
        
        # Update location info
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update universities if provided
        if universities_data is not None:
            # Clear existing universities
            instance.target_universities.all().delete()
            
            # Create new universities
            for university_data in universities_data:
                TargetUniversity.objects.create(
                    location_info=instance,
                    **university_data
                )
        
        return instance


class AccommodationUnitBulkSerializer(serializers.Serializer):
    """Serializer for bulk operations on accommodation units."""
    
    units = AccommodationUnitSerializer(many=True)
    
    def validate_units(self, value):
        """Validate that unit names are unique within the scheme."""
        unit_names = [unit['unit_name'] for unit in value]
        if len(unit_names) != len(set(unit_names)):
            raise serializers.ValidationError(
                "Unit names must be unique within the scheme"
            )
        return value
    
    def create(self, validated_data):
        """Bulk create accommodation units."""
        units_data = validated_data['units']
        scheme = self.context['scheme']
        
        created_units = []
        with transaction.atomic():
            for unit_data in units_data:
                unit = AccommodationUnit.objects.create(
                    scheme=scheme,
                    **unit_data
                )
                created_units.append(unit)
        
        return created_units


class SchemeAnalyticsSerializer(serializers.Serializer):
    """Serializer for scheme analytics and reporting."""
    
    date_from = serializers.DateField(
        required=False,
        help_text="Start date for analytics period"
    )
    
    date_to = serializers.DateField(
        required=False,
        help_text="End date for analytics period"
    )
    
    development_stage = serializers.ChoiceField(
        choices=DevelopmentStage.choices,
        required=False,
        help_text="Filter by development stage"
    )
    
    min_beds = serializers.IntegerField(
        required=False,
        help_text="Minimum number of beds"
    )
    
    max_beds = serializers.IntegerField(
        required=False,
        help_text="Maximum number of beds"
    )
    
    country = serializers.CharField(
        max_length=2,
        required=False,
        help_text="Filter by country (ISO code)"
    )
    
    group_by = serializers.ChoiceField(
        choices=['month', 'quarter', 'stage', 'country', 'developer'],
        required=False,
        help_text="Group analytics by dimension"
    )


class SchemeComparisonSerializer(serializers.Serializer):
    """Serializer for comparing multiple schemes."""
    
    scheme_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=2,
        max_length=10,
        help_text="List of scheme IDs to compare (2-10 schemes)"
    )
    
    comparison_metrics = serializers.MultipleChoiceField(
        choices=[
            'financial', 'location', 'operational',
            'market_position', 'development_timeline'
        ],
        default=['financial', 'location', 'operational'],
        help_text="Metrics to include in comparison"
    )