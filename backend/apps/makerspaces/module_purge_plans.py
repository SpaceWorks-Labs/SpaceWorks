"""What "purge this module's data" means, per module (plan A9).

Per-app purge is NEW semantics and deliberately narrower than `lifecycle.purge()`,
which deletes an entire archived makerspace. Here the makerspace survives; only one
module's rows, its private object-storage keys and its blind-index entries go.

Each plan declares three things the service needs and cannot infer:

* `delete` -- rows in dependency order, run inside the authorized purge context
  (immutability triggers bypassed for DELETE only).
* `pii_labels` -- registry model labels whose `PiiBlindIndex` rows must go too.
  Blind-index rows carry keyed HMACs of PII and have **no FK** to the source row, so
  nothing deletes them for us; leaving them behind is a genuine PII leak.
* storage collectors -- private keys and public image keys, deleted post-commit.

A module absent from this registry has no purgeable data of its own, or its graph is
inseparable from the makerspace's (see `NOT_SEPARABLE`).
"""

from dataclasses import dataclass
from typing import Callable

from .module_purge_collectors_booking_website import bookings_private_keys, bookings_private_key_sizes

from apps.makerspaces.module_purge_collectors import (
    bookings_delete,
    bookings_public_images,
    discord_destinations_delete,
    events_delete,
    events_private_key_sizes,
    events_private_keys,
    events_public_images,
    mattermost_destinations_delete,
    machine_service_delete,
    machine_service_private_key_sizes,
    machine_service_private_keys,
    membership_delete,
    membership_private_key_sizes,
    membership_private_keys,
    membership_public_image_keys,
    notifications_delete,
    qr_print_batches_delete,
    slack_destinations_delete,
    stock_transfers_delete,
    stocktake_delete,
    telegram_destinations_delete,
    webhook_destinations_delete,
)
from apps.makerspaces.module_purge_collectors_devices import devices_delete
from apps.makerspaces.module_purge_collectors_reimbursements import (
    REIMBURSEMENT_PII_LABELS,
    STAGE_PII_LABELS,
)
from apps.makerspaces.module_purge_collectors_reports import (
    reports_delete,
    reports_private_keys,
)


@dataclass(frozen=True)
class ModulePurgePlan:
    key: str
    summary: str
    delete: Callable
    # There is deliberately NO `payment_subjects`. A `Payment` is payments-module data, and
    # its subject going away is not grounds to destroy the financial record -- the same
    # reasoning that already retained membership dues. No module purge deletes a payment;
    # the whole-makerspace `lifecycle.purge` still does, because `Payment.makerspace` is
    # PROTECT and the rows cannot outlive their makerspace. Surviving payments keep a
    # snapshotted `subject_label` so a receipt stays readable once its subject is gone.
    pii_labels: tuple[str, ...] = ()
    private_keys: Callable | None = None
    # `{object_key: size_bytes}` for private objects whose bytes were charged to the
    # makerspace's storage quota. Declared separately from `private_keys` so the quota is
    # released only for keys whose deletion the bucket actually confirmed: a private
    # delete is best-effort, and freeing bytes for an object that survived is the
    # direction that permanently grants free storage. A module that charges nothing for
    # its private objects leaves this None.
    private_key_sizes: Callable | None = None
    public_image_keys: Callable | None = None


# Modules whose rows cannot be purged independently of the makerspace itself. Naming
# them explicitly (rather than letting them fall through as "unknown") is the point:
# the operator gets told why, not just "no".
NOT_SEPARABLE = {
    "machines": (
        "Machine rows host warranty records, inventory-backed consumables and machine "
        "service history, so deleting them piecemeal would orphan other modules. Purge "
        "machine_service first, then archive and purge the makerspace."
    ),
    "public_inventory": "Core module.",
    "request_workflow": "Core module.",
    "staff_admin": "Core module.",
    "evidence_uploads": "Core module.",
    "qr_management": "Core module.",
    "scanner": "Core module.",
}


from .module_purge_collectors_addressed import sms_delete, whatsapp_delete

