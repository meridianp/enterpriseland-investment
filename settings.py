"""
Investment Module Settings
"""

# Module configuration
INVESTMENT_MODULE_CONFIG = {
    "LEAD_SCORING_ENABLED": True,
    "MARKET_INTELLIGENCE_ENABLED": True,
    "ASSESSMENT_WORKFLOW_ENABLED": True,
    "HUBSPOT_INTEGRATION_ENABLED": False,
    
    # Scoring thresholds
    "LEAD_SCORING_THRESHOLDS": {
        "qualified": 70,
        "interested": 50,
        "unqualified": 30
    },
    
    # Market intelligence settings
    "MARKET_INTEL_CONFIG": {
        "news_sources": [
            "techcrunch.com",
            "venturebeat.com", 
            "businessinsider.com"
        ],
        "update_frequency": "daily",
        "sentiment_analysis_enabled": True
    },
    
    # Deal workflow settings
    "DEAL_WORKFLOW_CONFIG": {
        "stages": [
            "initial_review",
            "due_diligence", 
            "negotiation",
            "closing"
        ],
        "auto_progression_enabled": False
    }
}
