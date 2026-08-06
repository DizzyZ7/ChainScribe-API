from .base import *

DEBUG = env_bool("DJANGO_DEBUG", True)
API_DOCS_ENABLED = env_bool("API_DOCS_ENABLED", True)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
