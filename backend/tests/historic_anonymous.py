"""Build the rows an account-less request left behind before #75f removed the path.

Production can no longer create them, but they exist in every database that ran the
opt-in, so tests that pin their readability and their exclusions build them directly,
exactly as the removed `get_or_create_anonymous_requester` and submit path did.
"""

import uuid

from apps.accounts.models import User
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from apps.makerspaces.models import Makerspace


def historic_principal(space):
    if space.anonymous_requester_id:
        return User.objects.get(pk=space.anonymous_requester_id)
    user = User(
        username=f"member_{uuid.uuid4().hex}", display_name="Anonymous requester (system principal)",
        email="", phone="", phone_e164="", role=User.Role.REQUESTER, is_active=False,
    )
    user.set_unusable_password()
    user.save()
    Makerspace.objects.filter(pk=space.pk).update(anonymous_requester=user)
    space.anonymous_requester = user
    return user


def historic_anonymous_request(space, product, *, name="Ada Lovelace", email="ada@example.test",
                               verified=False, key="legacy-key"):
    row = HardwareRequest.objects.create(
        makerspace=space, requester=historic_principal(space), requester_username="",
        requester_name=name, requester_contact_email=email, requester_contact_verified=verified,
        anonymous_idempotency_key_fingerprint=f"fp-{key}", anonymous_payload_fingerprint=f"pf-{key}",
        status=HardwareRequest.Status.PENDING_APPROVAL, requested_for="Bench diagnostics",
    )
    HardwareRequestItem.objects.create(request=row, product=product, requested_quantity=1)
    return row
