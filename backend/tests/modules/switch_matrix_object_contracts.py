"""Reviewed seeded-object operations; expectations come from the owning handlers.

Each entry pins domain, URL name, verb, optional capability, on status/code, and body.
Module refusals are typed. Some event capabilities deliberately conceal their surface
with not_found; those must be listed explicitly instead of inferred from an HTTP crawl.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Operation:
    target: str
    name: str
    method: str = "GET"
    feature: str | None = None
    status: int = 200
    code: str | None = None
    body: tuple = ()
    feature_code: str = "feature_disabled"
    module_code: str = "module_disabled"


OPERATIONS = (
    Operation("event", "events-programme-admin-certificate-signatories", feature="events.certificate_designer"),
    Operation("event", "events-programme-admin-certificate-signatories", "POST", "events.certificate_designer",
              body=(("slot", 1), ("name", "Changed signatory"))),
    Operation("event", "events-programme-admin-certificate-signatory-detail", "DELETE", "events.certificate_designer"),
    Operation("event", "events-programme-admin-certificate-signatory-candidates", feature="events.certificate_designer"),
    Operation("event", "events-programme-admin-certificate-signatory-policy", "POST", "events.certificate_designer",
              body=(("required", False),)),
    Operation("event", "events-programme-admin-certificates-issued"),
    Operation("event", "events-programme-admin-certificate-eligibility"),
    Operation("event", "events-programme-admin-certificate-publication-policy"),
    Operation("event", "admin-event-tickets", feature="events.ticket_types"),
    Operation("event", "admin-event-tickets", "POST", "events.ticket_types", 201,
              body=(("name", "Free admission"), ("amount", "0.00"))),
    Operation("event", "admin-event-invites", feature="events.invites"),
    Operation("event", "admin-event-invites", "POST", "events.invites", 201),
    Operation("event", "admin-event-promos", feature="events.promo_codes"),
    Operation("event", "admin-event-promos", "POST", "events.promo_codes", 201, body=(("percent_off", 10),)),
    Operation("event", "admin-event-addons", feature="events.addons"),
    Operation("addon", "admin-event-addon-detail", "PATCH", "events.addons", body=(("name", "Changed add-on"),)),
    Operation("addon", "admin-event-addon-detail", "DELETE", "events.addons", 204),
    Operation("event", "admin-event-orders", feature="events.orders"),
    Operation("event", "admin-event-sales-settings", feature="events.orders"),
    Operation("event", "admin-event-sales-settings", "PUT", "events.orders"),
    Operation("event", "admin-event-refund-policy", feature="events.refund_override"),
    Operation("event", "admin-event-check-in-station", feature="events.offline_checkin"),
    Operation("event", "admin-event-check-in-station", "DELETE", "events.offline_checkin"),
    Operation("event", "admin-event-website-content", feature="events.website"),
    Operation("event", "admin-event-website-content", "PUT", "events.website",
              body=(("revision", 1), ("sections", []), ("sessions", []))),
    Operation("event", "admin-event-id-cards", feature="events.id_cards"),
    Operation("event", "admin-event-card-settings", feature="events.id_cards"),
    Operation("event", "admin-event-card-settings", "PUT", "events.id_cards",
              body=(("extras_visible_to_organizers", True),)),
    Operation("event", "admin-event-card-jobs", feature="events.id_cards"),
    Operation("room", "admin-bookable-space-detail"),
    Operation("room", "admin-bookable-space-detail", "PATCH", body=(("name", "Changed room"),)),
    Operation("room", "admin-bookable-space-booking-rules"),
    Operation("room", "admin-bookable-space-booking-rules", "PATCH"),
    Operation("room", "admin-booking-staff-grants", feature="bookings.staff_grants"),
    Operation("room", "admin-booking-staff-invites", feature="bookings.staff_grants"),
    Operation("room", "admin-booking-website", feature="bookings.website"),
    Operation("room", "admin-booking-website", "PUT", "bookings.website", body=(("revision", 1), ("sections", []))),
    Operation("room", "admin-booking-website-release", "POST", "bookings.website",
              body=(("revision", 1), ("released", True))),
    Operation("box", "container-detail"),
    Operation("box", "container-detail", "PATCH", body=(("label", "Changed shelf"),)),
    Operation("box", "container-contents"),
    Operation("box", "container-history"),
    Operation("stocktake", "stocktake-detail"),
    Operation("batch", "qr-print-batch-detail"),
    Operation("transfer", "stock-transfer-detail"),
    Operation("machine", "admin-machine-detail"),
    Operation("machine", "admin-machine-detail", "PATCH", body=(("name", "Changed machine"),)),
    Operation("machine", "admin-machine-documents"),
    Operation("machine", "admin-machine-operators"),
    Operation("machine", "admin-machine-downtime", feature="machines.maintenance",
              feature_code="capability_disabled", module_code="capability_disabled"),
    Operation("machine", "admin-machine-lockout", feature="machines.maintenance",
              feature_code="capability_disabled", module_code="capability_disabled"),
    Operation("shop_product", "admin-shop-product", "PATCH", body=(("name", "Changed shop product"),), module_code="shop_closed"),
    Operation("shop_product", "admin-shop-product", "DELETE", module_code="shop_closed"),
    Operation("shop_variant", "admin-shop-variant", "DELETE", module_code="shop_closed"),
    Operation("shop_variant", "admin-shop-variant-stock", "POST",
              body=(("kind", "restock"), ("quantity", 1), ("reason", "Switch restoration proof")), module_code="shop_closed"),
)

MODULES = {"event": "events", "addon": "events", "room": "bookings", "box": "containers",
           "stocktake": "stocktake", "batch": "qr_print_batches", "transfer": "stock_transfers",
           "machine": "machines", "shop_product": "shop", "shop_variant": "shop"}


def object_cases(shard, shards=3):
    cases = [(index, key, native) for index, operation in enumerate(OPERATIONS)
             for key in (MODULES[operation.target], *((operation.feature,) if operation.feature else ()))
             for native in (False, True)]
    return cases[shard::shards]


def case_id(case):
    index, key, native = case
    operation = OPERATIONS[index]
    return f"{'native' if native else 'web'}:{key}:{operation.method}:{operation.name}"
