from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # ==================== 로그인 ====================
    path('designer/login/', views.designer_login_view, name='designer_login'),
    path('factory/login/', views.factory_login_view, name='factory_login'),
    
    # ==================== 인증 ====================
    path('logout/', views.logout_view, name='logout'),
    path('token/refresh/', views.token_refresh_view, name='token_refresh'),
    
    # ==================== 사용자 프로필 ====================
    path('profile/', views.user_profile_view, name='user_profile'),
    # 호환: 프론트에서 /user_info/ 호출 시 404 방지
    path('user_info/', views.user_profile_view, name='user_info'),
]