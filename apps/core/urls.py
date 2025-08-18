"""
Core app URL configuration
"""
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Health check endpoints
    path('health/', views.health_check, name='health'),
    path('ready/', views.readiness_check, name='ready'),
    path('startup/', views.startup_check, name='startup'),
]
