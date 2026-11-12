"""The console's "Send test" / "Check credentials" for platform providers (#190).

Each one proves what a real send needs and fails safe with a typed error: nothing here
raises past the view, and no provider body, credential or phone number reaches a log line
or the audit row.

* SMS sends one short text from the sign-in number to a number the superadmin types.
* Push signs in to FCM with the service account, and signs an APNs provider token
  locally (APNs has no harmless call without a device token).
* WhatsApp reads the configured phone number id from Meta's Graph API.
* App attestation has no test: Play Integrity has no call without a device token, and its
  key is already checked when it is saved.
"""

from django.utils.translation import gettext
import logging
import re

import requests
from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)
TEST_TEXT = "Space Works test message: platform SMS is working."


class ProviderNotConfigured(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "provider_not_configured"
    default_detail = {"code": "provider_not_configured", "detail": "Save complete credentials first."}


class ProviderTestFailed(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "provider_test_failed"

    def __init__(self, detail):
        super().__init__({"code": "provider_test_failed", "detail": detail})


def check_sms(row, to):
    from apps.integrations.sms.twilio import TwilioSmsProvider
    provider = TwilioSmsProvider(row)
    if row.pk is None or not provider.is_configured():
        raise ProviderNotConfigured()
    if not provider.send(to=to, body=TEST_TEXT):
        raise ProviderTestFailed(gettext("The SMS provider refused the test message. Check the account and sender."))
    return {"outcome": "sent"}


def check_push(row):
    from apps.integrations.push_apns import apns_authorization
    from apps.integrations.push_fcm import PushProviderError, fcm_access_token
    if row.pk is None or not (row.fcm_configured or row.apns_configured):
        raise ProviderNotConfigured()
    checked = []
    try:
        if row.fcm_configured:
            fcm_access_token(row)
            checked.append("fcm")
        if row.apns_configured:
            apns_authorization(row)
            checked.append("apns")
    except PushProviderError as exc:
        logger.warning("platform_push_check_failed", extra={"checked": checked})
        raise ProviderTestFailed(str(exc)) from None
    return {"outcome": "ok", "checked": checked}


def check_whatsapp(row):
    try:
        token = row.get_secret("access_token") if row.pk else ""
    except Exception:
        token = ""
    if not (token and row.phone_number_id):
        raise ProviderNotConfigured()
    version = settings.WHATSAPP_META_GRAPH_VERSION
    if not re.fullmatch(r"v\d+\.\d+", version) or not row.phone_number_id.isdigit():
        raise ProviderTestFailed(gettext("The WhatsApp settings cannot be checked; review the phone number id."))
    try:
        response = requests.get(f"https://graph.facebook.com/{version}/{row.phone_number_id}",
                                params={"fields": "id"}, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    except requests.RequestException:
        raise ProviderTestFailed(gettext("Meta could not be reached. Try again.")) from None
    if response.status_code != 200:
        # The status only: Graph error bodies can echo request details.
        logger.warning("platform_whatsapp_check_failed", extra={"status": response.status_code})
        raise ProviderTestFailed(gettext("Meta refused the access token or phone number id."))
    return {"outcome": "ok", "checked": ["whatsapp"]}
