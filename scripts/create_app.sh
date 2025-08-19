#!/bin/bash

# =================================================================
# scripts/create_app.sh - Django 앱 생성 스크립트
# =================================================================
# 
# 새로운 Django 앱을 생성하고 필요한 설정을 자동으로 구성합니다.
#
# =================================================================

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# 로그 함수들
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_step() {
    echo -e "${PURPLE}🔄 $1${NC}"
}

log_header() {
    echo ""
    echo -e "${CYAN}================================================${NC}"
    echo -e "${CYAN} $1${NC}"
    echo -e "${CYAN}================================================${NC}"
    echo ""
}

# 도움말 출력
show_help() {
    echo "Django 앱 생성 스크립트"
    echo ""
    echo "사용법:"
    echo "  ./scripts/create_app.sh <app_name> [옵션]"
    echo ""
    echo "옵션:"
    echo "  -h, --help         이 도움말 출력"
    echo "  --no-auto-config   자동 설정 건너뛰기 (수동으로 설정)"
    echo "  --api-only         API 전용 앱 생성 (ViewSet, Serializer 템플릿 포함)"
    echo ""
    echo "예시:"
    echo "  ./scripts/create_app.sh payments                    # 일반 앱 생성"
    echo "  ./scripts/create_app.sh analytics --api-only        # API 전용 앱 생성"
    echo "  ./scripts/create_app.sh reviews --no-auto-config    # 수동 설정 앱 생성"
    echo ""
    echo "앱 이름 규칙:"
    echo "  • 소문자와 언더스코어만 사용"
    echo "  • 숫자로 시작하면 안됨"
    echo "  • Python 예약어 사용 금지"
    echo ""
}

# 앱 이름 유효성 검사
validate_app_name() {
    local app_name=$1
    
    # 빈 값 체크
    if [ -z "$app_name" ]; then
        log_error "앱 이름을 입력해주세요."
        show_help
        exit 1
    fi
    
    # 소문자와 언더스코어만 허용
    if [[ ! "$app_name" =~ ^[a-z][a-z0-9_]*$ ]]; then
        log_error "앱 이름은 소문자로 시작하고, 소문자, 숫자, 언더스코어만 사용할 수 있습니다."
        log_error "잘못된 이름: $app_name"
        exit 1
    fi
    
    # Python 예약어 체크
    python_keywords=("and" "as" "assert" "break" "class" "continue" "def" "del" "elif" "else" "except" "exec" "finally" "for" "from" "global" "if" "import" "in" "is" "lambda" "not" "or" "pass" "print" "raise" "return" "try" "while" "with" "yield")
    
    for keyword in "${python_keywords[@]}"; do
        if [ "$app_name" = "$keyword" ]; then
            log_error "Python 예약어는 앱 이름으로 사용할 수 없습니다: $app_name"
            exit 1
        fi
    done
    
    # 기존 앱과 중복 체크
    if [ -d "apps/$app_name" ]; then
        log_error "이미 존재하는 앱입니다: $app_name"
        log_info "기존 앱 목록:"
        ls -1 apps/ | grep -v __pycache__ | grep -v __init__.py | sed 's/^/  • /'
        exit 1
    fi
    
    log_success "앱 이름 유효성 검사 통과: $app_name"
}

