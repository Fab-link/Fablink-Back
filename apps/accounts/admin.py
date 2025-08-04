from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # 리스트에서 보여줄 필드
    list_display = ('user_id', 'name', 'user_type', 'is_staff', 'is_active', 'created_at')
    list_filter = ('user_type', 'is_staff', 'is_active', 'created_at')
    search_fields = ('user_id', 'name', 'contact')
    ordering = ('-created_at',)

    # 필드셋 구성 (관리자 상세 페이지에서 보여줄 항목)
    fieldsets = (
        (_('기본 정보'), {
            'fields': ('user_id', 'password')
        }),
        (_('개인 정보'), {
            'fields': ('name', 'user_type', 'contact', 'address')
        }),
        (_('권한 설정'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        (_('기록'), {
            'fields': ('last_login', 'created_at', 'updated_at')
        }),
    )

    # 유저 생성 시 나오는 필드
    add_fieldsets = (
        (_('회원가입'), {
            'classes': ('wide',),
            'fields': ('user_id', 'name', 'user_type', 'contact', 'address', 'password1', 'password2'),
        }),
    )

    readonly_fields = ('created_at', 'updated_at', 'last_login')
    filter_horizontal = ('groups', 'user_permissions')
    
    # AbstractBaseUser 사용을 위한 설정
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        is_superuser = request.user.is_superuser
        disabled_fields = set()

        if not is_superuser:
            disabled_fields |= {
                'is_superuser',
                'user_permissions',
                'groups',
            }

        for f in disabled_fields:
            if f in form.base_fields:
                form.base_fields[f].disabled = True

        return form
