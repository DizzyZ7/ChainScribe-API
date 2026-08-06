import os

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register


@register(Tags.security, deploy=True)
def production_security_checks(app_configs, **kwargs):
    issues = []
    if settings.DEBUG:
        issues.append(Warning("DEBUG is enabled.", id="chainscribe.W001"))
    if "*" in settings.ALLOWED_HOSTS:
        issues.append(Error("Wildcard ALLOWED_HOSTS is forbidden.", id="chainscribe.E001"))
    if getattr(settings, "CORS_ALLOW_ALL_ORIGINS", False):
        issues.append(Error("Wildcard CORS is forbidden.", id="chainscribe.E002"))
    if os.getenv("DJANGO_SETTINGS_MODULE", "").endswith("production"):
        backend = settings.CACHES["default"]["BACKEND"]
        if "LocMemCache" in backend:
            issues.append(
                Error("Production rate limiting requires a shared cache.", id="chainscribe.E003")
            )
        if getattr(settings, "API_DOCS_ENABLED", False):
            issues.append(Warning("API documentation is enabled.", id="chainscribe.W002"))
    return issues
