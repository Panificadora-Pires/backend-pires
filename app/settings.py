import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

# ============================================================
# Carregamento das variáveis de ambiente
# ============================================================

load_dotenv()

# ============================================================
# Caminhos do projeto
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================
# Configurações básicas
# ============================================================

DEBUG = os.getenv('DEBUG', 'True').strip().lower() in {
    'true',
    '1',
    'yes',
    'on',
}

SECRET_KEY = os.getenv('SECRET_KEY')

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-development-only'
    else:
        raise RuntimeError(
            'A variável de ambiente SECRET_KEY não foi configurada.'
        )

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        'ALLOWED_HOSTS',
        'localhost,127.0.0.1',
    ).split(',')
    if host.strip()
]

# ============================================================
# Frontend autorizado
# ============================================================

FRONTEND_URLS = [
    url.strip().rstrip('/')
    for url in os.getenv(
        'FRONTEND_URLS',
        'http://localhost:5173,http://127.0.0.1:5173',
    ).split(',')
    if url.strip()
]

CORS_ALLOWED_ORIGINS = FRONTEND_URLS
CSRF_TRUSTED_ORIGINS = FRONTEND_URLS
CORS_ALLOW_CREDENTIALS = True

# ============================================================
# Configurações de segurança e proxy
# ============================================================

SECURE_PROXY_SSL_HEADER = (
    'HTTP_X_FORWARDED_PROTO',
    'https',
)

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# ============================================================
# Regras de negócio do app pedidos
# ============================================================

PEDIDO_TEMPO_LIMITE_RETIRADA_MINUTOS = int(
    os.getenv(
        'PEDIDO_TEMPO_LIMITE_RETIRADA_MINUTOS',
        '15',
    )
)

# ============================================================
# Cloudinary
# ============================================================

CLOUDINARY_URL = os.getenv('CLOUDINARY_URL', '').strip()

# ============================================================
# Login com Google
# ============================================================

GOOGLE_CLIENT_ID = os.getenv(
    'GOOGLE_CLIENT_ID',
    '',
).strip()

# ============================================================
# E-mail
# ============================================================

EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)

DEFAULT_FROM_EMAIL = os.getenv(
    'DEFAULT_FROM_EMAIL',
    'nao-responda@pirespanificadora.com.br',
)

EMAIL_HOST = os.getenv(
    'EMAIL_HOST',
    '',
)

EMAIL_PORT = int(
    os.getenv(
        'EMAIL_PORT',
        '587',
    )
)

EMAIL_HOST_USER = os.getenv(
    'EMAIL_HOST_USER',
    '',
)

EMAIL_HOST_PASSWORD = os.getenv(
    'EMAIL_HOST_PASSWORD',
    '',
)

EMAIL_USE_TLS = os.getenv(
    'EMAIL_USE_TLS',
    'True',
).strip().lower() in {
    'true',
    '1',
    'yes',
    'on',
}

# ============================================================
# Aplicações instaladas
# ============================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Terceiros
    'corsheaders',
    'django_extensions',
    'django_filters',
    'drf_spectacular',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',

    # Aplicações do projeto
    'core',
    'catalogo',
    'pedidos',
    'notificacoes',
]

if CLOUDINARY_URL:
    INSTALLED_APPS += [
        'cloudinary',
        'cloudinary_storage',
    ]

# ============================================================
# Middlewares
# ============================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ============================================================
# URLs e aplicações WSGI/ASGI
# ============================================================

ROOT_URLCONF = 'app.urls'

WSGI_APPLICATION = 'app.wsgi.application'
ASGI_APPLICATION = 'app.asgi.application'

# ============================================================
# Templates
# ============================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

# ============================================================
# Banco de dados
# ============================================================

DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///db.sqlite3',
        conn_max_age=600,
        conn_health_checks=True,
    ),
}

# ============================================================
# Modelo de usuário
# ============================================================

AUTH_USER_MODEL = 'core.User'

# ============================================================
# Validação de senhas
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'UserAttributeSimilarityValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'MinimumLengthValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'CommonPasswordValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'NumericPasswordValidator'
        ),
    },
]

# ============================================================
# Internacionalização
# ============================================================

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True
USE_TZ = True

# ============================================================
# Arquivos estáticos
# ============================================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ============================================================
# Arquivos de mídia
# ============================================================

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

FILE_UPLOAD_PERMISSIONS = 0o640

# ============================================================
# Armazenamento de arquivos
# ============================================================

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': (
            'whitenoise.storage.'
            'CompressedManifestStaticFilesStorage'
        ),
    },
}

if CLOUDINARY_URL:
    STORAGES['default'] = {
        'BACKEND': (
            'cloudinary_storage.storage.'
            'MediaCloudinaryStorage'
        ),
    }

# ============================================================
# Modelo padrão de chave primária
# ============================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================================
# Django REST Framework
# ============================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.'
        'JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.'
        'DjangoModelPermissionsOrAnonReadOnly',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.'
        'DjangoFilterBackend',
    ),
    'DEFAULT_SCHEMA_CLASS': (
        'drf_spectacular.openapi.AutoSchema'
    ),
    'DEFAULT_PAGINATION_CLASS': (
        'app.pagination.CustomPagination'
    ),
    'PAGE_SIZE': 10,
}

# ============================================================
# OpenAPI / Swagger
# ============================================================

SPECTACULAR_SETTINGS = {
    'TITLE': 'Pires Panificadora API',
    'DESCRIPTION': (
        'API para o sistema de pedidos da '
        'Pires Panificadora.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# ============================================================
# Simple JWT
# ============================================================

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=3),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ============================================================
# Logging
# ============================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    'formatters': {
        'verbose': {
            'format': (
                '{levelname} {asctime} '
                '{name} {message}'
            ),
            'style': '{',
        },
    },

    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },

    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },

    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },

        'django.utils.autoreload': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },

        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
