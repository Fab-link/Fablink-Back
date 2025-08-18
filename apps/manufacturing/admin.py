from django.contrib import admin
from .models import Product, Order, RequestOrder, BidFactory

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'designer', 'season', 'target', 'created_at')
    list_filter = ('season', 'target', 'created_at')
    # Designer 모델은 User FK가 없으므로 designer의 name/user_id로 직접 검색
    search_fields = ('name', 'designer__name', 'designer__user_id')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('name', 'designer', 'season', 'target', 'concept')
        }),
        ('상세 정보', {
            'fields': ('detail', 'image_path', 'size', 'quantity')
        }),
        ('소재 정보', {
            'fields': ('fabric', 'material')
        }),
        ('일정 및 메모', {
            'fields': ('due_date', 'memo', 'work_sheet_path')
        }),
        ('시스템 정보', {
            'fields': ('created_at', 'updated_at')
        }),
    )

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'product', 'get_designer_name')
    search_fields = ('order_id', 'product__name', 'product__designer__name')
    
    def get_designer_name(self, obj):
        # Designer 모델은 User FK가 없으므로 직접 name 접근
        return obj.product.designer.name
    get_designer_name.short_description = '디자이너'


@admin.register(RequestOrder)
class RequestOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'designer_name', 'product_name', 'quantity', 'due_date')
    list_filter = ('due_date', 'designer_name')
    search_fields = ('designer_name', 'product_name', 'order__order_id')
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('order', 'designer_name', 'product_name')
        }),
        ('주문 세부', {
            'fields': ('quantity', 'due_date', 'work_sheet_path')
        }),
    )


@admin.register(BidFactory)
class BidFactoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_factory_name', 'get_request_order_info', 'work_price', 
                   'expect_work_day', 'settlement_status', 'is_matched', 'matched_date')
    list_filter = ('settlement_status', 'is_matched', 'expect_work_day')
    search_fields = ('factory__name', 'request_order__product_name', 'request_order__designer_name')
    
    def get_factory_name(self, obj):
        return obj.factory.name
    get_factory_name.short_description = '공장명'
    
    def get_request_order_info(self, obj):
        return f"{obj.request_order.product_name} ({obj.request_order.designer_name})"
    get_request_order_info.short_description = '주문 정보'
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('factory', 'request_order')
        }),
        ('입찰 세부', {
            'fields': ('work_price', 'expect_work_day', 'settlement_status')
        }),
        ('낙찰 정보', {
            'fields': ('is_matched', 'matched_date')
        }),
    )