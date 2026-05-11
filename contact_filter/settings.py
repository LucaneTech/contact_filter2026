from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Local apps
    'apps.accounts',
    'apps.companies',
    'apps.billing',
    'apps.uploads',
    'apps.filtering',
    'apps.processing',
    'apps.exports',
    'apps.dashboard',
    
    # Third party
    'tailwind',
    'theme',
    'django_browser_reload',
    "lucide",
    'django_celery_beat',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.companies.middleware.CompanyMiddleware',
    'django_browser_reload.middleware.BrowserReloadMiddleware',
]

ROOT_URLCONF = 'contact_filter.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
            ],
        },
    },
]

WSGI_APPLICATION = 'contact_filter.wsgi.application'

# Database
_database_url = os.getenv('DATABASE_URL')
if _database_url:
    import dj_database_url
    DATABASES = {'default': dj_database_url.parse(_database_url, conn_max_age=600)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Custom User
AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Europe/Paris'
USE_I18N = True
USE_TZ = True

# Auth
AUTHENTICATION_BACKENDS = ['apps.accounts.backends.EmailBackend']
LOGIN_REDIRECT_URL = 'dashboard:company_dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'
LOGIN_URL = 'accounts:login'
PASSWORD_RESET_TIMEOUT = 3600
# Static & Media
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'theme' / 'static'] if (BASE_DIR / 'theme' / 'static').exists() else []
# STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'  # Active en prod après collectstatic

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Tailwind
TAILWIND_APP_NAME = 'theme'
NPM_BIN_PATH = '/home/lucane/.nvm/versions/node/v22.22.1/bin/npm'
if DEBUG:
    INTERNAL_IPS = ['127.0.0.1']
else:
    INTERNAL_IPS = [os.getenv('INTERNAL_IP', '')]

# Email
# EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')

# settings.py
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = '{name} <noreply@lucanefilter.com>'.format(name='Lucane Filter', email=EMAIL_HOST_USER)

SITE_NAME = 'Lucane Filter'

# Quota & expiration (défini avant Celery pour pouvoir être référencé dans CELERY_BEAT_SCHEDULE)
HISTORIC_FILE_EXPIRATION_TIME = 15   # minutes
UPLOADED_FILE_EXPIRATION_TIME = 5   # minutes

# Celery
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_TIMEZONE = 'Africa/Casablanca'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

# Planification automatique (Celery Beat)
# Le nettoyage s'exécute toutes les UPLOADED_FILE_EXPIRATION_TIME minutes :
# les uploads expirent vite (10 min), les historiques après 1 jour.
# Un seul passage couvre les deux car la requête filtre expires_at__lt=now.
# CELERY_BEAT_SCHEDULE = {
#     'cleanup-expired-files': {
#         # Tâche définie dans apps/processing/tasks_cleanup.py
#         # Découverte via autodiscover_tasks(related_name='tasks_cleanup') dans celery.py
#         'task': 'processing.cleanup_expired_files',
#         'schedule': UPLOADED_FILE_EXPIRATION_TIME * 60,  # secondes (600 par défaut)
#     },
# }

# Stripe
STRIPE_PUBLIC_KEY = os.getenv('STRIPE_PUBLIC_KEY', '')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

# Default primary key
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
