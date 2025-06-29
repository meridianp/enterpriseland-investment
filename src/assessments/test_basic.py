"""
Basic tests to verify test setup is working.
"""
from django.test import TestCase
from tests.base import BaseTestCase
from accounts.models import User, Group


class BasicSetupTest(BaseTestCase):
    """Test basic setup functionality."""
    
    def test_user_creation(self):
        """Test that test users are created properly."""
        self.assertIsNotNone(self.admin_user)
        self.assertEqual(self.admin_user.role, User.Role.ADMIN)
        self.assertTrue(self.admin_user.groups.filter(id=self.group.id).exists())
        
    def test_group_creation(self):
        """Test that test group is created properly."""
        self.assertIsNotNone(self.group)
        self.assertEqual(self.group.name, 'test_group')
        
    def test_role_assignment(self):
        """Test all roles are assigned correctly."""
        self.assertEqual(self.admin_user.role, User.Role.ADMIN)
        self.assertEqual(self.manager_user.role, User.Role.PORTFOLIO_MANAGER)
        self.assertEqual(self.analyst_user.role, User.Role.BUSINESS_ANALYST)
        self.assertEqual(self.viewer_user.role, User.Role.READ_ONLY)
        self.assertEqual(self.auditor_user.role, User.Role.AUDITOR)
        self.assertEqual(self.partner_user.role, User.Role.EXTERNAL_PARTNER)