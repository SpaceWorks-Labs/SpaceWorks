"""Member machine catalogue/access and the retired-but-routed certification surface."""
import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.machines.models import CertificationGrant, CertificationType, MachineAccessGrant
from apps.makerspaces.models import MakerspaceMembership
from tests.machines.member_support_cx11b_g2 import member_world
from tests.machines.route_support_cx11b_g2 import command, domain_rows, no_domain_writes, prove, response_pair, rows, toggle
from tests.modules.test_switch_matrix_objects_rest_support import _no_write

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name", ["member-machines", "member-machine-access"])
def test_member_reads_show_the_exact_machine_or_grant_and_keep_personal_refusal(native, name):
    w = member_world(native)
    grant = MachineAccessGrant.objects.create(makerspace=w.space, member=w.member, machine=w.machine, granted_by=w.actor)

    def check(response):
        if name == "member-machines":
            assert [(r["id"], r["name"]) for r in rows(response)] == [(w.machine.pk, "Retained machine")]
        else:
            assert [(r["id"], r["machine_id"], r["status"]) for r in response.data["grants"]] == [(grant.pk, w.machine.pk, "live")]
            assert response.data["open_machines"] == [{"id": w.machine.pk, "name": "Retained machine"}]

    # 494/486: these require an active community membership, and explicitly use 403
    # on the person surface. They are not makerspace-addressed STAFF routes.
    prove(w, "machines", lambda c: command(c, name, "get", [w.space.pk]), check, foreign=(403, "permission_denied"))


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_registered_certifications_route_remains_retired_in_every_switch_state(native):
    w = member_world(native)
    certification = CertificationType.objects.create(makerspace=w.space, machine_type=w.kind, name="Retained training")
    grant = CertificationGrant.objects.create(certification_type=certification, granted_by=w.actor,
        membership=MakerspaceMembership.objects.get(makerspace=w.space, user=w.member), notes="Legacy training proof")
    before = domain_rows()
    for key in ("machines", "machines.certifications"):
        for disabled in (False, True):
            original = toggle(w.space, key) if disabled else None
            for client in (w.client, w.foreign, APIClient()):
                # This retired mixin refuses before perform_authentication, so
                # install the SQL fence directly as well as the normal HTTP fence.
                with connection.execute_wrapper(_no_write), no_domain_writes():
                    response = command(client, "member-certifications", "get", [w.space.pk])
                # Decision 319 addendum: retirement precedes auth and lookup; registered,
                # not routeless. No fictional successful certification handler is used.
                assert response_pair(response) == (410, "certifications_retired")
                assert domain_rows() == before
            if disabled:
                toggle(w.space, key, original)
    saved = CertificationGrant.objects.get(pk=grant.pk)
    assert (saved.certification_type_id, saved.notes) == (certification.pk, "Legacy training proof")
