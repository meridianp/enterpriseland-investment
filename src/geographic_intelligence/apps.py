from django.apps import AppConfig


class GeographicIntelligenceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'geographic_intelligence'
    verbose_name = 'Geographic Intelligence'
    
    def ready(self):
        """Import signals when app is ready."""
        try:
            import geographic_intelligence.signals  # noqa F401
        except ImportError:
            pass
