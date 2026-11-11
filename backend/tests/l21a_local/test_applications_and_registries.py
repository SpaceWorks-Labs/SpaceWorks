"""L21a: applications on any event (on/off), webhook payloads, applications:read and route decisions."""
import pytest
from rest_framework.exceptions import APIException

from apps.accounts.programme_route_catalog import BY_NAME, NATIVE_DECISIONS, NATIVE_WEB_ONLY
from apps.events.hackathons import admission_feature, admission_transactions, admission_webhooks
from apps.events.hackathons.admission_models import HackathonApplication, HackathonConfig
from apps.events.models import EventRegistration
from apps.makerspaces.capabilities import FEATURES
from tests.events.ticketing_helpers import account, event_space, open_event

pytestmark = pytest.mark.django_db
KEYS = ("events.applications", "events.application_stages", "events.attendance_confirmation", "events.crew",
        "events.crew_claims", "events.checkin_lists")


def test_capability_keys_are_under_events_and_off_by_default():
    for key in KEYS:
        assert FEATURES[key].parent_module == "events" and FEATURES[key].default_enabled is False
    assert FEATURES["events.application_stages"].requires_features == ("events.applications",)
    assert FEATURES["events.crew_claims"].requires_features == ("events.crew",)
    assert FEATURES["events.crew_claims"].requires_modules == ("event_reimbursements",)


def _space(features):
    space = event_space("apps-any")
    space.enabled_features = sorted(set(space.enabled_features) | set(features))
    space.save(update_fields=["enabled_features"])
    return space


@pytest.mark.parametrize("features, opens", [((), False), (("events.applications",), True),
                                             (("events.hackathons",), True)])
def test_applications_open_the_admission_engine_on_any_event(features, opens):
    space = _space(features)
    event = open_event(space)
    HackathonConfig.objects.create(event=event, enabled=True)
    if opens:
        assert admission_transactions.require_programme(event).event_id == event.pk
    else:
        with pytest.raises(APIException) as exc:
            admission_transactions.require_programme(event)
        assert exc.value.status_code == 404
    assert admission_feature.applications_only(space) is (features == ("events.applications",))


def test_application_webhook_carries_ids_and_stage_only(monkeypatch):
    space = _space(("events.applications",))
    event = open_event(space)
    member = account("hook-member")
    registration = EventRegistration.objects.create(event=event, member=member, name="Secret Name",
                                                    email=member.email, phone="1", status="pending_approval")
    app = HackathonApplication.objects.create(event=event, member=member, registration=registration, state="offered",
                                              answers_snapshot='{"answers": [{"value": "private"}]}')
    seen = {}

    def capture(makerspace, *, feature, event, build, **kwargs):
        seen.update(feature=feature, event=event, payload=build())
    monkeypatch.setattr("apps.integrations.notify.notify_lifecycle", capture)
    admission_webhooks.application_changed(event, app, "application_offered")
    payload = seen["payload"]
    assert seen["event"] == "application_offered" and seen["feature"] == "events"
    assert set(payload.data) == {"event_id", "application_id", "registration_id", "stage_id", "stage_position"}
    assert "Secret" not in payload.text and "private" not in payload.text


def test_webhook_schema_and_lifecycle_ids_admit_application_and_stage():
    from apps.integrations.lifecycle_data import lifecycle_data
    from apps.integrations.webhook_schema import FAMILY_IDS, schema_catalog
    assert {"application_id", "stage_id", "stage_position"} <= set(FAMILY_IDS["events"])
    assert lifecycle_data({"application_id": 3, "stage_id": 4, "answers": "x"}) == {"application_id": 3, "stage_id": 4}
    assert "events.application_stage_advanced" in schema_catalog()["$defs"]


def test_applications_read_scope_is_registered_for_counts_only():
    from apps.apiclients.scope_registry_reads import APPLICATION_READ, read_route_entries, read_scope_vocabulary
    assert APPLICATION_READ in read_scope_vocabulary()
    entry = read_route_entries()[("integration-application-counts", "GET")]
    assert entry.scopes == frozenset({APPLICATION_READ}) and entry.server_only and entry.tenant_bound


def test_every_l21a_route_has_an_explicit_native_decision():
    from apps.accounts.programme_route_catalog_l21a import L21A_ROUTES
    names = {name for name, methods, target in L21A_ROUTES}
    assert names <= set(BY_NAME) and set(NATIVE_DECISIONS) == names
    assert {"events-programme-admin-crew", "events-programme-admin-application-stage-my-reviews"} <= NATIVE_WEB_ONLY
    assert "events-programme-member-attendance" not in NATIVE_WEB_ONLY


def test_crew_desk_is_web_only_for_native_selection():
    from apps.makerspaces.origin_scope_programme import programme_route_targets
    space = _space(("events.crew",))
    event = open_event(space)
    assert programme_route_targets("events-programme-admin-crew", {"pk": event.pk})[3] is False
    assert programme_route_targets("events-programme-admin-checkin-lists", {"pk": event.pk})[3] is True
