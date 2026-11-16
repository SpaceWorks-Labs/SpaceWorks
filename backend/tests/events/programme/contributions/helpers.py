"""PostgreSQL domain fixtures. The test port substitutes only cross-lane services."""
from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4
from django.utils import timezone
from apps.encryption.write_fence import assert_mapped_write_allowed
from apps.events.contributions.models import EventRoleAssignment, EventRolePosting, EventShift
from apps.events.contributions.ports import install
from tests.events.ticketing_helpers import event_space, account, open_event


def setup_shift(settings):
    settings.PII_ENCRYPTION_ENABLED = False
    space = event_space(f"contributors-{uuid4().hex[:8]}")
    space.enabled_features += ["events.volunteering", "events.hackathons", "events.mentoring", "events.mentor_rounds"]
    space.save(update_fields=["enabled_features"])
    event = open_event(space)
    event.starts_at = timezone.now() - timedelta(hours=1)
    event.ends_at = timezone.now() + timedelta(hours=4)
    event.save(update_fields=["starts_at", "ends_at"])
    posting = EventRolePosting.objects.create(event=event, makerspace=space, role="volunteer",
        title="Bench crew", state="open", opens_at=timezone.now() - timedelta(days=1),
        closes_at=event.ends_at)
    shift = EventShift.objects.create(event=event, makerspace=space, posting=posting,
        starts_at=timezone.now() + timedelta(hours=1), ends_at=event.ends_at,
        signup_deadline=timezone.now() + timedelta(minutes=30), task="Workshop setup", capacity=1,
        waitlist_enabled=True, approval_required=False)
    users = [account(f"contributor-{uuid4().hex[:10]}") for _ in range(2)]
    from tests.events.collab_helpers import make_staff
    issuer = make_staff(space, username=f"contributor-issuer-{uuid4().hex[:8]}")
    roles = [EventRoleAssignment.objects.create(event=event, makerspace=space, posting=posting,
        member=user, role="volunteer", state="approved", approved_by=issuer) for user in users]
    adapter = TestPorts(event, users)
    adapter.issuer = issuer
    install(adapter)
    return space, event, posting, shift, users, roles, adapter


class TestPorts:
    __test__ = False

    def __init__(self, event, users):
        self.event = event
        self.users = users
        self.grants = SimpleNamespace(sync_shift_locked=lambda **kwargs: None,
                                      sync_role_locked=lambda **kwargs: None)
        self.forms = SimpleNamespace()
        self.members = {}
        self.teams = self
        self.messages = []

    @contextmanager
    def fences(self, *, tenant_ids, account_ids):
        for pk in tenant_ids:
            assert_mapped_write_allowed(pk)
        yield

    def prepare_private_write(self, **kwargs):
        pass  # This fixture explicitly disables PII encryption; no fake crypto proof.

    def require_event_feature(self, *, event_id, feature):
        assert event_id == self.event.pk

    def lock_authority_locked(self, *, actor_id, event_id, locks):
        assert event_id == self.event.pk
        assert actor_id in locks.account_ids

    def require_role_audience(self, *, actor_id, event_id, posting_id):
        assert event_id == self.event.pk
        assert actor_id in [user.pk for user in self.users]

    def require_requirements(self, **kwargs):
        pass  # Requirements validation has separate refusal tests.

    def member_ids(self, *, event_id, team_id):
        from rest_framework.exceptions import NotFound
        if event_id != self.event.pk or team_id not in self.members:
            raise NotFound()
        return tuple(self.members[team_id])

    def require_member(self, *, actor_id, event_id, team_id):
        from rest_framework.exceptions import NotFound
        if actor_id not in self.member_ids(event_id=event_id, team_id=team_id):
            raise NotFound()

    def require_eligible(self, *, event_id, team_id, at):
        self.member_ids(event_id=event_id, team_id=team_id)

    def require_practice(self, *, event_id, team_id, practice_run_id):
        self.member_ids(event_id=event_id, team_id=team_id)

    def alias(self, **kwargs):
        return "Team bench"

    def own_ids(self, *, actor_id, event_id):
        return tuple(pk for pk, members in self.members.items() if actor_id in members)

    def skills(self, **kwargs):
        return ("pcb",)

    def ids(self, **kwargs):
        return tuple(self.members)

    def organizer_ids(self, **kwargs):
        return ()

    def deliver_help(self, **kwargs):
        self.messages.append(kwargs)

    def delegation_scope(self, **kwargs):
        # The real source-aware delegation check; this fixture only stubs I/O-bearing ports.
        from apps.events.contributions.runtime import ContributorPorts
        return ContributorPorts().delegation_scope(**kwargs)
