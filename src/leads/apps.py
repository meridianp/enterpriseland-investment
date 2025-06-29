from django.apps import AppConfig


class LeadsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'leads'
    verbose_name = 'Lead Management'
    
    def ready(self):
        """Import signals when app is ready."""
        try:
            import leads.signals  # noqa
        except ImportError:
            pass
