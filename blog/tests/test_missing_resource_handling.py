from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase

from blog.models import Article, Comment


class MissingResourceMutationTests(TestCase):
    """A deletion between lookup and mutation must produce 404, not 500."""

    def test_missing_article_on_patch(self):
        from blog.api import patch_article
        from blog.schemas import ArticleUpdateInput

        request = type("Request", (), {"user": object()})()
        with patch("blog.api.update_article", side_effect=Article.DoesNotExist):
            with self.assertRaises(Exception) as caught:
                patch_article(request, uuid4(), ArticleUpdateInput(title="Updated"))
        self.assertEqual(getattr(caught.exception, "status_code", None), 404)

    def test_missing_article_on_delete(self):
        from blog.api import remove_article

        request = type("Request", (), {"user": object()})()
        with patch("blog.api.delete_article", side_effect=Article.DoesNotExist):
            with self.assertRaises(Exception) as caught:
                remove_article(request, uuid4())
        self.assertEqual(getattr(caught.exception, "status_code", None), 404)

    def test_missing_comment_on_patch(self):
        from blog.api import patch_comment
        from blog.schemas import CommentUpdateInput

        request = type("Request", (), {"user": object()})()
        with patch("blog.api.update_comment", side_effect=Comment.DoesNotExist):
            with self.assertRaises(Exception) as caught:
                patch_comment(request, uuid4(), CommentUpdateInput(body="Updated"))
        self.assertEqual(getattr(caught.exception, "status_code", None), 404)

    def test_missing_comment_on_delete(self):
        from blog.api import remove_comment

        request = type("Request", (), {"user": object()})()
        with patch("blog.api.delete_comment", side_effect=Comment.DoesNotExist):
            with self.assertRaises(Exception) as caught:
                remove_comment(request, uuid4())
        self.assertEqual(getattr(caught.exception, "status_code", None), 404)
