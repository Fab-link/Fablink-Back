import logging
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.renderers import JSONRenderer
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.db.utils import IntegrityError
from .models import Product, Order, RequestOrder, BidFactory
from .serializers import (
    ProductSerializer, ProductCreateSerializer, OrderSerializer, OrderCreateSerializer,
    RequestOrderSerializer, BidFactorySerializer, BidFactoryCreateSerializer
)
from apps.core.services.mongo import get_collection, now_iso_with_minutes, ensure_indexes
from apps.core.services.orders_steps_template import build_orders_steps_template
from apps.accounts.models import Designer

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
@renderer_classes([JSONRenderer])  # force snake_case to match frontend expectations
def get_designer_orders(request):
    """
    디자이너용 주문 목록 조회
    """
    try:
        # 디자이너 권한 확인
        if not hasattr(request.user, 'designer'):
            return Response({'detail': '디자이너만 접근할 수 있습니다.'}, status=status.HTTP_403_FORBIDDEN)

        # 해당 디자이너의 주문들 조회
        orders_qs = (
            Order.objects.filter(product__designer=request.user.designer)
            .select_related('product')
            .prefetch_related('request_orders')
        )
        orders = list(orders_qs)

        # Mongo(orders)에서 current_step_index 및 steps 등 배치 조회
        current_idx_map: dict[str, int] = {}
        steps_map: dict[str, list] = {}
        overall_status_map: dict[str, str] = {}
        last_updated_map: dict[str, str] = {}
        try:
            order_ids_str = [str(o.order_id) for o in orders if getattr(o, 'order_id', None) is not None]
            order_ids_int = []
            for o in orders:
                try:
                    if getattr(o, 'order_id', None) is not None:
                        order_ids_int.append(int(o.order_id))
                except Exception:
                    pass
            if order_ids_str or order_ids_int:
                col_orders = get_collection(settings.MONGODB_COLLECTIONS['orders'])
                query = {'$or': []}
                if order_ids_str:
                    query['$or'].append({'order_id': {'$in': order_ids_str}})
                if order_ids_int:
                    query['$or'].append({'order_id': {'$in': order_ids_int}})
                cur = col_orders.find(
                    query,
                    projection={
                        '_id': 0,
                        'order_id': 1,
                        'current_step_index': 1,
                        'steps': 1,
                        'overall_status': 1,
                        'last_updated': 1,
                    },
                )
                for doc in cur:
                    oid = str(doc.get('order_id'))
                    try:
                        current_idx_map[oid] = int(doc.get('current_step_index') or 1)
                    except Exception:
                        current_idx_map[oid] = 1
                    if 'steps' in doc:
                        steps_map[oid] = doc.get('steps')
                    if 'overall_status' in doc:
                        overall_status_map[oid] = doc.get('overall_status')
                    if 'last_updated' in doc:
                        last_updated_map[oid] = doc.get('last_updated')
        except Exception:
            # Mongo 조회 실패 시 전체 흐름을 막지 않음 (기본 1)
            logger.exception('get_designer_orders: failed to fetch current_step_index from orders')

        orders_data = []
        for order in orders:
            request_order = order.request_orders.first()
            oid = str(order.order_id)
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
                },
                # 진행 단계: Mongo orders.current_step_index 우선 사용(기본 1)
                'current_step_index': current_idx_map.get(oid, 1),
                # 세부 단계 데이터: Mongo steps, 없으면 템플릿 제공
                'steps': steps_map.get(oid) or build_orders_steps_template(),
                'overall_status': overall_status_map.get(oid, ''),
                'last_updated': last_updated_map.get(oid),
            }
            orders_data.append(order_data)

        return Response({'results': orders_data}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception('get_designer_orders error')
        return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])  # force snake_case for this endpoint
