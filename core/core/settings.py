from pathlib import Path
import os
from dotenv import load_dotenv
from celery.schedules import crontab  # type:ignore
load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'django_celery_beat',
    'rest_framework',
    'storages',
    'user',
    'clinic',
    'doctor',
    'patient',
    'treatment',
    'whatsapp',
]

AUTH_USER_MODEL = 'user.User'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "HOST": os.environ.get("DB_HOST"),
        "NAME": os.environ.get("DB_NAME"),
        "USER": os.environ.get("DB_USER"),
        "PASSWORD": os.environ.get("DB_PASS"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files configuration (using Whitenoise)
WHITENOISE_AUTOREFRESH = True
MEDIA_ROOT = "/vol/web/media"
MEDIA_URL = "/media/"         
STATIC_ROOT = "/vol/web/static"
STATIC_URL = "/static/"

# MinIO / S3 Storage Settings
AWS_ACCESS_KEY_ID = os.environ.get('MINIO_ROOT_USER')
AWS_SECRET_ACCESS_KEY = os.environ.get('MINIO_ROOT_PASSWORD')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_BUCKET_NAME', 'patient-reports')
AWS_S3_ENDPOINT_URL = os.environ.get('AWS_ENDPOINT', 'http://rheuma-minio:7000')
AWS_S3_REGION_NAME = os.environ.get('AWS_REGION', 'us-east-1')

# MinIO / S3 configuration details
AWS_S3_SIGNATURE_VERSION = 's3v4'
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = True

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

ASGI_APPLICATION = 'core.asgi.application'

# Redis configuration
REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
REDIS_PORT = os.environ.get('REDIS_PORT', '6379')
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')
REDIS_AUTH = f":{REDIS_PASSWORD}@" if REDIS_PASSWORD else ""

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{REDIS_AUTH}{REDIS_HOST}:{REDIS_PORT}/1",
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                {
                    "address": f"redis://{REDIS_AUTH}{REDIS_HOST}:{REDIS_PORT}/2",
                    "socket_timeout": 30,
                    "socket_connect_timeout": 5,
                    "health_check_interval": 30,
                    "socket_keepalive": True,
                }
            ],
        },
    },
}


# celery settings 
CELERY_REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
CELERY_REDIS_PORT = os.environ.get('REDIS_PORT', '6379')
CELERY_BROKER_URL = f"redis://:{REDIS_PASSWORD}@{CELERY_REDIS_HOST}:{CELERY_REDIS_PORT}/0"
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Kolkata"
CELERY_RESULT_BACKEND = f"redis://:{REDIS_PASSWORD}@{CELERY_REDIS_HOST}:{CELERY_REDIS_PORT}/0"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_DEFAULT_QUEUE = 'primary'
CELERY_BEAT_SCHEDULE = {
    "cleanup-expired-whatsapp-sessions": {
        "task": "cleanup_expired_whatsapp_sessions",
        "schedule": 60.0,
    },
    "cleanup-unverified-lab-reports": {
        "task": "cleanup_unverified_lab_reports_task",
        "schedule": 10800.0, # Every 3 hours (3 * 3600 seconds)
    },
}

from .logging_config import master_logger  

try:
    from .logging_config import *
except ImportError:
    pass