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
from apps.core.services.orders_steps_template import build_orders_steps_template  # 추가: 주문 steps 템플릿
from apps.accounts.models import Designer

logger = logging.getLogger(__name__)

# --- Stage/Step 무결성 보강 유틸리티 ---------------------------------------
# 일부 역사적 문서가 step index 2, 6 의 stage 리스트가 누락/불완전하여 stage 표시 문제가 발생.
# 조회 시 템플릿 기준으로 보강하며 필요 시 DB 반영.

_TEMPLATE_STAGE = [
    {"index": 1, "name": "1차 가봉",       "status": "", "end_date": ""},
    {"index": 2, "name": "부자재 부착",   "status": "", "end_date": ""},
    {"index": 3, "name": "마킹 및 재단",   "status": "", "end_date": ""},
    {"index": 4, "name": "봉제",           "status": "", "end_date": ""},
    {"index": 5, "name": "검사 및 다림질", "status": "", "end_date": ""},
    {"index": 6, "name": "배송",           "status": "", "end_date": "", "delivery_code": ""},
]

def _merge_stage_list(existing: list[dict]) -> tuple[list[dict], bool]:
    if not isinstance(existing, list):
        return [_ for _ in _TEMPLATE_STAGE], True
    by_index: dict[int, dict] = {int(s.get("index")): s for s in existing if s.get("index") is not None}
    changed = False
    merged: list[dict] = []
    for tpl in _TEMPLATE_STAGE:
        idx = tpl["index"]
        if idx in by_index:
            cur = by_index[idx]
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

        # Fallback: ensure Mongo unified orders document exists (signals may have failed if import disabled)
        try:
            from apps.core.services.mongo import get_collection, now_iso_with_minutes, ensure_indexes
            from apps.core.services.orders_steps_template import build_orders_steps_template
            try:
                ensure_indexes()
            except Exception:
                pass
            col = get_collection(settings.MONGODB_COLLECTIONS['orders'])
            order_id_str = str(order.order_id)
            if not col.find_one({'order_id': order_id_str}):
                col.update_one(
                    {'order_id': order_id_str},
                    {
                        '$setOnInsert': {
                            'order_id': order_id_str,
                            'current_step_index': 1,
                            'overall_status': '',
                            'phase': 'sample',
                            'steps': build_orders_steps_template(),
                        },
                        '$set': {
                            'designer_id': str(product.designer.id),
                            'product_id': str(product.id),
                            'last_updated': now_iso_with_minutes(),
                        },
                    },
                    upsert=True,
                )
        except Exception:
            logger.exception('submit_manufacturing fallback Mongo upsert failed')

        return Response({
            'product_id': product.id,
            'order_id': order.order_id,
            'request_order_id': request_order.id,
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.exception('submit_manufacturing error')
        return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


## Legacy list endpoints (get_factory_orders, get_designer_orders) removed: use get_orders_mongo


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def get_orders_mongo(request):
    """Unified orders list (designer + factory).
    Filters:
      - page, page_size (<=100)
      - status (overall_status)
      - role-based access:
         * designer: product.designer == user.designer.id
         * factory: (factory_id == user.factory.id) OR factory in steps.factory_list.factory_id
    """
    try:
        try:
            page = int(request.GET.get('page', '1'))
            page_size = int(request.GET.get('page_size', '20'))
        except ValueError:
            return Response({'detail': 'page/page_size는 정수여야 합니다.'}, status=status.HTTP_400_BAD_REQUEST)
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        status_filter = request.GET.get('status')
        debug_mode = str(request.GET.get('debug', '')).lower() in ('1','true','yes')

        col = get_collection(settings.MONGODB_COLLECTIONS['orders'])

        base_query: dict = {}
        if status_filter:
            base_query['overall_status'] = status_filter

        is_designer = hasattr(request.user, 'designer')
        is_factory = hasattr(request.user, 'factory')
        if not (is_designer or is_factory):
            return Response({'detail': '권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)

        if is_designer:
            designer_id = str(request.user.designer.id)
            base_query['designer_id'] = designer_id
        else:
            factory_id = str(request.user.factory.id)
            base_query['$or'] = [
                {'factory_id': factory_id},
                {'steps.factory_list.factory_id': factory_id},
            ]

        total = col.count_documents(base_query)
        # 전체 문서가 필요하다는 요구사항(/factory/orders/ 전체 필드 표시) 반영: projection 제거하여 _id 제외 모든 필드 반환
        # (주의) 문서 크기 증가에 따른 네트워크 비용 상승 가능 → 필요시 page_size 조절 또는 full=0/1 파라미터 도입 고려
        cursor = col.find(
            base_query,
            projection={'_id': 0}  # _id만 제거, 나머지 전체
        ).sort('last_updated', -1).skip((page-1)*page_size).limit(page_size)
        items = list(cursor)

        for it in items:
            try:
                if repair_steps_stage_integrity(it):
                    col.update_one({'order_id': it.get('order_id')}, {'$set': {'steps': it.get('steps'), 'last_updated': now_iso_with_minutes()}})
            except Exception:
                logger.exception('stage integrity repair error (order_id=%s)', it.get('order_id'))

        # --- Meta enrichment: Mongo 문서에 누락된 상위 메타(designer_name, product_name, quantity, due_date) 보강 ---
        # 기존 문서(과거 생성)들이 초기 upsert 시 이름/메타를 채우지 않아 프론트에서 '-' 노출되는 문제 해결.
        # N회 find_one 대신 product_id 모아서 bulk ORM 조회 후 메모리에 매핑.
        try:
            need_enrich: list[dict] = []
            product_ids: set[int] = set()
            for it in items:
                # 누락 판정: 하나라도 비어 있으면 enrichment 대상 (work_price 포함)
                cond_missing_meta = not (it.get('designer_name') and it.get('product_name') and it.get('quantity') and it.get('due_date'))
                cond_missing_price = it.get('work_price') in (None, '', 0)
                if cond_missing_meta or cond_missing_price:
                    pid_raw = it.get('product_id') or it.get('productId')
                    try:
                        if pid_raw is not None:
                            pid_int = int(pid_raw)
                            product_ids.add(pid_int)
                            need_enrich.append(it)
                    except Exception:
                        continue
            if need_enrich and product_ids:
                prod_qs = Product.objects.filter(id__in=product_ids).select_related('designer')
                prod_map = {p.id: p for p in prod_qs}
                for it in need_enrich:
                    pid_raw = it.get('product_id') or it.get('productId')
                    try:
                        pid_int = int(pid_raw)
                    except Exception:
                        continue
                    p = prod_map.get(pid_int)
                    if not p:
                        continue
                    changed = False
                    # 제품/디자이너 메타
                    if not it.get('product_name'):
                        it['product_name'] = p.name or ''
                        changed = True
                    if not it.get('designer_name'):
                        try:
                            designer_nm = getattr(p.designer, 'name', '') or ''
                        except Exception:
                            designer_nm = ''
                        it['designer_name'] = designer_nm
                        # 프론트 별칭도 함께 (camelCase)
                        it['designerName'] = designer_nm
                        changed = True
                    else:
                        # designerName alias 가 없으면 추가
                        if not it.get('designerName'):
                            it['designerName'] = it.get('designer_name')
                            changed = True
                    if not it.get('quantity'):
                        it['quantity'] = p.quantity or 0
                        changed = True
                    if not it.get('due_date') and getattr(p, 'due_date', None):
                        try:
                            it['due_date'] = p.due_date.isoformat()
                        except Exception:
                            it['due_date'] = ''
                        changed = True
                    # work_price: 선정된 입찰(bid) 기반 상단 work_price 미기록 문서 처리.
                    # 우선 steps[0].factory_list 에 bid 정보(work_price)가 있으면 그 중 최소값(또는 첫 값)을 채움.
                    if it.get('work_price') in (None, '', 0):
                        try:
                            steps_arr = it.get('steps') or []
                            if isinstance(steps_arr, list) and steps_arr:
                                fac_list = steps_arr[0].get('factory_list') if isinstance(steps_arr[0], dict) else None
                                if isinstance(fac_list, list) and fac_list:
                                    prices = [f.get('work_price') for f in fac_list if isinstance(f, dict) and isinstance(f.get('work_price'), (int, float)) and f.get('work_price') > 0]
                                    if prices:
                                        it['work_price'] = min(prices)
                                        changed = True
                        except Exception:
                            pass
                    if changed:
                        try:
                            update_fields = {
                                'product_name': it.get('product_name'),
                                'designer_name': it.get('designer_name'),
                                'quantity': it.get('quantity'),
                                'due_date': it.get('due_date'),
                                'last_updated': now_iso_with_minutes(),
                            }
                            if it.get('work_price') not in (None, '', 0):
                                update_fields['work_price'] = it.get('work_price')
                            col.update_one(
                                {'order_id': it.get('order_id')},
                                {'$set': update_fields},
                                upsert=False
                            )
                        except Exception:
                            logger.exception('meta enrichment persist failed (order_id=%s)', it.get('order_id'))
        except Exception:
            logger.exception('meta enrichment block failed')

        debug_summary = None
        debug_raw_docs = None
        if debug_mode:
            try:
                debug_summary = {
                    'query': base_query,
                    'page': page,
                    'page_size': page_size,
                    'returned': len(items),
                    'projection': 'FULL_DOCUMENT',  # 전체 문서 반환 모드 표시
                }
                # 페이지에 표시된 order_id 들의 원본 문서를 projection 없이 추가 (민감정보 최소화 위해 제한)
                order_ids = [it.get('order_id') for it in items if it.get('order_id')]
                if order_ids:
                    raw_cursor = col.find({'order_id': {'$in': order_ids}})
                    raw_docs = []
                    for doc in raw_cursor:
                        doc.pop('_id', None)
                        raw_docs.append(doc)
                    debug_raw_docs = raw_docs
            except Exception:
                logger.exception('failed to build debug payload for unified orders')

        resp_payload = {
            'count': total,
            'page': page,
            'page_size': page_size,
            'has_next': (page * page_size) < total,
            'results': items,
        }
        if debug_summary:
            resp_payload['debug_summary'] = debug_summary
        if debug_raw_docs is not None:
            resp_payload['debug_raw_docs'] = debug_raw_docs
        return Response(resp_payload, status=status.HTTP_200_OK)
    except Exception:
        logger.exception('get_orders_mongo error')
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def has_factory_bid(request):
    """현재 로그인한 factory 사용자가 특정 order 에 대해 이미 입찰(bid_factory 레코드)을 제출했는지 여부.
    입력 쿼리 파라미터: order_id
    응답: { has_bid: bool, bid_id: int|None }
    권한: factory 사용자만.
    """
    try:
        if not hasattr(request.user, 'factory'):
            return Response({'detail': '공장 사용자만 조회할 수 있습니다.'}, status=status.HTTP_403_FORBIDDEN)
        order_id = request.GET.get('order_id')
        if not order_id:
            return Response({'detail': 'order_id 파라미터 필요'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            # order_id 는 BidFactory->request_order->order.order_id 경로로 매칭
            bid = BidFactory.objects.select_related('request_order__order').filter(
                request_order__order__order_id=order_id,
                factory=request.user.factory,
            ).first()
        except Exception:
            bid = None
        return Response({'has_bid': bool(bid), 'bid_id': bid.id if bid else None}, status=status.HTTP_200_OK)
    except Exception:
        logger.exception('has_factory_bid error')
        return Response({'detail': '서버 오류'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def get_factory_quotes(request):
    """공장 견적 요청 목록 (RequestOrder 기반)
    - 대상: 로그인한 factory 사용자만
    - 필터: RequestOrder.status in (sample_pending, product_pending)
    - 응답 필드:
        request_order_id, order_id, status, quantity, due_date, work_sheet_url,
        product_info: { name, season, target, concept, detail, size, quantity, dueDate, memo, imageUrl, workSheetUrl },
        designer: { id, name, contact, address }
    프론트 요구사항: 카드 표시용 designer 이름/전화/주소, 제품 수량/작업지시서 URL 제공
    """
    try:
        if not hasattr(request.user, 'factory'):
            return Response({'detail': '공장 사용자만 접근 가능합니다.'}, status=status.HTTP_403_FORBIDDEN)

        qs = (RequestOrder.objects
              .select_related('order__product__designer')
              .filter(status__in=['sample_pending', 'product_pending']))

        # 향후 페이징 필요 시 page/page_size 파라미터 처리 가능 (현재 최대 500 제한)
        page_size = 500
        items = []
        for ro in qs.order_by('-id')[:page_size]:
            product = getattr(ro.order, 'product', None)
            designer = getattr(product, 'designer', None) if product else None
            # 파일 URL 구성
            def _abs(u):
                if not u:
                    return None
                try:
                    return request.build_absolute_uri(u)
                except Exception:
                    return u
            work_sheet_url = _abs(ro.work_sheet_path.url) if ro.work_sheet_path else None
            product_image_url = _abs(product.image_path.url) if (product and product.image_path) else None
            product_work_sheet_url = _abs(product.work_sheet_path.url) if (product and product.work_sheet_path) else None
            product_info = {
                'id': product.id if product else None,
                'name': product.name if product else ro.product_name,
                'season': getattr(product, 'season', ''),
                'target': getattr(product, 'target', ''),
                'concept': getattr(product, 'concept', ''),
                'detail': getattr(product, 'detail', ''),
                'size': getattr(product, 'size', ''),
                'quantity': getattr(product, 'quantity', None) or ro.quantity,
                'dueDate': getattr(product, 'due_date', None) or ro.due_date,
                'memo': getattr(product, 'memo', ''),
                'imageUrl': product_image_url,
                'workSheetUrl': work_sheet_url or product_work_sheet_url,
                'designerName': getattr(designer, 'name', ro.designer_name),
                'designerContact': getattr(designer, 'contact', ''),
                'designerAddress': getattr(designer, 'address', ''),
            }
            items.append({
                'request_order_id': ro.id,
                'order_id': ro.order.order_id,
                'status': ro.status,
                'quantity': ro.quantity,
                'due_date': ro.due_date.isoformat() if ro.due_date else None,
                'work_sheet_url': work_sheet_url,
                'productInfo': product_info,
                'customerName': product_info['designerName'],
                'customerContact': product_info['designerContact'],
                'shippingAddress': product_info['designerAddress'],
                # 하위 로직 호환 필드
                'orderId': ro.order.order_id,
                'createdAt': getattr(product, 'created_at', None) or timezone.now().isoformat(),
            })

        return Response({'count': len(items), 'results': items}, status=status.HTTP_200_OK)
    except Exception:
        logger.exception('get_factory_quotes error')
        return Response({'detail': '서버 오류가 발생했습니다.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
                # 기본 식별값 문자열 변환
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

                # unified orders collection
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
                    logger.warning('orders not matched on $pull (step1.factory_list). order_id=%s', order_id_str)

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
                    logger.warning('orders not matched on $push (step1.factory_list). order_id=%s', order_id_str)

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

    # unified orders 문서 업데이트 (phase=sample 선정 반영)
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

            # legacy factory_orders collection removed
            col = None
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
            # no-op: legacy upsert removed
        except Exception:
            logger.exception('legacy factory_orders block removed but error occurred')

        # orders: step 1(업체 선정) 완료 처리 + current_step_index -> 2 (조건부, 이미 2 이상이면 skip)
        try:
            order_id_str = str(bid.request_order.order.order_id)
            col_orders = get_collection(settings.MONGODB_COLLECTIONS['orders'])
            now_ts = now_iso_with_minutes()
            expect_date = getattr(bid, 'expect_work_day', None)
            if hasattr(expect_date, 'isoformat'):
                try:
                    expect_date = expect_date.isoformat()
                except Exception:
                    expect_date = None

            doc_before = col_orders.find_one(
                {'order_id': order_id_str},
                projection={'_id': 0, 'current_step_index': 1, 'steps': 1, 'overall_status': 1},
            ) or {}

            set_updates = {
                'factory_id': str(getattr(bid.factory, 'id', '')),
                'work_price': getattr(bid, 'work_price', None),
                'due_date': expect_date,
                'phase': 'sample',
                'last_updated': now_ts,
            }

            current_idx = int(doc_before.get('current_step_index') or 1)
            steps = doc_before.get('steps') or []
            # step 1 완료 마킹 (이미 완료가 아니면)
            if steps and isinstance(steps, list):
                # steps[0] 이 존재하고 end_date 없으면 완료 처리
                if len(steps) >= 1 and not steps[0].get('end_date'):
                    set_updates['steps.0.end_date'] = now_ts
                    set_updates['steps.0.status'] = 'done'
            # current_step_index < 2 이면 2로 전진
            if current_idx < 2:
                set_updates['current_step_index'] = 2

            col_orders.update_one({'order_id': order_id_str}, {'$set': set_updates}, upsert=False)
        except Exception:  # noqa: E722
            logger.exception('orders unified update after bid select failed')

        # 정상 처리 응답 반환 (선정된 입찰 정보와 상태)
        return Response({
            'detail': '입찰이 선정되었습니다.',
            'bid_id': bid.id,
            'request_order_id': bid.request_order.id,
            'order_id': bid.request_order.order.order_id,
            'factory_id': getattr(bid.factory, 'id', None),
            'status': 'sample_matched',
            'matched_date': bid.matched_date,
        }, status=status.HTTP_200_OK)
    except Exception:
        logger.exception('select_bid error (post-processing)')
        return Response({'detail': '서버 오류'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_order_mongo(request, order_id: str):
    """단일 주문 Mongo 문서 반환 (unified orders)."""
    try:
        col = get_collection(settings.MONGODB_COLLECTIONS['orders'])
        doc = col.find_one({'order_id': str(order_id)})
        if not doc:
            return Response({'detail': '주문 문서를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)
        # 권한
        if hasattr(request.user, 'designer'):
            if doc.get('designer_id') != str(request.user.designer.id):
                return Response({'detail': '권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        elif hasattr(request.user, 'factory'):
            f_id = str(request.user.factory.id)
            if doc.get('factory_id') and doc.get('factory_id') != f_id:
                # factory_id가 아직 지정되지 않았다면 읽기 허용 (입찰 단계 등)
                if doc.get('factory_id'):
                    return Response({'detail': '권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({'detail': '권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        doc.pop('_id', None)
        if repair_steps_stage_integrity(doc):
            try:
                col.update_one({'order_id': str(order_id)}, {'$set': {'steps': doc.get('steps'), 'last_updated': now_iso_with_minutes()}})
            except Exception:
                logger.exception('failed to persist repaired stages (order_id=%s)', order_id)
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