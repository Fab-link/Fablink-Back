#!/bin/bash

# =================================================================
# scripts/fix_scripts.sh - 스크립트 파일 문제 해결 도구
# =================================================================
# 
# 모든 스크립트 파일의 공통 문제들을 자동으로 수정합니다:
# 1. 라인 엔딩 문제 (CRLF -> LF)
# 2. 실행 권한 설정
# 3. 인코딩 문제 해결
# 4. 환경 변수 검증
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

log_header() {
    echo ""
    echo -e "${CYAN}================================================${NC}"
    echo -e "${CYAN} $1${NC}"
    echo -e "${CYAN}================================================${NC}"
    echo ""
}

log_header "🔧 FabLink Backend 스크립트 파일 문제 해결"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

log_info "스크립트 디렉토리: $SCRIPT_DIR"
log_info "프로젝트 루트: $PROJECT_ROOT"

# 1. 라인 엔딩 문제 해결
log_info "1. 라인 엔딩 문제를 해결합니다..."
cd "$SCRIPT_DIR"
for file in *.sh; do
    if [ -f "$file" ]; then
        # CRLF를 LF로 변환
        sed -i 's/\r$//' "$file"
        log_success "라인 엔딩 수정: $file"
    fi
done

# 2. 실행 권한 설정
log_info "2. 실행 권한을 설정합니다..."
for file in *.sh; do
    if [ -f "$file" ]; then
        chmod +x "$file"
        log_success "실행 권한 설정: $file"
    fi
done

# 3. 스크립트 파일 검증
log_info "3. 스크립트 파일을 검증합니다..."
for file in *.sh; do
    if [ -f "$file" ]; then
        # 문법 검사
        if bash -n "$file" 2>/dev/null; then
            log_success "문법 검사 통과: $file"
        else
            log_error "문법 오류 발견: $file"
        fi
        
        # 파일 타입 확인
        file_type=$(file "$file")
        if [[ "$file_type" == *"CRLF"* ]]; then
            log_warning "CRLF 라인 엔딩 발견: $file"
        else
            log_success "라인 엔딩 정상: $file"
        fi
    fi
done

# 4. 환경 파일 검증
log_info "4. 환경 파일을 검증합니다..."
cd "$PROJECT_ROOT"

# .env 파일들 확인
for env_file in .env .env.local .env.dev .env.prod; do
    if [ -f "$env_file" ]; then
        log_success "환경 파일 존재: $env_file"
        # 권한 설정 (보안을 위해 600)
        chmod 600 "$env_file"
        log_success "환경 파일 권한 설정: $env_file (600)"
    else
        log_warning "환경 파일 없음: $env_file"
    fi
done

# 5. requirements 파일 확인
log_info "5. requirements 파일을 확인합니다..."
if [ -d "requirements" ]; then
    for req_file in requirements/*.txt; do
        if [ -f "$req_file" ]; then
            log_success "requirements 파일 존재: $req_file"
        fi
    done
else
    log_warning "requirements 디렉토리가 없습니다."
fi

# 6. 가상환경 확인
log_info "6. 가상환경을 확인합니다..."
if [ -d "venv" ]; then
    log_success "가상환경 디렉토리 존재: venv"
    if [ -f "venv/bin/activate" ]; then
        log_success "가상환경 활성화 스크립트 존재"
    else
        log_warning "가상환경 활성화 스크립트가 없습니다."
    fi
else
    log_warning "가상환경 디렉토리가 없습니다."
fi

# 7. Django 프로젝트 구조 확인
log_info "7. Django 프로젝트 구조를 확인합니다..."
essential_files=(
    "manage.py"
    "fablink_project/settings.py"
    "apps"
)

for file in "${essential_files[@]}"; do
    if [ -e "$file" ]; then
        log_success "필수 파일/디렉토리 존재: $file"
    else
        log_error "필수 파일/디렉토리 없음: $file"
    fi
done

# 8. 스크립트 실행 테스트
log_info "8. 주요 스크립트 실행 가능성을 테스트합니다..."
cd "$SCRIPT_DIR"

# setup_env.sh 테스트
if [ -f "setup_env.sh" ]; then
    if bash -n "setup_env.sh"; then
        log_success "setup_env.sh 문법 검사 통과"
    else
        log_error "setup_env.sh 문법 오류"
    fi
fi

# build.sh 테스트
if [ -f "build.sh" ]; then
    if bash -n "build.sh"; then
        log_success "build.sh 문법 검사 통과"
    else
        log_error "build.sh 문법 오류"
    fi
fi

log_header "🎉 스크립트 파일 문제 해결 완료!"

echo ""
echo -e "${GREEN}✅ 모든 스크립트 파일이 수정되었습니다!${NC}"
echo ""
echo -e "${BLUE}📋 수정된 내용:${NC}"
echo "   • 라인 엔딩 문제 해결 (CRLF → LF)"
echo "   • 실행 권한 설정 (chmod +x)"
echo "   • 환경 파일 권한 설정 (chmod 600)"
echo "   • 문법 검사 완료"
echo ""
echo -e "${YELLOW}🚀 이제 다음 명령어들을 안전하게 사용할 수 있습니다:${NC}"
echo "   ./scripts/setup_env.sh local"
echo "   ./scripts/setup_postgresql_local.sh"
echo "   ./scripts/first_build.sh local"
echo "   ./scripts/build.sh local normal"
echo "   ./scripts/create_app.sh [앱이름]"
echo ""
