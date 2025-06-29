from django.apps import AppConfig


class MarketIntelligenceConfig(AppConfig):
    """
    Market Intelligence app configuration.
    
    Handles news scraping, target identification, and lead scoring
    for the PBSA investment lifecycle platform.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'market_intelligence'
    verbose_name = 'Market Intelligence'
    
    def ready(self):
        """Import signals when Django starts."""
        try:
            import market_intelligence.signals
        except ImportError as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to import market_intelligence.signals: {e}")
