"""Initial OpenAPI schema settings."""

SPECTACULAR_SETTINGS = {
    "TITLE": "Space Works API",
    "DESCRIPTION": (
        "Multi-tenant makerspace hardware loan system.\n\n"
        "Public flow: browse inventory, search with `q`, page with `page`, "
        "sign in as a member, submit a borrow request, then track it by public token.\n\n"
        "Admin flow: authenticate with JWT, manage makerspaces, inventory, "
        "staff, QR labels, bulk imports, request review, issue, and return.\n\n"
        "Authentication: staff/admin endpoints use `Authorization: Bearer <access>`. "
        "Public browser endpoints can use `X-Publishable-Key` when public key "
        "hardening is enabled. Server API clients send `X-Client-Id`, `X-Timestamp`, "
        "`X-Nonce`, and `X-Signature`. Generate a unique, unpredictable `X-Nonce` "
        "for every request and sign the byte sequence "
        "`METHOD\\nFULL_PATH\\nTIMESTAMP\\nNONCE\\nBODY` with HMAC-SHA256. "
        "The nonce uses 1-128 characters from `A-Z`, `a-z`, `0-9`, `.`, `_`, `~`, "
        "and `-`. A deployment may temporarily accept the legacy nonce-less signed "
        "format while `APICLIENT_REQUIRE_NONCE` is disabled."
    ),
    # Kept in step with the root `VERSION` file by
    # `tests/test_version_consistency.py`. It cannot simply READ that file: the backend
    # image is built with `context: ./backend`, so the repo root is outside the build
    # context and the file does not exist inside the container.
    "VERSION": "0.9.2",
    "ENUM_NAME_OVERRIDES": {
        "DevicePlatformEnum": "apps.accounts.models_devices.DevicePlatform.choices",
        # Each anyOf proof branch has a `type` discriminator. Without unique names
        # spectacular extracts all three as DeviceAttestationPayloadTypeEnum and
        # silently replaces the iOS/development choices with the Android choice.
        "PlayIntegrityAttestationTypeEnum": ["play_integrity"],
        "AppAttestAttestationTypeEnum": ["app_attest"],
        "DevelopmentAttestationTypeEnum": ["development"],
        # Phase 9b: the kiosk evidence-prepare route shares these choices; pin the
        # existing component name so the generated client type does not rename.
        "EvidenceUrlRequestEvidenceTypeEnum": [("issue", "Issue"), ("return", "Return")],
        "QrPrintBatchStatusEnum": [
            ("draft", "Draft"),
            ("printed", "Printed"),
            ("archived", "Archived"),
        ],
        # Refund cases: stable names instead of hash-suffixed collision names.
        "RefundCaseKindEnum": [("due", "Due under policy"), ("request", "Requested by member")],
        "RefundCaseStatusEnum": [
            ("open", "Open"), ("approved", "Approved"), ("approval_failed", "Approval failed"),
            ("declined", "Declined"), ("withdrawn", "Withdrawn"), ("void", "Void"),
        ],
        "RefundCaseReasonCodeEnum": [
            ("event_cancelled", "Event cancelled by the space"), ("registration_cancelled", "Registration cancelled"),
            ("booking_cancelled", "Booking cancelled"), ("staff_cancelled", "Cancelled by staff"),
            ("membership_cancelled", "Membership term cancelled"),
            ("member_request", "Member request"),
            ("capture_flagged", "Unexpected online capture"),  # lane L5 (capture flags)
            ("fee_waived", "Loan fee waived by staff"),  # lane L15 (loan fee waivers)
            ("order_unfulfilled", "Order could not be seated"),  # lane L6 (ticket orders)
            ("ticket_type_changed", "Changed to a cheaper ticket"),  # lane L6
            ("pass_occurrence_cancelled", "Pass occurrence cancelled"),  # lane L6
        ],
        "InventoryAssetStatusEnum": [
            ("available", "Available"),
            ("reserved", "Reserved"),
            ("issued", "Issued"),
            ("damaged", "Damaged"),
            ("lost", "Lost"),
            ("retired", "Retired"),
            ("maintenance", "Maintenance"),
        ],
    },
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVERS": [
        {"url": "http://localhost:8001", "description": "Local Docker backend"},
        {"url": "http://localhost:8000", "description": "Local Django runserver"},
    ],
    "TAGS": [
        {"name": "Auth", "description": "Staff login, refresh, logout, and profile."},
        {"name": "Public inventory", "description": "Public makerspace catalog browsing."},
        {"name": "Public requests", "description": "Public borrow request and status flows."},
        {"name": "Admin makerspaces", "description": "Admin makerspace CRUD."},
        {"name": "Admin inventory", "description": "Admin inventory CRUD and search lists."},
        {"name": "Admin requests", "description": "Review, handover, issue, and return workflows."},
        {"name": "Bulk import", "description": "Inventory import preview and apply workflow."},
        {"name": "Admin users", "description": "Staff, guest-admin, and access restriction."},
        {"name": "QR assets", "description": "QR-coded boxes, tools, scans, print, revoke."},
        {"name": "Telegram", "description": "Telegram webhook and alert integration."},
        {"name": "Printing", "description": "3D printing request and management APIs."},
        {"name": "Payments", "description": "Stripe payment configuration and verified webhooks."},
        {"name": "Containers", "description": "Container hierarchy, movement, contents, and scan history."},
        {"name": "Stock transfers", "description": "Administrative stock movement between containers and makerspaces."},
        {"name": "Stocktake", "description": "Stocktake sessions, line counts, approvals, and adjustments."},
        {"name": "Analytics", "description": "Operational inventory analytics and report summaries."},
        {"name": "Reports", "description": "CSV and XLSX operational report exports."},
        {"name": "QR print batches", "description": "QR label batch creation, item management, and print HTML."},
        {"name": "Asset units", "description": "Individual asset unit generation and QR assignment."},
        {"name": "Health", "description": "Health and readiness probes."},
        {"name": "Notifications", "description": "Persistent staff inbox notifications."},
        {"name": "Platform", "description": "Superadmin platform settings: email, social sign-in, Stripe Connect."},
        {"name": "Admin hosting", "description": "Platform subdomains and custom-domain verification."},
        {"name": "Internal", "description": "Infrastructure-only routes (TLS ask, cron); refused at the public edge."},
        {"name": "API clients", "description": "HMAC API clients, their scopes and integration settings."},
        {"name": "API key requests", "description": "Staff requests for a superadmin to issue an API client."},
    ],
}
