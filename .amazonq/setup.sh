#!/bin/bash

# Amazon Q 설정 스크립트 for FabLink Backend
# 다른 PC에서 동일한 환경을 구성하기 위한 스크립트

set -e

echo "🚀 FabLink Backend - Amazon Q 환경 설정을 시작합니다..."

# 프로젝트 루트 확인
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "📁 프로젝트 루트: $PROJECT_ROOT"

# Amazon Q CLI 설치 확인
if ! command -v q &> /dev/null; then
    echo "❌ Amazon Q CLI가 설치되지 않았습니다."
    echo "다음 링크에서 설치해주세요: https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/command-line-getting-started-installing.html"
    exit 1
fi

echo "✅ Amazon Q CLI 버전: $(q --version)"

# AWS CLI 설치 확인
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI가 설치되지 않았습니다."
    echo "AWS CLI를 먼저 설치해주세요."
    exit 1
fi

echo "✅ AWS CLI 설치됨"

# AWS 프로필 설정 확인
echo "🔐 AWS 자격증명을 설정합니다..."
echo "다음 정보를 입력해주세요:"

read -p "AWS Access Key ID: " AWS_ACCESS_KEY_ID
read -s -p "AWS Secret Access Key: " AWS_SECRET_ACCESS_KEY
echo

# devops 프로필 설정
aws configure set aws_access_key_id "$AWS_ACCESS_KEY_ID" --profile devops
aws configure set aws_secret_access_key "$AWS_SECRET_ACCESS_KEY" --profile devops
aws configure set region ap-northeast-2 --profile devops
aws configure set output json --profile devops

echo "✅ AWS devops 프로필이 설정되었습니다."

# AWS 연결 테스트
echo "🔍 AWS 연결을 테스트합니다..."
if aws sts get-caller-identity --profile devops > /dev/null 2>&1; then
    echo "✅ AWS 연결 성공"
    aws sts get-caller-identity --profile devops
else
    echo "❌ AWS 연결 실패. 자격증명을 확인해주세요."
    exit 1
fi

# Amazon Q 컨텍스트 디렉토리 생성
AMAZONQ_CONFIG_DIR="$HOME/.config/amazonq"
mkdir -p "$AMAZONQ_CONFIG_DIR/context"
mkdir -p "$AMAZONQ_CONFIG_DIR/profiles"

# 프로젝트 컨텍스트를 Amazon Q에 등록
echo "📋 프로젝트 컨텍스트를 설정합니다..."

# 컨텍스트 파일들을 Amazon Q 설정에 복사
if [ -f "$PROJECT_ROOT/.amazonq/context.md" ]; then
    cp "$PROJECT_ROOT/.amazonq/context.md" "$AMAZONQ_CONFIG_DIR/context/fablink-backend.md"
    echo "✅ 프로젝트 컨텍스트가 등록되었습니다."
fi

# 환경변수 설정 제안
echo ""
echo "🔧 다음 환경변수를 ~/.bashrc 또는 ~/.zshrc에 추가하는 것을 권장합니다:"
echo ""
echo "export FABLINK_PROJECT_ROOT=\"$PROJECT_ROOT\""
echo "export AWS_PROFILE=devops"
echo "export AWS_DEFAULT_REGION=ap-northeast-2"
echo ""

# kubectl 설정 (EKS 클러스터 접근)
echo "☸️  EKS 클러스터 접근을 설정합니다..."
if command -v kubectl &> /dev/null; then
    aws eks update-kubeconfig --region ap-northeast-2 --name fablink-cluster-dev --profile devops
    echo "✅ kubectl이 EKS 클러스터에 연결되었습니다."
else
    echo "⚠️  kubectl이 설치되지 않았습니다. 필요시 설치해주세요."
fi

echo ""
echo "🎉 Amazon Q 환경 설정이 완료되었습니다!"
echo ""
echo "📚 다음 단계:"
echo "1. Amazon Q CLI에 로그인: q auth login (필요시)"
echo "2. 프로젝트 디렉토리에서 q chat 실행"
echo "3. 컨텍스트가 자동으로 로드됩니다"
echo ""
echo "🔗 유용한 명령어:"
echo "- q chat                    # Amazon Q 채팅 시작"
echo "- kubectl get pods -n fablink-dev  # 개발 환경 Pod 확인"
echo "- aws apigateway get-rest-apis --profile devops  # API Gateway 확인"
