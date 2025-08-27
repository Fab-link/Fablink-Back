from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone
import logging

from apps.manufacturing.models import Order
# 통합 NoSQL 서비스 사용 (환경별 자동 분기: local=MongoDB, dev/prod=DynamoDB)
from apps.core.services.nosql import get_collection, now_iso_with_minutes
from apps.core.services.orders_steps_template import build_orders_steps_template

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Order)
def create_or_update_unified_order(sender, instance: Order, created: bool, **kwargs):
    """On Order creation/update, upsert a corresponding document in unified MongoDB 'orders'.

    Legacy designer_orders/factory_orders will be deprecated; this keeps backward compatibility minimal.
    """
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
    col = get_collection('orders')

    # ----- Initial meta field derivation (schema alignment) -----
    # Product meta
    product_name = getattr(product, 'name', '') or ''
    product_quantity = getattr(product, 'quantity', None)
    if product_quantity is None:
        product_quantity = 0
    product_due_date = getattr(product, 'due_date', None)
    if product_due_date:
        try:
            product_due_date = product_due_date.isoformat()
        except Exception:
            product_due_date = ''
    else:
        product_due_date = ''

    # Designer meta
    designer = getattr(product, 'designer', None)
    designer_name = getattr(designer, 'name', '') if designer else ''
    designer_contact = getattr(designer, 'contact', '') if designer else ''

    # Factory meta (none at initial creation)
    factory_id = ''
    factory_name = ''
    factory_contact = ''
    factory_address = ''

    # Order meta
    order_date = timezone.now().date().isoformat()

    # ----- Document update spec -----
    # IMPORTANT: Avoid putting same key in both $setOnInsert and $set.
    update_doc = {
        '$setOnInsert': {
            'order_id': order_id_str,
            'current_step_index': 1,
            'overall_status': '',
            'phase': 'sample',  # default initial phase
            'steps': build_orders_steps_template(),
            # schema meta initial snapshot
            'product_name': product_name,
            'quantity': product_quantity,
            'due_date': product_due_date,
            'designer_name': designer_name,
            'designer_contact': designer_contact,
            'work_price': 0,  # until bids populate
            'factory_id': factory_id,
            'factory_name': factory_name,
            'factory_contact': factory_contact,
            'factory_address': factory_address,
            'order_date': order_date,
        },
        '$set': {
            # stable references & mutable timestamps
            'designer_id': designer_id_str,
            'product_id': product_id_str,
            'last_updated': now_iso_with_minutes(),
        },
    }

    try:
        # Keep order_id out of $set to avoid conflicts; set only on insert above
        col.update_one({'order_id': order_id_str}, update_doc, upsert=True)
    except Exception as e:
        logger.warning(
            "[Mongo] Upsert unified orders failed for order_id=%s: %s",
            order_id_str,
            e,
        )
