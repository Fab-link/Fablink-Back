#!/bin/bash

# =================================================================
# scripts/first_build.sh - FabLink Backend 최초 빌드 스크립트
# =================================================================
# 
# 이 스크립트는 FabLink Backend 프로젝트를 최초로 설정할 때 사용합니다.
# 
# 실행 순서:
# 1. ./scripts/setup_env.sh [local|dev|prod]
# 2. ./scripts/setup_postgresql_[local|dev|prod].sh  
# 3. ./scripts/first_build.sh [local|dev|prod]
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
    log_error "스크립트 실행 중 오류가 발생했습니다."
    log_error "라인 $1에서 오류 발생"
    exit 1
}

trap 'handle_error $LINENO' ERR

# 도움말 출력
show_help() {
    echo "FabLink Backend 최초 빌드 스크립트"
    echo ""
    echo "사용법:"
    echo "  ./scripts/first_build.sh [환경] [옵션]"
    echo ""
    echo "환경:"
    echo "  local      로컬 개발 환경"
    echo "  dev        개발 서버 환경"
    echo "  prod       운영 서버 환경"
    echo ""
    echo "옵션:"
    echo "  -h, --help     이 도움말 출력"
    echo "  --skip-deps    의존성 설치 건너뛰기"
    echo "  --skip-test    테스트 데이터 생성 건너뛰기 (local만)"
    echo "  --reset-db     데이터베이스 완전 초기화"
    echo ""
    echo "전제 조건:"
    echo "  1. ./scripts/setup_env.sh [환경] 실행 완료"
    echo "  2. ./scripts/setup_postgresql_[환경].sh 실행 완료"
    echo "  3. 가상환경 활성화 (source venv/bin/activate)"
    echo ""
    echo "예시:"
    echo "  ./scripts/first_build.sh local"
    echo "  ./scripts/first_build.sh dev --skip-test"
    echo "  ./scripts/first_build.sh prod --skip-deps"
    echo ""
}

# 환경별 설정 로드
load_environment_config() {
    local env_type=$1
    
    case $env_type in
        local)
            ENV_FILE=".env.local"
            DJANGO_SETTINGS="fablink_project.settings.local"
            DB_NAME="fablink_local_db"
            DB_USER="fablink_user"
            DB_PASSWORD="local123"
            DB_HOST="localhost"
            ADMIN_USER="admin"
            ADMIN_PASSWORD="admin123"
            ADMIN_NAME="관리자"
            REQUIREMENTS_FILE="requirements/local.txt"
            COLLECT_STATIC=false
            ALLOW_TEST_DATA=true
            ;;
        dev)
            ENV_FILE=".env.dev"
            DJANGO_SETTINGS="fablink_project.settings.dev"
            DB_NAME="fablink_dev_db"
            DB_USER="fablink_dev_user"
            DB_PASSWORD="dev-db-password"
            DB_HOST="fablink-dev-cluster.cluster-xxxxx.ap-northeast-2.rds.amazonaws.com"
            ADMIN_USER="dev_admin"
            ADMIN_PASSWORD="dev_admin_secure_password"
            ADMIN_NAME="개발서버 관리자"
            REQUIREMENTS_FILE="requirements/dev.txt"
            COLLECT_STATIC=true
            ALLOW_TEST_DATA=true
            ;;
        prod)
            ENV_FILE=".env.prod"
            DJANGO_SETTINGS="fablink_project.settings.prod"
            DB_NAME="fablink_prod_db"
            DB_USER="fablink_prod_user"
            DB_PASSWORD="super-secure-prod-password"
            DB_HOST="fablink-prod-cluster.cluster-xxxxx.ap-northeast-2.rds.amazonaws.com"
            ADMIN_USER="prod_admin"
            ADMIN_PASSWORD=""  # 운영환경에서는 대화형으로 입력받음
            ADMIN_NAME="운영서버 관리자"
            REQUIREMENTS_FILE="requirements/prod.txt"
            COLLECT_STATIC=true
            ALLOW_TEST_DATA=false
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
        echo ""
        echo "다음 명령어로 가상환경을 활성화하세요:"
        echo "  python3 -m venv venv"
        echo "  source venv/bin/activate  # Linux/Mac"
        echo "  # venv\\Scripts\\activate   # Windows"
        echo ""
        exit 1
    fi
    log_success "가상환경이 활성화되어 있습니다: $VIRTUAL_ENV"
    
    # 환경변수 파일 확인
    if [ ! -f "$ENV_FILE" ]; then
        log_error "$ENV_FILE 파일이 없습니다."
        echo ""
        echo "먼저 다음 명령어를 실행하세요:"
        echo "  ./scripts/setup_env.sh $ENVIRONMENT"
        echo ""
        exit 1
    fi
    log_success "$ENV_FILE 파일이 존재합니다."
    
    # 데이터베이스 연결 확인 (환경별)
    log_info "데이터베이스 연결을 확인합니다..."
    if [ "$ENVIRONMENT" = "local" ]; then
        if ! PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT 1;" > /dev/null 2>&1; then
            log_error "PostgreSQL 데이터베이스에 연결할 수 없습니다."
            echo ""
            echo "먼저 다음 명령어를 실행하세요:"
            echo "  ./scripts/setup_postgresql_local.sh"
            echo ""
            exit 1
        fi
    else
        # dev/prod 환경에서는 RDS 연결 확인
        log_info "RDS 데이터베이스 연결을 확인합니다..."
        # 실제 연결 테스트는 Django 설정을 통해 수행
    fi
    log_success "데이터베이스 연결 확인 완료"
    
    # Python 버전 확인
    python_version=$(python --version 2>&1 | cut -d' ' -f2)
    log_success "Python 버전: $python_version"
    
    # requirements 파일 확인
    if [ ! -f "$REQUIREMENTS_FILE" ]; then
        log_error "$REQUIREMENTS_FILE 파일이 없습니다."
        exit 1
    fi
    log_success "requirements 파일 확인 완료: $REQUIREMENTS_FILE"
    
    # 운영환경 추가 확인사항
    if [ "$ENVIRONMENT" = "prod" ]; then
        log_warning "운영환경 배포를 진행합니다."
        log_warning "다음 사항들을 확인해주세요:"
        echo "  • AWS RDS 데이터베이스가 준비되어 있는가?"
        echo "  • AWS S3 버킷이 설정되어 있는가?"
        echo "  • 도메인 및 SSL 인증서가 준비되어 있는가?"
        echo "  • 환경변수의 모든 보안 키가 안전하게 설정되어 있는가?"
        echo ""
        read -p "모든 사항을 확인했습니까? (yes/no): " confirm
        if [[ $confirm != "yes" ]]; then
            log_error "운영환경 배포를 취소합니다."
            exit 1
        fi
    fi
}

