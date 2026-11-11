from datetime import timedelta
import pytest
from django.utils import timezone

from apps.events.services_clone import duplicate_event
from apps.events.hackathons.admission_models import HackathonConfig, HackathonCocRevision
from apps.events.contributions.models_roles import EventRolePosting, EventSponsor, EventSponsorTrack
from apps.events.contributions.models_shifts import EventShift
from apps.events.judging.models_definitions import HackathonTrack, HackathonPrize, JudgingRound, JudgingCriterion
from tests.events.staff_grant_helpers import grant_fixture


@pytest.mark.django_db(transaction=True)
def test_clone_copies_definitions_with_new_ids_and_never_restores_authority():
    space, manager, member, event, grant = grant_fixture()
    config = HackathonConfig.objects.create(event=event, enabled=True, team_max=5,
        application_form=[], review_round=9, first_results_published_at=timezone.now())
    HackathonCocRevision.objects.create(event=event, revision=1, body="Respect other makers.")
    sponsor = EventSponsor.objects.create(event=event, makerspace=space, label="Tools sponsor", page_reference="source-only")
    posting = EventRolePosting.objects.create(event=event, makerspace=space, role="volunteer", title="Door crew",
        opens_at=event.starts_at-timedelta(days=5), closes_at=event.starts_at,
        permission_preset=["check_in"], permission_issuer=manager, state="open")
    EventShift.objects.create(event=event, makerspace=space, posting=posting,
        starts_at=event.starts_at, ends_at=event.ends_at, signup_deadline=event.starts_at,
        permission_preset=["check_in"], task="Welcome")
    track = HackathonTrack.objects.create(event=event, name="Hardware")
    prize = HackathonPrize.objects.create(event=event, name="Build prize", sponsor=sponsor, track=track)
    EventSponsorTrack.objects.create(event=event, makerspace=space, sponsor=sponsor, track=track)
    round = JudgingRound.objects.create(event=event, key="final", mode="weighted_1_5")
    JudgingCriterion.objects.create(round=round, key="craft", label="Craft", weight=1, anchors={"1": "Early", "5": "Complete"})
    clone = duplicate_event(event, actor=manager)
    copied = HackathonConfig.objects.get(event=clone)
    assert not copied.enabled and copied.review_round == 1 and copied.team_max == 5
    assert copied.first_results_published_at is None and copied.results_revision_id is None
    new_post = EventRolePosting.objects.get(event=clone)
    assert new_post.pk != posting.pk and new_post.state == "draft"
    assert not new_post.permission_preset and new_post.permission_issuer_id is None
    new_shift = EventShift.objects.get(event=clone)
    assert new_shift.posting_id == new_post.pk and new_shift.state == "closed" and not new_shift.permission_preset
    new_prize = HackathonPrize.objects.get(event=clone)
    assert new_prize.track_id != track.pk and new_prize.sponsor_id != sponsor.pk
    assert new_prize.sponsor.page_reference == ""
    assert EventSponsorTrack.objects.filter(event=clone, sponsor_id=new_prize.sponsor_id,
                                            track_id=new_prize.track_id).exists()
    assert JudgingRound.objects.get(event=clone).state == "draft"
    from apps.events.models_staff_grants import EventStaffGrant
    assert not EventStaffGrant.objects.filter(event=clone).exists()
    config.refresh_from_db()
    assert config.enabled and config.review_round == 9
