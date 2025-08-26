#!/bin/bash
# =================================================================
# scripts/setup_postgresql_dev.sh - 개발 서버환경 PostgreSQL DB 설정
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

log_info "FabLink 개발 서버환경 PostgreSQL 데이터베이스 설정을 시작합니다..."

# 개발 서버 환경에서는 주로 AWS RDS를 사용
log_warning "개발 서버 환경에서는 AWS RDS PostgreSQL을 사용합니다."
echo ""
echo "다음 사항들을 확인해주세요:"
echo "1. AWS RDS PostgreSQL 인스턴스가 생성되어 있는가?"
echo "2. 보안 그룹에서 개발 서버 IP가 허용되어 있는가?"
echo "3. 데이터베이스 엔드포인트 정보를 알고 있는가?"
echo ""

# 사용자 입력 받기
read -p "RDS 엔드포인트를 입력하세요 (예: fablink-dev.cluster-xxxxx.ap-northeast-2.rds.amazonaws.com): " RDS_ENDPOINT
read -p "마스터 사용자명을 입력하세요 (기본값: postgres): " MASTER_USER
MASTER_USER=${MASTER_USER:-postgres}
read -s -p "마스터 비밀번호를 입력하세요: " MASTER_PASSWORD
echo ""

# 개발환경 데이터베이스 정보
DEV_DB_NAME="fablink_dev_db"
DEV_DB_USER="fablink_dev_user"
DEV_DB_PASSWORD="dev-db-password-$(date +%s)"  # 타임스탬프 추가로 유니크하게

log_info "개발환경 데이터베이스와 사용자를 생성합니다..."

# PostgreSQL 연결 테스트
log_info "RDS 연결을 테스트합니다..."
if ! PGPASSWORD=$MASTER_PASSWORD psql -h $RDS_ENDPOINT -U $MASTER_USER -d postgres -c "SELECT version();" > /dev/null 2>&1; then
    log_error "RDS에 연결할 수 없습니다. 다음을 확인해주세요:"
    echo "  • RDS 엔드포인트가 올바른가?"
    echo "  • 마스터 사용자명과 비밀번호가 올바른가?"
    echo "  • 보안 그룹에서 현재 IP가 허용되어 있는가?"
    echo "  • RDS 인스턴스가 실행 중인가?"
    exit 1
fi
log_success "RDS 연결 테스트 성공!"

# 개발환경 데이터베이스 및 사용자 생성
PGPASSWORD=$MASTER_PASSWORD psql -h $RDS_ENDPOINT -U $MASTER_USER -d postgres << EOSQL
-- 기존 데이터베이스 및 사용자 삭제 (있다면)
DROP DATABASE IF EXISTS $DEV_DB_NAME;
DROP USER IF EXISTS $DEV_DB_USER;

-- 개발환경 사용자 생성
CREATE USER $DEV_DB_USER WITH PASSWORD '$DEV_DB_PASSWORD';
ALTER ROLE $DEV_DB_USER SET client_encoding TO 'utf8';
ALTER ROLE $DEV_DB_USER SET default_transaction_isolation TO 'read committed';
ALTER ROLE $DEV_DB_USER SET timezone TO 'Asia/Seoul';
ALTER USER $DEV_DB_USER CREATEDB;

-- 개발환경 데이터베이스 생성
CREATE DATABASE $DEV_DB_NAME
    WITH 
    OWNER = $DEV_DB_USER
    ENCODING = 'UTF8'
    TEMPLATE = template0
    LC_COLLATE = 'C.UTF-8'
    LC_CTYPE = 'C.UTF-8'
    TABLESPACE = pg_default
    CONNECTION LIMIT = -1;

-- 권한 부여
GRANT ALL PRIVILEGES ON DATABASE $DEV_DB_NAME TO $DEV_DB_USER;

\echo '✅ 개발 서버환경 PostgreSQL 설정 완료!'
\echo '📋 데이터베이스: $DEV_DB_NAME'
\echo '👤 사용자: $DEV_DB_USER'
\echo '🔑 비밀번호: $DEV_DB_PASSWORD'
EOSQL

# 추가 권한 설정
PGPASSWORD=$DEV_DB_PASSWORD psql -h $RDS_ENDPOINT -U $DEV_DB_USER -d $DEV_DB_NAME << EOSQL
GRANT ALL ON SCHEMA public TO $DEV_DB_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DEV_DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DEV_DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DEV_DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DEV_DB_USER;
EOSQL

# 연결 테스트
log_info "개발 데이터베이스 연결을 테스트합니다..."
if PGPASSWORD=$DEV_DB_PASSWORD psql -h $RDS_ENDPOINT -U $DEV_DB_USER -d $DEV_DB_NAME -c "SELECT version();" > /dev/null 2>&1; then
    log_success "개발 데이터베이스 연결 테스트 성공!"
else
    log_error "개발 데이터베이스 연결 테스트 실패!"
    exit 1
fi

# .env.dev 파일 업데이트 (있다면)
if [ -f ".env.dev" ]; then
    log_info ".env.dev 파일의 데이터베이스 정보를 업데이트합니다..."
    
    # 백업 생성
    cp .env.dev .env.dev.backup.$(date +%Y%m%d_%H%M%S)
    
    # 데이터베이스 정보 업데이트
    sed -i.tmp \
        -e "s/DB_HOST=.*/DB_HOST=$RDS_ENDPOINT/" \
        -e "s/DB_NAME=.*/DB_NAME=$DEV_DB_NAME/" \
        -e "s/DB_USER=.*/DB_USER=$DEV_DB_USER/" \
        -e "s/DB_PASSWORD=.*/DB_PASSWORD=$DEV_DB_PASSWORD/" \
        .env.dev
    
    rm .env.dev.tmp
    log_success ".env.dev 파일이 업데이트되었습니다."
fi

echo ""
log_success "🎉 개발 서버환경 PostgreSQL 설정이 완료되었습니다!"
echo ""
echo -e "${BLUE}📋 개발 서버 데이터베이스 정보:${NC}"
echo "   🌐 호스트: $RDS_ENDPOINT"
echo "   🏷️  데이터베이스: $DEV_DB_NAME"
echo "   👤 사용자: $DEV_DB_USER"
echo "   🔑 비밀번호: $DEV_DB_PASSWORD"
echo ""
echo -e "${YELLOW}🔐 보안 정보:${NC}"
echo "   • 데이터베이스 비밀번호를 안전한 곳에 저장하세요"
echo "   • .env.dev 파일의 권한을 600으로 설정하세요: chmod 600 .env.dev"
echo ""
echo -e "${YELLOW}🚀 다음 단계:${NC}"
echo "   1. .env.dev 파일의 다른 환경변수들도 확인하세요"
echo "   2. ./scripts/first_build.sh dev"
echo ""
echo -e "${BLUE}🗄️ 데이터베이스 직접 접속:${NC}"
echo "   psql -h $RDS_ENDPOINT -U $DEV_DB_USER -d $DEV_DB_NAME"
echo ""
