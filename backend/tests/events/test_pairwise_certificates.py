"""Pairwise comparisons count as judging work for judge certificates and survive tenant remapping."""

import pytest

from apps.events.certificates.contribution_proof import snapshot
from apps.events.judging.boundary import mutation
from apps.events.judging.lifecycle import invalidate_snapshot_locked
from apps.events.judging.models_pairwise import JudgePairwiseComparison
from apps.tenant_migration.semantic_certificate_proof import remap_contribution_proof
from tests.events.pairwise_helpers import judge_command, judge_until_done, pairwise_round, pairwise_world

pytestmark = pytest.mark.django_db


def test_valid_decisive_comparisons_are_judge_work_in_the_certificate_proof(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=3, judges=2)
    round = pairwise_round(world)
    judge_until_done(world, round, 0)
    proof = snapshot(event_id=world.event.pk, assignment_id=world.roles[0])
    rows = JudgePairwiseComparison.objects.filter(judge_id=world.roles[0]).order_by("pk")
    assert proof["comparisons"] == [[row.pk, row.version] for row in rows] and len(rows) == 2
    assert proof["scores"] == [] and proof["ballots"] == []
    # A judge who only viewed and skipped has no work, and an earlier-shape proof has no new key.
    judge_command(world, 1, "next", round)
    judge_command(world, 1, "skip", round)
    assert "comparisons" not in snapshot(event_id=world.event.pk, assignment_id=world.roles[1])


def test_invalidated_comparisons_leave_the_proof(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=3, judges=1)
    round = pairwise_round(world)
    judge_until_done(world, round, 0)
    with mutation(world.event.pk, world.manager) as (event, locks):
        for pk in world.snapshots:
            invalidate_snapshot_locked(event=event, snapshot_id=pk, locks=locks, actor=world.manager)
    assert "comparisons" not in snapshot(event_id=world.event.pk, assignment_id=world.roles[0])


def test_a_pairwise_judge_is_eligible_for_a_judge_certificate(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=3, judges=1)
    round = pairwise_round(world)
    from apps.events.contracts.certificate_registration import _compared
    from apps.events.contributions.models_roles import EventRoleAssignment
    role = EventRoleAssignment.objects.get(pk=world.roles[0])
    assert not _compared(world.event.pk, role)
    judge_until_done(world, round, 0)
    assert _compared(world.event.pk, role)


def test_portable_proof_remaps_comparison_ids_and_keeps_versions():
    proof = {"version": 1, "role_assignment_id": 7, "role": "judge", "scores": [], "ballots": [],
             "comparisons": [[11, 2]]}
    seen = []

    def mapped(model, pk):
        seen.append((model, pk))
        return pk + 100
    value = remap_contribution_proof({"contribution_proof": proof}, mapped)
    assert value["contribution_proof"]["comparisons"] == [[111, 2]]
    assert ("events.JudgePairwiseComparison", 11) in seen
    earlier = {key: value for key, value in proof.items() if key != "comparisons"}
    legacy = remap_contribution_proof({"contribution_proof": earlier}, mapped)
    assert "comparisons" not in legacy["contribution_proof"]
