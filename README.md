# FabLink Backend 🚀

AI 기반 맞춤형 의류 제작 플랫폼 FabLink의 Django REST API 서버입니다.

## 🚀 빠른 시작

### 1단계: 저장소 클론

```bash
git clone https://github.com/your-username/Fablink-Back.git
cd Fablink-Back
```

### 2단계: 가상환경 설정

```bash
# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
```

### 3.단계: PostgreSQL 설치 및 설정
#### Ubuntu/Debian:
```bash
bashsudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### macOS:
```bash
bashbrew install postgresql
brew services start postgresql
```

### 4단계: 개발 데이터베이스 설정

```bash
# PostgreSQL 설치 및 개발 DB 생성
./scripts/setup_postgresql_dev.sh
```

### 5단계: Django 개발환경 설정

```bash
# 패키지 설치, 마이그레이션, 슈퍼유저 생성
./scripts/setup_dev.sh
```

### 6단계: 개발 서버 실행

```bash
# Django 개발 서버 시작
python manage.py runserver
```

🎉 **성공!** 브라우저에서 다음 주소로 접속하세요:
- **API 서버**: http://localhost:8000/
- **관리자 페이지**: http://localhost:8000/admin/
- **API 문서**: http://localhost:8000/api/

**기본 관리자 계정**: `admin` / `admin123`

## 🔧 로컬 개발환경 설정

### 자동 설정 스크립트 사용 (권장)

```bash
# 1. PostgreSQL 개발 DB 생성
./scripts/setup_postgresql_dev.sh

# 2. Django 개발환경 설정
./scripts/setup_dev.sh

# 3. 개발 서버 실행
python manage.py runserver
```

## 📁 프로젝트 구조

```
fablink-backend/
├── apps/                          # Django 앱들
│   ├── accounts/                  # 사용자 관리
│   ├── core/                      # 공통 기능
│   ├── manufacturing/             # 제조 관리
│   ├── orders/                    # 주문 관리
│   ├── notifications/             # 알림 시스템
│   └── files/                     # 파일 관리
├── fablink_project/               # Django 프로젝트 설정
│   ├── settings/                  # 환경별 설정
│   │   ├── base.py               # 공통 설정
│   │   ├── development.py        # 개발환경
│   │   └── production.py         # 운영환경
│   ├── urls.py                   # 메인 URL 설정
│   └── wsgi.py                   # WSGI 설정
├── scripts/                      # 유틸리티 스크립트
│   ├── setup_postgresql_dev.sh   # 개발 DB 설정
│   ├── setup_dev.sh             # 개발환경 설정
│   ├── backup_db.sh             # DB 백업
│   └── restore_db.sh            # DB 복원
├── static/                      # 정적 파일
├── media/                       # 업로드된 미디어 파일
├── templates/                   # HTML 템플릿
├── requirements/                # 의존성 파일들
│   ├── base.txt                # 공통 패키지
│   ├── development.txt         # 개발환경 패키지
│   └── production.txt          # 운영환경 패키지
├── .env                        # 환경변수 (로컬에만 존재)
├── .env.example               # 환경변수 예시
├── manage.py                  # Django 관리 도구
└── README.md                  # 프로젝트 문서
```

### 주요 앱 설명

#### `apps/accounts/`
- 사용자 인증 및 관리
- 디자이너/제조업체 프로필 관리
- JWT 토큰 인증

#### `apps/manufacturing/`
- 제품 디자인 및 제조 요청 관리
- AI 디자인 분석 결과 저장
- 제조업체 매칭 로직

#### `apps/orders/`
- 주문 및 견적 관리
- 결제 및 정산 처리
- 주문 상태 추적

#### `apps/notifications/`
- 실시간 알림 시스템
- 이메일/SMS 발송
- 알림 히스토리 관리

## 📚 API 문서

### 인증

모든 API는 Token 기반 인증을 사용합니다:

```bash
# 토큰 획득
curl -X POST http://localhost:8000/api/accounts/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin", "password":"admin123"}'

# API 호출 시 헤더에 토큰 포함
curl -H "Authorization: Token your-token-here" \
  http://localhost:8000/api/manufacturing/products/
