"""Tell registered Apple devices that a pass changed (APNs pass-update push).

An empty-payload push to each device's push token, topic = the Pass Type ID, using
the pass certificate for TLS client auth (the space's, else the platform's). A failed push
never blocks a card; the device also re-checks on its own schedule.
"""
import logging
import os
import tempfile

from .credentials import apple_for

logger = logging.getLogger(__name__)
APNS = "https://api.push.apple.com/3/device/"


def notify(wallet_pass):
    import httpx
    tokens = [row.push_token for row in wallet_pass.devices.all() if row.push_token]
    creds = apple_for(wallet_pass.makerspace_id)
    if not tokens or creds is None:
        return 0
    sent, paths = 0, []
    try:
        # httpx takes certificate FILES; they live only for this push (mkstemp is 0600) and are removed after.
        for blob in (creds.cert_pem, creds.key_pem):
            handle, path = tempfile.mkstemp(suffix=".pem")
            paths.append(path)
            with os.fdopen(handle, "wb") as file:
                file.write(blob)
        with httpx.Client(http2=True, cert=tuple(paths), timeout=10) as client:
            for token in tokens:
                response = client.post(APNS + token, json={}, headers={"apns-topic": creds.pass_type_id})
                sent += response.status_code == 200
    except Exception:
        logger.warning("wallet_apple_push_failed", extra={"pass_id": wallet_pass.pk})
    finally:
        for path in paths:
            try:
                os.remove(path)
            except OSError:
                pass
    return sent
