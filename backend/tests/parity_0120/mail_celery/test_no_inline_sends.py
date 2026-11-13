"""Guard: outbound messages leave the request cycle. New inline provider sends or synchronous fan-out must not creep back."""
import re
from pathlib import Path

APPS = Path(__file__).resolve().parents[3] / "apps"

# Dispatcher / transport modules (they run inside the Celery worker) and the explicit operator test-send actions.
DIRECT_SEND_ALLOWED = (
    "integrations/dispatch_", "integrations/mail_providers/", "integrations/email.py",
    "integrations/sms/", "integrations/platform_credential_checks.py", "integrations/messaging/",
    "integrations/telegram", "integrations/webhooks.py", "integrations/push", "integrations/notification_",
    "integrations/transient_mail.py", "integrations/tasks_transient.py", "integrations/smtp_validation.py",
    "integrations/delivery_tests.py", "integrations/views.py",  # operator "send a test now"
    "admin_api/views_space_email_test.py",
    "card_designs/wallet/", "maintenance/repairs/channels.py",  # runs from dispatch.send_planned in the worker
    "audit/anchors_", "accounts/attestation_", "accounts/apple_credentials.py",
)
DIRECT_SEND = re.compile(
    r"\bsend_mail\(|\bsend_mass_mail\(|\bEmailMessage\(|\bEmailMultiAlternatives\(|\bsmtplib\.|"
    r"\bsend_sms_now\(|\bsend_signed_webhook\(|\bsend_webhook\(")

# Modules that call emit()/notify_lifecycle()/dispatch_channel() without a deferral decorator. Every entry must
# say WHY it never runs in a web request. Convert and REMOVE entries; adding one needs a concrete technical reason.
_WORKER = "executes only inside a Celery task / batch worker, never from a request: "
FANOUT_RATCHET = {
    "bookings/broadcasts_personal.py": _WORKER + "per-recipient callback of the booking broadcast batch worker",
    "events/broadcast_channels.py": _WORKER + "reserve_personal callback of the events broadcast batch worker",
    "bookings/reminder_envelopes.py": _WORKER + "called by dispatch_booking_reminder from the reminder sweeper",
    "events/reminders.py": _WORKER + "dispatch_event_reminder is a reminder-sweeper dispatch hook",
    "events/staged_forms/rsvp_reminders.py": _WORKER + "dispatch hook of the reminder sweeper",
    "operations/reminder_members.py": _WORKER + "dispatch_member_reminder is a reminder-sweeper hook",
    "events/approval_digest.py": _WORKER + "send_approval_digests_task is itself a Celery beat task",
    "events/registration_invites.py": _WORKER + "update_envelope is called by events/tasks_invites.py (Celery)",
    "presence/notifications.py": _WORKER + "remind() is called by presence/tasks.py (Celery)",
    "events/contributions/runtime_notices.py": _WORKER + "persisted-intent processor driven by the contributor/"
                                                        "mentor notice sweepers (manifest: *_sweep) with claim+attempts",
    "events/contracts/admission_registration.py": "only registers the notice adapters above (install/register); no send",
    "events/judging/provider_notices.py": _WORKER + "deliver(notice_id) is run by the judging provider notice runtime",
    "events/linked_change_recipients.py": "helper called only from safe_adapter-decorated adapters "
                                           "(events/linked_change_notices.py), so it already runs in the worker job",
    "hardware_requests/notifications_p2_rooms.py": "queue_rooms is called only by notifications_p2.fanout, which is "
                                                    "reached only from safe_adapter-decorated adapters",
    "integrations/dispatch_channels.py": "the dispatcher itself: creates the log row and enqueues deliver_notification_task",
    "integrations/notification_outbox.py": "the outbox: emit() writes the envelope row; delivery is deliver_envelope",
    "integrations/notification_digest.py": _WORKER + "collect_digest is called by deliver_envelope",
    "integrations/notification_legacy.py": "the legacy shell recover/dispatch; invoked by deliver_envelope / fanout jobs",
    "integrations/notify.py": "notify_lifecycle runs inside a fan-out job; inline only under eager/free/in-worker",
    "integrations/notification_diagnostics.py": "operator 'send a test notification now' (explicit test-send, "
                                                 "returns the delivery row to the admin who asked)",
    "integrations/invite_chat.py": "returns whether a chat DM went out, which organizations/invitation_delivery "
                                    "uses to decide the email fallback in the same request, and takes the invitee "
                                    "address (personal data must not enter a job row)",
}
FANOUT_CALL = re.compile(r"\bnotify_lifecycle\(|\bemit\(|\bfanout\(|\bdispatch_channel\(")
DEFERRAL = re.compile(r"safe_adapter|safe_notification|deferred_fanout|maybe_defer")


def _sources():
    for path in APPS.rglob("*.py"):
        rel = path.relative_to(APPS).as_posix()
        if "/migrations/" in rel or "/tests/" in rel or "/management/" in rel:
            continue
        yield rel, path.read_text(encoding="utf-8", errors="ignore")


def test_no_direct_provider_send_outside_the_dispatchers():
    offenders = [rel for rel, text in _sources()
                 if DIRECT_SEND.search(text) and not rel.startswith(DIRECT_SEND_ALLOWED)]
    assert not offenders, f"Inline message sends outside the Celery dispatcher allow-list: {offenders}"


def test_new_modules_cannot_fan_out_synchronously():
    offenders = sorted(rel for rel, text in _sources()
                       if FANOUT_CALL.search(text) and not DEFERRAL.search(text) and rel not in FANOUT_RATCHET)
    assert not offenders, ("Notification fan-out must go through a deferred adapter (safe_adapter, "
                           f"safe_notification, deferred_fanout) so a worker runs it: {offenders}")


def test_ratchet_has_no_stale_entries():
    present = {rel for rel, text in _sources() if FANOUT_CALL.search(text) and not DEFERRAL.search(text)}
    stale = sorted(set(FANOUT_RATCHET) - present)
    assert not stale, f"Remove converted modules from FANOUT_RATCHET: {stale}"


def test_every_ratchet_entry_states_a_concrete_reason():
    assert all(len(reason) > 40 for reason in FANOUT_RATCHET.values())


def test_notify_family_has_no_production_caller():
    """Kept (tests exercise it and assert its return value); deferral would change that contract."""
    callers = [rel for rel, text in _sources()
               if "notify_family(" in text and rel != "integrations/notifications_research.py"]
    assert callers == []


def test_secret_bearing_mail_is_queued_not_sent_inline():
    text = (APPS / "integrations/dispatch_outbox.py").read_text(encoding="utf-8")
    assert "queue_email(" in text, "dispatch_email must hand persist_body=False mail to the worker (transient_mail)"
