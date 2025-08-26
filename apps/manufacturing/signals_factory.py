from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from apps.manufacturing.models import BidFactory
from apps.core.services.mongo import get_collection, ensure_indexes, now_iso_with_minutes
from apps.core.services.factory_steps_template import build_factory_steps_template


def _extract_phase_from_bid(bid: BidFactory) -> str:
    """Derive phase from bid context. For now default to 'sample'.
    If later you add explicit field for main production, adjust here.
    """
    # Placeholder: determine via request_order/product or future flag
    return 'sample'


@receiver(post_save, sender=BidFactory)
def upsert_factory_order_on_award(sender, instance: BidFactory, created: bool, **kwargs):
    """LEGACY (factory_orders) upsert hook.

    NOTE: Unified Mongo collection 'orders' is now the single source of truth.
    If settings.MONGODB_COLLECTIONS does NOT contain 'factory_orders', this
    handler becomes a NO-OP to avoid KeyError and duplicate documents.

    Retained temporarily for backward compatibility; safe to remove once
    legacy data paths are fully deprecated.
    """
    # Skip entirely if unified collection active (no legacy key)
    collections = getattr(settings, 'MONGODB_COLLECTIONS', {}) or {}
    if 'factory_orders' not in collections:
        return

    # Only act when the bid is marked as matched
    if not instance.is_matched:
        return

    try:
        ensure_indexes()
    except Exception:
        pass

    # Resolve references
    req = instance.request_order
    order = req.order
    product = order.product
    factory = instance.factory

    order_id = str(order.order_id)
    product_id = str(product.id) if product and product.id else None
    designer_id = str(product.designer.id) if getattr(product, 'designer', None) else None
    factory_id = str(factory.id) if factory and factory.id else None

    phase = _extract_phase_from_bid(instance)  # 'sample' or 'main'

    base_doc = {
        'order_id': order_id,
        'phase': phase,
        'factory_id': factory_id,
        'designer_id': designer_id,
        'product_id': product_id,
    }

    # Business fields from bid/request
    # Convert date to ISO string for Mongo compatibility
    expect_date = getattr(instance, 'expect_work_day', None)
    if hasattr(expect_date, 'isoformat'):
        try:
            expect_date = expect_date.isoformat()
        except Exception:
            expect_date = None

    business_fields = {
        'quantity': getattr(req, 'quantity', None),
        'unit_price': getattr(instance, 'work_price', None),
        'currency': 'KRW',
        'due_date': expect_date,
        'delivery_status': '',
        'delivery_code': '',
    }

    # Safe access (guarded above)
    col = get_collection(collections['factory_orders'])

    update_doc = {
        '$setOnInsert': {
            **base_doc,
            'current_step_index': 1,
            'overall_status': '',
            'steps': build_factory_steps_template(phase),
        },
        '$set': {
            # business fields only here to avoid conflicts on insert
            **business_fields,
            'last_updated': now_iso_with_minutes(),
        },
    }

    try:
        col.update_one(
            {'order_id': base_doc['order_id'], 'phase': base_doc['phase'], 'factory_id': base_doc['factory_id']},
            update_doc,
            upsert=True,
        )
    except Exception as e:
        print(f"[Mongo] Upsert factory_orders failed for order_id={order_id}, phase={phase}, factory_id={factory_id}: {e}")
