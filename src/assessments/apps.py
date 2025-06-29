
from django.apps import AppConfig

class AssessmentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'assessments'
    
    def ready(self):
        try:
            import assessments.signals
        except ImportError as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to import assessments.signals: {e}")
