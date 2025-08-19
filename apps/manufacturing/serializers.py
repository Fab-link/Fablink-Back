from rest_framework import serializers
from .models import Product, Order, RequestOrder, BidFactory
from apps.accounts.serializers import UserSerializer, DesignerSerializer, FactorySerializer

class ProductSerializer(serializers.ModelSerializer):
    """제품 시리얼라이저"""
    designer_info = DesignerSerializer(source='designer', read_only=True)
    image_url = serializers.SerializerMethodField()
    work_sheet_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'season', 'target', 'concept', 'detail', 
            'image_path', 'image_url', 'size', 'quantity', 'fabric', 
            'material', 'due_date', 'memo', 'work_sheet_path', 'work_sheet_url',
            'designer', 'designer_info', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'designer', 'created_at', 'updated_at']
    
    def get_image_url(self, obj):
        """이미지 URL 반환"""
        if obj.image_path:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image_path.url)
            return obj.image_path.url
        return None
    
    def get_work_sheet_url(self, obj):
        """작업지시서 URL 반환"""
        if obj.work_sheet_path:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.work_sheet_path.url)
            return obj.work_sheet_path.url
        return None


class ProductCreateSerializer(serializers.ModelSerializer):
    """제품 생성용 시리얼라이저"""
    target_customer = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'season', 'target', 'target_customer', 'concept', 'detail', 
            'image_path', 'size', 'quantity', 'fabric', 
            'material', 'due_date', 'memo', 'work_sheet_path'
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'image_path': {'required': False},
            'target': {'required': False}
        }
    
    def validate_name(self, value):
        """제품명 검증"""
        if not value or not value.strip():
            raise serializers.ValidationError("제품명은 필수입니다.")
        return value.strip()
    
    def validate_season(self, value):
        """시즌 검증"""
        valid_seasons = ['spring', 'summer', 'autumn', 'winter', 'all-season']
        if value not in valid_seasons:
            raise serializers.ValidationError(f"유효한 시즌을 선택해주세요: {', '.join(valid_seasons)}")
        return value
    
    def validate_target(self, value):
        """타겟 고객층 검증"""
        valid_targets = ['teens', 'twenties', 'thirties', 'forties', 'fifties-plus', 'all-ages']
        if value not in valid_targets:
            raise serializers.ValidationError(f"유효한 타겟 고객층을 선택해주세요: {', '.join(valid_targets)}")
        return value
    
    def validate_concept(self, value):
        """컨셉 검증"""
        if not value or not value.strip():
            raise serializers.ValidationError("컨셉 설명은 필수입니다.")
        return value.strip()
    
    def validate_quantity(self, value):
        """수량 검증"""
        if value is not None and value <= 0:
            raise serializers.ValidationError("수량은 1 이상이어야 합니다.")
        return value
    
    def validate(self, attrs):
        """전체 데이터 검증"""
        # target_customer를 target으로 매핑
        if 'target_customer' in attrs:
            attrs['target'] = attrs.pop('target_customer')
        
        # 필수 필드 검증
        required_fields = ['name', 'season', 'target', 'concept']
        for field in required_fields:
            if field not in attrs or not attrs[field]:
                raise serializers.ValidationError(f"{field} 필드는 필수입니다.")
        
        return attrs


class ProductListSerializer(serializers.ModelSerializer):
    """제품 목록용 간단한 시리얼라이저"""
    # Designer는 User FK가 없으므로 직접 name 사용
    designer_name = serializers.CharField(source='designer.name', read_only=True)
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'season', 'target', 'concept', 
            'image_path', 'image_url', 'quantity', 'due_date',
            'designer', 'designer_name', 'created_at'
        ]
    
    def get_image_url(self, obj):
        """이미지 URL 반환"""
        if obj.image_path:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image_path.url)
            return obj.image_path.url
        return None


class OrderSerializer(serializers.ModelSerializer):
    """주문 시리얼라이저"""
    product_info = ProductListSerializer(source='product', read_only=True)
    
    class Meta:
        model = Order
        fields = ['order_id', 'product', 'product_info']
        read_only_fields = ['order_id']


class OrderCreateSerializer(serializers.ModelSerializer):
    """주문 생성용 시리얼라이저"""
    
    class Meta:
        model = Order
        fields = ['product']


class RequestOrderSerializer(serializers.ModelSerializer):
    """주문 요청 시리얼라이저"""
    work_sheet_url = serializers.SerializerMethodField()
    
    class Meta:
        model = RequestOrder
        fields = ['id', 'order', 'designer_name', 'product_name', 'quantity', 
                 'due_date', 'work_sheet_path', 'work_sheet_url']
        read_only_fields = ['id']
    
    def get_work_sheet_url(self, obj):
        """작업지시서 URL 반환"""
        if obj.work_sheet_path:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.work_sheet_path.url)
            return obj.work_sheet_path.url
        return None


class RequestOrderCreateSerializer(serializers.ModelSerializer):
    """주문 요청 생성용 시리얼라이저"""
    
    class Meta:
        model = RequestOrder
        fields = ['order', 'designer_name', 'product_name', 'quantity', 
                 'due_date', 'work_sheet_path']
    
    def validate_quantity(self, value):
        """수량 검증"""
        if value <= 0:
            raise serializers.ValidationError("수량은 1 이상이어야 합니다.")
        return value


class BidFactorySerializer(serializers.ModelSerializer):
    """공장 입찰 시리얼라이저"""
    factory_info = FactorySerializer(source='factory', read_only=True)
    request_order_info = RequestOrderSerializer(source='request_order', read_only=True)
    
    class Meta:
        model = BidFactory
        fields = ['id', 'factory', 'factory_info', 'request_order', 'request_order_info',
                 'work_price', 'expect_work_day', 'settlement_status', 'is_matched', 'matched_date']
        read_only_fields = ['id', 'is_matched', 'matched_date']


class BidFactoryCreateSerializer(serializers.ModelSerializer):
    """공장 입찰 생성용 시리얼라이저"""
    
    class Meta:
        model = BidFactory
        fields = ['factory', 'request_order', 'work_price', 'expect_work_day']
    
    def validate_work_price(self, value):
        """장당 가격 검증"""
        if value <= 0:
            raise serializers.ValidationError("장당 가격은 1 이상이어야 합니다.")
        return value