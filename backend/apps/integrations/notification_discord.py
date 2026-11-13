"""Discord identify OAuth, signed interactions and private bot notifications."""
import time
from uuid import uuid4
from urllib.parse import urlencode

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .notification_providers import CallbackEvent, EndpointProof, ProviderResult
from .notification_slack_http import api, credentials_for, failure_result, live_endpoint, message_text, room, ProviderFailure
from .notification_slack_oauth import read_state, redirect_uri, state_for

API = "https://discord.com/api/v10"


def signed_request(request, public_key):
    try:
        timestamp = request.headers.get("X-Signature-Timestamp", "")
        if abs(time.time() - int(timestamp)) > 300:
            return False
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key))
        key.verify(bytes.fromhex(request.headers.get("X-Signature-Ed25519", "")),
                   timestamp.encode() + request.body)
        return True
    except (InvalidSignature, ValueError, TypeError, UnicodeError):
        return False


class DiscordProvider:
    channel = "discord"

    def __init__(self, config):
        self.config = config

    def start_challenge(self, challenge, code):
        creds = credentials_for(self.config)
        self.check_identity(creds)
        if not creds.get("bot_token") or not creds.get("client_secret"):
            raise ProviderFailure("not_configured")
        return {"connect_url": "https://discord.com/oauth2/authorize?" + urlencode({
            "client_id": creds["application_id"], "response_type": "code", "scope": "identify",
            "redirect_uri": redirect_uri(self.channel, self.config.makerspace_id, challenge.pk), "state": state_for(challenge, code)})}

    def verify_callback(self, request):
        try:
            if (request.method == "POST"
                    and getattr(getattr(request, "user", None), "is_authenticated", False)):
                data = request.query_params if request.method == "GET" else request.data
                if data.get("state"):
                    return self.oauth_proof(data, getattr(getattr(request, "user", None), "pk", None))
            if signed_request(request, credentials_for(self.config).get("public_key", "")):
                return CallbackEvent()
        except Exception:
            return None
        return None

    def oauth_proof(self, data, user_id=None):
        if user_id is None:
            return None
        challenge, proof_code = read_state(self.config, data["state"], user_id=user_id)
        creds = credentials_for(self.config)
        self.check_identity(creds)
        tokens = api("POST", API + "/oauth2/token", form=True, data={
            "client_id": creds["application_id"], "client_secret": creds["client_secret"],
            "code": data["code"], "redirect_uri": redirect_uri(self.channel, self.config.makerspace_id, challenge.pk), "grant_type": "authorization_code"})
        if "identify" not in tokens.get("scope", "").split():
            return None
        user = api("GET", API + "/users/@me", token=tokens["access_token"])
        if not user.get("id") or user.get("bot"):
            return None
        return CallbackEvent(proof=EndpointProof(proof_code, user["id"],
            self.config.integration_identity, user["id"], private=True))

    def send(self, delivery, rendered):
        return failure_result(self.channel, lambda: self.send_personal(delivery.endpoint,
            message_text(rendered), str(delivery.pk)))

    def send_document(self, delivery, *, filename, pdf_bytes, caption):
        from .notification_chat_documents import discord_document
        return discord_document(self, delivery, filename=filename, pdf_bytes=pdf_bytes, caption=caption)

    def send_room(self, text, destination=None):
        self.config.refresh_from_db()
        return failure_result(self.channel, lambda: room(self.config, destination, text))

    def check_identity(self, creds):
        if self.config.integration_identity != f"{creds.get('application_id')}:{creds.get('guild_id')}":
            raise ProviderFailure("not_configured")

    def send_personal(self, endpoint, text, key):
        self.config.refresh_from_db()
        user = live_endpoint(self.config, endpoint)
        creds = credentials_for(self.config)
        self.check_identity(creds)
        token = creds.get("bot_token")
        if not token:
            raise ProviderFailure("not_configured")
        channel = api("POST", API + "/users/@me/channels", token=token, auth="Bot", data={"recipient_id": user})
        channel_id = channel["id"]
        if not str(channel_id).isdigit():
            raise ProviderFailure("provider_error")
        result = api("POST", API + f"/channels/{channel_id}/messages", token=token, auth="Bot", data={
            "content": text[:2000], "allowed_mentions": {"parse": []}, "nonce": key, "enforce_nonce": True})
        return ProviderResult(True, provider_id=result["id"])

    def test(self, target):
        self.config.refresh_from_db()
        return failure_result(self.channel, lambda: self.send_personal(target, "Space Works test notification", uuid4().hex[:25])
            if hasattr(target, "verification_state") else room(self.config, target, "Space Works test notification"))


def register():
    from .notification_providers import register_provider
    register_provider("discord", "discord", DiscordProvider)
