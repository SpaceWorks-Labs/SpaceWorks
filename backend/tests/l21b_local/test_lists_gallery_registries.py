"""L21b staff lists and exports (X40), gallery search (X54), and the registries every new row joins."""
from types import SimpleNamespace

import pytest
from django.http import Http404
from rest_framework.exceptions import ValidationError

from apps.events.views_staff_lists import safe_cell
from tests.events.pairwise_helpers import command, pairwise_world


# ----- registries -----

def test_capabilities_live_under_events_with_their_requirements_and_defaults():
    from apps.makerspaces.capability_definitions import FEATURES
    keys = {"events.finalists", "events.prize_payouts", "events.entry_fees", "events.paid_teams",
            "events.saved_views", "events.gallery_search"}
    assert keys <= set(FEATURES)
    for key in keys:
        assert FEATURES[key].parent_module == "events"
        assert FEATURES[key].default_enabled is (key == "events.gallery_search")
    for key in ("events.finalists", "events.prize_payouts", "events.entry_fees", "events.paid_teams"):
        assert FEATURES[key].requires_features == ("events.hackathons",)
    assert FEATURES["events.gallery_search"].requires_features == ("events.project_gallery",)


def test_new_payment_subjects_join_every_registry():
    from apps.payments.availability import SUBJECT_DOMAINS
    from apps.payments.finance_scope import PAYMENT_DOMAINS
    from apps.payments.models import Payment
    from apps.payments.reconciliation_authority import SUBJECT_ACTIONS
    from apps.tenant_migration.references import PAYMENT_SUBJECT_REFERENCES
    for subject, model in (("submission_fee", "events.HackathonSubmission"), ("team_registration", "events.HackathonTeam")):
        assert subject in Payment.SubjectType.values and subject in Payment.EVENT_SUBJECT_TYPES
        assert SUBJECT_DOMAINS[subject] == PAYMENT_DOMAINS[subject] == "events"
        assert SUBJECT_ACTIONS[subject] == "manage_events"
        assert PAYMENT_SUBJECT_REFERENCES[subject] == model
    from apps.payments.models import RefundCase
    assert {"submission_disqualified", "team_rejected"} <= set(RefundCase.ReasonCode.values)


def test_user_edges_are_classified_for_account_merge():
    from apps.accounts.merge_registry import USER_REFERENCES
    for edge in (("events.FinalistAdvance", "created_by"), ("events.FinalistAnnouncement", "published_by"),
                 ("events.HackathonPrizePayout", "recipient"), ("events.HackathonPrizePayout", "recorded_by")):
        assert USER_REFERENCES[edge] == "keep_on_shell"


def test_new_models_are_in_the_programme_catalogues():
    from apps.tenant_migration.catalog_events_programme import FIELD_NAMES
    from apps.tenant_migration.catalog_events_programme_references import DATASETS
    from apps.makerspaces.purge_events_programme_catalog import PURGE_ORDER
    for label in ("events.JudgingPanelSeat", "events.FinalistAdvance", "events.JudgingFinalist",
                  "events.FinalistAnnouncement", "events.HackathonProgrammeOptions", "events.HackathonPrizePayout"):
        assert label in FIELD_NAMES and label in DATASETS and label in {row[0] for row in PURGE_ORDER}
    assert {"visibility", "fresh_eyes", "advanced_from"} <= FIELD_NAMES["events.JudgingRound"]
    assert "amount_per_winner" in FIELD_NAMES["events.HackathonPrize"]


def test_every_l21b_route_is_catalogued_and_mounted():
    from django.urls import reverse
    from apps.accounts.programme_route_catalog import BY_NAME
    from apps.accounts.programme_route_catalog_l21b import L21B_ROUTES
    for name, _methods, kind in L21B_ROUTES:
        assert BY_NAME[name][1] == kind == "event"
        kwargs = {"pk": 1}
        if "teams-" in name:
            kwargs |= {"makerspace_id": 1, "team_id": 1}
        if "round" in name:
            kwargs["round_id"] = 1
        if "payouts-reverse" in name:
            kwargs["payout_id"] = 1
        if "staff-list" in name:
            kwargs["list_key"] = "teams"
        assert reverse(name, kwargs=kwargs)


@pytest.mark.django_db
def test_money_fingerprint_keys_are_omitted_when_empty():
    from apps.tenant_migration.money_digest_r2_l21b import l21b_money_rows
    assert l21b_money_rows(10**9) == {}


# ----- staff lists -----

def test_csv_cells_neutralise_formulas():
    assert safe_cell("=SUM(A1)") == "'=SUM(A1)"
    assert safe_cell(" ​+1") == "' ​+1"
    assert safe_cell("@cmd") == "'@cmd" and safe_cell("-2") == "'-2"
    assert safe_cell("Plain") == "Plain" and safe_cell(None) == ""


@pytest.fixture
def listed(settings, monkeypatch):
    from tests.events.collab_helpers import client_for
    world = pairwise_world(settings, monkeypatch, projects=3, judges=3, enabled=False)
    world.space.enabled_features = sorted(set(world.space.enabled_features) | {"events.saved_views"})
    world.space.save(update_fields=["enabled_features"])
    world.client = client_for(world.manager)
    return world


