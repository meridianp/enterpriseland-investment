"""
Frontend API Utilities for CASA Due Diligence Platform - Phase 7.

Provides utility functions, mixins, and helpers to support frontend
development with consistent API patterns and responses.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date
from decimal import Decimal
import json

from django.db.models import QuerySet, Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils import timezone

from rest_framework import status
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import GroupFilteredPermission


class APIResponseMixin:
    """
    Mixin to provide consistent API response formatting.
    """
    
    @staticmethod
    def success_response(
        data: Any = None,
        message: str = "Success",
        status_code: int = status.HTTP_200_OK,
        meta: Dict[str, Any] = None
    ) -> Response:
        """Create a standardized success response."""
        response_data = {
            'status': 'success',
            'message': message,
            'data': data,
        }
        
        if meta:
            response_data['meta'] = meta
        
        return Response(response_data, status=status_code)
    
    @staticmethod
    def error_response(
        message: str = "An error occurred",
        errors: Dict[str, Any] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        error_code: str = None
    ) -> Response:
        """Create a standardized error response."""
        response_data = {
            'status': 'error',
            'message': message,
        }
        
        if errors:
            response_data['errors'] = errors
        
        if error_code:
            response_data['error_code'] = error_code
        
        return Response(response_data, status=status_code)
    
    @staticmethod
    def validation_error_response(errors: Dict[str, List[str]]) -> Response:
        """Create a validation error response."""
        return Response({
            'status': 'error',
            'message': 'Validation failed',
            'type': 'validation_error',
            'errors': errors,
        }, status=status.HTTP_400_BAD_REQUEST)


class PaginationMixin:
    """
    Mixin to provide consistent pagination handling.
    """
    
    default_page_size = 20
    max_page_size = 100
    
    def paginate_queryset_response(
        self,
        queryset: QuerySet,
        request: Request,
        serializer_class,
        context: Dict[str, Any] = None
    ) -> Response:
        """Paginate a queryset and return formatted response."""
        # Get pagination parameters
        page_number = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', self.default_page_size)
        
        # Validate page size
        try:
            page_size = min(int(page_size), self.max_page_size)
        except (ValueError, TypeError):
            page_size = self.default_page_size
        
        # Create paginator
        paginator = Paginator(queryset, page_size)
        
        try:
            page = paginator.page(page_number)
        except Exception:
            return self.error_response(
                message="Invalid page number",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Serialize data
        serializer_context = {'request': request}
        if context:
            serializer_context.update(context)
        
        serializer = serializer_class(
            page.object_list,
            many=True,
            context=serializer_context
        )
        
        # Build response
        return self.success_response(
            data=serializer.data,
            meta={
                'pagination': {
                    'page': page.number,
                    'page_size': page_size,
                    'total_pages': paginator.num_pages,
                    'total_items': paginator.count,
                    'has_next': page.has_next(),
                    'has_previous': page.has_previous(),
                }
            }
        )


class FilteringMixin:
    """
    Mixin to provide consistent filtering utilities.
    """
    
    def apply_date_filters(
        self,
        queryset: QuerySet,
        request: Request,
        date_field: str = 'created_at'
    ) -> QuerySet:
        """Apply common date range filters."""
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(**{f'{date_field}__gte': date_from})
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(**{f'{date_field}__lte': date_to})
            except ValueError:
                pass
        
        return queryset
    
    def apply_search_filter(
        self,
        queryset: QuerySet,
        request: Request,
        search_fields: List[str]
    ) -> QuerySet:
        """Apply search across multiple fields."""
        search_term = request.query_params.get('search', '').strip()
        
        if search_term:
            q_objects = Q()
            for field in search_fields:
                q_objects |= Q(**{f'{field}__icontains': search_term})
            queryset = queryset.filter(q_objects)
        
        return queryset
    
    def apply_ordering(
        self,
        queryset: QuerySet,
        request: Request,
        default_ordering: str = '-created_at',
        allowed_fields: List[str] = None
    ) -> QuerySet:
        """Apply ordering with validation."""
        ordering = request.query_params.get('ordering', default_ordering)
        
        # Validate ordering field
        if allowed_fields:
            field_name = ordering.lstrip('-')
            if field_name not in allowed_fields:
                ordering = default_ordering
        
        return queryset.order_by(ordering)


class SerializerContextMixin:
    """
    Mixin to provide consistent serializer context.
    """
    
    def get_serializer_context(self, request: Request) -> Dict[str, Any]:
        """Get standard serializer context."""
        return {
            'request': request,
            'user': request.user,
            'group': getattr(request.user, 'group', None),
            'timestamp': timezone.now(),
        }


class BulkOperationsMixin:
    """
    Mixin to provide bulk operation utilities.
    """
    
    def bulk_update_response(
        self,
        model_class,
        updates: List[Dict[str, Any]],
        id_field: str = 'id'
    ) -> Response:
        """Handle bulk update operations."""
        successful = []
        failed = []
        
        for update_data in updates:
            try:
                obj_id = update_data.pop(id_field, None)
                if not obj_id:
                    failed.append({
                        'id': None,
                        'error': f'Missing {id_field} field'
                    })
                    continue
                
                obj = model_class.objects.get(**{id_field: obj_id})
                
                # Update fields
                for field, value in update_data.items():
                    setattr(obj, field, value)
                
                obj.save()
                successful.append(obj_id)
                
            except model_class.DoesNotExist:
                failed.append({
                    'id': obj_id,
                    'error': 'Object not found'
                })
            except Exception as e:
                failed.append({
                    'id': obj_id,
                    'error': str(e)
                })
        
        return self.success_response(
            data={
                'updated': successful,
                'failed': failed,
            },
            message=f"Bulk update completed. {len(successful)} succeeded, {len(failed)} failed."
        )


class ExportMixin:
    """
    Mixin to provide data export utilities.
    """
    
    def export_to_dict(
        self,
        queryset: QuerySet,
        fields: List[str],
        serializer_class=None
    ) -> List[Dict[str, Any]]:
        """Export queryset to list of dictionaries."""
        if serializer_class:
            return serializer_class(queryset, many=True).data
        
        return list(queryset.values(*fields))
    
    def export_to_csv_response(
        self,
        queryset: QuerySet,
        fields: List[str],
        filename: str = 'export.csv'
    ) -> JsonResponse:
        """Export queryset to CSV response."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.DictWriter(response, fieldnames=fields)
        writer.writeheader()
        
        for obj in queryset.values(*fields):
            # Convert dates and decimals to strings
            for key, value in obj.items():
                if isinstance(value, (date, datetime)):
                    obj[key] = value.isoformat()
                elif isinstance(value, Decimal):
                    obj[key] = str(value)
            
            writer.writerow(obj)
        
        return response


