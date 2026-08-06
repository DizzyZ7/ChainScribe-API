from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse, JsonResponse
from ninja import Router
from ninja.errors import HttpError

from accounts.authentication import dual_auth, optional_dual_auth
from core.errors import error_payload
from core.schemas import ErrorSchema

from .models import Article, Category, Comment
from .schemas import (
    ArticleCreateInput,
    ArticleOutput,
    ArticlePage,
    ArticleUpdateInput,
    CategoryOutput,
    CommentCreateInput,
    CommentOutput,
    CommentPage,
    CommentUpdateInput,
)
from .selectors import available_articles, available_comments, can_read_article, filtered_articles
from .services import (
    create_article,
    create_comment,
    delete_article,
    delete_comment,
    update_article,
    update_comment,
)

router = Router(tags=["Blog"])


def _pagination(limit: int, offset: int) -> tuple[int, int]:
    if not 1 <= limit <= 100 or offset < 0:
        raise HttpError(422, "limit must be between 1 and 100 and offset must be non-negative.")
    return limit, offset


def _category_payload(category: Category | None):
    if category is None:
        return None
    return {
        "id": category.pk,
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
        "is_active": category.is_active,
        "created_at": category.created_at,
        "updated_at": category.updated_at,
    }


def _article_payload(article: Article) -> dict:
    return {
        "id": article.pk,
        "author": {"id": article.author_id, "username": article.author.username},
        "category": _category_payload(article.category),
        "title": article.title,
        "content": article.content,
        "status": article.status,
        "created_at": article.created_at,
        "updated_at": article.updated_at,
    }


def _comment_payload(comment: Comment) -> dict:
    return {
        "id": comment.pk,
        "article_id": comment.article_id,
        "author": {"id": comment.author_id, "username": comment.author.username},
        "body": comment.body,
        "created_at": comment.created_at,
        "updated_at": comment.updated_at,
    }


def _validation_response(request, exc: DjangoValidationError):
    fields = exc.message_dict if hasattr(exc, "message_dict") else {"non_field": exc.messages}
    return JsonResponse(
        error_payload(request, "Object validation failed.", "validation_error", fields),
        status=422,
    )


def _permission_denied(request, entity_type: str, entity_id) -> JsonResponse:
    return JsonResponse(
        error_payload(request, f"You do not own this {entity_type}.", "permission_denied"),
        status=403,
    )


@router.get("/categories", response=list[CategoryOutput], auth=None)
def list_categories(request):
    return [_category_payload(category) for category in Category.objects.filter(is_active=True)]


@router.get("/articles", response=ArticlePage, auth=optional_dual_auth)
def list_articles(
    request,
    limit: int = 20,
    offset: int = 0,
    category: str | None = None,
    status: str | None = None,
    author: UUID | None = None,
):
    limit, offset = _pagination(limit, offset)
    if status is not None and status not in Article.Status.values:
        raise HttpError(422, "status must be draft or published.")
    queryset = filtered_articles(
        user=request.user,
        category_slug=category,
        status=status,
        author_id=author,
    )
    count = queryset.count()
    items = [_article_payload(article) for article in queryset[offset : offset + limit]]
    return {"count": count, "limit": limit, "offset": offset, "items": items}


@router.post(
    "/articles",
    response={201: ArticleOutput, 401: ErrorSchema, 422: ErrorSchema},
    auth=dual_auth,
)
def add_article(request, payload: ArticleCreateInput):
    try:
        article = create_article(
            request=request,
            actor=request.user,
            data=payload.model_dump(),
        )
    except DjangoValidationError as exc:
        return _validation_response(request, exc)
    article = Article.objects.select_related("author", "category").get(pk=article.pk)
    return 201, _article_payload(article)


@router.get(
    "/articles/{article_id}",
    response={200: ArticleOutput, 404: ErrorSchema},
    auth=optional_dual_auth,
)
def get_article(request, article_id: UUID):
    article = available_articles(request.user).filter(pk=article_id).first()
    if article is None:
        raise HttpError(404, "Article not found.")
    return _article_payload(article)


