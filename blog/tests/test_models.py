from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from blog.models import Article, Comment
from tests.helpers import ApiTestMixin


class BlogModelIntegrityTests(ApiTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user("model-owner")

    def test_blank_article_is_blocked_by_database_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Article.objects.create(author=self.user, title="", content="content")

    def test_blank_comment_is_blocked_by_database_constraint(self):
        article = self.create_article(self.user)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Comment.objects.create(article=article, author=self.user, body="")

    def test_category_with_articles_is_protected(self):
        category = self.create_category()
        self.create_article(self.user, category=category)

        with self.assertRaises(ProtectedError):
            category.delete()

    def test_author_with_content_is_protected(self):
        self.create_article(self.user)

        with self.assertRaises(ProtectedError):
            self.user.delete()

    def test_article_delete_cascades_comments(self):
        article = self.create_article(self.user)
        self.create_comment(article, self.user)

        article.delete()

        self.assertFalse(Comment.objects.exists())
