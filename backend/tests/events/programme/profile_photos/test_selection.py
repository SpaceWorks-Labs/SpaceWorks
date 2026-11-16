from uuid import uuid4
import pytest
from rest_framework.exceptions import NotFound

from apps.events.credentials.errors import ProgrammeConflict
from apps.events.profile_photos.models import EventMemberPresentation
from apps.events.profile_photos.selection_workflow import options, select, source_revision
from apps.events.profile_photos.policy import print_profile
from apps.makerspaces.models_profiles import MemberProfile
from tests.events.checkin_helpers import make_event, make_member, make_space, register, add_membership

pytestmark = pytest.mark.django_db


def setup():
    host, source = make_space("photo-host"), make_space("photo-source")
    event, member = make_event(host), make_member(host)
    register(event, member)
    membership = add_membership(source, member)
    profile = MemberProfile.objects.create(membership=membership, avatar_key=f"member/{source.pk}/portrait.png")
    return event, member, profile


def choose(event, member, profile, **changes):
    values = dict(operation_id=uuid4(), expected_version=0, profile_id=profile.pk,
                  membership_id=profile.membership_id, source_revision=source_revision(profile),
                  print_photo_consent=False, public_card_consent=False, public_card_scopes=[])
    values.update(changes)
    return select(event.pk, actor=member, **values)


def test_options_are_explicit_with_no_preselected_host_or_first_membership():
    event, member, profile = setup()
    result = options(event, member)
    assert result["selected_profile_id"] is None and result["no_photo_allowed"] is True
    assert any(row["profile_id"] == profile.pk for row in result["options"])
    assert not EventMemberPresentation.objects.exists()


def test_cross_venue_photo_choice_does_not_grant_source_authority_and_consents_are_independent():
    event, member, profile = setup()
    result = choose(event, member, profile, print_photo_consent=True)
    presentation = EventMemberPresentation.objects.get(pk=result["id"])
    assert print_profile(presentation).pk == profile.pk
    assert presentation.public_card_consent is False and presentation.public_card_scopes == []
    profile.membership.status = "revoked"
    profile.membership.save(update_fields=("status",))
    presentation.refresh_from_db()
    assert print_profile(presentation) is None


def test_foreign_profile_and_stale_revision_fail_without_creating_a_presentation():
    event, member, profile = setup()
    other = make_member(profile.membership.makerspace, "another")
    foreign = MemberProfile.objects.create(membership=other.makerspace_memberships.get(makerspace=profile.membership.makerspace))
    with pytest.raises(NotFound):
        choose(event, member, foreign)
    with pytest.raises(ProgrammeConflict):
        choose(event, member, profile, source_revision="old")
    assert not EventMemberPresentation.objects.exists()


def test_same_operation_replays_and_changed_selection_requires_fresh_version():
    event, member, profile = setup()
    operation = uuid4()
    first = choose(event, member, profile, operation_id=operation)
    assert choose(event, member, profile, operation_id=operation) == first
    with pytest.raises(ProgrammeConflict):
        choose(event, member, profile, operation_id=operation, print_photo_consent=True)
    cleared = select(event.pk, actor=member, operation_id=uuid4(), expected_version=first["version"],
                     profile_id=None, membership_id=None, source_revision=None)
    assert cleared["profile_id"] is None and cleared["public_card_scopes"] == []
