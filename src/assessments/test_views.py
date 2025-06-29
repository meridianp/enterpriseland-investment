"""
Tests for assessment views and API endpoints.
"""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from datetime import datetime, timedelta
from decimal import Decimal
import json

from tests.base import BaseAPITestCase
from tests.factories.user_factories import UserFactory, GroupFactory, create_test_users
from tests.factories.assessment_factories import (
    DevelopmentPartnerFactory, AssessmentFactory, FXRateFactory,
    create_complete_assessment, create_assessment_workflow,
    create_bulk_assessments
)
from assessments.models import (
    DevelopmentPartner, Assessment, FXRate, AssessmentAuditLog_Legacy
)
from accounts.models import User


class DevelopmentPartnerViewSetTest(BaseAPITestCase):
    """Test DevelopmentPartner ViewSet."""
    
    def setUp(self):
        super().setUp()
        self.url = reverse('developmentpartner-list')
        
    def test_list_partners_authenticated(self):
        """Test listing partners requires authentication."""
        # Create partners
        partner1 = DevelopmentPartnerFactory(group=self.group)
        partner2 = DevelopmentPartnerFactory(group=self.group)
        
        # Test unauthenticated
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Test authenticated
        self.login(self.analyst_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        
    def test_group_filtering(self):
        """Test partners are filtered by user's group."""
        # Create partners in different groups
        partner1 = DevelopmentPartnerFactory(group=self.group)
        
        other_group = GroupFactory()
        partner2 = DevelopmentPartnerFactory(group=other_group)
        
        self.login(self.analyst_user)
        response = self.client.get(self.url)
        
        partner_ids = [p['id'] for p in response.data['results']]
        self.assertIn(partner1.id, partner_ids)
        self.assertNotIn(partner2.id, partner_ids)
        
    def test_create_partner(self):
        """Test creating a development partner."""
        self.login(self.manager_user)
        
        data = {
            'name': 'New Partner Ltd',
            'registration_number': 'REG123456',
            'year_established': 2010,
            'website': 'https://newpartner.com',
            'primary_contact_name': 'John Doe',
            'primary_contact_email': 'john@newpartner.com',
            'primary_contact_phone': '+1234567890',
            'total_employees': 100,
            'development_employees': 30,
            'company_structure': 'LLC',
            'business_model': 'Development and management',
            'office_locations': [
                {
                    'address': '123 Main St',
                    'city': 'London',
                    'country': 'UK',
                    'is_headquarters': True,
                    'employee_count': 50
                }
            ],
            'key_shareholders': [
                {
                    'name': 'John Smith',
                    'ownership_percentage': '51.00',
                    'is_company': False,
                    'background_info': 'Founder and CEO'
                },
                {
                    'name': 'Investment Corp',
                    'ownership_percentage': '49.00',
                    'is_company': True,
                    'background_info': 'Private equity firm'
                }
            ]
        }
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify partner created
        partner = DevelopmentPartner.objects.get(id=response.data['id'])
        self.assertEqual(partner.name, 'New Partner Ltd')
        self.assertEqual(partner.group, self.group)
        self.assertEqual(partner.created_by, self.manager_user)
        
        # Verify relationships
        self.assertEqual(partner.office_locations.count(), 1)
        self.assertEqual(partner.key_shareholders.count(), 2)
        
    def test_create_partner_permission(self):
        """Test only certain roles can create partners."""
        # Read-only user cannot create
        self.login(self.viewer_user)
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Analyst can create
        self.login(self.analyst_user)
        data = {
            'name': 'Test Partner',
            'registration_number': 'REG999',
            'year_established': 2020
        }
        response = self.client.post(self.url, data, format='json')
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])
        
    def test_update_partner(self):
        """Test updating a partner."""
        partner = DevelopmentPartnerFactory(group=self.group)
        
        self.login(self.manager_user)
        url = reverse('developmentpartner-detail', kwargs={'pk': partner.id})
        
        data = {
            'name': 'Updated Partner Name',
            'website': 'https://updated.com'
        }
        
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        partner.refresh_from_db()
        self.assertEqual(partner.name, 'Updated Partner Name')
        self.assertEqual(partner.website, 'https://updated.com')
        
    def test_delete_partner(self):
        """Test deleting a partner."""
        partner = DevelopmentPartnerFactory(group=self.group)
        
        # Only admin can delete
        self.login(self.analyst_user)
        url = reverse('developmentpartner-detail', kwargs={'pk': partner.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Admin can delete
        self.login(self.admin_user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        self.assertFalse(DevelopmentPartner.objects.filter(id=partner.id).exists())
        
    def test_partner_assessments_endpoint(self):
        """Test the assessments endpoint for a partner."""
        partner = DevelopmentPartnerFactory(group=self.group)
        
        # Create assessments
        assessment1 = create_complete_assessment(
            group=self.group,
            development_partner=partner
        )
        assessment2 = create_complete_assessment(
            group=self.group,
            development_partner=partner
        )
        
        self.login(self.analyst_user)
        url = reverse('developmentpartner-assessments', kwargs={'pk': partner.id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
    def test_search_partners(self):
        """Test searching partners."""
        DevelopmentPartnerFactory(name='ABC Corporation', group=self.group)
        DevelopmentPartnerFactory(name='XYZ Limited', group=self.group)
        DevelopmentPartnerFactory(name='ABC Holdings', group=self.group)
        
        self.login(self.analyst_user)
        
        # Search by name
        response = self.client.get(self.url, {'search': 'ABC'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        
    def test_filter_partners(self):
        """Test filtering partners."""
        DevelopmentPartnerFactory(
            year_established=2010,
            company_structure='LLC',
            group=self.group
        )
        DevelopmentPartnerFactory(
            year_established=2020,
            company_structure='Corporation',
            group=self.group
        )
        
        self.login(self.analyst_user)
        
        # Filter by year
        response = self.client.get(self.url, {'year_established': 2010})
        self.assertEqual(len(response.data['results']), 1)
        
        # Filter by structure
        response = self.client.get(self.url, {'company_structure': 'LLC'})
        self.assertEqual(len(response.data['results']), 1)
        
    def test_order_partners(self):
        """Test ordering partners."""
        DevelopmentPartnerFactory(name='Zebra Inc', group=self.group)
        DevelopmentPartnerFactory(name='Alpha Corp', group=self.group)
        DevelopmentPartnerFactory(name='Beta Ltd', group=self.group)
        
        self.login(self.analyst_user)
        
        # Order by name
        response = self.client.get(self.url, {'ordering': 'name'})
        names = [p['name'] for p in response.data['results']]
        self.assertEqual(names, ['Alpha Corp', 'Beta Ltd', 'Zebra Inc'])
        
        # Order by name descending
        response = self.client.get(self.url, {'ordering': '-name'})
        names = [p['name'] for p in response.data['results']]
        self.assertEqual(names, ['Zebra Inc', 'Beta Ltd', 'Alpha Corp'])


class AssessmentViewSetTest(BaseAPITestCase):
    """Test Assessment ViewSet."""
    
    def setUp(self):
        super().setUp()
        self.url = reverse('assessment-list')
        
    def test_list_assessments(self):
        """Test listing assessments."""
        # Create assessments
        assessment1 = create_complete_assessment(group=self.group)
        assessment2 = create_complete_assessment(group=self.group)
        
        self.login(self.analyst_user)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        
    def test_create_assessment(self):
        """Test creating an assessment."""
        partner = DevelopmentPartnerFactory(group=self.group)
        
        self.login(self.analyst_user)
        
        data = {
            'development_partner': partner.id,
            'assessment_type': 'INITIAL',
            'financial_risk': 5,
            'operational_risk': 4,
            'market_risk': 6,
            'regulatory_risk': 3,
            'reputational_risk': 4,
            'esg_risk': 5,
            'risk_mitigation': 'Comprehensive risk management plan',
            'key_risks_identified': ['Market volatility', 'Regulatory changes'],
            'risk_appetite': 'medium',
            'financial_info': {
                'financial_year': 2023,
                'currency': 'USD',
                'revenue': '50000000.00',
                'ebitda': '10000000.00',
                'total_debt': '20000000.00',
                'net_worth': '30000000.00',
                'debt_ratio_category': 'moderate',
                'primary_funding_source': 'Bank loans',
                'funding_diversification': 'moderate'
            },
            'credit_info': {
                'credit_rating_agency': "S&P",
                'credit_rating': 'BBB',
                'rating_date': '2024-01-15',
                'rating_outlook': 'Stable',
                'payment_history': 'Good payment history',
                'bankruptcy_history': False,
                'litigation_history': 'No major litigation',
                'bank_references': 'Strong banking relationships',
                'trade_references': 'Positive trade references'
            }
        }
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify assessment created
        assessment = Assessment.objects.get(id=response.data['id'])
        self.assertEqual(assessment.development_partner, partner)
        self.assertEqual(assessment.status, 'DRAFT')
        self.assertEqual(assessment.created_by, self.analyst_user)
        
        # Verify related objects created
        self.assertIsNotNone(assessment.financial_info)
        self.assertIsNotNone(assessment.credit_info)
        
    def test_update_assessment(self):
        """Test updating an assessment."""
        assessment = create_complete_assessment(
            group=self.group,
            status='DRAFT'
        )
        
        self.login(self.analyst_user)
        url = reverse('assessment-detail', kwargs={'pk': assessment.id})
        
        data = {
            'financial_risk': 8,
            'operational_risk': 7,
            'status': 'IN_REVIEW'
        }
        
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        assessment.refresh_from_db()
        self.assertEqual(assessment.financial_risk, 8)
        self.assertEqual(assessment.operational_risk, 7)
        self.assertEqual(assessment.status, 'IN_REVIEW')
        
        # Check version increment
        self.assertEqual(assessment.version_patch, 1)
        
    def test_approve_assessment(self):
        """Test approving an assessment."""
        assessment = create_complete_assessment(
            group=self.group,
            status='IN_REVIEW'
        )
        
        # Analyst cannot approve
        self.login(self.analyst_user)
        url = reverse('assessment-approve', kwargs={'pk': assessment.id})
        
        data = {
            'decision': 'APPROVED',
            'decision_notes': 'All criteria met'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Manager can approve
        self.login(self.manager_user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, 'APPROVED')
        self.assertEqual(assessment.decision, 'APPROVED')
        self.assertEqual(assessment.decision_by, self.manager_user)
        self.assertIsNotNone(assessment.decision_date)
        
    def test_approve_draft_assessment(self):
        """Test cannot approve draft assessment."""
        assessment = create_complete_assessment(
            group=self.group,
            status='DRAFT'
        )
        
        self.login(self.manager_user)
        url = reverse('assessment-approve', kwargs={'pk': assessment.id})
        
        data = {
            'decision': 'APPROVED',
            'decision_notes': 'Trying to approve draft'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_clone_assessment(self):
        """Test cloning an assessment."""
        original = create_complete_assessment(
            group=self.group,
            status='APPROVED'
        )
        
        self.login(self.analyst_user)
        url = reverse('assessment-clone', kwargs={'pk': original.id})
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify clone created
        clone = Assessment.objects.get(id=response.data['id'])
        self.assertEqual(clone.development_partner, original.development_partner)
        self.assertEqual(clone.status, 'DRAFT')
        self.assertIsNone(clone.decision)
        self.assertEqual(clone.created_by, self.analyst_user)
        
        # Verify related objects cloned
        self.assertIsNotNone(clone.financial_info)
        self.assertNotEqual(clone.financial_info.id, original.financial_info.id)
        
    def test_dashboard_endpoint(self):
        """Test dashboard KPI endpoint."""
        # Create assessments with different statuses
        create_bulk_assessments(count=10, group=self.group)
        
        self.login(self.analyst_user)
        url = reverse('assessment-dashboard')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check response structure
        self.assertIn('total_assessments', response.data)
        self.assertIn('by_status', response.data)
        self.assertIn('by_decision', response.data)
        self.assertIn('avg_scores', response.data)
        self.assertIn('recent_assessments', response.data)
        
    def test_filter_assessments(self):
        """Test filtering assessments."""
        partner1 = DevelopmentPartnerFactory(group=self.group)
        partner2 = DevelopmentPartnerFactory(group=self.group)
        
        assessment1 = create_complete_assessment(
            group=self.group,
            development_partner=partner1,
            status='DRAFT'
        )
        assessment2 = create_complete_assessment(
            group=self.group,
            development_partner=partner2,
            status='APPROVED'
        )
        
        self.login(self.analyst_user)
        
        # Filter by partner
        response = self.client.get(self.url, {'development_partner': partner1.id})
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], assessment1.id)
        
        # Filter by status
        response = self.client.get(self.url, {'status': 'APPROVED'})
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], assessment2.id)
        
    def test_assessment_permissions(self):
        """Test assessment permissions for different roles."""
        assessment = create_complete_assessment(group=self.group)
        url = reverse('assessment-detail', kwargs={'pk': assessment.id})
        
        # External partner has limited access
        self.login(self.partner_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # But cannot update
        response = self.client.patch(url, {'financial_risk': 10})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Auditor can view
        self.login(self.auditor_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class FXRateViewSetTest(BaseAPITestCase):
    """Test FXRate ViewSet."""
    
    def setUp(self):
        super().setUp()
        self.url = reverse('fxrate-list')
        
    def test_list_fx_rates(self):
        """Test listing FX rates."""
        FXRateFactory(base_currency='USD', target_currency='EUR')
        FXRateFactory(base_currency='USD', target_currency='GBP')
        
        self.login(self.analyst_user)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        
    def test_fx_rates_read_only(self):
        """Test FX rates are read-only for most users."""
        self.login(self.analyst_user)
        
        # Cannot create
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Cannot update
        rate = FXRateFactory()
        url = reverse('fxrate-detail', kwargs={'pk': rate.id})
        response = self.client.patch(url, {'rate': '1.5'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
    def test_refresh_fx_rates(self):
        """Test refresh FX rates endpoint (admin only)."""
        self.login(self.analyst_user)
        url = reverse('fxrate-refresh')
        
        # Non-admin cannot refresh
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Admin can refresh
        self.login(self.admin_user)
        response = self.client.post(url)
        # Should trigger Celery task
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_202_ACCEPTED])


class AuditLogViewSetTest(BaseAPITestCase):
    """Test Legacy AuditLog ViewSet."""
    
    def setUp(self):
        super().setUp()
        self.url = reverse('auditlog-list')
        
    def test_audit_log_permissions(self):
        """Test audit log is restricted to admin/auditor."""
        # Create some audit logs by performing actions
        partner = DevelopmentPartnerFactory(group=self.group, created_by=self.analyst_user)
        
        # Analyst cannot view audit logs
        self.login(self.analyst_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Auditor can view
        self.login(self.auditor_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Admin can view
        self.login(self.admin_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
    def test_audit_log_filtering(self):
        """Test filtering audit logs."""
        # Perform various actions to create logs
        self.login(self.analyst_user)
        
        partner = DevelopmentPartnerFactory(group=self.group)
        assessment = create_complete_assessment(group=self.group)
        
        # Login as auditor to view logs
        self.login(self.auditor_user)
        
        # Filter by user
        response = self.client.get(self.url, {'user': self.analyst_user.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Filter by model
        response = self.client.get(self.url, {'model_name': 'Assessment'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Filter by action
        response = self.client.get(self.url, {'action': 'CREATE'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)