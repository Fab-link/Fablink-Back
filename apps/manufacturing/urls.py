from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductViewSet, OrderViewSet, submit_manufacturing,
    create_factory_bid, get_bids_by_order, select_bid,
    get_orders_mongo, get_order_mongo, update_order_progress_mongo,
    has_factory_bid,
)

router = DefaultRouter()
router.register(r'products', ProductViewSet)
router.register(r'orders', OrderViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('submit/', submit_manufacturing, name='manufacturing-submit'),
    # Unified orders (Mongo) list & detail/progress
    path('orders/', get_orders_mongo, name='orders-mongo'),
    path('orders/<str:order_id>/', get_order_mongo, name='order-mongo-detail'),
    path('orders/<str:order_id>/progress/', update_order_progress_mongo, name='order-mongo-progress'),
    path('bids/', create_factory_bid, name='create-factory-bid'),
    path('bids/by_order/', get_bids_by_order, name='get-bids-by-order'),
    path('bids/has_bid/', has_factory_bid, name='has-factory-bid'),
    path('bids/<int:bid_id>/select/', select_bid, name='select-bid'),
]