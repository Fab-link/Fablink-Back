from django.contrib import admin
from django.db import models
from .models import Product, Order, RequestOrder, BidFactory


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
        # Exclude ManyToMany from list_display to satisfy admin constraints
        if getattr(f, "many_to_many", False):
            continue
        if getattr(f, "concrete", False):
            names.append(f.name)
    return names

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = tuple(_list_display_fields(Product))
    list_filter = tuple(_list_filters(Product))
    search_fields = tuple(_search_fields(Product))
    # 모든 필드 수정 가능 요구에 따라 readonly_fields 미사용

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = tuple(_list_display_fields(Order))
    list_filter = tuple(_list_filters(Order))
    search_fields = tuple(_search_fields(Order))


@admin.register(RequestOrder)
class RequestOrderAdmin(admin.ModelAdmin):
    list_display = tuple(_list_display_fields(RequestOrder))
    list_filter = tuple(_list_filters(RequestOrder))
    search_fields = tuple(_search_fields(RequestOrder))


@admin.register(BidFactory)
class BidFactoryAdmin(admin.ModelAdmin):
    list_display = tuple(_list_display_fields(BidFactory))
    list_filter = tuple(_list_filters(BidFactory))
    search_fields = tuple(_search_fields(BidFactory))