# FabLink Backend 🚀

AI 기반 맞춤형 의류 제작 플랫폼 FabLink의 Django REST API 서버입니다.

## 📌 목차
1. [환경별 설정 가이드](#-환경별-설정-가이드)
2. [빌드 가이드](#-빌드-가이드)
3. [새 기능 개발 가이드](#-새-기능-개발-가이드)

## 🔧 환경별 설정 가이드

### 📋 **환경별 설정 관리 전략**

| 환경 | 설정 방식 | 환경 결정 | 관리 도구 | 용도 |
|------|-----------|-----------|-----------|------|
| **Local** | `.env.local` 파일 | 기본값 | `setup_env.sh` | 로컬 개발 |
| **Dev** | ConfigMap + Secret | Docker 빌드 시 고정 | Kubernetes | 개발 서버 |
| **Prod** | ConfigMap + Secret | Docker 빌드 시 고정 | Kubernetes | 운영 서버 |

### 🎯 **핵심 개념**

#### **환경 결정 방식**
- **Local**: `DJANGO_ENV=local` (기본값)
- **Dev**: Docker 빌드 시 `--build-arg ENV=dev` → `DJANGO_ENV=dev` 고정
- **Prod**: Docker 빌드 시 `--build-arg ENV=prod` → `DJANGO_ENV=prod` 고정

#### **설정 소스**
- **Local**: `.env.local` 파일 → 환경변수 → Django 설정
- **Dev/Prod**: Kubernetes ConfigMap/Secret → 환경변수 → Django 설정

### 공통 준비사항

```bash
# 1. 저장소 클론
git clone https://github.com/your-username/Fablink-Back.git
cd Fablink-Back

# 2. 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
```

### 환경별 초기 설정

#### 로컬 환경 설정 (파일 기반)
```bash
# 1. 환경변수 설정 (.env.local 파일 생성)
./scripts/setup_env.sh
# => .env.local 파일 생성
# => 로컬 PostgreSQL 설정
# => 개발 편의성 제공

# 2. PostgreSQL 설치 및 DB 설정
./scripts/setup_postgresql_local.sh
# => PostgreSQL 설치 (없는 경우)
# => 로컬 DB 및 사용자 생성
# => 기본 DB: fablink_local_db
# => 기본 사용자: fablink_user

# 3. 최초 빌드 실행
./scripts/first_build.sh local
# => 패키지 설치
# => DB 마이그레이션
# => 기본 관리자 계정 생성
```

#### 개발 서버 환경 설정 (Kubernetes 기반)
```bash
# 1. Docker 이미지 빌드 (환경 고정)
docker buildx build --platform linux/amd64,linux/arm64 \
  --build-arg ENV=dev \
  -t 853963783084.dkr.ecr.ap-northeast-2.amazonaws.com/fablink-backend-dev:latest \
  --push .
# => DJANGO_ENV=dev로 고정된 이미지 생성

# 2. Kubernetes 배포
kubectl apply -k kubernetes/environments/dev/
# => ConfigMap으로 환경변수 주입
# => Secret으로 민감 정보 주입
# => 자동 DB 마이그레이션
```

#### 운영 서버 환경 설정 (Kubernetes 기반)
```bash
# 1. Docker 이미지 빌드 (환경 고정)
docker buildx build --platform linux/amd64,linux/arm64 \
  --build-arg ENV=prod \
  -t 853963783084.dkr.ecr.ap-northeast-2.amazonaws.com/fablink-backend-prod:latest \
  --push .
# => DJANGO_ENV=prod로 고정된 이미지 생성

# 2. Kubernetes 배포
kubectl apply -k kubernetes/environments/prod/
# => 운영용 ConfigMap/Secret
# => 보안 강화 설정
# => 프로덕션 최적화
```

### 🔍 **환경 감지 및 설정 로드**

시스템이 자동으로 환경을 감지하고 적절한 설정을 로드합니다:

#### **로컬 환경 (파일 기반)**
```python
# fablink_project/settings/__init__.py
🌍 Django 환경: local (Docker 빌드 시 고정)
💻 로컬 환경 - .env 파일 로드
🔧 환경변수 파일 로드됨: .env.local
📦 설정 로드 완료
```

#### **Kubernetes 환경 (ConfigMap/Secret)**
```python
# fablink_project/settings/__init__.py  
🌍 Django 환경: dev (Docker 빌드 시 고정)
🚀 DEV 환경 - ConfigMap/Secret 사용
📦 설정 로드 완료
```

## 🚀 빌드 가이드

### 빌드 타입 개요

| 빌드 타입 | 설명 | 사용 시나리오 |
|-----------|------|---------------|
| normal | 일반 빌드 | 코드 수정 후 |
| model | 모델 변경 빌드 | DB 모델 변경 시 |
| rebuild | DB 재구성 빌드 | DB 완전 초기화 필요 시 |

### 일반 빌드 (normal)

코드 수정 후 일반적인 빌드를 실행할 때 사용합니다.

```bash
# 로컬 환경만 지원 (dev/prod는 Docker 이미지 사용)
./scripts/build.sh local normal
```

### 모델 변경 빌드 (model)

Django 모델 변경 시 사용하며, 여러 옵션을 제공합니다.

```bash
# 1. 전체 앱 마이그레이션
./scripts/build.sh local model

# 2. 특정 앱만 마이그레이션
./scripts/build.sh local model --app accounts

# 3. 데이터 삭제 후 마이그레이션
./scripts/build.sh local model --flush
```

#### 모델 변경 시나리오별 가이드

1. **새 필드 추가** (기존 데이터 유지)
   ```python
   # models.py
   class User(AbstractUser):
       name = models.CharField(max_length=100)
       phone = models.CharField(max_length=20, null=True)  # 새 필드
   ```
   ```bash
   ./scripts/build.sh local model  # flush 불필요
   ```

2. **필수 필드 추가** (기존 데이터 삭제 필요)
   ```python
   # models.py
   class User(AbstractUser):
       phone = models.CharField(max_length=20)  # 필수 필드
   ```
   ```bash
   ./scripts/build.sh local model --flush
   ```

### DB 재구성 빌드 (rebuild)

데이터베이스를 완전히 초기화해야 할 때 사용합니다.

```bash
# ⚠️ 주의: 모든 데이터가 삭제됩니다!
./scripts/build.sh local rebuild
```

## 🛠 새 기능 개발 가이드

### 새 앱 생성

`create_app.sh` 스크립트를 사용하여 새로운 Django 앱을 생성합니다.

```bash
# 기본 사용법
./scripts/create_app.sh [앱이름] [옵션]

# 예시
./scripts/create_app.sh payments                    # 일반 앱 생성
./scripts/create_app.sh analytics --api-only        # API 전용 앱 생성
./scripts/create_app.sh reviews --no-auto-config    # 수동 설정 앱 생성
```

### 생성되는 앱 구조

```
apps/your_app/
├── __init__.py
├── admin.py              # 관리자 페이지 설정
├── apps.py              # 앱 설정
├── models.py            # 데이터 모델
├── serializers.py       # DRF 시리얼라이저
├── services.py          # 비즈니스 로직
├── permissions.py       # 권한 설정
├── urls.py              # URL 라우팅
├── views.py            # API 뷰
├── viewsets.py         # API ViewSets (--api-only)
├── filters.py          # 필터링 (--api-only)
└── tests/              # 테스트 코드
    ├── __init__.py
    ├── test_models.py
    ├── test_api.py
    └── test_services.py
```

### 옵션 설명

| 옵션 | 설명 | 예시 |
|------|------|------|
| --api-only | API 전용 앱 생성 | ./scripts/create_app.sh payments --api-only |
| --no-auto-config | 자동 설정 건너뛰기 | ./scripts/create_app.sh reviews --no-auto-config |

### 앱 생성 후 작업

1. **모델 정의**
   ```python
   # apps/payments/models.py
   from django.db import models
   
   class Payment(models.Model):
       amount = models.DecimalField(max_digits=10, decimal_places=2)
       # ... 필요한 필드 추가
   ```

2. **마이그레이션 생성 및 적용**
   ```bash
   ./scripts/build.sh local model --app payments
   ```

3. **API 구현**
   ```python
   # apps/payments/views.py 또는 viewsets.py
   from rest_framework import viewsets
   from .models import Payment
   from .serializers import PaymentSerializer
   
   class PaymentViewSet(viewsets.ModelViewSet):
       queryset = Payment.objects.all()
       serializer_class = PaymentSerializer
   ```

4. **URL 설정**
   ```python
   # apps/payments/urls.py
   from django.urls import path, include
   from rest_framework.routers import DefaultRouter
   from . import viewsets
   
   router = DefaultRouter()
   router.register(r'payments', viewsets.PaymentViewSet)
   
   urlpatterns = [
       path('', include(router.urls)),
   ]
   ```

### 테스트 작성

```python
# apps/payments/tests/test_api.py
from rest_framework.test import APITestCase
from django.urls import reverse

class PaymentAPITest(APITestCase):
    def test_create_payment(self):
        url = reverse('payments-list')
        data = {'amount': '100.00'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 201)
```

## 🔐 환경별 보안 고려사항

### **로컬 환경**
- `.env.local` 파일은 Git에 커밋하지 않음
- 개발 편의성을 위한 간단한 패스워드 사용 가능
- 로컬 데이터베이스 사용

### **개발/운영 환경**
- ConfigMap: 공개 가능한 설정값
- Secret: 민감한 정보 (DB 패스워드, API 키 등)
- AWS Secrets Manager 연동
- IRSA (IAM Roles for Service Accounts) 사용

## ⚠️ 주의사항

1. **환경별 이미지 분리**
   - Dev 이미지: `fablink-backend-dev:latest`
   - Prod 이미지: `fablink-backend-prod:latest`
   - 환경이 Docker 빌드 시 고정되므로 혼용 불가

2. **로컬 환경 작업 시**
   - 가상환경 활성화 상태 확인
   - 최신 코드 동기화 확인
   - 브랜치 확인

3. **환경변수 파일 관리**
   - `.env.local` 파일은 Git에 커밋하지 않음
   - 로컬 환경에서만 `.env` 파일 사용
   - Dev/Prod 환경에서는 ConfigMap/Secret만 사용

4. **설정 변경 시**
   - 로컬: `.env.local` 파일 수정 후 재시작
   - Dev/Prod: ConfigMap/Secret 수정 후 Pod 재시작

## 🔍 환경별 접속 정보

### 로컬 환경
- http://localhost:8000/
- http://localhost:8000/admin/
- http://localhost:8000/api/

### 개발 서버
- https://dev-api.fablink.com/
- https://dev-api.fablink.com/admin/
- https://dev-api.fablink.com/api/

### 운영 서버
- https://api.fablink.com/
- https://api.fablink.com/admin/
- https://api.fablink.com/api/

## 🚀 **배포 및 인프라**

### **환경별 Docker 이미지 빌드**

```bash
# 개발 환경 이미지 빌드
docker buildx build --platform linux/amd64,linux/arm64 \
  --build-arg ENV=dev \
  -t 853963783084.dkr.ecr.ap-northeast-2.amazonaws.com/fablink-backend-dev:latest \
  --push .

# 운영 환경 이미지 빌드 (향후)
docker buildx build --platform linux/amd64,linux/arm64 \
  --build-arg ENV=prod \
  -t 853963783084.dkr.ecr.ap-northeast-2.amazonaws.com/fablink-backend-prod:latest \
  --push .
```

### **Kubernetes 배포**
```bash
# 개발 환경 배포
kubectl apply -k kubernetes/environments/dev/

# 운영 환경 배포 (향후)
kubectl apply -k kubernetes/environments/prod/
```

### **배포 상태 확인**
```bash
# Pod 상태 확인
kubectl get pods -n fablink-dev

# 로그 확인
kubectl logs -f deployment/fablink-backend -n fablink-dev

# 서비스 상태 확인
kubectl get svc -n fablink-dev
```

## 📁 **프로젝트 구조**

```
Fablink-Back/
├── fablink_project/
│   ├── settings/
│   │   ├── __init__.py          # 환경별 분기 로직
│   │   ├── base.py             # Django 핵심 설정
│   │   └── env_loader.py       # 로컬 전용 .env 로더
│   └── wsgi.py
├── kubernetes/
│   ├── base/                   # 공통 매니페스트
│   └── environments/
│       ├── dev/               # 개발 환경 설정
│       └── prod/              # 운영 환경 설정
├── scripts/
│   ├── setup_env.sh           # 로컬 전용 환경 설정
│   ├── build.sh              # 로컬 빌드 스크립트
│   └── create_app.sh         # 앱 생성 스크립트
├── .env.example              # 환경변수 템플릿
├── Dockerfile               # 환경별 이미지 빌드
└── README.md               # 이 파일
```

자세한 인프라 정보는 [kubernetes/README.md](./kubernetes/README.md)를 참조하세요.

