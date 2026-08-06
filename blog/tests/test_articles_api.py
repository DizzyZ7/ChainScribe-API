from django.test import TestCase

from audit.models import AuditEvent
from blog.models import Article, Comment
from tests.helpers import ApiTestMixin


class CategoryApiTests(ApiTestMixin, TestCase):
    def test_list_categories_returns_only_active_categories(self):
        active = self.create_category()
        self.create_category(name="Hidden", slug="hidden", is_active=False)

        response = self.client.get("/api/v1/categories")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], [str(active.pk)])

    def test_list_categories_has_stable_empty_response(self):
        response = self.client.get("/api/v1/categories")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])


class ArticleCollectionApiTests(ApiTestMixin, TestCase):
    def setUp(self):
        self.owner = self.create_user("article-owner")
        self.other = self.create_user("article-other")
        self.owner_headers, _ = self.opaque_header(self.owner)

    def test_public_list_returns_published_but_not_drafts(self):
        published = self.create_article(self.owner)
        self.create_article(self.owner, title="Private draft", status=Article.Status.DRAFT)

        response = self.client.get("/api/v1/articles")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["items"][0]["id"], str(published.pk))

    def test_authenticated_list_includes_own_drafts_only(self):
        own_draft = self.create_article(
            self.owner,
            title="Own draft",
            status=Article.Status.DRAFT,
        )
        self.create_article(self.other, title="Other draft", status=Article.Status.DRAFT)

        response = self.client.get(
            "/api/v1/articles?status=draft",
            **self.owner_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["items"][0]["id"], str(own_draft.pk))

    def test_list_filters_and_validates_pagination(self):
        category = self.create_category()
        matching = self.create_article(self.owner, category=category)
        self.create_article(self.owner, title="No category")

        filtered = self.client.get("/api/v1/articles?category=security&limit=1&offset=0")
        invalid = self.client.get("/api/v1/articles?limit=101")

        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.json()["items"][0]["id"], str(matching.pk))
        self.assertEqual(invalid.status_code, 422)

    def test_list_avoids_n_plus_one_queries(self):
        category = self.create_category()
        for index in range(5):
            self.create_article(self.owner, category=category, title=f"Article {index}")

        with self.assertNumQueries(2):
            response = self.client.get("/api/v1/articles")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 5)

    def test_create_article_uses_authenticated_owner(self):
        category = self.create_category()
        response = self.post_json(
            "/api/v1/articles",
            {
                "title": "Production checklist",
                "content": "Validate every release boundary.",
                "status": "published",
                "category_id": str(category.pk),
            },
            **self.owner_headers,
        )

        self.assertEqual(response.status_code, 201)
        article = Article.objects.get(pk=response.json()["id"])
        self.assertEqual(article.author, self.owner)
        self.assertEqual(article.category, category)
        self.assertTrue(
            AuditEvent.objects.filter(action="article.created", actor=self.owner).exists()
        )

    def test_create_accepts_jwt_but_rejects_anonymous(self):
        jwt_headers, _ = self.jwt_header(self.owner)
        payload = {"title": "JWT article", "content": "Authenticated by JWT."}

        jwt_response = self.post_json("/api/v1/articles", payload, **jwt_headers)
        anonymous_response = self.post_json("/api/v1/articles", payload)

        self.assertEqual(jwt_response.status_code, 201)
        self.assertEqual(anonymous_response.status_code, 401)

    def test_create_rejects_blank_content_and_mass_assignment(self):
        blank = self.post_json(
            "/api/v1/articles",
            {"title": "Blank", "content": "   "},
            **self.owner_headers,
        )
        forged = self.post_json(
            "/api/v1/articles",
            {
                "title": "Forged",
                "content": "Attempted owner replacement.",
                "author_id": str(self.other.pk),
            },
            **self.owner_headers,
        )

        self.assertEqual(blank.status_code, 422)
        self.assertEqual(forged.status_code, 422)
        self.assertFalse(Article.objects.filter(title="Forged").exists())

    def test_create_rejects_inactive_or_unknown_category(self):
        category = self.create_category(is_active=False)

        response = self.post_json(
            "/api/v1/articles",
            {"title": "Bad category", "content": "Cannot attach.", "category_id": str(category.pk)},
            **self.owner_headers,
        )

        self.assertEqual(response.status_code, 422)


