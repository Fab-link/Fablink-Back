from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from apps.manufacturing.models import BidFactory
from apps.core.services.mongo import get_collection, ensure_indexes, now_iso_with_minutes
from apps.core.services.orders_steps_template import build_orders_steps_template


def _extract_phase_from_bid(bid: BidFactory) -> str:
    """Derive phase from bid context. For now default to 'sample'.
    If later you add explicit field for main production, adjust here.
    """
    # Placeholder: determine via request_order/product or future flag
    return 'sample'


@receiver(post_save, sender=BidFactory)
def upsert_factory_order_on_award(sender, instance: BidFactory, created: bool, **kwargs):
    """
    On bid award (is_matched=True), update unified 'orders' document for the order.
    Uses Option B: create/update when factory assignment happens.
    """
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
        'work_price': getattr(instance, 'work_price', None),
        'due_date': expect_date,
    }

    col = get_collection(settings.MONGODB_COLLECTIONS['orders'])

    update_doc = {
        '$setOnInsert': {
            **base_doc,
            'current_step_index': 1,
            'overall_status': '',
            # unified schema steps
            'steps': build_orders_steps_template(),
        },
        '$set': {
            'designer_id': designer_id,
            'product_id': product_id,
            'factory_id': factory_id,
            'phase': phase,
            **business_fields,
            'last_updated': now_iso_with_minutes(),
        },
    }

    try:
        col.update_one({'order_id': base_doc['order_id']}, update_doc, upsert=True)
    except Exception as e:
        print(f"[Mongo] Upsert orders failed for order_id={order_id}: {e}")
