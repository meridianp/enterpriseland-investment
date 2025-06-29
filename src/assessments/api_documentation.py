"""
API Documentation for CASA Due Diligence Platform - Phase 7.

Provides comprehensive OpenAPI documentation for all assessment endpoints
to support frontend development with clear schemas and examples.
"""

from drf_spectacular.utils import (
    extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample,
    inline_serializer, OpenApiResponse
)
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers

# Common parameters used across multiple endpoints
COMMON_PARAMETERS = {
    'group_filter': OpenApiParameter(
        name='group',
        description='Filter by group ID (automatically applied based on user permissions)',
        required=False,
        type=OpenApiTypes.UUID,
        location=OpenApiParameter.QUERY,
    ),
    'search': OpenApiParameter(
        name='search',
        description='Search across multiple fields',
        required=False,
        type=OpenApiTypes.STR,
        location=OpenApiParameter.QUERY,
    ),
    'ordering': OpenApiParameter(
        name='ordering',
        description='Order results by field (prefix with - for descending)',
        required=False,
        type=OpenApiTypes.STR,
        location=OpenApiParameter.QUERY,
    ),
    'page': OpenApiParameter(
        name='page',
        description='Page number for pagination',
        required=False,
        type=OpenApiTypes.INT,
        location=OpenApiParameter.QUERY,
    ),
    'page_size': OpenApiParameter(
        name='page_size',
        description='Number of results per page',
        required=False,
        type=OpenApiTypes.INT,
        location=OpenApiParameter.QUERY,
    ),
}

# Due Diligence Case Documentation
due_diligence_case_list_docs = extend_schema(
    summary="List Due Diligence Cases",
    description="""
    Retrieve a paginated list of due diligence cases.
    
    ## Filtering Options
    - **case_status**: Filter by one or more statuses
    - **priority**: Filter by priority level (urgent, high, medium, low)
    - **is_overdue**: Show only overdue cases
    - **my_cases**: Show only cases where user is lead or team member
    - **date ranges**: Filter by creation, target, or completion dates
    
    ## Ordering
    Default ordering is by creation date (newest first).
    Available fields: created_at, target_completion_date, priority, case_status
    """,
    parameters=[
        COMMON_PARAMETERS['search'],
        COMMON_PARAMETERS['ordering'],
        COMMON_PARAMETERS['page'],
        COMMON_PARAMETERS['page_size'],
        OpenApiParameter(
            name='case_status',
            description='Filter by case status (multiple allowed)',
            required=False,
            type={'type': 'array', 'items': {'type': 'string'}},
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name='is_overdue',
            description='Filter for overdue cases only',
            required=False,
            type=OpenApiTypes.BOOL,
            location=OpenApiParameter.QUERY,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description="Paginated list of due diligence cases",
            examples=[
                OpenApiExample(
                    'Success Response',
                    value={
                        "count": 25,
                        "next": "http://api.example.com/api/due-diligence/cases/?page=2",
                        "previous": None,
                        "results": [
                            {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "case_reference": "DD20240001",
                                "case_name": "ABC Development Partner Assessment",
                                "case_type": "full_dd",
                                "case_status": "analysis",
                                "priority": "high",
                                "completion_percentage": 50,
                                "is_overdue": False,
                                "days_until_due": 15,
                                "primary_partner": {
                                    "id": "456e7890-e89b-12d3-a456-426614174000",
                                    "company_name": "ABC Development Ltd"
                                },
                                "scheme_count": 2,
                                "overall_risk_level": "medium",
                                "lead_assessor": {
                                    "id": "789e0123-e89b-12d3-a456-426614174000",
                                    "name": "John Smith",
                                    "email": "john.smith@example.com"
                                },
                                "created_at": "2024-01-15T10:30:00Z",
                                "target_completion_date": "2024-02-15"
                            }
                        ]
                    }
                )
            ]
        ),
    },
    tags=['Due Diligence Cases']
)

