"""HTTPS, CSP, cookies and token settings."""

from config.settings_runtime import env, timedelta

# TLS-dependent hardening. Gated behind ENABLE_HTTPS (env), NOT DEBUG: the default
# Docker/prod compose serves plain HTTP and must not trust client-supplied forwarded
# proto headers. TLS overlays set TRUST_X_FORWARDED_PROTO=true only when a trusted
# reverse proxy is the sole path to the backend.
ENABLE_HTTPS = env.bool("ENABLE_HTTPS", default=False)
TRUST_X_FORWARDED_PROTO = env.bool("TRUST_X_FORWARDED_PROTO", default=False)
SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https") if TRUST_X_FORWARDED_PROTO else None
)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=ENABLE_HTTPS)
# Plain-HTTP callers INSIDE the deployment must not be bounced to https:// -- there is no
# TLS on the backend port, so the redirect is a failure, not an upgrade. These are the
# compose healthchecks (`urllib` follows the 301 onto a TLS-less port), Caddy's on-demand
# TLS ask (any non-200 means no certificate is ever issued for a custom domain) and a
# Prometheus scrape. A request that arrives through the TLS proxy is already secure
# (`TRUST_X_FORWARDED_PROTO`), so it was never redirected: the exemption changes the answer
# only for a caller that reached the plain backend port, which is exactly the internal one.
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/", r"^api/v1/internal/", r"^api/v1/metrics/$"]
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=ENABLE_HTTPS)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=ENABLE_HTTPS)
# Needed for admin/login POST when reached over HTTPS via a custom domain behind a
# proxy. Same-origin HTTP needs nothing here; set to the public https origin(s) when
# ENABLE_HTTPS is on, e.g. CSRF_TRUSTED_ORIGINS=https://makerspace.example.org
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
SECURE_HSTS_SECONDS = env.int(
    "SECURE_HSTS_SECONDS", default=31536000 if ENABLE_HTTPS else 0
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0

# Always-on, transport-independent headers.
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin"

# Permissive enough for the current admin and API docs; tighten per deployment later.
# drf-spectacular's Swagger UI / Redoc load their JS+CSS from the jsDelivr CDN, so the
# CDN is allowed for script/style/img/font; drop it (or adopt drf-spectacular-sidecar to
# serve the assets from 'self') once the docs UI is locally hosted.
_SWAGGER_CDN = "https://cdn.jsdelivr.net"
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        # 'wasm-unsafe-eval' lets the in-browser QR scanner instantiate the bundled
        # zxing-wasm reader (the camera fallback on browsers without a native
        # BarcodeDetector). It permits ONLY WebAssembly compilation, NOT arbitrary
        # JS eval, so it is far narrower than 'unsafe-eval'.
        "script-src": ["'self'", "'unsafe-inline'", "'wasm-unsafe-eval'", _SWAGGER_CDN],
        "style-src": ["'self'", "'unsafe-inline'", _SWAGGER_CDN],
        "img-src": ["'self'", "data:", _SWAGGER_CDN],
        "font-src": ["'self'", "data:", _SWAGGER_CDN],
        "worker-src": ["'self'", "blob:"],
    }
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": (
        "apps.accounts.tokens.SpaceWorksAccessToken",
        "apps.accounts.claim_tokens.ClaimAccessToken",
    ),
}

# Cross-site refresh cookie (frontends live on separate origins).
AUTH_REFRESH_COOKIE = "refresh_token"
# CSRF defense for the cookie-bearing endpoints (refresh/logout): the view requires
# this custom header to be PRESENT - a non-simple header forces a CORS preflight that
# an attacker's origin cannot pass - AND validates the Origin header against the
# allowlist (review fixes #1, #8). The header VALUE is not a secret; presence + Origin
# is the defense. This works cross-origin where a readable double-submit cookie cannot.
AUTH_REFRESH_CSRF_HEADER = "X-Refresh-CSRF"
AUTH_COOKIE_PATH = "/api/v1/auth/"
# SameSite=None REQUIRES Secure or browsers silently drop the cookie (review fix #2).
# Prod (separate origins over HTTPS): SAMESITE=None, SECURE=True.
# Local dev: serve the frontend through a same-origin Vite proxy to the API and set
# AUTH_COOKIE_SAMESITE=Lax + AUTH_COOKIE_SECURE=False via .env (see Step 3c note).
AUTH_COOKIE_SAMESITE = env("AUTH_COOKIE_SAMESITE", default="None")
AUTH_COOKIE_SECURE = env.bool("AUTH_COOKIE_SECURE", default=True)

