"""
Virtual Data Room (VDR) models for secure document sharing and management.
"""

from django.db import models
from django.core.exceptions import ValidationError
from assessments.base_models import GroupFilteredModel, TimestampedModel, UUIDModel
from accounts.models import User


class VirtualDataRoom(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Virtual Data Room - secure workspace for deal documents.
    
    Each deal can have one or more VDRs for different phases or audiences.
    """
    
    class VDRStatus(models.TextChoices):
        SETUP = 'setup', 'Setup'
        ACTIVE = 'active', 'Active'
        LOCKED = 'locked', 'Locked'
        ARCHIVED = 'archived', 'Archived'
        EXPIRED = 'expired', 'Expired'
    
    class AccessLevel(models.TextChoices):
        FULL = 'full', 'Full Access'
        LIMITED = 'limited', 'Limited Access'
        READ_ONLY = 'read_only', 'Read Only'
        PREVIEW_ONLY = 'preview_only', 'Preview Only'
    
    deal = models.ForeignKey(
        'Deal',
        on_delete=models.CASCADE,
        related_name='data_rooms'
    )
    
    # VDR Configuration
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=VDRStatus.choices,
        default=VDRStatus.SETUP
    )
    
    # Access Control
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_vdrs'
    )
    administrators = models.ManyToManyField(
        User,
        related_name='administered_vdrs',
        help_text="Users who can manage VDR settings and permissions"
    )
    
    # Security Settings
    password_protected = models.BooleanField(default=False)
    password_hash = models.CharField(max_length=128, blank=True)
    ip_restrictions = models.JSONField(
        default=list,
        blank=True,
        help_text="List of allowed IP addresses/ranges"
    )
    
    # Access Tracking
    track_downloads = models.BooleanField(default=True)
    track_views = models.BooleanField(default=True)
    watermark_documents = models.BooleanField(default=True)
    disable_printing = models.BooleanField(default=True)
    disable_screenshots = models.BooleanField(default=True)
    
    # Expiration
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When VDR access expires"
    )
    auto_extend_expiry = models.BooleanField(default=False)
    
    # Notifications
    notify_on_access = models.BooleanField(default=True)
    notify_on_download = models.BooleanField(default=True)
    notification_recipients = models.ManyToManyField(
        User,
        blank=True,
        related_name='vdr_notifications',
        help_text="Users to notify of VDR activity"
    )
    
    class Meta:
        db_table = 'vdr_data_rooms'
        verbose_name = 'Virtual Data Room'
        verbose_name_plural = 'Virtual Data Rooms'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['deal', 'status']),
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.deal.code}"
    
    @property
    def is_expired(self):
        """Check if VDR has expired"""
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    @property
    def document_count(self):
        """Total documents in VDR"""
        return VDRDocument.objects.filter(folder__data_room=self).count()
    
    @property
    def total_size_mb(self):
        """Total size of all documents in MB"""
        from django.db.models import Sum
        size_bytes = VDRDocument.objects.filter(
            folder__data_room=self
        ).aggregate(
            total=Sum('file_size')
        )['total'] or 0
        return round(size_bytes / (1024 * 1024), 2)
    
    def activate(self):
        """Activate the VDR"""
        self.status = self.VDRStatus.ACTIVE
        self.save(update_fields=['status'])
        
        # Create activity log
        from .activity import DealActivity
        DealActivity.objects.create(
            deal=self.deal,
            activity_type='vdr_activated',
            performed_by=self.created_by,
            description=f"Virtual Data Room '{self.name}' activated",
            metadata={'vdr_id': str(self.id)},
            group=self.group
        )
    
    def lock(self, locked_by):
        """Lock the VDR to prevent access"""
        self.status = self.VDRStatus.LOCKED
        self.save(update_fields=['status'])
        
        # Create activity log
        from .activity import DealActivity
        DealActivity.objects.create(
            deal=self.deal,
            activity_type='vdr_locked',
            performed_by=locked_by,
            description=f"Virtual Data Room '{self.name}' locked",
            metadata={'vdr_id': str(self.id)},
            group=self.group
        )


class VDRFolder(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Folder structure within a Virtual Data Room.
    """
    
    data_room = models.ForeignKey(
        VirtualDataRoom,
        on_delete=models.CASCADE,
        related_name='folders'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subfolders'
    )
    
    # Folder details
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    
    # Access control
    restricted_access = models.BooleanField(
        default=False,
        help_text="Requires special permission to access"
    )
    access_roles = models.JSONField(
        default=list,
        blank=True,
        help_text="Roles that can access this restricted folder"
    )
    
    class Meta:
        db_table = 'vdr_folders'
        verbose_name = 'VDR Folder'
        verbose_name_plural = 'VDR Folders'
        ordering = ['order', 'name']
        unique_together = [['data_room', 'parent', 'name']]
        indexes = [
            models.Index(fields=['data_room', 'parent']),
            models.Index(fields=['data_room', 'order']),
        ]
    
    def __str__(self):
        return f"{self.data_room.name} / {self.get_full_path()}"
    
    def get_full_path(self):
        """Get full folder path"""
        if self.parent:
            return f"{self.parent.get_full_path()}/{self.name}"
        return self.name
    
    @property
    def depth(self):
        """Get folder depth in hierarchy"""
        if self.parent:
            return self.parent.depth + 1
        return 0
    
    def clean(self):
        """Validate folder structure"""
        # Prevent circular references
        if self.parent:
            current = self.parent
            while current:
                if current == self:
                    raise ValidationError("Folder cannot be its own parent")
                current = current.parent
        
        # Limit depth
        if self.depth > 5:
            raise ValidationError("Folder depth cannot exceed 5 levels")


class VDRDocument(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Documents within a Virtual Data Room folder.
    """
    
    class DocumentStatus(models.TextChoices):
        UPLOADING = 'uploading', 'Uploading'
        PROCESSING = 'processing', 'Processing'
        ACTIVE = 'active', 'Active'
        HIDDEN = 'hidden', 'Hidden'
        ARCHIVED = 'archived', 'Archived'
    
    folder = models.ForeignKey(
        VDRFolder,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    # Document details
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file_attachment = models.ForeignKey(
        'files.FileAttachment',
        on_delete=models.CASCADE,
        related_name='vdr_documents'
    )
    
    # Metadata
    file_size = models.BigIntegerField(help_text="File size in bytes")
    file_type = models.CharField(max_length=50)
    version = models.PositiveIntegerField(default=1)
    checksum = models.CharField(max_length=64, help_text="SHA-256 checksum")
    
    # Status and visibility
    status = models.CharField(
        max_length=20,
        choices=DocumentStatus.choices,
        default=DocumentStatus.UPLOADING
    )
    is_featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    
    # Upload tracking
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='uploaded_vdr_documents'
    )
    upload_completed_at = models.DateTimeField(null=True, blank=True)
    
    # Access control
    restricted_access = models.BooleanField(default=False)
    access_roles = models.JSONField(
        default=list,
        blank=True,
        help_text="Roles that can access this document"
    )
    
    # Versioning
    previous_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='newer_versions'
    )
    is_current_version = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'vdr_documents'
        verbose_name = 'VDR Document'
        verbose_name_plural = 'VDR Documents'
        ordering = ['order', 'name']
        unique_together = [['folder', 'name', 'is_current_version']]
        indexes = [
            models.Index(fields=['folder', 'status']),
            models.Index(fields=['folder', 'order']),
            models.Index(fields=['uploaded_by', '-created_at']),
            models.Index(fields=['is_current_version', 'status']),
        ]
    
    def __str__(self):
        return f"{self.name} v{self.version}"
    
    @property
    def file_size_mb(self):
        """File size in MB"""
        return round(self.file_size / (1024 * 1024), 2)
    
    def create_new_version(self, new_file_attachment, uploaded_by):
        """Create a new version of this document"""
        # Mark current version as not current
        self.is_current_version = False
        self.save(update_fields=['is_current_version'])
        
        # Create new version
        new_version = VDRDocument.objects.create(
            folder=self.folder,
            name=self.name,
            description=self.description,
            file_attachment=new_file_attachment,
            file_size=new_file_attachment.file_size,
            file_type=new_file_attachment.content_type,
            version=self.version + 1,
            checksum="",  # FileAttachment doesn't have checksum field
            uploaded_by=uploaded_by,
            previous_version=self,
            group=self.group
        )
        
        return new_version


class VDRAccess(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Track user access and permissions to Virtual Data Rooms.
    """
    
    class AccessType(models.TextChoices):
        INVITED = 'invited', 'Invited'
        GRANTED = 'granted', 'Granted'
        REVOKED = 'revoked', 'Revoked'
        EXPIRED = 'expired', 'Expired'
    
    data_room = models.ForeignKey(
        VirtualDataRoom,
        on_delete=models.CASCADE,
        related_name='access_records'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='vdr_access'
    )
    
    # Access details
    access_type = models.CharField(
        max_length=20,
        choices=AccessType.choices,
        default=AccessType.INVITED
    )
    access_level = models.CharField(
        max_length=20,
        choices=VirtualDataRoom.AccessLevel.choices,
        default=VirtualDataRoom.AccessLevel.READ_ONLY
    )
    
    # Permissions
    can_download = models.BooleanField(default=False)
    can_upload = models.BooleanField(default=False)
    can_comment = models.BooleanField(default=True)
    can_view_audit_log = models.BooleanField(default=False)
    
    # Folder restrictions
    accessible_folders = models.ManyToManyField(
        VDRFolder,
        blank=True,
        help_text="Specific folders this user can access (if restricted)"
    )
    
    # Time restrictions
    granted_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='granted_vdr_access'
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revoked_vdr_access'
    )
    
    # Invitation details
    invitation_email = models.EmailField(blank=True)
    invitation_message = models.TextField(blank=True)
    invitation_accepted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'vdr_access'
        verbose_name = 'VDR Access'
        verbose_name_plural = 'VDR Access Records'
        ordering = ['-granted_at']
        unique_together = [['data_room', 'user']]
        indexes = [
            models.Index(fields=['data_room', 'access_type']),
            models.Index(fields=['user', 'access_type']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.data_room.name}"
    
    @property
    def is_active(self):
        """Check if access is currently active"""
        return (
            self.access_type == self.AccessType.GRANTED and
            not self.is_expired and
            not self.revoked_at
        )
    
    @property
    def is_expired(self):
        """Check if access has expired"""
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    def revoke(self, revoked_by, reason=""):
        """Revoke user access"""
        from django.utils import timezone
        
        self.access_type = self.AccessType.REVOKED
        self.revoked_at = timezone.now()
        self.revoked_by = revoked_by
        self.save()
        
        # Create activity log
        from .activity import DealActivity
        DealActivity.objects.create(
            deal=self.data_room.deal,
            activity_type='vdr_access_revoked',
            performed_by=revoked_by,
            description=f"Revoked VDR access for {self.user.get_full_name()}",
            metadata={
                'vdr_id': str(self.data_room.id),
                'user_id': str(self.user.id),
                'reason': reason
            },
            group=self.group
        )


class VDRAuditLog(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Comprehensive audit log for all VDR activities.
    """
    
    class ActionType(models.TextChoices):
        LOGIN = 'login', 'Login'
        LOGOUT = 'logout', 'Logout'
        VIEW_DOCUMENT = 'view_document', 'View Document'
        DOWNLOAD_DOCUMENT = 'download_document', 'Download Document'
        UPLOAD_DOCUMENT = 'upload_document', 'Upload Document'
        DELETE_DOCUMENT = 'delete_document', 'Delete Document'
        VIEW_FOLDER = 'view_folder', 'View Folder'
        CREATE_FOLDER = 'create_folder', 'Create Folder'
        GRANT_ACCESS = 'grant_access', 'Grant Access'
        REVOKE_ACCESS = 'revoke_access', 'Revoke Access'
        MODIFY_PERMISSIONS = 'modify_permissions', 'Modify Permissions'
        CHANGE_SETTINGS = 'change_settings', 'Change Settings'
        FAILED_ACCESS = 'failed_access', 'Failed Access Attempt'
    
    data_room = models.ForeignKey(
        VirtualDataRoom,
        on_delete=models.CASCADE,
        related_name='audit_logs'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='vdr_audit_logs'
    )
    
    # Action details
    action_type = models.CharField(
        max_length=30,
        choices=ActionType.choices
    )
    description = models.TextField()
    
    # Context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Related objects
    document = models.ForeignKey(
        VDRDocument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    folder = models.ForeignKey(
        VDRFolder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    
    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'vdr_audit_logs'
        verbose_name = 'VDR Audit Log'
        verbose_name_plural = 'VDR Audit Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['data_room', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action_type', '-created_at']),
            models.Index(fields=['document', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.action_type} - {self.created_at}"
    
    @classmethod
    def log_action(cls, data_room, user, action_type, description, **kwargs):
        """Create an audit log entry"""
        return cls.objects.create(
            data_room=data_room,
            user=user,
            action_type=action_type,
            description=description,
            group=data_room.group,
            **kwargs
        )