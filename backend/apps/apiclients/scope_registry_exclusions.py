"""View names no API-client scope may ever reach (split from `scope_registry.py`).

``lookup`` in the ``scope_registry`` barrel refuses these before consulting the registry.
"""
# Session-only lifecycle routes lie outside the HMAC protected prefixes. Explicit
# exclusion also refuses deployments that extend those prefixes; legacy:v1 never
# grants staff lifecycle authority.
from .scope_registry_programme import SESSION_ONLY
STAFF_ACCOUNT_EXCLUSIONS = frozenset(SESSION_ONLY)
# Release 2 (U-B): staff roles on people replaced the staff-account routes; still session-only.
from apps.accounts.delegated_route_catalog import STAFF_ROLE_ROUTES
STAFF_ACCOUNT_EXCLUSIONS |= STAFF_ROLE_ROUTES
# Reimbursement, stage-form and payout routes are full-session only: no API-key scope may
# reach owner money, payee data, finance files or staff review (views refuse api_client too).
from apps.accounts.reimbursement_route_catalog import BY_NAME as _REIMBURSEMENT_ROUTES
STAFF_ACCOUNT_EXCLUSIONS |= frozenset(_REIMBURSEMENT_ROUTES)


# Owner self-service on the member surface acts on the caller's own job; an API client
# (public scopes or legacy:v1) never acquires it, even if a deployment widens prefixes.
OWNER_SESSION_EXCLUSIONS = frozenset({"member-machine-service-cancel", "member-machine-service-owner",
                                       "hardware_requests:member-borrowing-history",
                                       "hardware_requests:contextual-request-self",
                                       "hardware_requests:contextual-request-staff",
                                       "hardware_requests:equipment-kit-public-list",
                                       "hardware_requests:equipment-kit-public-detail",
                                       "hardware_requests:equipment-kit-list",
                                       "hardware_requests:equipment-kit-detail",
                                       "hardware_requests:equipment-kit-version",
                                       "hardware_requests:equipment-kit-publication",
                                       "hardware_requests:equipment-kit-archive",
                                       "event-equipment-request-products",
                                       "booking-equipment-request-products",
                                       "event-equipment-kits",
                                       "event-equipment-desk",
                                       "event-equipment-availability",
                                       "event-equipment-plan",
                                       "booking-equipment-kits",
                                       "admin-consumable-equipment-sources"})
