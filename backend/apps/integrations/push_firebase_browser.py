"""Typed FID target, reusing platform service-account authentication."""
import requests
from .push_fcm import fcm_access_token, PushProviderError


def send_challenge(settings_row, expected_project, fid, challenge, nonce):
    access_token, project_id = fcm_access_token(settings_row)
    if project_id != expected_project:
        raise PushProviderError("Firebase project does not match platform credentials.")
    try:
        response = requests.post(
            f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
            headers={"Authorization": f"Bearer {access_token}"}, timeout=10,
            json={"message": {"fid": fid, "data": {"kind": "spaceworks_fcm_challenge",
                                                    "challenge": challenge, "nonce": nonce}}},
        )
    except requests.RequestException as exc:
        raise PushProviderError("Firebase challenge delivery failed.") from exc
    if response.status_code != 200:
        raise PushProviderError("Firebase challenge delivery failed.")


def send_inbox_hint(settings_row, expected_project, fid, owner_epoch, *, context=None):
    """A generic wake-up only; the authenticated inbox supplies any private content."""
    timeout = context.timeout(5.0) if context else 10
    access_token, project_id = fcm_access_token(settings_row, timeout=timeout)
    if project_id != expected_project:
        raise PushProviderError("Firebase project does not match platform credentials.")
    try:
        if context:
            context.check()
        response = requests.post(
            f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
            headers={"Authorization": f"Bearer {access_token}"}, timeout=context.timeout(5.0) if context else 10,
            json={"message": {"fid": fid, "data": {"kind": "spaceworks_inbox_changed", "owner_epoch": owner_epoch}}},
        )
    except requests.RequestException as exc:
        raise PushProviderError("Firebase delivery failed.") from exc
    if response.status_code != 200:
        try:
            payload = response.json()
            error = payload.get("error", {}) if isinstance(payload, dict) else {}
            details = error.get("details", []) if isinstance(error, dict) else []
            invalid = isinstance(details, list) and any(
                isinstance(item, dict) and item.get("errorCode") == "UNREGISTERED"
                for item in details)
        except (ValueError, TypeError):
            invalid = False
        raise PushProviderError("Firebase delivery failed.", invalid_token=invalid)
