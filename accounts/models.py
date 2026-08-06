import uuid

from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models
from django.utils import timezone

from .validators import normalize_username, username_validator


class UserManager(DjangoUserManager):
    use_in_migrations = True

    def _create_user(self, username, email, password, **extra_fields):
        return super()._create_user(
            normalize_username(username),
            self.normalize_email(email),
            password,
            **extra_fields,
        )


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(
        max_length=64,
        unique=True,
        validators=[username_validator],
        help_text="Lowercase ASCII letters, numbers, dot, dash and underscore.",
        error_messages={"unique": "A user with that username already exists."},
    )

    objects = UserManager()

    def clean(self):
        self.username = normalize_username(self.username)
        super().clean()

    def save(self, *args, **kwargs):
        self.username = normalize_username(self.username)
        return super().save(*args, **kwargs)


class ApiToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_tokens")
    digest = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=("user", "revoked_at", "expires_at"),
                name="acct_token_state_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{str(self.id)[:8]}"

    @property
    def is_usable(self) -> bool:
        now = timezone.now()
        return self.revoked_at is None and self.expires_at > now and self.user.is_active
