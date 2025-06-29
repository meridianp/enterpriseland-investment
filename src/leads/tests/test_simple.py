"""Simple unit tests for leads models without database."""

import unittest
from django.test import TestCase
from leads.models import LeadScoringModel, Lead, LeadActivity


class SimpleLeadScoringModelTest(unittest.TestCase):
    """Test LeadScoringModel methods without database."""
    
    def test_model_status_choices(self):
        """Test ModelStatus choices are defined correctly."""
        choices = LeadScoringModel.ModelStatus.choices
        self.assertIn(('draft', 'Draft'), choices)
        self.assertIn(('active', 'Active'), choices)
        self.assertIn(('archived', 'Archived'), choices)
        self.assertIn(('testing', 'Testing'), choices)
    
    def test_scoring_method_choices(self):
        """Test ScoringMethod choices are defined correctly."""
        choices = LeadScoringModel.ScoringMethod.choices
        self.assertIn(('weighted_average', 'Weighted Average'), choices)
        self.assertIn(('neural_network', 'Neural Network'), choices)
        self.assertIn(('ensemble', 'Ensemble Method'), choices)
        self.assertIn(('custom', 'Custom Algorithm'), choices)
    
    def test_get_default_weights(self):
        """Test get_default_weights method."""
        model = LeadScoringModel()
        weights = model.get_default_weights()
        
        self.assertIsInstance(weights, dict)
        self.assertEqual(len(weights), 7)
        self.assertIn('business_alignment', weights)
        self.assertIn('market_presence', weights)
        self.assertIn('financial_strength', weights)
        self.assertIn('strategic_fit', weights)
        self.assertIn('geographic_fit', weights)
        self.assertIn('engagement_potential', weights)
        self.assertIn('data_completeness', weights)
        
        # Check weights sum to 1.0
        total_weight = sum(weights.values())
        self.assertAlmostEqual(total_weight, 1.0, places=2)
    
    def test_f1_score_property(self):
        """Test F1 score calculation."""
        model = LeadScoringModel()
        
        # Test with no scores
        self.assertIsNone(model.f1_score)
        
        # Test with precision and recall
        model.precision_score = 0.8
        model.recall_score = 0.75
        expected_f1 = 2 * (0.8 * 0.75) / (0.8 + 0.75)
        self.assertAlmostEqual(model.f1_score, expected_f1, places=4)


class SimpleLeadModelTest(unittest.TestCase):
    """Test Lead model methods without database."""
    
    def test_lead_status_choices(self):
        """Test LeadStatus choices are defined correctly."""
        choices = Lead.LeadStatus.choices
        self.assertIn(('new', 'New'), choices)
        self.assertIn(('qualified', 'Qualified'), choices)
        self.assertIn(('contacted', 'Contacted'), choices)
        self.assertIn(('meeting_scheduled', 'Meeting Scheduled'), choices)
        self.assertIn(('proposal_sent', 'Proposal Sent'), choices)
        self.assertIn(('negotiating', 'Negotiating'), choices)
        self.assertIn(('converted', 'Converted'), choices)
        self.assertIn(('lost', 'Lost'), choices)
        self.assertIn(('nurturing', 'Nurturing'), choices)
        self.assertIn(('rejected', 'Rejected'), choices)
    
    def test_lead_source_choices(self):
        """Test LeadSource choices are defined correctly."""
        choices = Lead.LeadSource.choices
        self.assertIn(('market_intelligence', 'Market Intelligence'), choices)
        self.assertIn(('referral', 'Referral'), choices)
        self.assertIn(('direct_inquiry', 'Direct Inquiry'), choices)
        self.assertIn(('conference', 'Conference'), choices)
        self.assertIn(('cold_outreach', 'Cold Outreach'), choices)
        self.assertIn(('website', 'Website'), choices)
        self.assertIn(('partner_network', 'Partner Network'), choices)
        self.assertIn(('other', 'Other'), choices)
    
    def test_priority_choices(self):
        """Test Priority choices are defined correctly."""
        choices = Lead.Priority.choices
        self.assertIn(('low', 'Low'), choices)
        self.assertIn(('medium', 'Medium'), choices)
        self.assertIn(('high', 'High'), choices)
        self.assertIn(('urgent', 'Urgent'), choices)


class SimpleLeadActivityTest(unittest.TestCase):
    """Test LeadActivity model methods without database."""
    
    def test_activity_type_choices(self):
        """Test ActivityType choices are defined correctly."""
        choices = LeadActivity.ActivityType.choices
        self.assertIn(('note', 'Note'), choices)
        self.assertIn(('email_sent', 'Email Sent'), choices)
        self.assertIn(('email_received', 'Email Received'), choices)
        self.assertIn(('phone_call', 'Phone Call'), choices)
        self.assertIn(('meeting', 'Meeting'), choices)
        self.assertIn(('proposal_sent', 'Proposal Sent'), choices)
        self.assertIn(('contract_sent', 'Contract Sent'), choices)
        self.assertIn(('follow_up', 'Follow-up'), choices)
        self.assertIn(('status_change', 'Status Change'), choices)
        self.assertIn(('score_update', 'Score Update'), choices)
        self.assertIn(('document_shared', 'Document Shared'), choices)
        self.assertIn(('task_completed', 'Task Completed'), choices)
        self.assertIn(('system_update', 'System Update'), choices)


if __name__ == '__main__':
    unittest.main()