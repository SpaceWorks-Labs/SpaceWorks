"""Slack room compatibility, workspace OIDC proof and personal bot delivery."""
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode
from uuid import NAMESPACE_URL, uuid5, uuid4

import jwt
from django.utils.crypto import constant_time_compare

from .notification_providers import CallbackEvent, EndpointProof, ProviderResult
from .notification_slack_http import api, credentials_for, failure_result, live_endpoint, message_text, room, ProviderFailure
from .notification_slack_oauth import read_state, redirect_uri, state_for, pkce, verifier


def slack_api(method, *, token="", data=None):
    value = api("POST", f"https://slack.com/api/{method}", token=token, data=data)
    if value.get("ok") is not True:
        error = value.get("error")
        if error in {"ratelimited", "rate_limited"}:
            raise ProviderFailure("rate_limited", retryable=True, retry_after=60)
        if error in {"user_not_found", "user_not_visible", "account_inactive", "channel_not_found",
                     "cannot_dm_bot", "users_not_found", "invalid_auth", "token_revoked", "not_authed"}:
            raise ProviderFailure("invalid_endpoint")
        raise ProviderFailure("provider_error")
    return value


def signed_request(request, secret):
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    try:
        if not secret or abs(time.time() - int(timestamp)) > 300:
            return False
        expected = "v0=" + hmac.new(secret.encode(), b"v0:" + timestamp.encode() + b":" + request.body,
                                    hashlib.sha256).hexdigest()
        return constant_time_compare(expected, signature)
    except (ValueError, TypeError, UnicodeError):
        return False


def workspace_identity(team_id):
    # Workspace IDs live encrypted in credentials; only an opaque routing identity
    # is exposed by the frozen configuration API.
    return "slack:" + hashlib.sha256(team_id.encode()).hexdigest()


class SlackProvider:
    channel = "slack"

    def __init__(self, config):
        self.config = config

    def start_challenge(self, challenge, code):
        credentials = credentials_for(self.config)
        if not credentials.get("client_id") or not credentials.get("client_secret") or not credentials.get("bot_token"):
            raise ProviderFailure("not_configured")
        if workspace_identity(credentials.get("team_id", "")) != self.config.integration_identity:
            raise ProviderFailure("not_configured")
        return {"connect_url": "https://slack.com/openid/connect/authorize?" + urlencode({
            "client_id": credentials["client_id"], "response_type": "code", "scope": "openid profile",
            "team": credentials["team_id"], "nonce": verifier(code),
            "redirect_uri": redirect_uri("slack", self.config.makerspace_id), "state": state_for(challenge, code)})}

    def verify_callback(self, request):
        try:
            if (request.method == "GET" or request.path.endswith("/oauth/callback")
                    or getattr(getattr(request, "user", None), "is_authenticated", False)):
                data = request.query_params if request.method == "GET" else request.data
                if data.get("state"):
                    return self.oauth_proof(data, getattr(getattr(request, "user", None), "pk", None))
            if signed_request(request, credentials_for(self.config).get("signing_secret", "")):
                # Events/interactivity acknowledge only; never a decision surface.
                return CallbackEvent()
        except Exception:
            return None
        return None

    def oauth_proof(self, data, user_id=None):
        _, proof_code = read_state(self.config, data["state"], user_id=user_id)
        creds = credentials_for(self.config)
        tokens = api("POST", "https://slack.com/api/openid.connect.token", form=True, data={
            "client_id": creds["client_id"], "client_secret": creds["client_secret"],
            "code": data["code"], "redirect_uri": redirect_uri("slack", self.config.makerspace_id), "grant_type": "authorization_code"})
        header = jwt.get_unverified_header(tokens["id_token"])
        keys = api("GET", "https://slack.com/openid/connect/keys")["keys"]
        key = next(key for key in keys if key.get("kid") == header.get("kid") and key.get("kty") == "RSA")
        claims = jwt.decode(tokens["id_token"], jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key)),
            algorithms=["RS256"], audience=creds["client_id"], issuer="https://slack.com",
            options={"require": ["exp", "iat", "sub", "nonce"]})
        if not constant_time_compare(claims["nonce"], verifier(proof_code)):
            return None
        identity = slack_api("openid.connect.userInfo", token=tokens["access_token"])
        team, user = identity.get("https://slack.com/team_id"), identity.get("https://slack.com/user_id")
        if (not team or not user or team != creds.get("team_id")
                or workspace_identity(team) != self.config.integration_identity
                or identity.get("sub") != claims["sub"]
                or claims.get("https://slack.com/team_id") != team
                or claims.get("https://slack.com/user_id") != user):
            return None
        return CallbackEvent(proof=EndpointProof(proof_code, user, self.config.integration_identity,
                                               f"{team}:{user}", private=True))

    def send(self, delivery, rendered):
        return failure_result(self.channel, lambda: self.send_personal(delivery.endpoint,
            message_text(rendered), str(delivery.pk)))

    def send_room(self, text, destination=None):
        self.config.refresh_from_db()
        return failure_result(self.channel, lambda: room(self.config, destination, text))

    def send_personal(self, endpoint, text, key):
        self.config.refresh_from_db()
        user = live_endpoint(self.config, endpoint)
        creds = credentials_for(self.config)
        token = creds.get("bot_token")
        if not token:
            raise ProviderFailure("not_configured")
        if (workspace_identity(creds.get("team_id", "")) != self.config.integration_identity
                or slack_api("auth.test", token=token).get("team_id") != creds.get("team_id")):
            raise ProviderFailure("invalid_endpoint")
        channel = slack_api("conversations.open", token=token, data={"users": user})["channel"]["id"]
        result = slack_api("chat.postMessage", token=token, data={"channel": channel, "text": text[:40000],
            "client_msg_id": str(uuid5(NAMESPACE_URL, f"spaceworks:slack:{self.config.pk}:{key}")),
            "unfurl_links": False, "unfurl_media": False})
        return ProviderResult(True, provider_id=result["ts"])

    def test(self, target):
        self.config.refresh_from_db()
        return failure_result(self.channel, lambda: self.send_personal(target, "Space Works test notification", str(uuid4()))
            if hasattr(target, "verification_state") else room(self.config, target, "Space Works test notification"))


def install_url(config, challenge, code):
    creds = credentials_for(config)
    return "https://slack.com/oauth/v2/authorize?" + urlencode({"client_id": creds["client_id"],
        "scope": "chat:write,im:write", "redirect_uri": redirect_uri("slack", config.makerspace_id),
        "state": state_for(challenge, code, purpose="install"),
        "code_challenge": pkce(code), "code_challenge_method": "S256"})


def complete_install(config, data):
    from .notification_slack_oauth import claim_install, save_install
    _, proof_code = read_state(config, data["state"], purpose="install")
    actor = claim_install(config, data["state"])
    creds = credentials_for(config)
    tokens = api("POST", "https://slack.com/api/oauth.v2.access", form=True, data={
        "client_id": creds["client_id"], "code": data["code"],
        "redirect_uri": redirect_uri("slack", config.makerspace_id), "code_verifier": verifier(proof_code)})
    if not tokens.get("ok") or not tokens.get("access_token") or not tokens.get("team", {}).get("id"):
        raise ProviderFailure("provider_error")
    creds.update(bot_token=tokens["access_token"], team_id=tokens["team"]["id"])
    return save_install(config, actor, creds, workspace_identity(tokens["team"]["id"]))


def register():
    from .notification_providers import register_provider
    register_provider("slack", "slack", SlackProvider)
