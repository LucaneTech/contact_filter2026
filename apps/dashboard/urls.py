from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.company_dashboard, name='company_dashboard'),
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('export/<int:processing_id>/', views.download_export, name='download_export'),
]
