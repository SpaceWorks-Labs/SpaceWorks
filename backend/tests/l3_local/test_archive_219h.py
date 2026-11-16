"""Owner decision 219(h): card designs and ID programmes are archived when removed; a hard
delete is allowed only for one that was never used. Issued programme cards are never deleted."""
import pytest

from apps.audit.models import AuditLog
from apps.card_designs import designs, resolution
from apps.card_designs.default_templates import build
from apps.card_designs.models import CardDesign
from apps.id_programmes import cards as programme_cards, services
from apps.id_programmes.models import IdProgramme, IdProgrammeCard
from apps.organizations.models import Organization, OrganizationMakerspace
from tests.l3_local.helpers import card_space, client, manager

pytestmark = pytest.mark.django_db
FEATURE = ("membership.id_programmes",)


def _plan_override(slug):
    from apps.makerspaces.models import MembershipPlan
    space = card_space(slug)
    sm = manager(space)
    plan = MembershipPlan.objects.create(makerspace=space, name="Monthly")
    created = client(sm).post(f"/api/v1/admin/makerspaces/{space.pk}/card-designs", {"plan_id": plan.pk},
                              format="json")
    assert created.status_code == 201, created.content
    return space, sm, plan, CardDesign.objects.get(pk=created.json()["id"])


def _publish(sm, design):
    saved = designs.save(sm, design, build("bold", "member_cards"), expected_revision=design.revision)
    designs.publish(sm, saved)
    saved.refresh_from_db()
    return saved


def test_never_published_override_is_hard_deleted():
    _space, sm, _plan, design = _plan_override("ar-del")
    response = client(sm).delete(f"/api/v1/admin/card-designs/{design.pk}")
    assert response.status_code == 204, response.content
    assert not CardDesign.objects.filter(pk=design.pk).exists()


def test_published_override_refuses_delete_and_archives_instead():
    space, sm, plan, design = _plan_override("ar-arch")
    design = _publish(sm, design)
    api = client(sm)
    refused = api.delete(f"/api/v1/admin/card-designs/{design.pk}")
    assert refused.status_code == 409 and refused.json()["code"] == "archive_instead"
    assert CardDesign.objects.filter(pk=design.pk).exists()
    assert resolution.resolve(space.pk, "member_cards", plan_id=plan.pk)[1] == design

    archived = api.post(f"/api/v1/admin/card-designs/{design.pk}/archive")
    assert archived.status_code == 200 and archived.json()["archived_at"]
    design.refresh_from_db()
    assert design.archived_at is not None and design.revisions.exists()
    # Holders fall back past the archived override; the active list hides it.
    assert resolution.resolve(space.pk, "member_cards", plan_id=plan.pk)[1] != design
    listed = [row["id"] for row in api.get(f"/api/v1/admin/makerspaces/{space.pk}/card-designs").json()]
    assert design.pk not in listed
    archived_list = api.get(f"/api/v1/admin/makerspaces/{space.pk}/card-designs?archived=true").json()
    assert [row["id"] for row in archived_list] == [design.pk]
    assert AuditLog.objects.filter(action="card_design.archived").exists()

    restored = api.post(f"/api/v1/admin/card-designs/{design.pk}/unarchive")
    assert restored.status_code == 200 and restored.json()["archived_at"] is None
    assert resolution.resolve(space.pk, "member_cards", plan_id=plan.pk)[1] == design


def test_asking_for_an_archived_targets_design_again_restores_it():
    space, sm, plan, design = _plan_override("ar-recreate")
    design = _publish(sm, design)
    client(sm).post(f"/api/v1/admin/card-designs/{design.pk}/archive")
    again = client(sm).post(f"/api/v1/admin/makerspaces/{space.pk}/card-designs", {"plan_id": plan.pk},
                            format="json")
    assert again.status_code == 200 and again.json()["id"] == design.pk and again.json()["archived_at"] is None


def test_space_default_cannot_be_archived_or_deleted():
    space = card_space("ar-default")
    sm = manager(space)
    default, _ = resolution.get_or_create(space, "member_cards", actor=sm)
    assert client(sm).post(f"/api/v1/admin/card-designs/{default.pk}/archive").status_code == 400
    assert client(sm).delete(f"/api/v1/admin/card-designs/{default.pk}").status_code == 400


def _programme(slug):
    space = card_space(slug, features=FEATURE)
    org = Organization.objects.create(name=f"Org {slug}", slug=f"org-{slug}")
    OrganizationMakerspace.objects.create(organization=org, makerspace=space, relationship="owner")
    sm = manager(space)
    programme = services.create(sm, org, space, {"name": "Student ID"})
    services.update(sm, programme, {"status": "active", "registration_open": True})
    programme.refresh_from_db()
    return space, org, sm, programme


def test_unused_programme_is_hard_deleted():
    _space, _org, sm, programme = _programme("ar-p-del")
    programme_cards.add(sm, programme, name="Pending", email="pending@example.com")
    assert client(sm).delete(f"/api/v1/admin/id-programmes/{programme.pk}").status_code == 204
    assert not IdProgramme.objects.filter(pk=programme.pk).exists()


def test_used_programme_is_archived_closed_and_keeps_its_cards():
    _space, org, sm, programme = _programme("ar-p-arch")
    card = programme_cards.add(sm, programme, name="A", email="a@example.com")
    programme_cards.decide(sm, programme, "approve", [card.pk])
    api = client(sm)
    refused = api.delete(f"/api/v1/admin/id-programmes/{programme.pk}")
    assert refused.status_code == 409 and refused.json()["code"] == "archive_instead"

    body = api.post(f"/api/v1/admin/id-programmes/{programme.pk}/archive").json()
    assert body["archived_at"] and body["status"] == "closed" and body["registration_open"] is False
    card.refresh_from_db()
    assert card.status == "approved" and card.id_number
    active = [row["id"] for row in api.get(f"/api/v1/admin/organizations/{org.pk}/id-programmes").json()]
    archived = [row["id"] for row in api.get(f"/api/v1/admin/organizations/{org.pk}/id-programmes?archived=true").json()]
    assert programme.pk not in active and archived == [programme.pk]
    # Reopening needs a restore first; a restore keeps it closed.
    assert api.patch(f"/api/v1/admin/id-programmes/{programme.pk}", {"status": "active"},
                     format="json").status_code == 400
    restored = api.post(f"/api/v1/admin/id-programmes/{programme.pk}/unarchive").json()
    assert restored["archived_at"] is None and restored["status"] == "closed"
    actions = set(AuditLog.objects.values_list("action", flat=True))
    assert {"id_programme.archived", "id_programme.unarchived", "id_programme.closed"} <= actions


def test_issued_programme_card_cannot_be_deleted_but_a_pending_one_can():
    _space, _org, sm, programme = _programme("ar-card")
    issued = programme_cards.add(sm, programme, name="Issued", email="i@example.com")
    pending = programme_cards.add(sm, programme, name="Pending", email="p@example.com")
    programme_cards.decide(sm, programme, "approve", [issued.pk])
    api = client(sm)
    refused = api.delete(f"/api/v1/admin/id-programme-cards/{issued.pk}")
    assert refused.status_code == 409 and refused.json()["code"] == "revoke_instead"
    assert IdProgrammeCard.objects.filter(pk=issued.pk).exists()
    assert api.delete(f"/api/v1/admin/id-programme-cards/{pending.pk}").status_code == 204
    assert not IdProgrammeCard.objects.filter(pk=pending.pk).exists()
