#!/bin/bash
# =================================================================
# scripts/setup_postgresql_prod.sh - 운영 서버환경 PostgreSQL DB 설정
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

log_warning "🚨 운영 서버환경 PostgreSQL 데이터베이스 설정을 시작합니다."
log_warning "이 작업은 운영 환경에 영향을 줄 수 있습니다. 신중하게 진행하세요."
echo ""

# 운영환경 확인
echo -e "${RED}⚠️ 운영환경 체크리스트:${NC}"
echo "□ AWS RDS PostgreSQL 운영 인스턴스가 준비되어 있는가?"
echo "□ 데이터베이스 백업이 설정되어 있는가?"
echo "□ 보안 그룹이 올바르게 설정되어 있는가?"
echo "□ SSL 연결이 강제되어 있는가?"
echo "□ 모니터링이 설정되어 있는가?"
echo "□ 데이터베이스 파라미터 그룹이 운영환경에 맞게 설정되어 있는가?"
echo ""

read -p "모든 체크리스트를 확인했습니까? (yes/no): " checklist_confirm
if [[ $checklist_confirm != "yes" ]]; then
    log_error "운영환경 설정을 취소합니다."
    exit 1
fi

echo ""
log_info "운영환경 데이터베이스 정보를 입력해주세요:"

# 사용자 입력 받기
read -p "RDS 엔드포인트를 입력하세요: " RDS_ENDPOINT
if [[ -z "$RDS_ENDPOINT" ]]; then
    log_error "RDS 엔드포인트는 필수입니다."
    exit 1
fi

read -p "마스터 사용자명을 입력하세요 (기본값: postgres): " MASTER_USER
MASTER_USER=${MASTER_USER:-postgres}

echo "마스터 비밀번호를 입력하세요:"
read -s MASTER_PASSWORD
echo ""

if [[ -z "$MASTER_PASSWORD" ]]; then
    log_error "마스터 비밀번호는 필수입니다."
    exit 1
fi

# 운영환경 데이터베이스 정보
PROD_DB_NAME="fablink_prod_db"
PROD_DB_USER="fablink_prod_user"

echo ""
echo "운영환경 데이터베이스 사용자의 강력한 비밀번호를 설정하세요:"
echo "(최소 12자, 대소문자, 숫자, 특수문자 포함)"
read -s PROD_DB_PASSWORD
echo ""
echo "비밀번호를 다시 입력하세요:"
read -s PROD_DB_PASSWORD_CONFIRM
echo ""

if [[ "$PROD_DB_PASSWORD" != "$PROD_DB_PASSWORD_CONFIRM" ]]; then
    log_error "비밀번호가 일치하지 않습니다."
    exit 1
fi

