"""
Comprehensive tests for leads serializers.

Tests all serializer functionality including validation, field representation,
and nested relationships.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import Group
from market_intelligence.models import TargetCompany
from ..models import LeadScoringModel, Lead, LeadActivity
from ..serializers import (
    LeadScoringModelSerializer, LeadSerializer, LeadActivitySerializer,
    LeadCreateSerializer, LeadUpdateSerializer, LeadSummarySerializer,
    LeadAnalyticsSerializer, BatchScoringResultSerializer
)
from .factories import (
    LeadScoringModelFactory, LeadFactory, LeadActivityFactory,
    TargetCompanyFactory, UserFactory, TestDataMixin
)


class LeadScoringModelSerializerTest(TestCase, TestDataMixin):
    """Test LeadScoringModelSerializer functionality."""
    
    def setUp(self):
        super().setUp()
        self.serializer_class = LeadScoringModelSerializer
    
    def test_serialize_lead_scoring_model(self):
        """Test serializing a lead scoring model."""
        model = LeadScoringModelFactory.create(
            group=self.group1,
            name="Test Scoring Model",
            version="1.0.0",
            is_active=True
        )
        
        serializer = self.serializer_class(model)
        data = serializer.data
        
        self.assertEqual(data['name'], "Test Scoring Model")
        self.assertEqual(data['version'], "1.0.0")
        self.assertTrue(data['is_active'])
        self.assertIn('scoring_criteria', data)
        self.assertIn('thresholds', data)
        self.assertIn('performance_metrics', data)
        self.assertIn('created_at', data)
    
    def test_deserialize_lead_scoring_model(self):
        """Test deserializing lead scoring model data."""
        data = {
            'name': 'New Scoring Model',
            'description': 'Test description',
            'model_type': LeadScoringModel.ModelType.RULES_BASED,
            'version': '1.0.0',
            'scoring_criteria': {
                'criterion1': {'weight': 0.5, 'max_score': 100},
                'criterion2': {'weight': 0.5, 'max_score': 100}
            },
            'thresholds': {
                'qualified': 70,
                'potential': 50,
                'unqualified': 30
            }
        }
        
        serializer = self.serializer_class(data=data)
        self.assertTrue(serializer.is_valid())
        
        model = serializer.save(group=self.group1)
        self.assertEqual(model.name, 'New Scoring Model')
        self.assertEqual(model.group, self.group1)
        self.assertEqual(model.scoring_criteria, data['scoring_criteria'])
    
    def test_validate_scoring_criteria(self):
        """Test validation of scoring criteria."""
        # Valid criteria
        data = {
            'name': 'Model',
            'model_type': LeadScoringModel.ModelType.RULES_BASED,
            'scoring_criteria': {
                'criterion1': {'weight': 0.6, 'max_score': 100},
                'criterion2': {'weight': 0.4, 'max_score': 100}
            }
        }
        
        serializer = self.serializer_class(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Invalid criteria - weights don't sum to 1
        data['scoring_criteria'] = {
            'criterion1': {'weight': 0.6, 'max_score': 100},
            'criterion2': {'weight': 0.6, 'max_score': 100}
        }
        
        serializer = self.serializer_class(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('scoring_criteria', serializer.errors)
    
    def test_validate_thresholds(self):
        """Test validation of thresholds."""
        # Valid thresholds
        data = {
            'name': 'Model',
            'model_type': LeadScoringModel.ModelType.RULES_BASED,
            'thresholds': {
                'qualified': 70,
                'potential': 50,
                'unqualified': 30
            }
        }
        
        serializer = self.serializer_class(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Invalid thresholds - not in descending order
        data['thresholds'] = {
            'qualified': 50,
            'potential': 70,
            'unqualified': 30
        }
        
        serializer = self.serializer_class(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('thresholds', serializer.errors)
    
    def test_read_only_fields(self):
        """Test that read-only fields are not writable."""
        model = LeadScoringModelFactory.create(group=self.group1)
        
        data = {
            'name': 'Updated Name',
            'created_at': timezone.now(),  # Should be read-only
            'updated_at': timezone.now(),  # Should be read-only
            'last_evaluated': timezone.now()  # Should be read-only
        }
        
        serializer = self.serializer_class(model, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        
        updated_model = serializer.save()
        self.assertEqual(updated_model.name, 'Updated Name')
        # Read-only fields should not change
        self.assertEqual(updated_model.created_at, model.created_at)


class LeadSerializerTest(TestCase, TestDataMixin):
    """Test LeadSerializer functionality."""
    
    def setUp(self):
        super().setUp()
        self.target = TargetCompanyFactory.create(
            group=self.group1,
            company_name="Test Company"
        )
        self.scoring_model = LeadScoringModelFactory.create(group=self.group1)
    
    def test_serialize_lead(self):
        """Test serializing a lead."""
        lead = LeadFactory.create(
            group=self.group1,
            target_company=self.target,
            scoring_model=self.scoring_model,
            lead_score=75.5,
            status=Lead.LeadStatus.QUALIFIED
        )
        
        serializer = LeadSerializer(lead)
        data = serializer.data
        
        self.assertEqual(data['id'], str(lead.id))
        self.assertEqual(data['lead_score'], 75.5)
        self.assertEqual(data['status'], Lead.LeadStatus.QUALIFIED)
        self.assertIn('target_company', data)
        self.assertIn('scoring_model', data)
        self.assertIn('contact_name', data)
        self.assertIn('is_qualified', data)
        self.assertIn('is_converted', data)
    
    def test_deserialize_lead_create(self):
        """Test creating a lead through serializer."""
        data = {
            'target_company': str(self.target.id),
            'scoring_model': str(self.scoring_model.id),
            'contact_name': 'John Doe',
            'contact_email': 'john@example.com',
            'contact_phone': '+44 20 1234 5678',
            'contact_title': 'CEO',
            'source': Lead.LeadSource.MARKET_INTELLIGENCE,
            'tags': ['pbsa', 'uk', 'high-priority']
        }
        
        serializer = LeadCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        lead = serializer.save(
            group=self.group1,
            assigned_to=self.analyst_user
        )
        
        self.assertEqual(lead.contact_name, 'John Doe')
        self.assertEqual(lead.target_company, self.target)
        self.assertEqual(lead.group, self.group1)
        self.assertEqual(lead.tags, ['pbsa', 'uk', 'high-priority'])
    
    def test_lead_list_serializer(self):
        """Test LeadListSerializer with minimal fields."""
        lead = LeadFactory.create(
            group=self.group1,
            target_company=self.target
        )
        
        serializer = LeadListSerializer(lead)
        data = serializer.data
        
        # Should have limited fields for list view
        self.assertIn('id', data)
        self.assertIn('company_name', data)
        self.assertIn('contact_name', data)
        self.assertIn('lead_score', data)
        self.assertIn('status', data)
        self.assertIn('priority', data)
        self.assertIn('assigned_to', data)
        self.assertIn('created_at', data)
        
        # Should not have detailed fields
        self.assertNotIn('score_breakdown', data)
        self.assertNotIn('metadata', data)
    
    def test_lead_detail_serializer(self):
        """Test LeadDetailSerializer with all fields and activities."""
        lead = LeadFactory.create(
            group=self.group1,
            target_company=self.target
        )
        
        # Add activities
        LeadActivityFactory.create_batch(3, lead=lead)
        
        serializer = LeadDetailSerializer(lead)
        data = serializer.data
        
        # Should have all fields including activities
        self.assertIn('activities', data)
        self.assertEqual(len(data['activities']), 3)
        self.assertIn('score_breakdown', data)
        self.assertIn('metadata', data)
        self.assertIn('days_since_creation', data)
        self.assertIn('days_in_current_status', data)
    
    def test_validate_unique_target_company(self):
        """Test validation of unique target company per group."""
        # Create existing lead
        LeadFactory.create(
            group=self.group1,
            target_company=self.target
        )
        
        # Try to create another lead for same target
        data = {
            'target_company': str(self.target.id),
            'scoring_model': str(self.scoring_model.id),
            'contact_name': 'Jane Doe'
        }
        
        serializer = LeadCreateSerializer(data=data)
        serializer.context['group'] = self.group1
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('target_company', serializer.errors)
    
    def test_update_lead_status(self):
        """Test updating lead status through serializer."""
        lead = LeadFactory.create(
            group=self.group1,
            status=Lead.LeadStatus.NEW
        )
        
        data = {'status': Lead.LeadStatus.QUALIFIED}
        serializer = LeadSerializer(lead, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        
        updated_lead = serializer.save()
        self.assertEqual(updated_lead.status, Lead.LeadStatus.QUALIFIED)
        self.assertIsNotNone(updated_lead.last_status_change)
    
    def test_bulk_action_serializer(self):
        """Test LeadBulkActionSerializer for bulk operations."""
        lead1 = LeadFactory.create(group=self.group1)
        lead2 = LeadFactory.create(group=self.group1)
        
        data = {
            'lead_ids': [str(lead1.id), str(lead2.id)],
            'action': 'update_status',
            'status': Lead.LeadStatus.CONTACTED
        }
        
        serializer = LeadBulkActionSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        validated_data = serializer.validated_data
        self.assertEqual(len(validated_data['lead_ids']), 2)
        self.assertEqual(validated_data['action'], 'update_status')
        self.assertEqual(validated_data['status'], Lead.LeadStatus.CONTACTED)
    
    def test_analytics_serializer(self):
        """Test LeadAnalyticsSerializer."""
        # Create leads with different statuses
        LeadFactory.create(
            group=self.group1,
            status=Lead.LeadStatus.NEW
        )
        LeadFactory.create(
            group=self.group1,
            status=Lead.LeadStatus.QUALIFIED,
            lead_score=80
        )
        LeadFactory.create(
            group=self.group1,
            status=Lead.LeadStatus.CONVERTED,
            conversion_value=Decimal('100000')
        )
        
        # Create analytics data
        analytics_data = {
            'total_leads': 3,
            'leads_by_status': {
                'NEW': 1,
                'QUALIFIED': 1,
                'CONVERTED': 1
            },
            'average_lead_score': 60.0,
            'conversion_rate': 0.33,
            'total_conversion_value': Decimal('100000'),
            'leads_by_source': {
                'MARKET_INTELLIGENCE': 3
            }
        }
        
        serializer = LeadAnalyticsSerializer(data=analytics_data)
        self.assertTrue(serializer.is_valid())
        
        data = serializer.data
        self.assertEqual(data['total_leads'], 3)
        self.assertEqual(data['conversion_rate'], 0.33)


class LeadActivitySerializerTest(TestCase, TestDataMixin):
    """Test LeadActivitySerializer functionality."""
    
    def setUp(self):
        super().setUp()
        self.lead = LeadFactory.create(group=self.group1)
    
    def test_serialize_lead_activity(self):
        """Test serializing a lead activity."""
        activity = LeadActivityFactory.create(
            lead=self.lead,
            activity_type=LeadActivity.ActivityType.CALL,
            description="Initial qualification call",
            created_by=self.analyst_user,
            contact_method='phone',
            outcome='connected'
        )
        
        serializer = LeadActivitySerializer(activity)
        data = serializer.data
        
        self.assertEqual(data['activity_type'], LeadActivity.ActivityType.CALL)
        self.assertEqual(data['description'], "Initial qualification call")
        self.assertEqual(data['contact_method'], 'phone')
        self.assertEqual(data['outcome'], 'connected')
        self.assertIn('created_by', data)
        self.assertIn('is_completed', data)
        self.assertIn('is_overdue', data)
    
    def test_create_activity(self):
        """Test creating an activity through serializer."""
        data = {
            'lead': str(self.lead.id),
            'activity_type': LeadActivity.ActivityType.EMAIL,
            'description': 'Sent introduction email',
            'contact_method': 'email'
        }
        
        serializer = LeadActivitySerializer(data=data)
        serializer.context['request'] = type('Request', (), {'user': self.analyst_user})
        self.assertTrue(serializer.is_valid())
        
        activity = serializer.save()
        self.assertEqual(activity.lead, self.lead)
        self.assertEqual(activity.created_by, self.analyst_user)
    
    def test_schedule_activity(self):
        """Test scheduling a future activity."""
        future_date = timezone.now() + timedelta(days=3)
        
        data = {
            'lead': str(self.lead.id),
            'activity_type': LeadActivity.ActivityType.MEETING,
            'description': 'Product demo meeting',
            'scheduled_at': future_date.isoformat()
        }
        
        serializer = LeadActivitySerializer(data=data)
        serializer.context['request'] = type('Request', (), {'user': self.analyst_user})
        self.assertTrue(serializer.is_valid())
        
        activity = serializer.save()
        self.assertEqual(activity.scheduled_at.date(), future_date.date())
        self.assertFalse(activity.is_completed)
        self.assertFalse(activity.is_overdue)
    
    def test_complete_activity(self):
        """Test marking an activity as completed."""
        activity = LeadActivityFactory.create(
            lead=self.lead,
            scheduled_at=timezone.now() - timedelta(hours=1),
            completed_at=None
        )
        
        data = {
            'completed_at': timezone.now().isoformat(),
            'outcome': 'Successful - moving to next stage'
        }
        
        serializer = LeadActivitySerializer(activity, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        
        updated_activity = serializer.save()
        self.assertTrue(updated_activity.is_completed)
        self.assertEqual(updated_activity.outcome, 'Successful - moving to next stage')
    
    def test_activity_validation(self):
        """Test activity validation rules."""
        # Cannot schedule in the past
        past_date = timezone.now() - timedelta(days=1)
        
        data = {
            'lead': str(self.lead.id),
            'activity_type': LeadActivity.ActivityType.CALL,
            'description': 'Call',
            'scheduled_at': past_date.isoformat()
        }
        
        serializer = LeadActivitySerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('scheduled_at', serializer.errors)
    
    def test_nested_user_representation(self):
        """Test nested user representation in activity."""
        activity = LeadActivityFactory.create(
            lead=self.lead,
            created_by=self.analyst_user
        )
        
        serializer = LeadActivitySerializer(activity)
        data = serializer.data
        
        self.assertIn('created_by', data)
        self.assertIsInstance(data['created_by'], dict)
        self.assertIn('id', data['created_by'])
        self.assertIn('username', data['created_by'])
        self.assertIn('email', data['created_by'])