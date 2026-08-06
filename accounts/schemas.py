from datetime import datetime
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from ninja import Schema
from pydantic import ConfigDict, Field, SecretStr, field_validator

from .validators import normalize_username, username_validator


class RegisterInput(Schema):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        normalized = normalize_username(value)
        try:
            username_validator(normalized)
        except DjangoValidationError as exc:
            raise ValueError(exc.messages[0]) from exc
        return normalized


class LoginInput(Schema):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=128)


class UserOutput(Schema):
    id: UUID
    username: str
    date_joined: datetime


class OpaqueTokenOutput(Schema):
    token: str
    token_type: str = "Token"
    expires_at: datetime
    user: UserOutput
