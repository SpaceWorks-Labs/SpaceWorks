"""Focused guards for owner decisions that had no behaviour test of their own (DEC-BE lane, round 2).

Each test names the decision it proves. Local and gitignored like every other test (#108).
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace

import pytest

from apps.events.submissions import retention, workflow
from apps.events.submissions.errors import SubmissionError


# 1: hackathons are an opt-in capability inside Events, off by default.
def test_hackathons_is_an_events_capability_off_by_default():
    from apps.makerspaces.capabilities import FEATURES

    hackathons = FEATURES["events.hackathons"]
    assert hackathons.parent_module == "events"
    assert hackathons.default_enabled is False
    for child in ("events.project_gallery", "events.pairwise_judging"):
        assert "events.hackathons" in FEATURES[child].requires_features


# 2 (+5): auto / rolling / batch admission, RSVP deadline default 4 days, N reviewers, optional blind mode.
def test_admission_modes_and_rsvp_default():
    from apps.events.hackathons.admission_models import HackathonConfig

    mode = HackathonConfig._meta.get_field("review_mode")
    assert {value for value, _label in mode.choices} == {"auto", "rolling", "batch"}
    assert HackathonConfig._meta.get_field("rsvp_days").default == 4
    assert HackathonConfig._meta.get_field("review_count").default >= 1
    assert HackathonConfig._meta.get_field("blind_review").default is False


# 8: the AI-use declaration (and the reuse declaration) are required on the final submission.
@pytest.mark.parametrize("ai, reuse", [({}, {"used": False}), ({"used": False}, {})])
def test_final_submission_requires_ai_and_reuse_declarations(monkeypatch, ai, reuse):
    monkeypatch.setattr(workflow, "_canonical_project", lambda *a, **k: {})
    monkeypatch.setattr(workflow, "validate_project_patch", lambda document: None)
    project = SimpleNamespace(public_asset_ids=[], asset_ids=[], title="Robot arm",
                              ai_declaration=ai, reuse_declaration=reuse)
    with pytest.raises(SubmissionError) as caught:
        workflow._snapshot(None, project, None, None, None, False, "", stage=None, extension=None)
    assert caught.value.code == "project_incomplete"


def test_declared_submission_passes_the_declaration_gate(monkeypatch):
    monkeypatch.setattr(workflow, "_canonical_project", lambda *a, **k: {})
    monkeypatch.setattr(workflow, "validate_project_patch", lambda document: None)

    class Reached(Exception):
        pass

    def assets():
        raise Reached()

    project = SimpleNamespace(public_asset_ids=[], asset_ids=[], title="Robot arm",
                              ai_declaration={"used": True, "details": "Copilot"},
                              reuse_declaration={"used": False, "details": ""},
                              assets=SimpleNamespace(select_for_update=assets))
    with pytest.raises(Reached):
        workflow._snapshot(None, project, None, None, None, False, "", stage=None, extension=None)


class _Rows:
    def __init__(self, sink):
        self.objects = self
        self.sink = sink

    def filter(self, **kwargs):
        return self

    def update(self, **kwargs):
        self.sink.append(kwargs["expires_at"])


def _usage():
    saved = []
    return SimpleNamespace(first_results_published_at=None, retention_anchor=None, retention_anchor_kind=None,
                           expires_at=None, save=lambda update_fields: saved.append(update_fields))


# 20: submission files are deleted 365 days after results; records + hashes stay (the anchor only moves files).
def test_submission_files_expire_365_days_after_results(monkeypatch):
    sink = []
    monkeypatch.setattr(retention, "SubmissionAsset", _Rows(sink))
    monkeypatch.setattr(retention, "HackathonParticipantAsset", _Rows(sink))
    monkeypatch.setattr(retention, "record", lambda *a, **k: None)
    event, usage = SimpleNamespace(makerspace=None), _usage()
    results_at = datetime(2026, 11, 1, tzinfo=dt_timezone.utc)

    deadline = retention.anchor_locked(event=event, usage=usage, actor=None, kind="results", at=results_at)

    assert deadline == results_at + timedelta(days=365)
    assert usage.expires_at == deadline and sink == [deadline, deadline]
    # A later results amendment never extends the schedule.
    assert retention.anchor_locked(event=event, usage=usage, actor=None, kind="results",
                                   at=results_at + timedelta(days=30)) == deadline
    with pytest.raises(SubmissionError):
        retention.anchor_locked(event=event, usage=_usage(), actor=None, kind="whenever", at=results_at)


# 51c: delight effects and easter eggs are ON by default and each space may turn them off.
def test_delight_and_easter_eggs_are_on_by_default_and_switchable():
    from apps.makerspaces.capabilities import FEATURES

    for key in ("ui.delight", "ui.easter_eggs"):
        assert FEATURES[key].default_enabled is True
        assert FEATURES[key].parent_module is None  # a per-space switch, not tied to a module


# 75e: the PRD self-accept rule is dropped -- staff may accept their own request.
@pytest.mark.django_db
def test_staff_may_accept_their_own_request():
    from apps.hardware_requests.models import HardwareRequest
    from tests.test_request_workflow import (accept_url, authenticated_client, make_hardware_request,
                                             make_member, make_product, make_space)

    space = make_space("self-accept")
    product = make_product(space, total_quantity=3, available_quantity=3)
    manager = make_member("self-accept-manager", space)
    own = make_hardware_request(space, product, requester=manager, quantity=1)

    response = authenticated_client(manager).post(accept_url(own), format="json")

    assert response.status_code == 200, response.data
    own.refresh_from_db()
    assert own.status == HardwareRequest.Status.ACCEPTED


# 80(1): the leftover external check-in field is gone.
def test_external_checkin_user_id_is_gone():
    from apps.accounts.models import User

    assert "external_checkin_user_id" not in {field.name for field in User._meta.get_fields()}


# 89a: on a full server an unreadable deployment binding proceeds; a positive managed binding refuses.
@pytest.mark.django_db
def test_full_server_proceeds_when_the_mode_binding_cannot_be_read(monkeypatch):
    from apps.backup.managed import admission, mode_binding, profile

    monkeypatch.setattr(profile, "deployment_profile", lambda environ=None: SimpleNamespace(mode="host"))
    monkeypatch.setattr(admission, "_managed_environment", lambda: False)

    def unreadable(cursor, mode):
        raise RuntimeError("binding table unreadable")

    monkeypatch.setattr(mode_binding, "assert_mode_binding", unreadable)
    assert admission.refuse_host_operation("deployment_backup_requires_host_supervisor") is None

    def managed(cursor, mode):
        raise admission.ManagedAdmissionError("managed binding")

    monkeypatch.setattr(mode_binding, "assert_mode_binding", managed)
    with pytest.raises(admission.ManagedAdmissionError):
        admission.refuse_host_operation("deployment_backup_requires_host_supervisor")


# 157: S0 defaults -- session 168 h, idle timeout off, IP auto-block on, WebAuthn RP name.
def test_s0_security_defaults():
    from django.conf import settings
    from apps.accounts import login_security_settings as security

    assert security.STAFF_SESSION_MAX_HOURS.key == "security.staff_session_max_hours"
    assert security.STAFF_SESSION_MAX_HOURS.default == 168
    assert security.STAFF_IDLE_TIMEOUT_MINUTES.default == 0
    assert settings.LOGIN_IP_BLOCK_ENABLED is True
    assert settings.WEBAUTHN_RP_NAME == "Space Works"


# 174: walk-in claim sessions are refused on the machine-job upload and submit routes (#140).
@pytest.mark.parametrize("route", ["public-machine-job-upload", "public-machine-job-submit"])
def test_walk_in_claim_sessions_cannot_submit_machine_jobs(route):
    from apps.accounts.claim_route_types import Refused
    from apps.accounts.claim_routes import policy_for

    policy = policy_for(route, "POST")
    assert isinstance(policy, Refused)
    assert "machine jobs" in repr(policy)


# 169: booking (and event) confirmation emails attach an .ics invite -- PUBLISH with a stable UID and
# sequence, CANCEL on cancellation -- and the body gains Google / Outlook add links.
def test_confirmation_emails_attach_an_ics_invite(monkeypatch):
    from apps.bookings import confirmation_invites as invites

    start = datetime(2026, 12, 1, 10, tzinfo=dt_timezone.utc)
    booking = SimpleNamespace(space=SimpleNamespace(name="Laser room", location="Bay 2"), public_token="tok123",
                              starts_at=start, ends_at=start + timedelta(hours=2), calendar_sequence=3,
                              calendar_updated_at=start - timedelta(days=1), status="confirmed")
    monkeypatch.setattr(invites, "_booking", lambda envelope: booking)

    (invite,) = invites.attachments(SimpleNamespace(audience="requester", event="confirmed"))
    body = invite.content.decode()
    assert invite.filename == "booking.ics" and invite.mimetype.endswith("method=PUBLISH")
    assert "METHOD:PUBLISH" in body and "UID:booking-tok123@spaceworks" in body and "SEQUENCE:3" in body
    assert "STATUS:CONFIRMED" in body

    (cancel,) = invites.attachments(SimpleNamespace(audience="requester", event="cancelled"))
    assert "METHOD:CANCEL" in cancel.content.decode() and "STATUS:CANCELLED" in cancel.content.decode()
    assert invites.attachments(SimpleNamespace(audience="staff", event="confirmed")) == ()

    rendered = invites.with_links({"text": "Booked."}, booking, "confirmed")
    assert "Add to Google Calendar:" in rendered["text"] and "Add to Outlook:" in rendered["text"]
