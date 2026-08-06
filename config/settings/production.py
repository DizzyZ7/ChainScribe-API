import os

from django.core.exceptions import ImproperlyConfigured

from .base import *


DEBUG = False
API_DOCS_ENABLED = env_bool("API_DOCS_ENABLED", False)

required = {
    "DJANGO_SECRET_KEY": os.getenv("DJANGO_SECRET_KEY"),
    "JWT_SIGNING_KEY": os.getenv("JWT_SIGNING_KEY"),
    "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD"),
    "REDIS_URL": os.getenv("REDIS_URL"),
}
missing = sorted(name for name, value in required.items() if not value)
if missing:
    raise ImproperlyConfigured(
        "Missing required production environment variables: " + ", ".join(missing)
    )

SECRET_KEY = required["DJANGO_SECRET_KEY"]
NINJA_JWT["SIGNING_KEY"] = required["JWT_SIGNING_KEY"]

if len(SECRET_KEY) < 50 or len(NINJA_JWT["SIGNING_KEY"]) < 32:
    raise ImproperlyConfigured("Production signing secrets are too short")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31_536_000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

if TRUST_PROXY_HEADERS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not CORS_ALLOWED_ORIGINS:
    raise ImproperlyConfigured("CORS_ALLOWED_ORIGINS must be configured in production")
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must be configured in production")
