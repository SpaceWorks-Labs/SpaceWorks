"""L25: the curated views carry no secret, evidence or contact columns; PII exists only in
`members` and is masked by default (always on the platform); the catalogue is versioned and
documented; every domain is one registered module."""

import re
from pathlib import Path

import pytest

from apps.analytics.catalogue.registry import DOMAIN_MODULES, VIEWS_VERSION, all_views

# R3: 4dd35be4 (catalogue version 2) registered the pre-written L18/L21a/L21b/L22 views and deleted
# catalogue/pending_lanes*.py; the checks below read them from the registered modules instead.
from apps.analytics.catalogue import donations as _donations, shop as _shop


def _named(*names):
    return tuple(view for view in all_views() if view.name in names)


L18_DONATIONS = tuple(_donations.VIEWS)
L22_SHOP = tuple(_shop.VIEWS)
from apps.analytics.catalogue.render import PLATFORM, SPACE, render

FORBIDDEN = re.compile(
    r"password|secret|token|digest|verifier|pickup_code|claim|evidence|object_key|image_key|logo_key|"
    r"storage_location|box_id|qr_|camera|checkout_url|external_|stripe_|session_id|pricing_snapshot|"
    r"tax_snapshot|custom_answers|answers|requester_name|contact_|phone|guest_|donor_|note|description|"
    r"counterparty|reference|receipt|join_url|calendar_uid|public_token|search_vector|address|pan\b",
    re.IGNORECASE,
)
DOCS = Path(__file__).resolve().parents[3] / "docs" / "analytics-views.md"


ALLOWED = {("donations", "wants_tax_receipt"), ("members", "display_name"), ("members", "email"),
           # 0.12: the incident register links a guest pass by id; the column holds a number, no guest detail.
           ("incidents", "pass_id")}


@pytest.mark.parametrize("view", all_views(), ids=lambda view: view.name)
def test_no_view_reads_a_secret_evidence_or_contact_column(view):
    for column in view.columns:
        if (view.name, column.name) in ALLOWED:
            continue
        assert not FORBIDDEN.search(column.name), (view.name, column.name)
        assert not FORBIDDEN.search(column.expr), (view.name, column.name, column.expr)


def test_personal_data_lives_only_in_members_and_is_masked():
    pii = {(view.name, column.name) for view in all_views() for column in view.columns if column.pii}
    # Version 2 adds two masked person ids (shop buyer, prize recipient), never a name or contact.
    assert pii == {("members", "display_name"), ("members", "email"), ("shop_orders", "member_id"),
                   ("prize_payouts", "recipient_id")}
    members = next(view for view in all_views() if view.name == "members")
    assert "show_member_details" in render(members, SPACE)
    platform = render(members, PLATFORM)
    assert "NULL::text AS \"display_name\"" in platform and "NULL::text AS \"email\"" in platform
    assert "u.email" not in platform


def test_every_space_view_is_pinned_to_the_logins_fixed_space_and_the_switch():
    for view in all_views():
        sql = render(view, SPACE)
        assert "spaceworks_rls_fixed_scope(current_user::text)" in sql, view.name
        assert "enabled_modules ? 'analytics'" in sql, view.name


def test_the_payments_views_are_amounts_only():
    payments = [view for view in all_views() if view.domain == "payments"]
    names = {column.name for view in payments for column in view.columns}
    assert "member_id" not in names
    assert not {"external_order_id", "checkout_url", "subject_label", "counterparty", "reference"} & names


def test_domains_are_registered_modules_and_names_unique():
    assert DOMAIN_MODULES == ("inventory", "machines", "bookings", "events", "tickets", "membership",
                              "payments", "procurement", "donations", "shop", "lending_contexts",
                              "access_safety", "release_devices_cards")
    names = [view.name for view in all_views()]
    assert len(names) == len(set(names))
    assert VIEWS_VERSION == 3 and all(view.since <= VIEWS_VERSION for view in all_views())


def test_release_two_views_are_registered_at_version_two():
    for view in L18_DONATIONS + L22_SHOP:
        assert view.since == 2, view.name


def test_l18_never_exposes_tax_details_or_secrets():
    sources = " ".join(view.source + " ".join(c.expr for c in view.columns) for view in L18_DONATIONS)
    sources = sources.replace("wants_tax_receipt", "")  # the reviewed boolean (ALLOWED above), never a receipt
    for word in ("DonorTaxDetail", "donor_name", "donor_email", "access_secret", "manage_secret", "tax_receipt",
                 "contact_", "PersonalCalendarFeed"):
        assert word not in sources


def test_every_view_and_column_is_documented():
    text = DOCS.read_text(encoding="utf-8")
    assert f"Catalogue version {VIEWS_VERSION}" in text
    for view in all_views():
        assert f"### `{view.name}`" in text, view.name
        for column in view.columns:
            assert f"| `{column.name}` |" in text, (view.name, column.name)


def test_shop_and_payout_people_are_masked_and_never_named():
    masked = {(view.name, column.name) for view in L22_SHOP + _named("prize_payouts")
              for column in view.columns if column.pii}
    assert masked == {("shop_orders", "member_id"), ("prize_payouts", "recipient_id")}
    text = " ".join(column.expr for view in L22_SHOP for column in view.columns)
    for word in ("guest_name", "guest_email", "status_secret", "pickup_code", "created_by", "collected_by",
                 "actor", "opened_by", "closed_by", "confirmed_by"):
        assert word not in text


R12 = ("loan_event_contexts", "loan_booking_contexts", "loan_charges", "included_hours_usage", "day_pass_products", "guest_passes",
       "guest_certification_grants", "incidents", "incident_actions",
       # Decision 327: machine grants, device adapters, card jobs and event certificates.
       "machine_access_grants", "adapter_usage", "adapter_access_decisions", "card_jobs", "event_certificates")


def test_release_twelve_views_are_registered_at_version_three():
    assert {view.name for view in all_views() if view.since == 3} == set(R12)
    inventory = next(view for view in all_views() if view.name == "inventory_products")
    event_only = next(column for column in inventory.columns if column.name == "event_only")
    assert event_only.expr == "p.event_only" and not event_only.pii


def test_release_twelve_views_carry_ids_not_people_or_text():
    banned = ("revoked_reason", "notes", "title", "description", "location", "involved_note", "resolution_note",
              "waiver_version", "operation_id", "entitlements,", "email", "display_name")
    for view in all_views():
        if view.name not in R12:
            continue
        sql = view.source + " ".join(column.expr for column in view.columns)
        # "title" must not match inside "entitlements" (the guest pass entitlement columns).
        assert not any(re.search(rf"(?<![a-z]){word}", sql) if word == "title" else word in sql
                       for word in banned), view.name
        assert not any(column.pii for column in view.columns), view.name


def test_included_hours_view_reads_the_ledger_and_signs_reversals():
    view = next(view for view in all_views() if view.name == "included_hours_usage")
    assert "IncludedHoursUsage" in view.source and view.makerspace == "u.makerspace_id"
    signed = next(column for column in view.columns if column.name == "signed_minutes")
    assert "'consume'" in signed.expr and "-u.minutes" in signed.expr



def test_loan_context_views_sit_under_their_own_domain():
    """Final audit m33: the context views follow Events / Bookings, so those switches gate them."""
    domains = {view.name: view.domain for view in all_views()}
    assert domains["loan_event_contexts"] == "events"
    assert domains["loan_booking_contexts"] == "bookings"
