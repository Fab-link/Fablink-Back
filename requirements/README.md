# Requirements 파일 구조

FabLink Backend 프로젝트의 의존성 패키지는 환경별로 분리되어 관리됩니다.

## 📁 파일 구조

```
requirements/
├── base.txt          # 모든 환경에서 공통으로 사용하는 패키지
├── local.txt         # 로컬 개발환경용 패키지
├── dev.txt           # 개발 서버환경용 패키지
├── prod.txt          # 운영환경용 패키지
└── README.md        # 이 파일
```

## 🎯 환경별 특징

### `base.txt` - 공통 패키지
- Django 프레임워크
- 데이터베이스 드라이버 (PostgreSQL)
- REST API 프레임워크
- 기본 유틸리티 패키지

### `local.txt` - 로컬 개발환경
```bash
pip install -r requirements/local.txt
```
- **대상**: 개발자 개인 로컬 환경
- **특징**: 
  - 디버깅 도구 (django-debug-toolbar, ipython)
  - 테스트 도구 (pytest, coverage)
  - 코드 품질 도구 (flake8, black, isort)
  - 개발 편의 도구

### `dev.txt` - 개발 서버환경
```bash
pip install -r requirements/dev.txt
```
- **대상**: 개발팀 공용 개발 서버
- **특징**:
  - 기본 디버깅 도구
  - 테스트 실행 도구
  - API 성능 프로파일링 도구
  - AWS 개발 환경 도구

### `production.txt` - 운영환경
```bash
pip install -r requirements/production.txt
```
- **대상**: 실제 서비스 운영 서버
- **특징**:
  - 웹서버 (Gunicorn)
  - 캐시 시스템 (Redis)
  - 파일 저장소 (AWS S3)
  - 모니터링 도구 (Sentry)
  - 보안 및 성능 최적화 도구

## 🚀 사용법

### 환경별 설치
```bash
# 로컬 개발환경
pip install -r requirements/local.txt

# 개발 서버환경
pip install -r requirements/development.txt

# 운영환경
pip install -r requirements/production.txt
```

### first_build.sh 스크립트 사용
```bash
# 자동으로 환경에 맞는 requirements 파일을 설치
./scripts/first_build.sh local      # local.txt 사용
./scripts/first_build.sh dev        # development.txt 사용
./scripts/first_build.sh prod       # production.txt 사용
```

## 📝 패키지 추가 가이드

### 1. 모든 환경에서 필요한 패키지
→ `base.txt`에 추가

### 2. 로컬 개발에만 필요한 패키지
→ `local.txt`에 추가

### 3. 개발 서버에만 필요한 패키지
→ `development.txt`에 추가

### 4. 운영환경에만 필요한 패키지
→ `production.txt`에 추가

## ⚠️ 주의사항

1. **버전 고정**: 모든 패키지는 정확한 버전을 명시합니다
2. **보안**: 운영환경에는 디버깅 도구를 포함하지 않습니다
3. **성능**: 각 환경에 필요한 최소한의 패키지만 설치합니다
4. **테스트**: 패키지 추가 후 각 환경에서 테스트를 수행합니다

## 🔄 업데이트 프로세스

1. 패키지 추가/수정
2. 해당 환경에서 테스트
3. 버전 고정
4. 다른 환경에 영향 없는지 확인
5. 커밋 및 배포