@router.patch(
    "/articles/{article_id}",
    response={
        200: ArticleOutput,
        401: ErrorSchema,
        403: ErrorSchema,
        404: ErrorSchema,
        422: ErrorSchema,
    },
    auth=dual_auth,
)
def patch_article(request, article_id: UUID, payload: ArticleUpdateInput):
    if not Article.objects.filter(pk=article_id).exists():
        raise HttpError(404, "Article not found.")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HttpError(422, "At least one field must be supplied.")
    try:
        article = update_article(
            request=request,
            actor=request.user,
            article_id=article_id,
            changes=changes,
        )
    except PermissionDenied:
        return _permission_denied(request, "article", article_id)
    except DjangoValidationError as exc:
        return _validation_response(request, exc)
    return _article_payload(article)


@router.delete(
    "/articles/{article_id}",
    response={204: None, 401: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema},
    auth=dual_auth,
)
def remove_article(request, article_id: UUID):
    if not Article.objects.filter(pk=article_id).exists():
        raise HttpError(404, "Article not found.")
    try:
        delete_article(request=request, actor=request.user, article_id=article_id)
    except PermissionDenied:
        return _permission_denied(request, "article", article_id)
    return HttpResponse(status=204)


@router.get(
    "/articles/{article_id}/comments",
    response={200: CommentPage, 404: ErrorSchema},
    auth=optional_dual_auth,
)
def list_comments(request, article_id: UUID, limit: int = 20, offset: int = 0):
    limit, offset = _pagination(limit, offset)
    article = available_articles(request.user).filter(pk=article_id).first()
    if article is None:
        raise HttpError(404, "Article not found.")
    queryset = available_comments(article=article)
    count = queryset.count()
    items = [_comment_payload(comment) for comment in queryset[offset : offset + limit]]
    return {"count": count, "limit": limit, "offset": offset, "items": items}


@router.post(
    "/articles/{article_id}/comments",
    response={201: CommentOutput, 401: ErrorSchema, 404: ErrorSchema, 422: ErrorSchema},
    auth=dual_auth,
)
def add_comment(request, article_id: UUID, payload: CommentCreateInput):
    article = Article.objects.select_related("author", "category").filter(pk=article_id).first()
    if article is None or not can_read_article(article, request.user):
        raise HttpError(404, "Article not found.")
    try:
        comment = create_comment(
            request=request,
            actor=request.user,
            article=article,
            body=payload.body,
        )
    except DjangoValidationError as exc:
        return _validation_response(request, exc)
    comment = Comment.objects.select_related("author", "article").get(pk=comment.pk)
    return 201, _comment_payload(comment)


@router.get(
    "/comments/{comment_id}",
    response={200: CommentOutput, 404: ErrorSchema},
    auth=optional_dual_auth,
)
def get_comment(request, comment_id: UUID):
    comment = (
        Comment.objects.select_related("author", "article", "article__author")
        .filter(pk=comment_id)
        .first()
    )
    if comment is None or not can_read_article(comment.article, request.user):
        raise HttpError(404, "Comment not found.")
    return _comment_payload(comment)


@router.patch(
    "/comments/{comment_id}",
    response={
        200: CommentOutput,
        401: ErrorSchema,
        403: ErrorSchema,
        404: ErrorSchema,
        422: ErrorSchema,
    },
    auth=dual_auth,
)
def patch_comment(request, comment_id: UUID, payload: CommentUpdateInput):
    if not Comment.objects.filter(pk=comment_id).exists():
        raise HttpError(404, "Comment not found.")
    try:
        comment = update_comment(
            request=request,
            actor=request.user,
            comment_id=comment_id,
            body=payload.body,
        )
    except PermissionDenied:
        return _permission_denied(request, "comment", comment_id)
    except DjangoValidationError as exc:
        return _validation_response(request, exc)
    return _comment_payload(comment)


@router.delete(
    "/comments/{comment_id}",
    response={204: None, 401: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema},
    auth=dual_auth,
)
def remove_comment(request, comment_id: UUID):
    if not Comment.objects.filter(pk=comment_id).exists():
        raise HttpError(404, "Comment not found.")
    try:
        delete_comment(request=request, actor=request.user, comment_id=comment_id)
    except PermissionDenied:
        return _permission_denied(request, "comment", comment_id)
    return HttpResponse(status=204)
