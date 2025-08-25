#!/bin/bash

# =================================================================
# scripts/reset_database.sh - DB 완전 초기화 후 재구성 스크립트
# =================================================================
# 
# 마이그레이션 충돌 해결을 위한 DB 완전 초기화 스크립트
# 1. 기존 마이그레이션 파일 백업 및 삭제
# 2. DB 완전 삭제 및 재생성
# 3. 새로운 마이그레이션 파일 생성
# 4. DB 마이그레이션 적용
# 5. 슈퍼유저 생성
#
# =================================================================

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# 에러 핸들링
handle_error() {
    log_error "스크립트 실행 중 오류가 발생했습니다."
    log_error "라인 $1에서 오류 발생"
    exit 1
}

trap 'handle_error $LINENO' ERR

# 도움말
show_help() {
    echo "DB 완전 초기화 후 재구성 스크립트"
    echo ""
    echo "사용법:"
    echo "  ./scripts/reset_database.sh [옵션]"
    echo ""
    echo "옵션:"
    echo "  -h, --help     이 도움말 출력"
    echo "  --no-backup    마이그레이션 파일 백업 건너뛰기"
    echo "  --no-superuser 슈퍼유저 생성 건너뛰기"
    echo ""
    echo "전제 조건:"
    echo "  • 가상환경 활성화 (source venv/bin/activate)"
    echo "  • PostgreSQL 서비스 실행 중"
    echo "  • .env 파일 존재"
    echo ""
}

# 전제 조건 확인
check_prerequisites() {
    log_info "전제 조건을 확인합니다..."
    
    # 가상환경 확인
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        log_error "가상환경이 활성화되지 않았습니다."
        echo "source venv/bin/activate 명령어로 가상환경을 활성화하세요."
        exit 1
    fi
    log_success "가상환경 확인: $VIRTUAL_ENV"
    
    # .env 파일 확인
    if [ ! -f ".env" ]; then
        log_error ".env 파일이 없습니다."
        exit 1
    fi
    log_success ".env 파일 확인"
    
    # 환경변수 로드
    source .env
    
    # DB 연결 확인
    log_info "데이터베이스 연결을 확인합니다..."
    if ! PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d postgres -c "SELECT 1;" > /dev/null 2>&1; then
        log_error "PostgreSQL에 연결할 수 없습니다."
        echo "PostgreSQL 서비스가 실행 중인지 확인하세요."
        exit 1
    fi
    log_success "데이터베이스 연결 확인"
}

# 마이그레이션 파일 백업
backup_migrations() {
    if [ "$NO_BACKUP" = true ]; then
        log_warning "마이그레이션 파일 백업을 건너뜁니다."
        return
    fi
    
    log_info "기존 마이그레이션 파일을 백업합니다..."
    
    backup_dir="backups/migrations/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    
    for app_dir in apps/*/; do
        if [ -d "$app_dir" ]; then
            app_name=$(basename "$app_dir")
            if [ "$app_name" != "__pycache__" ] && [ -d "$app_dir/migrations" ]; then
                mkdir -p "$backup_dir/$app_name"
                find "$app_dir/migrations" -name "*.py" ! -name "__init__.py" -exec cp {} "$backup_dir/$app_name/" \; 2>/dev/null || true
                log_info "$app_name 앱 마이그레이션 백업 완료"
            fi
        fi
    done
    
    log_success "마이그레이션 파일 백업 완료: $backup_dir"
}

# 마이그레이션 파일 삭제
remove_migrations() {
    log_info "기존 마이그레이션 파일을 삭제합니다..."
    
    for app_dir in apps/*/; do
        if [ -d "$app_dir" ]; then
            app_name=$(basename "$app_dir")
            if [ "$app_name" != "__pycache__" ] && [ -d "$app_dir/migrations" ]; then
                find "$app_dir/migrations" -name "*.py" ! -name "__init__.py" -delete 2>/dev/null || true
                log_info "$app_name 앱 마이그레이션 파일 삭제 완료"
            fi
        fi
    done
    
    log_success "마이그레이션 파일 삭제 완료"
}

