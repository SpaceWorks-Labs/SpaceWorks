"""Submit a borrow request the way the space requires (owner decisions #80/#91).

Without member accounts everyone -- signed in or not -- uses the contact form plus an
emailed code, so module-independence tests that run the loan spine on such a space go
through that path instead of the account path.
"""

from unittest.mock import patch

from django.urls import reverse


def post_borrow_request(client, space, body, format="json", **extra):
    from apps.makerspaces.request_access import contact_requests_allowed

    url = reverse("hardware_requests:request-submit", args=[space.slug])
    if not contact_requests_allowed(space):
        return client.post(url, body, format=format, **extra)
    email = f"spine-{space.slug}@example.test"
    sent = []
    with patch("apps.integrations.email.send_email_verification_otp",
               lambda to, code: sent.append(code) or True):
        client.post(reverse("hardware_requests:request-contact-code", args=[space.slug]),
                    {"email": email}, format="json")
    body = {**body, "contact_name": "Spine Borrower", "contact_phone": "+15550101010",
            "contact_email": email, "email_code": sent[-1] if sent else ""}
    return client.post(url, body, format=format, **extra)
