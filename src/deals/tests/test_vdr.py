"""
Tests for Virtual Data Room (VDR) functionality.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock
from datetime import timedelta

from accounts.models import Group
from assessments.models import DevelopmentPartner
from files.models import FileAttachment
from deals.models import (
    Deal, DealType, DealSource, VirtualDataRoom, VDRFolder, VDRDocument,
    VDRAccess, VDRAuditLog, DealTeamMember, DealRole
)

User = get_user_model()


class VirtualDataRoomModelTests(TestCase):
    """Test VirtualDataRoom model functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.user.groups.add(self.group)
        
        self.partner = DevelopmentPartner.objects.create(
            company_name="Test Partner Company",
            group=self.group
        )
        
        self.deal_type = DealType.objects.create(
            name="Test Deal Type",
            code="TEST",
            group=self.group
        )
        
        self.deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=1000000,
            group=self.group
        )
    
    def test_create_vdr(self):
        """Test creating a Virtual Data Room."""
        vdr = VirtualDataRoom.objects.create(
            deal=self.deal,
            name="Test VDR",
            description="VDR for testing",
            created_by=self.user,
            group=self.group
        )
        
        self.assertEqual(vdr.deal, self.deal)
        self.assertEqual(vdr.name, "Test VDR")
        self.assertEqual(vdr.created_by, self.user)
        self.assertEqual(vdr.status, VirtualDataRoom.VDRStatus.SETUP)
        self.assertFalse(vdr.password_protected)
        self.assertTrue(vdr.track_downloads)
    
    def test_vdr_activation(self):
        """Test VDR activation."""
        vdr = VirtualDataRoom.objects.create(
            deal=self.deal,
            name="Test VDR",
            created_by=self.user,
            group=self.group
        )
        
        vdr.activate()
        
        self.assertEqual(vdr.status, VirtualDataRoom.VDRStatus.ACTIVE)
    
    def test_vdr_lock(self):
        """Test VDR locking."""
        vdr = VirtualDataRoom.objects.create(
            deal=self.deal,
            name="Test VDR",
            created_by=self.user,
            status=VirtualDataRoom.VDRStatus.ACTIVE,
            group=self.group
        )
        
        vdr.lock(self.user)
        
        self.assertEqual(vdr.status, VirtualDataRoom.VDRStatus.LOCKED)
    
    def test_vdr_expiration(self):
        """Test VDR expiration check."""
        # Create expired VDR
        expired_vdr = VirtualDataRoom.objects.create(
            deal=self.deal,
            name="Expired VDR",
            created_by=self.user,
            expires_at=timezone.now() - timedelta(days=1),
            group=self.group
        )
        
        # Create non-expired VDR
        active_vdr = VirtualDataRoom.objects.create(
            deal=self.deal,
            name="Active VDR",
            created_by=self.user,
            expires_at=timezone.now() + timedelta(days=1),
            group=self.group
        )
        
        self.assertTrue(expired_vdr.is_expired)
        self.assertFalse(active_vdr.is_expired)
    
    def test_vdr_administrators(self):
        """Test VDR administrator management."""
        vdr = VirtualDataRoom.objects.create(
            deal=self.deal,
            name="Test VDR",
            created_by=self.user,
            group=self.group
        )
        
        admin_user = User.objects.create_user(
            username="vdradmin",
            email="admin@example.com",
            password="testpass123"
        )
        admin_user.groups.add(self.group)
        
        vdr.administrators.add(admin_user)
        
        self.assertIn(admin_user, vdr.administrators.all())