# Django 앱 생성
create_django_app() {
    local app_name=$1
    
    log_step "Django 앱을 생성합니다: $app_name"
    
    # 앱 생성
    if [ ! -d "apps" ]; then
        log_info "apps 디렉토리를 생성합니다..."
        mkdir -p apps
    fi
    
    # 앱 디렉토리가 이미 존재하는지 확인
    if [ -d "apps/$app_name" ]; then
        log_warning "앱 디렉토리가 이미 존재합니다: apps/$app_name"
        read -p "기존 디렉토리를 삭제하고 새로 생성하시겠습니까? (y/N): " confirm
        if [[ $confirm =~ ^[Yy]$ ]]; then
            log_info "기존 디렉토리를 삭제합니다..."
            rm -rf "apps/$app_name"
        else
            log_error "앱 생성을 취소합니다."
            exit 1
        fi
    fi


    if python manage.py startapp $app_name apps/$app_name 2>/dev/null; then
        log_success "Django 앱 생성 완료 (방법 1)"
    else
        log_info "방법 1 실패, 대안 방법으로 앱을 생성합니다..."
        
        # 대안: 임시로 앱을 생성한 후 이동
        if python manage.py startapp $app_name 2>/dev/null; then
            log_info "임시 앱 생성 후 apps 디렉토리로 이동합니다..."
            mv $app_name apps/
            log_success "Django 앱 생성 완료 (방법 2)"
        else
            log_error "Django 앱 생성에 실패했습니다."
            exit 1
        fi
    fi
}

# 기본 파일들 생성
create_basic_files() {
    local app_name=$1
    
    log_step "기본 파일들을 생성합니다..."
    
    # URLs 파일 생성
    cat > apps/$app_name/urls.py << EOF
from django.urls import path, include
from rest_framework.routers import DefaultRouter

app_name = '$app_name'

router = DefaultRouter()
# router.register(r'items', ItemViewSet)  # 필요시 추가

urlpatterns = [
    path('', include(router.urls)),
    # path('custom/', CustomView.as_view(), name='custom'),  # 커스텀 뷰 예시
]
EOF
    
    # Serializers 파일 생성
    cat > apps/$app_name/serializers.py << EOF
from rest_framework import serializers
# from .models import YourModel


# class YourModelSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = YourModel
#         fields = '__all__'
EOF
    
    # Services 파일 생성 (비즈니스 로직 분리용)
    cat > apps/$app_name/services.py << EOF
"""
$app_name 앱의 비즈니스 로직을 담당하는 서비스 레이어

Service 레이어의 역할:
- 비즈니스 로직 처리
- 데이터 검증 및 변환
- 외부 API 호출
- 복잡한 쿼리 로직
- 트랜잭션 관리

View는 HTTP 요청/응답 처리만 담당하고,
실제 비즈니스 로직은 Service에서 처리합니다.
"""

from rest_framework import serializers
from django.db import transaction
# from .models import YourModel
# from .serializers import YourModelSerializer


class ${app_name^}Service:
    """
    $app_name 앱의 메인 서비스 클래스
    """
    
    @staticmethod
    def create_item(data: dict):
        """
        새 아이템 생성
        
        Args:
            data (dict): 생성할 아이템 데이터
            
        Returns:
            YourModel: 생성된 아이템
            
        Raises:
            serializers.ValidationError: 검증 실패 시
        """
        # 비즈니스 로직 구현 예시:
        # 1. 데이터 검증
        # 2. 중복 체크
        # 3. 관련 데이터 처리
        # 4. 아이템 생성
        # 5. 후처리 작업
        
        # with transaction.atomic():
        #     # 트랜잭션 내에서 처리
        #     item = YourModel.objects.create(**data)
        #     # 추가 처리...
        #     return item
        
        pass
    
    @staticmethod
    def get_items(filters: dict = None):
        """
        아이템 목록 조회
        
        Args:
            filters (dict, optional): 필터 조건
            
        Returns:
            QuerySet: 아이템 목록
        """
        # queryset = YourModel.objects.all()
        # 
        # if filters:
        #     if 'status' in filters:
        #         queryset = queryset.filter(status=filters['status'])
        #     if 'search' in filters:
        #         queryset = queryset.filter(name__icontains=filters['search'])
        # 
        # return queryset.order_by('-created_at')
        
        pass
    
    @staticmethod
    def update_item(item_id: int, data: dict):
        """
        아이템 업데이트
        
        Args:
            item_id (int): 아이템 ID
            data (dict): 업데이트 데이터
            
        Returns:
            YourModel: 업데이트된 아이템
            
        Raises:
            serializers.ValidationError: 검증 실패 시
        """
        # try:
        #     item = YourModel.objects.get(id=item_id)
        # except YourModel.DoesNotExist:
        #     raise serializers.ValidationError("아이템을 찾을 수 없습니다.")
        # 
        # with transaction.atomic():
        #     for field, value in data.items():
        #         if hasattr(item, field):
        #             setattr(item, field, value)
        #     item.save()
        #     return item
        
        pass
    
    @staticmethod
    def delete_item(item_id: int):
        """
        아이템 삭제
        
        Args:
            item_id (int): 아이템 ID
            
        Raises:
            serializers.ValidationError: 삭제 실패 시
        """
        # try:
        #     item = YourModel.objects.get(id=item_id)
        #     item.delete()
        # except YourModel.DoesNotExist:
        #     raise serializers.ValidationError("아이템을 찾을 수 없습니다.")
        
        pass
EOF
    
    # Permissions 파일 생성
    cat > apps/$app_name/permissions.py << EOF
from rest_framework import permissions


# class ${app_name^}Permission(permissions.BasePermission):
#     """
#     $app_name 앱 전용 권한 클래스
#     """
#     
#     def has_permission(self, request, view):
#         # 권한 로직 구현
#         return True
#     
#     def has_object_permission(self, request, view, obj):
#         # 객체별 권한 로직 구현
#         return True
EOF
    
    log_success "기본 파일 생성 완료"
}

