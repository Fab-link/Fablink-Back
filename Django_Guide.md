# Django 개발 가이드

이 문서는 Django 프레임워크의 핵심 개념과 우리 프로젝트의 구조를 이해하는 데 도움을 주기 위해 작성되었습니다.

## 목차
1. [Django란 무엇인가?](#1-django란-무엇인가)
2. [프로젝트 구조 설명](#2-프로젝트-구조-설명)
3. [MTV 패턴 이해하기](#3-mtv-패턴-이해하기)
4. [Django 주요 기능 살펴보기](#4-django-주요-기능-살펴보기)
5. [기본 개발 흐름](#5-기본-개발-흐름)
6. [개발 환경 및 실행 방법](#6-개발-환경-및-실행-방법)

---

## 1. Django란 무엇인가?

### Django의 정의
Django는 Python으로 작성된 고수준(high-level) 웹 프레임워크입니다. 복잡하고 데이터베이스 중심의 웹사이트를 빠르고 쉽게 개발할 수 있도록 돕는 것을 목표로 합니다.

### Django의 특징
- **MTV 아키텍처**: Model-Template-View 패턴을 사용하여 코드의 역할을 명확하게 분리하고 재사용성을 높입니다.
- **"Batteries Included"**: 웹 개발에 필요한 대부분의 기능(인증, 관리자 페이지, ORM 등)을 기본적으로 내장하고 있어, 개발자가 핵심 비즈니스 로직에만 집중할 수 있게 해줍니다.
- **보안성**: SQL Injection, XSS(Cross-site scripting), CSRF(Cross-site request forgery) 등 일반적인 웹 보안 위협에 대한 보호 기능을 기본적으로 제공합니다.
- **생산성**: 적은 코드로 많은 것을 할 수 있게 설계되어(DRY: Don't Repeat Yourself 원칙) 개발 속도가 매우 빠릅니다.

### 언제 Django를 사용하는가?
- 복잡한 데이터 모델과 비즈니스 로직을 가진 웹 애플리케이션
- 빠른 프로토타이핑과 개발이 필요한 프로젝트
- 관리자 페이지, 콘텐츠 관리 시스템(CMS) 등이 필요한 경우
- 높은 수준의 보안과 확장성이 요구되는 서비스

---

## 2. 프로젝트 구조 설명

우리 프로젝트(`Fablink-Back`)를 기준으로 Django 프로젝트의 구조를 살펴봅니다.

```
/mnt/c/Users/DSO32/source/Fablink-Back/
├── manage.py
├── fablink_project/  # Django 프로젝트 설정 디렉터리
│   ├── settings/
│   │   ├── base.py
│   │   └── development.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── apps/             # 기능별 앱 디렉터리
    ├── accounts/
    └── manufacturing/
```

### `manage.py`의 역할
Django 프로젝트와 상호작용하는 커맨드라인 유틸리티입니다. 이 파일을 통해 다음과 같은 작업을 수행합니다.
- `runserver`: 개발 서버 실행
- `startapp`: 새로운 앱 생성
- `makemigrations`: 모델 변경사항에 대한 마이그레이션 파일 생성
- `migrate`: 마이그레이션을 데이터베이스에 적용
- `shell`: Django 환경이 설정된 파이썬 셸 실행

### 주요 디렉터리: `project/` vs `app/`
- **프로젝트 (`fablink_project/`)**: 전체 웹사이트의 설정을 담는 컨테이너입니다. 데이터베이스 연결, 설치된 앱 목록, 전체 URL 구성 등 프로젝트 전반의 설정이 이곳에 위치합니다.
- **앱 (`apps/`)**: 특정 기능을 수행하는 재사용 가능한 소프트웨어 단위입니다. 예를 들어, `accounts` 앱은 사용자 인증을, `manufacturing` 앱은 제조 관련 기능을 담당합니다.

### 주요 설정 파일
- **`settings.py` (`fablink_project/settings/base.py`)**: Django 프로젝트의 모든 설정을 담고 있는 핵심 파일입니다. (DB, `INSTALLED_APPS`, `MIDDLEWARE` 등)
- **`urls.py` (`fablink_project/urls.py`)**: 프로젝트 레벨의 URL 라우팅을 담당합니다. 각 앱의 `urls.py` 파일을 이곳에서 포함(include)하여 전체 URL 구조를 완성합니다.
- **`wsgi.py` / `asgi.py`**: 웹 서버와 Django 애플리케이션을 연결하는 진입점(entry-point)입니다. `wsgi`는 동기식, `asgi`는 비동기식 요청을 처리합니다.

---

## 3. MTV 패턴 이해하기

Django는 전통적인 MVC(Model-View-Controller) 패턴을 변형한 **MTV(Model-Template-View)** 아키텍처를 사용합니다.

- **Model (`apps/accounts/models.py`)**: 데이터의 구조를 정의합니다. Python 클래스로 모델을 정의하면, Django ORM이 이를 데이터베이스 테이블로 변환하고 관리해줍니다.
- **Template (`*.html`)**: 사용자에게 보여지는 UI(프론트엔드)를 담당합니다. Django 템플릿 언어를 사용하여 동적인 데이터를 HTML에 렌더링할 수 있습니다.
- **View (`apps/accounts/views.py`)**: 실질적인 비즈니스 로직을 처리합니다. HTTP 요청을 받아 Model을 통해 데이터를 조회/처리하고, 그 결과를 Template에 전달하여 사용자에게 응답을 반환합니다.
- **URLConf (`urls.py`)**: URL과 View를 연결하는 라우팅 시스템입니다. 특정 URL로 요청이 들어왔을 때 어떤 View 함수를 실행할지 정의합니다.

---

## 4. Django 주요 기능 살펴보기

### Admin 페이지
Django의 가장 강력한 기능 중 하나입니다. `admin.py`에 모델을 몇 줄의 코드로 등록하기만 하면, 해당 모델의 데이터를 생성(Create), 조회(Read), 수정(Update), 삭제(Delete)할 수 있는 관리자 페이지가 자동으로 생성됩니다.

### ORM (Object-Relational Mapping)
SQL 쿼리를 직접 작성하지 않고, Python 객체와 메소드를 사용하여 데이터베이스와 상호작용할 수 있게 해주는 기능입니다.
```python
# SQL: SELECT * FROM users WHERE name = 'Alice';
# Django ORM:
from apps.accounts.models import User
users = User.objects.filter(name='Alice')
```

### Form 처리
HTML 폼 생성, 유효성 검사, 데이터 처리를 쉽게 할 수 있는 `Form` 클래스를 제공합니다. 이를 통해 코드 중복을 줄이고 보안을 강화할 수 있습니다.

### 인증/권한 시스템
사용자 회원가입, 로그인, 로그아웃, 비밀번호 관리 등 견고한 인증 시스템을 기본으로 제공합니다. 또한, 사용자의 권한을 그룹별 또는 개별적으로 제어할 수 있는 권한 시스템도 내장되어 있습니다.

---

## 5. 기본 개발 흐름

새로운 기능을 추가하는 일반적인 과정입니다.

1.  **앱 생성**: `python manage.py startapp <앱이름>` 명령어로 새로운 기능 단위를 위한 앱을 생성합니다.
2.  **모델 정의**: `models.py`에 데이터의 구조를 Python 클래스로 정의합니다.
3.  **마이그레이션**:
    - `python manage.py makemigrations`: 모델의 변경사항을 감지하여 마이그레이션 파일(`0001_initial.py` 등)을 생성합니다.
    - `python manage.py migrate`: 생성된 마이그레이션 파일을 실제 데이터베이스에 적용하여 테이블을 생성하거나 변경합니다.
4.  **URL 연결 및 뷰 작성**:
    - `views.py`에 비즈니스 로직을 담은 함수나 클래스를 작성합니다.
    - `urls.py`에 특정 URL 패턴과 방금 작성한 View를 연결합니다.
5.  **템플릿과 연결** (API 서버의 경우 생략될 수 있음): View에서 처리한 데이터를 보여줄 HTML 템플릿을 작성하고, View가 이 템플릿을 렌더링하여 사용자에게 반환하도록 설정합니다.

---

## 6. 개발 환경 및 실행 방법

### 가상환경 관리
프로젝트는 `venv/` 라는 가상환경(Virtual Environment)을 사용합니다. 이를 통해 프로젝트별로 독립된 Python 라이브러리 버전을 관리할 수 있습니다.
- **활성화**: `source venv/bin/activate` (Linux/macOS)
- **비활성화**: `deactivate`

### 의존성 설치
`requirements/` 폴더에 환경별로 필요한 라이브러리 목록이 정의되어 있습니다.
- **개발 환경용 설치**: `pip install -r requirements/dev.txt`

### DB 설정
`fablink_project/settings/development.py` 파일의 `DATABASES` 항목에서 개발용 데이터베이스 설정을 확인할 수 있습니다. 기본적으로는 간편한 `SQLite`를 사용하거나, `PostgreSQL` 등 외부 DB와 연동하여 사용합니다.

### 개발 서버 실행
다음 명령어를 실행하면 로컬에서 개발용 웹 서버가 실행됩니다.
```bash
python manage.py runserver
```
기본적으로 `http://127.0.0.1:8000/` 주소에서 애플리케이션을 확인할 수 있습니다.
