import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.db import models

ARTICLE_CONTENT_MAX_LENGTH = 100_000
COMMENT_BODY_MAX_LENGTH = 5_000


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True, validators=[MaxLengthValidator(2_000)])
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name

    def clean(self):
        self.name = self.name.strip()
        self.slug = self.slug.strip().lower()
        self.description = self.description.strip()
        if not self.name:
            raise ValidationError({"name": "Name cannot be blank."})
        super().clean()


class Article(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="articles",
    )
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="articles",
    )
    title = models.CharField(max_length=200)
    content = models.TextField(validators=[MaxLengthValidator(ARTICLE_CONTENT_MAX_LENGTH)])
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(condition=~models.Q(title=""), name="article_title_not_empty"),
            models.CheckConstraint(
                condition=~models.Q(content=""), name="article_content_not_empty"
            ),
        ]
        indexes = [
            models.Index(fields=("status", "created_at"), name="article_status_time_idx"),
            models.Index(fields=("author", "created_at"), name="article_author_time_idx"),
            models.Index(fields=("category", "created_at"), name="article_cat_time_idx"),
        ]

    def __str__(self) -> str:
        return self.title

    def clean(self):
        self.title = self.title.strip()
        self.content = self.content.strip()
        errors = {}
        if not self.title:
            errors["title"] = "Title cannot be blank."
        if not self.content:
            errors["content"] = "Content cannot be blank."
        if errors:
            raise ValidationError(errors)
        super().clean()


class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="comments",
    )
    body = models.TextField(validators=[MaxLengthValidator(COMMENT_BODY_MAX_LENGTH)])
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.CheckConstraint(condition=~models.Q(body=""), name="comment_body_not_empty")
        ]
        indexes = [
            models.Index(fields=("article", "created_at"), name="comment_article_time_idx"),
            models.Index(fields=("author", "created_at"), name="comment_author_time_idx"),
        ]

    def __str__(self) -> str:
        return f"Comment {self.id}"

    def clean(self):
        self.body = self.body.strip()
        if not self.body:
            raise ValidationError({"body": "Comment cannot be blank."})
        super().clean()
