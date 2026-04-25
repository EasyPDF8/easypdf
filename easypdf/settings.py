import os
from pathlib import Path
import dj_database_url

# ======================================
# BASE DIRECTORY
# ======================================
BASE_DIR = Path(__file__).resolve().parent.parent

# ======================================
# SECRET KEY
# Render Environment Variable:
# DJANGO_SECRET_KEY
# ======================================
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "change-this-in-render-production"
)

# ======================================
# DEBUG MODE
# Render:
# DEBUG=False
# Local:
# DEBUG=True
# ======================================
DEBUG = os.environ.get("DEBUG", "False") == "True"

# ======================================
# ALLOWED HOSTS
# Example:
# easypdf.onrender.com,www.easypdf.xyz,easypdf.xyz
# ======================================
ALLOWED_HOSTS = ["*"]

# ======================================
# INSTALLED APPS
# ======================================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    'django.contrib.sitemaps',

    "tools",
    "csp",
]

# ======================================
# MIDDLEWARE
# ======================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    # WhiteNoise for static files on Render
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # Your cleanup middleware
    "tools.middleware.FileCleanupMiddleware",
]

ROOT_URLCONF = "easypdf.urls"

# ======================================
# TEMPLATES
# ======================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.media",
            ],
        },
    },
]

WSGI_APPLICATION = "easypdf.wsgi.application"

# ======================================
# DATABASE
# Add in Render:
# DATABASE_URL = your_neon_link
# ======================================
if os.environ.get("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.parse(
            os.environ.get("DATABASE_URL"),
            conn_max_age=600,
            ssl_require=True
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ======================================
# PASSWORD VALIDATORS
# ======================================
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ======================================
# LANGUAGE / TIME
# ======================================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ======================================
# STATIC FILES
# ======================================
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_STORAGE = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)

# ======================================
# MEDIA FILES
# Temporary only
# ======================================
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ======================================
# DEFAULT PRIMARY KEY
# ======================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ======================================
# FILE UPLOAD LIMITS
# ======================================
DATA_UPLOAD_MAX_MEMORY_SIZE = 209715200
FILE_UPLOAD_MAX_MEMORY_SIZE = 209715200
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

# ======================================
# SESSION SETTINGS
# ======================================
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 60 * 60 * 24
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True

# ======================================
# SECURITY (PRODUCTION READY)
# ======================================
SECURE_SSL_REDIRECT = not DEBUG

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

X_FRAME_OPTIONS = "DENY"

SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# ======================================
# CSRF TRUSTED ORIGINS
# ======================================
CSRF_TRUSTED_ORIGINS = os.environ.get(
    "CSRF_TRUSTED_ORIGINS",
    "http://127.0.0.1:8000,http://localhost:8000"
).split(",")

# ======================================
# FILE CLEANUP
# ======================================
CLEANUP_MINUTES = 5

PILLOW_OPTIMIZATION = True
IMAGE_OPTIMIZE_QUALITY = 85
IMAGE_MAX_DIMENSION = 1920

# ======================================
# RATE LIMIT
# ======================================
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = "default"
RATELIMIT_CACHE_PREFIX = "rl:"

# ======================================
# ADMIN URL
# ======================================
ADMIN_URL = "secure-admin-panel-2026/"

# ======================================
# EMAIL SETTINGS
# Render Variables:
# EMAIL_HOST_PASSWORD
# ======================================
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")

DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# ======================================
# LOGGING
# ======================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
}