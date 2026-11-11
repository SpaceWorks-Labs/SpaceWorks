"""Notifications audit 0.12.0 (owner 2026-11-11, "all notification things too, make sure all done well").

One test per gap the audit fixed, plus a registry-coverage guard:

* decision 284: a space quota that stops something tells the Space Managers and superadmins, once a month;
* the platform-limit notice links to a real console tab;
* an organization's hours bank running low or empty tells the booking staff;
* a registrant's "No" to the attendance check tells the organisers (the catalogued `attendance_replied`);
* a guest-pass holder certified after an induction hears about it, like a member;
* a named guardian account is asked to sign the guardian consent;
* member-facing notice copy is translatable (no bare English f-strings in the audited builders);
* every catalogue event has a template route, a source, a family default and a preference category.
"""
import ast
import pathlib
from types import SimpleNamespace

import pytest

from tests.return_helpers import make_space

APPS = pathlib.Path(__file__).resolve().parents[2] / "apps"


def _enable(space, *modules):
    space.enabled_modules = sorted(set(space.enabled_modules or []) | set(modules))
    space.save(update_fields=["enabled_modules"])


# --- decision 284: quota notices ---------------------------------------------------------------

@pytest.mark.django_db
def test_a_quota_refusal_tells_superadmins_once_per_month():
    from apps.accounts.models import User
    from apps.managed_hosting.space_quotas import SpaceQuotaReached, check_space_quota, tell_managers
    from apps.notifications.models_inbox import NotificationInboxRow
    space = make_space("na-quota")
    _enable(space, "notifications")
    space.resource_limit_overrides = {"events_monthly": 0}
    space.save(update_fields=["resource_limit_overrides"])
    root = User.objects.create_user(username="na-root", password="Root password 77!", account_kind="platform",
                                    role=User.Role.SUPERADMIN, is_superuser=True, is_staff=True)
    with pytest.raises(SpaceQuotaReached) as caught:
        check_space_quota(space, "events_monthly")
    assert caught.value.key == "events_monthly" and caught.value.makerspace_id == space.pk
    tell_managers(caught.value)
    tell_managers(caught.value)  # a repeat the same month changes nothing
    rows = NotificationInboxRow.objects.filter(makerspace=space, event="platform_limit.reached", user=root)
    assert rows.count() == 1
    row = rows.get()
    assert row.title == "Monthly allowance reached" and "events created this month" in row.summary
    assert row.link == "/admin/platform-spaces"


@pytest.mark.django_db
def test_the_api_exception_handler_tells_managers_after_the_refusal():
    from apps.hardware_requests.exceptions import workflow_exception_handler
    from apps.managed_hosting.space_quotas import SpaceQuotaReached
    from apps.notifications.models_inbox import NotificationInboxRow
    space = make_space("na-quota-handler")
    _enable(space, "notifications")
    from apps.accounts.models import User
    User.objects.create_user(username="na-root2", password="Root password 77!", account_kind="platform",
                             role=User.Role.SUPERADMIN, is_superuser=True, is_staff=True)
    response = workflow_exception_handler(SpaceQuotaReached("bookings_monthly", 0, makerspace=space), {})
    assert response.status_code == 409 and response.data["code"] == "booking_quota_reached"
    assert NotificationInboxRow.objects.filter(makerspace=space, event="platform_limit.reached").exists()


@pytest.mark.django_db
def test_a_quota_with_no_limit_never_notifies():
    from apps.managed_hosting.space_quotas import check_space_quota
    from apps.notifications.models_inbox import NotificationInboxRow
    space = make_space("na-quota-none")
    check_space_quota(space, "events_monthly")  # unlimited by default: no raise, no notice
    assert not NotificationInboxRow.objects.filter(makerspace=space).exists()


def test_the_platform_limit_notice_links_to_real_console_tabs():
    from apps.managed_hosting import limit_notices
    root = SimpleNamespace(is_superuser=True, role="superadmin")
    staff = SimpleNamespace(is_superuser=False, role="requester")
    assert limit_notices._link_for(None, root) == "/admin/platform-spaces"
    assert limit_notices._link_for(None, staff) == limit_notices.USAGE_LINK == "/admin/usage"
    frontend = APPS.parents[1] / "frontend" / "src" / "features" / "staff"
    assert '"tab:usage"' in (frontend / "settingsSections.ts").read_text(encoding="utf-8")
    assert '"platform-spaces"' in (frontend / "staffTabs.ts").read_text(encoding="utf-8")


# --- hours bank --------------------------------------------------------------------------------

