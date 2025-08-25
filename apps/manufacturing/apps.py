from django.apps import AppConfig


def _ready_hook():
    # signals import 복구: Order post_save -> unified orders upsert 활성화
    # (이전 리베이스 과정에서 제거되어 Mongo 문서가 생성되지 않는 문제 발생)
    try:
        from . import signals  # noqa: F401
    except Exception:
        # 신속 부트 유지 (로그는 signals 내부 logger 사용 예상)
        pass
    try:
        from . import signals_factory  # noqa: F401 (레거시/추가 처리 유지 시)
    except Exception:
        pass
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
