# fablink_project/settings/production.py
from .base import *
import dj_database_url

# 운영환경 보안 설정
DEBUG = False
ALLOWED_HOSTS = [
    '*',  # 임시로 모든 호스트 허용 (나중에 실제 도메인으로 변경)
    # 'your-production-domain.com',
    # 'www.your-production-domain.com',
    # AWS ELB나 CloudFlare 등의 IP도 추가
]

# 운영환경 데이터베이스
DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.getenv('DB_NAME', 'fablink'),
        'USER': os.getenv('DB_USER', 'fablinkadmin'),
        'PASSWORD': os.getenv('DB_PASSWORD'),  # 필수값
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'OPTIONS': {
            'sslmode': 'require',  # 운영환경에서는 SSL 필수
            'client_encoding': 'UTF8',
        },
        'CONN_MAX_AGE': int(os.getenv('DB_CONN_MAX_AGE', '300')),  # 연결 풀링
        'CONN_HEALTH_CHECKS': os.getenv('DB_CONN_HEALTH_CHECKS', 'True').lower() == 'true',
        'TEST': {
            'NAME': f"test_{os.getenv('DB_NAME', 'fablink')}",
        }
    }
}

# DATABASE_URL 환경변수 지원 (Heroku, Railway 등)
if 'DATABASE_URL' in os.environ:
    DATABASES['default'] = dj_database_url.parse(os.environ['DATABASE_URL'])
    DATABASES['default']['OPTIONS'] = {
        'sslmode': 'require',
    }

# 보안 설정 (임시로 완화)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_SECONDS = 31536000
# SECURE_REDIRECT_EXEMPT = []
# SECURE_SSL_REDIRECT = True
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True

# 운영환경용 이메일 설정
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@fablink.com')

# 정적 파일 설정 (S3 사용 예시)
if os.getenv('USE_S3', 'False').lower() == 'true':
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'ap-northeast-2')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'
    
    # Static 파일
    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'
    
    # Media 파일
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'

# 캐시 설정 (Redis)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',  # DB 캐시 사용
        'LOCATION': 'cache_table',
        # 'BACKEND': 'django_redis.cache.RedisCache',
        # 'LOCATION': os.getenv('REDIS_URL', 'redis://localhost:6379/1'),
        # 'OPTIONS': {
        #     'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        #     'CONNECTION_POOL_KWARGS': {
        #         'ssl_cert_reqs': None,
        #     },
        # }
    }
}

# 세션 저장소
SESSION_ENGINE = 'django.contrib.sessions.backends.db'  # 임시로 DB 사용
# SESSION_CACHE_ALIAS = 'default'

# Celery 설정 (운영환경)
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# 로깅 설정 (운영환경용)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/fablink/django.log',
            'maxBytes': 1024*1024*15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],  # 임시로 콘솔만 사용
        'level': 'INFO',
    },
    'loggers': {
        'django.db.backends': {
            'level': 'ERROR',
            'handlers': ['console'],
            'propagate': False,
        },
    },
}

# CORS 설정 (운영환경)
CORS_ALLOWED_ORIGINS = [
    # "https://your-frontend-domain.com",
    # "https://www.your-frontend-domain.com",
]
CORS_ALLOW_ALL_ORIGINS = True  # 임시로 모든 오리진 허용
CORS_ALLOW_CREDENTIALS = True

# 모니터링 및 성능 설정
if 'SENTRY_DSN' in os.environ:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    
    sentry_sdk.init(
        dsn=os.getenv('SENTRY_DSN'),
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
        ],
        traces_sample_rate=0.1,
        send_default_pii=True
    )