# API 전용 파일들 생성
create_api_files() {
    local app_name=$1
    
    log_step "API 전용 파일들을 생성합니다..."
    
    # ViewSets 파일 생성
    cat > apps/$app_name/viewsets.py << EOF
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
# from .models import YourModel
# from .serializers import YourModelSerializer
# from .services import ${app_name^}Service


# class YourModelViewSet(viewsets.ModelViewSet):
#     """
#     YourModel에 대한 CRUD API
#     """
#     # queryset = YourModel.objects.all()
#     # serializer_class = YourModelSerializer
#     
#     @action(detail=False, methods=['get'])
#     def custom_action(self, request):
#         """
#         커스텀 액션 예시
#         """
#         # data = ${app_name^}Service.get_items()
#         return Response({'message': 'Custom action'}, status=status.HTTP_200_OK)
EOF
    
    # Filters 파일 생성
    cat > apps/$app_name/filters.py << EOF
import django_filters
# from .models import YourModel


# class YourModelFilter(django_filters.FilterSet):
#     """
#     YourModel 필터링 클래스
#     """
#     # name = django_filters.CharFilter(lookup_expr='icontains')
#     # created_at = django_filters.DateFromToRangeFilter()
#     
#     class Meta:
#         # model = YourModel
#         # fields = ['name', 'status', 'created_at']
#         pass
EOF
    
    # URLs 파일을 ViewSet 용으로 업데이트
    cat > apps/$app_name/urls.py << EOF
from django.urls import path, include
from rest_framework.routers import DefaultRouter
# from .viewsets import YourModelViewSet

app_name = '$app_name'

router = DefaultRouter()
# router.register(r'items', YourModelViewSet, basename='items')

urlpatterns = [
    path('', include(router.urls)),
]
EOF
    
    log_success "API 전용 파일 생성 완료"
}

