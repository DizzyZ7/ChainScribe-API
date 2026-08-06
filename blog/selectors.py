from uuid import UUID

from django.db.models import Q, QuerySet

from .models import Article, Comment


def can_read_article(article: Article, user) -> bool:
    if article.status == Article.Status.PUBLISHED:
        return True
    return bool(
        getattr(user, "is_authenticated", False)
        and (getattr(user, "is_staff", False) or article.author_id == user.pk)
    )


def available_articles(user) -> QuerySet[Article]:
    queryset = Article.objects.select_related("author", "category")
    if getattr(user, "is_staff", False):
        return queryset
    if getattr(user, "is_authenticated", False):
        return queryset.filter(Q(status=Article.Status.PUBLISHED) | Q(author=user))
    return queryset.filter(status=Article.Status.PUBLISHED)


def filtered_articles(
    *,
    user,
    category_slug: str | None = None,
    status: str | None = None,
    author_id: UUID | None = None,
) -> QuerySet[Article]:
    queryset = available_articles(user)
    if category_slug:
        queryset = queryset.filter(category__slug=category_slug.lower())
    if status:
        queryset = queryset.filter(status=status)
    if author_id:
        queryset = queryset.filter(author_id=author_id)
    return queryset.order_by("-created_at", "-id")


def available_comments(*, article: Article) -> QuerySet[Comment]:
    return Comment.objects.select_related("author", "article", "article__author").filter(
        article=article
    )
