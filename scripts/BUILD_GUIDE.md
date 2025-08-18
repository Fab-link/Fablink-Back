# FabLink Backend 빌드 가이드

FabLink Backend 프로젝트의 다양한 빌드 시나리오를 위한 `build.sh` 스크립트 사용 가이드입니다.

## 🚀 빠른 시작

```bash
# 기본 사용법
./scripts/build.sh [환경] [빌드타입] [옵션]

# 예시
./scripts/build.sh local normal        # 로컬 일반 빌드
./scripts/build.sh local model         # 로컬 모델 변경 빌드
./scripts/build.sh local rebuild       # 로컬 DB 완전 재생성
```

## 📋 빌드 타입별 상세 가이드

### 1. 🔨 일반 빌드 (normal)

**언제 사용하나요?**
- 코드 로직 변경 후
- 새로운 기능 추가 후
- 버그 수정 후
- 의존성 패키지 업데이트 후

**수행 작업:**
- 의존성 패키지 업데이트
- 기존 마이그레이션 적용
- 정적 파일 수집
- 테스트 실행

```bash
# 기본 일반 빌드
./scripts/build.sh local normal

# 테스트 제외하고 빌드
./scripts/build.sh local normal --skip-test

# 의존성 설치 제외하고 빌드
./scripts/build.sh local normal --skip-deps
```

### 2. 🗄️ 모델 변경 빌드 (model)

**언제 사용하나요?**
- Django 모델 필드 추가/수정/삭제
- 새로운 모델 생성
- 모델 관계 변경
- Meta 옵션 변경

**수행 작업:**
- 마이그레이션 파일 생성
- 마이그레이션 적용
- 마이그레이션 상태 확인
- 선택적 데이터 삭제 (--flush 옵션)

#### 2-1. 기본 모델 빌드

```bash
# 모든 앱의 모델 변경사항 적용
./scripts/build.sh local model

# 특정 앱만 마이그레이션
./scripts/build.sh local model --app accounts
./scripts/build.sh local model --app manufacturing
```

#### 2-2. 데이터 삭제 후 모델 빌드 (--flush 옵션)

**언제 --flush를 사용하나요?**
- ✅ 필드 삭제 시
- ✅ NOT NULL 제약 조건 추가 시 (기존 데이터가 NULL)
- ✅ 호환되지 않는 필드 타입 변경 시
- ✅ 외래키 관계 변경으로 데이터 무결성 문제 발생 시

**언제 --flush가 불필요한가요?**
- ❌ 새 필드 추가 (nullable=True 또는 default 값 있음)
- ❌ 새 모델 추가
- ❌ 인덱스 추가/제거
- ❌ Meta 옵션 변경

```bash
# 데이터 삭제 후 모든 앱 마이그레이션
./scripts/build.sh local model --flush

# 특정 앱 데이터 삭제 후 마이그레이션
./scripts/build.sh local model --app accounts --flush

# ⚠️ 운영환경에서는 --flush 사용 불가
./scripts/build.sh prod model --flush  # ❌ 에러 발생
```

### 3. 🔥 완전 재생성 빌드 (rebuild)

**언제 사용하나요?**
- 모델 구조를 전면적으로 변경할 때
- 마이그레이션 파일이 꼬였을 때
- 개발 초기 단계에서 DB 스키마를 자주 변경할 때
- 테스트 환경 초기화가 필요할 때

**⚠️ 주의사항:**
- **모든 데이터가 삭제됩니다**
- **마이그레이션 파일이 모두 삭제됩니다**
- **운영환경에서는 사용할 수 없습니다**

**수행 작업:**
- 기존 마이그레이션 파일 백업
- 마이그레이션 파일 삭제
- 데이터베이스 완전 재생성
- 새 마이그레이션 생성 및 적용
- 기본 데이터 재생성 (슈퍼유저 등)