# 데이터베이스 재생성
recreate_database() {
    log_info "데이터베이스를 재생성합니다..."
    
    # 환경변수에서 DB 정보 읽기
    source .env
    
    # 기존 연결 종료
    log_info "기존 데이터베이스 연결을 종료합니다..."
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d postgres -c "
        SELECT pg_terminate_backend(pid) 
        FROM pg_stat_activity 
        WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();
    " 2>/dev/null || true
    
    # 데이터베이스 삭제 및 재생성
    log_info "데이터베이스를 삭제하고 재생성합니다..."
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d postgres << EOF
DROP DATABASE IF EXISTS $DB_NAME;
CREATE DATABASE $DB_NAME OWNER $DB_USER ENCODING 'UTF8' LC_COLLATE='C.UTF-8' LC_CTYPE='C.UTF-8';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
EOF
    
    log_success "데이터베이스 재생성 완료"
}

# 새 마이그레이션 생성 및 적용
create_and_apply_migrations() {
    log_info "새로운 마이그레이션을 생성합니다..."
    
    # Django 설정 확인
    python manage.py check
    
    # 새 마이그레이션 생성
    python manage.py makemigrations accounts
    python manage.py makemigrations manufacturing
    python manage.py makemigrations core
    
    log_success "새 마이그레이션 생성 완료"
    
    log_info "마이그레이션을 적용합니다..."
    python manage.py migrate
    
    log_success "마이그레이션 적용 완료"
    
    # 마이그레이션 상태 확인
    log_info "마이그레이션 상태를 확인합니다..."
    python manage.py showmigrations
}

# 슈퍼유저 생성
create_superuser() {
    if [ "$NO_SUPERUSER" = true ]; then
        log_warning "슈퍼유저 생성을 건너뜁니다."
        return
    fi
    
    log_info "개발용 슈퍼유저를 생성합니다..."
    
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(user_id='admin').exists():
    try:
        User.objects.create_superuser(
            user_id='admin', 
            password='admin123',
            name='관리자'
        )
        print('✅ 슈퍼유저 생성 완료')
    except Exception as e:
        print(f'⚠️ 슈퍼유저 생성 실패: {e}')
else:
    print('✅ 슈퍼유저가 이미 존재합니다.')
"
    
    log_success "슈퍼유저 설정 완료"
}

# 완료 메시지
show_completion() {
    echo ""
    echo -e "${GREEN}🎉 데이터베이스 완전 초기화 및 재구성이 완료되었습니다!${NC}"
    echo ""
    echo -e "${BLUE}📋 작업 완료 내역:${NC}"
    echo "  ✅ 마이그레이션 파일 백업"
    echo "  ✅ 기존 마이그레이션 파일 삭제"
    echo "  ✅ 데이터베이스 완전 재생성"
    echo "  ✅ 새 마이그레이션 생성 및 적용"
    if [ "$NO_SUPERUSER" != true ]; then
        echo "  ✅ 개발용 슈퍼유저 생성"
    fi
    echo ""
    echo -e "${BLUE}👤 개발용 계정 정보:${NC}"
    echo "  • User ID: admin"
    echo "  • Password: admin123"
    echo "  • Name: 관리자"
    echo ""
    echo -e "${YELLOW}🚀 다음 단계:${NC}"
    echo "  python manage.py runserver"
    echo ""
}

# 메인 함수
main() {
    # 옵션 파싱
    NO_BACKUP=false
    NO_SUPERUSER=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            --no-backup)
                NO_BACKUP=true
                shift
                ;;
            --no-superuser)
                NO_SUPERUSER=true
                shift
                ;;
            *)
                log_error "알 수 없는 옵션: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 프로젝트 루트로 이동
    cd "$(dirname "$0")/.."
    
    echo ""
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE} 🔥 DB 완전 초기화 및 재구성 시작${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo ""
    
    log_warning "⚠️ 이 작업은 모든 데이터베이스 데이터를 삭제합니다!"
    log_warning "⚠️ 마이그레이션 파일도 모두 삭제됩니다!"
    echo ""
    
    read -p "정말로 데이터베이스를 완전히 초기화하시겠습니까? (y/n): " confirm
    if [[ $confirm != "y" ]]; then
        log_info "작업을 취소했습니다."
        exit 0
    fi
    
    # 실행 단계
    check_prerequisites
    backup_migrations
    remove_migrations
    recreate_database
    create_and_apply_migrations
    create_superuser
    show_completion
    
    log_success "🎉 모든 작업이 성공적으로 완료되었습니다!"
}

# 스크립트 실행
main "$@"