class VDRFolderModelTests(TestCase):
    """Test VDRFolder model functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.user.groups.add(self.group)
        
        self.partner = DevelopmentPartner.objects.create(
            company_name="Test Partner Company",
            group=self.group
        )
        
        self.deal_type = DealType.objects.create(
            name="Test Deal Type",
            code="TEST",
            group=self.group
        )
        
        self.deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=1000000,
            group=self.group
        )
        
        self.vdr = VirtualDataRoom.objects.create(
            deal=self.deal,
            name="Test VDR",
            created_by=self.user,
            group=self.group
        )
    
    def test_create_folder(self):
        """Test creating a VDR folder."""
        folder = VDRFolder.objects.create(
            data_room=self.vdr,
            name="Test Folder",
            description="Folder for testing",
            group=self.group
        )
        
        self.assertEqual(folder.data_room, self.vdr)
        self.assertEqual(folder.name, "Test Folder")
        self.assertEqual(folder.depth, 0)
        self.assertEqual(folder.get_full_path(), "Test Folder")
    
    def test_folder_hierarchy(self):
        """Test folder hierarchy functionality."""
        parent_folder = VDRFolder.objects.create(
            data_room=self.vdr,
            name="Parent Folder",
            group=self.group
        )
        
        child_folder = VDRFolder.objects.create(
            data_room=self.vdr,
            name="Child Folder",
            parent=parent_folder,
            group=self.group
        )
        
        self.assertEqual(child_folder.parent, parent_folder)
        self.assertEqual(child_folder.depth, 1)
        self.assertEqual(child_folder.get_full_path(), "Parent Folder/Child Folder")
        self.assertIn(child_folder, parent_folder.subfolders.all())
    
    def test_folder_depth_validation(self):
        """Test folder depth limit validation."""
        # Create nested folders up to the limit
        current_folder = None
        for i in range(6):  # Try to create 6 levels (limit is 5)
            if current_folder is None:
                folder = VDRFolder.objects.create(
                    data_room=self.vdr,
                    name=f"Level {i}",
                    group=self.group
                )
            else:
                folder = VDRFolder.objects.create(
                    data_room=self.vdr,
                    name=f"Level {i}",
                    parent=current_folder,
                    group=self.group
                )
            current_folder = folder
        
        # Try to create one more level (should fail)
        with self.assertRaises(ValidationError):
            deep_folder = VDRFolder(
                data_room=self.vdr,
                name="Too Deep",
                parent=current_folder,
                group=self.group
            )
            deep_folder.clean()
    
    def test_folder_restricted_access(self):
        """Test folder access restrictions."""
        restricted_folder = VDRFolder.objects.create(
            data_room=self.vdr,
            name="Restricted Folder",
            restricted_access=True,
            access_roles=["senior_partner", "legal_team"],
            group=self.group
        )
        
        self.assertTrue(restricted_folder.restricted_access)
        self.assertEqual(restricted_folder.access_roles, ["senior_partner", "legal_team"])


class VDRDocumentModelTests(TestCase):
    """Test VDRDocument model functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.user.groups.add(self.group)
        
        self.partner = DevelopmentPartner.objects.create(
            company_name="Test Partner Company",
            group=self.group
        )
        
        self.deal_type = DealType.objects.create(
            name="Test Deal Type",
            code="TEST",
            group=self.group
        )
        
        self.deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=1000000,
            group=self.group
        )
        
        self.vdr = VirtualDataRoom.objects.create(
            deal=self.deal,
            name="Test VDR",
            created_by=self.user,
            group=self.group
        )
        
        self.folder = VDRFolder.objects.create(
            data_room=self.vdr,
            name="Test Folder",
            group=self.group
        )
        
        # Create a minimal assessment for file attachment  
        from assessments.models import Assessment
        self.assessment = Assessment.objects.create(
            group=self.group,
            created_by=self.user,
            updated_by=self.user
        )
        
        # Mock file attachment
        self.file_attachment = FileAttachment.objects.create(
            assessment=self.assessment,
            file="test_document.pdf",
            filename="test_document.pdf",
            file_size=1024000,
            content_type="application/pdf",
            uploaded_by=self.user
        )
    
    def test_create_document(self):
        """Test creating a VDR document."""
        document = VDRDocument.objects.create(
            folder=self.folder,
            name="Test Document",
            description="Document for testing",
            file_attachment=self.file_attachment,
            file_size=1024000,
            file_type="application/pdf",
            checksum="abc123def456",
            uploaded_by=self.user,
            group=self.group
        )
        
        self.assertEqual(document.folder, self.folder)
        self.assertEqual(document.name, "Test Document")
        self.assertEqual(document.uploaded_by, self.user)
        self.assertEqual(document.version, 1)
        self.assertTrue(document.is_current_version)
        self.assertEqual(document.status, VDRDocument.DocumentStatus.UPLOADING)
    
    def test_document_versioning(self):
        """Test document version management."""
        # Create initial document
        original_doc = VDRDocument.objects.create(
            folder=self.folder,
            name="Versioned Document",
            file_attachment=self.file_attachment,
            file_size=1024000,
            file_type="application/pdf",
            checksum="original123",
            uploaded_by=self.user,
            status=VDRDocument.DocumentStatus.ACTIVE,
            group=self.group
        )
        
        # Create new file attachment for version 2
        new_file_attachment = FileAttachment.objects.create(
            assessment=self.assessment,
            file="test_document_v2.pdf",
            filename="test_document_v2.pdf",
            file_size=2048000,
            content_type="application/pdf",
            uploaded_by=self.user
        )
        
        # Create new version
        new_version = original_doc.create_new_version(new_file_attachment, self.user)
        
        # Check original document
        original_doc.refresh_from_db()
        self.assertFalse(original_doc.is_current_version)
        
        # Check new version
        self.assertEqual(new_version.version, 2)
        self.assertTrue(new_version.is_current_version)
        self.assertEqual(new_version.previous_version, original_doc)
        self.assertEqual(new_version.file_attachment, new_file_attachment)
    
    def test_document_file_size_mb(self):
        """Test file size calculation in MB."""
        document = VDRDocument.objects.create(
            folder=self.folder,
            name="Large Document",
            file_attachment=self.file_attachment,
            file_size=5242880,  # 5 MB
            file_type="application/pdf",
            uploaded_by=self.user,
            group=self.group
        )
        
        self.assertEqual(document.file_size_mb, 5.0)


