import uuid

import audit.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("timestamp", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("request_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("action", models.CharField(db_index=True, max_length=80)),
                ("entity_type", models.CharField(db_index=True, max_length=80)),
                ("entity_id", models.CharField(blank=True, max_length=64)),
                (
                    "outcome",
                    models.CharField(
                        choices=[
                            ("success", "Success"),
                            ("denied", "Denied"),
                            ("failure", "Failure"),
                        ],
                        db_index=True,
                        max_length=16,
                    ),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-timestamp",),
                "indexes": [
                    models.Index(fields=["entity_type", "entity_id"], name="audit_entity_idx"),
                    models.Index(fields=["actor", "timestamp"], name="audit_actor_time_idx"),
                ],
            },
            managers=[("objects", audit.models.ImmutableAuditManager())],
        )
    ]