class WebSocketMessageMixin:
    """
    Mixin to provide WebSocket message formatting.
    """
    
    @staticmethod
    def format_ws_message(
        message_type: str,
        data: Any,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Format a WebSocket message."""
        message = {
            'type': message_type,
            'data': data,
            'timestamp': timezone.now().isoformat(),
        }
        
        if metadata:
            message['metadata'] = metadata
        
        return json.dumps(message, default=str)
    
    @staticmethod
    def format_case_update(case, update_type: str = 'status_change') -> str:
        """Format a case update message."""
        return WebSocketMessageMixin.format_ws_message(
            'case_update',
            {
                'case_id': str(case.id),
                'case_reference': case.case_reference,
                'update_type': update_type,
                'new_status': case.case_status,
                'completion_percentage': case.completion_percentage,
            },
            metadata={
                'user': case.lead_assessor.email if case.lead_assessor else None,
                'priority': case.priority,
            }
        )


# Utility Functions

def calculate_business_days(start_date: date, end_date: date) -> int:
    """Calculate business days between two dates."""
    from datetime import timedelta
    
    business_days = 0
    current_date = start_date
    
    while current_date <= end_date:
        if current_date.weekday() < 5:  # Monday = 0, Friday = 4
            business_days += 1
        current_date += timedelta(days=1)
    
    return business_days


def format_currency(amount: Decimal, currency: str = 'GBP') -> str:
    """Format currency amount for display."""
    symbols = {
        'GBP': '£',
        'EUR': '€',
        'USD': '$',
    }
    
    symbol = symbols.get(currency, currency)
    formatted = f"{amount:,.2f}"
    
    return f"{symbol}{formatted}"


def get_risk_color(risk_level: str) -> str:
    """Get color code for risk level."""
    colors = {
        'low': '#28a745',      # Green
        'medium': '#ffc107',   # Yellow
        'high': '#fd7e14',     # Orange
        'critical': '#dc3545', # Red
    }
    
    return colors.get(risk_level.lower(), '#6c757d')  # Default gray


def get_status_color(status: str) -> str:
    """Get color code for case status."""
    colors = {
        'initiated': '#6c757d',        # Gray
        'data_collection': '#17a2b8',  # Info blue
        'analysis': '#007bff',         # Primary blue
        'review': '#6f42c1',           # Purple
        'decision_pending': '#fd7e14', # Orange
        'approved': '#28a745',         # Green
        'rejected': '#dc3545',         # Red
        'on_hold': '#ffc107',          # Yellow
        'completed': '#20c997',        # Teal
        'archived': '#6c757d',         # Gray
    }
    
    return colors.get(status.lower(), '#6c757d')


def calculate_completion_stats(checklist_items) -> Dict[str, Any]:
    """Calculate completion statistics for checklist items."""
    total = checklist_items.count()
    completed = checklist_items.filter(is_completed=True).count()
    required = checklist_items.filter(is_required=True).count()
    required_completed = checklist_items.filter(
        is_required=True,
        is_completed=True
    ).count()
    
    return {
        'total_items': total,
        'completed_items': completed,
        'required_items': required,
        'required_completed': required_completed,
        'completion_percentage': round((completed / total * 100), 1) if total > 0 else 0,
        'required_completion_percentage': round(
            (required_completed / required * 100), 1
        ) if required > 0 else 0,
    }


# Decorators

def require_case_permission(permission_type: str = 'view'):
    """Decorator to check case-specific permissions."""
    def decorator(func):
        def wrapper(request, case_id, *args, **kwargs):
            from .root_aggregate import DueDiligenceCase
            
            try:
                case = DueDiligenceCase.objects.get(
                    id=case_id,
                    group=request.user.group
                )
            except DueDiligenceCase.DoesNotExist:
                return APIResponseMixin.error_response(
                    message="Case not found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            # Check specific permissions
            if permission_type == 'edit':
                if not (request.user == case.lead_assessor or 
                       request.user in case.assessment_team.all() or
                       request.user.role in ['admin', 'manager']):
                    return APIResponseMixin.error_response(
                        message="You don't have permission to edit this case",
                        status_code=status.HTTP_403_FORBIDDEN
                    )
            
            return func(request, case_id, *args, **kwargs)
        
        return wrapper
    return decorator


# API View Examples

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_dashboard_stats(request):
    """Get dashboard statistics for the current user."""
    from .root_aggregate import DueDiligenceCase
    from django.db.models import Count, Q
    
    # Get user's cases
    user_cases = DueDiligenceCase.objects.filter(
        Q(lead_assessor=request.user) | Q(assessment_team=request.user),
        group=request.user.group
    ).distinct()
    
    # Calculate statistics
    stats = {
        'my_cases': {
            'total': user_cases.count(),
            'active': user_cases.filter(
                case_status__in=['initiated', 'data_collection', 'analysis', 'review']
            ).count(),
            'pending_decision': user_cases.filter(case_status='decision_pending').count(),
            'overdue': user_cases.filter(
                target_completion_date__lt=timezone.now().date(),
                case_status__in=['initiated', 'data_collection', 'analysis', 'review']
            ).count(),
        },
        'by_priority': dict(
            user_cases.values('priority').annotate(count=Count('id')).values_list('priority', 'count')
        ),
        'recent_activity': user_cases.order_by('-updated_at')[:5].values(
            'id', 'case_reference', 'case_name', 'case_status', 'updated_at'
        ),
    }
    
    return APIResponseMixin.success_response(data=stats)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_update_checklist_items(request):
    """Bulk update checklist items."""
    from .root_aggregate import CaseChecklistItem
    
    mixin = BulkOperationsMixin()
    
    updates = request.data.get('updates', [])
    if not updates:
        return mixin.error_response(
            message="No updates provided",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Filter to user's group
    for update in updates:
        update['group'] = request.user.group
    
    return mixin.bulk_update_response(CaseChecklistItem, updates)