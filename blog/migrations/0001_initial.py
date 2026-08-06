import uuid

import django.core.validators
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
                ("slug", models.SlugField(max_length=120, unique=True)),
                (
                    "description",
                    models.TextField(
                        blank=True, validators=[django.core.validators.MaxLengthValidator(2000)]
                    ),
                ),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name_plural": "categories", "ordering": ("name", "id")},
        ),
        migrations.CreateModel(
            name="Article",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("title", models.CharField(max_length=200)),
                (
                    "content",
                    models.TextField(
                        validators=[django.core.validators.MaxLengthValidator(100000)]
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("draft", "Draft"), ("published", "Published")],
                        db_index=True,
                        default="draft",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="articles",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="articles",
                        to="blog.category",
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "-id"),
                "indexes": [
                    models.Index(fields=["status", "created_at"], name="article_status_time_idx"),
                    models.Index(fields=["author", "created_at"], name="article_author_time_idx"),
                    models.Index(fields=["category", "created_at"], name="article_cat_time_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("title", ""), _negated=True),
                        name="article_title_not_empty",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("content", ""), _negated=True),
                        name="article_content_not_empty",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Comment",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                (
                    "body",
                    models.TextField(validators=[django.core.validators.MaxLengthValidator(5000)]),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "article",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comments",
                        to="blog.article",
                    ),
                ),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="comments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("created_at", "id"),
                "indexes": [
                    models.Index(
                        fields=["article", "created_at"], name="comment_article_time_idx"
                    ),
                    models.Index(
                        fields=["author", "created_at"], name="comment_author_time_idx"
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("body", ""), _negated=True),
                        name="comment_body_not_empty",
                    )
                ],
            },
        ),
    ]