```

### 주요 엔드포인트

#### 인증 관련
- `POST /api/accounts/login/` - 로그인
- `POST /api/accounts/logout/` - 로그아웃
- `POST /api/accounts/register/` - 회원가입

#### 제조 관리
- `GET /api/manufacturing/products/` - 제품 목록
- `POST /api/manufacturing/products/` - 제품 생성
- `GET /api/manufacturing/orders/` - 제조 주문 목록

#### 주문 관리
- `GET /api/orders/` - 주문 목록
- `POST /api/orders/` - 주문 생성
- `GET /api/orders/{id}/` - 주문 상세

### API 문서 확인

개발 서버 실행 후 다음 주소에서 상세한 API 문서를 확인할 수 있습니다:
- **Django REST Framework Browsable API**: http://localhost:8000/api/

## 🗄️ 데이터베이스 관리

### 백업

```bash
# 개발 DB 백업
./scripts/backup_db.sh dev

# 운영 DB 백업 (운영환경에서만)
./scripts/backup_db.sh prod
```

### 복원

```bash
# 백업 파일 확인
./scripts/restore_db.sh

# 개발 DB 복원
./scripts/restore_db.sh dev backup_filename.sql
```

### 마이그레이션

```bash
# 마이그레이션 파일 생성
python manage.py makemigrations

# 마이그레이션 적용
python manage.py migrate

# 마이그레이션 상태 확인
python manage.py showmigrations
```

## 🚢 배포

### 운영환경 설정

```bash
# 1. 운영 DB 설정
./scripts/setup_postgresql_prod.sh

# 2. 운영환경 Django 설정
./scripts/setup_prod.sh

# 3. Gunicorn으로 서버 실행
gunicorn fablink_project.wsgi:application --bind 0.0.0.0:8000
```

### Docker 배포 (선택사항)

```bash
# Docker 이미지 빌드
docker build -t fablink-backend .

# Docker 컨테이너 실행
docker run -d -p 8000:8000 \
  -e DJANGO_ENV=production \
  --name fablink-backend \
  fablink-backend
```

### 환경별 설정

#### 개발환경
- `DJANGO_ENV=development`
- DEBUG=True
- SQLite/PostgreSQL 로컬 DB

#### 운영환경
- `DJANGO_ENV=production`  
- DEBUG=False
- PostgreSQL (AWS RDS)
- AWS S3 파일 저장소
- SSL/HTTPS 필수

## 🔍 문제해결

### 자주 발생하는 문제들

#### 1. PostgreSQL 연결 오류

**문제**: `connection to server at "localhost" failed`

**해결책**:
```bash
# PostgreSQL 서비스 상태 확인
sudo systemctl status postgresql

# PostgreSQL 서비스 시작
sudo systemctl start postgresql

# 데이터베이스 존재 확인
sudo -u postgres psql -l
```

#### 2. 마이그레이션 오류

**문제**: `django.db.utils.ProgrammingError`

**해결책**:
```bash
# 마이그레이션 초기화
python manage.py migrate --fake-initial

# 또는 마이그레이션 파일 재생성
rm apps/*/migrations/00*.py
python manage.py makemigrations
python manage.py migrate
```

#### 3. 패키지 설치 오류

**문제**: `psycopg2` 설치 실패

**해결책** (Ubuntu/Debian):
```bash
sudo apt install python3-dev libpq-dev
pip install psycopg2-binary
```

#### 4. 권한 오류

**문제**: `permission denied` 스크립트 실행 시

**해결책**:
```bash
# 스크립트 실행 권한 부여
chmod +x scripts/*.sh
```

### 로그 확인

```bash
# Django 로그 확인
tail -f logs/django.log

# PostgreSQL 로그 확인 (Ubuntu)
sudo tail -f /var/log/postgresql/postgresql-14-main.log
```

### 성능 최적화

```bash
# 데이터베이스 연결 확인
python manage.py dbshell

# 쿼리 성능 분석
python manage.py shell
>>> from django.db import connection
>>> print(connection.queries)
```

**FabLink Backend v1.0.0** - AI 기반 맞춤형 의류 제작 플랫폼 🚀
