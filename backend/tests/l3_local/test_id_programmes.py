"""L3 ID programmes (`membership.id_programmes`, #128 C-12/C-13, SPEC §4.3, §5.2)."""
import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.card_designs import tokens
from apps.card_designs.holders import spec_for
from apps.id_programmes import cards as programme_cards, imports, invites, services
from apps.id_programmes.models import IdProgrammeCard
from apps.organizations.models import Organization, OrganizationMakerspace
from tests.l3_local.helpers import card_space, client, custom_staff, manager, member

pytestmark = pytest.mark.django_db
FEATURE = ("membership.id_programmes",)


def _owned(slug):
    space = card_space(slug, features=FEATURE)
    org = Organization.objects.create(name=f"Org {slug}", slug=f"org-{slug}")
    OrganizationMakerspace.objects.create(organization=org, makerspace=space, relationship="owner")
    return space, org


def _programme(slug, **values):
    space, org = _owned(slug)
    sm = manager(space)
    programme = services.create(sm, org, space, {"name": "Student ID", **values})
    services.update(sm, programme, {"status": "active", "registration_open": True})
    programme.refresh_from_db()
    return space, org, sm, programme


def test_programmes_need_an_owned_host_space():
    space = card_space("ip-unowned", features=FEATURE)
    org = Organization.objects.create(name="Elsewhere", slug="elsewhere")
    with pytest.raises(ValidationError):
        services.create(manager(space), org, space, {"name": "Nope"})


def test_join_numbering_and_verify():
    space, _org, sm, programme = _programme("ip-join")
    user, _m = member(space, "joiner")
    response = client(user).post(f"/api/v1/public/organizations/{programme.organization.slug}/id-programmes/"
                                 f"{programme.slug}/join", {"answers": {}}, format="json")
    assert response.status_code == 201, response.content
    card = IdProgrammeCard.objects.get(programme=programme)
    assert card.status == "pending" and card.email == user.email and spec_for("programme_card").standing(card) is None
    programme_cards.decide(sm, programme, "approve", [card.pk])
    card.refresh_from_db()
    assert card.id_number == f"{programme.id_prefix}-{timezone.now().year}-0001"
    token = tokens.live("programme_card", card)
    assert token is not None
    from rest_framework.test import APIClient
    body = APIClient().get(f"/api/v1/public/card-verifications/{token.token}").json()
    assert body["status"] == "valid" and body["label"] == "Student ID" and body["issuer"]["kind"] == "organisation"


def test_one_request_per_person_and_approval_off_auto_approves():
    space, _org, sm, programme = _programme("ip-auto", requires_approval=False)
    user, _m = member(space, "auto")
    from apps.id_programmes.join import join
    card = join(user, programme, answers={})
    assert card.status == "approved" and card.id_number
    with pytest.raises(ValidationError):
        join(user, programme, answers={})


def test_numbers_survive_revoke_and_reinstate_and_renew_moves_expiry():
    space, _org, sm, programme = _programme("ip-numbers", validity_mode="days", validity_days=30)
    first = programme_cards.add(sm, programme, name="A", email="a@example.com")
    second = programme_cards.add(sm, programme, name="B", email="b@example.com")
    programme_cards.decide(sm, programme, "approve", [first.pk, second.pk])
    first.refresh_from_db()
    number, expiry = first.id_number, first.expires_at
    with pytest.raises(ValidationError):
        programme_cards.decide(sm, programme, "revoke", [first.pk])
    programme_cards.decide(sm, programme, "revoke", [first.pk], reason="Left the course")
    programme_cards.decide(sm, programme, "reinstate", [first.pk])
    first.refresh_from_db()
    assert first.id_number == number and first.expires_at == expiry and first.status == "approved"
    assert first.status_reason == ""
    programme_cards.decide(sm, programme, "renew", [first.pk])
    first.refresh_from_db()
    assert first.expires_at > expiry
    programme.refresh_from_db()
    assert programme.next_sequence == 3


