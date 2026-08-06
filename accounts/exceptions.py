class DuplicateUsernameError(Exception):
    """Raised when normalized username uniqueness would be violated."""


class InvalidCredentialsError(Exception):
    """Raised for a generic username/password authentication failure."""
