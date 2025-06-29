"""
Base service class for business logic operations.

Provides common functionality for all service classes including
error handling, logging, and transaction management.
"""

import logging
from typing import Any, Dict, Optional, List, Type, TypeVar
from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth import get_user_model

from accounts.models import Group

User = get_user_model()
T = TypeVar('T')


class ServiceError(Exception):
    """Base exception for service errors."""
    pass


class ValidationServiceError(ServiceError):
    """Service error for validation failures."""
    pass


class PermissionServiceError(ServiceError):
    """Service error for permission failures."""
    pass


class NotFoundServiceError(ServiceError):
    """Service error for not found resources."""
    pass


class BaseService:
    """
    Base service class providing common functionality.
    
    All business logic services should inherit from this class to get
    consistent error handling, logging, and transaction management.
    """
    
    def __init__(self, user: Optional[User] = None, group: Optional[Group] = None):
        """
        Initialize service with user context.
        
        Args:
            user: The user performing the operation
            group: The group context for multi-tenant operations
        """
        self.user = user
        self.group = group
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    def _log_operation(self, operation: str, details: Dict[str, Any] = None):
        """Log service operation."""
        user_info = f"user={self.user.email}" if self.user else "user=anonymous"
        group_info = f"group={self.group.name}" if self.group else "group=none"
        details_info = f"details={details}" if details else ""
        
        self.logger.info(f"{operation} - {user_info}, {group_info} {details_info}")
    
    def _check_permission(self, permission: str, obj: Any = None) -> bool:
        """
        Check if user has permission for operation.
        
        Args:
            permission: Permission to check
            obj: Object to check permission against
            
        Returns:
            bool: True if user has permission
            
        Raises:
            PermissionServiceError: If user lacks permission
        """
        if not self.user:
            raise PermissionServiceError("Authentication required")
        
        # Admin users have all permissions
        if self.user.role == User.Role.ADMIN:
            return True
        
        # Check if user belongs to the group context
        if self.group and not self.user.groups.filter(id=self.group.id).exists():
            raise PermissionServiceError(f"User does not belong to group {self.group.name}")
        
        # Add more specific permission checks here based on your permission system
        return True
    
    def _validate_group_context(self, obj: Any) -> None:
        """
        Validate that object belongs to the current group context.
        
        Args:
            obj: Object to validate
            
        Raises:
            PermissionServiceError: If object doesn't belong to group
        """
        if not self.group:
            raise ValidationServiceError("Group context required")
        
        if hasattr(obj, 'group') and obj.group != self.group:
            raise PermissionServiceError("Object does not belong to current group")
    
    @transaction.atomic
    def _execute_with_transaction(self, operation_func, *args, **kwargs):
        """
        Execute operation within a database transaction.
        
        Args:
            operation_func: Function to execute
            *args: Arguments for function
            **kwargs: Keyword arguments for function
            
        Returns:
            Result of operation_func
        """
        try:
            return operation_func(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"Transaction failed: {str(e)}")
            raise
    
    def _get_user_groups(self) -> List[Group]:
        """Get list of groups for current user."""
        if not self.user:
            return []
        
        if self.user.role == User.Role.ADMIN:
            return list(Group.objects.all())
        
        return list(self.user.groups.all())
    
    def _filter_by_group_access(self, queryset, user: Optional[User] = None):
        """
        Filter queryset by user's group access.
        
        Args:
            queryset: Django QuerySet to filter
            user: User to filter for (defaults to self.user)
            
        Returns:
            Filtered queryset
        """
        filter_user = user or self.user
        
        if not filter_user:
            return queryset.none()
        
        if filter_user.role == User.Role.ADMIN:
            return queryset
        
        user_groups = filter_user.groups.all()
        return queryset.filter(group__in=user_groups)
    
    def _handle_validation_error(self, error: ValidationError) -> None:
        """
        Handle Django validation errors.
        
        Args:
            error: ValidationError to handle
            
        Raises:
            ValidationServiceError: Converted service error
        """
        if hasattr(error, 'message_dict'):
            # Form/model validation errors
            raise ValidationServiceError(f"Validation failed: {error.message_dict}")
        elif hasattr(error, 'messages'):
            # Multiple validation messages
            raise ValidationServiceError(f"Validation failed: {'; '.join(error.messages)}")
        else:
            # Single validation message
            raise ValidationServiceError(f"Validation failed: {str(error)}")
    
    def create_response_data(self, 
                           success: bool = True, 
                           data: Any = None, 
                           message: str = None,
                           errors: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create standardized service response.
        
        Args:
            success: Whether operation was successful
            data: Response data
            message: Optional message
            errors: Optional error details
            
        Returns:
            Standardized response dictionary
        """
        response = {
            'success': success,
            'data': data,
        }
        
        if message:
            response['message'] = message
            
        if errors:
            response['errors'] = errors
            
        return response