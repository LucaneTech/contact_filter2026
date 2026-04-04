from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView, TemplateView
from django.contrib.auth.views import LoginView

urlpatterns = [
    # path('admin/', TemplateView.as_view(template_name='index.html'), name='index'),
    # path('', TemplateView.as_view(template_name='index.html'), name='index'),
    # path('profile/', TemplateView.as_view(template_name='profile.html'), name='profile'),
    # path('register/', LoginView.as_view(template_name='accounts/register.html'), name='register'),
    # path('login/', LoginView.as_view(template_name='accounts/login.html'), name='login'),
    # path('logout/', LoginView.as_view(template_name='accounts/logout.html'), name='logout'),
    
    
    
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/accounts/login/', permanent=False)),
    path('accounts/', include('apps.accounts.urls')),
    path('uploads/', include('apps.uploads.urls')),
    path('dashboard/', include('apps.dashboard.urls')),
    path('__reload__/', include('django_browser_reload.urls')),
]

if settings.DEBUG and settings.MEDIA_ROOT:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
