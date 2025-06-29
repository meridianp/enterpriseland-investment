"""
OpenAPI schema customization for the CASA Due Diligence Platform.

Provides preprocessing and postprocessing hooks for enhanced API documentation.
"""

from typing import Dict, Any, List
from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


def preprocessing_filter_spec(endpoints):
    """
    Preprocessing hook to filter and customize API endpoints.
    
    Args:
        endpoints: List of endpoint tuples
        
    Returns:
        Filtered list of endpoints with customizations
    """
    filtered = []
    
    for endpoint in endpoints:
        # Handle both 3-tuple and 4-tuple formats
        if len(endpoint) == 3:
            path, method, callback = endpoint
        else:
            path, method, callback = endpoint[0], endpoint[1], endpoint[2]
        # Skip internal Django admin endpoints
        if path.startswith('/admin/'):
            continue
            
        # Skip debug endpoints in production
        if path.startswith('/__debug__/'):
            continue
            
        # Add custom tags based on path patterns
        if hasattr(callback, 'cls'):
            viewset = callback.cls
            
            # Add tags based on app and viewset name
            if 'assessment' in viewset.__name__.lower():
                if not hasattr(viewset, 'tags'):
                    viewset.tags = ['Assessments']
            elif 'partner' in viewset.__name__.lower():
                if not hasattr(viewset, 'tags'):
                    viewset.tags = ['Partners']
            elif 'scheme' in viewset.__name__.lower():
                if not hasattr(viewset, 'tags'):
                    viewset.tags = ['Schemes']
            elif 'risk' in viewset.__name__.lower():
                if not hasattr(viewset, 'tags'):
                    viewset.tags = ['Risk Analysis']
            elif 'performance' in viewset.__name__.lower():
                if not hasattr(viewset, 'tags'):
                    viewset.tags = ['Performance']
        
        # Preserve the original tuple format
        filtered.append(endpoint)
    
    return filtered


def postprocessing_hook(result: Dict[str, Any], generator, request, public: bool) -> Dict[str, Any]:
    """
    Postprocessing hook to enhance the generated OpenAPI schema.
    
    Args:
        result: Generated OpenAPI schema dictionary
        generator: Schema generator instance
        request: HTTP request instance
        public: Whether this is for public documentation
        
    Returns:
        Enhanced OpenAPI schema
    """
    # Add custom security schemes
    if 'components' not in result:
        result['components'] = {}
    
    if 'securitySchemes' not in result['components']:
        result['components']['securitySchemes'] = {}
    
    # Enhanced JWT security scheme
    result['components']['securitySchemes']['JWTAuth'] = {
        'type': 'http',
        'scheme': 'bearer',
        'bearerFormat': 'JWT',
        'description': 'JWT token authentication. Obtain token from /api/auth/login/ endpoint.'
    }
    
    # Add API key authentication for webhook endpoints
    result['components']['securitySchemes']['ApiKeyAuth'] = {
        'type': 'apiKey',
        'in': 'header',
        'name': 'X-API-Key',
        'description': 'API key for webhook and system integrations.'
    }
    
    # Add global security requirement
    if 'security' not in result:
        result['security'] = []
    
    result['security'].append({'JWTAuth': []})
    
    # Add custom response examples
    if 'components' in result and 'schemas' in result['components']:
        _add_response_examples(result['components']['schemas'])
    
    # Add rate limiting information to operation descriptions
    if 'paths' in result:
        _add_rate_limiting_info(result['paths'])
    
    # Add pagination information
    _add_pagination_info(result)
    
    return result


def _add_response_examples(schemas: Dict[str, Any]) -> None:
    """Add response examples to schema components."""
    
    # Example for Assessment model
    if 'Assessment' in schemas:
        schemas['Assessment']['example'] = {
            'id': '123e4567-e89b-12d3-a456-426614174000',
            'assessment_type': 'COMBINED',
            'status': 'APPROVED',
            'decision': 'Premium/Priority',
            'total_score': 185,
            'created_at': '2024-01-15T10:30:00Z',
            'updated_at': '2024-01-16T14:20:00Z',
            'version': '1.0.0'
        }
    
    # Example for DevelopmentPartner model
    if 'DevelopmentPartner' in schemas:
        schemas['DevelopmentPartner']['example'] = {
            'id': '987fcdeb-51a2-43d1-9f12-345678901234',
            'company_name': 'Urban Living Developers Ltd',
            'trading_name': 'ULD',
            'headquarter_city': 'London',
            'headquarter_country': 'GB',
            'year_established': 2010,
            'number_of_employees': 150,
            'completed_pbsa_schemes': 12,
            'total_pbsa_beds_delivered': 3200
        }
    
    # Example for error responses
    schemas['ErrorResponse'] = {
        'type': 'object',
        'properties': {
            'error': {
                'type': 'string',
                'description': 'Error message'
            },
            'detail': {
                'type': 'string',
                'description': 'Detailed error information'
            },
            'code': {
                'type': 'string',
                'description': 'Error code for programmatic handling'
            }
        },
        'example': {
            'error': 'Validation failed',
            'detail': 'The provided data does not meet validation requirements',
            'code': 'VALIDATION_ERROR'
        }
    }