due_diligence_case_create_docs = extend_schema(
    summary="Create Due Diligence Case",
    description="""
    Create a new due diligence case with automatic checklist generation.
    
    ## Case Types
    - **partner_only**: Assessment of partner only
    - **scheme_only**: Assessment of schemes only
    - **full_dd**: Complete due diligence (partner + schemes)
    - **portfolio**: Portfolio-wide assessment
    
    ## Automatic Features
    - Case reference auto-generated (DD20240001 format)
    - Standard checklist items created based on case type
    - Initial timeline event recorded
    - Lead assessor defaults to current user if not specified
    """,
    request=inline_serializer(
        name='DueDiligenceCaseCreate',
        fields={
            'case_name': serializers.CharField(required=True, help_text="Descriptive name for the case"),
            'case_type': serializers.ChoiceField(
                choices=['partner_only', 'scheme_only', 'full_dd', 'portfolio'],
                required=True,
                help_text="Type of due diligence"
            ),
            'primary_partner': serializers.UUIDField(required=False, help_text="Primary partner ID"),
            'schemes': serializers.ListField(
                child=serializers.UUIDField(),
                required=False,
                help_text="List of scheme IDs"
            ),
            'priority': serializers.ChoiceField(
                choices=['urgent', 'high', 'medium', 'low'],
                default='medium',
                help_text="Priority level"
            ),
            'target_completion_date': serializers.DateField(
                required=False,
                help_text="Target completion date (YYYY-MM-DD)"
            ),
            'assessment_team': serializers.ListField(
                child=serializers.UUIDField(),
                required=False,
                help_text="Team member user IDs"
            ),
            'total_investment_amount': serializers.DecimalField(
                max_digits=20,
                decimal_places=2,
                required=False,
                help_text="Total investment amount"
            ),
            'total_investment_currency': serializers.ChoiceField(
                choices=['GBP', 'EUR', 'USD'],
                required=False,
                help_text="Investment currency"
            ),
        }
    ),
    responses={
        201: OpenApiResponse(
            description="Case created successfully with details",
        ),
        400: OpenApiResponse(
            description="Validation error",
            examples=[
                OpenApiExample(
                    'Validation Error',
                    value={
                        "case_type": ["Partner is required for partner_only case type"],
                        "target_completion_date": ["Date cannot be in the past"]
                    }
                )
            ]
        ),
    },
    tags=['Due Diligence Cases']
)

