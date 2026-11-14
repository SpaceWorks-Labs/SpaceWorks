"""Contact-code creation proves the persisted scoped OTP and audited recipient hash."""
import pytest
from django.urls import reverse

from apps.accounts.models import EmailVerificationChallenge
from apps.accounts.services_registration import _digest
from apps.hardware_requests.contact_verification import email_key
from apps.makerspaces.anonymous_requesters import get_or_create_anonymous_requester
from tests.modules.switch_matrix_object_helpers import object_world
from tests.modules.test_switch_matrix_objects_rest_support import switch
from tests.operations.route_support_cx11b_g4 import cycle, send

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending, pytest.mark.area_auth]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_contact_code_route_restores_the_real_scoped_challenge(native, monkeypatch):
    space, client, _ = object_world(native)
    switch(space, "member_accounts")
    principal = get_or_create_anonymous_requester(space)
    monkeypatch.setattr("apps.hardware_requests.contact_verification._generate_otp", lambda: "123456")
    mailed = []
    monkeypatch.setattr("apps.integrations.email.send_email_verification_otp", lambda email, code: mailed.append((email, code)) or True)
    url = reverse("hardware_requests:request-contact-code", kwargs={"makerspace_slug": space.slug})
    missing = reverse("hardware_requests:request-contact-code", kwargs={"makerspace_slug": "g4-missing-space"})
    email = "g4-contact@example.test"
    def check(response):
        assert response.data is None
        proof = EmailVerificationChallenge.objects.get(user=principal, email=email_key(space, email))
        assert (proof.code_digest, proof.consumed_at, proof.failed_attempts) == (_digest("123456"), None, 0)
        assert mailed[-1] == (email, "123456")
    # A contact endpoint has no account-standing requirement (80/91); a missing slug
    # remains not_found while the public loan feature is on or off.
    cycle(space, "loans.enabled", lambda: send(client, "POST", url, {"email": email}), check,
          on=(202, None), off=(404, "feature_disabled"), audit=("request.contact_code_sent",),
          foreign=lambda: send(client, "POST", missing, {"email": email}), foreign_native=native)
