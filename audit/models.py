import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ImmutableAuditQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Audit events are immutable.")

    def delete(self):
        raise ValidationError("Audit events are immutable.")


class ImmutableAuditManager(models.Manager.from_queryset(ImmutableAuditQuerySet)):
    use_in_migrations = True


class AuditEvent(models.Model):
    class Outcome(models.TextChoices):
        SUCCESS = "success", "Success"
        DENIED = "denied", "Denied"
        FAILURE = "failure", "Failure"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    request_id = models.UUIDField(null=True, blank=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(max_length=80, db_index=True)
    entity_type = models.CharField(max_length=80, db_index=True)
    entity_id = models.CharField(max_length=64, blank=True)
    outcome = models.CharField(max_length=16, choices=Outcome.choices, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    objects = ImmutableAuditManager()

    class Meta:
        ordering = ("-timestamp",)
        indexes = [
            models.Index(fields=("entity_type", "entity_id"), name="audit_entity_idx"),
            models.Index(fields=("actor", "timestamp"), name="audit_actor_time_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Audit events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit events are immutable.")

    def __str__(self) -> str:
        return f"{self.timestamp:%Y-%m-%d %H:%M:%S} {self.action}"
