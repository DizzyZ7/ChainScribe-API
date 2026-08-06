#!/usr/bin/env python
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE_URL = os.getenv("CHAIN_SCRIBE_BASE_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
if urllib.parse.urlsplit(BASE_URL).scheme not in {"http", "https"}:
    raise SystemExit("CHAIN_SCRIBE_BASE_URL must use http or https")


def request(method: str, path: str, payload=None, token: str | None = None, expected=(200,)):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Token {token}"
    req = urllib.request.Request(  # noqa: S310 - BASE_URL scheme is validated above
        f"{BASE_URL}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(  # noqa: S310 - request URL is scheme-validated
            req, timeout=10
        ) as response:
            status = response.status
            raw = response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read()
    if status not in expected:
        safe_body = raw.decode(errors="replace")[:500]
        raise RuntimeError(f"{method} {path} returned {status}: {safe_body}")
    return json.loads(raw) if raw else {}


def main() -> int:
    suffix = uuid.uuid4().hex[:10]
    credentials = {
        "username": f"smoke-{suffix}",
        "password": f"Smoke-{suffix}-Correct-Horse-2026!",
    }
    registration = request("POST", "/auth/register", credentials, expected=(201,))
    token = registration["token"]
    request("GET", "/auth/me", token=token)
    article = request(
        "POST",
        "/articles",
        {"title": "Smoke article", "content": "End-to-end verification.", "status": "published"},
        token=token,
        expected=(201,),
    )
    request(
        "PATCH",
        f"/articles/{article['id']}",
        {"title": "Verified smoke article"},
        token=token,
    )
    comment = request(
        "POST",
        f"/articles/{article['id']}/comments",
        {"body": "Smoke comment."},
        token=token,
        expected=(201,),
    )
    request("DELETE", f"/comments/{comment['id']}", token=token, expected=(204,))
    request("DELETE", f"/articles/{article['id']}", token=token, expected=(204,))
    request("POST", "/auth/logout", {}, token=token, expected=(204,))
    request("GET", "/auth/me", token=token, expected=(401,))
    print("ChainScribe smoke journey passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