def get_factory_orders_mongo(request):
    """
    공장주용 orders 목록(MongoDB, 선정된 주문만)
    - 인증된 공장 사용자만 접근 가능
    - 기본 정렬: last_updated desc
    - 페이징: ?page=1&page_size=20 (최대 100)
    - 필터: ?phase=sample|main (선택), ?status=...
        응답 형식:
    {
            count, page, page_size, has_next,
            results: [{ order_id, phase, factory_id, overall_status, due_date, quantity, work_price, last_updated, product_id }]
    }
    """
    try:
        if not hasattr(request.user, 'factory'):
            return Response({'detail': '공장주만 접근할 수 있습니다.'}, status=status.HTTP_403_FORBIDDEN)

        # 입력 파라미터
        try:
            page = int(request.GET.get('page', '1'))
            page_size = int(request.GET.get('page_size', '20'))
        except ValueError:
            return Response({'detail': 'page/page_size는 정수여야 합니다.'}, status=status.HTTP_400_BAD_REQUEST)
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        phase = request.GET.get('phase')
        status_filter = request.GET.get('status')
        # 진단용: debug=1|true|yes 일 때 응답 아이템의 핵심 필드를 서버 로그로 남긴다
        debug_mode = str(request.GET.get('debug', '')).lower() in ('1', 'true', 'yes')

        factory_id = str(request.user.factory.id)

        # Match docs where factory_id may be stored as string or int
        q: dict = { '$or': [
            { 'factory_id': factory_id },
            { 'factory_id': int(factory_id) if factory_id.isdigit() else -1 }
        ] }
        if phase:
            q['phase'] = phase
        if status_filter:
            q['overall_status'] = status_filter

        col = get_collection(settings.MONGODB_COLLECTIONS['orders'])

        # 정렬 및 페이징 쿼리
        total = col.count_documents(q)
        cursor = (
            col.find(q, projection={
                '_id': 0,
                'order_id': 1,
                'phase': 1,
                'factory_id': 1,
                'overall_status': 1,
                'due_date': 1,
                'quantity': 1,
                'work_price': 1,
                'last_updated': 1,
                'product_id': 1,
                'steps': 1,
                'designer_id': 1,
            })
            .sort('last_updated', -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )

        items = list(cursor)

        # Enrich with product_name and designer_name via batch lookups
        product_ids: list[int] = []
        designer_ids: list[int] = []
        for it in items:
            try:
                if it.get('product_id') is not None:
                    product_ids.append(int(it['product_id']))
            except Exception:
                pass
            try:
                if it.get('designer_id') is not None:
                    designer_ids.append(int(it['designer_id']))
            except Exception:
                pass
        product_map = {}
        designer_map = {}
        if product_ids:
            try:
                qs = Product.objects.filter(id__in=product_ids).only('id', 'name')
                product_map = {str(p.id): p.name for p in qs}
            except Exception:
                product_map = {}
        if designer_ids:
            try:
                qs = Designer.objects.filter(id__in=designer_ids).only('id', 'name')
                designer_map = {str(d.id): d.name for d in qs}
            except Exception:
                designer_map = {}

        for it in items:
            pid = it.get('product_id')
            did = it.get('designer_id')
            if pid is not None:
                it['product_name'] = product_map.get(str(pid), '')
            else:
                it['product_name'] = ''
            if did is not None:
                it['designer_name'] = designer_map.get(str(did), '')
            else:
                it['designer_name'] = ''

        # Fallback 제거: 단일 orders 컬렉션 사용
        try:
            pass
        except Exception:
            pass

        # Recompute names if new IDs were filled
        try:
            product_ids2 = []
            designer_ids2 = []
            for it in items:
                if it.get('product_id') and not it.get('product_name'):
                    try:
                        product_ids2.append(int(str(it['product_id'])))
                    except Exception:
                        pass
                if it.get('designer_id') and not it.get('designer_name'):
                    try:
                        designer_ids2.append(int(str(it['designer_id'])))
                    except Exception:
                        pass
            if product_ids2:
                try:
                    qs = Product.objects.filter(id__in=product_ids2).only('id', 'name')
                    product_map2 = {str(p.id): p.name for p in qs}
                except Exception:
                    product_map2 = {}
            else:
                product_map2 = {}
            if designer_ids2:
                try:
                    qs = Designer.objects.filter(id__in=designer_ids2).only('id', 'name')
                    designer_map2 = {str(d.id): d.name for d in qs}
                except Exception:
                    designer_map2 = {}
            else:
                designer_map2 = {}
            for it in items:
                if not it.get('product_name') and it.get('product_id'):
                    it['product_name'] = product_map2.get(str(it['product_id']), it.get('product_name', ''))
                if not it.get('designer_name') and it.get('designer_id'):
                    it['designer_name'] = designer_map2.get(str(it['designer_id']), it.get('designer_name', ''))
        except Exception:
            pass

        # Fallback enrichment via SQL Order when product/designer info is missing
        try:
            need_fallback = [it for it in items if not it.get('product_name') or not it.get('designer_name') or not it.get('product_id') or not it.get('designer_id')]
            if need_fallback:
                order_ids: list[int] = []
                for it in need_fallback:
                    try:
                        if it.get('order_id') is not None:
                            order_ids.append(int(str(it['order_id'])))
                    except Exception:
                        pass
                if order_ids:
                    qs = Order.objects.filter(order_id__in=order_ids).select_related('product__designer')
                    by_oid = {str(o.order_id): o for o in qs}
                    for it in need_fallback:
                        o = by_oid.get(str(it.get('order_id')))
                        if not o:
                            continue
                        # product
                        if not it.get('product_name') and getattr(o, 'product', None):
                            it['product_name'] = getattr(o.product, 'name', '') or ''
                        if not it.get('product_id') and getattr(o, 'product', None) and getattr(o.product, 'id', None):
                            it['product_id'] = str(o.product.id)
                        # designer
                        if getattr(o, 'product', None) and getattr(o.product, 'designer', None):
                            if not it.get('designer_name'):
                                it['designer_name'] = getattr(o.product.designer, 'name', '') or ''
                            if not it.get('designer_id') and getattr(o.product.designer, 'id', None):
                                it['designer_id'] = str(o.product.designer.id)
        except Exception:
            # Fallback enrichment should not break API
            pass

    # 필요 시 BidFactory로 보강(선택) — 기본적으로 orders에 work_price/due_date가 존재해야 함
        try:
            factory_obj = getattr(request.user, 'factory', None)
            if factory_obj:
                order_ids_for_bids: list[int] = []
                for it in items:
                    try:
                        if it.get('order_id') is not None:
                            order_ids_for_bids.append(int(str(it['order_id'])))
                    except Exception:
                        pass
                if order_ids_for_bids:
                    req_orders = RequestOrder.objects.filter(order__order_id__in=order_ids_for_bids).select_related('order').only('id', 'order__order_id')
                    ro_by_orderid = {str(ro.order.order_id): ro for ro in req_orders}
                    ro_ids = [ro.id for ro in req_orders]
                    if ro_ids:
                        bids = (
                            BidFactory.objects
                            .filter(request_order_id__in=ro_ids, factory=factory_obj)
                            .order_by('-is_matched', '-id')
                        )
                        bid_by_ro = {}
                        for b in bids:
                            if b.request_order_id not in bid_by_ro:
                                bid_by_ro[b.request_order_id] = b
                        for it in items:
                            oid = str(it.get('order_id'))
                            ro = ro_by_orderid.get(oid)
                            if not ro:
                                continue
                            bid = bid_by_ro.get(ro.id)
                            if not bid:
                                continue
                            if it.get('work_price') in (None, ''):
                                it['work_price'] = getattr(bid, 'work_price', None)
                            if not it.get('due_date') and getattr(bid, 'expect_work_day', None):
                                try:
                                    it['due_date'] = bid.expect_work_day.isoformat()
                                except Exception:
                                    pass
        except Exception:
            # Do not fail response on enrichment error
            pass

        # Debug: summarize key fields to help diagnose '-' or '주문' fallbacks on the front-end
        debug_payload = None
        if debug_mode:
            try:
                debug_list = []
                for it in items:
                    debug_item = {
                        'order_id': it.get('order_id'),
                        'factory_id': it.get('factory_id'),
                        'phase': it.get('phase'),
                        'product_id': it.get('product_id'),
                        'product_name': it.get('product_name'),
                        'designer_id': it.get('designer_id'),
                        'designer_name': it.get('designer_name'),
                        'work_price': it.get('work_price'),
                        'due_date': it.get('due_date'),
                        'quantity': it.get('quantity'),
                        'overall_status': it.get('overall_status'),
                    }
                    debug_list.append(debug_item)
                debug_payload = {
                    'query': {'phase': phase, 'status': status_filter, 'factory_id': factory_id},
                    'size': len(items),
                    'items': debug_list,
                }
                logger.info('orders-mongo debug: %s', debug_payload)
            except Exception:
                logger.exception('failed to build debug payload for factory-orders-mongo')

        return Response({
            'count': total,
            'page': page,
            'page_size': page_size,
            'has_next': (page * page_size) < total,
            'results': items,
            **({'debug_summary': debug_payload} if debug_payload is not None else {}),
        }, status=status.HTTP_200_OK)
    except Exception:
        logger.exception('get_factory_orders_mongo error')
        return Response({'detail': '서버 오류가 발생했습니다.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
                # 기본 식별값 (orders는 문자열 order_id를 사용하므로 str로 변환)
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

                # unified 'orders' collection: store bid candidates under steps[1].factory_list
                col = get_collection(settings.MONGODB_COLLECTIONS['orders'])

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
                        'orders not matched on $pull. order_id=%s (check order doc creation and type).',
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
                        'orders not matched on $push. order_id=%s (check order doc creation and type).',
                        order_id_str
                    )

                # 3) placeholder 정리: 템플릿에 포함된 빈 항목(factory_id가 '' 또는 null)을 제거
                try:
                    col.update_one(
                        { 'order_id': order_id_str },
                        {
                            '$pull': {
                                'steps.$[step].factory_list': {
                                    '$or': [ { 'factory_id': '' }, { 'factory_id': None } ]
                                }
                            },
                            '$set': { 'last_updated': now_iso_with_minutes() }
                        },
                        array_filters=[ { 'step.index': 1 } ],
                        upsert=False
                    )
                except Exception:
                    logger.exception('Failed to cleanup placeholder from orders.steps[1].factory_list')
            except Exception:
                # Mongo 반영 실패는 bid 생성 자체를 실패로 만들지 않음(로그만 남김)
                logger.exception('Failed to push factory item into orders.steps[1].factory_list')

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

        # 선택된 입찰의 요청 상태를 샘플 매칭으로 업데이트
        try:
            req_order = bid.request_order
            # STATUS_CHOICES에 따라 샘플 매칭 상태로 설정
            req_order.status = 'sample_matched'
            req_order.save(update_fields=['status'])
        except Exception:
            # 상태 업데이트 실패가 전체 플로우를 막지 않도록 로그만 남김
            logger.exception('Failed to update RequestOrder.status to sample_matched')

        # unified orders 문서 갱신 (선정 정보 반영)
        try:
            ensure_indexes()
        except Exception:
            pass
        try:
            ro = bid.request_order
            order = ro.order
            product = order.product
            factory = bid.factory

            order_id = str(order.order_id)
            product_id = str(getattr(product, 'id', None)) if getattr(product, 'id', None) else None
            designer_id = str(getattr(getattr(product, 'designer', None), 'id', None)) if getattr(product, 'designer', None) else None
            factory_id = str(getattr(factory, 'id', None)) if getattr(factory, 'id', None) else None

            # phase 기본값: sample (본 생산 단계 진입 시 'product'로 업데이트 예정)
            phase = 'sample'

            # 날짜는 문자열로 저장
            expect_date = getattr(bid, 'expect_work_day', None)
            if hasattr(expect_date, 'isoformat'):
                try:
                    expect_date = expect_date.isoformat()
                except Exception:
                    expect_date = None

            col = get_collection(settings.MONGODB_COLLECTIONS['orders'])
            update_doc = {
                '$setOnInsert': {
                    'order_id': order_id,
                    'current_step_index': 1,
                    'overall_status': '',
                    'steps': build_orders_steps_template(),
                },
                '$set': {
                    'designer_id': designer_id,
                    'product_id': product_id,
                    # Ensure factory_id is stored as string to match API filters
                    'factory_id': factory_id,
                    'factory_name': getattr(factory, 'name', ''),
                    'factory_contact': getattr(factory, 'contact', ''),
                    'factory_address': getattr(factory, 'address', ''),
                    'work_price': getattr(bid, 'work_price', None),
                    'quantity': getattr(ro, 'quantity', None),
                    # no currency at top-level per order_schema.json
                    'due_date': expect_date,
                    'phase': phase,
                    'last_updated': now_iso_with_minutes(),
                },
            }
            try:
                col.update_one({'order_id': order_id}, update_doc, upsert=True)
            except Exception:
                logger.exception('Failed to upsert orders in select_bid')
        except Exception:
            logger.exception('orders upsert fallback block failed')

        # orders current_step_index is advanced to 2
        try:
            try:
                order_id_str = str(bid.request_order.order.order_id)
                order_id_int = int(bid.request_order.order.order_id)
            except Exception:
                order_id_str = None
                order_id_int = None

            if order_id_str or order_id_int is not None:
                try:
                    col_orders = get_collection(settings.MONGODB_COLLECTIONS['orders'])
                    # match both string and int order_id for legacy docs
                    res = col_orders.update_one(
                        { '$or': [
                            ({ 'order_id': order_id_str } if order_id_str else {}),
                            ({ 'order_id': order_id_int } if (order_id_int is not None) else {}),
                        ] },
                        { '$set': { 'current_step_index': 2, 'last_updated': now_iso_with_minutes() } },
                        upsert=False
                    )
                    if getattr(res, 'matched_count', 0) == 0:
                        logger.warning('orders not matched to advance step. order_id=%s', order_id_str)
                    else:
                        # 초기 단계 활성화: 샘플 생산 현황(step.index=2)의 첫 stage를 active로 설정
                        try:
                            col_orders.update_one(
                                { '$or': [
                                    ({ 'order_id': order_id_str } if order_id_str else {}),
                                    ({ 'order_id': order_id_int } if (order_id_int is not None) else {}),
                                ] },
                                {
                                    '$set': {
                                        'steps.$[step].stage.$[first].status': 'active',
                                        'steps.$[step].stage.$[first].end_date': '',
                                        'last_updated': now_iso_with_minutes()
                                    }
                                },
                                array_filters=[ { 'step.index': 2 }, { 'first.index': 1 } ],
                                upsert=False
                            )
                        except Exception:
                            logger.exception('Failed to set first stage active for step 2')
                except Exception:
                    logger.exception('Failed to advance orders.current_step_index to 2')
        except Exception:
            # Do not fail selection on step advance errors
            pass
        
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def advance_order_stage(request):
    """
    공정 단계 진행(공장 버튼 트리거)
    - 입력(JSON): { order_id: string|int, phase: 'sample'|'main', stage_index?: number }
    - 동작: 해당 phase의 스텝(샘플=2, 본생산=6)에서
        1) 현재 active이거나 지정된 stage_index 단계를 status='done', end_date=YYYY-MM-DD로 설정
        2) 다음 단계 status='active'로 설정
        3) last_updated 갱신
    - 권한: 공장주만
    """
    try:
        if not hasattr(request.user, 'factory'):
            return Response({'detail': '공장주만 접근할 수 있습니다.'}, status=status.HTTP_403_FORBIDDEN)

        payload = request.data or {}
        order_id_raw = payload.get('order_id')
        phase = (payload.get('phase') or 'sample').strip()
        stage_index_override = payload.get('stage_index')

        if not order_id_raw:
            return Response({'detail': 'order_id가 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)
        if phase not in ('sample', 'main'):
            return Response({'detail': "phase는 'sample' 또는 'main'이어야 합니다."}, status=status.HTTP_400_BAD_REQUEST)

        # step index 결정
        step_idx = 6 if phase == 'main' else 2

        # 문자열/정수 혼용 저장 고려: $or 매칭
        order_id_str = str(order_id_raw)
        try:
            order_id_int = int(order_id_raw)
        except Exception:
            order_id_int = None

        col = get_collection(settings.MONGODB_COLLECTIONS['orders'])

        # 현재 문서 조회 (단계 계산을 위해 읽기)
        doc = col.find_one({ '$or': [
            ({ 'order_id': order_id_str } if order_id_str else {}),
            ({ 'order_id': order_id_int } if order_id_int is not None else {}),
        ] }, projection={ '_id': 0, 'steps': 1, 'factory_id': 1 })
        if not doc:
            return Response({'detail': '해당 주문 문서를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        # 권한: 해당 문서의 factory_id와 로그인 공장 일치(가능할 때)
        try:
            factory_id_in_doc = str(doc.get('factory_id')) if doc.get('factory_id') is not None else None
            if factory_id_in_doc and factory_id_in_doc != str(request.user.factory.id):
                return Response({'detail': '해당 주문에 대한 권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        except Exception:
            pass

        steps = doc.get('steps') or []
        step = None
        for s in steps:
            try:
                if int(s.get('index')) == step_idx:
                    step = s
                    break
            except Exception:
                continue
        if not step:
            return Response({'detail': '대상 단계(step)를 찾을 수 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        stages = step.get('stage') or step.get('stages') or []
        if not isinstance(stages, list) or not stages:
            return Response({'detail': 'stage 목록이 비어있습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        # 진행 대상 stage 인덱스 결정: override > active > 첫 미완료
        target_idx = None
        if stage_index_override is not None:
            try:
                target_idx = int(stage_index_override)
            except Exception:
                return Response({'detail': 'stage_index는 정수여야 합니다.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # active 우선 찾기
            for st in stages:
                if (st.get('status') or '') == 'active':
                    target_idx = int(st.get('index') or 0) or None
                    break
            if target_idx is None:
                # 첫 미완료(끝난 날짜가 없는 것)
                for st in stages:
                    if not st.get('end_date'):
                        try:
                            target_idx = int(st.get('index') or 0)
                            break
                        except Exception:
                            pass
            if target_idx is None:
                # 모두 완료
                return Response({'detail': '모든 단계가 이미 완료되었습니다.'}, status=status.HTTP_200_OK)

        # 다음 단계 인덱스
        indices = [int(st.get('index') or 0) for st in stages if st.get('index') is not None]
        if not indices:
            return Response({'detail': '유효한 stage 인덱스가 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)
        max_idx = max(indices)
        next_idx = target_idx + 1 if target_idx is not None else None

        # 오늘 날짜 문자열
        today = timezone.now().date().isoformat()

        # Mongo 업데이트: arrayFilters로 대상 step과 stage를 지정
        update: dict = {
            '$set': {
                'last_updated': now_iso_with_minutes(),
                # 대상 단계 완료 처리
                'steps.$[step].stage.$[done].status': 'done',
                'steps.$[step].stage.$[done].end_date': today,
            }
        }
        array_filters = [ { 'step.index': step_idx }, { 'done.index': target_idx } ]

        # 다음 단계 활성화
        if next_idx is not None and next_idx <= max_idx:
            update['$set'].update({
                'steps.$[step].stage.$[next].status': 'active',
            })
            array_filters.append({ 'next.index': next_idx })

        res = col.update_one(
            { '$or': [
                ({ 'order_id': order_id_str } if order_id_str else {}),
                ({ 'order_id': order_id_int } if order_id_int is not None else {}),
            ] },
            update,
            array_filters=array_filters,
            upsert=False,
        )

        if getattr(res, 'matched_count', 0) == 0:
            return Response({'detail': '업데이트할 문서를 찾지 못했습니다.'}, status=status.HTTP_404_NOT_FOUND)

        return Response({'detail': '단계가 업데이트되었습니다.', 'done_stage_index': target_idx, 'next_stage_index': next_idx}, status=status.HTTP_200_OK)
    except Exception:
        logger.exception('advance_order_stage error')
        return Response({'detail': '서버 오류가 발생했습니다.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)