def _add_rate_limiting_info(paths: Dict[str, Any]) -> None:
    """Add rate limiting information to operation descriptions."""
    
    rate_limits = {
        'GET': '100 requests per minute',
        'POST': '50 requests per minute', 
        'PUT': '50 requests per minute',
        'PATCH': '50 requests per minute',
        'DELETE': '20 requests per minute'
    }
    
    for path, methods in paths.items():
        for method, operation in methods.items():
            if method.upper() in rate_limits:
                if 'description' not in operation:
                    operation['description'] = ''
                
                rate_limit = rate_limits[method.upper()]
                operation['description'] += f'\n\n**Rate Limit:** {rate_limit}'


def _add_pagination_info(result: Dict[str, Any]) -> None:
    """Add pagination information to the schema."""
    
    if 'components' not in result:
        result['components'] = {}
    
    if 'schemas' not in result['components']:
        result['components']['schemas'] = {}
    
    # Add pagination schema
    result['components']['schemas']['PaginatedResponse'] = {
        'type': 'object',
        'properties': {
            'count': {
                'type': 'integer',
                'description': 'Total number of items'
            },
            'next': {
                'type': 'string',
                'nullable': True,
                'description': 'URL to next page of results'
            },
            'previous': {
                'type': 'string', 
                'nullable': True,
                'description': 'URL to previous page of results'
            },
            'results': {
                'type': 'array',
                'description': 'Array of result items'
            }
        },
        'example': {
            'count': 150,
            'next': 'http://api.example.com/assessments/?page=3',
            'previous': 'http://api.example.com/assessments/?page=1',
            'results': []
        }
    }


class CustomAutoSchema(AutoSchema):
    """
    Custom AutoSchema class for enhanced OpenAPI schema generation.
    
    Provides additional customization beyond what hooks can accomplish.
    """
    
    def get_operation_id(self, path: str, method: str) -> str:
        """Generate more meaningful operation IDs."""
        operation_id = super().get_operation_id(path, method)
        
        # Clean up operation IDs to be more descriptive
        replacements = {
            'assessments_assessments': 'assessments',
            'assessments_partners': 'partners',
            'assessments_schemes': 'schemes',
        }
        
        for old, new in replacements.items():
            operation_id = operation_id.replace(old, new)
        
        return operation_id
    
    def get_tags(self) -> List[str]:
        """Get tags for the operation."""
        tags = super().get_tags()
        
        # Add custom tags based on the view
        if hasattr(self.target, 'tags'):
            return self.target.tags
        
        return tags
    
    def get_operation(self, path: str, method: str) -> Dict[str, Any]:
        """Customize the operation dictionary."""
        operation = super().get_operation(path, method)
        
        # Add common responses
        if 'responses' not in operation:
            operation['responses'] = {}
        
        # Add standard error responses
        if '400' not in operation['responses']:
            operation['responses']['400'] = {
                'description': 'Bad Request',
                'content': {
                    'application/json': {
                        'schema': {'$ref': '#/components/schemas/ErrorResponse'}
                    }
                }
            }
        
        if '401' not in operation['responses']:
            operation['responses']['401'] = {
                'description': 'Unauthorized',
                'content': {
                    'application/json': {
                        'schema': {'$ref': '#/components/schemas/ErrorResponse'}
                    }
                }
            }
        
        if '403' not in operation['responses']:
            operation['responses']['403'] = {
                'description': 'Forbidden',
                'content': {
                    'application/json': {
                        'schema': {'$ref': '#/components/schemas/ErrorResponse'}
                    }
                }
            }
        
        return operation


# Custom serializer extensions for enhanced documentation

class MoneyFieldExtension(OpenApiSerializerExtension):
    """Extension for Money field documentation."""
    
    target_class = 'assessments.value_objects.MoneyField'
    
    def map_serializer(self, auto_schema, direction):
        return {
            'type': 'object',
            'properties': {
                'amount': {
                    'type': 'string',
                    'format': 'decimal',
                    'description': 'Monetary amount with decimal precision'
                },
                'currency': {
                    'type': 'string',
                    'enum': ['AED', 'EUR', 'GBP', 'SAR', 'USD'],
                    'description': 'ISO 4217 currency code'
                }
            },
            'required': ['amount', 'currency'],
            'example': {
                'amount': '1250000.00',
                'currency': 'GBP'
            }
        }


class AreaFieldExtension(OpenApiSerializerExtension):
    """Extension for Area field documentation."""
    
    target_class = 'assessments.value_objects.AreaField'
    
    def map_serializer(self, auto_schema, direction):
        return {
            'type': 'object',
            'properties': {
                'value': {
                    'type': 'string',
                    'format': 'decimal',
                    'description': 'Area value with decimal precision'
                },
                'unit': {
                    'type': 'string',
                    'enum': ['SQ_FT', 'SQ_M'],
                    'description': 'Unit of measurement'
                }
            },
            'required': ['value', 'unit'],
            'example': {
                'value': '2500.00',
                'unit': 'SQ_M'
            }
        }