def test_hours_bank_levels():
    from apps.bookings.organization_hours_notice import level_for
    assert level_for(600, 0) is None
    assert level_for(600, 479) is None          # more than a fifth left
    assert level_for(600, 480) == "low"         # exactly a fifth left
    assert level_for(600, 599) == "low"
    assert level_for(600, 600) == "exhausted"
    assert level_for(600, 700) == "exhausted"   # overdrawn by a charged remainder
    assert level_for(0, 0) is None              # no pool, nothing to warn about


def test_hours_bank_notice_is_catalogued_sourced_and_chat_contracted():
    from apps.integrations.chat_templates_catalog import EVENTS
    from apps.integrations.notification_catalog import FEATURE_EVENTS
    from apps.integrations.notification_catalog_sources import event_source
    assert "hours_bank_low" in FEATURE_EVENTS["bookings"]
    assert ("bookings", "hours_bank_low") in EVENTS
    assert event_source("bookings", "hours_bank_low") == "bookings.organization_bookings"


def test_a_booking_that_takes_hours_raises_the_notice():
    source = (APPS / "bookings" / "organization_hours.py").read_text(encoding="utf-8")
    assert "alert_if_needed(" in source.split("def consume(")[1].split("def release(")[0]


# --- attendance reply --------------------------------------------------------------------------

def test_attendance_replied_has_a_producer_and_a_source():
    reply = (APPS / "events" / "attendance_confirmation.py").read_text(encoding="utf-8")
    assert "reply_notice(row)" in reply and "Answer.NO" in reply  # only "No" is actionable
    notices = (APPS / "events" / "notices_r2_l21a.py").read_text(encoding="utf-8")
    assert 'event="attendance_replied"' in notices and "REPLY_SOURCE" in notices
    assert "register_source(REPLY_SOURCE" in notices


@pytest.mark.django_db
def test_attendance_reply_notice_is_refused_when_the_reply_is_gone_or_not_a_no():
    from apps.events.notices_r2_l21a import reply_eligible
    space = make_space("na-attendance")
    envelope = SimpleNamespace(context={"reply_id": 0}, audience="staff", source_id="0", makerspace_id=space.pk)
    assert reply_eligible(envelope) is False


# --- guest-pass induction certificates ---------------------------------------------------------

def test_guest_certification_grants_and_revokes_notify_their_holder():
    induction = (APPS / "machines" / "induction.py").read_text(encoding="utf-8")
    assert 'notify_guest(grant, "granted")' in induction and 'notify_guest(grant, "revoked")' in induction


@pytest.mark.django_db
def test_guest_certification_source_refuses_a_missing_grant():
    from apps.machines.notifications_p2_certifications import eligible_guest
    space = make_space("na-guest-cert")
    envelope = SimpleNamespace(makerspace_id=space.pk, makerspace=space, source_id="0", recipient_id=1,
                               audience="requester", revision="x", event="granted")
    assert eligible_guest(envelope) is False


# --- minors: guardian consent ------------------------------------------------------------------

def test_no_guardian_account_means_no_notice():
    from apps.makerspaces.notifications_guardian import notify_requested
    profile = SimpleNamespace(guardian_user_id=None, cleared_at=None)
    assert notify_requested(profile) is None


def test_guardian_notice_is_catalogued_personal_only_and_gated_on_minors():
    from apps.integrations.chat_templates_catalog import PERSONAL_ONLY_EVENTS
    from apps.integrations.notification_catalog import FEATURE_EVENTS
    from apps.integrations.notification_catalog_sources import event_source
    assert "guardian_consent_requested" in FEATURE_EVENTS["members"]
    assert ("members", "guardian_consent_requested") in PERSONAL_ONLY_EVENTS
    assert event_source("members", "guardian_consent_requested") == "membership.minors"
    # Never names the minor.
    text = (APPS / "makerspaces" / "notifications_guardian.py").read_text(encoding="utf-8")
    assert "profile.user" not in text and "date_of_birth" not in text


@pytest.mark.django_db
def test_guardian_source_refuses_a_missing_profile():
    from apps.makerspaces.notifications_guardian import eligible
    space = make_space("na-guardian")
    envelope = SimpleNamespace(makerspace_id=space.pk, source_id="0", recipient_id=1, audience="requester",
                               revision="x")
    assert eligible(envelope) is False


# --- translation guard -------------------------------------------------------------------------

#: Builders converted to gettext by this audit. A bare English f-string in a subject/text/title/body here
#: is a regression: it can never be translated.
TRANSLATED_BUILDERS = (
    "bookings/member_notices.py", "bookings/organization_hours_notice.py", "events/notices_r2_l21a.py",
    "hardware_requests/notifications_loans.py", "hardware_requests/notifications_p2_requests.py",
    "hardware_requests/pickup_reminders.py", "machines/notifications_job_flow.py",
    "machines/notifications_sessions.py", "machines/notifications_p2_certifications.py",
    "makerspaces/member_dashboard_service.py", "makerspaces/notifications_guardian.py",
    "makerspaces/notifications_p2_members.py", "presence/notifications.py",
)
_COPY_KEYS = {"text", "title", "subject", "body", "summary"}


