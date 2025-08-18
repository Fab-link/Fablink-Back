from django.apps import AppConfig


def _ready_hook():
    # Import signal handlers
    from . import signals  # noqa: F401
    from . import signals_factory  # noqa: F401
    # Ensure Mongo indexes at startup (non-fatal if fails)
    try:
        from apps.core.services.mongo import ensure_indexes
        ensure_indexes()
    except Exception:
        pass


class ManufacturingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.manufacturing'
    
    def ready(self):
        _ready_hook()
