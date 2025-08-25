from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductViewSet, OrderViewSet, submit_manufacturing, get_factory_orders, 
    get_designer_orders, create_factory_bid, get_bids_by_order, select_bid,
    get_factory_orders_mongo, advance_order_stage,
)

router = DefaultRouter()
router.register(r'products', ProductViewSet)
router.register(r'orders', OrderViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('submit/', submit_manufacturing, name='manufacturing-submit'),
    path('factory-orders/', get_factory_orders, name='factory-orders'),
    path('factory-orders-mongo/', get_factory_orders_mongo, name='factory-orders-mongo'),
    path('factory-orders/advance-stage/', advance_order_stage, name='factory-orders-advance-stage'),
    path('designer-orders/', get_designer_orders, name='designer-orders'),
    path('bids/', create_factory_bid, name='create-factory-bid'),
    path('bids/by_order/', get_bids_by_order, name='get-bids-by-order'),
    path('bids/<int:bid_id>/select/', select_bid, name='select-bid'),
]