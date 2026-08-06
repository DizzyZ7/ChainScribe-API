from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from blog.models import Article, Category, Comment
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

    def test_model_clean_methods_trim_and_validate_text(self):
        category = Category(name="  Security  ", slug="  SECURITY  ", description="  News  ")
        category.clean()
        category.full_clean()
        category.save()
        article = Article(
            author=self.user, category=category, title="  Title  ", content="  Body  "
        )
        article.full_clean()
        article.save()
        comment = Comment(article=article, author=self.user, body="  Reviewed  ")
        comment.full_clean()
        comment.save()

        self.assertEqual(
            (category.name, category.slug, category.description), ("Security", "security", "News")
        )
        self.assertEqual((article.title, article.content), ("Title", "Body"))
        self.assertEqual(comment.body, "Reviewed")
        self.assertEqual(str(category), "Security")
        self.assertEqual(str(article), "Title")
        self.assertIn(str(comment.pk), str(comment))

    def test_model_clean_methods_reject_whitespace_only_text(self):
        with self.assertRaises(ValidationError):
            Category(name=" ", slug="valid").full_clean()
        with self.assertRaises(ValidationError):
            Article(author=self.user, title=" ", content=" ").full_clean()
        article = self.create_article(self.user)
        with self.assertRaises(ValidationError):
            Comment(article=article, author=self.user, body=" ").full_clean()
