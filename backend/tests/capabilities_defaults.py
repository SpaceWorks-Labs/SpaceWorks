import pytest
from django.core.exceptions import ValidationError

from apps.makerspaces.capabilities import default_enabled_features, validate_capabilities
from apps.makerspaces.module_registry import core_module_keys


def test_kiosk_feature_is_standalone_default_off_and_advertises_two_workflows():
    from apps.makerspaces.capabilities import FEATURE_DEFINITIONS, FEATURES
    from apps.makerspaces.platform import FEATURE_WORKFLOWS

    definition = FEATURES["inventory.kiosk"]
    assert definition.parent_module is None
    assert definition.default_enabled is False
    assert "inventory.kiosk" not in default_enabled_features()
    # Merged lanes added billing/loan policy, staff security, admission, inbox,
    # certification/reminder and offline-event capabilities, WP1 ticketing, WP2 family
    # visibility, WP3 delivery/recurrence, and WP4 inventory/machine opt-ins.
    # Lane G deliberately adds the default-off organization audience feature.
    # Lane D adds event broadcasts/PDF/detail exports; BK lanes and Lane E add
    # private confirmations, arrival, passes, resource tools/reports/grants and designs.
    # Merged staging (2026-10-24): Yuyu lanes F, C and BK-F (event and booking websites,
    # embeds and API reads), Pages, mobile, cloud, hosting, machine ETA and the events
    # programme (hackathons, mentoring, volunteering, gallery, reimbursements).
    # 264 = the 263 below + 1 switch added in the final 0.12.0 round; every definition is frontend-exposed, so this is
    # also the line count of the frontend mirror (lib/featureDefinitions/part*.ts), which another test holds equal.
    assert len(FEATURE_DEFINITIONS) == 264  # 0.12.0 parity round: + 41 keys (events badge/crew/discovery switches, machine certifications and induction events, Device Adapter integration keys, space display, email sender identity, legal pages ...), each pinned individually by the frontend mirror and the defaults list; before it: + 8 Device Adapter media/data keys (decision 321), + 5 Device Adapter API keys (machines.integrations + .access/.usage_billing/.video/.kiosk/.recording; decisions 310-312), + charges.donations (r2-gap-money, #184), + events.peoples_choice (r2-peoples-choice, #181), + events.prize_claims, events.deposits, events.accepted_addons (r2-hack-money), + 2 GAP2 maintenance reminder keys, + platform.help_centre (L20), + 14 shop.* + charges.shop + payments.shop (L22), + charges.price_drop_refunds (L24), + 6 L21b keys, + 6 L21a participation keys, + 10 L18 keys, + 8 L6 ticketing keys, + 2 L13 sheet-import keys, + 5 L3 card keys, + machines.sessions (R2 L23), - security.staff_mfa_required (R2 S-A, retired), + mobile.watch_actions (R2 L19), + machines.integrations (R2 L10), + inventory.contact_self_checkout (#95), + 13 L17 per-parent keys (#97), + events.pairwise_judging (R2 L7), + 3 L1 keys, + 9 L2 keys, + 14 L4 membership keys, + 7 L5 billing/finance keys, + 3 L15 pricing keys, + 12 L12 keys
    assert {"events.website", "events.embed", "events.api_read",
            "bookings.website", "bookings.embed", "bookings.api_read"} <= FEATURES.keys()
    audience = FEATURES["events.organization_audience"]
    assert audience.parent_module == "events" and not audience.default_enabled
    assert audience.key not in default_enabled_features()
    assert FEATURE_WORKFLOWS["inventory.kiosk"] == ["kiosk", "kiosk_scanner"]


def test_feature_registry_rejects_unknown_duplicate_and_missing_dependencies():
    with pytest.raises(ValidationError):
        validate_capabilities(["public_inventory"], ["inventory.unknown"])
    with pytest.raises(ValidationError):
        validate_capabilities(
            ["public_inventory"],
            ["inventory.self_checkout", "inventory.self_checkout"],
        )
    with pytest.raises(ValidationError):
        validate_capabilities(["machines"], ["payments.machines"])