# 테스트 파일 생성
create_test_files() {
    local app_name=$1
    
    log_step "테스트 파일을 생성합니다..."
    
    # 기존 tests.py 삭제하고 tests 디렉토리 생성
    rm -f apps/$app_name/tests.py
    mkdir -p apps/$app_name/tests
    
    # __init__.py 생성
    touch apps/$app_name/tests/__init__.py
    
    # 모델 테스트
    cat > apps/$app_name/tests/test_models.py << EOF
from django.test import TestCase
# from ..models import YourModel


class ${app_name^}ModelTest(TestCase):
    """
    $app_name 앱의 모델 테스트
    """
    
    def setUp(self):
        """테스트 데이터 설정"""
        pass
    
    # def test_model_creation(self):
    #     """모델 생성 테스트"""
    #     pass
EOF
    
    # API 테스트
    cat > apps/$app_name/tests/test_api.py << EOF
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()


class ${app_name^}APITest(TestCase):
    """
    $app_name 앱의 API 테스트
    """
    
    def setUp(self):
        """테스트 데이터 설정"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            user_id='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    # def test_api_endpoint(self):
    #     """API 엔드포인트 테스트"""
    #     url = reverse('$app_name:items-list')
    #     response = self.client.get(url)
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
EOF
    
    # 서비스 테스트
    cat > apps/$app_name/tests/test_services.py << EOF
from django.test import TestCase
# from ..services import ${app_name^}Service


class ${app_name^}ServiceTest(TestCase):
    """
    $app_name 앱의 서비스 레이어 테스트
    """
    
    def setUp(self):
        """테스트 데이터 설정"""
        pass
    
    # def test_service_method(self):
    #     """서비스 메소드 테스트"""
    #     pass
EOF
    
    log_success "테스트 파일 생성 완료"
}

# 자동 설정 (settings.py와 urls.py에 추가)
auto_configure() {
    local app_name=$1
    
    if [ "$NO_AUTO_CONFIG" = true ]; then
        log_warning "자동 설정을 건너뜁니다."
        return
    fi
    
    log_step "자동 설정을 수행합니다..."
    
    # settings/base.py에 앱 추가
    local settings_file="fablink_project/settings/base.py"
    if [ -f "$settings_file" ]; then
        # LOCAL_APPS 섹션 찾아서 추가
        if grep -q "LOCAL_APPS" "$settings_file"; then
            # LOCAL_APPS 리스트에 추가
            sed -i.bak "/LOCAL_APPS = \[/a\\
    'apps.$app_name'," "$settings_file"
            rm "$settings_file.bak"
            log_success "settings/base.py에 앱 추가 완료"
        else
            log_warning "LOCAL_APPS를 찾을 수 없습니다. 수동으로 추가해주세요."
        fi
    else
        log_warning "$settings_file을 찾을 수 없습니다."
    fi
    
    # 메인 urls.py에 URL 패턴 추가
    local main_urls="fablink_project/urls.py"
    if [ -f "$main_urls" ]; then
        # urlpatterns에 추가할 패턴 생성
        local url_pattern="    path('api/$app_name/', include('apps.$app_name.urls')),"
        
        # 이미 추가되어 있는지 확인
        if ! grep -q "apps.$app_name.urls" "$main_urls"; then
            # urlpatterns 리스트에 추가
            sed -i.bak "/urlpatterns = \[/a\\
$url_pattern" "$main_urls"
            rm "$main_urls.bak"
            log_success "메인 urls.py에 URL 패턴 추가 완료"
        else
            log_info "URL 패턴이 이미 존재합니다."
        fi
    else
        log_warning "$main_urls을 찾을 수 없습니다."
    fi
}

# 완료 메시지 출력
show_completion_message() {
    local app_name=$1
    
    log_header "🎉 앱 생성 완료!"
    
    echo -e "${GREEN}✅ '$app_name' 앱이 성공적으로 생성되었습니다!${NC}"
    echo ""
    
    echo -e "${BLUE}📁 생성된 파일 구조:${NC}"
    echo "apps/$app_name/"
    echo "├── __init__.py"
    echo "├── admin.py"
    echo "├── apps.py"
    echo "├── models.py"
    echo "├── views.py"
    echo "├── urls.py          # 🆕 URL 라우팅"
    echo "├── serializers.py   # 🆕 DRF 시리얼라이저"
    echo "├── services.py      # 🆕 비즈니스 로직"
    echo "├── permissions.py   # 🆕 권한 관리"
    if [ "$API_ONLY" = true ]; then
        echo "├── viewsets.py      # 🆕 DRF ViewSet"
        echo "├── filters.py       # 🆕 필터링"
    fi
    echo "├── tests/"
    echo "│   ├── __init__.py"
    echo "│   ├── test_models.py   # 🆕 모델 테스트"
    echo "│   ├── test_api.py      # 🆕 API 테스트"
    echo "│   └── test_services.py # 🆕 서비스 테스트"
    echo "└── migrations/"
    echo "    └── __init__.py"
    echo ""
    
    if [ "$NO_AUTO_CONFIG" != true ]; then
        echo -e "${GREEN}🔧 자동 설정 완료:${NC}"
        echo "  ✅ settings/base.py의 LOCAL_APPS에 추가됨"
        echo "  ✅ 메인 urls.py에 URL 패턴 추가됨"
        echo "  🌐 API 엔드포인트: http://localhost:8000/api/$app_name/"
        echo ""
    fi
    
    echo -e "${YELLOW}📝 다음 단계:${NC}"
    echo "  1. apps/$app_name/models.py에서 모델 정의"
    echo "  2. apps/$app_name/serializers.py에서 시리얼라이저 작성"
    if [ "$API_ONLY" = true ]; then
        echo "  3. apps/$app_name/viewsets.py에서 ViewSet 구현"
    else
        echo "  3. apps/$app_name/views.py에서 뷰 구현"
    fi
    echo "  4. 마이그레이션 생성 및 적용:"
    echo "     ./scripts/build.sh local model --app $app_name"
    echo ""
    
    echo -e "${BLUE}🧪 테스트 실행:${NC}"
    echo "  python manage.py test apps.$app_name"
    echo ""
    
    if [ "$NO_AUTO_CONFIG" = true ]; then
        echo -e "${RED}⚠️ 수동 설정 필요:${NC}"
        echo "  1. fablink_project/settings/base.py의 LOCAL_APPS에 'apps.$app_name' 추가"
        echo "  2. fablink_project/urls.py에 다음 패턴 추가:"
        echo "     path('api/$app_name/', include('apps.$app_name.urls')),"
        echo ""
    fi
}

# 메인 실행 함수
main() {
    # 인자 확인
    if [ $# -eq 0 ]; then
        log_error "앱 이름을 입력해주세요."
        show_help
        exit 1
    fi
    
    APP_NAME=$1
    shift
    
    # 도움말 확인
    if [ "$APP_NAME" = "-h" ] || [ "$APP_NAME" = "--help" ]; then
        show_help
        exit 0
    fi
    
    # 옵션 파싱
    NO_AUTO_CONFIG=false
    API_ONLY=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            --no-auto-config)
                NO_AUTO_CONFIG=true
                shift
                ;;
            --api-only)
                API_ONLY=true
                shift
                ;;
            *)
                log_error "알 수 없는 옵션: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 프로젝트 루트 디렉토리로 이동
    cd "$(dirname "$0")/.."
    
    # 가상환경 확인
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        log_error "가상환경이 활성화되지 않았습니다."
        echo "source venv/bin/activate 명령어로 가상환경을 활성화하세요."
        exit 1
    fi
    
    log_header "🚀 Django 앱 생성: $APP_NAME"
    
    # 실행 단계
    validate_app_name $APP_NAME
    create_django_app $APP_NAME
    create_basic_files $APP_NAME
    
    if [ "$API_ONLY" = true ]; then
        create_api_files $APP_NAME
    fi
    
    create_test_files $APP_NAME
    auto_configure $APP_NAME
    show_completion_message $APP_NAME
    
    log_success "🎉 모든 작업이 성공적으로 완료되었습니다!"
}

# 스크립트 실행
main "$@"
