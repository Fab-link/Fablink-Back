#!/bin/bash
# ==============================================================
# scripts/setup_mongodb.sh - 로컬/WSL Ubuntu에서 MongoDB 설치/설정
# ==============================================================

set -euo pipefail

# 색상 및 로그 함수 (다른 스크립트와 일관)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error()   { echo -e "${RED}❌ $1${NC}"; }

# 인자 사용 금지: 모든 설정은 .env.local에서 읽음
if [[ $# -gt 0 ]]; then
  log_error "본 스크립트는 옵션/인자를 지원하지 않습니다. 설정은 .env.local에서 읽습니다."
  exit 1
fi

# 프로젝트 루트 및 환경파일(.env.local 고정)
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
PROJECT_ROOT="${SCRIPT_DIR}/.."
ENV_FILE="${PROJECT_ROOT}/.env.local"

if [[ ! -f "$ENV_FILE" ]]; then
  log_error ".env.local이 없습니다: ${ENV_FILE}"
  echo "➡️  ./scripts/setup_env.sh local 로 먼저 환경파일을 생성하세요."
  exit 1
fi

# .env.local 로드
log_info ".env.local에서 Mongo 설정을 로드합니다: ${ENV_FILE}"
set -a
source "$ENV_FILE"
set +a

# 기본값 처리 및 URI 파싱
MONGODB_URI="${MONGODB_URI:-mongodb://localhost:9000}"
DB_NAME="${MONGODB_DB:-fablink}"
ORDERS_COLL="${MONGODB_COLLECTION_ORDERS:-orders}"

# mongodb://[auth@]host:port[/...]
_URI_NO_SCHEME="${MONGODB_URI#mongodb://}"
_AFTER_AUTH="${_URI_NO_SCHEME#*@}"
_HOSTPORT="${_AFTER_AUTH%%/*}"
URI_HOST="${_HOSTPORT%%:*}"
_PORT_CANDIDATE="${_HOSTPORT##*:}"

PORT=9000
if [[ "${_PORT_CANDIDATE}" =~ ^[0-9]+$ ]]; then
  PORT="${_PORT_CANDIDATE}"
fi
if [[ -z "${URI_HOST}" ]]; then
  URI_HOST="localhost"
fi

log_info "MongoDB 설치/설정을 시작합니다 (host=${URI_HOST}, port=${PORT}, db=${DB_NAME})..."

# 1) Ubuntu codename 탐지
if command -v lsb_release >/dev/null 2>&1; then
  UBUNTU_CODENAME=$(lsb_release -sc)
else
  UBUNTU_CODENAME="jammy"
fi
log_info "Ubuntu codename: ${UBUNTU_CODENAME}"

# MongoDB series 결정: noble(24.04) 기본 8.0, 그 외 7.0 (고정 정책)
if [[ "$UBUNTU_CODENAME" == "noble" ]]; then
  MONGO_SERIES="8.0"
else
  MONGO_SERIES="7.0"
fi
log_info "선택된 MongoDB series: ${MONGO_SERIES}"

# 2) MongoDB 7.0 저장소 추가 및 설치
if ! command -v mongod >/dev/null 2>&1; then
  log_info "MongoDB 패키지를 설치합니다..."
  # 이전 실행에서 남아있을 수 있는 구버전 리포 파일 정리(선택된 series와 다른 항목 삭제)
  REPO_DIR="/etc/apt/sources.list.d"
  if [[ -d "$REPO_DIR" ]]; then
    for f in "$REPO_DIR"/mongodb-org-*.list; do
      # 파일이 존재하고, 현재 series 파일이 아니면 삭제
      if [[ -f "$f" && "$f" != "$REPO_DIR/mongodb-org-${MONGO_SERIES}.list" ]]; then
        log_warning "기존 Mongo 리포 파일 제거: $f"
        sudo rm -f "$f" || true
      fi
    done
  fi
  # GPG 키/리포 파일명은 시리즈와 무관하게 식별 가능하도록 series 포함
  curl -fsSL https://www.mongodb.org/static/pgp/server-${MONGO_SERIES%%.*}.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-${MONGO_SERIES}.gpg --dearmor || true
  echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-${MONGO_SERIES}.gpg ] https://repo.mongodb.org/apt/ubuntu ${UBUNTU_CODENAME}/mongodb-org/${MONGO_SERIES} multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-${MONGO_SERIES}.list >/dev/null
  sudo apt-get update -y
  if ! sudo apt-get install -y mongodb-org mongodb-mongosh; then
    log_warning "패키지 설치 실패. 리포지토리가 없을 수 있습니다. codename=${UBUNTU_CODENAME}, series=${MONGO_SERIES}"
    if [[ "$UBUNTU_CODENAME" == "noble" && "$MONGO_SERIES" == "7.0" ]]; then
      log_info "noble에서 7.0은 미지원일 수 있습니다. 8.0으로 재시도합니다."
      MONGO_SERIES="8.0"
      curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor || true
      echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/8.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list >/dev/null
      sudo apt-get update -y
      sudo apt-get install -y mongodb-org mongodb-mongosh || { log_error "MongoDB 설치 실패. 수동 설치 또는 Docker 사용을 검토하세요."; exit 1; }
    else
      log_error "MongoDB 설치 실패. Docker 사용 또는 수동 설치를 검토하세요."; exit 1
    fi
  fi
  log_success "MongoDB 설치 완료"
else
  log_success "MongoDB가 이미 설치되어 있습니다"
fi

# 3) mongod.conf 백업 및 포트/바인드 설정
CONF=/etc/mongod.conf
log_info "mongod.conf(${CONF})를 설정합니다 (port=${PORT}, bindIp=127.0.0.1)..."
if [[ -f "$CONF" ]]; then
  sudo cp "$CONF" "${CONF}.bak.$(date +%s)"
fi

if ! grep -qE '^net:' "$CONF" 2>/dev/null; then
  printf "\nnet:\n  port: %s\n  bindIp: 127.0.0.1\n" "$PORT" | sudo tee -a "$CONF" >/dev/null
else
  if grep -qE '^\s*port:\s*[0-9]+' "$CONF"; then
    sudo sed -r -i "s/^\s*port:\s*[0-9]+/  port: ${PORT}/" "$CONF"
  else
    sudo awk -v port="$PORT" '{print} /^net:/ {print "  port: " port}' "$CONF" | sudo tee "$CONF.tmp" >/dev/null && sudo mv "$CONF.tmp" "$CONF"
  fi
  if grep -qE '^\s*bindIp:\s*.*' "$CONF"; then
    sudo sed -r -i "s/^\s*bindIp:\s*.*/  bindIp: 127.0.0.1/" "$CONF"
  else
    sudo awk '{print} /^net:/ {print "  bindIp: 127.0.0.1"}' "$CONF" | sudo tee "$CONF.tmp" >/dev/null && sudo mv "$CONF.tmp" "$CONF"
  fi
fi

# 4) 서비스 시작/재시작
log_info "mongod 서비스를 시작/재시작합니다..."
if command -v systemctl >/dev/null 2>&1 && systemctl is-system-running >/dev/null 2>&1; then
  sudo systemctl daemon-reload || true
  sudo systemctl enable mongod || true
  sudo systemctl restart mongod || sudo systemctl start mongod
else
  sudo service mongod restart || sudo service mongod start || true
fi
log_success "mongod 서비스 기동"

# 5) 연결 확인
if command -v mongosh >/dev/null 2>&1; then
  log_info "연결 확인: ${MONGODB_URI}"
  if mongosh "${MONGODB_URI}" --eval 'db.runCommand({ ping: 1 })' >/dev/null 2>&1; then
    log_success "MongoDB ping 성공"
  else
    log_warning "MongoDB ping 실패(서비스 기동 직후 지연일 수 있음). 수동 확인 권장"
  fi
else
  log_warning "mongosh 미설치: ping 스킵"
fi

echo ""; log_success "🎉 MongoDB 설치/설정 완료"
echo -e "${BLUE}📋 요약:${NC}"
echo "   🌐 URI: ${MONGODB_URI}"
echo "   🗄  DB : ${DB_NAME}"
echo "   📦 컬렉션(주문)   : ${ORDERS_COLL}"
echo "   � env 파일: ${ENV_FILE} (.env.local 고정)"
echo ""
echo -e "${YELLOW}🚀 다음 단계:${NC}"
echo "   1) (필요 시) venv 활성화 후 의존성 설치: source venv/bin/activate && pip install -r requirements/local.txt"
echo "   2) (미실행 시) ./scripts/setup_env.sh local 로 .env.local 생성"
echo "   3) python manage.py runserver"
echo ""
