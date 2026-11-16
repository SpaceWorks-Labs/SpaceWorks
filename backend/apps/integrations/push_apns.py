import time

import httpx
import jwt
from cryptography.fernet import InvalidToken

from apps.integrations.push_categories import thread_id
from apps.integrations.push_fcm import PushProviderError
from apps.integrations.push_payload import short_body, short_title


def aps_payload(title, body, data):
    """The `aps` dictionary: watch-sized text, the space thread and the safe action set."""
    aps = {"alert": {"title": short_title(title), "body": short_body(body)}}
    if data.get("makerspace_id"):
        aps["thread-id"] = thread_id(data["makerspace_id"], data.get("channel", ""))
    if data.get("category"):
        aps["category"] = data["category"]
    return aps


def apns_authorization(settings_row):
    """The signed APNs provider token; also the console's local key check (#190)."""
    try:
        private_key = settings_row.get_apns_private_key()
        if not private_key or not settings_row.apns_team_id or not settings_row.apns_key_id or not settings_row.apns_topic:
            raise ValueError
        authorization = jwt.encode(
            {"iss": settings_row.apns_team_id, "iat": int(time.time())},
            private_key, algorithm="ES256", headers={"kid": settings_row.apns_key_id},
        )
    # PyJWT reports an unusable key as InvalidKeyError, which is not a ValueError: without
    # it a bad .p8 escaped as an unclassified exception instead of a configuration error.
    except (InvalidToken, ValueError, TypeError, jwt.PyJWTError) as exc:
        raise PushProviderError("APNs configuration is unavailable.") from exc
    return authorization


def send_apns(settings_row, token, environment, title, body, data):
    authorization = apns_authorization(settings_row)
    host = "api.sandbox.push.apple.com" if environment == "development" else "api.push.apple.com"
    try:
        with httpx.Client(http2=True, timeout=10) as client:
            response = client.post(
                f"https://{host}/3/device/{token}",
                headers={
                    "authorization": f"bearer {authorization}",
                    "apns-topic": settings_row.apns_topic,
                    "apns-push-type": "alert",
                },
                json={"aps": aps_payload(title, body, data), "data": data},
            )
    except httpx.HTTPError as exc:
        raise PushProviderError("APNs request failed.") from exc
    if response.status_code == 200:
        return
    try:
        payload = response.json()
        reason = payload.get("reason", "") if isinstance(payload, dict) else ""
        if not isinstance(reason, str):
            reason = ""
    except (ValueError, TypeError):
        reason = ""
    raise PushProviderError(
        "APNs delivery failed.", invalid_token=reason in {"BadDeviceToken", "Unregistered"}
    )
