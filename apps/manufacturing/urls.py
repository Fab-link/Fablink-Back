from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductViewSet, OrderViewSet, submit_manufacturing, get_factory_orders,
    get_designer_orders, create_factory_bid, get_bids_by_order, select_bid,
    get_factory_orders_mongo, get_order_mongo, update_order_progress_mongo,
)

router = DefaultRouter()
router.register(r'products', ProductViewSet)
router.register(r'orders', OrderViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('submit/', submit_manufacturing, name='manufacturing-submit'),
    path('factory-orders/', get_factory_orders, name='factory-orders'),
    path('factory-orders-mongo/', get_factory_orders_mongo, name='factory-orders-mongo'),
    # Mongo 단일 주문 조회 / 진행 업데이트
    path('orders-mongo/<str:order_id>/', get_order_mongo, name='order-mongo-detail'),
    path('orders-mongo/<str:order_id>/progress/', update_order_progress_mongo, name='order-mongo-progress'),
    path('designer-orders/', get_designer_orders, name='designer-orders'),
    path('bids/', create_factory_bid, name='create-factory-bid'),
    path('bids/by_order/', get_bids_by_order, name='get-bids-by-order'),
    path('bids/<int:bid_id>/select/', select_bid, name='select-bid'),
]