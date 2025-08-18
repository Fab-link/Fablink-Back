# Amazon Q Context for FabLink Backend

이 파일은 FabLink Backend 프로젝트의 Amazon Q 컨텍스트를 정의합니다.

## 📁 프로젝트 구조

```
Fablink-Back/                           # 프로젝트 루트
├── .amazonq/                           # Amazon Q 설정 (이 디렉토리)
│   ├── context.md                      # 프로젝트 컨텍스트
│   └── setup.sh                        # 설정 스크립트
├── kubernetes/                         # K8s 매니페스트
│   ├── environments/dev/               # 개발 환경
│   └── environments/prod/              # 운영 환경
├── apps/                               # Django 앱들
├── scripts/                            # 빌드/배포 스크립트
└── README.md                           # 프로젝트 메인 문서
```

## 🔧 주요 컨텍스트 파일들

### 1. 인프라 관련
- `kubernetes/environments/dev/README.md` - 개발 환경 설정
- `kubernetes/environments/prod/README.md` - 운영 환경 설정
- `kubernetes/README.md` - K8s 배포 가이드

### 2. 개발 관련
- `README.md` - 프로젝트 전체 가이드
- `scripts/` - 빌드 및 배포 스크립트들

## 🌐 AWS 리소스 정보

### 개발 환경 (현재 상태)
- **계정**: 853963783084
- **리전**: ap-northeast-2
- **API Gateway**: 8wwdg03sr6 (fablink-dev-api) ✅
- **NLB**: fablink-dev-nlb ✅
- **EKS**: fablink-cluster-dev ✅
- **Aurora**: fablink-aurora-cluster ✅
- **DynamoDB**: fablink-dynamodb-dev ✅

### 🚨 현재 문제점
1. **NLB Target Group 헬스체크 실패** - EKS에 백엔드 앱 미배포
2. **API Gateway → NLB VPC Link 미설정**
3. **Django 헬스체크 엔드포인트 미구현**
4. **ECR 리포지토리 및 Docker 이미지 없음**

### 운영 환경
- 현재 구축되지 않음 (설계 단계)

## 📋 자주 사용하는 명령어

```bash
# 개발 환경 배포
kubectl apply -k kubernetes/environments/dev/

# AWS 리소스 확인
aws sts get-caller-identity --profile devops
aws apigateway get-rest-apis --profile devops --region ap-northeast-2

# 헬스체크
curl https://8wwdg03sr6.execute-api.ap-northeast-2.amazonaws.com/health/
```

## 🔄 다른 PC에서 설정하기

1. 이 프로젝트를 클론
2. `.amazonq/setup.sh` 실행
3. AWS 자격증명 설정
4. Amazon Q CLI 설치 및 로그인