class ArticleItemApiTests(ApiTestMixin, TestCase):
    def setUp(self):
        self.owner = self.create_user("article-owner")
        self.other = self.create_user("article-other")
        self.owner_headers, _ = self.opaque_header(self.owner)
        self.other_headers, _ = self.opaque_header(self.other)

    def test_get_published_article_is_public(self):
        article = self.create_article(self.owner)

        response = self.client.get(f"/api/v1/articles/{article.pk}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["author"]["id"], str(self.owner.pk))

    def test_get_draft_is_only_visible_to_owner(self):
        article = self.create_article(self.owner, status=Article.Status.DRAFT)

        public = self.client.get(f"/api/v1/articles/{article.pk}")
        other = self.client.get(f"/api/v1/articles/{article.pk}", **self.other_headers)
        owner = self.client.get(f"/api/v1/articles/{article.pk}", **self.owner_headers)

        self.assertEqual(public.status_code, 404)
        self.assertEqual(other.status_code, 404)
        self.assertEqual(owner.status_code, 200)

    def test_get_missing_article_returns_standard_404(self):
        response = self.client.get("/api/v1/articles/00000000-0000-0000-0000-000000000000")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "not_found")

    def test_owner_can_patch_article(self):
        article = self.create_article(self.owner, status=Article.Status.DRAFT)

        response = self.patch_json(
            f"/api/v1/articles/{article.pk}",
            {"title": "Updated safely", "status": "published"},
            **self.owner_headers,
        )

        self.assertEqual(response.status_code, 200)
        article.refresh_from_db()
        self.assertEqual(article.title, "Updated safely")
        self.assertEqual(article.status, Article.Status.PUBLISHED)
        self.assertTrue(
            AuditEvent.objects.filter(action="article.updated", actor=self.owner).exists()
        )

    def test_non_owner_cannot_patch_article(self):
        article = self.create_article(self.owner)

        response = self.patch_json(
            f"/api/v1/articles/{article.pk}",
            {"title": "Hijacked"},
            **self.other_headers,
        )

        self.assertEqual(response.status_code, 403)
        article.refresh_from_db()
        self.assertNotEqual(article.title, "Hijacked")
        self.assertTrue(
            AuditEvent.objects.filter(action="article.updated", outcome="denied").exists()
        )

    def test_patch_rejects_empty_payload_and_author_id(self):
        article = self.create_article(self.owner)

        empty = self.patch_json(f"/api/v1/articles/{article.pk}", {}, **self.owner_headers)
        forged = self.patch_json(
            f"/api/v1/articles/{article.pk}",
            {"author_id": str(self.other.pk)},
            **self.owner_headers,
        )

        self.assertEqual(empty.status_code, 422)
        self.assertEqual(forged.status_code, 422)

    def test_owner_can_delete_article_and_comments(self):
        article = self.create_article(self.owner)
        self.create_comment(article, self.owner)

        response = self.client.delete(
            f"/api/v1/articles/{article.pk}",
            **self.owner_headers,
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Article.objects.filter(pk=article.pk).exists())
        self.assertFalse(Comment.objects.exists())
        self.assertTrue(AuditEvent.objects.filter(action="article.deleted").exists())

    def test_non_owner_and_anonymous_cannot_delete_article(self):
        article = self.create_article(self.owner)

        other = self.client.delete(
            f"/api/v1/articles/{article.pk}",
            **self.other_headers,
        )
        anonymous = self.client.delete(f"/api/v1/articles/{article.pk}")

        self.assertEqual(other.status_code, 403)
        self.assertEqual(anonymous.status_code, 401)
        self.assertTrue(Article.objects.filter(pk=article.pk).exists())

    def test_patch_and_delete_missing_article_return_404(self):
        missing = "00000000-0000-0000-0000-000000000000"

        patch = self.patch_json(
            f"/api/v1/articles/{missing}",
            {"title": "No object"},
            **self.owner_headers,
        )
        delete = self.client.delete(f"/api/v1/articles/{missing}", **self.owner_headers)

        self.assertEqual(patch.status_code, 404)
        self.assertEqual(delete.status_code, 404)
