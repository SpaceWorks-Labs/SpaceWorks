"""Real rows for pairwise judging tests; the judging ports project them as plain values.

The installed providers read B's submission state and C's role entitlements. These tests own
those inputs through a small subclass so they stay about D's pairwise behaviour only.
"""

from types import SimpleNamespace
from uuid import uuid4

from django.apps import apps
from django.db import transaction
from django.http import Http404

from apps.events.contributions.models_roles import EventGrantEntitlement, EventRoleAssignment
from apps.events.judging import ports
from apps.events.judging.ports import Judge, Snapshot
from apps.events.judging.provider_runtime import JudgingProviders
from apps.events.models import EventStaffGrant
from apps.events.submissions.models_projects import HackathonSubmission, SubmissionSnapshot
from apps.makerspaces.platform import feature_enabled, module_enabled
from tests.events.collab_helpers import make_staff
from tests.events.ticketing_helpers import account, event_space, open_event


class PairwisePorts(JudgingProviders):
    """Real locks, fences and authority; snapshot/judge values come from the test's own table."""

    def __init__(self):
        self.snaps, self.judge_rows, self.notices = {}, {}, []

    def require_programme(self, event, *, gallery=False):
        if not module_enabled(event.makerspace, "events") or not feature_enabled(event.makerspace, "events.hackathons"):
            raise Http404

    def snapshot(self, snapshot_id):
        if snapshot_id not in self.snaps:
            raise Http404
        return self.snaps[snapshot_id]

    def snapshots(self, event_id):
        return tuple(s for s in self.snaps.values() if s.event_id == event_id)

    def judge(self, role_assignment_id):
        if role_assignment_id not in self.judge_rows:
            raise Http404
        return self.judge_rows[role_assignment_id]

    def judges(self, event_id):
        return tuple(j for _, j in sorted(self.judge_rows.items()) if j.event_id == event_id)

    def is_conflicted(self, *, member_id, team_id, round_id):
        return False

    def notify_intent(self, notice_id):
        self.notices.append(notice_id)

    def publish_retention_locked(self, *, event_id, first_published_at, locks):
        self.assert_lock_context(locks)  # B's retention anchor is out of scope for D's pairwise tests.


def pairwise_world(settings, monkeypatch, *, projects=4, judges=3, enabled=True):
    settings.PII_ENCRYPTION_ENABLED = False
    space = event_space(f"pairwise-{uuid4().hex[:8]}")
    space.enabled_features += ["events.hackathons"] + (["events.pairwise_judging"] if enabled else [])
    space.save(update_fields=["enabled_features"])
    event = open_event(space)
    manager = make_staff(space, username=f"pairwise-manager-{uuid4().hex[:6]}")
    adapter = PairwisePorts()
    monkeypatch.setattr(ports, "_installed", adapter)
    snapshot_ids = [_project(event, adapter, index) for index in range(projects)]
    judge_users, role_ids = [], []
    for index in range(judges):
        user = account(f"judge-{uuid4().hex[:10]}")
        role = EventRoleAssignment.objects.create(event=event, makerspace=space, member=user, role="judge",
                                                  state="approved", approved_by=manager)
        grant = EventStaffGrant.objects.create(event=event, makerspace=space, user=user, granted_by=manager,
                                               permissions=["judge"])
        EventGrantEntitlement.objects.create(event=event, makerspace=space, grant=grant, source_kind="manual",
                                             permissions=["judge"], created_by=manager)
        adapter.judge_rows[role.pk] = Judge(role_assignment_id=role.pk, event_id=event.pk, member_id=user.pk, active=True)
        judge_users.append(user)
        role_ids.append(role.pk)
    return SimpleNamespace(space=space, event=event, manager=manager, ports=adapter, snapshots=snapshot_ids,
                           judges=judge_users, roles=role_ids)


def _project(event, adapter, index, mates=0):
    """One submitted project. `mates` extra accounts are sealed into the snapshot at INSERT time: the snapshot is
    immutable afterwards (trigger `events_submissionsnapshot_immutable`), so members can only be set here."""
    leader = account(f"maker-{uuid4().hex[:10]}")
    mate_ids = [account(f"mate-{uuid4().hex[:10]}").pk for _ in range(mates)]
    with transaction.atomic():
        application = apps.get_model("events", "HackathonApplication").objects.create(event=event, member=leader)
        name = f"Team {index} {uuid4().hex[:4]}"
        team = apps.get_model("events", "HackathonTeam").objects.create(event=event, leader=leader, name=name,
                                                                          normalized_name=name.casefold())
        apps.get_model("events", "HackathonTeamMember").objects.create(event=event, team=team, member=leader,
            application=application, creator=leader, state="active")
    project = HackathonSubmission.objects.create(event=event, team=team, state="submitted", triage="eligible")
    snapshot = SubmissionSnapshot.objects.create(submission=project, sequence=1, submitted_by=leader,
        project={"title": f"Project {index}"}, content_sha256=f"{index:064x}", sealed_member_ids=[leader.pk, *mate_ids])
    adapter.snaps[snapshot.pk] = Snapshot(id=snapshot.pk, event_id=event.pk, team_id=team.pk, member_ids=(leader.pk, *mate_ids),
        track_ids=(), prize_ids=(), title=f"Project {index}", description="", content_sha256=snapshot.content_sha256,
        eligible=True, current=True, metadata_public=False, public_asset_ids=(), public_links=(), expires_at=None)
    return snapshot.pk


def command(version=0, **fields):
    return {"operation_id": str(uuid4()), "expected_version": version, **fields}


def pairwise_round(world, *, key="final", min_reviews=3, open_round=True, **fields):
    from apps.events.judging.definitions_workflow import save_definition
    from apps.events.judging.models_definitions import JudgingRound
    from apps.events.judging.round_workflow import transition
    saved = save_definition(world.event.pk, actor=world.manager, kind="judging-rounds",
                            data=command(key=key, mode="pairwise", min_reviews=min_reviews, **fields))
    if open_round:
        transition(world.event.pk, saved["id"], actor=world.manager, action="open", data=command(saved["version"]))
    return JudgingRound.objects.get(pk=saved["id"])


def judge_command(world, index, name, round, **fields):
    """Run a pairwise judge command with the judge's current cursor version."""
    from apps.events.judging import pairwise_workflow as workflow
    from apps.events.judging.models_pairwise import JudgePairwiseCursor
    cursor = JudgePairwiseCursor.objects.filter(round=round, judge_id=world.roles[index]).first()
    handler = {"next": workflow.next_project, "compare": workflow.compare, "skip": workflow.skip_current,
               "recuse": workflow.recuse_current}[name]
    return handler(world.event.pk, round.pk, actor=world.judges[index],
                   data=command(cursor.version if cursor else 0, **fields))


def judge_until_done(world, round, index, outcome="current"):
    """Walk one judge through every project: view the first, then compare each next one."""
    from apps.events.judging.models_pairwise import JudgePairwiseCursor
    while True:
        cursor = JudgePairwiseCursor.objects.get(round=round, judge_id=world.roles[index])
        if cursor.current_id is None:
            judge_command(world, index, "next", round)
            cursor.refresh_from_db()
            if cursor.current_id is None:
                return
        elif cursor.previous_id is None:
            judge_command(world, index, "next", round)
        else:
            judge_command(world, index, "compare", round, outcome=outcome)
