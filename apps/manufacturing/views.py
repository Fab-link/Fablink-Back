import logging
from typing import Any
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
from apps.core.services.factory_steps_template import build_factory_steps_template
from apps.accounts.models import Designer

logger = logging.getLogger(__name__)

# --- Stage/Step 무결성 보강 유틸리티 ---------------------------------------
# 일부 역사적 문서가 step index 2, 6 의 stage 목록을 1개(1차 가봉)만 가진 상태로
# 저장되어 프론트 진행 상황 다이얼로그에서 나머지 stage (2~6)가 표시되지 않는 문제가 보고됨.
# 최신 템플릿(build_orders_steps_template)에는 6개 stage 가 정의되어 있으므로
# 조회 시 누락된 stage 항목을 동적으로 보강하고, 필요 시 DB에도 반영한다.

_TEMPLATE_STAGE = [
    {"index": 1, "name": "1차 가봉",       "status": "", "end_date": ""},
    {"index": 2, "name": "부자재 부착",   "status": "", "end_date": ""},
    {"index": 3, "name": "마킹 및 재단",   "status": "", "end_date": ""},
    {"index": 4, "name": "봉제",           "status": "", "end_date": ""},
    {"index": 5, "name": "검사 및 다림질", "status": "", "end_date": ""},
    {"index": 6, "name": "배송",           "status": "", "end_date": "", "delivery_code": ""},
]

def _merge_stage_list(existing: list[dict]) -> tuple[list[dict], bool]:
    """기존 stage 리스트(existing)를 템플릿과 merge.
    - 동일 index 는 기존 end_date/status/delivery_code 유지
    - 누락 index 는 템플릿 기본값 추가
    반환: (merged_list, changed)
    """
    if not isinstance(existing, list):
        return [_ for _ in _TEMPLATE_STAGE], True
    by_index: dict[int, dict] = {int(s.get("index")): s for s in existing if s.get("index") is not None}
    changed = False
    merged: list[dict] = []
    for tpl in _TEMPLATE_STAGE:
        idx = tpl["index"]
        if idx in by_index:
            cur = by_index[idx]
            # ensure required keys exist
            # preserve existing mutable fields
            merged.append({
                "index": idx,
                "name": cur.get("name") or tpl["name"],
                "status": cur.get("status", ""),
                "end_date": cur.get("end_date", ""),
                **({"delivery_code": cur.get("delivery_code", cur.get("deliveryCode", ""))} if idx == 6 else {}),
            })
        else:
            changed = True
            merged.append({**tpl})
    # 변경 여부 추가 판단 (길이/순서 차이)
    if not changed:
        if len(existing) != len(merged):
            changed = True
        else:
            for a, b in zip(existing, merged):
                if int(a.get("index", -1)) != int(b.get("index", -1)):
                    changed = True
                    break
    return merged, changed

