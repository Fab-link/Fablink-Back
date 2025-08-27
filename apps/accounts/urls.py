from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # ==================== 루트 ====================
    path('', views.accounts_root_view, name='accounts_root'),
    
    # ==================== 로그인 ====================
    path('designer/login/', views.designer_login_view, name='designer_login'),
    path('factory/login/', views.factory_login_view, name='factory_login'),
    
    # ==================== 인증 ====================
    path('logout/', views.logout_view, name='logout'),
    path('token/refresh/', views.token_refresh_view, name='token_refresh'),
]
