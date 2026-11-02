"""
Django settings for the Manufacturing Manual Assistant project.

Generated for Django 5.2 LTS.
Architecture: RAG-based Technical Manual Assistant.
Database: PostgreSQL 18 with Psycopg 3.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file located at BASE_DIR / '.env'
load_dotenv(BASE_DIR / '.env')

# ==============================================================================
# Core Security & Debug Settings
# ==============================================================================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv(
    'SECRET_KEY',
    'django-insecure-mman-dev-d8f92b7c4a1e506381e4a69c0d12e4f7a930b8c6e1d2f5'
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't', 'yes')

# Allowed hosts configuration
raw_allowed_hosts = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost,testserver')
ALLOWED_HOSTS = [host.strip() for host in raw_allowed_hosts.split(',') if host.strip()]
if 'testserver' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('testserver')


# ==============================================================================
# Application Definition
# ==============================================================================

INSTALLED_APPS = [
    # Default Django Applications
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-Party Applications
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',

    # Domain Applications
    'accounts.apps.AccountsConfig',
    'machines.apps.MachinesConfig',
    'documents.apps.DocumentsConfig',
    'rag.apps.RagConfig',
    'history.apps.HistoryConfig',
    'chat.apps.ChatConfig',
]

MIDDLEWARE = [
    # CorsMiddleware must be as high as possible, especially before CommonMiddleware
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'


# ==============================================================================
# Custom User Model Configuration
# ==============================================================================

AUTH_USER_MODEL = 'accounts.User'


# ==============================================================================
# Database Configuration (Neon PostgreSQL / PostgreSQL 18)
# ==============================================================================

DATABASE_URL = os.getenv('DATABASE_URL', '').strip()

if DATABASE_URL:
    # Primary configuration method: parse DATABASE_URL via psycopg conninfo
    from psycopg.conninfo import conninfo_to_dict

    conn_params = conninfo_to_dict(DATABASE_URL)
    standard_keys = {'dbname', 'user', 'password', 'host', 'port'}
    db_options = {k: v for k, v in conn_params.items() if k not in standard_keys}

    # Enforce SSL requirement for Neon connectivity
    if 'sslmode' not in db_options:
        db_options['sslmode'] = 'require'

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': conn_params.get('dbname', ''),
            'USER': conn_params.get('user', ''),
            'PASSWORD': conn_params.get('password', ''),
            'HOST': conn_params.get('host', ''),
            'PORT': int(conn_params.get('port', 5432)) if conn_params.get('port') else 5432,
            'OPTIONS': db_options,
            'CONN_HEALTH_CHECKS': True,
        }
    }
else:
    # Fallback configuration method: discrete environment parameters
    DB_NAME = os.getenv('DB_NAME', 'manufacturing_manual_assistant')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_SSLMODE = os.getenv('DB_SSLMODE', '')

    db_options = {}
    if DB_SSLMODE:
        db_options['sslmode'] = DB_SSLMODE

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASSWORD,
            'HOST': DB_HOST,
            'PORT': int(DB_PORT) if DB_PORT else 5432,
            'OPTIONS': db_options,
            'CONN_HEALTH_CHECKS': True,
        }
    }

# ==============================================================================
# Mandatory PostgreSQL Enforcement
# SQLite is strictly prohibited for production, development, and testing.
# ==============================================================================
if DATABASES['default'].get('ENGINE') != 'django.db.backends.postgresql':
    raise RuntimeError('PostgreSQL is mandatory. SQLite is strictly prohibited.')


# ==============================================================================
# Password Validation
# ==============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        },
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# ==============================================================================
# Internationalization
# ==============================================================================

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# ==============================================================================
# Static and Media Files
# ==============================================================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Configurable maximum file upload size (default 25 MB)
MAX_UPLOAD_SIZE_BYTES = int(os.getenv('MAX_UPLOAD_SIZE_BYTES', str(25 * 1024 * 1024)))


# ==============================================================================
# Default Primary Key Field Type
# ==============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ==============================================================================
# Django REST Framework (DRF) Configuration
# ==============================================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',  # Deny-by-default security posture
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
}


# ==============================================================================
# SimpleJWT Configuration
# ==============================================================================

jwt_access_mins = int(os.getenv('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', '30'))
jwt_refresh_days = int(os.getenv('JWT_REFRESH_TOKEN_LIFETIME_DAYS', '7'))

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=jwt_access_mins),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=jwt_refresh_days),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'TOKEN_TYPE_CLAIM': 'token_type',
}


# ==============================================================================
# CORS Configuration
# ==============================================================================

raw_cors_origins = os.getenv(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000'
)
CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in raw_cors_origins.split(',') if origin.strip()
]

CORS_ALLOW_CREDENTIALS = True

CORS_EXPOSE_HEADERS = [
    'Content-Type',
    'Content-Disposition',
    'Content-Length',
    'Content-Range',
    'Accept-Ranges',
]


# ==============================================================================
# RAG, Embedding Provider & ChromaDB Configuration
# ==============================================================================

# Embedding Provider Selection ('huggingface' or 'lm_studio')
EMBEDDING_PROVIDER = os.getenv('EMBEDDING_PROVIDER', 'huggingface').lower().strip()

# Hugging Face Inference Providers Configuration
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'Qwen/Qwen3-Embedding-0.6B').strip()
EMBEDDING_API_KEY = os.getenv('EMBEDDING_API_KEY') or os.getenv('HF_TOKEN', '')
EMBEDDING_BASE_URL = os.getenv('EMBEDDING_BASE_URL', '').strip()

# LM Studio Local Provider Configuration
LM_STUDIO_BASE_URL = os.getenv('LM_STUDIO_BASE_URL', 'http://127.0.0.1:1234/v1').strip()
LM_STUDIO_EMBEDDING_MODEL = os.getenv('LM_STUDIO_EMBEDDING_MODEL', 'nomic-ai/nomic-embed-text-v1.5-GGUF').strip()

# General Embedding Settings
EMBEDDING_REQUEST_TIMEOUT = int(os.getenv('EMBEDDING_REQUEST_TIMEOUT', '30'))

# ChromaDB Vector Database Configuration
CHROMA_PERSIST_DIRECTORY = Path(os.getenv('CHROMA_PERSIST_DIRECTORY', str(BASE_DIR / 'data' / 'chroma')))
CHROMA_COLLECTION_NAME = os.getenv('CHROMA_COLLECTION_NAME', 'manufacturing_manual_chunks_v1').strip()

# Vector Backend Selection -- controls whether retrieval uses ChromaDB or pgvector.
# Switch to 'pgvector' only after: migration applied, embeddings rebuilt, and full test suite passes.
VECTOR_BACKEND = os.getenv('VECTOR_BACKEND', 'pgvector').lower().strip()
if VECTOR_BACKEND not in ('chroma', 'pgvector'):
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured(
        f"VECTOR_BACKEND must be 'chroma' or 'pgvector', got: {VECTOR_BACKEND!r}"
    )

# Document Chunking Configuration
CHUNK_TARGET_TOKENS = int(os.getenv('CHUNK_TARGET_TOKENS', '400'))
CHUNK_MAX_TOKENS = int(os.getenv('CHUNK_MAX_TOKENS', '500'))
CHUNK_OVERLAP_TOKENS = int(os.getenv('CHUNK_OVERLAP_TOKENS', '60'))
CHUNK_MIN_TOKENS = int(os.getenv('CHUNK_MIN_TOKENS', '40'))

# RAG Semantic Retrieval Configuration
RAG_TOP_K = int(os.getenv('RAG_TOP_K', '5'))

# LLM Answer Generation Configuration ('gemini', 'openai_compatible', 'lm_studio')
# Google Gemini API is the mandatory default API provider.
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'gemini').lower().strip()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '').strip()
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview').strip()

# Common Provider Settings
LLM_TIMEOUT = int(os.getenv('LLM_TIMEOUT', '60'))
LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.1'))

# Secondary / Self-hosted Fallback Options (never used implicitly when Gemini fails)
LLM_MODEL = os.getenv('LLM_MODEL', 'gemini-2.5-flash').strip()
LLM_BASE_URL = os.getenv('LLM_BASE_URL', '').strip()
LLM_API_KEY = os.getenv('LLM_API_KEY', '').strip()
