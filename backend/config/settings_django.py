"""Django app, middleware, database and authentication configuration."""

from config.settings_runtime import (
    BASE_DIR, SPACEWORKS_DEPLOYMENT_MODE, SYSTEM_LOCALE, TRUSTED_PROXY_COUNT,
    django_languages, env, tombstoned_app_labels,
)

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "django.contrib.admin",
    "django.contrib.auth",
    "axes",
    "django.contrib.contenttypes",
    "django.contrib.postgres",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "storages",
    "apps.accounts",
    "apps.makerspaces",
    "apps.organizations",
    "apps.payments",
    # The provider rail's surfaces, separable from the ledger above.
    "apps.payments_rail",
    "apps.presence",
    "apps.encryption",
    "apps.apiclients",
    "apps.boxes",
    "apps.inventory",
    "apps.hardware_requests",
    "apps.printing",
    "apps.audit",
    "apps.evidence",
    "apps.warranty",
    "apps.admin_api",
    "apps.data_export",
    "apps.integrations",
    "apps.operations",
    "apps.procurement",
    "apps.notifications",
    "apps.backup",
    "apps.machines",
    "apps.events",
    "apps.event_reimbursements",
    "apps.bookings",
    "apps.maintenance",
    "apps.roadmap",
    "apps.tenant_migration",
    # Enrolled printers/label printers (phase 7a); separable.
    "apps.devices",
    # Managed-platform hosting requests; inert on self-host.
    "apps.hosting_requests",
    # Release 2 L3: the shared card engine (designs, rendering, jobs, verify, wallet); core.
    "apps.card_designs",
    # Release 2 L3: organisation ID programmes; separable, switched by membership.id_programmes.
    "apps.id_programmes",
    # Lane L8 (#75d/#120): the Postgres row-level-security backstop (core, never tombstoned).
    "apps.tenant_rls",
    # Release 2 L22: the per-space shop; separable, switched by the `shop` module key.
    "apps.shop",
    # Lane L25 (#163B): per-space read-only analytics logins and Metabase embedding.
    "apps.analytics",
    # #185: superadmin space controls (suspend, read-only, schedules, announcements); core.
    "apps.space_controls",
    # #187A: the managed-hosting limiter (plans, trials, hosting billing); OFF unless
    # MANAGED_PLANS_ENABLED, and then only on a managed deployment.
    "apps.managed_hosting",
    # Must stay LAST. Django calls ready() in this order, so being last is what
    # guarantees every other app has registered before finalize() freezes the
    # separability registries.
    "apps.separability",
]

# App labels whose runtime surfaces this deployment does not ship: no URLs, no admin
# registration, no sidebar entry, no OpenAPI paths. Rows and migrations are retained,
# and so is the retention registry, so nothing becomes unpurgeable or unencryptable.
# Deployment-scoped rather than per-tenant, because URL routing and the schema are
# process-global. App labels, not module keys -- one app can own several keys.
# A label naming a core module's app is refused at startup (separability.E007).
TOMBSTONED_APPS = tombstoned_app_labels()

MIDDLEWARE = [
    # The recovery gate stays FIRST -- it must refuse a request before any other layer
    # can act on it, and tests/backup/test_recovery_gate.py pins that position.
    "apps.backup.middleware.DeploymentRecoveryGateMiddleware",
    # Second, so it still wraps every view that could log a calendar-feed bearer token.
    "apps.events.middleware.CalendarFeedLogRedactionMiddleware",
    # Binds the per-request correlation id before any layer below can log. The two gates
    # above refuse without logging through it; that is the accepted cost of their position.
    "config.request_id.RequestIdMiddleware",
    # Phase 8 i18n: a fresh locale context per request, OUTSIDE every layer below that can
    # answer early, so no refusal inherits another request's locale (config/locale_context.py).
    "config.locale_context.LocaleContextResetMiddleware",
    # #189/#191: with CONTROL_PLANE_PROXY off, /control/ answers only the server and its
    # SSH tunnel; the public origin gets a plain 404 before any session or login layer runs.
    "config.control_plane_access.ControlPlaneReachMiddleware",
    # Clears the per-request native-session marker (accounts.native_session).
    "apps.accounts.native_session.NativeSessionContextMiddleware",
    "apps.tenant_migration.middleware.SourceMigrationGateMiddleware",
    "apps.makerspaces.middleware.TenantHostValidationMiddleware",
    "config.cloud_settings.forwarded_host.TrustedForwardedHostMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "apps.accounts.social_csp.SocialCspMiddleware",
    "csp.middleware.CSPMiddleware",
    "config.admin_access.AdminCspEvalMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # After sessions, before CommonMiddleware (Django's required placement); the explicit
    # X-SpaceWorks-Locale choice is re-applied right after it.
    "django.middleware.locale.LocaleMiddleware",
    "config.locale_context.ExplicitLocaleMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "apps.inventory.middleware.FrontendHMACMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "config.admin_access.AdminSuperuserOnlyMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Platform IP rules, automatic blocks and Turnstile on sign-in views only (S-C); before
    # axes so a refused request never reaches a credential check.
    "apps.accounts.ip_guard_middleware.LoginIPGuardMiddleware",
    "axes.middleware.AxesMiddleware",
    # Masks tenant PII for a superadmin inside a space's staff routes (owner decision #115).
    "apps.accounts.platform_tenant_pii.PlatformTenantPiiMiddleware",
    # Counts-only api_client channel analytics, on the way out (accounts/channel_middleware.py).
    "apps.accounts.channel_middleware.ChannelUsageMiddleware",
    # #185/#195: one request's superadmin admission to paused spaces (set after authentication).
    "apps.makerspaces.middleware.ServabilityScopeMiddleware",
    # --- lane L8: binds each request's RLS scope once its route is resolved; LAST so every
    # other layer's own lookups run unbound. Views still scope through rbac (backstop only).
    "apps.tenant_rls.middleware.TenantRlsBoundaryMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": env.db()}
