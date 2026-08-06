from .base import *


DEBUG = False
API_DOCS_ENABLED = False
RATE_LIMIT_ENABLED = env_bool("RATE_LIMIT_ENABLED", False)

if env_bool("USE_SQLITE_FOR_TESTS", False):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "test.sqlite3",
        }
    }

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "chainscribe-tests",
    }
}

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
