# =================================================================
# scripts/setup_prod.sh - 운영환경 Django 설정
# =================================================================

#!/bin/bash

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

echo "🏭 FabLink 운영환경 Django 배포를 시작합니다..."
echo "🚨 이는 운영환경입니다. 신중하게 진행하세요!"

# 확인
read -p "🔐 운영환경 배포를 계속하시겠습니까? (DEPLOY 입력): " confirm
if [[ $confirm != "DEPLOY" ]]; then
    log_error "운영환경 배포가 취소되었습니다."
    exit 1
fi

# 가상환경 확인
if [[ "$VIRTUAL_ENV" == "" ]]; then
    log_error "가상환경이 활성화되지 않았습니다."
    exit 1
fi

# .env 파일 존재 확인
if [ ! -f ".env" ]; then
    log_error ".env 파일이 없습니다. 먼저 ./scripts/setup_postgresql_prod.sh 를 실행하세요."
    exit 1
fi

# 환경변수 설정
export DJANGO_ENV=production

# 운영환경 패키지 설치
log_info "운영환경 패키지를 설치합니다..."
pip install -r requirements/prod.txt

# Django 보안 체크
log_info "Django 보안 설정을 검증합니다..."
python manage.py check --deploy
if [ $? -ne 0 ]; then
    log_error "운영환경 보안 설정에 문제가 있습니다."
    exit 1
fi

# 데이터베이스 연결 테스트
log_info "운영 데이터베이스 연결을 테스트합니다..."
python manage.py shell -c "
from django.db import connection
cursor = connection.cursor()
cursor.execute('SELECT version()')
result = cursor.fetchone()
print(f'✅ 운영 PostgreSQL 연결 성공: {result[0][:50]}...')
"

# 정적 파일 수집
log_info "정적 파일을 수집합니다..."
python manage.py collectstatic --noinput

# 마이그레이션
log_info "운영 데이터베이스 마이그레이션을 실행합니다..."
python manage.py migrate

# 캐시 클리어
log_info "캐시를 클리어합니다..."
python manage.py shell -c "
try:
    from django.core.cache import cache
    cache.clear()
    print('✅ 캐시가 클리어되었습니다.')
except Exception as e:
    print(f'⚠️ 캐시 클리어 실패: {e}')
"

# 운영환경 슈퍼유저 생성 안내
log_warning "운영환경에서는 수동으로 슈퍼유저를 생성하세요:"
echo "python manage.py createsuperuser"

# 보안 체크 재실행
log_info "최종 보안 설정을 확인합니다..."
python manage.py check --deploy --verbosity=2

echo ""
log_success "🎉 FabLink 운영환경 배포가 완료되었습니다!"
echo ""
echo -e "${YELLOW}⚠️ 배포 후 확인 사항:${NC}"
echo "   1. .env 파일의 ALLOWED_HOSTS 도메인 설정"
echo "   2. 이메일 SMTP 설정 확인"
echo "   3. AWS S3 파일 저장소 설정"
echo "   4. SSL 인증서 설정"
echo "   5. 방화벽 및 보안 그룹 설정"
echo ""
echo -e "${BLUE}🚀 웹 서버 실행 (Gunicorn):${NC}"
echo "   gunicorn fablink_project.wsgi:application --bind 0.0.0.0:8000"
echo ""
echo -e "${BLUE}🔧 Nginx 설정 예시:${NC}"
echo "   upstream django {"
echo "       server 127.0.0.1:8000;"
echo "   }"
echo ""