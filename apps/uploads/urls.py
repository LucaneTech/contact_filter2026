from django.urls import path
from . import views

app_name = 'uploads'

urlpatterns = [
    path('', views.upload_view, name='upload'),
    path('<int:upload_id>/filters/', views.filter_config_view, name='filter_config'),
    path('<int:upload_id>/status/', views.upload_status_view, name='upload_status'),
]