def _untranslated(value):
    if isinstance(value, ast.JoinedStr):
        return sum(len(part.value.split()) for part in value.values if isinstance(part, ast.Constant)) >= 3
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return len(value.value.split()) >= 3
    return False


@pytest.mark.parametrize("relative", TRANSLATED_BUILDERS)
def test_audited_notice_builders_use_gettext(relative):
    tree = ast.parse((APPS / relative).read_text(encoding="utf-8"))
    bare = []
    for node in ast.walk(tree):
        pairs = []
        if isinstance(node, ast.Dict):
            pairs = [(key.value, value) for key, value in zip(node.keys, node.values)
                     if isinstance(key, ast.Constant) and key.value in _COPY_KEYS]
        elif isinstance(node, ast.Call):
            pairs = [(kw.arg, kw.value) for kw in node.keywords if kw.arg in _COPY_KEYS]
        bare += [f"{relative}:{value.lineno} {key}" for key, value in pairs if _untranslated(value)]
    assert not bare, bare


# --- registry coverage guard -------------------------------------------------------------------

def test_every_catalogue_event_has_a_template_route_a_source_a_default_and_a_preference_category():
    from apps.integrations import chat_templates_catalog as chat
    from apps.integrations.email_templates_registry import iter_entries
    from apps.integrations.notification_catalog import DEFAULT_CHANNEL_STATE, FEATURE_EVENTS
    from apps.integrations.notification_catalog_sources import event_source
    from apps.integrations.recipients_selection import FEATURE_MODULES
    from apps.notifications.preferences import PERSONAL_CHANNELS
    from apps.makerspaces.capabilities import FEATURES
    from apps.makerspaces.module_registry import MODULE_KEYS
    registry_names = {key for (_stream, _audience, key), _entry in iter_entries()}
    chat_names = {event for (_feature, event) in chat.EVENTS} | {event for (_f, event) in chat.PERSONAL_ONLY_EVENTS}
    from apps.integrations import link_webhooks
    link_names = set(getattr(link_webhooks, "LINK_EVENTS", ()) or ())
    missing, no_default, bad_source = [], [], []
    for feature, events in FEATURE_EVENTS.items():
        defaults = DEFAULT_CHANNEL_STATE.get(feature)
        if defaults is None or any(channel not in defaults for channel in PERSONAL_CHANNELS):
            no_default.append(feature)  # the preference matrix needs every personal channel per family
        for event in events:
            if event not in registry_names | chat_names | link_names:
                missing.append((feature, event))
            for source in (event_source(feature, event) or "").split("|"):
                if source and source not in (FEATURES if "." in source else MODULE_KEYS):
                    bad_source.append((feature, event, source))
        assert feature in FEATURE_MODULES or feature in {"api_access", "presence"}, feature
    assert not no_default, no_default
    assert not bad_source, bad_source
    # Link-change events are webhook-only and listed by `link_webhooks`; everything else must have copy.
    allowed_webhook_only = {"event_booking_linked", "event_loan_linked", "event_loan_unlinked",
                            "booking_loan_linked", "booking_loan_unlinked"}
    assert not [pair for pair in missing if pair[1] not in allowed_webhook_only], missing


def test_every_emit_call_site_with_a_literal_event_is_mapped_or_exempt():
    """The staff-alert (`emit_notification`) vocabulary stays sourced; a new alert must declare its module."""
    from apps.integrations.notification_catalog_sources import EMIT_EXEMPT, emit_source
    unmapped = []
    for path in APPS.rglob("*.py"):
        if "migrations" in path.parts or "management" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "emit_notification":
                event = next((kw.value for kw in node.keywords if kw.arg == "event"), None)
                if isinstance(event, ast.Constant) and event.value not in EMIT_EXEMPT and emit_source(event.value) is None:
                    unmapped.append(f"{path.name}: {event.value}")
    assert not unmapped, unmapped


# --- machine-service alert links ---------------------------------------------------------------

def test_machine_service_alert_link_opens_the_machines_tab():
    """The alert path is also the feed's machine-scope provenance key, so it stays; the console maps it."""
    tabs = (APPS.parents[1] / "frontend" / "src" / "features" / "staff" / "staffTabs.ts").read_text(encoding="utf-8")
    assert 'path === "machine-service"' in tabs
    from apps.notifications.legacy_feed_scope import _request_id
    assert _request_id("/admin/machine-service/requests/12") == 12