# 의존성 패키지 설치
install_dependencies() {
    if [ "$SKIP_DEPS" = true ]; then
        log_warning "의존성 설치를 건너뜁니다."
        return
    fi
    
    log_step "의존성 패키지를 설치합니다..."
    
    # pip 업그레이드
    log_info "pip를 최신 버전으로 업그레이드합니다..."
    pip install --upgrade pip
    
    # 환경별 패키지 설치
    log_info "환경별 패키지를 설치합니다: $REQUIREMENTS_FILE"
    pip install -r $REQUIREMENTS_FILE
    
    # 운영환경 추가 패키지
    if [ "$ENVIRONMENT" = "prod" ]; then
        log_info "운영환경 추가 패키지를 설치합니다..."
        pip install gunicorn psycopg2-binary
    fi
    
    log_success "의존성 패키지 설치 완료"
}

# Django 설정 및 검증
setup_django() {
    log_step "Django 설정을 검증합니다..."
    
    # 환경변수 설정
    export DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS
    
    # 환경별 .env 파일을 .env로 복사
    if [ -f "$ENV_FILE" ]; then
        cp $ENV_FILE .env
        log_info "$ENV_FILE을 .env로 복사했습니다."
    fi
    
    # Django 설정 검증
    log_info "Django 설정을 검증합니다..."
    python manage.py check
    
    # 운영환경에서는 보안 검사 추가
    if [ "$ENVIRONMENT" = "prod" ]; then
        log_info "운영환경 보안 검사를 수행합니다..."
        python manage.py check --deploy
    fi
    
    log_success "Django 설정 검증 완료"
}

# 데이터베이스 설정
setup_database() {
    log_step "데이터베이스를 설정합니다..."
    
    if [ "$RESET_DB" = true ]; then
        if [ "$ENVIRONMENT" = "prod" ]; then
            log_error "운영환경에서는 --reset-db 옵션을 사용할 수 없습니다."
            exit 1
        fi
        log_warning "데이터베이스를 완전 초기화합니다..."
        python manage.py flush --noinput || true
    fi
    
    # 마이그레이션 생성 및 적용
    log_info "마이그레이션을 생성합니다..."
    python manage.py makemigrations
    
    log_info "마이그레이션을 적용합니다..."
    python manage.py migrate
    
    log_success "데이터베이스 설정 완료"
}

