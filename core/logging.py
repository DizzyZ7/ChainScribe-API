import json
import logging
import re
from datetime import datetime, timezone

JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
OPAQUE_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_-]{256}\b")
AUTH_HEADER_RE = re.compile(r"(?i)(authorization|cookie)\s*[:=]\s*[^\s,;]+")


def redact_text(value: object) -> str:
    text = str(value)
    text = JWT_RE.sub("[REDACTED_JWT]", text)
    text = OPAQUE_TOKEN_RE.sub("[REDACTED_TOKEN]", text)
    return AUTH_HEADER_RE.sub(r"\1=[REDACTED]", text)


class JsonFormatter(logging.Formatter):
    extra_fields = (
        "request_id",
        "method",
        "route",
        "status_code",
        "duration_ms",
        "user_id",
        "entity_type",
        "entity_id",
        "action",
        "outcome",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "event": redact_text(record.getMessage()),
            "logger": record.name,
        }
        for field in self.extra_fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = redact_text(value) if isinstance(value, str) else value
        if record.exc_info:
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
