from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django import forms
from django.db import models
from .models import User, Designer, Factory


def _all_field_names(model: type[models.Model]):
    names = []
    for f in model._meta.get_fields():
        if getattr(f, "auto_created", False) and not getattr(f, "concrete", False):
            continue
        if getattr(f, "concrete", False) and not getattr(f, "many_to_many", False):
            names.append(f.name)
        elif getattr(f, "many_to_many", False) and not getattr(f, "auto_created", False):
            names.append(f.name)
    return names


def _search_fields(model: type[models.Model]):
    fields = []
    for f in model._meta.get_fields():
        if not getattr(f, "concrete", False):
            continue
        if isinstance(
            f,
            (models.CharField, models.TextField, models.EmailField, models.SlugField, models.UUIDField),
        ):
            fields.append(f"{f.name}__icontains")
    return fields


def _list_filters(model: type[models.Model]):
    filters = []
    for f in model._meta.get_fields():
        if getattr(f, "auto_created", False) and not getattr(f, "concrete", False):
            continue
        if isinstance(f, models.BooleanField) or getattr(f, "choices", None):
            filters.append(f.name)
        elif isinstance(f, (models.DateField, models.DateTimeField)):
            filters.append(f.name)
        elif isinstance(f, (models.ForeignKey, models.OneToOneField, models.ManyToManyField)) and not getattr(
            f, "auto_created", False
        ):
            filters.append(f.name)
    return filters


def _list_display_fields(model: type[models.Model]):
    names = []
    for f in model._meta.get_fields():
        if getattr(f, "auto_created", False) and not getattr(f, "concrete", False):
            continue
        # Exclude ManyToMany from list_display to avoid admin.E109
        if getattr(f, "many_to_many", False):
            continue
        if getattr(f, "concrete", False):
            names.append(f.name)
    return names


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # 모든 필드 노출/수정 가능 + 기본 필터/검색
    list_display = tuple(_list_display_fields(User))
    list_filter = tuple(_list_filters(User))
    search_fields = tuple(_search_fields(User))
    ordering = ('-pk',)
    
    def get_user_type(self, obj):
        return obj.user_type or '미설정'
    get_user_type.short_description = '사용자 타입'

    # 단순화: 모든 필드를 한 화면에서 표시/수정 가능하게 구성
    fieldsets = None
    add_fieldsets = None
    readonly_fields = ()
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


@admin.register(Designer)
class DesignerAdmin(admin.ModelAdmin):
    list_display = tuple(_list_display_fields(Designer))
    list_filter = tuple(_list_filters(Designer))
    search_fields = tuple(_search_fields(Designer))
    ordering = ('-pk',)
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['password'].widget = forms.PasswordInput()
        return form
    
    def save_model(self, request, obj, form, change):
        if 'password' in form.changed_data:
            obj.set_password(form.cleaned_data['password'])
        super().save_model(request, obj, form, change)


@admin.register(Factory)
class FactoryAdmin(admin.ModelAdmin):
    list_display = tuple(_list_display_fields(Factory))
    list_filter = tuple(_list_filters(Factory))
    search_fields = tuple(_search_fields(Factory))
    ordering = ('-pk',)
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['password'].widget = forms.PasswordInput()
        return form
    
    def save_model(self, request, obj, form, change):
        if 'password' in form.changed_data:
            obj.set_password(form.cleaned_data['password'])
        super().save_model(request, obj, form, change)
