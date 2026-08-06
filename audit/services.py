import json
import logging
from collections.abc import Mapping
from typing import Any

from django.contrib.auth.models import AnonymousUser

from .models import AuditEvent


logger = logging.getLogger("chainscribe.audit")
SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "jwt",
    "password",
    "password_hash",
    "refresh",
    "secret",
    "token",
}


def _sanitize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if str(key).lower() in SENSITIVE_KEYS else _sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value[:50]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def record_audit(
    *,
    request=None,
    actor=None,
    action: str,
    entity_type: str,
    entity_id: object = "",
    outcome: str = AuditEvent.Outcome.SUCCESS,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    if isinstance(actor, AnonymousUser) or not getattr(actor, "is_authenticated", False):
        actor = None
    request_id = getattr(request, "request_id", None) if request is not None else None
    safe_metadata = _sanitize(metadata or {})
    if len(json.dumps(safe_metadata, default=str)) > 4096:
        safe_metadata = {"truncated": True}

    event = AuditEvent.objects.create(
        request_id=request_id,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id)[:64],
        outcome=outcome,
        metadata=safe_metadata,
    )
    logger.info(
        "audit.event",
        extra={
            "request_id": str(request_id) if request_id else None,
            "user_id": str(actor.pk) if actor else None,
            "entity_type": entity_type,
            "entity_id": str(entity_id)[:64],
            "action": action,
            "outcome": outcome,
        },
    )
    return event
