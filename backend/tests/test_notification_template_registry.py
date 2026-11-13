"""Registry sample and coverage checks, split from template-editing tests."""

import pytest

from apps.integrations.email_templates_registry import (
    STREAMS, get_entry, iter_entries, validate_email_template_strings,
)
from apps.integrations.email_templates_registry_fablab import FABLAB_STREAM_KEYS, STREAM_FOR_FEATURE
from apps.integrations.models import EmailTemplate
from apps.integrations.notification_catalog import FEATURE_EVENTS

pytestmark = pytest.mark.django_db


FABLAB_ENTRIES = [
    (stream, audience, key)
    for stream, keys in FABLAB_STREAM_KEYS.items()
    for key in keys
    for audience in ("staff", "requester")
]


# --- D6: both audiences, including event approval outcomes and reminders ---------


def test_the_registry_covers_thirty_events_in_both_audiences():
    assert sum(len(keys) for keys in FABLAB_STREAM_KEYS.values()) == 32
    assert len(FABLAB_ENTRIES) == 64
    # Events programme notices are personal-only and carry their own renderers.
    # Stale since L16/GAP2/L2/L6/L21/L22 (R3 AG1): later events carry their own renderers and are
    # classified per event as personal-only or chat-only staff notices instead of fablab email keys.
    from apps.integrations.chat_templates_catalog import EVENTS as CHAT_ONLY, PERSONAL_ONLY_EVENTS
    from apps.integrations.notification_catalog_events_programme import PROGRAMME_EVENTS
    assert {("events", event) for event in PROGRAMME_EVENTS} <= PERSONAL_ONLY_EVENTS
    for feature in ("events", "bookings"):
        own_renderer = {event for (f, event) in PERSONAL_ONLY_EVENTS | set(CHAT_ONLY) if f == feature}
        assert set(FABLAB_STREAM_KEYS[feature]) == set(FEATURE_EVENTS[feature]) - own_renderer, feature
        assert not set(FABLAB_STREAM_KEYS[feature]) & own_renderer, feature
    for coordinates in FABLAB_ENTRIES:
        assert get_entry(*coordinates) is not None, coordinates


@pytest.mark.parametrize("stream,audience,key", FABLAB_ENTRIES)
def test_every_entry_renders_against_its_own_sample_context(stream, audience, key):
    entry = get_entry(stream, audience, key)
    validate_email_template_strings(
        stream, audience, key, entry.default_subject, entry.default_text, entry.default_html
    )


def test_every_registry_entry_anywhere_still_renders():
    """The whole registry, not just the new half — the defaults are the fallback path."""
    for (stream, audience, key), entry in iter_entries():
        validate_email_template_strings(
            stream,
            audience,
            key,
            entry.default_subject,
            entry.default_text,
            entry.default_html,
        )


def test_defaults_are_not_blank():
    for coordinates in FABLAB_ENTRIES:
        entry = get_entry(*coordinates)
        assert entry.default_subject.strip(), coordinates
        assert entry.default_text.strip(), coordinates
        assert entry.fields, coordinates


def test_new_streams_are_selectable_on_the_model_and_in_the_registry():
    model_streams = {value for value, _ in EmailTemplate.Stream.choices}
    assert model_streams == STREAMS
    assert set(FABLAB_STREAM_KEYS) <= model_streams


def test_the_members_feature_maps_to_the_membership_stream():
    # The one pair where the feature key and the stream name differ. A render call that
    # assumed they were equal would raise KeyError at send time.
    assert STREAM_FOR_FEATURE["members"] == "membership"
    assert get_entry("membership", "staff", "member_joined") is not None



def test_every_notification_event_has_a_valid_staff_chat_template():
    from apps.integrations.chat_templates import chat_entry, validate_chat_template_string
    from apps.integrations.chat_templates_catalog import PERSONAL_ONLY_EVENTS

    for feature, events in FEATURE_EVENTS.items():
        for event in events:
            entry = chat_entry(feature, event)
            if (feature, event) in PERSONAL_ONLY_EVENTS:
                assert entry is None, (feature, event)
                continue
            assert entry is not None, (feature, event)
            validate_chat_template_string(feature, event, entry.default_text)


def test_personal_only_chat_exclusions_are_explicit_registered_events():
    from apps.integrations.chat_templates_catalog import PERSONAL_ONLY_EVENTS
    from apps.integrations.notification_catalog_events_programme import PROGRAMME_EVENTS

    assert PERSONAL_ONLY_EVENTS == {
        ("members", "broadcast"), ("members", "invitation"),
        ("api_access", "email.failed"), ("api_access", "scheduled_report"),
        ("payments", "document_issued"), ("presence", "expired"),
        ("printing", "next"),
        # L12: owner reminders and the waitlist offer.
        ("printing", "quote_reminder"), ("printing", "pickup_reminder"), ("hardware_requests", "waitlist_offer"),
        # The events programme's addressed notices have no staff room body.
        *(("events", event) for event in PROGRAMME_EVENTS),
        # Release 2 personal notices (R3 AG1, classified from each producer: one recipient, no staff leg).
        ("events", "invitation"), ("bookings", "invitation"),
        *(("events", event) for event in (
            "order_confirmed", "order_payment_reminder", "order_abandoned", "ticket_type_changed",
            "pass_occurrence_cancelled", "ticket_claim_invite", "ticket_transfer_received", "ticket_pay_link",
            "registration_updated", "application_stage_advanced", "attendance_confirmation",
            "attendance_reminder", "crew_invited", "crew_decided", "finalists_announced",
            "prize_payout_recorded", "prize_split_proposed", "prize_claim_verified", "prize_forfeited",
            "prize_recovery_opened", "peoples_choice_open", "stage_deadline_reminder", "stage_shortlisted",
            "stage_not_shortlisted", "stage_promoted", "judge_reminder")),
        ("payments", "donation_received"), ("payments", "pledge_due"),
        *(("payments", event) for event in (
            "shop_order_placed", "shop_order_paid", "shop_order_ready", "shop_order_lapsed",
            "shop_order_cancelled", "shop_order_reminder", "shop_order_receipt",
            "shop_order_pickup_moved_to_space", "shop_order_collected")),
        # Decision 216: the borrower's linked-event notice (no staff leg).
        ("hardware_requests", "linked_event_changed"),
        ("hardware_requests", "pickup_expiring"),
        ("hardware_requests", "repair_closed"), ("bookings", "repair_closed"), ("maintenance", "repair_closed"),
        # Interconnection 18: webhook-only link changes; 0.12.0 owner-only member notices.
        ("events", "event_booking_linked"), ("events", "event_loan_linked"), ("events", "event_loan_unlinked"),
        ("bookings", "booking_loan_linked"), ("bookings", "booking_loan_unlinked"),
        ("members", "guardian_consent_requested"), ("members", "profile_opened"), ("members", "changes_requested"), ("members", "resubmitted"),
        ("devices", "adapter_session_ending"),
        ("events", "pay_window_opened"), ("events", "pay_window_expired"),
    }
    assert PERSONAL_ONLY_EVENTS <= {
        (feature, event) for feature, events in FEATURE_EVENTS.items() for event in events
    }
