# fablink_project/settings/local.py
from .base import *

# 로컬 개발환경 디버그 모드
DEBUG = True

# 로컬 개발환경용 데이터베이스 (로컬 PostgreSQL)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'fablink_local_db'),
        'USER': os.getenv('DB_USER', 'fablink_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'local123'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'OPTIONS': {
            'client_encoding': 'UTF8',
        },
        'TEST': {
            'NAME': 'test_fablink_local_db',
        }
    }
}

# 로컬 개발환경용 이메일 백엔드 (콘솔 출력)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# 로컬 개발환경에서만 사용할 추가 앱
INSTALLED_APPS += [
    'django_extensions',  # 개발 도구
    'debug_toolbar',      # 디버그 툴바
]

# Debug Toolbar 미들웨어 추가
MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']

# 로컬 개발환경 전용 설정
INTERNAL_IPS = [
    '127.0.0.1',
    'localhost',
]

# 로컬 개발환경용 미디어/스태틱 파일 (로컬 저장)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STATIC_URL = '/static/'
STATICFILES_DIRS = []  # 빈 리스트로 설정

# 로컬 개발환경용 CORS 설정
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# CORS 설정 완화 (로컬 개발용)
CORS_ALLOW_ALL_ORIGINS = True

# 로컬 개발환경용 로깅
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
