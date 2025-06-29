"""
Factory classes for generating test data for leads app models.
"""

import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from accounts.models import Group
# from market_intelligence.models import TargetCompany
# from market_intelligence.tests.factories import TargetCompanyFactory
from ..models import LeadScoringModel, Lead, LeadActivity

User = get_user_model()


class GroupFactory(DjangoModelFactory):
    """Factory for creating Group instances."""
    
    class Meta:
        model = Group
    
    name = factory.Sequence(lambda n: f"Test Group {n}")
    description = factory.Faker('text', max_nb_chars=200)


class TargetCompanyFactory(DjangoModelFactory):
    """Simple factory for creating TargetCompany instances."""
    
    class Meta:
        model = 'market_intelligence.TargetCompany'
    
    group = factory.SubFactory(GroupFactory)
    name = factory.Faker('company')
    domain = factory.Faker('url')
    sector = factory.Faker('bs')
    

class UserFactory(DjangoModelFactory):
    """Factory for creating User instances."""
    
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    role = User.Role.BUSINESS_ANALYST


class LeadScoringModelFactory(DjangoModelFactory):
    """Factory for creating LeadScoringModel instances."""
    
    class Meta:
        model = LeadScoringModel
    
    group = factory.SubFactory(GroupFactory)
    name = factory.Sequence(lambda n: f"Scoring Model {n}")
    description = factory.Faker('text', max_nb_chars=200)
    status = LeadScoringModel.ModelStatus.ACTIVE
    scoring_method = LeadScoringModel.ScoringMethod.WEIGHTED_AVERAGE
    version = "1.0.0"
    
    # Component weights for scoring
    component_weights = factory.LazyFunction(lambda: {
        'business_alignment': 0.25,
        'market_presence': 0.20,
        'financial_strength': 0.15,
        'strategic_fit': 0.15,
        'geographic_fit': 0.10,
        'engagement_potential': 0.10,
        'data_completeness': 0.05
    })
    
    # Thresholds
    qualification_threshold = 70.0
    high_priority_threshold = 85.0
    auto_convert_threshold = 95.0
    
    # Performance metrics
    accuracy_score = 0.85
    precision_score = 0.82
    recall_score = 0.78
    
    @factory.post_generation
    def set_active_model(obj, create, extracted, **kwargs):
        """Set model as active if requested."""
        if create and extracted:
            obj.activated_at = timezone.now()
            obj.save()


class LeadFactory(DjangoModelFactory):
    """Factory for creating Lead instances."""
    
    class Meta:
        model = Lead
    
    group = factory.SubFactory(GroupFactory)
    market_intelligence_target = factory.SubFactory(TargetCompanyFactory)
    scoring_model = factory.SubFactory(LeadScoringModelFactory)
    
    # Basic Information
    company_name = factory.Faker('company')
    trading_name = factory.Faker('company_suffix')
    
    # Lead details
    current_score = factory.Faker('pyfloat', min_value=0, max_value=100, right_digits=2)
    status = Lead.LeadStatus.NEW
    priority = Lead.Priority.MEDIUM
    
    # Contact information
    primary_contact_name = factory.Faker('name')
    primary_contact_email = factory.Faker('email')
    primary_contact_phone = factory.Faker('phone_number')
    primary_contact_title = factory.Faker('job')
    
    # Company details
    domain = factory.Faker('url')
    linkedin_url = factory.LazyAttribute(lambda obj: f"https://linkedin.com/company/{obj.company_name.lower().replace(' ', '-')}")
    headquarters_city = factory.Faker('city')
    headquarters_country = factory.Faker('country')
    
    # Lead management
    source = Lead.LeadSource.MARKET_INTELLIGENCE
    tags = factory.LazyFunction(lambda: ['pbsa', 'uk'])
    custom_fields = factory.LazyFunction(lambda: {})
    
    # Assignment
    assigned_to = factory.SubFactory(UserFactory)
    identified_by = factory.SubFactory(UserFactory)
    
    last_scored_at = factory.LazyFunction(timezone.now)
    
    @factory.post_generation
    def set_qualified_status(obj, create, extracted, **kwargs):
        """Automatically set status based on lead score."""
        if create:
            if obj.current_score >= 70:
                obj.status = Lead.LeadStatus.QUALIFIED
            elif obj.current_score >= 50:
                obj.status = Lead.LeadStatus.CONTACTED
            obj.save()


