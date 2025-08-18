#!/bin/bash

# =================================================================
# scripts/build.sh - FabLink Backend 빌드 스크립트
# =================================================================
# 
# 다양한 빌드 시나리오를 제공합니다:
# 1. 일반 빌드 (코드 변경 후)
# 2. 모델 변경 후 빌드 (특정 앱 선택 가능, flush 옵션)
# 3. 모델 구조 전면 변경 후 빌드 (DB 완전 재생성)
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

# 에러 핸들링
handle_error() {
    log_error "빌드 중 오류가 발생했습니다."
    log_error "라인 $1에서 오류 발생"
    exit 1
}

trap 'handle_error $LINENO' ERR

# 도움말 출력
show_help() {
    echo "FabLink Backend 빌드 스크립트"
    echo ""
    echo "사용법:"
    echo "  ./scripts/build.sh [환경] [빌드타입] [옵션]"
    echo ""
    echo "환경:"
    echo "  local      로컬 개발 환경"
    echo "  dev        개발 서버 환경"
    echo "  prod       운영 서버 환경"
    echo ""
    echo "빌드타입:"
    echo "  normal     일반 빌드 (기본값)"
    echo "  model      모델 변경 후 빌드"
    echo "  rebuild    모델 구조 전면 변경 후 빌드 (DB 완전 재생성)"
    echo ""
    echo "옵션:"
    echo "  -h, --help         이 도움말 출력"
    echo "  --app APP_NAME     특정 앱만 마이그레이션 (model 빌드타입에서만)"
    echo "  --flush            모델 빌드 시 기존 데이터 삭제 (model 빌드타입에서만)"
    echo "  --skip-deps        의존성 설치 건너뛰기"
    echo "  --skip-static      정적 파일 수집 건너뛰기"
    echo "  --skip-test        테스트 실행 건너뛰기"
    echo ""
    echo "예시:"
    echo "  ./scripts/build.sh local normal                    # 일반 빌드"
    echo "  ./scripts/build.sh local model                     # 모든 앱 마이그레이션"
    echo "  ./scripts/build.sh local model --app accounts      # accounts 앱만 마이그레이션"
    echo "  ./scripts/build.sh local model --flush             # 데이터 삭제 후 마이그레이션"
    echo "  ./scripts/build.sh local model --app accounts --flush  # accounts 앱 데이터 삭제 후 마이그레이션"
    echo "  ./scripts/build.sh local rebuild                   # DB 완전 재생성"
    echo "  ./scripts/build.sh prod normal --skip-test         # 운영환경 빌드 (테스트 제외)"
    echo ""
    echo "모델 변경 시나리오 가이드:"
    echo "  • 새 필드 추가, 새 모델 추가 → flush 불필요"
    echo "  • 필드 삭제, NOT NULL 제약 추가 → --flush 권장"
    echo "  • 호환되지 않는 타입 변경 → --flush 또는 rebuild 권장"
    echo ""
}

# 환경별 설정 로드
load_environment_config() {
    local env_type=$1
    
    case $env_type in
        local)
            ENV_FILE=".env.local"
            DJANGO_SETTINGS="fablink_project.settings.local"
            REQUIREMENTS_FILE="requirements/local.txt"
            COLLECT_STATIC=false
            RUN_TESTS=true
            ;;
        dev)
            ENV_FILE=".env.dev"
            DJANGO_SETTINGS="fablink_project.settings.dev"
            REQUIREMENTS_FILE="requirements/dev.txt"
            COLLECT_STATIC=true
            RUN_TESTS=true
            ;;
        prod)
            ENV_FILE=".env.prod"
            DJANGO_SETTINGS="fablink_project.settings.prod"
            REQUIREMENTS_FILE="requirements/prod.txt"
            COLLECT_STATIC=true
            RUN_TESTS=false
            ;;
        *)
            log_error "지원하지 않는 환경입니다: $env_type"
            log_info "지원 환경: local, dev, prod"
            exit 1
            ;;
    esac
    
    log_info "환경 설정 로드 완료: $env_type"
}

