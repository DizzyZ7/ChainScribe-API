from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from audit.services import record_audit

from .models import Article, Category, Comment


def _active_category(category_id):
    if category_id is None:
        return None
    try:
        return Category.objects.get(pk=category_id, is_active=True)
    except Category.DoesNotExist as exc:
        raise ValidationError({"category_id": "Active category was not found."}) from exc


@transaction.atomic
def create_article(*, request, actor, data: dict) -> Article:
    article = Article(
        author=actor,
        category=_active_category(data.get("category_id")),
        title=data["title"],
        content=data["content"],
        status=data.get("status", Article.Status.DRAFT),
    )
    article.full_clean()
    article.save()
    record_audit(
        request=request,
        actor=actor,
        action="article.created",
        entity_type="article",
        entity_id=article.pk,
    )
    return article


@transaction.atomic
def update_article(*, request, actor, article_id, changes: dict) -> Article:
    article = (
        Article.objects.select_for_update()
        .select_related("author", "category")
        .get(pk=article_id)
    )
    if article.author_id != actor.pk:
        record_audit(
            request=request,
            actor=actor,
            action="article.updated",
            entity_type="article",
            entity_id=article.pk,
            outcome="denied",
        )
        raise PermissionDenied
    if "category_id" in changes:
        article.category = _active_category(changes.pop("category_id"))
    for field in ("title", "content", "status"):
        if field in changes:
            setattr(article, field, changes[field])
    article.full_clean()
    article.save()
    record_audit(
        request=request,
        actor=actor,
        action="article.updated",
        entity_type="article",
        entity_id=article.pk,
    )
    return article


@transaction.atomic
def delete_article(*, request, actor, article_id) -> None:
    article = Article.objects.select_for_update().get(pk=article_id)
    if article.author_id != actor.pk:
        record_audit(
            request=request,
            actor=actor,
            action="article.deleted",
            entity_type="article",
            entity_id=article.pk,
            outcome="denied",
        )
        raise PermissionDenied
    entity_id = article.pk
    article.delete()
    record_audit(
        request=request,
        actor=actor,
        action="article.deleted",
        entity_type="article",
        entity_id=entity_id,
    )


@transaction.atomic
def create_comment(*, request, actor, article: Article, body: str) -> Comment:
    comment = Comment(article=article, author=actor, body=body)
    comment.full_clean()
    comment.save()
    record_audit(
        request=request,
        actor=actor,
        action="comment.created",
        entity_type="comment",
        entity_id=comment.pk,
        metadata={"article_id": str(article.pk)},
    )
    return comment


@transaction.atomic
def update_comment(*, request, actor, comment_id, body: str) -> Comment:
    comment = (
        Comment.objects.select_for_update()
        .select_related("author", "article", "article__author")
        .get(pk=comment_id)
    )
    if comment.author_id != actor.pk:
        record_audit(
            request=request,
            actor=actor,
            action="comment.updated",
            entity_type="comment",
            entity_id=comment.pk,
            outcome="denied",
        )
        raise PermissionDenied
    comment.body = body
    comment.full_clean()
    comment.save()
    record_audit(
        request=request,
        actor=actor,
        action="comment.updated",
        entity_type="comment",
        entity_id=comment.pk,
    )
    return comment


@transaction.atomic
def delete_comment(*, request, actor, comment_id) -> None:
    comment = Comment.objects.select_for_update().get(pk=comment_id)
    if comment.author_id != actor.pk:
        record_audit(
            request=request,
            actor=actor,
            action="comment.deleted",
            entity_type="comment",
            entity_id=comment.pk,
            outcome="denied",
        )
        raise PermissionDenied
    entity_id = comment.pk
    comment.delete()
    record_audit(
        request=request,
        actor=actor,
        action="comment.deleted",
        entity_type="comment",
        entity_id=entity_id,
    )