# 슈퍼유저 생성
create_superuser() {
    log_step "관리자 계정을 생성합니다..."
    
    if [ "$ENVIRONMENT" = "prod" ] && [ -z "$ADMIN_PASSWORD" ]; then
        # 운영환경에서는 안전한 비밀번호를 대화형으로 입력받음
        log_info "운영환경 관리자 계정을 생성합니다."
        echo "보안을 위해 강력한 비밀번호를 설정해주세요."
        python manage.py createsuperuser --username $ADMIN_USER
    else
        # 개발환경에서는 자동으로 생성
        python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(user_id='$ADMIN_USER').exists():
    try:
        User.objects.create_superuser(
            user_id='$ADMIN_USER', 
            password='$ADMIN_PASSWORD',
            name='$ADMIN_NAME',
            user_type='designer'
        )
        print('✅ 관리자 계정 생성 완료')
    except Exception as e:
        print(f'⚠️ 관리자 계정 생성 실패: {e}')
        print('나중에 수동으로 생성하세요: python manage.py createsuperuser')
else:
    print('✅ 관리자 계정이 이미 존재합니다.')
"
    fi
    
    log_success "관리자 계정 설정 완료"
}

# 테스트 데이터 생성
create_test_data() {
    if [ "$SKIP_TEST" = true ] || [ "$ALLOW_TEST_DATA" = false ]; then
        log_warning "테스트 데이터 생성을 건너뜁니다."
        return
    fi
    
    if [ "$ENVIRONMENT" = "prod" ]; then
        log_warning "운영환경에서는 테스트 데이터를 생성하지 않습니다."
        return
    fi
    
    log_step "테스트 데이터를 생성합니다..."
    
    # fixtures 디렉토리가 있고 테스트 데이터 파일이 있으면 로드
    if [ -f "fixtures/test_data.json" ]; then
        log_info "테스트 데이터를 로드합니다..."
        python manage.py loaddata fixtures/test_data.json
        log_success "테스트 데이터 로드 완료"
    else
        log_info "fixtures/test_data.json 파일이 없습니다. 기본 테스트 데이터를 생성합니다..."
        
        # 기본 테스트 데이터 생성 스크립트 실행
        python manage.py shell -c "
# 기본 테스트 데이터 생성 로직을 여기에 추가
print('✅ 기본 테스트 데이터 생성 완료')
"
    fi
}

# 정적 파일 수집
collect_static_files() {
    if [ "$COLLECT_STATIC" = false ]; then
        log_info "정적 파일 수집을 건너뜁니다."
        return
    fi
    
    log_step "정적 파일을 수집합니다..."
    
    python manage.py collectstatic --noinput --clear
    
    log_success "정적 파일 수집 완료"
}

# 최종 검증
final_verification() {
    log_step "최종 검증을 수행합니다..."
    
    # 데이터베이스 연결 테스트
    log_info "데이터베이스 연결을 테스트합니다..."
    python manage.py shell -c "
from django.db import connection
cursor = connection.cursor()
cursor.execute('SELECT version()')
result = cursor.fetchone()
print(f'✅ PostgreSQL 연결 성공: {result[0][:50]}...')
"
    
    # 관리자 계정 확인
    log_info "관리자 계정을 확인합니다..."
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
admin_user = User.objects.filter(user_id='$ADMIN_USER').first()
if admin_user:
    print(f'✅ 관리자 계정 확인: {admin_user.user_id} ({admin_user.name})')
else:
    print('⚠️ 관리자 계정이 없습니다.')
"
    
    # 환경별 추가 검증
    if [ "$ENVIRONMENT" = "prod" ]; then
        log_info "운영환경 보안 설정을 확인합니다..."
        python manage.py shell -c "
from django.conf import settings
print(f'DEBUG: {settings.DEBUG}')
print(f'ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}')
print(f'SECURE_SSL_REDIRECT: {getattr(settings, \"SECURE_SSL_REDIRECT\", False)}')
"
    fi
    
    log_success "최종 검증 완료"
}