# 전제 조건 확인
check_prerequisites() {
    log_step "전제 조건을 확인합니다..."
    
    # 가상환경 확인
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        log_error "가상환경이 활성화되지 않았습니다."
        echo "source venv/bin/activate 명령어로 가상환경을 활성화하세요."
        exit 1
    fi
    log_success "가상환경이 활성화되어 있습니다."
    
    # 환경변수 파일 확인
    if [ ! -f "$ENV_FILE" ]; then
        log_error "$ENV_FILE 파일이 없습니다."
        echo "먼저 ./scripts/setup_env.sh $ENVIRONMENT 를 실행하세요."
        exit 1
    fi
    log_success "$ENV_FILE 파일이 존재합니다."
    
    # Django 설정
    export DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS
    cp $ENV_FILE .env
    
    log_success "전제 조건 확인 완료"
}

# 의존성 설치
install_dependencies() {
    if [ "$SKIP_DEPS" = true ]; then
        log_warning "의존성 설치를 건너뜁니다."
        return
    fi
    
    log_step "의존성을 확인하고 업데이트합니다..."
    pip install -r $REQUIREMENTS_FILE --upgrade
    log_success "의존성 설치 완료"
}

# Django 설정 검증
verify_django_setup() {
    log_step "Django 설정을 검증합니다..."
    python manage.py check
    
    if [ "$ENVIRONMENT" = "prod" ]; then
        python manage.py check --deploy
    fi
    
    log_success "Django 설정 검증 완료"
}

# 일반 빌드
normal_build() {
    log_header "🔨 일반 빌드 실행"
    
    # 기본 마이그레이션 적용
    log_step "마이그레이션을 적용합니다..."
    python manage.py migrate
    
    log_success "일반 빌드 완료"
}

# 모델 변경 후 빌드
model_build() {
    log_header "🗄️ 모델 변경 후 빌드 실행"
    
    # Flush 옵션 처리
    if [ "$FLUSH_DATA" = true ]; then
        if [ "$ENVIRONMENT" = "prod" ]; then
            log_error "운영환경에서는 --flush 옵션을 사용할 수 없습니다!"
            log_error "데이터 손실 위험이 있습니다."
            exit 1
        fi
        
        log_warning "⚠️ 기존 데이터를 모두 삭제합니다!"
        echo ""
        read -p "정말로 데이터를 삭제하시겠습니까? (yes/no): " confirm
        if [[ $confirm == "yes" ]]; then
            log_step "기존 데이터를 삭제합니다..."
            python manage.py flush --noinput
            log_success "데이터 삭제 완료"
        else
            log_info "데이터 삭제를 취소했습니다. 마이그레이션만 진행합니다."
        fi
    fi
    
    if [ -n "$SPECIFIC_APP" ]; then
        log_info "특정 앱에 대해서만 마이그레이션을 수행합니다: $SPECIFIC_APP"
        
        # 앱 존재 확인
        if [ ! -d "apps/$SPECIFIC_APP" ]; then
            log_error "앱이 존재하지 않습니다: $SPECIFIC_APP"
            echo ""
            echo "사용 가능한 앱:"
            for app_dir in apps/*/; do
                if [ -d "$app_dir" ]; then
                    app_name=$(basename "$app_dir")
                    if [ "$app_name" != "__pycache__" ]; then
                        echo "  • $app_name"
                    fi
                fi
            done
            exit 1
        fi
        
        log_step "$SPECIFIC_APP 앱의 마이그레이션을 생성합니다..."
        python manage.py makemigrations $SPECIFIC_APP
        
        log_step "$SPECIFIC_APP 앱의 마이그레이션을 적용합니다..."
        python manage.py migrate $SPECIFIC_APP
        
    else
        log_info "모든 앱에 대해 마이그레이션을 수행합니다."
        
        # 사용 가능한 앱 목록 표시
        echo ""
        echo -e "${BLUE}📱 사용 가능한 앱 목록:${NC}"
        for app_dir in apps/*/; do
            if [ -d "$app_dir" ]; then
                app_name=$(basename "$app_dir")
                if [ "$app_name" != "__pycache__" ]; then
                    echo "  • $app_name"
                fi
            fi
        done
        echo ""
        
        log_step "모든 앱의 마이그레이션을 생성합니다..."
        python manage.py makemigrations
        
        log_step "마이그레이션을 적용합니다..."
        python manage.py migrate
    fi
    
    # 마이그레이션 상태 확인
    log_step "마이그레이션 상태를 확인합니다..."
    python manage.py showmigrations
    
    # Flush 후 기본 데이터 재생성 (로컬 환경만)
    if [ "$FLUSH_DATA" = true ] && [ "$ENVIRONMENT" = "local" ]; then
        log_step "기본 데이터를 재생성합니다..."
        
        # 슈퍼유저 재생성
        python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(user_id='admin').exists():
    try:
        User.objects.create_superuser(
            user_id='admin', 
            password='admin123',
            name='관리자',
            user_type='designer'
        )
        print('✅ 개발용 슈퍼유저 재생성 완료')
    except Exception as e:
        print(f'⚠️ 슈퍼유저 생성 실패: {e}')
else:
    print('✅ 슈퍼유저가 이미 존재합니다.')
"
        
        # 테스트 데이터 로드 (있다면)
        if [ -f "fixtures/test_data.json" ]; then
            log_step "테스트 데이터를 로드합니다..."
            python manage.py loaddata fixtures/test_data.json
            log_success "테스트 데이터 로드 완료"
        fi
    fi
    
    log_success "모델 변경 후 빌드 완료"
}

