from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/accounts/login/', permanent=False)),
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('uploads/', include('apps.uploads.urls')),
    path('dashboard/', include('apps.dashboard.urls')),
    path('__reload__/', include('django_browser_reload.urls')),
]

if settings.DEBUG and settings.MEDIA_ROOT:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
