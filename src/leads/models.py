"""
Lead Management Models.

Provides models for managing the lead lifecycle from market intelligence
through qualification, scoring, and conversion to development partners.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import Point
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import transaction

from assessments.base_models import UUIDModel, TimestampedModel, PlatformModel

User = get_user_model()


class LeadScoringModel(UUIDModel, TimestampedModel, PlatformModel):
    """
    Advanced lead scoring model with configurable weights and thresholds.
    
    Supports multiple scoring methodologies and provides audit trail
    for scoring decisions and model performance tracking.
    """
    
    class ScoringMethod(models.TextChoices):
        WEIGHTED_AVERAGE = 'weighted_average', 'Weighted Average'
        NEURAL_NETWORK = 'neural_network', 'Neural Network'
        ENSEMBLE = 'ensemble', 'Ensemble Method'
        CUSTOM = 'custom', 'Custom Algorithm'
    
    class ModelStatus(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ACTIVE = 'active', 'Active'
        ARCHIVED = 'archived', 'Archived'
        TESTING = 'testing', 'Testing'
    
    name = models.CharField(
        max_length=255,
        help_text="Name of the scoring model"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of scoring methodology and use case"
    )
    
    # Model Configuration
    scoring_method = models.CharField(
        max_length=50,
        choices=ScoringMethod.choices,
        default=ScoringMethod.WEIGHTED_AVERAGE,
        help_text="Primary scoring methodology"
    )
    
    status = models.CharField(
        max_length=50,
        choices=ModelStatus.choices,
        default=ModelStatus.DRAFT,
        help_text="Current status of the scoring model"
    )
    
    # Scoring Components and Weights
    component_weights = models.JSONField(
        default=dict,
        help_text="Component weights for scoring calculation"
    )
    
    # Thresholds for Lead Qualification
    qualification_threshold = models.FloatField(
        default=70.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Minimum score for lead qualification"
    )
    
    high_priority_threshold = models.FloatField(
        default=85.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Score threshold for high priority leads"
    )
    
    auto_convert_threshold = models.FloatField(
        default=95.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Score threshold for automatic conversion"
    )
    
    # Model Performance Tracking
    accuracy_score = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Model accuracy based on historical performance"
    )
    
    precision_score = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Model precision for qualified leads"
    )
    
    recall_score = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Model recall for qualified leads"
    )
    
    # Metadata
    version = models.CharField(
        max_length=20,
        default='1.0.0',
        help_text="Model version for tracking changes"
    )
    
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default scoring model"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_scoring_models',
        help_text="User who created this scoring model"
    )
    
    activated_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the model was activated"
    )
    
    deactivated_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the model was deactivated"
    )
    
    class Meta:
        db_table = 'leads_scoring_model'
        ordering = ['-created_at']
        unique_together = [['group', 'name', 'version']]
        indexes = [
            models.Index(fields=['group', 'status', 'is_default']),
            models.Index(fields=['scoring_method', 'status']),
            models.Index(fields=['qualification_threshold', 'is_default']),
        ]
    
    def __str__(self):
        return f"{self.name} v{self.version} ({self.get_scoring_method_display()})"
    
    @property
    def is_active(self):
        """Check if scoring model is currently active."""
        return self.status == self.ModelStatus.ACTIVE
    
    @property
    def f1_score(self):
        """Calculate F1 score from precision and recall."""
        if self.precision_score and self.recall_score:
            return 2 * (self.precision_score * self.recall_score) / (self.precision_score + self.recall_score)
        return None
    
    def get_default_weights(self):
        """Get default component weights for scoring with enhanced geographic intelligence."""
        return {
            'business_alignment': 0.22,
            'market_presence': 0.18,
            'financial_strength': 0.15,
            'strategic_fit': 0.15,
            'geographic_fit': 0.20,  # Increased weight for geographic intelligence
            'engagement_potential': 0.08,
            'data_completeness': 0.02
        }
    
    def activate(self, user=None):
        """Activate this scoring model."""
        with transaction.atomic():
            # Deactivate other models in the same group
            LeadScoringModel.objects.filter(
                group=self.group,
                status=self.ModelStatus.ACTIVE
            ).update(
                status=self.ModelStatus.ARCHIVED,
                deactivated_at=timezone.now()
            )
            
            # Activate this model
            self.status = self.ModelStatus.ACTIVE
            self.activated_at = timezone.now()
            self.save()
    
    def calculate_score(self, lead_data):
        """Calculate score for a lead using this model."""
        if not self.is_active:
            raise ValueError("Cannot score with inactive model")
        
        # Get weights, fallback to defaults if not configured
        weights = self.component_weights or self.get_default_weights()
        
        if self.scoring_method == self.ScoringMethod.WEIGHTED_AVERAGE:
            return self._weighted_average_score(lead_data, weights)
        elif self.scoring_method == self.ScoringMethod.NEURAL_NETWORK:
            return self._neural_network_score(lead_data)
        elif self.scoring_method == self.ScoringMethod.ENSEMBLE:
            return self._ensemble_score(lead_data, weights)
        else:
            return self._custom_score(lead_data, weights)
    
    def _weighted_average_score(self, lead_data, weights):
        """Calculate weighted average score."""
        total_score = 0.0
        total_weight = 0.0
        
        for component, weight in weights.items():
            if component in lead_data:
                score = float(lead_data[component])
                total_score += score * weight
                total_weight += weight
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    def _neural_network_score(self, lead_data):
        """Placeholder for neural network scoring."""
        # This would integrate with a trained ML model
        return self._weighted_average_score(lead_data, self.get_default_weights())
    
    def _ensemble_score(self, lead_data, weights):
        """Calculate ensemble score combining multiple methods."""
        weighted_score = self._weighted_average_score(lead_data, weights)
        # Add other scoring methods and ensemble them
        return weighted_score
    
    def _custom_score(self, lead_data, weights):
        """Placeholder for custom scoring logic."""
        return self._weighted_average_score(lead_data, weights)


class Lead(UUIDModel, TimestampedModel, PlatformModel):
    """
    Lead model representing a potential investment target in various stages
    of the qualification and conversion process.
    """
    
    class LeadStatus(models.TextChoices):
        NEW = 'new', 'New'
        QUALIFIED = 'qualified', 'Qualified'
        CONTACTED = 'contacted', 'Contacted'
        MEETING_SCHEDULED = 'meeting_scheduled', 'Meeting Scheduled'
        PROPOSAL_SENT = 'proposal_sent', 'Proposal Sent'
        NEGOTIATING = 'negotiating', 'Negotiating'
        CONVERTED = 'converted', 'Converted'
        LOST = 'lost', 'Lost'
        NURTURING = 'nurturing', 'Nurturing'
        REJECTED = 'rejected', 'Rejected'
    
    class LeadSource(models.TextChoices):
        MARKET_INTELLIGENCE = 'market_intelligence', 'Market Intelligence'
        REFERRAL = 'referral', 'Referral'
        DIRECT_INQUIRY = 'direct_inquiry', 'Direct Inquiry'
        CONFERENCE = 'conference', 'Conference'
        COLD_OUTREACH = 'cold_outreach', 'Cold Outreach'
        WEBSITE = 'website', 'Website'
        PARTNER_NETWORK = 'partner_network', 'Partner Network'
        OTHER = 'other', 'Other'
    
    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'
    
    # Basic Information
    company_name = models.CharField(
        max_length=255,
        help_text="Name of the target company"
    )
    
    trading_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Trading or brand name if different from company name"
    )
    
    # Contact Information
    primary_contact_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name of primary contact person"
    )
    
    primary_contact_email = models.EmailField(
        blank=True,
        help_text="Email of primary contact"
    )
    
    primary_contact_phone = models.CharField(
        max_length=50,
        blank=True,
        help_text="Phone number of primary contact"
    )
    
    primary_contact_title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Job title of primary contact"
    )
    
    # Company Details
    domain = models.URLField(
        blank=True,
        help_text="Company website URL"
    )
    
    linkedin_url = models.URLField(
        blank=True,
        help_text="Company LinkedIn profile"
    )
    
    headquarters_city = models.CharField(
        max_length=255,
        blank=True,
        help_text="City where company is headquartered"
    )
    
    headquarters_country = models.CharField(
        max_length=100,
        blank=True,
        help_text="Country where company is headquartered"
    )
    
    # Lead Management
    status = models.CharField(
        max_length=50,
        choices=LeadStatus.choices,
        default=LeadStatus.NEW,
        help_text="Current status in the lead lifecycle"
    )
    
    source = models.CharField(
        max_length=50,
        choices=LeadSource.choices,
        default=LeadSource.MARKET_INTELLIGENCE,
        help_text="How this lead was identified"
    )
    
    priority = models.CharField(
        max_length=50,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        help_text="Priority level for follow-up"
    )
    
    # Scoring and Qualification
    current_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Current lead score"
    )
    
    scoring_model = models.ForeignKey(
        LeadScoringModel,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='scored_leads',
        help_text="Scoring model used for this lead"
    )
    
    last_scored_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the lead was last scored"
    )
    
    qualification_notes = models.TextField(
        blank=True,
        help_text="Notes about lead qualification"
    )
    
    # Assignment and Ownership
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_leads',
        help_text="User responsible for this lead"
    )
    
    identified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='identified_leads',
        help_text="User who identified this lead"
    )
    
    # Source Integration
    market_intelligence_target = models.ForeignKey(
        'market_intelligence.TargetCompany',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='leads',
        help_text="Associated market intelligence target"
    )
    
    # Geographic Intelligence Integration
    headquarters_location = gis_models.PointField(
        srid=4326,
        null=True, blank=True,
        help_text="Geographic coordinates of company headquarters"
    )
    
    target_neighborhood = models.ForeignKey(
        'geographic_intelligence.Neighborhood',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='leads',
        help_text="Target neighborhood for investment focus"
    )
    
    target_universities = models.ManyToManyField(
        'geographic_intelligence.University',
        blank=True,
        related_name='target_leads',
        help_text="Universities in target market area"
    )
    
    # Geographic Scoring Components
    geographic_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Geographic intelligence score based on location analysis"
    )
    
    accessibility_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Transport and infrastructure accessibility score"
    )
    
    university_proximity_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Proximity to target universities score"
    )
    
    market_demand_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Local market demand and student population score"
    )
    
    competition_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Competitive landscape score (higher = less competition)"
    )
    
    geographic_analysis_date = models.DateTimeField(
        null=True, blank=True,
        help_text="When geographic analysis was last performed"
    )
    
    # Conversion Tracking
    converted_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the lead was converted to a partner"
    )
    
    converted_to_partner = models.ForeignKey(
        'assessments.DevelopmentPartner',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='source_leads',
        help_text="Development partner created from this lead"
    )
    
    # Metadata
    tags = models.JSONField(
        default=list,
        help_text="Tags for categorizing and filtering leads"
    )
    
    custom_fields = models.JSONField(
        default=dict,
        help_text="Custom fields for additional lead data"
    )
    
    # Lead Value Estimation
    estimated_deal_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True, blank=True,
        help_text="Estimated value of potential partnership"
    )
    
    estimated_timeline_months = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
        help_text="Estimated months to conversion"
    )
    
    class Meta:
        db_table = 'leads_lead'
        ordering = ['-current_score', '-created_at']
        unique_together = [['group', 'company_name']]
        indexes = [
            models.Index(fields=['group', 'status', 'priority']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['source', 'created_at']),
            models.Index(fields=['current_score', 'status']),
            models.Index(fields=['last_scored_at', 'scoring_model']),
        ]
    
    def __str__(self):
        return f"{self.company_name} ({self.get_status_display()})"
    
    @property
    def is_qualified(self):
        """Check if lead meets qualification threshold."""
        if self.scoring_model:
            return self.current_score >= self.scoring_model.qualification_threshold
        return self.current_score >= 70.0  # Default threshold
    
    @property
    def is_high_priority(self):
        """Check if lead meets high priority threshold."""
        if self.scoring_model:
            return self.current_score >= self.scoring_model.high_priority_threshold
        return self.current_score >= 85.0  # Default threshold
    
    @property
    def days_in_pipeline(self):
        """Calculate days since lead was created."""
        return (timezone.now().date() - self.created_at.date()).days
    
    @property
    def is_stale(self):
        """Check if lead has been in pipeline too long without activity."""
        return self.days_in_pipeline > 30 and not self.activities.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=14)
        ).exists()
    
    def get_latest_activity(self):
        """Get the most recent activity for this lead."""
        return self.activities.order_by('-created_at').first()
    
    def calculate_score(self, scoring_model=None):
        """Calculate and update lead score using specified or default model."""
        model = scoring_model or self.scoring_model
        if not model:
            # Get default scoring model for this group
            model = LeadScoringModel.objects.filter(
                group=self.group,
                is_default=True,
                status=LeadScoringModel.ModelStatus.ACTIVE
            ).first()
        
        if not model:
            return self.current_score
        
        # Prepare lead data for scoring
        lead_data = self._prepare_scoring_data()
        
        # Calculate score using model
        new_score = model.calculate_score(lead_data)
        
        # Update lead with new score
        self.current_score = min(max(new_score, 0.0), 100.0)
        self.scoring_model = model
        self.last_scored_at = timezone.now()
        self.save(update_fields=['current_score', 'scoring_model', 'last_scored_at'])
        
        return self.current_score
    
    def _prepare_scoring_data(self):
        """Prepare lead data for scoring calculation."""
        # This would extract relevant features for scoring
        return {
            'business_alignment': self._score_business_alignment(),
            'market_presence': self._score_market_presence(),
            'financial_strength': self._score_financial_strength(),
            'strategic_fit': self._score_strategic_fit(),
            'geographic_fit': self._score_geographic_fit(),
            'engagement_potential': self._score_engagement_potential(),
            'data_completeness': self._score_data_completeness()
        }
    
    def _score_business_alignment(self):
        """Score business model alignment."""
        # Placeholder scoring logic
        score = 50.0
        
        # Add points based on custom fields or market intelligence data
        if self.market_intelligence_target:
            target = self.market_intelligence_target
            if 'pbsa' in target.focus_sectors:
                score += 30.0
            if target.business_model in ['developer', 'investor']:
                score += 20.0
        
        return min(score, 100.0)
    
    def _score_market_presence(self):
        """Score market presence and visibility."""
        score = 0.0
        
        if self.domain:
            score += 15.0
        if self.linkedin_url:
            score += 15.0
        if self.market_intelligence_target and self.market_intelligence_target.source_articles.exists():
            score += 20.0
        
        return min(score + 50.0, 100.0)  # Base score + bonuses
    
    def _score_financial_strength(self):
        """Score financial strength indicators."""
        # Placeholder - would integrate with financial data sources
        return 60.0
    
    def _score_strategic_fit(self):
        """Score strategic fit with investment criteria."""
        # Placeholder - would evaluate against investment strategy
        return 65.0
    
    def _score_geographic_fit(self):
        """Score geographic alignment using geographic intelligence."""
        # Use stored geographic score if available and recent
        if (self.geographic_score > 0 and self.geographic_analysis_date and 
            (timezone.now() - self.geographic_analysis_date).days < 30):
            return self.geographic_score
        
        # Calculate new geographic score
        return self.update_geographic_scores()
    
    def _score_engagement_potential(self):
        """Score likelihood of successful engagement."""
        score = 50.0
        
        if self.primary_contact_email:
            score += 20.0
        if self.primary_contact_name:
            score += 15.0
        if self.status in [self.LeadStatus.CONTACTED, self.LeadStatus.MEETING_SCHEDULED]:
            score += 15.0
        
        return min(score, 100.0)
    
    def _score_data_completeness(self):
        """Score data completeness."""
        total_fields = 10
        filled_fields = 0
        
        fields_to_check = [
            'company_name', 'domain', 'headquarters_city', 'headquarters_country',
            'primary_contact_name', 'primary_contact_email', 'primary_contact_title',
            'linkedin_url', 'trading_name', 'qualification_notes'
        ]
        
        for field in fields_to_check:
            if getattr(self, field):
                filled_fields += 1
        
        return (filled_fields / total_fields) * 100.0
    
    def update_geographic_scores(self):
        """Update geographic intelligence scores for this lead."""
        if not self.headquarters_location:
            # Try to get coordinates from city/country
            coordinates = self._get_coordinates_from_address()
            if coordinates:
                self.headquarters_location = Point(coordinates[1], coordinates[0], srid=4326)
                self.save(update_fields=['headquarters_location'])
        
        if not self.headquarters_location:
            # Default geographic score for unknown locations
            self.geographic_score = 40.0
            return 40.0
        
        # Import geographic intelligence service
        from geographic_intelligence.services import GeographicIntelligenceService
        
        try:
            service = GeographicIntelligenceService(group=self.group)
            
            # Analyze location
            analysis = service.analyze_location(
                lat=self.headquarters_location.y,
                lng=self.headquarters_location.x,
                radius_km=10.0
            )
            
            # Update individual scores
            self.accessibility_score = analysis.get('accessibility_score', 0.0)
            self.university_proximity_score = self._calculate_university_proximity_score(analysis)
            self.market_demand_score = self._calculate_market_demand_score(analysis)
            self.competition_score = self._calculate_competition_score(analysis)
            
            # Calculate overall geographic score
            self.geographic_score = self._calculate_overall_geographic_score()
            self.geographic_analysis_date = timezone.now()
            
            # Auto-assign target neighborhood if not set
            if not self.target_neighborhood and analysis.get('neighborhoods', {}).get('best_neighborhood'):
                self._assign_best_neighborhood(analysis)
            
            # Save updated scores
            self.save(update_fields=[
                'geographic_score', 'accessibility_score', 'university_proximity_score',
                'market_demand_score', 'competition_score', 'geographic_analysis_date',
                'target_neighborhood'
            ])
            
            return self.geographic_score
            
        except Exception as e:
            # Log error and return basic geographic score
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Geographic scoring failed for lead {self.id}: {str(e)}")
            
            # Basic scoring based on country
            if self.headquarters_country == 'GB':
                self.geographic_score = 70.0
            elif self.headquarters_country in ['IE', 'NL', 'DE', 'FR']:
                self.geographic_score = 50.0
            else:
                self.geographic_score = 30.0
            
            return self.geographic_score
    
    def _calculate_university_proximity_score(self, analysis):
        """Calculate university proximity score from location analysis."""
        universities = analysis.get('universities', {})
        
        if universities.get('count', 0) == 0:
            return 0.0
        
        # Score based on number and quality of nearby universities
        score = min(universities['count'] * 15, 60)  # Max 60 for university count
        
        # Bonus for large student populations
        total_students = universities.get('total_students_in_area', 0)
        if total_students > 50000:
            score += 25
        elif total_students > 20000:
            score += 15
        elif total_students > 10000:
            score += 10
        
        # Bonus for close proximity
        avg_distance = universities.get('average_distance_km', 10)
        if avg_distance <= 2:
            score += 15
        elif avg_distance <= 5:
            score += 10
        
        return min(score, 100.0)
    
    def _calculate_market_demand_score(self, analysis):
        """Calculate market demand score based on student population and supply."""
        universities = analysis.get('universities', {})
        total_students = universities.get('total_students_in_area', 0)
        
        if total_students == 0:
            return 0.0
        
        # Base score from student population
        if total_students > 100000:
            score = 80.0
        elif total_students > 50000:
            score = 65.0
        elif total_students > 20000:
            score = 50.0
        elif total_students > 10000:
            score = 35.0
        else:
            score = 20.0
        
        # Adjust for international students (higher demand)
        international_students = universities.get('total_international_students', 0)
        if total_students > 0:
            intl_percentage = (international_students / total_students) * 100
            if intl_percentage > 30:
                score += 15
            elif intl_percentage > 20:
                score += 10
            elif intl_percentage > 10:
                score += 5
        
        return min(score, 100.0)
    
    def _calculate_competition_score(self, analysis):
        """Calculate competition score (higher = less competition)."""
        pois = analysis.get('pois', {}).get('by_type', {})
        dormitory_count = pois.get('dormitory', {}).get('count', 0)
        
        # Higher dormitory count = more competition = lower score
        if dormitory_count == 0:
            return 100.0
        elif dormitory_count <= 2:
            return 80.0
        elif dormitory_count <= 5:
            return 60.0
        elif dormitory_count <= 10:
            return 40.0
        else:
            return 20.0
    
    def _calculate_overall_geographic_score(self):
        """Calculate weighted overall geographic score."""
        weights = {
            'accessibility': 0.25,
            'university_proximity': 0.35,
            'market_demand': 0.25,
            'competition': 0.15
        }
        
        total_score = (
            self.accessibility_score * weights['accessibility'] +
            self.university_proximity_score * weights['university_proximity'] +
            self.market_demand_score * weights['market_demand'] +
            self.competition_score * weights['competition']
        )
        
        return round(total_score, 1)
    
    def _assign_best_neighborhood(self, analysis):
        """Assign the best neighborhood from analysis."""
        neighborhoods = analysis.get('neighborhoods', {}).get('neighborhoods', [])
        if neighborhoods:
            best_neighborhood = neighborhoods[0]  # Already sorted by score
            
            # Try to find the neighborhood in our database
            from geographic_intelligence.models import Neighborhood
            try:
                neighborhood = Neighborhood.objects.get(
                    group=self.group,
                    name=best_neighborhood['name']
                )
                self.target_neighborhood = neighborhood
            except Neighborhood.DoesNotExist:
                pass
    
    def _get_coordinates_from_address(self):
        """Get coordinates from city/country information."""
        if not self.headquarters_city:
            return None
        
        # Simple lookup for major UK cities
        uk_cities = {
            'london': (51.5074, -0.1278),
            'birmingham': (52.4862, -1.8904),
            'manchester': (53.4808, -2.2426),
            'glasgow': (55.8642, -4.2518),
            'edinburgh': (55.9533, -3.1883),
            'liverpool': (53.4084, -2.9916),
            'leeds': (53.8008, -1.5491),
            'sheffield': (53.3811, -1.4701),
            'bristol': (51.4545, -2.5879),
            'nottingham': (52.9548, -1.1581),
            'leicester': (52.6369, -1.1398),
            'coventry': (52.4068, -1.5197),
            'cardiff': (51.4816, -3.1791),
            'belfast': (54.5973, -5.9301),
            'oxford': (51.7520, -1.2577),
            'cambridge': (52.2053, 0.1218),
            'bath': (51.3758, -2.3599),
            'durham': (54.7753, -1.5849),
            'exeter': (50.7184, -3.5339),
            'york': (53.9600, -1.0873),
            'newcastle': (54.9783, -1.6178),
            'southampton': (50.9097, -1.4044),
            'brighton': (50.8225, -0.1372)
        }
        
        city_lower = self.headquarters_city.lower().strip()
        return uk_cities.get(city_lower)
    
    def get_nearby_universities(self, radius_km=10):
        """Get universities near this lead's location."""
        if not self.headquarters_location:
            return []
        
        from geographic_intelligence.models import University
        from django.contrib.gis.measure import Distance
        
        return University.objects.filter(
            group=self.group,
            main_campus__location__distance_lte=(self.headquarters_location, Distance(km=radius_km))
        ).select_related('main_campus')
    
    def get_geographic_summary(self):
        """Get a summary of geographic intelligence for this lead."""
        if not self.headquarters_location:
            return {
                'status': 'no_location',
                'message': 'No geographic coordinates available'
            }
        
        return {
            'status': 'analyzed',
            'location': {
                'lat': self.headquarters_location.y,
                'lng': self.headquarters_location.x,
                'city': self.headquarters_city,
                'country': self.headquarters_country
            },
            'scores': {
                'overall_geographic': self.geographic_score,
                'accessibility': self.accessibility_score,
                'university_proximity': self.university_proximity_score,
                'market_demand': self.market_demand_score,
                'competition': self.competition_score
            },
            'target_neighborhood': self.target_neighborhood.name if self.target_neighborhood else None,
            'nearby_universities': [
                {'name': uni.name, 'students': uni.total_students}
                for uni in self.get_nearby_universities()[:5]
            ],
            'last_analyzed': self.geographic_analysis_date.isoformat() if self.geographic_analysis_date else None
        }