# 모델 구조 전면 변경 후 빌드 (DB 완전 재생성)
rebuild_database() {
    log_header "🔥 데이터베이스 완전 재생성 빌드"
    
    # 운영환경에서는 금지
    if [ "$ENVIRONMENT" = "prod" ]; then
        log_error "운영환경에서는 데이터베이스 완전 재생성을 할 수 없습니다!"
        log_error "데이터 손실 위험이 있습니다."
        exit 1
    fi
    
    log_warning "⚠️ 이 작업은 모든 데이터베이스 데이터를 삭제합니다!"
    log_warning "⚠️ 마이그레이션 파일도 모두 삭제됩니다!"
    echo ""
    
    # 사용자 확인
    read -p "정말로 데이터베이스를 완전히 재생성하시겠습니까? (yes/no): " confirm
    if [[ $confirm != "yes" ]]; then
        log_info "데이터베이스 재생성을 취소했습니다."
        exit 0
    fi
    
    # 마이그레이션 파일 백업
    log_step "기존 마이그레이션 파일을 백업합니다..."
    backup_dir="backups/migrations/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    
    for app_dir in apps/*/; do
        if [ -d "$app_dir" ]; then
            app_name=$(basename "$app_dir")
            if [ "$app_name" != "__pycache__" ] && [ -d "$app_dir/migrations" ]; then
                mkdir -p "$backup_dir/$app_name"
                cp -r "$app_dir/migrations/"*.py "$backup_dir/$app_name/" 2>/dev/null || true
                log_info "$app_name 앱의 마이그레이션 파일을 백업했습니다."
            fi
        fi
    done
    
    # 데이터베이스 연결 종료 (PostgreSQL)
    log_step "데이터베이스 연결을 종료합니다..."
    python manage.py shell -c "
from django.db import connection
connection.close()
print('데이터베이스 연결이 종료되었습니다.')
" || true
    
    # 마이그레이션 파일 삭제
    log_step "마이그레이션 파일을 삭제합니다..."
    for app_dir in apps/*/; do
        if [ -d "$app_dir" ]; then
            app_name=$(basename "$app_dir")
            if [ "$app_name" != "__pycache__" ] && [ -d "$app_dir/migrations" ]; then
                find "$app_dir/migrations" -name "*.py" ! -name "__init__.py" -delete 2>/dev/null || true
                log_info "$app_name 앱의 마이그레이션 파일을 삭제했습니다."
            fi
        fi
    done
    
    # 데이터베이스 테이블 삭제 (환경별)
    if [ "$ENVIRONMENT" = "local" ]; then
        log_step "로컬 데이터베이스를 재생성합니다..."
        
        # .env에서 데이터베이스 정보 읽기
        source .env
        
        # PostgreSQL 데이터베이스 재생성
        if command -v systemctl &> /dev/null; then
            # Linux
            sudo -u postgres psql -c "DROP DATABASE IF EXISTS $DB_NAME;"
            sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
        else
            # macOS
            /opt/homebrew/bin/psql postgres -c "DROP DATABASE IF EXISTS $DB_NAME;" || true
            /opt/homebrew/bin/psql postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
        fi
        
    elif [ "$ENVIRONMENT" = "dev" ]; then
        log_warning "개발 서버 데이터베이스 재생성은 DBA와 상의 후 진행하세요."
        log_info "Django 레벨에서만 테이블을 재생성합니다."
        python manage.py flush --noinput || true
    fi
    
    # 새 마이그레이션 생성
    log_step "새로운 마이그레이션을 생성합니다..."
    python manage.py makemigrations
    
    # 마이그레이션 적용
    log_step "마이그레이션을 적용합니다..."
    python manage.py migrate
    
    # 슈퍼유저 재생성 (로컬 환경만)
    if [ "$ENVIRONMENT" = "local" ]; then
        log_step "개발용 슈퍼유저를 재생성합니다..."
        python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(user_id='admin').exists():
    try:
        User.objects.create_superuser(
            user_id='admin', 
            password='admin123',
            name='관리자',
            user_type='designer'
        )
        print('✅ 개발용 슈퍼유저 재생성 완료')
    except Exception as e:
        print(f'⚠️ 슈퍼유저 생성 실패: {e}')
else:
    print('✅ 슈퍼유저가 이미 존재합니다.')
"
    fi
    
    log_success "데이터베이스 완전 재생성 완료"
    log_info "백업 위치: $backup_dir"
}

