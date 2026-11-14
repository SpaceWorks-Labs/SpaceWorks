"""All thirty reimbursement route/methods; independently switch both modules and features."""

import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401

from tests.event_reimbursements.effects_cx11b_g5 import assertions
from tests.modules.switch_matrix_object_contracts_rest import OPERATIONS, keys_for
from tests.modules.test_switch_matrix_objects_rest_reimbursement_support import reimbursement_world
from tests.payments.route_support_cx11b_g5 import cycle, foreign_client, hidden, world

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_event_reimbursements]
OPS = tuple(op for op in OPERATIONS if op.target == "reimbursement")
CASES = [(i, key, native) for i, op in enumerate(OPS)
         for key in (*keys_for(op), *(("events.crew",) if op.name.endswith("crew-pool") else ()))
         for native in (False, True)]


@pytest.mark.parametrize("index,key,native", CASES,
    ids=[f"{OPS[i].name}:{OPS[i].method}:{key}:{'native' if native else 'browser'}" for i, key, native in CASES])
def test_reimbursement_route_effect_standing_off_fence_and_restore(index, key, native, make_world, monkeypatch):
    op = OPS[index]
    space, client, objects, url, body = reimbursement_world(op, native, make_world, monkeypatch)
    event = objects["reimbursement"]
    event.is_public = False
    event.save(update_fields=["is_public"])
    check, audit, prefix = assertions(op, objects, body)
    # 506: event-ID staff outsiders keep the uniform surface-gate 403. Use a real
    # browser JWT here so that gate is exercised, not bypassed by force_authenticate.
    # 494/524 also preserve the native tenant mismatch; private owner reads use 520.
    staff = op.name.startswith("admin-")
    foreign = foreign_client(native, reauth=True, browser_token=staff and not native)
    expected = (403, "permission_denied") if staff or native else (404, "not_found")
    probes = [hidden(foreign, expected)]
    if op.name in {"member-event-receipt-file-detail", "member-event-receipt-file-complete"}:
        from apps.events.models import EventRegistration
        from tests.modules.switch_matrix_object_helpers import client_for
        from tests.accounts.account_factories import make_staff
        other = make_staff(space, username="g5-other-participant")
        EventRegistration.objects.create(event=event, member=other, status="registered", name="Other participant")
        probes.append(hidden(client_for(other, space, native), (404, "not_found")))
    w = world(space, client, url, op.method, body, (op.status, None), audit, check,
              probes=probes, audit_prefix=prefix)
    w.outside = op.name == "member-event-receipt-file-create"
    cycle(w, key, (404, "feature_disabled" if "." in key else "module_disabled"))

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
