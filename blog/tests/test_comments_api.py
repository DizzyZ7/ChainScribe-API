from django.test import TestCase

from audit.models import AuditEvent
from blog.models import Article, Comment
from tests.helpers import ApiTestMixin


class CommentCollectionApiTests(ApiTestMixin, TestCase):
    def setUp(self):
        self.owner = self.create_user("article-owner")
        self.commenter = self.create_user("commenter")
        self.other = self.create_user("other-commenter")
        self.article = self.create_article(self.owner)
        self.commenter_headers, _ = self.opaque_header(self.commenter)
        self.owner_headers, _ = self.opaque_header(self.owner)

    def test_public_can_list_comments_on_published_article(self):
        comment = self.create_comment(self.article, self.commenter)

        response = self.client.get(f"/api/v1/articles/{self.article.pk}/comments")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["items"][0]["id"], str(comment.pk))

    def test_comments_on_private_draft_are_hidden_from_non_owner(self):
        draft = self.create_article(self.owner, title="Draft", status=Article.Status.DRAFT)
        self.create_comment(draft, self.owner)

        public = self.client.get(f"/api/v1/articles/{draft.pk}/comments")
        owner = self.client.get(
            f"/api/v1/articles/{draft.pk}/comments",
            **self.owner_headers,
        )

        self.assertEqual(public.status_code, 404)
        self.assertEqual(owner.status_code, 200)

    def test_comment_list_validates_pagination(self):
        response = self.client.get(
            f"/api/v1/articles/{self.article.pk}/comments?offset=-1"
        )

        self.assertEqual(response.status_code, 422)

    def test_authenticated_user_can_create_comment(self):
        response = self.post_json(
            f"/api/v1/articles/{self.article.pk}/comments",
            {"body": "A carefully reviewed comment."},
            **self.commenter_headers,
        )

        self.assertEqual(response.status_code, 201)
        comment = Comment.objects.get(pk=response.json()["id"])
        self.assertEqual(comment.author, self.commenter)
        self.assertTrue(AuditEvent.objects.filter(action="comment.created").exists())

    def test_create_comment_requires_authentication(self):
        response = self.post_json(
            f"/api/v1/articles/{self.article.pk}/comments",
            {"body": "Anonymous mutation."},
        )

        self.assertEqual(response.status_code, 401)
        self.assertFalse(Comment.objects.exists())

    def test_create_comment_rejects_blank_and_mass_assignment(self):
        blank = self.post_json(
            f"/api/v1/articles/{self.article.pk}/comments",
            {"body": "   "},
            **self.commenter_headers,
        )
        forged = self.post_json(
            f"/api/v1/articles/{self.article.pk}/comments",
            {"body": "Forged", "author_id": str(self.other.pk)},
            **self.commenter_headers,
        )

        self.assertEqual(blank.status_code, 422)
        self.assertEqual(forged.status_code, 422)

    def test_cannot_comment_inaccessible_or_missing_article(self):
        draft = self.create_article(self.owner, title="Draft", status=Article.Status.DRAFT)

        hidden = self.post_json(
            f"/api/v1/articles/{draft.pk}/comments",
            {"body": "Not allowed"},
            **self.commenter_headers,
        )
        missing = self.post_json(
            "/api/v1/articles/00000000-0000-0000-0000-000000000000/comments",
            {"body": "No article"},
            **self.commenter_headers,
        )

        self.assertEqual(hidden.status_code, 404)
        self.assertEqual(missing.status_code, 404)


class CommentItemApiTests(ApiTestMixin, TestCase):
    def setUp(self):
        self.article_owner = self.create_user("article-owner")
        self.author = self.create_user("comment-author")
        self.other = self.create_user("comment-other")
        self.article = self.create_article(self.article_owner)
        self.comment = self.create_comment(self.article, self.author)
        self.author_headers, _ = self.opaque_header(self.author)
        self.other_headers, _ = self.opaque_header(self.other)

    def test_get_comment_on_published_article_is_public(self):
        response = self.client.get(f"/api/v1/comments/{self.comment.pk}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["author"]["id"], str(self.author.pk))

    def test_get_missing_or_hidden_comment_returns_404(self):
        draft = self.create_article(
            self.article_owner,
            title="Draft",
            status=Article.Status.DRAFT,
        )
        hidden_comment = self.create_comment(draft, self.article_owner)

        hidden = self.client.get(f"/api/v1/comments/{hidden_comment.pk}")
        missing = self.client.get(
            "/api/v1/comments/00000000-0000-0000-0000-000000000000"
        )

        self.assertEqual(hidden.status_code, 404)
        self.assertEqual(missing.status_code, 404)

    def test_owner_can_patch_comment(self):
        response = self.patch_json(
            f"/api/v1/comments/{self.comment.pk}",
            {"body": "Updated comment."},
            **self.author_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, "Updated comment.")
        self.assertTrue(AuditEvent.objects.filter(action="comment.updated").exists())

    def test_non_owner_cannot_patch_comment(self):
        response = self.patch_json(
            f"/api/v1/comments/{self.comment.pk}",
            {"body": "Hijacked comment."},
            **self.other_headers,
        )

        self.assertEqual(response.status_code, 403)
        self.comment.refresh_from_db()
        self.assertNotEqual(self.comment.body, "Hijacked comment.")
        self.assertTrue(
            AuditEvent.objects.filter(action="comment.updated", outcome="denied").exists()
        )

    def test_patch_rejects_blank_or_extra_article_id(self):
        blank = self.patch_json(
            f"/api/v1/comments/{self.comment.pk}",
            {"body": " "},
            **self.author_headers,
        )
        forged = self.patch_json(
            f"/api/v1/comments/{self.comment.pk}",
            {"body": "Valid body", "article_id": str(self.article.pk)},
            **self.author_headers,
        )

        self.assertEqual(blank.status_code, 422)
        self.assertEqual(forged.status_code, 422)

    def test_owner_can_delete_comment(self):
        response = self.client.delete(
            f"/api/v1/comments/{self.comment.pk}",
            **self.author_headers,
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(action="comment.deleted").exists())

    def test_non_owner_and_anonymous_cannot_delete_comment(self):
        other = self.client.delete(
            f"/api/v1/comments/{self.comment.pk}",
            **self.other_headers,
        )
        anonymous = self.client.delete(f"/api/v1/comments/{self.comment.pk}")

        self.assertEqual(other.status_code, 403)
        self.assertEqual(anonymous.status_code, 401)
        self.assertTrue(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_patch_and_delete_missing_comment_return_404(self):
        missing = "00000000-0000-0000-0000-000000000000"

        patch = self.patch_json(
            f"/api/v1/comments/{missing}",
            {"body": "No object"},
            **self.author_headers,
        )
        delete = self.client.delete(f"/api/v1/comments/{missing}", **self.author_headers)

        self.assertEqual(patch.status_code, 404)
        self.assertEqual(delete.status_code, 404)
