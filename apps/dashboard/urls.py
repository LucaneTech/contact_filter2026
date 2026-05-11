from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # ── Client ────────────────────────────────────────────────────────────────
    path('', views.company_dashboard, name='company_dashboard'),
    path('export/<int:processing_id>/', views.download_export, name='download_export'),
    path('export/<int:processing_id>/<str:fmt>/', views.download_export, name='download_export_format'),

    # ── Admin : vue d'ensemble ────────────────────────────────────────────────
    path('admin/', views.admin_dashboard, name='admin_dashboard'),

    # ── Admin : entreprises ───────────────────────────────────────────────────
    path('admin/companies/', views.admin_companies, name='admin_companies'),
    path('admin/companies/<int:pk>/edit/', views.admin_company_edit, name='admin_company_edit'),
    path('admin/companies/<int:pk>/delete/', views.admin_company_delete, name='admin_company_delete'),

    # ── Admin : utilisateurs ──────────────────────────────────────────────────
    path('admin/users/', views.admin_users, name='admin_users'),
    path('admin/users/new/', views.admin_user_form, name='admin_user_create'),
    path('admin/users/<int:pk>/edit/', views.admin_user_form, name='admin_user_edit'),
    path('admin/users/<int:pk>/delete/', views.admin_user_delete, name='admin_user_delete'),

    # ── Admin : plans ─────────────────────────────────────────────────────────
    path('admin/plans/', views.admin_plans, name='admin_plans'),
    path('admin/plans/new/', views.admin_plan_form, name='admin_plan_create'),
    path('admin/plans/<int:pk>/edit/', views.admin_plan_form, name='admin_plan_edit'),
    path('admin/plans/<int:pk>/delete/', views.admin_plan_delete, name='admin_plan_delete'),

    # ── Admin : traitements ───────────────────────────────────────────────────
    path('admin/uploads/', views.admin_uploads, name='admin_uploads'),
    path('admin/uploads/<int:pk>/delete/', views.admin_upload_delete, name='admin_upload_delete'),

    # ── Admin : historiques ───────────────────────────────────────────────────
    path('admin/histories/', views.admin_histories, name='admin_histories'),
    path('admin/histories/<int:pk>/delete/', views.admin_history_delete, name='admin_history_delete'),

    # ── Ancienne route company_detail (conservée) ─────────────────────────────
    path('admin/company/<int:company_id>/', views.company_detail, name='company_detail'),
]