def repair_steps_stage_integrity(doc: dict) -> bool:
    """주문 문서의 steps 중 index 2, 6 단계의 stage 배열을 템플릿 기준으로 보강.
    반환: 수정 발생 여부(True/False)
    """
    steps = doc.get("steps")
    if not isinstance(steps, list):
        return False
    changed_any = False
    for step in steps:
        try:
            idx = int(step.get("index"))
        except Exception:
            continue
        if idx not in (2, 6):
            continue
        cur_stage = step.get("stage")
        merged, changed = _merge_stage_list(cur_stage if isinstance(cur_stage, list) else [])
        if changed:
            step["stage"] = merged
            changed_any = True
    return changed_any

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
        
        # Mongo orders 에서 current_step_index / steps 배치 조회 (order_id 기반)
        current_idx_map: dict[str, int] = {}
        steps_map: dict[str, Any] = {}
        overall_status_map: dict[str, Any] = {}
        last_updated_map: dict[str, Any] = {}
        try:
            order_ids = list({str(r.order.order_id) for r in request_orders if getattr(r.order, 'order_id', None) is not None})
            if order_ids:
                col_orders_fact = get_collection(settings.MONGODB_COLLECTIONS['orders'])
                cur = col_orders_fact.find(
                    { 'order_id': { '$in': order_ids } },
                    projection={ '_id': 0, 'order_id': 1, 'current_step_index': 1, 'steps': 1, 'overall_status': 1, 'last_updated': 1 }
                )
                for doc in cur:
                    oid = str(doc.get('order_id'))
                    try:
                        current_idx_map[oid] = int(doc.get('current_step_index') or 1)
                    except Exception:
                        # 문자열 '1' 등 비정상 값 fallback
                        try:
                            current_idx_map[oid] = int(str(doc.get('current_step_index')).strip()) if doc.get('current_step_index') is not None else 1
                        except Exception:
                            current_idx_map[oid] = 1
                    if 'steps' in doc:
                        steps_map[oid] = doc.get('steps')
                    if 'overall_status' in doc:
                        overall_status_map[oid] = doc.get('overall_status')
                    if 'last_updated' in doc:
                        last_updated_map[oid] = doc.get('last_updated')
        except Exception:
            logger.exception('get_factory_orders: failed to fetch current_step_index from orders')

        debug_flag = request.query_params.get('debug') == '1'

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
            
            mongo_oid = str(req_order.order.order_id)
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

            # Mongo 진행 단계 정보 주입
            order_data['current_step_index'] = current_idx_map.get(mongo_oid, 1)
            order_data['overall_status'] = overall_status_map.get(mongo_oid, '')
            order_data['last_updated'] = last_updated_map.get(mongo_oid)
            if debug_flag:
                order_data['steps'] = steps_map.get(mongo_oid)
            
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
            logger.exception('get_designer_orders: failed to fetch current_step_index from designer_orders')

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
    공장주용 factory_orders 목록(MongoDB)
    - 인증된 공장 사용자만 접근 가능
    - 기본 정렬: last_updated desc
    - 페이징: ?page=1&page_size=20 (최대 100)
    - 필터: ?phase=sample|main (선택), ?status=...
    응답 형식:
    {
      count, page, page_size, has_next,
      results: [{ order_id, phase, factory_id, overall_status, due_date, quantity, unit_price, last_updated, product_id }]
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

        col = get_collection(settings.MONGODB_COLLECTIONS['factory_orders'])

        # 정렬 및 페이징 쿼리
        total = col.count_documents(q)
        try:
            # 디버그: 목록이 비거나 debug 모드이면 쿼리 조건/total 즉시 로깅
            if total == 0 or debug_mode:
                logger.info('factory-orders-mongo query=%s total=%s page=%s page_size=%s debug=%s', q, total, page, page_size, debug_mode)
        except Exception:
            pass
        cursor = (
            col.find(q, projection={
                '_id': 0,
                'order_id': 1,
                'phase': 1,
                'factory_id': 1,
                'overall_status': 1,
                'due_date': 1,
                'quantity': 1,
                'unit_price': 1,
                'currency': 1,
                'last_updated': 1,
                'product_id': 1,
                'steps': 1,
                'designer_id': 1,
                # 진행 단계 필드 누락으로 프론트/디버그 요약에서 항상 1로 fallback 되는 문제 수정
                'current_step_index': 1,
            })
            .sort('last_updated', -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )

        items = list(cursor)

        # Stage 무결성 보강 (in-memory) 및 필요 시 비동기성 없이 즉시 update
        # (문서 수가 페이지 단위이므로 성능 영향 미미)
        for it in items:
            try:
                if repair_steps_stage_integrity(it):
                    # DB 반영: steps 와 last_updated만 업데이트
                    try:
                        col.update_one({'order_id': it.get('order_id')}, {'$set': {'steps': it.get('steps'), 'last_updated': now_iso_with_minutes()}})
                    except Exception:
                        logger.exception('failed to persist repaired stages (order_id=%s)', it.get('order_id'))
            except Exception:
                logger.exception('stage integrity repair error (order_id=%s)', it.get('order_id'))

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

        # Fallback: pull product_id/designer_id from designer_orders if missing
        try:
            missing_ids = [str(it.get('order_id')) for it in items if not it.get('product_id') or not it.get('designer_id')]
            missing_ids = [oid for oid in missing_ids if oid and oid != 'None']
            if missing_ids:
                col_designer = get_collection(settings.MONGODB_COLLECTIONS['designer_orders'])
                cur2 = col_designer.find(
                    { 'order_id': { '$in': missing_ids } },
                    projection={ '_id': 0, 'order_id': 1, 'product_id': 1, 'designer_id': 1 }
                )
                di_map = {doc.get('order_id'): doc for doc in cur2}
                for it in items:
                    oid = str(it.get('order_id'))
                    doc = di_map.get(oid)
                    if not doc:
                        continue
                    if not it.get('product_id') and doc.get('product_id'):
                        it['product_id'] = str(doc.get('product_id'))
                    if not it.get('designer_id') and doc.get('designer_id'):
                        it['designer_id'] = str(doc.get('designer_id'))
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

        # Fill missing unit_price / due_date from BidFactory joined via RequestOrder
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
                            if it.get('unit_price') in (None, ''):
                                it['unit_price'] = getattr(bid, 'work_price', None)
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
                    # Progress diagnostics
                    steps = it.get('steps') if isinstance(it.get('steps'), list) else []
                    # 실제 Mongo 값 사용(0/None 아닌 경우). 과거 projection 누락으로 기본 1이었던 문제 해결.
                    if it.get('current_step_index') is not None:
                        current_step_index = it.get('current_step_index')
                    elif it.get('currentStepIndex') is not None:
                        current_step_index = it.get('currentStepIndex')
                    else:
                        current_step_index = 1
                    steps_count = len(steps)
                    completed_count = 0
                    current_step_status = None
                    current_step_has_end_date = None
                    can_complete = False
                    locked_reason = None
                    steps_progress = []  # detailed per-step progress for debugging
                    try:
                        for s in steps:
                            idx = s.get('index')
                            end_date = s.get('end_date') or s.get('endDate')
                            status_val = s.get('status')
                            if end_date:
                                completed_count += 1
                            if idx == current_step_index:
                                current_step_status = status_val
                                current_step_has_end_date = bool(end_date)
                            steps_progress.append({
                                'index': idx,
                                'name': s.get('name'),
                                'status': status_val,
                                'end_date': end_date,
                                'done': bool(end_date),
                            })
                        if steps_count > 0:
                            if current_step_index < 1 or current_step_index > steps_count:
                                can_complete = False
                                locked_reason = 'out_of_range'
                            else:
                                if current_step_has_end_date:
                                    can_complete = False
                                    locked_reason = 'already_completed'
                                else:
                                    can_complete = True
                        else:
                            locked_reason = 'no_steps'
                    except Exception:
                        locked_reason = 'diag_error'

                    debug_item = {
                        'order_id': it.get('order_id'),
                        'factory_id': it.get('factory_id'),
                        'phase': it.get('phase'),
                        'product_id': it.get('product_id'),
                        'product_name': it.get('product_name'),
                        'designer_id': it.get('designer_id'),
                        'designer_name': it.get('designer_name'),
                        'unit_price': it.get('unit_price'),
                        'currency': it.get('currency'),
                        'due_date': it.get('due_date'),
                        'quantity': it.get('quantity'),
                        'overall_status': it.get('overall_status'),
                        # Progress debug additions
                        'current_step_index': current_step_index,
                        'steps_count': steps_count,
                        'completed_steps': completed_count,
                        'incomplete_steps': (steps_count - completed_count) if steps_count else 0,
                        'current_step_status': current_step_status,
                        'current_step_has_end_date': current_step_has_end_date,
                        'can_complete': can_complete,
                        'locked_reason': locked_reason,
                        'next_step_index': (current_step_index + 1) if steps_count and current_step_index < steps_count else None,
                        'steps_progress': steps_progress,
                    }
                    debug_list.append(debug_item)
                debug_payload = {
                    'query': {'phase': phase, 'status': status_filter, 'factory_id': factory_id},
                    'size': len(items),
                    'items': debug_list,
                }
                logger.info('factory-orders-mongo debug: %s', debug_payload)
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
                'work_price': bid.work_price,
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
    # Frontend now sends 'work_price' directly; legacy 'unit_price' removed.
    # If backward compatibility needed, uncomment below line.
    # if 'work_price' not in data and 'unit_price' in data:
    #     data['work_price'] = data.get('unit_price')
        
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

        # 선택된 입찰의 요청 상태를 샘플 매칭으로 업데이트
        try:
            req_order = bid.request_order
            # STATUS_CHOICES에 따라 샘플 매칭 상태로 설정
            req_order.status = 'sample_matched'
            req_order.save(update_fields=['status'])
        except Exception:
            # 상태 업데이트 실패가 전체 플로우를 막지 않도록 로그만 남김
            logger.exception('Failed to update RequestOrder.status to sample_matched')

        # factory_orders 문서 upsert (시그널 보조/폴백)
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
            product_id = str(product.id) if getattr(product, 'id', None) else None
            designer_id = str(product.designer.id) if getattr(product, 'designer', None) else None
            factory_id = str(factory.id) if getattr(factory, 'id', None) else None

            phase = 'sample'  # 샘플 선정 단계 기준

            base_doc = {
                'order_id': order_id,
                'phase': phase,
                'factory_id': factory_id,
                'designer_id': designer_id,
                'product_id': product_id,
            }
            # Mongo에 date를 그대로 넣지 않고 문자열로 변환
            expect_date = getattr(bid, 'expect_work_day', None)
            if hasattr(expect_date, 'isoformat'):
                try:
                    expect_date = expect_date.isoformat()
                except Exception:
                    expect_date = None

            business_fields = {
                'quantity': getattr(ro, 'quantity', None),
                'unit_price': getattr(bid, 'work_price', None),
                'currency': 'KRW',
                'due_date': expect_date,
                'delivery_status': '',
                'delivery_code': '',
            }

            col = get_collection(settings.MONGODB_COLLECTIONS['factory_orders'])
            update_doc = {
                '$setOnInsert': {
                    **base_doc,
                    'current_step_index': 1,
                    'overall_status': '',
                    'steps': build_factory_steps_template(phase),
                },
                '$set': {
                    **business_fields,
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
                col.update_one(
                    {'order_id': order_id, 'phase': phase, 'factory_id': factory_id},
                    update_doc,
                    upsert=True,
                )
            except Exception:
                logger.exception('Failed to upsert factory_orders in select_bid')
        except Exception:
            logger.exception('factory_orders upsert fallback block failed')

        # orders: step 1(업체 선정) 완료 처리 + current_step_index -> 2 (조건부, 이미 2 이상이면 skip)
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
                    # current_step_index < 2 조건에서 step 1 완료(status/end_date) + current_step_index=2 원자적 처리
                    now_ts = now_iso_with_minutes()
                    # 사전 문서 스냅샷 로깅 (타입 확인 목적)
                    try:
                        doc_before = col_orders.find_one({'order_id': order_id_str}, projection={'_id': 0, 'current_step_index': 1, 'steps': 1})
                        if doc_before is not None:
                            logger.info('orders pre-advance snapshot order_id=%s current_step_index=%s (type=%s)', order_id_str, doc_before.get('current_step_index'), type(doc_before.get('current_step_index')).__name__)
                        else:
                            logger.warning('orders pre-advance snapshot missing doc order_id=%s', order_id_str)
                    except Exception:
                        logger.exception('orders pre-advance snapshot failed order_id=%s', order_id_str)

                    # 필드 타입이 문자열 '1' 이거나 누락된 경우도 포함해 전진 필터 구성
                    advance_filter = {
                        'order_id': order_id_str,
                        '$or': [
                            { 'current_step_index': { '$lt': 2 } },  # 정상 numeric 케이스
                            { 'current_step_index': '1' },            # 과거 string 저장 케이스
                            { 'current_step_index': { '$exists': False } },  # 누락 케이스
                        ]
                    }
                    res_atomic = col_orders.update_one(
                        advance_filter,
                        {
                            '$set': {
                                'current_step_index': 2,
                                'last_updated': now_ts,
                                'steps.$[s].status': 'completed',
                                'steps.$[s].end_date': now_ts,
                            }
                        },
                        array_filters=[ { 's.index': 1, 's.status': { '$ne': 'completed' } } ],
                        upsert=False
                    )
                    if getattr(res_atomic, 'matched_count', 0) == 0:
                        # 1차 시도 실패: 현재 값이 이미 2 이상이거나 타입/조건 불일치. 추가 디버그.
                        try:
                            doc_after_fail = col_orders.find_one({'order_id': order_id_str}, projection={'_id': 0, 'current_step_index': 1, 'steps': 1})
                            logger.warning('orders advance mismatch order_id=%s snapshot_after_fail=%s', order_id_str, doc_after_fail)
                        except Exception:
                            logger.exception('orders advance mismatch snapshot fetch failed order_id=%s', order_id_str)
                    else:
                        logger.info('orders step 1 completed & advanced to 2. order_id=%s modified=%s', order_id_str, getattr(res_atomic, 'modified_count', '?'))
                except Exception:
                    logger.exception('Failed to atomically complete step 1 & advance current_step_index to 2')
        except Exception:
            logger.exception('Failed to advance designer_orders.current_step_index to 2')
        
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_order_mongo(request, order_id: str):
    """단일 Mongo orders 문서 조회 (factory 권한 제한).
    - factory 사용자: 자신의 factory_id가 문서에 매칭되어야 함
    - designer 사용자: 현재는 제한 (필요 시 확장)
    """
    try:
        col = get_collection(settings.MONGODB_COLLECTIONS['orders'])
        doc = col.find_one({'order_id': str(order_id)})
        if not doc:
            return Response({'detail': '주문 문서를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        # 권한 검사: factory 사용자인 경우 factory_id 일치 필요
        if hasattr(request.user, 'factory'):
            f_id = str(getattr(request.user.factory, 'id', ''))
            if doc.get('factory_id') and doc.get('factory_id') != f_id:
                return Response({'detail': '권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        else:
            # 비-factory 사용자는 차후 정책 확정 전까지 차단 (필요 시 디자이너 허용 가능)
            return Response({'detail': '공장 사용자만 접근 가능합니다.'}, status=status.HTTP_403_FORBIDDEN)

        # ObjectId 제거 등 직렬화 안전 처리
        doc.pop('_id', None)
        # 단일 조회 시에도 stage 무결성 보강
        if repair_steps_stage_integrity(doc):
            try:
                col.update_one({'order_id': str(order_id)}, {'$set': {'steps': doc.get('steps'), 'last_updated': now_iso_with_minutes()}})
            except Exception:
                logger.exception('failed to persist repaired stages on single fetch (order_id=%s)', order_id)
        return Response(doc, status=status.HTTP_200_OK)
    except Exception:
        logger.exception('get_order_mongo error')
        return Response({'detail': '서버 오류'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_order_progress_mongo(request, order_id: str):
    """현재 진행중 '단계' 또는 해당 단계의 'stage'(하위 작업)를 완료 처리.
    요청 body:
        - 단계 완료: { "complete_step_index": <int> }
        - stage 완료: { "complete_step_index": <int>, "complete_stage_index": <int> }
    규칙:
        - 단계/스테이지 모두 순차 진행(가장 낮은 미완료 index만 완료 가능)
        - complete_step_index 는 문서의 current_step_index 와 일치해야 단계 완료 가능
        - stage 완료 시:
                * 해당 step 이 stage 배열을 가진 경우에만 허용
                * 아직 완료되지 않은 stage 중 index 가장 낮은 항목만 완료 가능
                * 모든 stage 완료되면 상위 step end_date/status=completed 설정 후 current_step_index 전진
        - 단계 직접 완료(PATCH에 stage 인덱스 미포함)는 stage 배열이 없거나(stage 모두 완료) 현재 step 이 stage 없는 일반 단계일 때 사용
        - 마지막 단계 완료 시 overall_status='completed'
    """
    try:
        col = get_collection(settings.MONGODB_COLLECTIONS['orders'])
        doc = col.find_one({'order_id': str(order_id)})
        if not doc:
            return Response({'detail': '주문 문서를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        # 권한: factory 소유
        if hasattr(request.user, 'factory'):
            f_id = str(getattr(request.user.factory, 'id', ''))
            if doc.get('factory_id') and doc.get('factory_id') != f_id:
                return Response({'detail': '권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({'detail': '공장 사용자만 변경할 수 있습니다.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            payload = request.data or {}
            step_to_complete = int(payload.get('complete_step_index'))
            stage_to_complete = payload.get('complete_stage_index')
            if stage_to_complete is not None:
                stage_to_complete = int(stage_to_complete)
        except Exception:
            return Response({'detail': 'complete_step_index / complete_stage_index 정수 필요'}, status=status.HTTP_400_BAD_REQUEST)

        current_idx = int(doc.get('current_step_index') or 1)
        steps = doc.get('steps') or []
        if not isinstance(steps, list) or len(steps) == 0:
            return Response({'detail': 'steps 데이터가 비었습니다.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        total_steps = len(steps)

        if step_to_complete != current_idx:
            return Response({'detail': 'current_step_index 와 일치하는 단계만 완료 가능', 'current_step_index': current_idx}, status=status.HTTP_400_BAD_REQUEST)
        if step_to_complete < 1 or step_to_complete > total_steps:
            return Response({'detail': '유효하지 않은 단계 인덱스입니다.'}, status=status.HTTP_400_BAD_REQUEST)
        # 이후 로직은 try 블록 내부에 있어야 하므로 들여쓰기 수정
        step_doc = steps[step_to_complete - 1]

        # Stage 기반 단계인지 확인
        is_stage_step = isinstance(step_doc.get('stage'), list) and len(step_doc['stage']) > 0

        # 완료 타임스탬프(분 단위 ISO) - stage/step end_date 에 공통 사용
        now_str = now_iso_with_minutes()
        set_updates = {'last_updated': now_str}

        if stage_to_complete is not None:
            if not is_stage_step:
                return Response({'detail': '해당 단계는 stage 목록이 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)
            stages = step_doc['stage']
            # 순차 진행: 미완료(stage.end_date 비어있는) stage 들 중 index 가장 낮은 것만 허용
            pending_stages = [s for s in stages if not s.get('end_date')]
            if not pending_stages:
                return Response({'detail': '이미 모든 stage 완료됨'}, status=status.HTTP_400_BAD_REQUEST)
            lowest_pending_index = min(s.get('index') for s in pending_stages if s.get('index') is not None)
            if stage_to_complete != lowest_pending_index:
                return Response({'detail': '가장 낮은 미완료 stage 만 완료 가능', 'next_stage_index': lowest_pending_index}, status=status.HTTP_400_BAD_REQUEST)
            # 해당 stage 위치 찾기 (배열 내 순서가 index 순서와 다를 수 있으므로 검색)
            stage_pos = None
            for pos, s in enumerate(stages):
                if s.get('index') == stage_to_complete:
                    stage_pos = pos
                    break
            if stage_pos is None:
                return Response({'detail': 'stage 인덱스를 찾을 수 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)
            if stages[stage_pos].get('end_date'):
                return Response({'detail': '이미 완료된 stage 입니다.'}, status=status.HTTP_400_BAD_REQUEST)
            # stage 완료 셋업
            set_updates[f'steps.{step_to_complete - 1}.stage.{stage_pos}.end_date'] = now_str
            set_updates[f'steps.{step_to_complete - 1}.stage.{stage_pos}.status'] = 'done'

            # 모든 stage 완료되었는지 재평가
            all_done = True
            for s in stages:
                if not s.get('end_date') and s is not stages[stage_pos]:  # 완료된 것 제외
                    all_done = False
                    break
            if all_done:
                # 상위 step 완료 처리
                if not step_doc.get('end_date'):
                    set_updates[f'steps.{step_to_complete - 1}.end_date'] = now_str
                set_updates[f'steps.{step_to_complete - 1}.status'] = 'done'
                next_index = current_idx + 1
                if next_index <= total_steps:
                    set_updates['current_step_index'] = next_index
                else:
                    set_updates['current_step_index'] = current_idx
                    if doc.get('overall_status') != 'done':
                        set_updates['overall_status'] = 'done'
        else:
            # 단계 직접 완료. stage 단계인 경우: 모든 stage 미완료이면 불허
            if is_stage_step:
                any_pending = any(not s.get('end_date') for s in step_doc['stage'])
                if any_pending:
                    return Response({'detail': 'stage 가 남아있어 단계 직접 완료 불가', 'pending_stage_indices': [s.get('index') for s in step_doc['stage'] if not s.get('end_date')]}, status=status.HTTP_400_BAD_REQUEST)
            if step_doc.get('end_date'):
                return Response({'detail': '이미 완료된 단계'}, status=status.HTTP_400_BAD_REQUEST)
            set_updates[f'steps.{step_to_complete - 1}.end_date'] = now_str
            set_updates[f'steps.{step_to_complete - 1}.status'] = 'done'
            next_index = current_idx + 1
            if next_index <= total_steps:
                set_updates['current_step_index'] = next_index
            else:
                set_updates['current_step_index'] = current_idx
                if doc.get('overall_status') != 'done':
                    set_updates['overall_status'] = 'done'

        try:
            res = col.update_one({'order_id': str(order_id)}, {'$set': set_updates})
            if getattr(res, 'matched_count', 0) == 0:
                return Response({'detail': '업데이트 실패'}, status=status.HTTP_409_CONFLICT)
        except Exception:
            logger.exception('update_order_progress_mongo update_one error')
            return Response({'detail': '업데이트 오류'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 갱신된 문서 재조회
        new_doc = col.find_one({'order_id': str(order_id)}) or {}
        new_doc.pop('_id', None)
        return Response(new_doc, status=status.HTTP_200_OK)
    except Exception:
        logger.exception('update_order_progress_mongo error')
        return Response({'detail': '서버 오류'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)