# Native device routes are dormant until an exact app allowlist and both the selected
# provider verifier URL and bearer credential are configured. Verifiers must perform
# real Apple App Attest / Google Play Integrity validation and return bound claims.
DEVICE_ATTESTATION_APPS = env.json("DEVICE_ATTESTATION_APPS", default={})
DEVICE_ATTESTATION_DEV_INSECURE = env.bool("DEVICE_ATTESTATION_DEV_INSECURE", default=False)
DEVICE_APPLE_ATTESTATION_VERIFY_URL = env("DEVICE_APPLE_ATTESTATION_VERIFY_URL", default="")
DEVICE_APPLE_ATTESTATION_VERIFY_TOKEN = env("DEVICE_APPLE_ATTESTATION_VERIFY_TOKEN", default="")
DEVICE_ANDROID_ATTESTATION_VERIFY_URL = env("DEVICE_ANDROID_ATTESTATION_VERIFY_URL", default="")
DEVICE_ANDROID_ATTESTATION_VERIFY_TOKEN = env("DEVICE_ANDROID_ATTESTATION_VERIFY_TOKEN", default="")
DEVICE_ATTESTATION_CHALLENGE_TTL_SECONDS = env.int("DEVICE_ATTESTATION_CHALLENGE_TTL_SECONDS", default=180)
DEVICE_ATTESTATION_PROVIDER_TIMEOUT_SECONDS = env.int("DEVICE_ATTESTATION_PROVIDER_TIMEOUT_SECONDS", default=10)
PUSH_TOKEN_HMAC_KEY = env("PUSH_TOKEN_HMAC_KEY", default="")
SOCIAL_AUTH_NONCE_TTL_SECONDS = env.int("SOCIAL_AUTH_NONCE_TTL_SECONDS", default=300)
SOCIAL_AUTH_CLOCK_SKEW_SECONDS = env.int("SOCIAL_AUTH_CLOCK_SKEW_SECONDS", default=60)
SOCIAL_AUTH_JWKS_TIMEOUT_SECONDS = env.int("SOCIAL_AUTH_JWKS_TIMEOUT_SECONDS", default=5)
SOCIAL_AUTH_JWKS_CACHE_SECONDS = env.int("SOCIAL_AUTH_JWKS_CACHE_SECONDS", default=3600)
SOCIAL_AUTH_JWKS_MAX_BYTES = env.int("SOCIAL_AUTH_JWKS_MAX_BYTES", default=1048576)
OIDC_ATTEMPT_TTL_SECONDS = env.int("OIDC_ATTEMPT_TTL_SECONDS", default=300)
OIDC_HTTP_TIMEOUT_SECONDS = env.int("OIDC_HTTP_TIMEOUT_SECONDS", default=5)
OIDC_HTTP_MAX_BYTES = env.int("OIDC_HTTP_MAX_BYTES", default=65536)
OIDC_DISCOVERY_CACHE_SECONDS = env.int("OIDC_DISCOVERY_CACHE_SECONDS", default=300)
MEMBER_CLAIM_CODE_TTL_SECONDS = env.int(
    "MEMBER_CLAIM_CODE_TTL_SECONDS", default=15 * 60
)
MEMBER_CLAIM_SESSION_TTL_SECONDS = env.int(
    "MEMBER_CLAIM_SESSION_TTL_SECONDS", default=12 * 60 * 60
)
SOCIAL_GOOGLE_JWKS_URL = env("SOCIAL_GOOGLE_JWKS_URL", default="https://www.googleapis.com/oauth2/v3/certs")
SOCIAL_APPLE_JWKS_URL = env("SOCIAL_APPLE_JWKS_URL", default="https://appleid.apple.com/auth/keys")