if [[ ${#PROD_DB_PASSWORD} -lt 12 ]]; then
    log_error "비밀번호는 최소 12자 이상이어야 합니다."
    exit 1
fi

log_info "운영환경 데이터베이스와 사용자를 생성합니다..."

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

# SSL 연결 확인
log_info "SSL 연결을 확인합니다..."
SSL_STATUS=$(PGPASSWORD=$MASTER_PASSWORD psql -h $RDS_ENDPOINT -U $MASTER_USER -d postgres -t -c "SHOW ssl;" | xargs)
if [[ "$SSL_STATUS" != "on" ]]; then
    log_warning "SSL이 활성화되지 않았습니다. 운영환경에서는 SSL을 사용하는 것을 강력히 권장합니다."
else
    log_success "SSL 연결이 활성화되어 있습니다."
fi

# 최종 확인
echo ""
log_warning "다음 작업을 수행합니다:"
echo "  • 데이터베이스: $PROD_DB_NAME 생성"
echo "  • 사용자: $PROD_DB_USER 생성"
echo "  • 권한 설정"
echo ""
read -p "계속 진행하시겠습니까? (yes/no): " final_confirm
if [[ $final_confirm != "yes" ]]; then
    log_error "운영환경 설정을 취소합니다."
    exit 1
fi

# 운영환경 데이터베이스 및 사용자 생성
log_info "운영환경 데이터베이스와 사용자를 생성합니다..."

PGPASSWORD=$MASTER_PASSWORD psql -h $RDS_ENDPOINT -U $MASTER_USER -d postgres << EOSQL
-- 기존 데이터베이스 및 사용자 확인 (운영환경에서는 삭제하지 않음)
DO \$\$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_database WHERE datname = '$PROD_DB_NAME') THEN
        RAISE NOTICE '⚠️ 데이터베이스 $PROD_DB_NAME이 이미 존재합니다.';
    ELSE
        -- 운영환경 데이터베이스 생성
        CREATE DATABASE $PROD_DB_NAME
            WITH 
            OWNER = $MASTER_USER
            ENCODING = 'UTF8'
            TEMPLATE = template0
            LC_COLLATE = 'C.UTF-8'
            LC_CTYPE = 'C.UTF-8'
            TABLESPACE = pg_default
            CONNECTION LIMIT = -1;
        RAISE NOTICE '✅ 데이터베이스 $PROD_DB_NAME이 생성되었습니다.';
    END IF;
END
\$\$;

-- 운영환경 사용자 생성 또는 업데이트
DO \$\$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_user WHERE usename = '$PROD_DB_USER') THEN
        -- 기존 사용자 비밀번호 업데이트
        ALTER USER $PROD_DB_USER WITH PASSWORD '$PROD_DB_PASSWORD';
        RAISE NOTICE '✅ 사용자 $PROD_DB_USER의 비밀번호가 업데이트되었습니다.';
    ELSE
        -- 새 사용자 생성
        CREATE USER $PROD_DB_USER WITH PASSWORD '$PROD_DB_PASSWORD';
        RAISE NOTICE '✅ 사용자 $PROD_DB_USER가 생성되었습니다.';
    END IF;
END
\$\$;

-- 사용자 설정
ALTER ROLE $PROD_DB_USER SET client_encoding TO 'utf8';
ALTER ROLE $PROD_DB_USER SET default_transaction_isolation TO 'read committed';
ALTER ROLE $PROD_DB_USER SET timezone TO 'Asia/Seoul';

-- 데이터베이스 소유권 변경
ALTER DATABASE $PROD_DB_NAME OWNER TO $PROD_DB_USER;

-- 권한 부여
GRANT ALL PRIVILEGES ON DATABASE $PROD_DB_NAME TO $PROD_DB_USER;

\echo '✅ 운영 서버환경 PostgreSQL 설정 완료!'
EOSQL

# 데이터베이스별 권한 설정
log_info "데이터베이스별 권한을 설정합니다..."
PGPASSWORD=$PROD_DB_PASSWORD psql -h $RDS_ENDPOINT -U $PROD_DB_USER -d $PROD_DB_NAME << EOSQL
GRANT ALL ON SCHEMA public TO $PROD_DB_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $PROD_DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $PROD_DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $PROD_DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $PROD_DB_USER;
EOSQL

# 연결 테스트
log_info "운영 데이터베이스 연결을 테스트합니다..."
if PGPASSWORD=$PROD_DB_PASSWORD psql -h $RDS_ENDPOINT -U $PROD_DB_USER -d $PROD_DB_NAME -c "SELECT version();" > /dev/null 2>&1; then
    log_success "운영 데이터베이스 연결 테스트 성공!"
else
    log_error "운영 데이터베이스 연결 테스트 실패!"
    exit 1
fi

# .env.prod 파일 업데이트 (있다면)
if [ -f ".env.prod" ]; then
    log_info ".env.prod 파일의 데이터베이스 정보를 업데이트합니다..."
    
    # 백업 생성
    cp .env.prod .env.prod.backup.$(date +%Y%m%d_%H%M%S)
    
    # 데이터베이스 정보 업데이트
    sed -i.tmp \
        -e "s/DB_HOST=.*/DB_HOST=$RDS_ENDPOINT/" \
        -e "s/DB_NAME=.*/DB_NAME=$PROD_DB_NAME/" \
        -e "s/DB_USER=.*/DB_USER=$PROD_DB_USER/" \
        -e "s/DB_PASSWORD=.*/DB_PASSWORD=$PROD_DB_PASSWORD/" \
        .env.prod
    
    rm .env.prod.tmp
    
    # 파일 권한 설정
    chmod 600 .env.prod
    log_success ".env.prod 파일이 업데이트되었습니다."
fi

# 보안 정보 저장
SECURITY_INFO_FILE="prod_db_info_$(date +%Y%m%d_%H%M%S).txt"
cat > $SECURITY_INFO_FILE << EOF
FabLink 운영환경 데이터베이스 정보
생성일시: $(date)

호스트: $RDS_ENDPOINT
데이터베이스: $PROD_DB_NAME
사용자: $PROD_DB_USER
비밀번호: $PROD_DB_PASSWORD

⚠️ 이 파일은 안전한 곳에 보관하고, 설정 완료 후 삭제하세요.
EOF

chmod 600 $SECURITY_INFO_FILE

echo ""
log_success "🎉 운영 서버환경 PostgreSQL 설정이 완료되었습니다!"
echo ""
echo -e "${BLUE}📋 운영 서버 데이터베이스 정보:${NC}"
echo "   🌐 호스트: $RDS_ENDPOINT"
echo "   🏷️  데이터베이스: $PROD_DB_NAME"
echo "   👤 사용자: $PROD_DB_USER"
echo "   🔑 비밀번호: [보안 정보 파일 참조]"
echo ""
echo -e "${RED}🔐 중요한 보안 사항:${NC}"
echo "   • 데이터베이스 정보가 $SECURITY_INFO_FILE 파일에 저장되었습니다"
echo "   • 이 파일을 안전한 곳에 백업하고 서버에서는 삭제하세요"
echo "   • .env.prod 파일의 권한이 600으로 설정되었습니다"
echo "   • 정기적으로 비밀번호를 변경하세요"
echo "   • 데이터베이스 접근 로그를 모니터링하세요"
echo ""
echo -e "${YELLOW}🚀 다음 단계:${NC}"
echo "   1. $SECURITY_INFO_FILE 파일을 안전한 곳에 백업"
echo "   2. 서버에서 보안 정보 파일 삭제: rm $SECURITY_INFO_FILE"
echo "   3. .env.prod 파일의 다른 환경변수들도 확인"
echo "   4. ./scripts/first_build.sh prod"
echo ""
echo -e "${BLUE}🗄️ 데이터베이스 직접 접속:${NC}"
echo "   psql -h $RDS_ENDPOINT -U $PROD_DB_USER -d $PROD_DB_NAME"
echo ""
echo -e "${YELLOW}📊 모니터링 설정 권장사항:${NC}"
echo "   • CloudWatch에서 데이터베이스 메트릭 모니터링"
echo "   • 연결 수, CPU 사용률, 메모리 사용률 알람 설정"
echo "   • 슬로우 쿼리 로그 활성화"
echo "   • 정기적인 백업 스케줄 확인"
echo ""
