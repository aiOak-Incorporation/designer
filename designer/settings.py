"""
Django settings for designer project.
"""

from pathlib import Path
import os
import socket
import warnings
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Core ---
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-change-this-in-production")
DEBUG = os.getenv("DEBUG", "False") == "True"

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "designer.aioak.co",
    "www.designer.aioak.co",
]


SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  
CSRF_TRUSTED_ORIGINS = [
    "https://designer.aioak.co",
    "https://www.designer.aioak.co",
]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# --- Apps ---
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "django_filters",
    
    # Local
    "designer_portfolio",
]

# --- REST Framework ---
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "designer Fashion Portfolio API",
    "DESCRIPTION": "REST API for Manya’s fashion portfolio (brand designer).",
    "VERSION": "1.0.0",
}

# --- Middleware ---
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # ✅ compressed static files
    "django.contrib.sessions.middleware.SessionMiddleware",
    "designer_portfolio.middleware.UTMTrackingMiddleware",  # ✅ capture UTM/session attribution
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "designer.urls"

# --- Static & Media ---
STATIC_URL = "/static/"
# Do not include app static directories here; AppDirectoriesFinder already handles them.
# Keeping this empty avoids duplicate collection of the same files.
STATICFILES_DIRS = []
STATIC_ROOT = BASE_DIR / "staticfiles"

# Use S3 for media in production to avoid losing uploads on deploys
USE_S3_MEDIA = os.getenv("USE_S3_MEDIA", "False") == "True"

if USE_S3_MEDIA:
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "")
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", None)
    AWS_S3_CUSTOM_DOMAIN = os.getenv("AWS_S3_CUSTOM_DOMAIN", "")
    AWS_S3_SIGNATURE_VERSION = os.getenv("AWS_S3_SIGNATURE_VERSION", "s3v4")
    AWS_QUERYSTRING_AUTH = False

    # Django 5 STORAGES API
    STORAGES = {
        "default": {"BACKEND": "designer.storages.MediaStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

    if AWS_S3_CUSTOM_DOMAIN:
        MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"
    else:
        MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/media/"
    MEDIA_ROOT = None  # S3 does not use local MEDIA_ROOT
else:
    # Local filesystem media (development)
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"

# --- Templates ---
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "designer_portfolio" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "designer_portfolio.context_processors.dashboard_counts",
                "designer_portfolio.context_processors.active_portfolio_template",
                "designer_portfolio.context_processors.utm_context",  # ✅ expose UTM/session attribution
            ],
        },
    }
]

WSGI_APPLICATION = "designer.wsgi.application"

# --- Database (Prefer DATABASE_URL for persistent DB in production) ---
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("DB_URL")

def _db_settings_from_url(database_url: str):
    parsed = urlparse(database_url)
    scheme = (parsed.scheme or "").lower()

    if scheme in {"postgres", "postgresql", "psql", "pgsql"}:
        engine = "django.db.backends.postgresql"
    elif scheme == "mysql":
        engine = "django.db.backends.mysql"
    elif scheme == "sqlite":
        engine = "django.db.backends.sqlite3"
    else:
        raise ValueError(f"Unsupported DATABASE_URL scheme: {scheme}")

    if engine.endswith("sqlite3"):
        name = parsed.path or (BASE_DIR / "db.sqlite3")
    else:
        # strip leading slash in /dbname
        name = parsed.path[1:] if parsed.path.startswith("/") else parsed.path

    return {
        "ENGINE": engine,
        "NAME": str(name),
        "USER": parsed.username or "",
        "PASSWORD": parsed.password or "",
        "HOST": parsed.hostname or "",
        "PORT": parsed.port or "",
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
    }

if DATABASE_URL:
    DATABASES = {"default": _db_settings_from_url(DATABASE_URL)}
else:
    DATABASES = {
        "default": {
            "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
            "NAME": os.getenv("DB_NAME", BASE_DIR / "db.sqlite3"),
            "USER": os.getenv("DB_USER", ""),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", ""),
            "PORT": os.getenv("DB_PORT", ""),
        }
    }
    if not str(DATABASES["default"]["NAME"]).endswith(".sqlite3"):
        DATABASES["default"]["CONN_MAX_AGE"] = int(os.getenv("DB_CONN_MAX_AGE", "60"))

# Warn loudly if SQLite is used while DEBUG=False (could lead to data loss in ephemeral envs)
if not DEBUG and DATABASES["default"]["ENGINE"].endswith("sqlite3"):
    warnings.warn(
        "SQLite is configured while DEBUG=False. Configure a persistent database via DATABASE_URL to avoid data loss.",
        RuntimeWarning,
    )

# --- Password validation ---
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- I18N ---
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Caching ---
# Use Redis only when explicitly enabled to avoid DNS issues in environments
# where a Redis hostname like "designer-redis" is not resolvable.
USE_REDIS = os.getenv("USE_REDIS", "False") == "True"
redis_url = os.getenv("REDIS_URL") or os.getenv("CACHE_URL") or "redis://127.0.0.1:6379/1"

if USE_REDIS:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": redis_url,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            },
            "TIMEOUT": 60 * 60,  # 1 hour
        }
    }
    # Use cache-backed sessions when Redis is available
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "default"
else:
    # Fallback: local-memory cache and DB-backed sessions (stable across processes)
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-designer-cache",
        }
    }

# --- Sessions ---
if USE_REDIS:
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "default"
else:
    # Store sessions in DB when Redis is disabled/missing
    SESSION_ENGINE = "django.contrib.sessions.backends.db"

# --- Email ---
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = "no-reply@designer.com"
ADMIN_EMAIL = "chpreddy@gmail.com"


LOGIN_REDIRECT_URL = "designer_dashboard"
LOGOUT_REDIRECT_URL = "home"
AUTHENTICATION_BACKENDS = [
    "designer_portfolio.auth_backends.EmailOrUsernameModelBackend",
    "django.contrib.auth.backends.ModelBackend",
]
DEBUG = os.getenv("DEBUG", "False") == "True"

# Custom session age when "Remember Me" is checked (default 30 days)
REMEMBER_ME_SESSION_AGE = int(os.getenv("REMEMBER_ME_SESSION_AGE", 60 * 60 * 24 * 30))