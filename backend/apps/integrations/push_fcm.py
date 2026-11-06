import json
import time

import jwt
import requests
from cryptography.fernet import InvalidToken

from apps.integrations.push_payload import short_body, short_title


class PushProviderError(Exception):
    def __init__(self, message, *, invalid_token=False):
        super().__init__(message)
        self.invalid_token = invalid_token


def fcm_message(token, title, body, data):
    """The FCM v1 message: watch-sized text; v3 adds the topic channel and a dedupe tag.

    `click_action` is deliberately absent: a v2 app without a matching intent filter would
    open nothing on tap. The action set travels in `data.category` instead.
    """
    message = {"token": token, "notification": {"title": short_title(title), "body": short_body(body)},
               "data": data}
    if data.get("channel"):
        message["android"] = {"notification": {
            "channel_id": data["channel"], "tag": f"sw-{data.get('event_id', '')}",
        }}
    return message


def fcm_access_token(settings_row):
    """Sign in to FCM with the stored service account: ``(access_token, project_id)``.

    Shared by every send and by the console's credential check (#190), so the check proves
    exactly what a real send needs.
    """
    try:
        account = json.loads(settings_row.get_fcm_service_account())
        if not isinstance(account, dict):
            raise ValueError
        required = {key: account.get(key) for key in (
            "client_email", "private_key", "token_uri", "project_id"
        )}
        if not all(isinstance(value, str) and value.strip() for value in required.values()) or not required["token_uri"].startswith("https://"):
            raise ValueError
        now = int(time.time())
        # Inside the try: a service account whose private_key is not a usable RSA key is a
        # configuration error, not an unclassified exception out of the sender.
        assertion = jwt.encode({
            "iss": required["client_email"],
            "scope": "https://www.googleapis.com/auth/firebase.messaging",
            "aud": required["token_uri"], "iat": now, "exp": now + 300,
        }, required["private_key"], algorithm="RS256")
    except (InvalidToken, ValueError, TypeError, jwt.PyJWTError) as exc:
        raise PushProviderError("FCM configuration is unavailable.") from exc
    try:
        oauth = requests.post(required["token_uri"], data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        }, timeout=10)
        payload = oauth.json() if oauth.status_code == 200 else {}
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise PushProviderError("FCM request failed.") from exc
    access_token = payload.get("access_token") if isinstance(payload, dict) else None
    if not isinstance(access_token, str) or not access_token.strip():
        raise PushProviderError("FCM authorization failed.")
    return access_token, required["project_id"]


def send_fcm(settings_row, token, title, body, data):
    access_token, project_id = fcm_access_token(settings_row)
    try:
        response = requests.post(
            f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"message": fcm_message(token, title, body, data)}, timeout=10,
        )
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise PushProviderError("FCM request failed.") from exc
    if response.status_code == 200:
        return
    try:
        payload = response.json()
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        if not isinstance(error, dict):
            error = {}
        details = error.get("details", [])
        invalid = error.get("status") == "NOT_FOUND" or (
            isinstance(details, list) and any(
                isinstance(detail, dict) and detail.get("errorCode") == "UNREGISTERED"
                for detail in details
            )
        )
    except (ValueError, TypeError):
        invalid = False
    raise PushProviderError("FCM delivery failed.", invalid_token=invalid)
