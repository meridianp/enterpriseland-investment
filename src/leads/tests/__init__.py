"""
Comprehensive test suite for leads app.

Tests cover models, services, serializers, viewsets and business logic
to ensure 95%+ model coverage and 90%+ service coverage.
"""

# Test class imports for easier access
from .test_models import (
    LeadScoringModelTest,
    LeadModelTest,
    LeadActivityModelTest,
    ModelIntegrationTest,
)

from .test_services import (
    LeadScoringServiceTest,
    LeadWorkflowServiceTest,
    ServiceIntegrationTest,
)

from .test_serializers import (
    LeadScoringModelSerializerTest,
    LeadSerializerTest,
    LeadActivitySerializerTest,
)

from .test_viewsets import (
    LeadScoringModelViewSetTest,
    LeadViewSetTest,
    LeadActivityViewSetTest,
    ViewSetIntegrationTest,
)

__all__ = [
    # Model tests
    'LeadScoringModelTest',
    'LeadModelTest',
    'LeadActivityModelTest',
    'ModelIntegrationTest',
    
    # Service tests
    'LeadScoringServiceTest',
    'LeadWorkflowServiceTest',
    'ServiceIntegrationTest',
    
    # Serializer tests
    'LeadScoringModelSerializerTest',
    'LeadSerializerTest',
    'LeadActivitySerializerTest',
    
    # ViewSet tests
    'LeadScoringModelViewSetTest',
    'LeadViewSetTest',
    'LeadActivityViewSetTest',
    'ViewSetIntegrationTest',
]