import logging
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.db.utils import IntegrityError
from .models import Product, Order, RequestOrder, BidFactory
from .serializers import (
    ProductSerializer, ProductCreateSerializer, OrderSerializer, OrderCreateSerializer,
    RequestOrderSerializer, BidFactorySerializer, BidFactoryCreateSerializer
)
from apps.core.services.mongo import get_collection, now_iso_with_minutes

logger = logging.getLogger(__name__)

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ProductCreateSerializer
        return ProductSerializer
    
    def get_queryset(self):
        # 디자이너는 자신의 제품만, 공장주는 모든 제품 조회 가능
        if hasattr(self.request.user, 'designer'):
            return Product.objects.filter(designer=self.request.user.designer)
        return Product.objects.all()

    def perform_create(self, serializer):
        # 디자이너만 제품 생성 가능
        if not hasattr(self.request.user, 'designer'):
            return Response(
                {'error': '디자이너만 제품을 생성할 수 있습니다.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        serializer.save(designer=self.request.user.designer)
    
    def create(self, request, *args, **kwargs):
        logger.info(f"Product create request from user: {request.user}")
        logger.info(f"Request data: {request.data}")
        
        # 디자이너 권한 확인
        if not hasattr(request.user, 'designer'):
            logger.warning(f"Non-designer user attempted to create product: {request.user}")
            return Response(
                {'error': '디자이너만 제품을 생성할 수 있습니다.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Serializer validation errors: {serializer.errors}")
            return Response(
                {'error': 'Validation failed', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            self.perform_create(serializer)
            logger.info(f"Product created successfully: {serializer.data}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error creating product: {str(e)}")
            return Response(
                {'error': 'Failed to create product', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer
    
    def get_queryset(self):
        # 디자이너는 자신의 제품에 대한 주문만 조회 가능
        if hasattr(self.request.user, 'designer'):
            return Order.objects.filter(product__designer=self.request.user.designer)
        # 공장주는 모든 주문 조회 가능
        return Order.objects.all()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_manufacturing(request):
    """
    단일 제출 엔드포인트: Product -> Order -> RequestOrder 생성.
    - 요구 권한: 디자이너
    - 입력: multipart/form-data 권장. 파일 필드는 image_path(선택).
    - 응답: { product_id, order_id, request_order_id }
    """
    try:
        # 디자이너 권한 확인
        if not hasattr(request.user, 'designer'):
            return Response({'detail': '디자이너만 제출할 수 있습니다.'}, status=status.HTTP_403_FORBIDDEN)

        data = request.data

        # 필드 매핑 및 전처리
        name = data.get('name')
        season = data.get('season')
        target = data.get('target') or data.get('target_customer')
        concept = data.get('concept')
        detail = data.get('detail')
        size = data.get('size')
        quantity_raw = data.get('quantity')
        fabric_code = data.get('fabric_code')
        material_code = data.get('material_code')
        due_date = data.get('due_date')
        memo = data.get('memo')
        image_file = request.FILES.get('image_path')

        # 유효성 최소 체크
        required = {'name': name, 'season': season, 'target': target, 'concept': concept}
        missing = [k for k, v in required.items() if not v]
        if missing:
            return Response({'detail': f"필수 값 누락: {', '.join(missing)}"}, status=status.HTTP_400_BAD_REQUEST)

        # 수량 정수 변환
        quantity = None
        if quantity_raw not in (None, ''):
            try:
                quantity = int(quantity_raw)
            except ValueError:
                return Response({'detail': 'quantity는 정수여야 합니다.'}, status=status.HTTP_400_BAD_REQUEST)

        fabric = {'name': fabric_code} if fabric_code else None
        material = {'name': material_code} if material_code else None

        with transaction.atomic():
            product = Product(
                designer=request.user.designer,
                name=name,
                season=season,
                target=target,
                concept=concept,
                detail=detail or '',
                size=size or None,
                quantity=quantity,
                fabric=fabric,
                material=material,
                due_date=due_date or None,
                memo=memo or '',
            )
            if image_file:
                product.image_path = image_file
            product.save()

            order = Order.objects.create(product=product)

            request_order = RequestOrder.objects.create(
                order=order,
                designer_name=str(request.user._obj.name if hasattr(request.user, '_obj') else getattr(request.user, 'name', '')),
                product_name=product.name,
                quantity=product.quantity or 0,
                due_date=product.due_date or None,
            )

        return Response({
            'product_id': product.id,
            'order_id': order.order_id,
            'request_order_id': request_order.id,
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.exception('submit_manufacturing error')
        return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_factory_orders(request):
    """
    공장주용 주문 목록 조회 - RequestOrder와 BidFactory 정보 포함
    """
    try:
        # 공장주 권한 확인
        if not hasattr(request.user, 'factory'):
            return Response({'detail': '공장주만 접근할 수 있습니다.'}, status=status.HTTP_403_FORBIDDEN)
        
        # 모든 RequestOrder 조회 (견적 대기 상태들만)
        # STATUS_CHOICES 변경에 따라 'pending' 대신 샘플/본생산 대기 상태만 노출
        request_orders = RequestOrder.objects.filter(
            status__in=['sample_pending', 'product_pending']
        ).select_related(
            'order__product__designer'
        ).prefetch_related('bids__factory')
        
        orders_data = []
        for req_order in request_orders:
            # 해당 공장의 입찰 정보 확인
            factory_bid = req_order.bids.filter(factory=request.user.factory).first()
            
            # 디자이너 정보 가져오기
            designer = req_order.order.product.designer

            # 요청 상태 라벨 매핑 (샘플/본생산 구분)
            status_map = {
                'sample_pending': '샘플 견적',
                'sample_matched': '샘플 견적',
                'product_pending': '생산 견적',
                'product_matched': '생산 견적',
                'finished': '완료'
            }
            request_status = req_order.status
            request_status_label = status_map.get(request_status, '')
            
            order_data = {
                'id': req_order.id,
                'orderId': req_order.order.order_id,
                'status': 'pending' if not factory_bid else 'responded',
                'requestStatus': request_status,
                'requestStatusLabel': request_status_label,
                'createdAt': req_order.order.product.created_at,
                'quantity': req_order.quantity,
                'customerName': req_order.designer_name,
                'customerContact': designer.contact if designer.contact else '연락처 정보 없음',
                'shippingAddress': designer.address if designer.address else '주소 정보 없음',

                'notes': req_order.order.product.memo or '',
                'productInfo': {
                    'id': req_order.order.product.id,
                    'name': req_order.product_name,
                    'designerName': req_order.designer_name,
                    'season': req_order.order.product.season,
                    'target': req_order.order.product.target,
                    'concept': req_order.order.product.concept,
                    'detail': req_order.order.product.detail,
                    'size': req_order.order.product.size,
                    'fabric': req_order.order.product.fabric,
                    'material': req_order.order.product.material,
                    'dueDate': req_order.due_date,
                    'memo': req_order.order.product.memo,
                    'imageUrl': request.build_absolute_uri(req_order.order.product.image_path.url) if req_order.order.product.image_path else None,
                    'workSheetUrl': request.build_absolute_uri(req_order.work_sheet_path.url) if req_order.work_sheet_path else None,
                }
            }
            
            # 입찰 정보가 있으면 단가 정보 추가, 없으면 기본값 설정
            if factory_bid:
                order_data.update({
                    'unitPrice': factory_bid.work_price,
                    'totalPrice': factory_bid.work_price * req_order.quantity,
                    'bidId': factory_bid.id,
                    'estimatedDeliveryDays': (factory_bid.expect_work_day - req_order.due_date).days if factory_bid.expect_work_day and req_order.due_date else 0,
                })
            else:
                # 입찰 정보가 없을 때 기본값 설정
                order_data.update({
                    'unitPrice': 0,
                    'totalPrice': 0,
                })
            
            orders_data.append(order_data)
        
        return Response({'results': orders_data}, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.exception('get_factory_orders error')
        return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_designer_orders(request):
    """
    디자이너용 주문 목록 조회
    """
    try:
        # 디자이너 권한 확인
        if not hasattr(request.user, 'designer'):
            return Response({'detail': '디자이너만 접근할 수 있습니다.'}, status=status.HTTP_403_FORBIDDEN)
        
        # 해당 디자이너의 주문들 조회
        orders = Order.objects.filter(
            product__designer=request.user.designer
        ).select_related('product').prefetch_related('request_orders')
        
        orders_data = []
        for order in orders:
            # RequestOrder 정보 가져오기
            request_order = order.request_orders.first()
            
            order_data = {
                'id': order.order_id,
                'order_id': order.order_id,
                'status': 'pending',  # 기본값
                'created_at': order.product.created_at,
                'quantity': request_order.quantity if request_order else order.product.quantity,
                'product': {
                    'id': order.product.id,
                    'name': order.product.name,
                    'designer': order.product.designer.id,
                },
                'productInfo': {
                    'id': order.product.id,
                    'name': order.product.name,
                    'designer': order.product.designer.id,
                    'designerName': order.product.designer.name,
                }
            }
            
            orders_data.append(order_data)
        
        return Response({'results': orders_data}, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.exception('get_designer_orders error')
        return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_bids_by_order(request):
    """
    특정 주문에 대한 입찰 목록 조회 (공장 정보 포함)
    """
    try:
        order_id = request.GET.get('order_id')
        logger.info(f"get_bids_by_order called with order_id: {order_id}")
        
        if not order_id:
            return Response({'detail': 'order_id 파라미터가 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # RequestOrder 찾기
        try:
            request_order = RequestOrder.objects.get(order__order_id=order_id)
            logger.info(f"Found request_order: {request_order.id}")
        except RequestOrder.DoesNotExist:
            logger.warning(f"RequestOrder not found for order_id: {order_id}")
            return Response({'detail': '해당 주문을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)
        
        # 해당 RequestOrder에 대한 입찰들 조회
        bids = BidFactory.objects.filter(
            request_order=request_order
        ).select_related('factory', 'request_order')
        
        logger.info(f"Found {bids.count()} bids for request_order {request_order.id}")
        
        bids_data = []
        for bid in bids:
            # 예상 납기일 계산
            estimated_days = 0
            if bid.expect_work_day and request_order.due_date:
                try:
                    estimated_days = (bid.expect_work_day - request_order.due_date).days
                except:
                    estimated_days = 0
            
            bid_data = {
                'id': bid.id,
                'factory_info': {
                    'id': bid.factory.id,
                    'name': bid.factory.name,
                    'contact': bid.factory.contact,
                    'address': bid.factory.address,
                    'profile_image': request.build_absolute_uri(bid.factory.profile_image.url) if bid.factory.profile_image else None,
                },
                'unit_price': bid.work_price,
                'total_price': bid.work_price * request_order.quantity,
                'estimated_delivery_days': abs(estimated_days),
                'expect_work_day': bid.expect_work_day.strftime('%Y-%m-%d') if bid.expect_work_day else None,
                'status': 'selected' if bid.is_matched else 'pending',
                'settlement_status': bid.settlement_status,
                'created_at': bid.request_order.order.product.created_at,
            }
            bids_data.append(bid_data)
        
        logger.info(f"Returning bids_data: {bids_data}")
        return Response(bids_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.exception('get_bids_by_order error')
        return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_factory_bid(request):
    """
    공장 입찰 생성
    """
    try:
        # 공장주 권한 확인
        if not hasattr(request.user, 'factory'):
            return Response({'detail': '공장주만 입찰할 수 있습니다.'}, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data.copy()
        data['factory'] = request.user.factory.id
        
        # RequestOrder ID를 통해 RequestOrder 객체 가져오기
        request_order_id = data.get('order')  # 프론트에서 order로 전송
        if not request_order_id:
            return Response({'detail': 'order 필드가 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            request_order = RequestOrder.objects.get(id=request_order_id)
            data['request_order'] = request_order.id
        except RequestOrder.DoesNotExist:
            return Response({'detail': '해당 주문을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)
        
        # 예상 납기일 계산 (단가와 예상 작업일수로부터)
        estimated_delivery_days = data.get('estimated_delivery_days', 7)
        from datetime import datetime, timedelta
        data['expect_work_day'] = (datetime.now().date() + timedelta(days=estimated_delivery_days))
        data['work_price'] = data.get('unit_price')
        
        serializer = BidFactoryCreateSerializer(data=data)
        if serializer.is_valid():
            try:
                bid = serializer.save()
            except IntegrityError:
                # 동일 공장-주문 조합 중복 입찰
                return Response({'detail': '이미 이 주문에 대해 입찰을 제출하셨습니다.'}, status=status.HTTP_400_BAD_REQUEST)

            # Bid 생성 성공 시, 디자이너 Mongo 문서의 step.index=1 factory_list에 항목 push
            try:
                # 기본 식별값 (designer_orders는 문자열 order_id를 사용하므로 str로 변환)
                order_id_str = str(request_order.order.order_id)
                factory = request.user.factory

                # 프로필 이미지 절대 URL 구성(없으면 빈 문자열)
                profile_image_url = ''
                try:
                    if getattr(factory, 'profile_image', None):
                        if factory.profile_image:
                            profile_image_url = request.build_absolute_uri(factory.profile_image.url)
                except Exception:
                    profile_image_url = ''

                # factory_list 항목 구성 (expect_work_day는 YYYY-MM-DD 문자열)
                item = {
                    'factory_id': str(factory.id),
                    'profile_image': profile_image_url,
                    'name': getattr(factory, 'name', ''),
                    'contact': getattr(factory, 'contact', ''),
                    'address': getattr(factory, 'address', ''),
                    'work_price': bid.work_price,
                    'currency': 'KRW',
                    'expect_work_day': bid.expect_work_day.strftime('%Y-%m-%d') if getattr(bid, 'expect_work_day', None) else ''
                }

                col = get_collection(settings.MONGODB_COLLECTIONS['designer_orders'])

                # 1) 동일 factory_id 항목 제거(중복 방지)
                res_pull = col.update_one(
                    { 'order_id': order_id_str },
                    {
                        '$pull': { 'steps.$[step].factory_list': { 'factory_id': str(factory.id) } },
                        '$set': { 'last_updated': now_iso_with_minutes() }
                    },
                    array_filters=[ { 'step.index': 1 } ],
                    upsert=False
                )
                if getattr(res_pull, 'matched_count', 0) == 0:
                    logger.warning(
                        'designer_orders not matched on $pull. order_id=%s (check order doc creation and type).',
                        order_id_str
                    )

                # 2) 새 항목 push
                res_push = col.update_one(
                    { 'order_id': order_id_str },
                    {
                        '$push': { 'steps.$[step].factory_list': item },
                        '$set': { 'last_updated': now_iso_with_minutes() }
                    },
                    array_filters=[ { 'step.index': 1 } ],
                    upsert=False
                )
                if getattr(res_push, 'matched_count', 0) == 0:
                    logger.warning(
                        'designer_orders not matched on $push. order_id=%s (check order doc creation and type).',
                        order_id_str
                    )
            except Exception:
                # Mongo 반영 실패는 bid 생성 자체를 실패로 만들지 않음(로그만 남김)
                logger.exception('Failed to push factory item into designer_orders.factory_list')

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.exception('create_factory_bid error')
        return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def select_bid(request, bid_id):
    """
    입찰 선정
    """
    try:
        logger.info(f"select_bid called with bid_id: {bid_id}")
        
        # 디자이너 권한 확인
        if not hasattr(request.user, 'designer'):
            return Response({'detail': '디자이너만 입찰을 선정할 수 있습니다.'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            bid = BidFactory.objects.get(id=bid_id)
            logger.info(f"Found bid: {bid.id} for factory: {bid.factory.name}")
        except BidFactory.DoesNotExist:
            return Response({'detail': '해당 입찰을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)
        
        # 해당 디자이너의 주문인지 확인
        if bid.request_order.order.product.designer != request.user.designer:
            return Response({'detail': '권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        
        # 입찰 선정
        bid.is_matched = True
        bid.matched_date = timezone.now().date()
        bid.settlement_status = 'confirmed'
        bid.save()
        
        # 같은 RequestOrder의 다른 입찰들은 거절 처리
        BidFactory.objects.filter(
            request_order=bid.request_order
        ).exclude(id=bid_id).update(
            settlement_status='cancelled'
        )
        
        logger.info(f"Bid {bid_id} selected successfully")
        return Response({'detail': '입찰이 선정되었습니다.'}, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.exception('select_bid error')
        return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)