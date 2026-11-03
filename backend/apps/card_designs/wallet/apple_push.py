"""Tell registered Apple devices that a pass changed (APNs pass-update push).

An empty-payload push to each device's push token, topic = the Pass Type ID, using
the pass certificate for TLS client auth. A failed push never blocks a card; the
device also re-checks on its own schedule.
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)
APNS = "https://api.push.apple.com/3/device/"


def notify(wallet_pass):
    import httpx
    tokens = [row.push_token for row in wallet_pass.devices.all() if row.push_token]
    if not tokens:
        return 0
    sent = 0
    try:
        with httpx.Client(http2=True, cert=(settings.WALLET_APPLE_CERT_FILE, settings.WALLET_APPLE_KEY_FILE),
                          timeout=10) as client:
            for token in tokens:
                response = client.post(APNS + token, json={},
                                       headers={"apns-topic": settings.WALLET_APPLE_PASS_TYPE_ID})
                sent += response.status_code == 200
    except Exception:
        logger.warning("wallet_apple_push_failed", extra={"pass_id": wallet_pass.pk})
    return sent
