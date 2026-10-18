"""Notification Twilio transport; OTP continues using its existing bool seam."""
import base64
from urllib.parse import quote, urlencode
from urllib.request import Request

from .resolver import webhook_urls
from .transport import send_request


def send_message(sender, *, to, body, delivery_id=None, status_callback=None):
    callback = status_callback or webhook_urls("sms", sender.makerspace_id)["status"]
    payload = urlencode({"To": to, "From": sender.from_number, "Body": body, "StatusCallback": callback}).encode()
    authorization = base64.b64encode(f"{sender.account_sid}:{sender.auth_token}".encode()).decode("ascii")
    req = Request(f"https://api.twilio.com/2010-04-01/Accounts/{quote(sender.account_sid, safe='')}/Messages.json",
                  data=payload, method="POST", headers={"Authorization": f"Basic {authorization}",
                  "Content-Type": "application/x-www-form-urlencoded"})
    return send_request(req, provider="twilio")
