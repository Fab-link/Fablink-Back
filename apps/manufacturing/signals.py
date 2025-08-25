from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone

from apps.manufacturing.models import Order
from apps.core.services.mongo import get_collection, ensure_indexes, now_iso_with_minutes
from apps.core.services.designer_steps_template import build_designer_steps_template


@receiver(post_save, sender=Order)
def create_or_update_designer_order(sender, instance: Order, created: bool, **kwargs):
    """On Order creation, upsert a corresponding document in MongoDB designer_orders."""
    # Ensure indexes (idempotent; considered cheap. Alternatively move to app ready())
    try:
        ensure_indexes()
    except Exception:
        # Don't block SQL commit due to Mongo index issues
        pass

    # Gather required fields
    order_id = instance.order_id  # BigAutoField -> int

    # Resolve designer_id and product_id
    product = instance.product
    product_id = product.id
    designer_id = getattr(product.designer, 'id', None)

    order_id_str = str(order_id)
    designer_id_str = str(designer_id) if designer_id is not None else None
    product_id_str = str(product_id) if product_id is not None else None

    # Upsert into collection
    col = get_collection(settings.MONGODB_COLLECTIONS['designer_orders'])

    # set defaults for steps only if creating new; avoid overwriting user progress later
    # IMPORTANT: Do not update the same field in both $set and $setOnInsert to prevent conflicts.
    update_doc = {
        '$setOnInsert': {
            'order_id': order_id_str,
            'current_step_index': 1,  # small integer per latest requirement
            'overall_status': '',  # field exists; later changes via dedicated triggers
            'steps': build_designer_steps_template(),
        },
        '$set': {
            'designer_id': designer_id_str,
            'product_id': product_id_str,
            'last_updated': now_iso_with_minutes(),
        },
    }

    try:
        # Keep order_id out of $set to avoid conflicts; set only on insert above
        col.update_one({'order_id': order_id_str}, update_doc, upsert=True)
    except Exception as e:
        # Log minimal info; do not raise to avoid breaking request flow
        # You may integrate with logging/Sentry
        print(f"[Mongo] Upsert designer_orders failed for order_id={order_id_str}: {e}")
