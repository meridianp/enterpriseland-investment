
from rest_framework import serializers
from platform_core.core.serializers import PlatformSerializer
from .models import (
    DevelopmentPartner, OfficeLocation, FinancialPartner, KeyShareholder,
    PBSAScheme, Assessment, FinancialInformation, CreditInformation,
    AssessmentMetric, FXRate, AssessmentAuditLog_Legacy
)

class OfficeLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfficeLocation
        fields = ['id', 'city', 'country']

class FinancialPartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialPartner
        fields = ['id', 'name', 'relationship_type']

class KeyShareholderSerializer(serializers.ModelSerializer):
    class Meta:
        model = KeyShareholder
        fields = ['id', 'name', 'ownership_percentage']

class DevelopmentPartnerSerializer(serializers.ModelSerializer):
    office_locations = OfficeLocationSerializer(many=True, read_only=True)
    financial_partners = FinancialPartnerSerializer(many=True, read_only=True)
    key_shareholders = KeyShareholderSerializer(many=True, read_only=True)
    pbsa_specialization_pct = serializers.ReadOnlyField()
    avg_pbsa_scheme_size = serializers.ReadOnlyField()
    
    class Meta:
        model = DevelopmentPartner
        fields = [
            'id', 'company_name', 'trading_name', 'headquarter_city',
            'headquarter_country', 'year_established', 'website_url',
            'size_of_development_team', 'number_of_employees',
            'completed_pbsa_schemes', 'schemes_in_development',
            'pbsa_schemes_in_development', 'completed_schemes_in_target_location',
            'years_of_pbsa_experience', 'total_pbsa_beds_delivered',
            'beds_in_development', 'shareholding_structure',
            'ultimate_parent_company', 'publicly_listed', 'stock_exchange',
            'office_locations', 'financial_partners', 'key_shareholders',
            'pbsa_specialization_pct', 'avg_pbsa_scheme_size',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class DevelopmentPartnerCreateSerializer(serializers.ModelSerializer):
    office_locations = OfficeLocationSerializer(many=True, required=False)
    financial_partners = FinancialPartnerSerializer(many=True, required=False)
    key_shareholders = KeyShareholderSerializer(many=True, required=False)
    
    class Meta:
        model = DevelopmentPartner
        fields = [
            'company_name', 'trading_name', 'headquarter_city',
            'headquarter_country', 'year_established', 'website_url',
            'size_of_development_team', 'number_of_employees',
            'completed_pbsa_schemes', 'schemes_in_development',
            'pbsa_schemes_in_development', 'completed_schemes_in_target_location',
            'years_of_pbsa_experience', 'total_pbsa_beds_delivered',
            'beds_in_development', 'shareholding_structure',
            'ultimate_parent_company', 'publicly_listed', 'stock_exchange',
            'office_locations', 'financial_partners', 'key_shareholders'
        ]
    
    def create(self, validated_data):
        office_locations_data = validated_data.pop('office_locations', [])
        financial_partners_data = validated_data.pop('financial_partners', [])
        key_shareholders_data = validated_data.pop('key_shareholders', [])
        
        # Get group from request context
        group = self.context['request'].user.groups.first()
        validated_data['group'] = group
        
        partner = DevelopmentPartner.objects.create(**validated_data)
        
        # Create related objects
        for location_data in office_locations_data:
            OfficeLocation.objects.create(partner=partner, **location_data)
        
        for partner_data in financial_partners_data:
            FinancialPartner.objects.create(partner=partner, **partner_data)
        
        for shareholder_data in key_shareholders_data:
            KeyShareholder.objects.create(partner=partner, **shareholder_data)
        
        return partner

class PBSASchemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PBSAScheme
        fields = [
            'id', 'scheme_name', 'location_city', 'location_country',
            'total_beds', 'site_area_value', 'site_area_unit',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class FinancialInformationSerializer(serializers.ModelSerializer):
    profit_margin_pct = serializers.ReadOnlyField()
    
    class Meta:
        model = FinancialInformation
        fields = [
            'id', 'net_assets_amount', 'net_assets_currency',
            'net_current_assets_amount', 'net_current_assets_currency',
            'net_profit_before_tax_amount', 'net_profit_before_tax_currency',
            'latest_annual_revenue_amount', 'latest_annual_revenue_currency',
            'ebitda_amount', 'ebitda_currency', 'financial_year_end_date',
            'profit_margin_pct'
        ]
        read_only_fields = ['id']

class CreditInformationSerializer(serializers.ModelSerializer):
    leverage_band = serializers.ReadOnlyField()
    liquidity_risk = serializers.ReadOnlyField()
    
    class Meta:
        model = CreditInformation
        fields = [
            'id', 'main_banking_relationship', 'amount_of_debt_amount',
            'amount_of_debt_currency', 'debt_to_total_assets_pct',
            'short_term_debt_pct', 'interest_coverage_ratio',
            'debt_service_coverage_ratio', 'credit_rating',
            'leverage_band', 'liquidity_risk'
        ]
        read_only_fields = ['id']

class AssessmentMetricSerializer(serializers.ModelSerializer):
    weighted_score = serializers.ReadOnlyField()
    
    class Meta:
        model = AssessmentMetric
        fields = ['id', 'metric_name', 'score', 'weight', 'justification', 'weighted_score']
        read_only_fields = ['id']

class AssessmentSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source='partner.company_name', read_only=True)
    scheme_name = serializers.CharField(source='scheme.scheme_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    semver = serializers.ReadOnlyField()
    
    financial_info = FinancialInformationSerializer(read_only=True)
    credit_info = CreditInformationSerializer(read_only=True)
    metrics = AssessmentMetricSerializer(many=True, read_only=True)
    
    class Meta:
        model = Assessment
        fields = [
            'id', 'assessment_type', 'partner', 'scheme', 'partner_name',
            'scheme_name', 'status', 'decision', 'total_score',
            'version_major', 'version_minor', 'version_patch', 'semver',
            'created_by', 'created_by_name', 'created_at',
            'updated_by', 'updated_by_name', 'updated_at',
            'approved_by', 'approved_by_name', 'approved_at',
            'financial_info', 'credit_info', 'metrics'
        ]
        read_only_fields = [
            'id', 'created_by', 'created_at', 'updated_by', 'updated_at',
            'approved_by', 'approved_at', 'semver'
        ]

class AssessmentCreateSerializer(serializers.ModelSerializer):
    financial_info = FinancialInformationSerializer(required=False)
    credit_info = CreditInformationSerializer(required=False)
    metrics = AssessmentMetricSerializer(many=True, required=False)
    
    class Meta:
        model = Assessment
        fields = [
            'assessment_type', 'partner', 'scheme', 'status',
            'financial_info', 'credit_info', 'metrics'
        ]
    
    def create(self, validated_data):
        financial_info_data = validated_data.pop('financial_info', None)
        credit_info_data = validated_data.pop('credit_info', None)
        metrics_data = validated_data.pop('metrics', [])
        
        # Get group and user from request context
        user = self.context['request'].user
        group = user.groups.first()
        
        validated_data['group'] = group
        validated_data['created_by'] = user
        
        assessment = Assessment.objects.create(**validated_data)
        
        # Create related objects
        if financial_info_data:
            FinancialInformation.objects.create(assessment=assessment, **financial_info_data)
        
        if credit_info_data:
            CreditInformation.objects.create(assessment=assessment, **credit_info_data)
        
        for metric_data in metrics_data:
            AssessmentMetric.objects.create(assessment=assessment, **metric_data)
        
        # Calculate total score
        total_score = sum(metric.weighted_score for metric in assessment.metrics.all())
        assessment.total_score = total_score
        assessment.save()
        
        return assessment

class AssessmentApprovalSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=Assessment._meta.get_field('decision').choices)
    comments = serializers.CharField(required=False, allow_blank=True)

class FXRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FXRate
        fields = ['id', 'base_currency', 'target_currency', 'rate', 'date', 'created_at']
        read_only_fields = ['id', 'created_at']

class AssessmentAuditLog_LegacySerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = AssessmentAuditLog_Legacy
        fields = [
            'id', 'user', 'user_email', 'table_name', 'record_id',
            'action', 'old_values', 'new_values', 'timestamp',
            'ip_address', 'user_agent'
        ]
        read_only_fields = ['id', 'timestamp']

class DashboardKPISerializer(serializers.Serializer):
    """Serializer for dashboard KPI data"""
    active_assessments = serializers.IntegerField()
    avg_risk_score = serializers.FloatField()
    high_risk_schemes = serializers.IntegerField()
    currency_exposure = serializers.DictField()
    turnaround_time_days = serializers.FloatField()
