import re
import unicodedata

from django.core.validators import RegexValidator

USERNAME_PATTERN = re.compile(r"^[a-z0-9_.-]+$")
username_validator = RegexValidator(
    regex=USERNAME_PATTERN,
    message="Username may contain only lowercase ASCII letters, numbers, dot, dash and underscore.",
    code="invalid_username",
)


def normalize_username(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().lower()