```bash
# 데이터베이스 완전 재생성
./scripts/build.sh local rebuild

# 개발 서버에서 재생성 (Django 레벨에서만)
./scripts/build.sh dev rebuild

# ⚠️ 운영환경에서는 사용 불가
./scripts/build.sh prod rebuild  # ❌ 에러 발생
```

## 🌍 환경별 특징

### Local 환경
- 테스트 실행: ✅
- 정적 파일 수집: ❌
- --flush 옵션: ✅
- rebuild 옵션: ✅
- 슈퍼유저 자동 재생성: ✅

### Dev 환경
- 테스트 실행: ✅
- 정적 파일 수집: ✅
- --flush 옵션: ✅
- rebuild 옵션: ✅ (Django 레벨에서만)
- 슈퍼유저 자동 재생성: ❌

### Prod 환경
- 테스트 실행: ❌
- 정적 파일 수집: ✅
- --flush 옵션: ❌
- rebuild 옵션: ❌
- 슈퍼유저 자동 재생성: ❌

## 🛠️ 옵션 상세 설명

| 옵션 | 설명 | 사용 가능한 빌드타입 |
|------|------|---------------------|
| `--app APP_NAME` | 특정 앱만 마이그레이션 | model |
| `--flush` | 기존 데이터 삭제 후 빌드 | model |
| `--skip-deps` | 의존성 설치 건너뛰기 | 모든 타입 |
| `--skip-static` | 정적 파일 수집 건너뛰기 | 모든 타입 |
| `--skip-test` | 테스트 실행 건너뛰기 | 모든 타입 |

## 📝 실제 사용 시나리오

### 시나리오 1: 새로운 필드 추가
```python
# models.py
class User(AbstractUser):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, null=True, blank=True)  # 새 필드 추가
```

```bash
# flush 불필요 (nullable=True)
./scripts/build.sh local model
```

### 시나리오 2: 필드 삭제
```python
# models.py
class User(AbstractUser):
    name = models.CharField(max_length=100)
    # phone 필드 삭제
```

```bash
# flush 권장 (데이터 정합성)
./scripts/build.sh local model --flush
```

### 시나리오 3: NOT NULL 제약 추가
```python
# models.py
class User(AbstractUser):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)  # null=True 제거
```

```bash
# flush 필요 (기존 NULL 데이터 때문에 마이그레이션 실패 가능)
./scripts/build.sh local model --flush
```

### 시나리오 4: 특정 앱만 변경
```bash
# accounts 앱의 모델만 변경했을 때
./scripts/build.sh local model --app accounts

# accounts 앱 데이터 삭제 후 마이그레이션
./scripts/build.sh local model --app accounts --flush
```

### 시나리오 5: 개발 초기 단계
```bash
# 모델 구조를 자주 변경하는 개발 초기
./scripts/build.sh local rebuild
```

## 🚨 주의사항

1. **운영환경에서의 제한사항:**
   - `--flush` 옵션 사용 불가
   - `rebuild` 빌드타입 사용 불가
   - 데이터 손실 위험이 있는 모든 작업 금지

2. **백업:**
   - `rebuild` 실행 시 마이그레이션 파일이 자동 백업됨
   - 백업 위치: `backups/migrations/YYYYMMDD_HHMMSS/`

3. **가상환경:**
   - 모든 빌드 작업 전에 가상환경 활성화 필수
   - `source venv/bin/activate`

4. **환경변수:**
   - 해당 환경의 `.env` 파일이 존재해야 함
   - `./scripts/setup_env.sh [환경]` 먼저 실행

## 🔄 일반적인 워크플로우

### 개발 시작 시
```bash
./scripts/setup_env.sh local
./scripts/setup_postgresql_local.sh
./scripts/first_build.sh local
```

### 일반적인 개발 중
```bash
# 코드 변경 후
./scripts/build.sh local normal

# 모델 변경 후
./scripts/build.sh local model

# 복잡한 모델 변경 후
./scripts/build.sh local model --flush
```

### 배포 시
```bash
# 개발 서버 배포
./scripts/build.sh dev normal

# 운영 서버 배포
./scripts/build.sh prod normal --skip-test
```