class LeadActivity(UUIDModel, TimestampedModel, PlatformModel):
    """
    Activity tracking for lead interactions and workflow progression.
    """
    
    class ActivityType(models.TextChoices):
        NOTE = 'note', 'Note'
        EMAIL_SENT = 'email_sent', 'Email Sent'
        EMAIL_RECEIVED = 'email_received', 'Email Received'
        PHONE_CALL = 'phone_call', 'Phone Call'
        MEETING = 'meeting', 'Meeting'
        PROPOSAL_SENT = 'proposal_sent', 'Proposal Sent'
        CONTRACT_SENT = 'contract_sent', 'Contract Sent'
        FOLLOW_UP = 'follow_up', 'Follow-up'
        STATUS_CHANGE = 'status_change', 'Status Change'
        SCORE_UPDATE = 'score_update', 'Score Update'
        DOCUMENT_SHARED = 'document_shared', 'Document Shared'
        TASK_COMPLETED = 'task_completed', 'Task Completed'
        SYSTEM_UPDATE = 'system_update', 'System Update'
    
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='activities',
        help_text="Lead this activity is associated with"
    )
    
    activity_type = models.CharField(
        max_length=50,
        choices=ActivityType.choices,
        help_text="Type of activity"
    )
    
    title = models.CharField(
        max_length=255,
        help_text="Brief title of the activity"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Detailed description of the activity"
    )
    
    # Activity Metadata
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='lead_activities',
        help_text="User who performed this activity"
    )
    
    activity_date = models.DateTimeField(
        default=timezone.now,
        help_text="When the activity occurred"
    )
    
    # Outcome Tracking
    outcome = models.CharField(
        max_length=255,
        blank=True,
        help_text="Outcome or result of the activity"
    )
    
    next_action = models.CharField(
        max_length=255,
        blank=True,
        help_text="Recommended next action"
    )
    
    next_action_date = models.DateTimeField(
        null=True, blank=True,
        help_text="When next action should be taken"
    )
    
    # Integration Fields
    email_message_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Email message ID for email activities"
    )
    
    document_ids = models.JSONField(
        default=list,
        help_text="IDs of documents associated with this activity"
    )
    
    external_reference = models.CharField(
        max_length=255,
        blank=True,
        help_text="External system reference ID"
    )
    
    # Activity Data
    activity_data = models.JSONField(
        default=dict,
        help_text="Additional structured data for the activity"
    )
    
    # Internal Fields
    is_milestone = models.BooleanField(
        default=False,
        help_text="Whether this activity represents a milestone"
    )
    
    is_automated = models.BooleanField(
        default=False,
        help_text="Whether this activity was automated"
    )
    
    class Meta:
        db_table = 'leads_activity'
        ordering = ['-activity_date', '-created_at']
        indexes = [
            models.Index(fields=['lead', 'activity_type', 'activity_date']),
            models.Index(fields=['performed_by', 'activity_date']),
            models.Index(fields=['activity_type', 'is_milestone']),
            models.Index(fields=['next_action_date', 'lead']),
        ]
        verbose_name_plural = 'Lead Activities'
    
    def __str__(self):
        return f"{self.get_activity_type_display()}: {self.title}"
    
    @property
    def is_overdue(self):
        """Check if next action is overdue."""
        if self.next_action_date:
            return timezone.now() > self.next_action_date
        return False
    
    @property
    def days_until_next_action(self):
        """Calculate days until next action is due."""
        if self.next_action_date:
            delta = self.next_action_date.date() - timezone.now().date()
            return delta.days
        return None