def test_feature_defaults_are_dormant_except_legacy_compatible_self_checkout():
    # The A6 master switches default ON so that adding them changes nothing for a space
    # already using the capability -- they are additive `AND`s in front of readiness
    # checks that stay dormant on their own. `payments.enabled` being on therefore
    # enables nothing by itself: every per-DOMAIN payments feature must still be off by
    # default, which is what the second assertion pins.
    # Staff invitations also stay available by default, including without the
    # community membership module; the staff security switch remains opt-in.
    assert default_enabled_features() == [
        "reports.saved_views",
        "billing.documents",
        "staff.invitations",
        "ui.delight",
        "ui.easter_eggs",
        "charges.enabled",
        "charges.bookings",
        "charges.events",
        "charges.machines",
        "charges.membership",
        "charges.loans",
        "inventory.self_checkout",
        "payments.enabled",
        "mobile.push",
        "presence.geofence",
        "loans.enabled",
        "events.anonymous_feedback",
        # L5: record-only money screens, on by default (they collect nothing themselves).
        "billing.disputes",
        "billing.capture_flags",
        "finance.ledger",
        # L15: pricing through the kernel and loan fee waivers.
        "charges.pricing",
        "loans.fee_waivers",
        # L12: the uniform machine job flow is today's behaviour, so it starts on.
        "machines.job_requests",
        "machines.job_quotes",
        # L19 (#128 C-27): watch-friendly push actions.
        "mobile.watch_actions",
        # r2-gap-money (#184 G10): gifts and sponsor charges are recorded like every other domain.
        "charges.donations",
        # L18: the booking and event calendar feeds existed before their switches.
        "bookings.calendar_feed",
        "events.calendar_feed",
        # L21b: gallery search is on wherever the gallery is on (inert while the gallery is off).
        "events.gallery_search",
        # L22: shop switches that keep today's counter behaviour, and the shop's charge tracking.
        "shop.holds",
        "shop.public_stock",
        "shop.receipts",
        "charges.shop",
        # L20: the help centre; GAP2: item and room maintenance reminders.
        "platform.help_centre",
        "inventory.maintenance_reminders",
        "bookings.room_maintenance_reminders",
        # 0.12.0 events parity: team moderation, crew kinds, the badge designer / desk print / role badges,
        # discovery filters and space insights keep today's behaviour (migration makerspaces 0151 switches them on).
        "events.team_moderation",
        "events.crew_kinds",
        "events.badge_designer",
        "events.badge_desk_print",
        "events.role_badges",
        "events.discovery_filters",
        "events.space_insights",
        # Sender identity and the space legal pages are on by default (inert until configured).
        "email.sender_identity",
        "legal.space_pages",
    ]
    assert not any(
        key.startswith("payments.") and key != "payments.enabled"
        for key in default_enabled_features()
    )
    # The `charges.*` family is the deliberate exception to "dormant by default". It
    # decides whether money owed is RECORDED, not whether it can be collected, so it
    # cannot make an unconfigured space start charging anyone: the real trigger stays a
    # configured amount. Defaulting it off would reproduce the bug it exists to fix --
    # a space with no gateway silently losing every debt.
    assert all(
        key.startswith("charges.") for key in default_enabled_features()[5:11]
    )


def test_delegated_notification_recipients_default_off_and_match_the_frontend():
    from apps.makerspaces.capabilities import FEATURES

    definition = FEATURES["notifications.delegated_recipients"]
    # Re-parented to machines by L17 (#97), behind machines.maintenance; key unchanged.
    assert definition.parent_module == "machines"
    assert definition.requires_features == ("machines.maintenance",)
    assert definition.default_enabled is False
    assert definition.key not in default_enabled_features()