transition_status_docs = extend_schema(
    summary="Transition Case Status",
    description="""
    Transition a due diligence case to a new status.
    
    ## Valid Transitions
    - **initiated** → data_collection, on_hold, archived
    - **data_collection** → analysis, on_hold, archived
    - **analysis** → review, on_hold, archived
    - **review** → decision_pending, analysis, on_hold, archived
    - **decision_pending** → approved, rejected, on_hold, archived
    - **approved** → completed, archived
    - **rejected** → completed, archived
    - **on_hold** → data_collection, analysis, review, archived
    - **completed** → archived
    
    ## Effects
    - Creates timeline event
    - Updates workflow history
    - Sends notifications to team
    - Creates audit trail entry
    """,
    request=inline_serializer(
        name='StatusTransition',
        fields={
            'new_status': serializers.ChoiceField(
                choices=[
                    'data_collection', 'analysis', 'review', 'decision_pending',
                    'approved', 'rejected', 'on_hold', 'completed', 'archived'
                ],
                required=True,
                help_text="Target status"
            ),
            'notes': serializers.CharField(
                required=False,
                help_text="Reason for transition"
            ),
        }
    ),
    responses={
        200: OpenApiResponse(
            description="Status transitioned successfully",
            examples=[
                OpenApiExample(
                    'Success',
                    value={
                        "status": "success",
                        "new_status": "analysis",
                        "message": "Case transitioned to Analysis in Progress"
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Invalid transition",
            examples=[
                OpenApiExample(
                    'Invalid Transition',
                    value={
                        "status": "error",
                        "message": "Invalid status transition from initiated to approved"
                    }
                )
            ]
        ),
    },
    tags=['Due Diligence Cases']
)

make_decision_docs = extend_schema(
    summary="Make Investment Decision",
    description="""
    Record final investment decision on a due diligence case.
    
    ## Decision Types
    - **proceed**: Proceed with investment
    - **conditional**: Proceed with conditions
    - **decline**: Decline investment
    - **defer**: Defer decision
    
    ## Requirements
    - Case must be in 'decision_pending' status
    - Conditions required for 'conditional' decision
    - Decision maker recorded as current user
    
    ## Effects
    - Updates case status (approved/rejected/on_hold)
    - Records decision date and maker
    - Creates significant timeline event
    - High-risk audit trail entry
    - Sends notifications to stakeholders
    """,
    request=inline_serializer(
        name='InvestmentDecision',
        fields={
            'decision': serializers.ChoiceField(
                choices=['proceed', 'conditional', 'decline', 'defer'],
                required=True,
                help_text="Investment decision"
            ),
            'conditions': serializers.ListField(
                child=serializers.CharField(),
                required=False,
                help_text="List of conditions (required for conditional decision)"
            ),
            'notes': serializers.CharField(
                required=False,
                help_text="Decision justification"
            ),
        }
    ),
    responses={
        200: OpenApiResponse(
            description="Decision recorded successfully",
        ),
        400: OpenApiResponse(
            description="Invalid decision",
        ),
    },
    tags=['Due Diligence Cases']
)

dashboard_docs = extend_schema(
    summary="Get Dashboard Summary",
    description="""
    Retrieve dashboard summary statistics for due diligence cases.
    
    ## Summary Statistics
    - Total cases and status breakdown
    - Overdue cases and upcoming deadlines
    - Priority distribution
    - Risk level distribution
    - Recent decisions
    - Investment summary by currency
    
    ## Use Cases
    - Dashboard widgets
    - Management reporting
    - Team workload overview
    - Portfolio summary
    """,
    parameters=[
        OpenApiParameter(
            name='date_from',
            description='Filter cases created from this date',
            required=False,
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name='date_to',
            description='Filter cases created until this date',
            required=False,
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description="Dashboard summary data",
            examples=[
                OpenApiExample(
                    'Dashboard Response',
                    value={
                        "summary": {
                            "total_cases": 45,
                            "overdue_cases": 3,
                            "due_this_week": 5,
                            "active_cases": 28,
                            "completed_cases": 17
                        },
                        "distributions": {
                            "by_status": {
                                "initiated": 5,
                                "data_collection": 8,
                                "analysis": 10,
                                "review": 3,
                                "decision_pending": 2,
                                "completed": 17
                            },
                            "by_priority": {
                                "urgent": 2,
                                "high": 12,
                                "medium": 25,
                                "low": 6
                            },
                            "by_risk": {
                                "low": 15,
                                "medium": 20,
                                "high": 8,
                                "critical": 2
                            }
                        },
                        "recent_decisions": [
                            {
                                "case_reference": "DD20240015",
                                "case_name": "XYZ Properties Assessment",
                                "final_decision": "proceed",
                                "decision_date": "2024-01-20"
                            }
                        ],
                        "investment_summary": [
                            {
                                "total_investment_currency": "GBP",
                                "total_amount": "125000000.00",
                                "count": 15
                            }
                        ]
                    }
                )
            ]
        ),
    },
    tags=['Due Diligence Cases']
)

# Assessment Documentation
assessment_list_docs = extend_schema(
    summary="List Assessments",
    description="""
    Retrieve a paginated list of assessments.
    
    ## Assessment Types
    - **partner**: Partner capability assessment
    - **scheme**: Individual scheme assessment
    - **combined**: Combined partner and scheme assessment
    
    ## Filtering Options
    - **assessment_type**: Filter by type
    - **status**: Filter by assessment status
    - **decision_band**: Filter by decision outcome
    - **partner/scheme**: Filter by specific entities
    
    ## Scoring System
    - Score: 1-5 per metric
    - Weight: 1-5 importance factor
    - Weighted Score = Score × Weight
    - Decision Bands:
      - Premium Priority: >165
      - Acceptable: 125-165
      - Reject: <125
    """,
    parameters=[
        COMMON_PARAMETERS['search'],
        COMMON_PARAMETERS['ordering'],
        OpenApiParameter(
            name='assessment_type',
            description='Filter by assessment type',
            required=False,
            type=OpenApiTypes.STR,
            enum=['partner', 'scheme', 'combined'],
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name='status',
            description='Filter by assessment status',
            required=False,
            type=OpenApiTypes.STR,
            enum=['draft', 'submitted', 'under_review', 'completed', 'rejected'],
            location=OpenApiParameter.QUERY,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description="Paginated list of assessments",
        ),
    },
    tags=['Assessments']
)

# Compliance Documentation
compliance_analytics_docs = extend_schema(
    summary="Get Compliance Analytics",
    description="""
    Retrieve comprehensive compliance analytics and statistics.
    
    ## Analytics Provided
    - Compliance rate by category
    - Risk distribution
    - Expiring items summary
    - Non-compliance trends
    - Jurisdiction breakdown
    
    ## Use Cases
    - Compliance dashboards
    - Risk reporting
    - Renewal planning
    - Audit preparation
    """,
    parameters=[
        OpenApiParameter(
            name='entity_type',
            description='Filter by entity type',
            required=False,
            type=OpenApiTypes.STR,
            enum=['partner', 'scheme', 'all'],
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name='days_ahead',
            description='Days to look ahead for expiring items',
            required=False,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description="Compliance analytics data",
        ),
    },
    tags=['Regulatory Compliance']
)

# Performance Metrics Documentation
performance_trends_docs = extend_schema(
    summary="Get Performance Trends",
    description="""
    Retrieve performance metric trends over time.
    
    ## Trend Analysis
    - Time series data for specified metrics
    - Aggregation by period (daily, weekly, monthly)
    - Target vs actual comparison
    - Statistical analysis (min, max, avg, std dev)
    
    ## Metrics Available
    - Occupancy rates
    - Financial performance
    - Operational efficiency
    - Student satisfaction
    - Cost metrics
    """,
    parameters=[
        OpenApiParameter(
            name='metric_names',
            description='Comma-separated list of metric names',
            required=True,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name='date_from',
            description='Start date for trends',
            required=True,
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name='date_to',
            description='End date for trends',
            required=True,
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name='aggregation',
            description='Aggregation period',
            required=False,
            type=OpenApiTypes.STR,
            enum=['daily', 'weekly', 'monthly'],
            default='monthly',
            location=OpenApiParameter.QUERY,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description="Performance trend data",
        ),
    },
    tags=['Performance Metrics']
)

# ESG Documentation
esg_comparison_docs = extend_schema(
    summary="Compare ESG Assessments",
    description="""
    Compare ESG assessments across multiple entities.
    
    ## Comparison Features
    - Side-by-side ESG scores
    - Environmental, Social, Governance breakdowns
    - Rating comparison (AAA to CCC)
    - Carbon intensity metrics
    - Improvement areas identification
    
    ## Use Cases
    - Portfolio ESG analysis
    - Peer comparison
    - Investment screening
    - Sustainability reporting
    """,
    request=inline_serializer(
        name='ESGComparison',
        fields={
            'entity_ids': serializers.ListField(
                child=serializers.UUIDField(),
                min_length=2,
                max_length=10,
                help_text="List of entity IDs to compare (2-10)"
            ),
            'entity_type': serializers.ChoiceField(
                choices=['partner', 'scheme'],
                help_text="Type of entities"
            ),
            'latest_only': serializers.BooleanField(
                default=True,
                help_text="Compare only latest assessments"
            ),
        }
    ),
    responses={
        200: OpenApiResponse(
            description="ESG comparison data",
        ),
    },
    tags=['ESG Assessments']
)

# API Schema Configuration
API_SCHEMA_CONFIG = {
    'TITLE': 'CASA Due Diligence Platform API',
    'DESCRIPTION': """
    ## Overview
    The CASA Due Diligence Platform provides comprehensive API endpoints for managing
    development partner assessments, PBSA scheme evaluations, and investment decisions.
    
    ## Authentication
    All endpoints require JWT authentication. Include the token in the Authorization header:
    ```
    Authorization: Bearer <your-token>
    ```
    
    ## Permissions
    - All data is filtered by user's group membership
    - Role-based permissions apply (Admin, Manager, Analyst, Assessor, Viewer)
    - Some endpoints have additional role requirements (e.g., audit trails)
    
    ## Common Patterns
    - **Pagination**: List endpoints support page and page_size parameters
    - **Filtering**: Comprehensive filtering via query parameters
    - **Ordering**: Sort results using ordering parameter (prefix with - for descending)
    - **Search**: Full-text search across relevant fields
    
    ## Response Formats
    - **Success**: 200 OK, 201 Created
    - **Client Error**: 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found
    - **Server Error**: 500 Internal Server Error
    
    ## Rate Limiting
    - 1000 requests per hour for authenticated users
    - 100 requests per hour for unauthenticated requests
    """,
    'VERSION': '1.0.0',
    'CONTACT': {
        'name': 'CASA Platform Support',
        'email': 'support@casa-platform.com',
    },
    'SERVERS': [
        {
            'url': 'https://api.casa-platform.com',
            'description': 'Production server',
        },
        {
            'url': 'https://staging-api.casa-platform.com',
            'description': 'Staging server',
        },
        {
            'url': 'http://localhost:8000',
            'description': 'Local development server',
        },
    ],
    'TAGS': [
        {
            'name': 'Due Diligence Cases',
            'description': 'Core case management and workflow operations',
        },
        {
            'name': 'Assessments',
            'description': 'Partner and scheme assessment operations',
        },
        {
            'name': 'Regulatory Compliance',
            'description': 'Compliance tracking and monitoring',
        },
        {
            'name': 'Performance Metrics',
            'description': 'Performance measurement and analytics',
        },
        {
            'name': 'ESG Assessments',
            'description': 'Environmental, Social, and Governance evaluations',
        },
        {
            'name': 'Partners',
            'description': 'Development partner management',
        },
        {
            'name': 'Schemes',
            'description': 'PBSA scheme management',
        },
    ],
}

# Frontend Integration Examples
FRONTEND_INTEGRATION_EXAMPLES = {
    'authentication': """
    // Authentication flow example
    async function login(email, password) {
        const response = await fetch('/api/auth/login/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, password }),
        });
        
        const data = await response.json();
        if (response.ok) {
            localStorage.setItem('access_token', data.access);
            localStorage.setItem('refresh_token', data.refresh);
            return data;
        }
        throw new Error(data.detail || 'Login failed');
    }
    """,
    
    'case_list': """
    // Fetch due diligence cases with filtering
    async function fetchCases(filters = {}) {
        const params = new URLSearchParams(filters);
        const response = await fetch(`/api/due-diligence/cases/?${params}`, {
            headers: {
                'Authorization': `Bearer ${getAccessToken()}`,
            },
        });
        
        if (!response.ok) throw new Error('Failed to fetch cases');
        return response.json();
    }
    
    // Example usage
    const cases = await fetchCases({
        case_status: 'analysis,review',
        is_overdue: true,
        ordering: '-priority',
    });
    """,
    
    'workflow_transition': """
    // Transition case status
    async function transitionStatus(caseId, newStatus, notes) {
        const response = await fetch(
            `/api/due-diligence/cases/${caseId}/transition_status/`,
            {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${getAccessToken()}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    new_status: newStatus,
                    notes: notes,
                }),
            }
        );
        
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.message || 'Transition failed');
        }
        return data;
    }
    """,
    
    'real_time_updates': """
    // WebSocket connection for real-time updates
    const ws = new WebSocket('wss://api.casa-platform.com/ws/cases/');
    
    ws.onopen = () => {
        // Authenticate
        ws.send(JSON.stringify({
            type: 'auth',
            token: getAccessToken(),
        }));
        
        // Subscribe to case updates
        ws.send(JSON.stringify({
            type: 'subscribe',
            cases: ['case-id-1', 'case-id-2'],
        }));
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'case_update') {
            // Handle case update
            updateCaseInUI(data.case);
        }
    };
    """,
}

# Error Response Examples
ERROR_RESPONSE_EXAMPLES = {
    'validation_error': {
        'description': 'Validation error response',
        'value': {
            'type': 'validation_error',
            'errors': {
                'field_name': ['Error message 1', 'Error message 2'],
                'another_field': ['Another error message'],
            },
        },
    },
    'authentication_error': {
        'description': 'Authentication required',
        'value': {
            'detail': 'Authentication credentials were not provided.',
        },
    },
    'permission_error': {
        'description': 'Insufficient permissions',
        'value': {
            'detail': 'You do not have permission to perform this action.',
        },
    },
    'not_found_error': {
        'description': 'Resource not found',
        'value': {
            'detail': 'Not found.',
        },
    },
}