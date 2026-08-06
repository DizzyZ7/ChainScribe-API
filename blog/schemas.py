from datetime import datetime
from uuid import UUID

from ninja import Schema
from pydantic import ConfigDict, Field, field_validator

from .models import ARTICLE_CONTENT_MAX_LENGTH, COMMENT_BODY_MAX_LENGTH, Article


class UserSummary(Schema):
    id: UUID
    username: str


class CategoryOutput(Schema):
    id: UUID
    name: str
    slug: str
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ArticleCreateInput(Schema):
    model_config = ConfigDict(extra="forbid")

    category_id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=ARTICLE_CONTENT_MAX_LENGTH)
    status: str = Article.Status.DRAFT

    @field_validator("title", "content")
    @classmethod
    def strip_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank.")
        return value

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str) -> str:
        if value not in Article.Status.values:
            raise ValueError("Status must be draft or published.")
        return value


class ArticleUpdateInput(Schema):
    model_config = ConfigDict(extra="forbid")

    category_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(
        default=None,
        min_length=1,
        max_length=ARTICLE_CONTENT_MAX_LENGTH,
    )
    status: str | None = None

    @field_validator("title", "content")
    @classmethod
    def strip_non_empty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank.")
        return value

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str | None) -> str | None:
        if value is not None and value not in Article.Status.values:
            raise ValueError("Status must be draft or published.")
        return value


class ArticleOutput(Schema):
    id: UUID
    author: UserSummary
    category: CategoryOutput | None
    title: str
    content: str
    status: str
    created_at: datetime
    updated_at: datetime


class ArticlePage(Schema):
    count: int
    limit: int
    offset: int
    items: list[ArticleOutput]


class CommentCreateInput(Schema):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=COMMENT_BODY_MAX_LENGTH)

    @field_validator("body")
    @classmethod
    def strip_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Comment cannot be blank.")
        return value


class CommentUpdateInput(Schema):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=COMMENT_BODY_MAX_LENGTH)

    @field_validator("body")
    @classmethod
    def strip_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Comment cannot be blank.")
        return value


class CommentOutput(Schema):
    id: UUID
    article_id: UUID
    author: UserSummary
    body: str
    created_at: datetime
    updated_at: datetime


class CommentPage(Schema):
    count: int
    limit: int
    offset: int
    items: list[CommentOutput]