class LeadActivityFactory(DjangoModelFactory):
    """Factory for creating LeadActivity instances."""
    
    class Meta:
        model = LeadActivity
    
    lead = factory.SubFactory(LeadFactory)
    activity_type = LeadActivity.ActivityType.NOTE
    description = factory.Faker('text', max_nb_chars=200)
    created_by = factory.SubFactory(UserFactory)
    
    # Optional fields
    contact_method = None
    outcome = None
    scheduled_at = None
    completed_at = None
    
    @factory.post_generation
    def set_activity_details(obj, create, extracted, **kwargs):
        """Set activity-specific details based on type."""
        if create:
            if obj.activity_type == LeadActivity.ActivityType.EMAIL:
                obj.contact_method = 'email'
                obj.outcome = 'sent'
                obj.completed_at = timezone.now()
            elif obj.activity_type == LeadActivity.ActivityType.CALL:
                obj.contact_method = 'phone'
                obj.outcome = 'connected'
                obj.completed_at = timezone.now()
            elif obj.activity_type == LeadActivity.ActivityType.MEETING:
                obj.scheduled_at = timezone.now() + timedelta(days=3)
            obj.save()


class TestDataMixin:
    """Mixin to provide common test data setup."""
    
    def setUp(self):
        """Set up common test data."""
        # Create groups
        self.group1 = GroupFactory.create(name="Test Group 1")
        self.group2 = GroupFactory.create(name="Test Group 2")
        
        # Create users with different roles
        self.admin_user = UserFactory.create(
            username="admin",
            email="admin@test.com",
            role=User.Role.ADMIN
        )
        self.manager_user = UserFactory.create(
            username="manager",
            email="manager@test.com",
            role=User.Role.PORTFOLIO_MANAGER
        )
        self.analyst_user = UserFactory.create(
            username="analyst",
            email="analyst@test.com",
            role=User.Role.BUSINESS_ANALYST
        )
        self.viewer_user = UserFactory.create(
            username="viewer",
            email="viewer@test.com",
            role=User.Role.READ_ONLY
        )
        
        # Create default scoring model
        self.default_scoring_model = LeadScoringModelFactory.create(
            group=self.group1,
            name="Default Scoring Model",
            status=LeadScoringModel.ModelStatus.ACTIVE,
            is_default=True
        )


# Factory extensions for specific test scenarios
class QualifiedLeadFactory(LeadFactory):
    """Factory for creating qualified leads."""
    
    current_score = factory.Faker('pyfloat', min_value=70, max_value=100, right_digits=2)
    status = Lead.LeadStatus.QUALIFIED
    priority = Lead.Priority.HIGH
    
    @factory.post_generation
    def add_activities(obj, create, extracted, **kwargs):
        """Add multiple activities to simulate engagement."""
        if create:
            # Add initial contact
            LeadActivityFactory.create(
                lead=obj,
                activity_type=LeadActivity.ActivityType.EMAIL,
                description="Initial outreach email sent",
                created_by=obj.assigned_to
            )
            # Add follow-up call
            LeadActivityFactory.create(
                lead=obj,
                activity_type=LeadActivity.ActivityType.CALL,
                description="Follow-up call - positive response",
                created_by=obj.assigned_to
            )


class ConvertedLeadFactory(LeadFactory):
    """Factory for creating converted leads."""
    
    current_score = factory.Faker('pyfloat', min_value=80, max_value=100, right_digits=2)
    status = Lead.LeadStatus.CONVERTED
    priority = Lead.Priority.HIGH
    converted_at = factory.LazyFunction(timezone.now)
    estimated_deal_value = factory.Faker('pydecimal', left_digits=7, right_digits=2, positive=True)
    
    @factory.post_generation
    def add_conversion_activity(obj, create, extracted, **kwargs):
        """Add conversion activity."""
        if create:
            LeadActivityFactory.create(
                lead=obj,
                activity_type=LeadActivity.ActivityType.STATUS_CHANGE,
                description=f"Lead converted with value £{obj.estimated_deal_value}",
                created_by=obj.assigned_to
            )


class UnqualifiedLeadFactory(LeadFactory):
    """Factory for creating unqualified leads."""
    
    current_score = factory.Faker('pyfloat', min_value=0, max_value=30, right_digits=2)
    status = Lead.LeadStatus.REJECTED
    priority = Lead.Priority.LOW
    
    @factory.post_generation
    def add_disqualification_activity(obj, create, extracted, **kwargs):
        """Add disqualification activity."""
        if create:
            LeadActivityFactory.create(
                lead=obj,
                activity_type=LeadActivity.ActivityType.STATUS_CHANGE,
                description="Lead marked as unqualified - score too low",
                created_by=obj.assigned_to
            )