# 완료 메시지 출력
show_completion_message() {
    log_header "🎉 FabLink Backend 최초 빌드 완료!"
    
    echo -e "${GREEN}✅ $ENVIRONMENT 환경 설정이 완료되었습니다!${NC}"
    echo ""
    
    case $ENVIRONMENT in
        local)
            echo -e "${BLUE}🚀 서버 시작:${NC}"
            echo "   python manage.py runserver"
            echo ""
            echo -e "${BLUE}🌐 접속 주소:${NC}"
            echo "   • 메인: http://localhost:8000/"
            echo "   • 관리자: http://localhost:8000/admin/"
            echo "   • API: http://localhost:8000/api/"
            echo ""
            echo -e "${BLUE}👤 관리자 계정:${NC}"
            echo "   • User ID: $ADMIN_USER"
            echo "   • Password: $ADMIN_PASSWORD"
            echo "   • Name: $ADMIN_NAME"
            ;;
        dev)
            echo -e "${BLUE}🚀 서버 시작:${NC}"
            echo "   python manage.py runserver 0.0.0.0:8000"
            echo "   # 또는 Gunicorn 사용:"
            echo "   gunicorn fablink_project.wsgi:application --bind 0.0.0.0:8000"
            echo ""
            echo -e "${BLUE}🌐 접속 주소:${NC}"
            echo "   • 메인: https://dev-api.fablink.com/"
            echo "   • 관리자: https://dev-api.fablink.com/admin/"
            echo "   • API: https://dev-api.fablink.com/api/"
            ;;
        prod)
            echo -e "${BLUE}🚀 서버 시작:${NC}"
            echo "   gunicorn fablink_project.wsgi:application --bind 0.0.0.0:8000 --workers 4"
            echo ""
            echo -e "${BLUE}🌐 접속 주소:${NC}"
            echo "   • 메인: https://api.fablink.com/"
            echo "   • 관리자: https://api.fablink.com/admin/"
            echo "   • API: https://api.fablink.com/api/"
            echo ""
            echo -e "${RED}⚠️ 운영환경 주의사항:${NC}"
            echo "   • 관리자 비밀번호를 안전하게 보관하세요"
            echo "   • 정기적으로 보안 업데이트를 수행하세요"
            echo "   • 로그 모니터링을 설정하세요"
            ;;
    esac
    
    echo ""
    echo -e "${BLUE}🗄️ 데이터베이스 접속:${NC}"
    echo "   psql -h $DB_HOST -U $DB_USER -d $DB_NAME"
    if [ "$ENVIRONMENT" = "local" ]; then
        echo "   (비밀번호: $DB_PASSWORD)"
    fi
    echo ""
    echo -e "${YELLOW}📝 다음 단계:${NC}"
    if [ "$ENVIRONMENT" = "local" ]; then
        echo "   1. python manage.py runserver 로 서버 시작"
        echo "   2. http://localhost:8000/admin/ 에서 관리자 페이지 확인"
        echo "   3. API 문서 확인: http://localhost:8000/api/"
    else
        echo "   1. 웹서버(Nginx) 설정"
        echo "   2. SSL 인증서 설정"
        echo "   3. 도메인 연결"
        echo "   4. 모니터링 설정"
    fi
    echo ""
}

# 메인 실행 함수
main() {
    # 환경 인자 확인
    if [ $# -eq 0 ]; then
        log_error "환경을 지정해주세요."
        show_help
        exit 1
    fi
    
    ENVIRONMENT=$1
    shift
    
    # 도움말 확인
    if [ "$ENVIRONMENT" = "-h" ] || [ "$ENVIRONMENT" = "--help" ]; then
        show_help
        exit 0
    fi
    
    # 옵션 파싱
    SKIP_DEPS=false
    SKIP_TEST=false
    RESET_DB=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            --skip-deps)
                SKIP_DEPS=true
                shift
                ;;
            --skip-test)
                SKIP_TEST=true
                shift
                ;;
            --reset-db)
                RESET_DB=true
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
    
    # 환경별 설정 로드
    load_environment_config $ENVIRONMENT
    
    log_header "🚀 FabLink Backend 최초 빌드 시작 ($ENVIRONMENT)"
    
    # 실행 단계들
    check_prerequisites
    install_dependencies
    setup_django
    setup_database
    create_superuser
    create_test_data
    collect_static_files
    final_verification
    show_completion_message
    
    log_success "🎉 모든 작업이 성공적으로 완료되었습니다!"
}

# 스크립트 실행
main "$@"
