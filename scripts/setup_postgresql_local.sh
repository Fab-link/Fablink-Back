#!/bin/bash
# =================================================================
# scripts/setup_postgresql_local.sh - 로컬 개발환경 PostgreSQL DB 생성
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

log_info "FabLink 로컬 개발환경 PostgreSQL 데이터베이스 설정을 시작합니다..."

# PostgreSQL 설치 확인
if ! command -v psql &> /dev/null; then
    log_warning "PostgreSQL이 설치되지 않았습니다. 설치를 진행합니다..."
    
    if command -v apt &> /dev/null; then
        sudo apt update
        sudo apt install -y postgresql postgresql-contrib
        log_success "PostgreSQL 설치가 완료되었습니다."
    elif command -v brew &> /dev/null; then
        brew install postgresql
        brew services start postgresql
        log_success "PostgreSQL 설치가 완료되었습니다."
    else
        log_error "지원하지 않는 운영체제입니다. PostgreSQL을 수동으로 설치해주세요."
        exit 1
    fi
else
    log_success "PostgreSQL이 이미 설치되어 있습니다."
fi

# PostgreSQL 서비스 시작 (Linux)
if command -v systemctl &> /dev/null; then
    log_info "PostgreSQL 서비스를 시작합니다..."
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
    log_success "PostgreSQL 서비스가 시작되었습니다."
fi

# 로컬 개발환경 데이터베이스 및 사용자 생성
log_info "로컬 개발환경 데이터베이스와 사용자를 생성합니다..."

# PostgreSQL 사용자 확인 (Linux vs macOS)
if command -v systemctl &> /dev/null; then
    # Linux
    POSTGRES_USER="postgres"
    PSQL_CMD="sudo -u postgres psql"
    LOCALE_COLLATE="C.UTF-8"
    LOCALE_CTYPE="C.UTF-8"
else
    # macOS
    POSTGRES_USER=$(whoami)
    PSQL_CMD="/opt/homebrew/bin/psql postgres"
    LOCALE_COLLATE="en_US.UTF-8"
    LOCALE_CTYPE="en_US.UTF-8"
fi

# 기존 데이터베이스 및 사용자 정리
$PSQL_CMD -c "DROP DATABASE IF EXISTS fablink_local_db;" 2>/dev/null || true
$PSQL_CMD -c "REVOKE ALL PRIVILEGES ON DATABASE fablink_db FROM fablink_user;" 2>/dev/null || true
$PSQL_CMD -c "DROP USER IF EXISTS fablink_user;" 2>/dev/null || true

# 로컬 개발환경 사용자 생성
$PSQL_CMD -c "CREATE USER fablink_user WITH PASSWORD 'local123' CREATEDB SUPERUSER;"
$PSQL_CMD -c "ALTER ROLE fablink_user SET client_encoding TO 'utf8';"
$PSQL_CMD -c "ALTER ROLE fablink_user SET default_transaction_isolation TO 'read committed';"
$PSQL_CMD -c "ALTER ROLE fablink_user SET timezone TO 'Asia/Seoul';"

# 로컬 개발환경 데이터베이스 생성 (로케일 변수 직접 사용)
$PSQL_CMD -c "CREATE DATABASE fablink_local_db WITH OWNER fablink_user ENCODING 'UTF8' LC_COLLATE='${LOCALE_COLLATE}' LC_CTYPE='${LOCALE_CTYPE}';"

# 권한 부여
$PSQL_CMD -c "GRANT ALL PRIVILEGES ON DATABASE fablink_local_db TO fablink_user;"

echo "✅ 로컬 개발환경 PostgreSQL 설정 완료!"
echo "📋 데이터베이스: fablink_local_db"
echo "👤 사용자: fablink_user"
echo "🔑 비밀번호: local123"

# 추가 권한 설정
$PSQL_CMD -d fablink_local_db << 'EOSQL'
GRANT ALL ON SCHEMA public TO fablink_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO fablink_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO fablink_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO fablink_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO fablink_user;
EOSQL

# 연결 테스트
log_info "데이터베이스 연결을 테스트합니다..."
if [ "$POSTGRES_USER" = "postgres" ]; then
    # Linux
    if PGPASSWORD=local123 psql -h localhost -U fablink_user -d fablink_local_db -c "SELECT version();" > /dev/null 2>&1; then
        log_success "데이터베이스 연결 테스트 성공!"
    else
        log_error "데이터베이스 연결 테스트 실패!"
        exit 1
    fi
else
    # macOS
    if PGPASSWORD=local123 /opt/homebrew/bin/psql -h localhost -U fablink_user -d fablink_local_db -c "SELECT version();" > /dev/null 2>&1; then
        log_success "데이터베이스 연결 테스트 성공!"
    else
        log_error "데이터베이스 연결 테스트 실패!"
        exit 1
    fi
fi

echo ""
log_success "🎉 로컬 개발환경 PostgreSQL 설정이 완료되었습니다!"
echo ""
echo -e "${BLUE}📋 로컬 데이터베이스 정보:${NC}"
echo "   🏷️  데이터베이스: fablink_local_db"
echo "   👤 사용자: fablink_user"
echo "   🔑 비밀번호: local123"
echo "   🌐 호스트: localhost:5432"
echo ""
echo -e "${YELLOW}🚀 다음 단계:${NC}"
echo "   1. ./scripts/setup_env.sh local"
echo "   2. python manage.py migrate"
echo "   3. python manage.py createsuperuser"
echo "   4. python manage.py runserver"
echo ""