PLANS = (
    ModulePurgePlan("sms", "SMS credentials, sender identities, consent and delivery history.", sms_delete),
    ModulePurgePlan("whatsapp", "WhatsApp credentials, sender identities, bindings, consent and delivery history.", whatsapp_delete),
    ModulePurgePlan(
        # The one-line description is what the purge confirmation shows an operator, so it
        # has to name what actually goes: registrations are only the first layer.
        "events",
        "Events, series, registrations, check-in history, feedback, certificates, template revisions, artwork and "
        "calendar feeds.",
        events_delete,
        pii_labels=(
            "events.EventRegistration",
            "events.EventFeedbackResponse",
            "events.EventAttendanceCertificate",
            "events.EventBroadcast",
            *REIMBURSEMENT_PII_LABELS,
            *STAGE_PII_LABELS,
        ),
        private_keys=events_private_keys,
        private_key_sizes=events_private_key_sizes,
        public_image_keys=events_public_images,
    ),
    ModulePurgePlan(
        "bookings", "Bookable spaces and their bookings.", bookings_delete,
        pii_labels=("bookings.Booking", "bookings.BookingBroadcast"),
        public_image_keys=bookings_public_images,
        private_keys=bookings_private_keys, private_key_sizes=bookings_private_key_sizes,
    ),
    # Maintenance and To-Buy are per-parent capabilities since #97; their data purge is
    # `capability_purge_plans` (split per parent), not a module plan.
    ModulePurgePlan(
        "notifications", "In-app notification rows.", notifications_delete,
        pii_labels=("notifications.NotificationInboxRow", "notifications.MemberBroadcast"),
    ),
    # No plan lists payments any more -- see ModulePurgePlan above. Membership dues were
    # always the exception; they are now simply the rule.
    ModulePurgePlan(
        "membership",
        "Admission settings, applications and vouches, invitation requests, membership plans and terms, and member "
        "profiles with their projects and imagery. Memberships, waivers and acceptance "
        "evidence stay as core RBAC/liability state.",
        membership_delete,
        pii_labels=("makerspaces.MemberCard", "makerspaces.InvitationRequest", "makerspaces.MembershipRequest"),
        private_keys=membership_private_keys,
        private_key_sizes=membership_private_key_sizes,
        public_image_keys=membership_public_image_keys,
    ),
    ModulePurgePlan(
        "machine_service",
        "Service requests, queues, uploads, consumption ledgers and the usage entries "
        "they produced. Consumable pools stay (they belong to `machines`).",
        machine_service_delete,
        pii_labels=("machines.MachineServiceRequest",),
        private_keys=machine_service_private_keys,
        private_key_sizes=machine_service_private_key_sizes,
    ),
    # One plan per chat channel, not one for "chat": a tenant may purge Discord while
    # keeping the Slack rooms it still uses, and each key is uninstalled independently.
    # Delivery logs deliberately survive (`destination` is SET_NULL) — the record that a
    # message was attempted is history, the webhook URL is the secret.
    ModulePurgePlan(
        "telegram", "Telegram destinations and their chat ids.", telegram_destinations_delete
    ),
    ModulePurgePlan(
        "slack", "Slack destinations and their stored webhooks.", slack_destinations_delete
    ),
    ModulePurgePlan(
        "mattermost",
        "Mattermost destinations and their stored webhooks.",
        mattermost_destinations_delete,
    ),
    ModulePurgePlan(
        "discord", "Discord destinations and their stored webhooks.", discord_destinations_delete
    ),
    ModulePurgePlan(
        "webhook",
        "Signed-webhook destinations, their endpoint URLs and signing secrets.",
        webhook_destinations_delete,
    ),
    # Metric rollups stay: they are append-only rows behind the evidence retention fence,
    # so removing them is a retention decision, not part of switching reporting off.
    ModulePurgePlan(
        "reports",
        "Saved report views and scheduled report deliveries: preferences, schedules, delivery history and delivered files. "
        "Metric rollups stay (retention fence).",
        reports_delete,
        private_keys=reports_private_keys,
    ),
    ModulePurgePlan("stocktake", "Stocktake sessions, lines and ledger entries.", stocktake_delete),
    ModulePurgePlan("stock_transfers", "Stock transfers and their lines.", stock_transfers_delete),
    ModulePurgePlan("qr_print_batches", "QR print batches and their items.", qr_print_batches_delete),
    ModulePurgePlan(
        "devices",
        "Devices, printer bindings, commands, measured reports, label receipts and device event history.",
        devices_delete,
    ),
)

from apps.presence.purge import delete as presence_delete
PLANS += (ModulePurgePlan("presence", "Current and historical presence sessions and display preferences.", presence_delete),)
from .module_purge_collectors_reimbursements import reimbursement_delete
PLANS += (ModulePurgePlan(
    "event_reimbursements",
    "Terminal travel-support history: programmes, requests, awards and claims. Core payout liabilities, "
    "finance receipts and stage forms survive.",
    reimbursement_delete, pii_labels=REIMBURSEMENT_PII_LABELS,
),)
from apps.shop.purge import delete as shop_delete, public_images as shop_public_images  # noqa: E402
PLANS += (ModulePurgePlan("shop", "Shop catalogue, stock history, orders, returns and cash-ups. Shop charges, their "
                          "receipts and refunds are core ledger and stay.", shop_delete, pii_labels=("shop.ShopOrder",),
                          public_image_keys=shop_public_images),)
BY_KEY = {plan.key: plan for plan in PLANS}