class VDRAccessModelTests(TestCase):
    """Test VDRAccess model functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123"
        )
        self.access_user = User.objects.create_user(
            username="access",
            email="access@example.com",
            password="testpass123"
        )
        self.admin_user.groups.add(self.group)
        self.access_user.groups.add(self.group)
        
        self.partner = DevelopmentPartner.objects.create(
            company_name="Test Partner Company",
            group=self.group
        )
        
        self.deal_type = DealType.objects.create(
            name="Test Deal Type",
            code="TEST",
            group=self.group
        )
        
        self.deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=1000000,
            group=self.group
        )
        
        self.vdr = VirtualDataRoom.objects.create(
            deal=self.deal,
            name="Test VDR",
            created_by=self.admin_user,
            group=self.group
        )
    
    def test_create_vdr_access(self):
        """Test creating VDR access record."""
        access = VDRAccess.objects.create(
            data_room=self.vdr,
            user=self.access_user,
            access_type=VDRAccess.AccessType.GRANTED,
            access_level=VirtualDataRoom.AccessLevel.READ_ONLY,
            granted_by=self.admin_user,
            group=self.group
        )
        
        self.assertEqual(access.data_room, self.vdr)
        self.assertEqual(access.user, self.access_user)
        self.assertEqual(access.granted_by, self.admin_user)
        self.assertTrue(access.is_active)
        self.assertFalse(access.is_expired)
    
    def test_access_expiration(self):
        """Test access expiration."""
        # Create second user for active access to avoid unique constraint violation
        active_user = User.objects.create_user(
            username="activeuser",
            email="active@example.com",
            password="testpass123"
        )
        active_user.groups.add(self.group)
        
        # Create expired access
        expired_access = VDRAccess.objects.create(
            data_room=self.vdr,
            user=self.access_user,
            access_type=VDRAccess.AccessType.GRANTED,
            expires_at=timezone.now() - timedelta(days=1),
            granted_by=self.admin_user,
            group=self.group
        )
        
        # Create active access with different user
        active_access = VDRAccess.objects.create(
            data_room=self.vdr,
            user=active_user,
            access_type=VDRAccess.AccessType.GRANTED,
            expires_at=timezone.now() + timedelta(days=1),
            granted_by=self.admin_user,
            group=self.group
        )
        
        self.assertTrue(expired_access.is_expired)
        self.assertFalse(expired_access.is_active)
        self.assertFalse(active_access.is_expired)
        self.assertTrue(active_access.is_active)
    
    def test_revoke_access(self):
        """Test revoking VDR access."""
        access = VDRAccess.objects.create(
            data_room=self.vdr,
            user=self.access_user,
            access_type=VDRAccess.AccessType.GRANTED,
            granted_by=self.admin_user,
            group=self.group
        )
        
        access.revoke(self.admin_user, "Access no longer needed")
        
        self.assertEqual(access.access_type, VDRAccess.AccessType.REVOKED)
        self.assertEqual(access.revoked_by, self.admin_user)
        self.assertIsNotNone(access.revoked_at)
        self.assertFalse(access.is_active)


class VDRAuditLogModelTests(TestCase):
    """Test VDRAuditLog model functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.user.groups.add(self.group)
        
        self.partner = DevelopmentPartner.objects.create(
            company_name="Test Partner Company",
            group=self.group
        )
        
        self.deal_type = DealType.objects.create(
            name="Test Deal Type",
            code="TEST",
            group=self.group
        )
        
        self.deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=1000000,
            group=self.group
        )
        
        self.vdr = VirtualDataRoom.objects.create(
            deal=self.deal,
            name="Test VDR",
            created_by=self.user,
            group=self.group
        )
    
    def test_create_audit_log(self):
        """Test creating audit log entry."""
        log_entry = VDRAuditLog.objects.create(
            data_room=self.vdr,
            user=self.user,
            action_type=VDRAuditLog.ActionType.LOGIN,
            description="User logged into VDR",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0 Test Browser",
            group=self.group
        )
        
        self.assertEqual(log_entry.data_room, self.vdr)
        self.assertEqual(log_entry.user, self.user)
        self.assertEqual(log_entry.action_type, VDRAuditLog.ActionType.LOGIN)
        self.assertEqual(log_entry.ip_address, "192.168.1.1")
    
    def test_log_action_classmethod(self):
        """Test the log_action class method."""
        log_entry = VDRAuditLog.log_action(
            data_room=self.vdr,
            user=self.user,
            action_type=VDRAuditLog.ActionType.VIEW_FOLDER,
            description="Viewed folder contents",
            ip_address="10.0.0.1",
            metadata={"folder_name": "Financial Documents"}
        )
        
        self.assertEqual(log_entry.data_room, self.vdr)
        self.assertEqual(log_entry.user, self.user)
        self.assertEqual(log_entry.action_type, VDRAuditLog.ActionType.VIEW_FOLDER)
        self.assertEqual(log_entry.metadata["folder_name"], "Financial Documents")


