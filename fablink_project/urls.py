from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

def api_root(request):
    """API 루트 엔드포인트"""
    return JsonResponse({
        'message': 'FabLink API Server',
        'version': '1.0.0',
        'documentation': {
            'swagger': '/api/docs/',
            'redoc': '/api/redoc/',
            'schema': '/api/schema/',
        },
        'health_endpoints': {
            'health': '/health/',
            'ready': '/ready/',
            'startup': '/startup/',
        },
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

urlpatterns = [
    path('', api_root, name='api-root'),
    path('admin/', admin.site.urls),
    
    # API 문서화 엔드포인트
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # Health check endpoints (루트 레벨)
    path('', include('apps.core.urls')),
    
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