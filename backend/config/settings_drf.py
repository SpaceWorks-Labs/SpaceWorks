"""DRF defaults, gate authentication and throttle rates."""

from config.settings_runtime import TRUSTED_PROXY_COUNT, env

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 24,
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.SpaceWorksJWTAuthentication",
    ),
    # DENY BY DEFAULT (review fix #4): every view requires auth unless it explicitly
    # opts into AllowAny. Public views are marked AllowAny in Step 3b.
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "EXCEPTION_HANDLER": "apps.hardware_requests.exceptions.workflow_exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "login": env("THROTTLE_LOGIN", default="10/min"),
        "mfa_verify": env("THROTTLE_MFA_VERIFY", default="10/min"),
        "mfa_challenge": env("THROTTLE_MFA_CHALLENGE", default="10/min"),
        "mfa_user": env("THROTTLE_MFA_USER", default="20/hour"),
        "mfa_manage": env("THROTTLE_MFA_MANAGE", default="10/hour"),
        "staff_invite": env("THROTTLE_STAFF_INVITE", default="20/hour"),
        "staff_invite_accept": env("THROTTLE_STAFF_INVITE_ACCEPT", default="10/min"),
        "device_attestation_challenge": env("THROTTLE_DEVICE_ATTESTATION_CHALLENGE", default="5/min"),
        "device_login": env("THROTTLE_DEVICE_LOGIN", default="5/min"),
        "device_login_user": env("THROTTLE_DEVICE_LOGIN_USER", default="10/hour"),
        "device_refresh": env("THROTTLE_DEVICE_REFRESH", default="30/min"),
        "push_device_registration": env("THROTTLE_PUSH_DEVICE_REGISTRATION", default="10/min"),
        "social_nonce": env("THROTTLE_SOCIAL_NONCE", default="10/min"),
        "social_login": env("THROTTLE_SOCIAL_LOGIN", default="10/min"),
        "social_link": env("THROTTLE_SOCIAL_LINK", default="10/hour"),
        # Issuance and redemption deliberately have independent budgets. A member who
        # mistypes a physically handed code must not consume the staff issue budget (or
        # vice versa), repeating the phone-OTP shared-bucket failure.
        "member_claim_issue": env("THROTTLE_MEMBER_CLAIM_ISSUE", default="10/hour"),
        # Each staff verification run is bounded cryptographic + anchor work.
        "audit_verification": env("THROTTLE_AUDIT_VERIFICATION", default="6/hour"),
        "member_claim_redeem": env("THROTTLE_MEMBER_CLAIM_REDEEM", default="10/min"),
        # Tighter than the email OTP rates: every one of these costs the operator money
        # and lands on a stranger's handset if the number is wrong.
        "phone_otp_request": env("THROTTLE_PHONE_OTP_REQUEST", default="5/min"),
        "phone_otp_number": env("THROTTLE_PHONE_OTP_NUMBER", default="5/hour"),
        "phone_login_confirm": env("THROTTLE_PHONE_LOGIN_CONFIRM", default="10/min"),
        "phone_confirm_number": env("THROTTLE_PHONE_CONFIRM_NUMBER", default="15/hour"),
        "password_reset_request": env(
            "THROTTLE_PASSWORD_RESET_REQUEST",
            default="5/min",
        ),
        "password_reset_email": env(
            "THROTTLE_PASSWORD_RESET_EMAIL",
            default="5/hour",
        ),
        "password_reset_confirm": env(
            "THROTTLE_PASSWORD_RESET_CONFIRM",
            default="10/min",
        ),
        "password_reset_confirm_email": env(
            "THROTTLE_PASSWORD_RESET_CONFIRM_EMAIL",
            default="15/hour",
        ),
        "member_sign_up": env("THROTTLE_MEMBER_SIGN_UP", default="5/min"),
        "email_verification_resend": env(
            "THROTTLE_EMAIL_VERIFICATION_RESEND", default="5/min"
        ),
        "email_verification_confirm": env(
            "THROTTLE_EMAIL_VERIFICATION_CONFIRM", default="10/min"
        ),
        "member_verification_email": env(
            "THROTTLE_MEMBER_VERIFICATION_EMAIL", default="5/hour"
        ),
        "telegram_webhook": env("THROTTLE_TELEGRAM_WEBHOOK", default="60/min"),
        "public_request_submit": env(
            "THROTTLE_PUBLIC_REQUEST_SUBMIT",
            default="10/min",
        ),
        "anonymous_request_ip_burst": env(
            "THROTTLE_ANONYMOUS_REQUEST_IP_BURST",
            default="5/min",
        ),
        "anonymous_request_ip_hour": env(
            "THROTTLE_ANONYMOUS_REQUEST_IP_HOUR",
            default="30/hour",
        ),
        "anonymous_request_email": env(
            "THROTTLE_ANONYMOUS_REQUEST_EMAIL",
            default="5/hour",
        ),
        "public_invitation_request": env(
            "THROTTLE_PUBLIC_INVITATION_REQUEST", default="10/hour"
        ),
        "hosting_request_submit": env("THROTTLE_HOSTING_REQUEST_SUBMIT", default="5/hour"),
        "hosting_request_email": env("THROTTLE_HOSTING_REQUEST_EMAIL", default="3/day"),
        "hosting_request_token": env("THROTTLE_HOSTING_REQUEST_TOKEN", default="30/hour"),
        "hosting_invitation_create": env("THROTTLE_HOSTING_INVITATION_CREATE", default="20/hour"),
        "print_request_submit": env("THROTTLE_PRINT_REQUEST_SUBMIT", default="10/min"),
        "public_tool_checkout": env("THROTTLE_PUBLIC_TOOL_CHECKOUT", default="10/min"),
        "public_tool_return": env("THROTTLE_PUBLIC_TOOL_RETURN", default="10/min"),
        "request_submit": env("THROTTLE_REQUEST_SUBMIT", default="10/min"),
        "request_status": env("THROTTLE_REQUEST_STATUS", default="60/min"),
        "public_read": env("THROTTLE_PUBLIC_READ", default="120/min"),
        "event_register": env("THROTTLE_EVENT_REGISTER", default="10/hour"),
        "event_registration_retry": env(
            "THROTTLE_EVENT_REGISTRATION_RETRY", default="30/hour"
        ),
        "event_checkin_resolve": env(
            "THROTTLE_EVENT_CHECKIN_RESOLVE", default="60/min"
        ),
        "event_offline_roster": env(
            "THROTTLE_EVENT_OFFLINE_ROSTER", default="10/hour"
        ),
        "event_offline_sync": env(
            "THROTTLE_EVENT_OFFLINE_SYNC", default="60/hour"
        ),
        "event_station_pin_token": env(
            "THROTTLE_EVENT_STATION_PIN_TOKEN", default="10/hour"
        ),
        "event_station_pin_ip": env(
            "THROTTLE_EVENT_STATION_PIN_IP", default="30/hour"
        ),
        "event_station_session": env(
            "THROTTLE_EVENT_STATION_SESSION", default="120/hour"
        ),
        "event_station_reveal": env(
            "THROTTLE_EVENT_STATION_REVEAL", default="5/hour"
        ),
        "kiosk_station_pin_token": env(
            "THROTTLE_KIOSK_STATION_PIN_TOKEN", default="10/hour"
        ),
        "kiosk_station_pin_ip": env(
            "THROTTLE_KIOSK_STATION_PIN_IP", default="30/hour"
        ),
        "kiosk_station_session": env(
            "THROTTLE_KIOSK_STATION_SESSION", default="120/hour"
        ),
        "kiosk_operator_lease": env(
            "THROTTLE_KIOSK_OPERATOR_LEASE", default="30/hour"
        ),
        "kiosk_replay_prepare": env("THROTTLE_KIOSK_REPLAY_PREPARE", default="60/hour"),
        "kiosk_replay_execute": env("THROTTLE_KIOSK_REPLAY_EXECUTE", default="240/hour"),
        # Fixed, not env-tunable: the plan pins reveal at exactly 5/hour.
        "kiosk_station_reveal": "5/hour",
        "event_calendar_feed_token": env(
            "THROTTLE_EVENT_CALENDAR_FEED_TOKEN", default="120/hour"
        ),
        "event_calendar_feed_ip": env(
            "THROTTLE_EVENT_CALENDAR_FEED_IP", default="300/hour"
        ),
        "public_stats": env("THROTTLE_PUBLIC_STATS", default="30/min"),
        "client_public": env("THROTTLE_CLIENT_PUBLIC", default="30/min"),
        "client_standard": env("THROTTLE_CLIENT_STANDARD", default="120/min"),
        "client_trusted": env("THROTTLE_CLIENT_TRUSTED", default="600/min"),
        'booking_submit': env('THROTTLE_BOOKING_SUBMIT', default='10/hour'),
        "membership_request": env("THROTTLE_MEMBERSHIP_REQUEST", default="10/hour"),
        "presence_start": env("THROTTLE_PRESENCE_START", default="10/hour"),
        # A presigned upload can be requested and never attached, stranding an object
        # that no row names and no quota counts. Generous for the real workflow -- an
        # avatar plus a handful of project images -- and a hard ceiling on how much one
        # member can strand. See `makerspaces.throttles.MemberImagePresignThrottle`.
        "member_image_presign": env("THROTTLE_MEMBER_IMAGE_PRESIGN", default="20/hour"),
        "data_export_create": env("THROTTLE_DATA_EXPORT_CREATE", default="3/hour"),
        "tenant_migration_read": env(
            "THROTTLE_TENANT_MIGRATION_READ", default="120/min"
        ),
        "tenant_migration_write": env(
            "THROTTLE_TENANT_MIGRATION_WRITE", default="30/hour"
        ),
        "tenant_migration_upload": env(
            "THROTTLE_TENANT_MIGRATION_UPLOAD", default="1200/min"
        ),
        # --- release 2 lane L1: event short-link resolution (/e/<code>) ---
        "event_short_link": env("THROTTLE_EVENT_SHORT_LINK", default="30/min"),
        # --- release 2 lane S0: login security (codes, passkeys, alert links) ---
        "login_code_resend": env("THROTTLE_LOGIN_CODE_RESEND", default="5/hour"),
        "login_code_ip": env("THROTTLE_LOGIN_CODE_IP", default="30/hour"),
        "passkey_options": env("THROTTLE_PASSKEY_OPTIONS", default="30/min"),
        "passkey_verify": env("THROTTLE_PASSKEY_VERIFY", default="10/min"),
        "security_alert_action": env("THROTTLE_SECURITY_ALERT_ACTION", default="10/hour"),
        # --- release 2 lane U-C: account merge (start/resend, proofs/preview/confirm) ---
        "account_merge_start": env("THROTTLE_ACCOUNT_MERGE_START", default="10/hour"),
        "account_merge_prove": env("THROTTLE_ACCOUNT_MERGE_PROVE", default="30/hour"),
    },
    # Proxy-aware client IP for throttling. Production must declare its topology at
    # settings import above; direct DEBUG development defaults to zero trusted proxies.
    # A positive count selects the Nth-from-last XFF entry appended by trusted proxies.
    "NUM_PROXIES": TRUSTED_PROXY_COUNT,
    "URL_FORMAT_OVERRIDE": None,
}
