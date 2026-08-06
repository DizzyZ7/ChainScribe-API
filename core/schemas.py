from typing import Any

from ninja import Schema


class ErrorSchema(Schema):
    detail: str
    code: str
    request_id: str
    fields: list[dict[str, Any]] | dict[str, Any] | None = None


class HealthSchema(Schema):
    status: str
    service: str
    version: str