def test_import_preview_commit_dry_run_and_dedup():
    space, _org, sm, programme = _programme("ip-import")
    programme_cards.add(sm, programme, name="Existing", email="old@example.com")
    csv = "﻿Full Name,Email\r\nPriya,priya@example.com\r\n,missing@example.com\r\nDup,priya@example.com\r\n" \
          "Old,old@example.com\r\nBad,not-an-email\r\n"
    preview = imports.preview(programme, csv)
    assert preview["mapping"]["name"] == 0 and preview["mapping"]["email"] == 1
    assert preview["to_create"] == 1
    reasons = {row["reason"] for row in preview["skipped"]}
    assert reasons == {"no_name", "duplicate_in_file", "already_in_programme", "bad_email"}
    dry = imports.commit(sm, programme, csv, preview["mapping"], dry_run=True)
    assert dry["created"] == 0 and IdProgrammeCard.objects.filter(programme=programme).count() == 1
    result = imports.commit(sm, programme, csv, preview["mapping"])
    assert result["created"] == 1
    imported = IdProgrammeCard.objects.get(programme=programme, source="import")
    assert imported.user is None and imported.status == "pending"


def test_invite_links_only_with_the_verified_email():
    space, _org, sm, programme = _programme("ip-invite")
    card = programme_cards.add(sm, programme, name="Invitee", email="invitee@example.com")
    import secrets
    token = secrets.token_urlsafe(32)
    IdProgrammeCard.objects.filter(pk=card.pk).update(invite_digest=invites._digest(token))
    wrong, _m = member(space, "wrong")
    with pytest.raises(Exception):
        invites.accept(wrong, card.pk, token)
    from apps.accounts.models import User
    right = User.objects.create_user(username="invitee", email="invitee@example.com", access_status="active")
    with pytest.raises(ValidationError):
        invites.accept(right, card.pk, token)  # email not verified yet
    User.objects.filter(pk=right.pk).update(email_verified_at=timezone.now())
    right.refresh_from_db()
    linked = invites.accept(right, card.pk, token)
    assert linked.user_id == right.pk and linked.invite_digest == ""


def test_staff_without_programme_authority_cannot_see_programmes():
    space, _org, sm, programme = _programme("ip-mask")
    programme_cards.add(sm, programme, name="Masked", email="masked@example.com")
    other = custom_staff(space, ["event_manager"], "viewer")
    assert client(other).get(f"/api/v1/admin/id-programmes/{programme.pk}/cards").status_code == 404
    assert client(other).patch(f"/api/v1/admin/id-programmes/{programme.pk}", {"name": "X"},
                               format="json").status_code == 404


def test_capability_off_hides_every_route():
    space, _org, sm, programme = _programme("ip-off")
    space.enabled_features = [key for key in space.enabled_features if key != "membership.id_programmes"]
    space.save(update_fields=["enabled_features"])
    assert client(sm).get(f"/api/v1/admin/id-programmes/{programme.pk}").status_code == 404
    from rest_framework.test import APIClient
    assert APIClient().get(f"/api/v1/public/organizations/{programme.organization.slug}/id-programmes").json() == []


def test_delete_only_without_approved_cards():
    space, _org, sm, programme = _programme("ip-delete")
    card = programme_cards.add(sm, programme, name="A", email="a2@example.com")
    programme_cards.decide(sm, programme, "approve", [card.pk])
    # Decision 219(h): a used programme is archived, not deleted (409 archive_instead).
    with pytest.raises(services.ArchiveInstead):
        services.delete(sm, programme)


def test_delete_refuses_a_programme_whose_design_was_published():
    from apps.card_designs.models import CardDesign
    space, _org, sm, programme = _programme("ip-delete-design")
    CardDesign.objects.create(makerspace=space, domain=CardDesign.Domain.ID_PROGRAMME if hasattr(
        CardDesign.Domain, "ID_PROGRAMME") else list(CardDesign.Domain)[0], programme=programme,
        document={}, published_revision=1, published_at=timezone.now())
    # Deleting would cascade the published design away (219(h)); archive instead.
    with pytest.raises(services.ArchiveInstead):
        services.delete(sm, programme)
