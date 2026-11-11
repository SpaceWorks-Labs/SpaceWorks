"""People's choice rows and routes join every registry a new model or route must join (#181 S3)."""

import pytest
from django.urls import reverse

ROUTES = ("events-programme-admin-peoples-choice", "events-programme-admin-peoples-choice-standings",
          "events-programme-admin-peoples-choice-publish", "events-programme-admin-peoples-choice-votes",
          "events-programme-admin-peoples-choice-vote-void", "events-programme-admin-peoples-choice-payouts",
          "events-programme-member-peoples-choice", "events-programme-member-peoples-choice-vote",
          "events-programme-public-peoples-choice")
MODELS = ("events.PeoplesChoiceConfig", "events.PeoplesChoiceVote", "events.PeoplesChoiceResult",
          "events.PeoplesChoiceStanding")


def test_every_route_is_catalogued_native_and_mounted():
    from apps.accounts.programme_route_catalog import BY_NAME, NATIVE_DECISIONS
    for name in ROUTES:
        assert name in BY_NAME and NATIVE_DECISIONS[name] == "native"
    kwargs = {"pk": 1}
    assert reverse(ROUTES[0], kwargs=kwargs).endswith("/admin/events/1/peoples-choice/")
    assert reverse(ROUTES[7], kwargs={"pk": 1, "makerspace_id": 2}).endswith("/member/makerspaces/2/events/1/peoples-choice/vote/")


def test_claim_sessions_are_refused_on_the_vote_and_anonymous_on_the_public_read():
    from apps.accounts.claim_route_types import AnonymousRead, Refused
    from apps.accounts.claim_routes_programme import CLAIM_ROUTES
    assert isinstance(CLAIM_ROUTES[("events-programme-member-peoples-choice-vote", "POST")], Refused)
    assert isinstance(CLAIM_ROUTES[("events-programme-public-peoples-choice", "GET")], AnonymousRead)


def test_admin_routes_are_staff_surface_and_session_only():
    from apps.accounts.delegated_routes import route_class
    from apps.apiclients.scope_registry_programme import SESSION_ONLY
    for name in ROUTES[:6]:
        assert route_class(name) is not None and name in SESSION_ONLY


def test_models_are_in_the_tenant_dump_and_export_catalogues():
    from apps.data_export.classification import EXPORTED_MODEL_FIELDS
    from apps.data_export.datasets import PROGRAMME_DATASETS
    from apps.tenant_migration.catalog_events_programme import FIELD_NAMES
    for label in MODELS:
        assert label in FIELD_NAMES and label in EXPORTED_MODEL_FIELDS and label in PROGRAMME_DATASETS
    assert "peoples_choice_standing" in EXPORTED_MODEL_FIELDS["events.HackathonPrizePayout"]


def test_ownership_predicates_reach_the_makerspace():
    from apps.tenant_rls.policies import build_plans
    plans, unresolved = build_plans()
    assert not {label for label in unresolved if "PeoplesChoice" in label}


def test_user_edges_stay_on_the_shell_account():
    from apps.accounts.merge_registry import disposition_for
    for label, field in (("events.PeoplesChoiceVote", "voter"), ("events.PeoplesChoiceVote", "voided_by"),
                         ("events.PeoplesChoiceResult", "published_by")):
        assert disposition_for(label, field) is not None


def test_audit_actions_are_presented_and_their_ids_declared():
    from apps.audit.presentation_catalog import PRESENTATION_CATALOG
    from apps.tenant_migration.audit_references_meta_r2 import lane_edges
    actions = ("event.peoples_choice.updated", "event.peoples_choice.ballot_cast",
               "event.peoples_choice.vote_voided", "event.peoples_choice.published")
    keys = {getattr(entry, "action", None) for entry in PRESENTATION_CATALOG} if not isinstance(
        PRESENTATION_CATALOG, dict) else set(PRESENTATION_CATALOG)
    assert set(actions) <= keys
    edges = lane_edges()
    assert ("event.peoples_choice.vote_voided", "vote_id") in edges
    assert ("event.prize.payout_recorded", "peoples_choice_standing_id") in edges


def test_purge_order_precedes_snapshots_and_follows_payouts():
    from apps.makerspaces.purge_events_programme_catalog import PURGE_ORDER
    labels = [label for label, _path in PURGE_ORDER]
    assert labels.index("events.HackathonPrizePayout") < labels.index("events.PeoplesChoiceStanding")
    assert labels.index("events.PeoplesChoiceStanding") < labels.index("events.PeoplesChoiceResult")
    if "events.SubmissionSnapshot" in labels:
        assert labels.index("events.PeoplesChoiceStanding") < labels.index("events.SubmissionSnapshot")


@pytest.mark.django_db
def test_the_voting_open_email_is_off_by_default_and_follows_the_switch(settings, monkeypatch):
    from apps.events.judging.models_results import JudgingNotice
    from tests.peoples_choice_local.helpers import configure, gallery_world
    world = gallery_world(settings, monkeypatch)
    configure(world)
    assert not JudgingNotice.objects.filter(event=world.event, kind="peoples_choice_open").exists()
    from apps.events.judging import peoples_choice
    from tests.events.pairwise_helpers import command
    from apps.events.judging.models_peoples_choice import PeoplesChoiceConfig
    row = PeoplesChoiceConfig.objects.get(event=world.event)
    peoples_choice.update(world.event.pk, actor=world.manager, data=command(row.version, enabled=False))
    peoples_choice.update(world.event.pk, actor=world.manager, data=command(row.version + 1, enabled=True, open_email=True))
    assert JudgingNotice.objects.filter(event=world.event, kind="peoples_choice_open").count() == 1
