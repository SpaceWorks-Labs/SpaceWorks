"""#185 item 1: a suspended space refuses every surface; unblocking restores everything."""

import pytest
from django.http import Http404
from django.urls import reverse

from apps.accounts import rbac
from apps.audit.models import AuditLog
from apps.integrations.models import EmailLog
from apps.makerspaces.lookup import get_makerspace_by_public_code, get_public_makerspace
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import is_servable, servable_queryset, unservable_makerspace_ids
from apps.space_controls.errors import SpaceSuspended
from apps.space_controls.models import SpaceControlState
from apps.space_controls.write_policy import BOTH, permitted
from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
from apps.tenant_migration.gate_runtime import boundary_tenant_write, fanout_tenant_write, tenant_write

from .helpers import REASON, api, control, manager, member, space, superadmin

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(mailbox, django_capture_on_commit_callbacks):
    lab = space()
    other = space("south-lab")
    root, boss, person = superadmin(), manager(lab), member(lab)
    with django_capture_on_commit_callbacks(execute=True):
        response = control(root, lab, "suspend", {"reason": REASON})
    assert response.status_code == 200, response.data
    lab.refresh_from_db()
    return type("World", (), dict(lab=lab, other=other, root=root, boss=boss, person=person, mail=mailbox))


def test_suspend_is_a_lifecycle_state_audited_and_mailed(world):
    assert world.lab.lifecycle_state == Makerspace.LifecycleState.SUSPENDED
    state = SpaceControlState.objects.get(makerspace=world.lab)
    assert state.suspension_reason == REASON and state.suspended_by == world.root
    entry = AuditLog.objects.get(action="space_control.suspended")
    assert entry.makerspace_id == world.lab.pk and REASON not in str(entry.meta)
    assert [message.to for message in world.mail] == [[world.boss.email]]
    assert "paused" in world.mail[0].subject and REASON not in world.mail[0].body


def test_servability_rbac_and_public_lookups_refuse_it(world):
    assert not is_servable(world.lab)
    assert world.lab.pk not in set(servable_queryset().values_list("pk", flat=True))
    assert world.lab.pk in unservable_makerspace_ids()
    assert not rbac.can(world.boss, rbac.Action.MANAGE_MAKERSPACE, world.lab.pk)
    with pytest.raises(Http404):
        get_public_makerspace(world.lab.slug)
    assert api(world.boss).get(f"/api/v1/admin/makerspace/{world.lab.pk}/usage").status_code in (403, 404)


def test_only_the_superadmin_is_admitted_to_a_paused_space(world):
    # #110/#190: nothing is hidden from the superadmin; the admission lives in servability.
    from apps.makerspaces.servability import admit_superadmin, request_scope
    with request_scope():
        admit_superadmin(world.boss)
        assert not is_servable(world.lab) and world.lab.pk in unservable_makerspace_ids()
    with request_scope():
        admit_superadmin(world.root)
        assert is_servable(world.lab) and world.lab.pk not in unservable_makerspace_ids()
        assert world.lab.pk in set(servable_queryset().values_list("pk", flat=True))
        assert rbac.can(world.root, rbac.Action.MANAGE_MAKERSPACE, world.lab.pk)
    assert not is_servable(world.lab)  # the admission never outlives its scope


def test_the_superadmin_reads_a_paused_space_and_staff_do_not(world):
    from tests.stage4.helpers import bearer_client
    usage = f"/api/v1/admin/makerspace/{world.lab.pk}/usage"
    root = bearer_client(world.root)
    assert root.get(usage).status_code == 200
    listed = root.get(reverse("admin-makerspaces")).json()
    rows = listed["results"] if isinstance(listed, dict) else listed
    assert world.lab.pk in {row["id"] for row in rows}
    assert bearer_client(world.boss).get(usage).status_code in (403, 404)
    assert api(world.person).get("/api/v1/platform-notices").json()["spaces"][0]["state"] == "suspended"
    assert not is_servable(world.lab)  # nothing leaked into this (test) context