# 정적 파일 수집
collect_static_files() {
    if [ "$SKIP_STATIC" = true ] || [ "$COLLECT_STATIC" = false ]; then
        log_info "정적 파일 수집을 건너뜁니다."
        return
    fi
    
    log_step "정적 파일을 수집합니다..."
    python manage.py collectstatic --noinput --clear
    log_success "정적 파일 수집 완료"
}

# 테스트 실행
run_tests() {
    if [ "$SKIP_TEST" = true ] || [ "$RUN_TESTS" = false ]; then
        log_info "테스트 실행을 건너뜁니다."
        return
    fi
    
    log_step "테스트를 실행합니다..."
    
    if [ "$ENVIRONMENT" = "local" ]; then
        # 로컬에서는 상세한 테스트 실행
        python manage.py test --verbosity=2
    else
        # 개발/운영에서는 기본 테스트만
        python manage.py test
    fi
    
    log_success "테스트 실행 완료"
}

# 빌드 완료 메시지
show_completion_message() {
    log_header "🎉 빌드 완료!"
    
    echo -e "${GREEN}✅ $ENVIRONMENT 환경에서 $BUILD_TYPE 빌드가 완료되었습니다!${NC}"
    echo ""
    
    # 빌드 타입별 메시지
    case $BUILD_TYPE in
        normal)
            echo -e "${BLUE}📝 일반 빌드 완료${NC}"
            echo "  • 의존성 업데이트"
            echo "  • 마이그레이션 적용"
            echo "  • 정적 파일 수집"
            ;;
        model)
            echo -e "${BLUE}🗄️ 모델 변경 빌드 완료${NC}"
            if [ "$FLUSH_DATA" = true ]; then
                echo "  • 기존 데이터 삭제"
            fi
            if [ -n "$SPECIFIC_APP" ]; then
                echo "  • $SPECIFIC_APP 앱 마이그레이션 생성 및 적용"
            else
                echo "  • 모든 앱 마이그레이션 생성 및 적용"
            fi
            echo "  • 마이그레이션 상태 확인"
            if [ "$FLUSH_DATA" = true ] && [ "$ENVIRONMENT" = "local" ]; then
                echo "  • 기본 데이터 재생성"
            fi
            ;;
        rebuild)
            echo -e "${BLUE}🔥 데이터베이스 완전 재생성 완료${NC}"
            echo "  • 기존 마이그레이션 파일 백업"
            echo "  • 데이터베이스 완전 재생성"
            echo "  • 새 마이그레이션 생성 및 적용"
            if [ "$ENVIRONMENT" = "local" ]; then
                echo "  • 개발용 슈퍼유저 재생성"
            fi
            ;;
    esac
    
    echo ""
    echo -e "${YELLOW}🚀 다음 단계:${NC}"
    echo "  python manage.py runserver  # 서버 시작"
    echo ""
}

