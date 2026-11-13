"""Bounded GitHub OAuth exchange. Provider tokens never leave this module."""

import json
import logging
import time

import requests
from cryptography.fernet import InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import validate_email
from django.views.decorators.debug import sensitive_variables
from urllib3.exceptions import HTTPError as Urllib3HTTPError

from apps.accounts.github_browser import GithubRejected, GithubUnavailable

logger = logging.getLogger(__name__)


@sensitive_variables()
def github_claims(row, attempt, code):
    try:
        secret = row.get_github_client_secret()
    except (InvalidToken, ImproperlyConfigured, ValueError, UnicodeError):
        logger.warning("github_credentials_unavailable")
        raise GithubUnavailable() from None
    token = _json_request(
        "post", "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={"client_id": row.github_client_id, "client_secret": secret,
              "code": code, "redirect_uri": attempt.redirect_uri,
              "code_verifier": attempt.code_verifier},
    )
    if not isinstance(token, dict):
        raise GithubUnavailable()
    if token.get("error"):
        raise GithubRejected()
    access = token.get("access_token")
    if not isinstance(access, str) or not access or len(access) > 4096 or not access.isascii() or any(
        char.isspace() or ord(char) < 33 or ord(char) == 127 for char in access
    ):
        raise GithubUnavailable()
    headers = {"Authorization": f"Bearer {access}",
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "SpaceWorks"}
    user = _json_request("get", "https://api.github.com/user", headers=headers)
    emails = _json_request("get", "https://api.github.com/user/emails", headers=headers)
    if not isinstance(user, dict) or not isinstance(emails, list):
        raise GithubUnavailable()
    subject = user.get("id")
    if type(subject) is not int or subject <= 0:
        raise GithubUnavailable()
    primary = next((item.get("email") for item in emails if isinstance(item, dict)
                    and item.get("primary") is True and item.get("verified") is True), None)
    if not isinstance(primary, str) or len(primary) > 254:
        raise GithubRejected()
    try:
        validate_email(primary)
    except ValidationError:
        raise GithubRejected() from None
    name = user.get("name") or user.get("login") or ""
    if not isinstance(name, str):
        raise GithubUnavailable()
    return {"sub": str(subject), "email": primary, "email_verified": True, "name": name[:200]}


@sensitive_variables()
def _json_request(method, url, *, headers, data=None):
    response = None
    started = time.monotonic()
    try:
        response = getattr(requests, method)(
            url, headers=headers, data=data, timeout=settings.OIDC_HTTP_TIMEOUT_SECONDS,
            stream=True, allow_redirects=False,
        )
        if response.status_code != 200:
            raise GithubUnavailable()
        if int(response.headers.get("Content-Length") or 0) > settings.OIDC_HTTP_MAX_BYTES:
            raise GithubUnavailable()
        # decode_content: GitHub may gzip; the bound applies to the decoded bytes.
        body = response.raw.read(settings.OIDC_HTTP_MAX_BYTES + 1, decode_content=True)
        if len(body) > settings.OIDC_HTTP_MAX_BYTES or (
            time.monotonic() - started > settings.OIDC_HTTP_TIMEOUT_SECONDS
        ):
            raise GithubUnavailable()
        return json.loads(body)
    except (requests.RequestException, Urllib3HTTPError, OSError, ValueError, TypeError):
        # Never log the response body, request headers, token, code or client secret.
        logger.warning("github_http_unavailable", extra={"operation": method})
        raise GithubUnavailable() from None
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                logger.warning("github_response_close_failed")