def test_every_write_boundary_refuses_it(world):
    with pytest.raises(SpaceSuspended):
        with tenant_write(world.lab.pk):
            pass
    with pytest.raises(SourceMigrationGateClosed):
        with boundary_tenant_write(world.lab.pk):
            pass
    counts = {}
    with fanout_tenant_write(world.lab.pk, operation="notification_contract_outbox", counts=counts) as allowed:
        assert allowed is False
    assert counts == {"skipped": 1}
    with tenant_write(world.other.pk):
        pass  # other spaces are untouched


def test_unsafe_http_to_the_space_answers_423_for_everyone_but_the_superadmin(world):
    url = reverse("admin-staff-invitations", kwargs={"makerspace_id": world.lab.pk})
    body = {"email": "new@example.test", "roles": ["inventory_manager"]}
    for actor in (world.boss, world.person):
        response = api(actor).post(url, body, format="json")
        assert response.status_code == 423 and response.json()["code"] == "space_suspended"
    # #195: the superadmin is never switched off; the write is let through the gate and audited.
    from tests.stage4.helpers import bearer_client
    response = bearer_client(world.root, recent=True).post(url, body, format="json")
    assert response.status_code != 423
    entry = AuditLog.objects.get(action="space_control.superadmin_bypass", makerspace=world.lab)
    assert entry.actor == world.root and entry.meta["bypass_space_control"] == "suspended"


def test_outbound_mail_for_the_space_is_held(world):
    log = EmailLog.objects.create(makerspace=world.lab, to_email="someone@example.test", subject="Hi",
                                  text_body="Body", stream="hardware", event="return_reminder",
                                  status=EmailLog.Status.PENDING)
    from apps.integrations.dispatch import _deliver
    with pytest.raises(SpaceSuspended):
        _deliver(log)
    log.refresh_from_db()
    assert log.status == EmailLog.Status.PENDING


def test_money_already_sent_still_settles(world):
    assert is_servable(world.lab, allow_archived=True)
    assert get_makerspace_by_public_code(world.lab.public_code, allow_archived=True) == world.lab
    with permitted(BOTH):
        with tenant_write(world.lab.pk):
            pass


def test_people_see_the_paused_page_and_only_the_superadmin_sees_the_reason(world):
    mine = api(world.person).get("/api/v1/platform-notices").json()["spaces"]
    assert mine == [{"id": world.lab.pk, "name": world.lab.name, "slug": world.lab.slug, "state": "suspended",
                     "reason": "This space is paused by the platform operator.", "since": mine[0]["since"]}]
    root_view = api(world.root).get("/api/v1/platform-notices").json()["spaces"]
    assert root_view[0]["reason"] == REASON
    public = api().get(f"/api/v1/public/makerspaces/{world.lab.slug}/availability")
    assert public.status_code == 200 and public.json() == {"state": "paused"}


def test_suspend_needs_superadmin_reauth_and_a_reason(world):
    other = world.other
    assert control(world.boss, other, "suspend", {"reason": REASON}).status_code == 403
    assert control(world.root, other, "suspend", {"reason": "short"}).status_code == 400
    from tests.stage4.helpers import bearer_client
    refused = bearer_client(world.root).post(f"/api/v1/admin/platform/spaces/{other.pk}/suspend",
                                             {"reason": REASON}, format="json")
    assert refused.status_code == 403
    assert control(world.root, world.lab, "suspend", {"reason": REASON}).json()["code"] == "space_not_active"


def test_unblock_restores_everything(world, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = control(world.root, world.lab, "unsuspend")
    assert response.status_code == 200 and response.json()["state"] == "active"
    world.lab.refresh_from_db()
    assert is_servable(world.lab)
    assert rbac.can(world.boss, rbac.Action.MANAGE_MAKERSPACE, world.lab.pk)
    with tenant_write(world.lab.pk):
        pass
    assert get_public_makerspace(world.lab.slug) == world.lab
    assert api(world.person).get("/api/v1/platform-notices").json()["spaces"] == []
    assert api().get(f"/api/v1/public/makerspaces/{world.lab.slug}/availability").json() == {"state": "active"}
    assert AuditLog.objects.filter(action="space_control.unsuspended", makerspace=world.lab).exists()
    assert "available again" in world.mail[-1].subject
    assert control(world.root, world.lab, "unsuspend").json()["code"] == "space_not_suspended"