# 메인 실행 함수
main() {
    # 인자 확인
    if [ $# -eq 0 ]; then
        log_error "환경과 빌드타입을 지정해주세요."
        show_help
        exit 1
    fi
    
    ENVIRONMENT=$1
    BUILD_TYPE=${2:-normal}  # 기본값: normal
    shift 2 2>/dev/null || shift 1  # 안전한 shift
    
    # 도움말 확인
    if [ "$ENVIRONMENT" = "-h" ] || [ "$ENVIRONMENT" = "--help" ]; then
        show_help
        exit 0
    fi
    
    # 옵션 파싱
    SKIP_DEPS=false
    SKIP_STATIC=false
    SKIP_TEST=false
    SPECIFIC_APP=""
    FLUSH_DATA=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            --app)
                SPECIFIC_APP="$2"
                shift 2
                ;;
            --flush)
                FLUSH_DATA=true
                shift
                ;;
            --skip-deps)
                SKIP_DEPS=true
                shift
                ;;
            --skip-static)
                SKIP_STATIC=true
                shift
                ;;
            --skip-test)
                SKIP_TEST=true
                shift
                ;;
            *)
                log_error "알 수 없는 옵션: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 빌드 타입 검증
    if [[ "$BUILD_TYPE" != "normal" && "$BUILD_TYPE" != "model" && "$BUILD_TYPE" != "rebuild" ]]; then
        log_error "지원하지 않는 빌드타입입니다: $BUILD_TYPE"
        log_info "지원 빌드타입: normal, model, rebuild"
        exit 1
    fi
    
    # --flush 옵션은 model 빌드타입에서만 사용 가능
    if [ "$FLUSH_DATA" = true ] && [ "$BUILD_TYPE" != "model" ]; then
        log_error "--flush 옵션은 model 빌드타입에서만 사용할 수 있습니다."
        exit 1
    fi
    
    # 프로젝트 루트 디렉토리로 이동
    cd "$(dirname "$0")/.."
    
    # 환경별 설정 로드
    load_environment_config $ENVIRONMENT
    
    log_header "🔨 FabLink Backend 빌드 시작 ($ENVIRONMENT - $BUILD_TYPE)"
    
    # 공통 단계
    check_prerequisites
    install_dependencies
    verify_django_setup
    
    # 빌드 타입별 실행
    case $BUILD_TYPE in
        normal)
            normal_build
            ;;
        model)
            model_build
            ;;
        rebuild)
            rebuild_database
            ;;
    esac
    
    # 후처리
    collect_static_files
    run_tests
    show_completion_message
    
    log_success "🎉 모든 빌드 작업이 성공적으로 완료되었습니다!"
    
    # 환경별 서버 실행
    log_header "🚀 서버 시작 ($ENVIRONMENT)"
    
    case $ENVIRONMENT in
        local)
            echo -e "${BLUE}로컬 개발 서버 주소:${NC}"
            echo "  • http://localhost:8000/"
            echo "  • http://127.0.0.1:8000/"
            echo ""
            echo -e "${YELLOW}서버를 중지하려면 Ctrl+C를 누르세요.${NC}"
            echo ""
            python manage.py runserver
            ;;
            
        dev)
            echo -e "${BLUE}개발 서버 주소:${NC}"
            echo "  • https://dev-api.fablink.com/"
            echo ""
            echo -e "${YELLOW}Gunicorn으로 서버를 시작합니다...${NC}"
            echo "서버 로그는 /var/log/fablink/dev/gunicorn.log에서 확인할 수 있습니다."
            echo ""
            gunicorn fablink_project.wsgi:application \
                --bind 0.0.0.0:8000 \
                --workers 3 \
                --access-logfile /var/log/fablink/dev/gunicorn-access.log \
                --error-logfile /var/log/fablink/dev/gunicorn-error.log \
                --daemon
            ;;
            
        prod)
            echo -e "${RED}⚠️ 운영 서버 배포 안내${NC}"
            echo "운영 서버는 시스템 서비스로 관리됩니다."
            echo ""
            echo -e "${BLUE}운영 서버 주소:${NC}"
            echo "  • https://api.fablink.com/"
            echo ""
            echo -e "${YELLOW}서버 관리 명령어:${NC}"
            echo "  • 상태 확인: sudo systemctl status fablink"
            echo "  • 서버 시작: sudo systemctl start fablink"
            echo "  • 서버 재시작: sudo systemctl restart fablink"
            echo "  • 서버 중지: sudo systemctl stop fablink"
            echo "  • 로그 확인: sudo journalctl -u fablink -f"
            echo ""
            read -p "운영 서버를 재시작하시겠습니까? (yes/no): " restart_prod
            if [[ $restart_prod == "yes" ]]; then
                echo "운영 서버를 재시작합니다..."
                sudo systemctl restart fablink
                echo "재시작이 완료되었습니다."
            else
                echo "운영 서버 재시작을 건너뜁니다."
            fi
            ;;
    esac
}

# 스크립트 실행
main "$@"