class VDRAPITests(APITestCase):
    """Test VDR API endpoints."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testapi",
            email="test@example.com",
            password="testpass123",
            role=User.Role.PORTFOLIO_MANAGER
        )
        self.user.groups.add(self.group)
        
        self.partner = DevelopmentPartner.objects.create(
            company_name="Test Partner Company",
            group=self.group
        )
        
        self.deal_type = DealType.objects.create(
            name="Test Deal Type",
            code="TEST",
            group=self.group
        )
        
        self.deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=1000000,
            group=self.group
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_create_vdr_api(self):
        """Test creating VDR via API."""
        url = '/api/deals/vdr/'
        data = {
            'deal': str(self.deal.id),
            'name': 'API Test VDR',
            'description': 'VDR created via API',
            'password_protected': True,
            'track_downloads': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(VirtualDataRoom.objects.count(), 1)
        
        vdr = VirtualDataRoom.objects.first()
        self.assertEqual(vdr.name, 'API Test VDR')
        self.assertEqual(vdr.created_by, self.user)
        self.assertTrue(vdr.password_protected)
    
    def test_activate_vdr_api(self):
        """Test activating VDR via API."""
        vdr = VirtualDataRoom.objects.create(
            deal=self.deal,
            name="Test VDR",
            created_by=self.user,
            group=self.group
        )
        
        url = f'/api/deals/vdr/{vdr.id}/activate/'
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        vdr.refresh_from_db()
        self.assertEqual(vdr.status, VirtualDataRoom.VDRStatus.ACTIVE)
    
    def test_create_vdr_folder_api(self):
        """Test creating VDR folder via API."""
        vdr = VirtualDataRoom.objects.create(
            deal=self.deal,
            name="Test VDR",
            created_by=self.user,
            group=self.group
        )
        
        url = '/api/deals/vdr-folders/'
        data = {
            'data_room': str(vdr.id),
            'name': 'API Test Folder',
            'description': 'Folder created via API',
            'order': 1,
            'parent': None  # Root folder
        }
        
        response = self.client.post(url, data, format='json')
        
        # Debug the response if it fails
        if response.status_code != status.HTTP_201_CREATED:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(VDRFolder.objects.count(), 1)
        
        folder = VDRFolder.objects.first()
        self.assertEqual(folder.name, 'API Test Folder')
        self.assertEqual(folder.data_room, vdr)
    
    @patch('deals.models.vdr.VDRAuditLog.log_action')
    def test_vdr_document_download_api(self, mock_log_action):
        """Test VDR document download tracking via API."""
        vdr = VirtualDataRoom.objects.create(
            deal=self.deal,
            name="Test VDR",
            created_by=self.user,
            group=self.group
        )
        
        folder = VDRFolder.objects.create(
            data_room=vdr,
            name="Test Folder",
            group=self.group
        )
        
        # Create assessment for file attachment requirement
        from assessments.models import Assessment
        assessment = Assessment.objects.create(
            group=self.group,
            created_by=self.user,
            updated_by=self.user
        )
        
        file_attachment = FileAttachment.objects.create(
            assessment=assessment,
            file="test_document.pdf",
            filename="test_document.pdf",
            file_size=1024000,
            content_type="application/pdf",
            uploaded_by=self.user
        )
        
        document = VDRDocument.objects.create(
            folder=folder,
            name="Test Document",
            file_attachment=file_attachment,
            file_size=1024000,
            file_type="application/pdf",
            uploaded_by=self.user,
            status=VDRDocument.DocumentStatus.ACTIVE,
            group=self.group
        )
        
        url = f'/api/deals/vdr-documents/{document.id}/download/'
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify audit log was called (IP address will be 127.0.0.1 in test environment)
        mock_log_action.assert_called_once_with(
            data_room=vdr,
            user=self.user,
            action_type=VDRAuditLog.ActionType.DOWNLOAD_DOCUMENT,
            description=f"Downloaded document: {document.name}",
            document=document,
            ip_address='127.0.0.1',  # Test client IP address
            user_agent=''
        )
    
    def test_vdr_access_management_api(self):
        """Test VDR access management via API."""
        vdr = VirtualDataRoom.objects.create(
            deal=self.deal,
            name="Test VDR",
            created_by=self.user,
            group=self.group
        )
        
        access_user = User.objects.create_user(
            username="vdraccess",
            email="access@example.com",
            password="testpass123"
        )
        access_user.groups.add(self.group)
        
        # Create access record
        access = VDRAccess.objects.create(
            data_room=vdr,
            user=access_user,
            access_type=VDRAccess.AccessType.GRANTED,
            access_level=VirtualDataRoom.AccessLevel.READ_ONLY,
            granted_by=self.user,
            group=self.group
        )
        
        # Test revoking access
        url = f'/api/deals/vdr-access/{access.id}/revoke/'
        data = {'reason': 'Access no longer needed'}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        access.refresh_from_db()
        self.assertEqual(access.access_type, VDRAccess.AccessType.REVOKED)
        self.assertEqual(access.revoked_by, self.user)
    
    def test_vdr_audit_log_api(self):
        """Test VDR audit log access via API."""
        vdr = VirtualDataRoom.objects.create(
            deal=self.deal,
            name="Test VDR",
            created_by=self.user,
            group=self.group
        )
        
        # Add user as VDR administrator
        vdr.administrators.add(self.user)
        
        # Create audit log entry
        VDRAuditLog.objects.create(
            data_room=vdr,
            user=self.user,
            action_type=VDRAuditLog.ActionType.LOGIN,
            description="User logged into VDR",
            group=self.group
        )
        
        url = f'/api/deals/vdr/{vdr.id}/access_log/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['action_type'], 'login')
    
    def test_vdr_structure_api(self):
        """Test getting VDR folder structure via API."""
        vdr = VirtualDataRoom.objects.create(
            deal=self.deal,
            name="Test VDR",
            created_by=self.user,
            group=self.group
        )
        
        # Create folder structure
        parent_folder = VDRFolder.objects.create(
            data_room=vdr,
            name="Parent Folder",
            group=self.group
        )
        
        child_folder = VDRFolder.objects.create(
            data_room=vdr,
            name="Child Folder",
            parent=parent_folder,
            group=self.group
        )
        
        url = f'/api/deals/vdr/{vdr.id}/structure/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # Parent + child folders