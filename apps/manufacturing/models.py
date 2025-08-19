from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone
import uuid

# accounts 앱의 User 모델 import
from apps.accounts.models import User

class Product(models.Model):
    """제품 모델"""
    SEASON_CHOICES = (
        ('spring', '봄'),
        ('summer', '여름'),
        ('autumn', '가을'),
        ('winter', '겨울'),
        ('all-season', '사계절'),
    )
    
    TARGET_CHOICES = (
        ('teens', '10대'),
        ('twenties', '20대'),
        ('thirties', '30대'),
        ('forties', '40대'),
        ('fifties-plus', '50대 이상'),
        ('all-ages', '전 연령'),
    )
    
    designer = models.ForeignKey(
        'accounts.Designer', 
        on_delete=models.CASCADE, 
        related_name='products',
        verbose_name="디자이너"
    )
    name = models.CharField(max_length=100, verbose_name="제품명")
    season = models.CharField(max_length=20, choices=SEASON_CHOICES, verbose_name="시즌")
    target = models.CharField(max_length=20, choices=TARGET_CHOICES, verbose_name="타겟 고객층")
    concept = models.TextField(verbose_name="컨셉 설명")
    image_path = models.ImageField(upload_to='design_image/', null=True, blank=True, verbose_name="디자인 이미지")
    detail = models.TextField(blank=True, null=True, verbose_name="포인트 부위 설명")
    size = models.CharField(max_length=20, null=True, blank=True, verbose_name="사이즈")
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)], 
        null=True, 
        blank=True, 
        verbose_name="수량"
    )
    fabric = models.JSONField(
        null=True, 
        blank=True, 
        verbose_name="원단 정보",
        help_text="원단 종류, 무게, 신축성 등의 정보를 JSON 형태로 저장"
    )
    material = models.JSONField(
        null=True, 
        blank=True, 
        verbose_name="부자재 정보",
        help_text="단추, 지퍼, 라이닝 등의 정보를 JSON 형태로 저장"
    ) 
    due_date = models.DateField(null=True, blank=True, verbose_name="납기일")
    memo = models.TextField(null=True, blank=True, verbose_name="메모")
    work_sheet_path = models.FileField(
        upload_to='worksheets/', 
        null=True, 
        blank=True, 
        verbose_name="작업지시서"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일시")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일시")

    class Meta:
        db_table = 'products'
        verbose_name = "제품"
        verbose_name_plural = "제품들"
        ordering = ['-created_at']
    
    def __str__(self):
        # Designer 모델은 User FK가 없으므로 직접 name 사용
        return f"{self.name} - {self.designer.name}"


class Order(models.Model):
    """주문 모델"""
    order_id = models.BigAutoField(primary_key=True, verbose_name="주문 번호")
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='orders',
        verbose_name="제품"
    )

    class Meta:
        db_table = 'orders'
        verbose_name = "주문"
        verbose_name_plural = "주문들"

    def __str__(self):
        return f"주문 {self.order_id} - {self.product.name}"


class RequestOrder(models.Model):
    """주문 요청 모델"""
    STATUS_CHOICES = (
        ('pending', '매칭 대기중'),
        ('matched', '매칭 완료'),
        ('cancelled', '취소됨'),
    )
    
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='request_orders',
        verbose_name="주문 번호"
    )
    designer_name = models.CharField(max_length=20, verbose_name="디자이너 사용자 이름")
    product_name = models.CharField(max_length=100, verbose_name="제품명")
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="수량"
    )
    due_date = models.DateField(verbose_name="납기일")
    work_sheet_path = models.FileField(
        upload_to='request_orders/worksheets/',
        verbose_name="작업지시서"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="매칭 상태"
    )

    class Meta:
        db_table = 'request_order'
        verbose_name = "주문 요청"
        verbose_name_plural = "주문 요청들"

    def __str__(self):
        return f"주문요청 {self.id} - {self.product_name}"


class BidFactory(models.Model):
    """공장 입찰 모델"""
    SETTLEMENT_STATUS_CHOICES = (
        ('pending', '대기중'),
        ('confirmed', '확인됨'),
        ('completed', '완료'),
        ('cancelled', '취소됨'),
    )
    
    factory = models.ForeignKey(
        'accounts.Factory',
        on_delete=models.CASCADE,
        related_name='bids',
        verbose_name="공장 ID"
    )
    request_order = models.ForeignKey(
        RequestOrder,
        on_delete=models.CASCADE,
        related_name='bids',
        verbose_name="주문 번호"
    )
    work_price = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="장당 가격"
    )
    expect_work_day = models.DateField(verbose_name="예상 납기일")
    settlement_status = models.CharField(
        max_length=20,
        choices=SETTLEMENT_STATUS_CHOICES,
        default='pending',
        verbose_name="주문 상태"
    )
    is_matched = models.BooleanField(default=False, verbose_name="낙찰 상태")
    matched_date = models.DateField(null=True, blank=True, verbose_name="낙찰 일자")

    class Meta:
        db_table = 'bid_factory'
        verbose_name = "공장 입찰"
        verbose_name_plural = "공장 입찰들"
        unique_together = ['factory', 'request_order']  # 공장당 한 번만 입찰 가능

    def __str__(self):
        return f"입찰 {self.id} - {self.factory.name} - {self.request_order.product_name}"