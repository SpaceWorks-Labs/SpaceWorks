"""Use the real control MFA endpoint before testing unrelated admin behavior."""

from django.utils import timezone

from apps.accounts.mfa_crypto import totp
from tests.accounts.mfa_helpers import enrolled


def force_control_mfa_login(client, user):
    # Superadmin enrollment is opt-in in this tree. Provision the credential first
    # so force_login cannot stamp a password-only session, then verify it over HTTP.
    _, secret = enrolled(user)
    client.force_login(user)
    setup = client.get("/mfa/control/")
    assert setup.status_code == 200
    assert setup.context["enrolling"] is False
    completed = client.post("/mfa/control/", {
        "code": totp(secret, int(timezone.now().timestamp() // 30)),
    })
    assert completed.status_code == 302
    assert completed.url == "/control/"
