"""Decision 219d: payee money (event reimbursements, payouts) is read in an account session only.

A personal access token or an OAuth app connection acting as finance staff still reads the rest
of the linked finance view, but never its `reimbursements` / `payouts` sections, and every
reimbursement route refuses it with `full_session_required`.
"""

from uuid import uuid4

import pytest

from apps.makerspaces.platform import module_enabled
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from tests.events.collab_helpers import client_for
from tests.events.ticketing_helpers import open_event
from tests.hardware_requests.test_phase2_person_credential_boundary import delegated_credential
from tests.api_r2.test_person_credentials import _bearer
from tests.payments.test_event_linked_finance_item08 import _charge, _space, _url
from tests.return_helpers import make_member

PAYEE_SECTIONS = {"reimbursements", "payouts"}


def _world(slug):
    space = _space(slug, modules=("events", "bookings", "event_reimbursements"))
    event = open_event(space)
    manager = make_member(f"{slug}-sm", space)
    _charge(space, event, 1, "10.00", "inr")
    EventPayoutObligation.objects.create(makerspace=space, event=event, event_id_snapshot=event.pk,
                                         event_title_snapshot=event.title, source_uuid=uuid4(),
                                         source_decision_revision=1, currency="INR", approved_minor=500)
    return space, event, manager


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["pat", "oauth"])
def test_delegated_credential_never_reads_payee_money(settings, kind):
    settings.API_CLIENT_AUTH_REQUIRED = False
    settings.HMAC_PROTECTED_PATH_PREFIXES = ["/api/v1/public/"]
    space, event, manager = _world(f"payee-{kind}")

    session = client_for(manager).get(_url(space, event))
    assert session.status_code == 200, session.content
    sections = session.json()["sections"]
    assert "payouts" in sections
    assert ("reimbursements" in sections) == module_enabled(space, "event_reimbursements")

    api = _bearer(delegated_credential(kind, manager, space))
    delegated = api.get(_url(space, event))
    assert delegated.status_code == 200, delegated.content
    visible = set(delegated.json()["sections"])
    assert "registration_charges" in visible
    assert not PAYEE_SECTIONS & visible

    for route in ("programme", "requests", "claims"):
        path = f"/api/v1/admin/events/{event.pk}/reimbursements/{route}/"
        if route != "programme" and module_enabled(space, "event_reimbursements"):
            assert client_for(manager).get(path).status_code == 200, (route, "session")
        denied = api.get(path)
        assert denied.status_code == 403, (route, denied.content)
