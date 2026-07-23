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

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure')
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
ALLOWED_HOSTS = ['*']

# ============================================================
# Frontend autorizado
# ============================================================

FRONTEND_URLS = [
    url.strip()
    for url in os.getenv(
        'FRONTEND_URLS',
        'http://localhost:5173,http://127.0.0.1:5173'
    ).split(',')
    if url.strip()
]

CLOUDINARY_URL = os.getenv('CLOUDINARY_URL')

CORS_ALLOWED_ORIGINS = FRONTEND_URLS
CSRF_TRUSTED_ORIGINS = FRONTEND_URLS
CORS_ALLOW_CREDENTIALS = True

# ============================================================
# Regras de negócio do app pedidos
# ============================================================

PEDIDO_TEMPO_LIMITE_RETIRADA_MINUTOS = int(os.getenv('PEDIDO_TEMPO_LIMITE_RETIRADA_MINUTOS', '15'))

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
    'django.contrib.sites',

    # Terceiros
    'corsheaders',
    'django_extensions',
    'django_filters',
    'drf_spectacular',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',

    # Social Auth (Removido dj_rest_auth para evitar bug de username)
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    # Aplicações do projeto
    'core',
    'catalogo',
    'pedidos',
    'notificacoes',
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
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ============================================================
# URLs
# ============================================================

ROOT_URLCONF = 'app.urls'
WSGI_APPLICATION = 'app.wsgi.application'

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
    )
}

# ============================================================
# Validação de senhas
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
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
MEDIA_ENDPOINT = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
FILE_UPLOAD_PERMISSIONS = 0o640
MEDIA_URL = 'http://127.0.0.1:8000/media/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ============================================================
# Cloudinary (opcional)
# ============================================================

if CLOUDINARY_URL:
    INSTALLED_APPS += ['cloudinary', 'cloudinary_storage']
    MEDIA_URL = '/media/'
    STORAGES = {
        'default': {'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage'},
        'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
    }

# ============================================================
# Modelo padrão de chave primária
# ============================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================================
# Modelo de usuário
# ============================================================

AUTH_USER_MODEL = 'core.User'

# ============================================================
# Django REST Framework
# ============================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework_simplejwt.authentication.JWTAuthentication',),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly',),
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend',),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'app.pagination.CustomPagination',
    'PAGE_SIZE': 10,
}

# ============================================================
# OpenAPI / Swagger
# ============================================================

SPECTACULAR_SETTINGS = {
    'TITLE': 'Pires Panificadora API',
    'DESCRIPTION': 'API para o sistema de pedidos da Pires Panificadora.',
    'VERSION': '1.0.0',
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
# Django Sites (Exigido pelo Allauth)
# ============================================================
SITE_ID = 1

# ============================================================
# Django Allauth (Social Auth)
# ============================================================
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# CRUCIAL: Como nosso model User NÃO tem username, dizemos ao Allauth
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']  # O * indica obrigatório, e não tem username
ACCOUNT_EMAIL_VERIFICATION = 'none'

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': os.getenv('GOOGLE_CLIENT_ID', ''),
            'secret': os.getenv('GOOGLE_CLIENT_SECRET', ''),
            'key': '',
        },
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    }
}

# ============================================================
# Informações de configuração (debug)
# ============================================================

print('=' * 70)
print('CONFIGURAÇÃO DA APLICAÇÃO')
print('=' * 70)

print(f'DEBUG....................: {DEBUG if DEBUG else "NÃO DEFINIDO"}')
print(f'SECRET_KEY...............: {SECRET_KEY if SECRET_KEY else "NÃO DEFINIDA"}')
print()
print(f'DATABASE ENGINE.............: {DATABASES["default"]["ENGINE"]}')
print(f'DATABASE NAME...............: {DATABASES["default"]["NAME"]}')
print()
print(f'FRONTEND_URLS ({len(FRONTEND_URLS)}).......: {FRONTEND_URLS}')
print(f'CORS_ALLOWED_ORIGINS....: {CORS_ALLOWED_ORIGINS}')
print(f'CSRF_TRUSTED_ORIGINS....: {CSRF_TRUSTED_ORIGINS}')
print()
print(f'MEDIA_URL...............: {MEDIA_URL}')
print(f'MEDIA_ROOT..............: {MEDIA_ROOT}')
print()
print(f'CLOUDINARY..............: {"SIM" if CLOUDINARY_URL else "NÃO"}')
if CLOUDINARY_URL:
    print(f'CLOUDINARY_URL..........: {CLOUDINARY_URL}')
print('=' * 70)
