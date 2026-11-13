"""Notifications follow-up 0.12.0 (owner rule 261): the four items the audit left, plus the guard.

* every notice builder module (any module importing `emit`, `fanout` or `NotificationSource`) uses gettext;
* a notice is built in the RECIPIENT's language, not the sender's request language;
* a new guardian-terms version asks existing guardians again, once per version, gated on `membership.minors`;
* the guardian ask has a reviewed SMS/WhatsApp projection that still obeys consent; staff-only events have none.
"""
import ast
import pathlib
import re
from types import SimpleNamespace

import pytest
from django.utils import translation

from tests.return_helpers import make_space, make_user

APPS = pathlib.Path(__file__).resolve().parents[2] / "apps"
_COPY_KEYS = {"text", "title", "subject", "body", "summary"}
_BUILDER_IMPORT = re.compile(r"import[^\n]*\b(emit|fanout|NotificationSource)\b|notification_outbox import|notifications_p2 import")


def _bare(value):
    if isinstance(value, ast.JoinedStr):
        return sum(len(part.value.split()) for part in value.values if isinstance(part, ast.Constant)) >= 3
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return len(value.value.split()) >= 3
    return False


def _bare_copy(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        pairs = []
        if isinstance(node, ast.Dict):
            pairs = [(k.value, v) for k, v in zip(node.keys, node.values)
                     if isinstance(k, ast.Constant) and k.value in _COPY_KEYS]
        elif isinstance(node, ast.Call):
            pairs = [(kw.arg, kw.value) for kw in node.keywords if kw.arg in _COPY_KEYS]
        found += [f"{path.relative_to(APPS)}:{v.lineno} {k}" for k, v in pairs if _bare(v)]
    return found


# --- 1. translation guard over EVERY builder module ---------------------------------------------

def test_every_notice_builder_module_uses_gettext():
    """A bare English string in a subject/text/title/body of any module that builds a notice can never be translated."""
    bare = []
    for path in APPS.rglob("*.py"):
        if "migrations" in path.parts or "management" in path.parts:
            continue
        if _BUILDER_IMPORT.search(path.read_text(encoding="utf-8")):
            bare += _bare_copy(path)
    assert not bare, bare


EXPLICIT_BUILDERS = (
    "event_reimbursements/notices.py", "event_reimbursements/queue_notices.py", "events/submissions/stage_notices.py",
    "events/judging/provider_notices.py", "events/staged_forms/notices.py", "events/staged_forms/milestone_notices.py",
    "events/staged_forms/rsvp_reminders.py", "events/hackathons/team_notifications.py", "events/notices_r2_l2.py",
    "accounts/staff_role_notices.py", "shop/notices.py", "payments/event_payouts/notices.py",
    "apiclients/notifications_p2.py", "operations/report_schedule_services.py", "backup/space_restore_notifications.py",
    "card_designs/notifications.py", "encryption/key_notifications.py", "makerspaces/notifications_p2_subdomains.py",
)


@pytest.mark.parametrize("relative", EXPLICIT_BUILDERS)
def test_listed_builders_use_gettext(relative):
    assert not _bare_copy(APPS / relative)


def test_emit_time_builders_are_deferred_so_they_render_per_recipient():
    """The emit()-time bodies of the converted builders are callables, not pre-built dicts."""
    for relative, needle in (("event_reimbursements/queue_notices.py", "rendered=lambda"),
                             ("accounts/staff_role_notices.py", "rendered=lambda"),
                             ("shop/notices.py", "owner_body=lambda"),
                             ("apiclients/notifications_p2.py", "owner_body=lambda")):
        assert needle in (APPS / relative).read_text(encoding="utf-8"), relative


# --- 2. recipient-language rendering -----------------------------------------------------------

@pytest.fixture
def two_locales(monkeypatch):
    """A second registered locale (no catalogue needed: the active language itself is observable)."""
    import config.locale_resolution as resolution
    monkeypatch.setattr(resolution, "supported_codes", lambda: ("en", "de"))
    monkeypatch.setattr(resolution, "canonicalize", lambda code: code if code in ("en", "de") else None)


def _emit(space, user, rendered, key):
    from apps.integrations.notification_outbox import emit
    return emit(makerspace=space, recipient=user, feature="members", stream="membership", event="guardian_consent_requested",
                audience="requester", dedup_key=key, source_kind="members.guardian_consent", source_id="1",
                revision="1", rendered=rendered)


@pytest.mark.django_db
def test_emit_builds_the_notice_in_the_recipients_language(two_locales):
    import json
    space = make_space("fu-locale")
    german = make_user("fu-de")
    german.preferred_locale = "de"
    german.save(update_fields=["preferred_locale"])
    plain = make_user("fu-plain")
    with translation.override("en"):  # the sender's request language
        sent_de = _emit(space, german, lambda: {"subject": "s", "text": translation.get_language()}, "fu:de")
        sent_default = _emit(space, plain, lambda: {"subject": "s", "text": translation.get_language()}, "fu:plain")
    assert json.loads(sent_de.message_body)["text"] == "de"
    assert json.loads(sent_default.message_body)["text"] == "en"  # no preference: makerspace default, then system


@pytest.mark.django_db
def test_a_plain_dict_body_is_still_accepted():
    import json
    space = make_space("fu-dict")
    user = make_user("fu-dict-user")
    sent = _emit(space, user, {"subject": "s", "text": "plain"}, "fu:dict")
    assert json.loads(sent.message_body)["text"] == "plain"


@pytest.mark.django_db
def test_delivery_activates_the_recipients_locale(two_locales):
    from apps.integrations.models_contract import NotificationDelivery
    from apps.integrations.notification_locale import recipient_locale
    space = make_space("fu-delivery")
    german = make_user("fu-de2")
    german.preferred_locale = "de"
    german.save(update_fields=["preferred_locale"])
    envelope = _emit(space, german, {"subject": "s", "text": "t"}, "fu:delivery")
    leg = NotificationDelivery.objects.create(envelope=envelope, makerspace=space, channel="in_app", target_key="x",
                                              provider="builtin", state="retrying")
    with translation.override("en"):
        with recipient_locale(leg.pk, space.pk):
            assert translation.get_language() == "de"
        assert translation.get_language() == "en"  # restored for the next delivery


def test_delivery_send_runs_inside_the_recipient_locale():
    source = (APPS / "integrations" / "notification_delivery.py").read_text(encoding="utf-8")
    assert "recipient_locale(delivery_id, tenant_id)" in source
    assert 'def recipient_locale' in (APPS / "integrations" / "notification_locale.py").read_text(encoding="utf-8")


def test_fanouts_accept_builders():
    from apps.hardware_requests.notifications_p2 import _annotated, _plain
    assert _annotated(None, None, lambda *_: None) is None
    built = _annotated(lambda: {"subject": "a"}, {"title": "x"}, lambda body, event: {**body, "event": event["title"]})
    assert built() == {"subject": "a", "event": "x"}
    assert _plain({"text": "t"}, None) == {"text": "t"}


# --- 3. guardian terms bump re-asks existing guardians, once per version -----------------------

def test_guardian_revision_carries_the_terms_version(monkeypatch):
    from apps.makerspaces import minors, notifications_guardian as guardian
    profile = SimpleNamespace(pk=7, updated_at="t0", guardian_user_id=9, makerspace=object())
    monkeypatch.setattr(minors, "active_terms", lambda space: SimpleNamespace(version="v1"))
    first, again = guardian._version(profile), guardian._version(profile)
    monkeypatch.setattr(minors, "active_terms", lambda space: SimpleNamespace(version="v2"))
    assert first == again                      # the same version is the same dedup identity: asked once
    assert guardian._version(profile) != first  # a new version is a fresh ask


@pytest.mark.django_db
def test_terms_bump_asks_only_named_guardians_and_only_when_minors_is_on(monkeypatch):
    from apps.makerspaces import notifications_guardian as guardian
    from apps.makerspaces.models import MinorProfile
    space = make_space("fu-terms")
    asked = []
    monkeypatch.setattr(guardian, "notify_requested", lambda profile: asked.append(profile.pk) or object())
    assert guardian.notify_terms_changed(space) == 0 and asked == []  # `membership.minors` is off by default
    monkeypatch.setattr("apps.makerspaces.platform.feature_enabled", lambda makerspace, key: key == "membership.minors")
    kid, guardian_user = make_user("fu-kid"), make_user("fu-guardian")
    named = MinorProfile.objects.create(makerspace=space, user=kid, declared_under_age=True, guardian_user=guardian_user)
    MinorProfile.objects.create(makerspace=space, user=make_user("fu-kid2"), declared_under_age=True)  # no account
    MinorProfile.objects.create(makerspace=space, user=make_user("fu-kid3"), declared_under_age=True,
                                guardian_user=guardian_user, cleared_at=named.created_at)  # cleared
    assert guardian.notify_terms_changed(space) == 1
    assert asked == [named.pk]


def test_publishing_terms_triggers_the_ask_after_the_commit():
    source = (APPS / "makerspaces" / "minors.py").read_text(encoding="utf-8")
    publish = source.split("def publish_terms(")[1].split("def sign_consent(")[0]
    assert "notify_terms_changed(makerspace)" in publish
    assert publish.index("except IntegrityError") < publish.index("notify_terms_changed(makerspace)")


# --- 4. addressed SMS / WhatsApp projections ---------------------------------------------------

def test_guardian_ask_has_a_scalar_only_sms_projection():
    from apps.integrations.messaging.projections import PROJECTION_KEYS, render_sms
    key = ("members", "guardian_consent_requested", "member")
    assert PROJECTION_KEYS[key] == ("makerspace.name",)
    text = render_sms(*key, {"makerspace.name": "Fab Lab"})
    assert "Fab Lab" in text and "guardian" in text.lower()
    with pytest.raises(Exception):
        render_sms(*key, {"makerspace.name": "Fab Lab", "minor.name": "Kid"})  # a minor's detail is never admitted


def test_staff_only_new_events_have_no_addressed_projection():
    from apps.integrations.messaging.projections import PROJECTION_KEYS
    for key in (("bookings", "hours_bank_low", "staff"), ("bookings", "hours_bank_low", "member"),
                ("events", "attendance_replied", "staff"), ("events", "attendance_replied", "member")):
        assert key not in PROJECTION_KEYS, key


@pytest.mark.django_db
def test_guardian_sms_is_refused_without_consent():
    from apps.integrations.notification_addressed import eligible
    space = make_space("fu-sms")
    guardian_user = make_user("fu-sms-guardian")
    envelope = _emit(space, guardian_user, {"subject": "s", "text": "t"}, "fu:sms")
    assert eligible(envelope, "sms") is False        # no consent, no sender, nothing configured
    assert eligible(envelope, "whatsapp") is False
