from __future__ import annotations

from typing import Dict
from pymongo import MongoClient, ASCENDING
from django.conf import settings
from django.utils import timezone

_client: MongoClient | None = None


def get_mongo_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI)
    return _client


def get_db():
    return get_mongo_client()[settings.MONGODB_DB]


def get_collection(name: str):
    db = get_db()
    return db[name]


def ensure_indexes():
    """Ensure required indexes exist on collections."""
    try:
        col_orders = get_collection(settings.MONGODB_COLLECTIONS['orders'])
        col_orders.create_index([('order_id', ASCENDING)], unique=True, name='ux_order_id')
        col_orders.create_index([('factory_id', ASCENDING)], name='ix_factory_id')
        col_orders.create_index([('designer_id', ASCENDING)], name='ix_designer_id')
        col_orders.create_index([('overall_status', ASCENDING)], name='ix_overall_status')
        col_orders.create_index([('current_step_index', ASCENDING)], name='ix_current_step_index')
        # 자주 필터/정렬되는 추가 필드 인덱스 (체크리스트 기준): due_date / last_updated / phase
        try:
            col_orders.create_index([('due_date', ASCENDING)], name='ix_due_date')
        except Exception:
            pass
        try:
            col_orders.create_index([('last_updated', ASCENDING)], name='ix_last_updated')
        except Exception:
            pass
        try:
            col_orders.create_index([('phase', ASCENDING)], name='ix_phase')
        except Exception:
            pass
        try:
            col_orders.create_index([('steps.factory_list.factory_id', ASCENDING)], name='ix_steps_factory_list_factory_id')
        except Exception:
            pass
    except Exception:
        pass


def now_iso_with_minutes() -> str:
    """Return ISO string with timezone info (KST by Django TIME_ZONE), minute precision."""
    dt = timezone.now().astimezone(timezone.get_current_timezone())
    return dt.isoformat(timespec='minutes')
