import logging

from django.db import connections
from ninja import Router

from .schemas import ErrorSchema, HealthSchema


router = Router(tags=["System"])
logger = logging.getLogger("chainscribe.health")


@router.get("/health/live", response={200: HealthSchema}, auth=None)
def live(request):
    return {"status": "ok", "service": "chainscribe-api", "version": "1.0.0"}


@router.get("/health/ready", response={200: HealthSchema, 503: ErrorSchema}, auth=None)
def ready(request):
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.warning(
            "health.database_unavailable",
            extra={"request_id": str(request.request_id), "outcome": "failure"},
        )
        return 503, {
            "detail": "Service is not ready.",
            "code": "database_unavailable",
            "request_id": str(request.request_id),
        }
    return {"status": "ok", "service": "chainscribe-api", "version": "1.0.0"}