@pytest.mark.django_db
def test_unknown_filters_are_refused_and_the_switch_hides_the_lists(listed):
    url = f"/api/v1/admin/events/{listed.event.pk}/lists/teams/"
    assert listed.client.get(url + "?state=forming").status_code == 200
    assert listed.client.get(url + "?owner=1").status_code == 400
    listed.space.enabled_features = [key for key in listed.space.enabled_features if key != "events.saved_views"]
    listed.space.save(update_fields=["enabled_features"])
    assert listed.client.get(url).status_code == 404
    assert listed.client.get(url + "export/").status_code == 404


@pytest.mark.django_db
def test_export_holds_exactly_the_filtered_rows(listed):
    from apps.events.submissions.models_projects import HackathonSubmission
    first = HackathonSubmission.objects.filter(event=listed.event).order_by("pk").first()
    HackathonSubmission.objects.filter(pk=first.pk).update(title="=cmd|' /C calc'!A0", triage="ineligible")
    url = f"/api/v1/admin/events/{listed.event.pk}/lists/submissions/"
    rows = listed.client.get(url + "?triage=ineligible").json()
    assert rows["count"] == 1 and rows["results"][0]["id"] == first.pk
    csv = listed.client.get(url + "export/?triage=ineligible").content.decode().splitlines()
    assert csv[0].startswith("id,") and len(csv) == 2 and ",'=cmd" in csv[1]
    from apps.audit.models import AuditLog
    assert AuditLog.objects.filter(action="event.export.csv").exists()


@pytest.mark.django_db
def test_a_saved_view_never_grants_access(listed):
    from tests.events.collab_helpers import client_for
    outsider = listed.judges[0]  # a judge: no manage_team permission on the list
    url = f"/api/v1/admin/events/{listed.event.pk}/lists/teams/"
    view = listed.client.post(f"/api/v1/admin/makerspaces/{listed.space.pk}/saved-views",
                              {"name": "Locked teams", "entity": "event_teams", "state": {"state": "locked"}, "shared": True},
                              format="json")
    assert view.status_code == 201
    assert client_for(outsider).get(url + "?state=locked").status_code in (403, 404)


@pytest.mark.django_db
def test_guest_pii_is_masked_and_its_export_refused_without_a_pii_window(listed):
    from django.contrib.auth import get_user_model
    from tests.events.collab_helpers import client_for
    root = get_user_model().objects.create_superuser("l21b-root", email="root@l21b.test", password="x" * 20)
    url = f"/api/v1/admin/events/{listed.event.pk}/lists/guests/"
    response = client_for(root).get(url)
    if response.status_code == 200:
        assert response.json().get("pii_masked") is True
    export = client_for(root).get(url + "export/")
    assert export.status_code == 403 and export.json()["code"] == "pii_access_required"


# ----- gallery -----

def _entries(world):
    from apps.events.submissions.gallery_models import GalleryEntry
    return GalleryEntry.objects.filter(event=world.event)


@pytest.mark.django_db
def test_gallery_search_is_404_when_switched_off_and_never_shows_winners_early(settings, monkeypatch):
    from apps.events.submissions import gallery_search
    world = pairwise_world(settings, monkeypatch, projects=2, judges=3, enabled=False)
    world.space.enabled_features = sorted(set(world.space.enabled_features) | {"events.project_gallery"})
    world.space.save(update_fields=["enabled_features"])
    with pytest.raises(Http404):
        gallery_search.query(world.event, _entries(world), {"q": "x"})
    rows, badges = gallery_search.query(world.event, _entries(world), {})
    assert badges == {}
    world.space.enabled_features += ["events.gallery_search"]
    world.space.save(update_fields=["enabled_features"])
    rows, badges = gallery_search.query(world.event, _entries(world), {"awards": "only", "sort": "awards"})
    assert badges == {} and list(rows) == []  # no published result: no winners, no badges
    with pytest.raises(ValidationError):
        gallery_search.query(world.event, _entries(world), {"sort": "loudest"})
    with pytest.raises(ValidationError):
        gallery_search.query(world.event, _entries(world), {"owner": "1"})


def test_awards_first_orders_winners_by_best_rank(monkeypatch):
    from apps.events.submissions import gallery_search
    rows = [SimpleNamespace(snapshot_id=pk) for pk in (1, 2, 3)]

    class Rows(list):
        def filter(self, **kwargs):
            return self

        def order_by(self, *args):
            return self

        def __or__(self, other):
            return self
    monkeypatch.setattr(gallery_search, "published_awards", lambda event: {3: [{"prize": "Gold", "rank": 1}],
                                                                           2: [{"prize": "Silver", "rank": 2}]})
    monkeypatch.setattr("apps.events.judging.feature.enabled", lambda *args: True)
    ordered, badges = gallery_search.query(SimpleNamespace(makerspace=object()), Rows(rows), {"sort": "awards"})
    assert [row.snapshot_id for row in ordered] == [3, 2, 1] and set(badges) == {2, 3}