# Persistent connections by default: gunicorn's worker processes otherwise open and close
# a Postgres connection per request. Transaction-mode poolers (Supabase :6543, PgBouncer)
# hand back a different server connection each time, so deployments on one set
# CONN_MAX_AGE=0 explicitly -- .env.production.example and docs/deploy-production.md do.
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = env.bool("CONN_HEALTH_CHECKS", default=True)
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = env.bool(
    "DISABLE_SERVER_SIDE_CURSORS", default=False
)
if SPACEWORKS_DEPLOYMENT_MODE == "managed":
    from config.cloud_settings.wiring import managed_database
    DATABASES["default"] = managed_database(DATABASES["default"], env)
SPACEWORKS_HOST_MARKER_PATH = env(
    "SPACEWORKS_HOST_MARKER_PATH",
    default="/run/spaceworks-host/restore-marker.json",
)
BACKUP_PRODUCER_CAPABILITY_MARKER_PATH = env(
    "BACKUP_PRODUCER_CAPABILITY_MARKER_PATH",
    default="/run/spaceworks-host/producer-capability.json",
)
BACKUP_PRODUCER_PRIVILEGED_SCRIPTS_DIR = env(
    "BACKUP_PRODUCER_PRIVILEGED_SCRIPTS_DIR",
    default="/run/spaceworks-privileged-scripts",
)
BACKUP_PRODUCER_ENTRYPOINT_PATH = env(
    "BACKUP_PRODUCER_ENTRYPOINT_PATH",
    default="/app/scripts/spaceworks_entrypoint.py",
)
BACKUP_PRODUCER_MIGRATIONS_DIR = env(
    "BACKUP_PRODUCER_MIGRATIONS_DIR",
    default=str(BASE_DIR / "apps"),
)

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
    # Last, so the cheap local checks run first: HIBP k-anonymity, fail-open (S-C).
    {
        "NAME": "apps.accounts.password_breach.BreachedPasswordValidator",
    },
]

# Phase 8 i18n: one code-defined locale registry (config/supported_locales.json), never an
# env read. English is the only catalogue; docs/i18n.md covers adding a language.
LANGUAGE_CODE = SYSTEM_LOCALE
LANGUAGES = django_languages()
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
ACCOUNT_DELETION_RETENTION_DAYS = env.int("ACCOUNT_DELETION_RETENTION_DAYS", default=90)
# PostgreSQL supports 63-character identifiers. The approved Maintenance schema
# intentionally uses a 32-character descriptive index name.
SILENCED_SYSTEM_CHECKS = ["models.E034"]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "apps.accounts.auth_backends.SpaceWorksModelBackend",
]

AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=5)
AXES_COOLOFF_TIME = 1
AXES_RESET_ON_SUCCESS = True
# Axes hooks Django's authenticate(), so it covers BOTH the admin session login and
# the SimpleJWT staff login (apps/accounts LoginView) - intentional brute-force lockout
# on top of that view's DRF rate throttle. The nested list makes the lockout key the
# COMBINATION of ip_address+username (AND), not either alone (OR): repeated failures
# against a known username from other IPs can't lock that account out (no username DoS).
AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"]]
AXES_ENABLED = env.bool("AXES_ENABLED", default=True)
# django-axes 8 names this setting AXES_IPWARE_PROXY_COUNT. Keep its declared
# topology tied to DRF's and use the shared resolver below so the two protections
# cannot interpret an X-Forwarded-For chain differently.
AXES_IPWARE_PROXY_COUNT = TRUSTED_PROXY_COUNT
AXES_CLIENT_IP_CALLABLE = "config.client_ip.get_throttle_client_ip"
# Only the platform superadmin's own username from an ALLOW-listed address is exempt (S-C).
AXES_WHITELIST_CALLABLE = "apps.accounts.ip_rules.axes_whitelisted"
