import json

from django.contrib.auth import get_user_model
from ninja_jwt.tokens import RefreshToken

from accounts.services import issue_api_token
from blog.models import Article, Category, Comment


TEST_PASSWORD = "Correct-Horse-Battery-2026!"


class ApiTestMixin:
    def create_user(self, username: str, password: str = TEST_PASSWORD, **kwargs):
        return get_user_model().objects.create_user(username=username, password=password, **kwargs)

    def opaque_header(self, user) -> tuple[dict, str]:
        _, raw_token = issue_api_token(user=user)
        return {"HTTP_AUTHORIZATION": f"Token {raw_token}"}, raw_token

    def jwt_header(self, user) -> tuple[dict, str]:
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)
        return {"HTTP_AUTHORIZATION": f"Bearer {access}"}, access

    def post_json(self, path: str, payload: dict, **headers):
        return self.client.post(
            path,
            data=json.dumps(payload),
            content_type="application/json",
            **headers,
        )

    def patch_json(self, path: str, payload: dict, **headers):
        return self.client.patch(
            path,
            data=json.dumps(payload),
            content_type="application/json",
            **headers,
        )

    def create_category(self, **kwargs):
        defaults = {"name": "Security", "slug": "security", "description": "Security news"}
        defaults.update(kwargs)
        return Category.objects.create(**defaults)

    def create_article(self, author, **kwargs):
        defaults = {
            "title": "Signed release notes",
            "content": "A verified and reproducible release.",
            "status": Article.Status.PUBLISHED,
        }
        defaults.update(kwargs)
        return Article.objects.create(author=author, **defaults)

    def create_comment(self, article, author, **kwargs):
        defaults = {"body": "Useful analysis."}
        defaults.update(kwargs)
        return Comment.objects.create(article=article, author=author, **defaults)
