from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
import time

def api_root(request):
    """API 루트 엔드포인트"""
    return JsonResponse({
        'message': 'FabLink API Server',
        'version': '1.0.0',
        'endpoints': {
            'admin': '/admin/',
            'accounts': '/api/accounts/',
            'manufacturing': '/api/manufacturing/',
        },
        'auth_endpoints': {
            'login': '/api/accounts/login/',
            'logout': '/api/accounts/logout/',
            'designer_register': '/api/accounts/designer/register/',
            'factory_register': '/api/accounts/factory/register/',
            'designer_profile': '/api/accounts/designer/profile/',
            'factory_profile': '/api/accounts/factory/profile/',
        }
    })

def health_check(request):
    """Health Check 엔드포인트 - Liveness Probe용"""
    return JsonResponse({
        'status': 'healthy',
        'timestamp': time.time(),
        'service': 'fablink-backend'
    })

def readiness_check(request):
    """Readiness Check 엔드포인트 - Readiness Probe용"""
    try:
        # 데이터베이스 연결 확인
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        
        db_status = 'connected'
    except Exception as e:
        return JsonResponse({
            'status': 'not_ready',
            'timestamp': time.time(),
            'service': 'fablink-backend',
            'checks': {
                'database': f'error: {str(e)}'
            }
        }, status=503)
    
    return JsonResponse({
        'status': 'ready',
        'timestamp': time.time(),
        'service': 'fablink-backend',
        'checks': {
            'database': db_status
        }
    })

urlpatterns = [
    path('', api_root, name='api-root'),
    path('health/', health_check, name='health-check'),
    path('ready/', readiness_check, name='readiness-check'),
    path('admin/', admin.site.urls),
    # API 엔드포인트들
    path('api/accounts/', include('apps.accounts.urls')),
    path('api/manufacturing/', include('apps.manufacturing.urls')),
    # path('api/orders/', include('apps.orders.urls')),
    # path('api/notifications/', include('apps.notifications.urls')),
    # path('api/files/', include('apps.files.urls')),
]

# Debug Toolbar URLs (로컬 환경에서만)
if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

# 정적 파일 서빙 (로컬 환경에서만)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
