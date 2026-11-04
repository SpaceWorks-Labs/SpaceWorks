"""Configured-server OAuth identity proof and bot DMs; rooms retain webhook delivery."""
from urllib.parse import urlencode
from uuid import NAMESPACE_URL, uuid5, uuid4

from django.utils.crypto import constant_time_compare

from .notification_providers import CallbackEvent, EndpointProof, ProviderResult
from .notification_slack_http import credentials_for, failure_result, live_endpoint, message_text, room, ProviderFailure
from .notification_slack_oauth import read_state, redirect_uri, state_for, pkce, verifier
from .notification_mattermost_http import mattermost_api, resolve_server, server_url


class MattermostProvider:
    channel = "mattermost"

    def __init__(self, config):
        self.config = config

    def start_challenge(self, challenge, code):
        creds = credentials_for(self.config)
        base = server_url(creds["server_url"])
        resolve_server(base, "/oauth/authorize")
        if base != self.config.integration_identity or not creds.get("bot_token"):
            raise ProviderFailure("not_configured")
        return {"connect_url": base + "/oauth/authorize?" + urlencode({
            "client_id": creds["client_id"], "response_type": "code", "redirect_uri": redirect_uri(self.channel, self.config.makerspace_id, challenge.pk),
            "state": state_for(challenge, code), "code_challenge": pkce(code), "code_challenge_method": "S256"})}

    def verify_callback(self, request):
        try:
            data = request.query_params if request.method == "GET" else request.data
            if (request.method == "POST" and data.get("state")
                    and getattr(getattr(request, "user", None), "is_authenticated", False)):
                return self.oauth_proof(data, getattr(getattr(request, "user", None), "pk", None))
            token = credentials_for(self.config).get("webhook_token", "")
            if token and constant_time_compare(token, data.get("token", "")):
                return CallbackEvent()
        except Exception:
            return None
        return None

    def oauth_proof(self, data, user_id=None):
        if user_id is None:
            return None
        challenge, proof_code = read_state(self.config, data["state"], user_id=user_id)
        creds = credentials_for(self.config)
        base = server_url(creds["server_url"])
        if base != self.config.integration_identity:
            return None
        tokens = mattermost_api(base, "POST", "/oauth/access_token", form=True, data={
            "client_id": creds["client_id"], "client_secret": creds["client_secret"],
            "code": data["code"], "redirect_uri": redirect_uri(self.channel, self.config.makerspace_id, challenge.pk),
            "grant_type": "authorization_code", "code_verifier": verifier(proof_code)})
        user = mattermost_api(base, "GET", "/api/v4/users/me", token=tokens["access_token"])
        if not user.get("id") or user.get("delete_at") or user.get("is_bot"):
            return None
        return CallbackEvent(proof=EndpointProof(proof_code, user["id"], base, user["id"], private=True))

    def send(self, delivery, rendered):
        return failure_result(self.channel, lambda: self.send_personal(delivery.endpoint,
            message_text(rendered), str(delivery.pk)))

    def send_document(self, delivery, *, filename, pdf_bytes, caption):
        from .notification_chat_documents import mattermost_document
        return mattermost_document(self, delivery, filename=filename, pdf_bytes=pdf_bytes, caption=caption)

    def send_room(self, text, destination=None):
        self.config.refresh_from_db()
        return failure_result(self.channel, lambda: room(self.config, destination, text))

    def send_personal(self, endpoint, text, key):
        self.config.refresh_from_db()
        user = live_endpoint(self.config, endpoint)
        creds = credentials_for(self.config)
        base = server_url(creds["server_url"])
        if base != self.config.integration_identity:
            raise ProviderFailure("not_configured")
        bot = mattermost_api(base, "GET", "/api/v4/users/me", token=creds["bot_token"])
        if not bot.get("id") or bot.get("delete_at") or not bot.get("is_bot"):
            raise ProviderFailure("invalid_endpoint")
        recipient = mattermost_api(base, "GET", f"/api/v4/users/{validated_id(user)}", token=creds["bot_token"])
        if recipient.get("delete_at") or not recipient.get("id"):
            raise ProviderFailure("invalid_endpoint")
        channel = mattermost_api(base, "POST", "/api/v4/channels/direct", token=creds["bot_token"],
                                 data=[bot["id"], user])
        result = mattermost_api(base, "POST", "/api/v4/posts", token=creds["bot_token"], data={
            "channel_id": channel["id"], "message": text[:16383],
            "pending_post_id": uuid5(NAMESPACE_URL, f"spaceworks:mm:{self.config.pk}:{key}").hex})
        return ProviderResult(True, provider_id=result["id"])

    def test(self, target):
        self.config.refresh_from_db()
        return failure_result(self.channel, lambda: self.send_personal(target, "Space Works test notification", str(uuid4()))
            if hasattr(target, "verification_state") else room(self.config, target, "Space Works test notification"))


def validated_id(value):
    import re
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9]{26}", value):
        raise ProviderFailure("invalid_endpoint")
    return value


def register():
    from .notification_providers import register_provider
    register_provider("mattermost", "mattermost", MattermostProvider)
