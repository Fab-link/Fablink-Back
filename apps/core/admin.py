from __future__ import annotations

from typing import List, Optional, Tuple
import importlib.util

from django.apps import apps as django_apps
from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered
from django.db import models


def _get_list_display(model: type[models.Model]) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    Build list_display for a model.
    - Include all concrete non-M2M fields (including FKs)
    - For M2M fields, create synthetic display methods and return their (name, field_name)
    """
    field_names: List[str] = []
    m2m_fields: List[models.ManyToManyField] = []

    for f in model._meta.get_fields():
        # Skip reverse relations
        if getattr(f, "auto_created", False) and not getattr(f, "concrete", False):
            continue

        # Concrete local fields (incl. FK, O2O, etc.)
        if getattr(f, "concrete", False) and not getattr(f, "many_to_many", False):
            field_names.append(f.name)
            continue

        # Direct M2M fields on the model
        if getattr(f, "many_to_many", False) and not getattr(f, "auto_created", False):
            m2m_fields.append(f)  # handle later via synthetic methods

    synthetic_methods: List[Tuple[str, str]] = []  # (method_name, field_name)
    for m2m in m2m_fields:
        method_name = f"display_{m2m.name}"
        synthetic_methods.append((method_name, m2m.name))
        field_names.append(method_name)

    return field_names, synthetic_methods


def _get_search_fields(model: type[models.Model]) -> List[str]:
    fields: List[str] = []
    for f in model._meta.get_fields():
        if not getattr(f, "concrete", False):
            continue
        if isinstance(
            f,
            (
                models.CharField,
                models.TextField,
                models.EmailField,
                models.SlugField,
                models.UUIDField,
            ),
        ):
            fields.append(f"{f.name}__icontains")
    return fields


def _get_list_filter(model: type[models.Model]) -> List[str]:
    filters: List[str] = []
    for f in model._meta.get_fields():
        # Only filter on concrete local fields or direct relations
        if getattr(f, "auto_created", False) and not getattr(f, "concrete", False):
            continue

        if isinstance(f, (models.BooleanField,)):
            filters.append(f.name)
        elif getattr(f, "choices", None):
            filters.append(f.name)
        elif isinstance(f, (models.DateField, models.DateTimeField)):
            filters.append(f.name)
        elif isinstance(f, (models.ForeignKey, models.OneToOneField)):
            filters.append(f.name)
        elif isinstance(f, (models.ManyToManyField,)) and not getattr(f, "auto_created", False):
            filters.append(f.name)
    return filters


def _get_date_hierarchy_field(model: type[models.Model]) -> Optional[str]:
    # Prefer common created fields
    preferred = ("created_at", "created", "ctime", "date_created")
    date_time_fields: List[str] = []
    date_fields: List[str] = []
    for f in model._meta.get_fields():
        if not getattr(f, "concrete", False):
            continue
        if isinstance(f, models.DateTimeField):
            date_time_fields.append(f.name)
        elif isinstance(f, models.DateField):
            date_fields.append(f.name)

    for name in preferred:
        if name in date_time_fields or name in date_fields:
            return name
    if date_time_fields:
        return date_time_fields[0]
    if date_fields:
        return date_fields[0]
    return None


def build_admin_class(model: type[models.Model]) -> type[admin.ModelAdmin]:
    list_display, synthetic = _get_list_display(model)
    search_fields = _get_search_fields(model)
    list_filter = _get_list_filter(model)
    date_hierarchy = _get_date_hierarchy_field(model)

    attrs: dict = {
        "list_display": tuple(list_display) if list_display else ("__str__",),
        "search_fields": tuple(search_fields),
        "list_filter": tuple(list_filter),
        "list_select_related": True,
        "list_per_page": 50,
        "ordering": ("-pk",),
        # All fields editable by default (no readonly_fields, no exclude)
    }

    # Attach synthetic m2m display methods
    for method_name, field_name in synthetic:
        def _make_func(fn: str):
            def _func(self, obj):
                qs = getattr(obj, fn).all()
                items = [str(v) for v in qs[:10]]
                # Avoid extra count() if possible
                more = 0
                try:
                    total = qs.count()
                    more = total - len(items)
                except Exception:
                    pass
                suffix = f" (+{more})" if more > 0 else ""
                return ", ".join(items) + suffix

            _func.short_description = field_name
            _func.admin_order_field = None
            return _func

        attrs[method_name] = _make_func(field_name)

    if date_hierarchy:
        attrs["date_hierarchy"] = date_hierarchy

    return type(f"AutoAdmin_{model.__name__}", (admin.ModelAdmin,), attrs)


def _should_skip_model(model: type[models.Model]) -> bool:
    # Per user request, do not skip any models
    return False


def autoregister_all_models():
    """Register models only for apps that don't define their own admin module."""
    registry = admin.site._registry  # type: ignore[attr-defined]

    for app_config in django_apps.get_app_configs():
        # If app has its own admin.py, skip to avoid AlreadyRegistered conflicts,
        # but do not skip this core app where the generic auto-admin lives.
        has_admin = importlib.util.find_spec(f"{app_config.name}.admin") is not None
        if has_admin and app_config.name != "apps.core":
            continue

        for model in app_config.get_models():
            if _should_skip_model(model):
                continue
            if model in registry:
                continue
            try:
                admin_class = build_admin_class(model)
                admin.site.register(model, admin_class)
            except AlreadyRegistered:
                continue
            except Exception:
                # Skip problematic models rather than blocking admin startup.
                continue


# Execute on admin autodiscover
autoregister_all_models()
