from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.admin_api.views_hosting import TlsCheckView
from apps.data_export.views import DataExportDownloadView
from apps.backup.views_archives import BackupArchiveDownloadView
from apps.backup.views_recovery import RecoveryStateView
from apps.payments.views import RazorpayWebhookView, StripeWebhookView
from apps.payments_rail.views_connect import (
    StripeConnectCallbackView,
    StripeConnectWebhookView,
)
from apps.separability.registry import runtime_active
from django.conf import settings
from config.cloud_settings.urls import free_tick_paths


def separable_paths(app_label, *routes):
    """Already-built paths for a separable app, kept in place while it is active.

    The `separable` helper below takes a urlconf module to include; these three Stripe
    routes are declared inline because they are single views rather than an app urlconf,
    so they need the same gate in a different shape.
    """
    return list(routes) if runtime_active(app_label) else []


def separable(app_label, route, urlconf, **kwargs):
    """Routes for a separable app, spliced in place -- empty while it is tombstoned.

    Returns a list so call sites can `*`-unpack it and keep the entry at its original
    position: URL resolution is order-sensitive, and appending conditional routes at
    the end of the list would change which pattern wins.

    `include()` is called only when the app is active, deliberately. A tombstoned app
    may have had its views deleted (`apps/printing` and `apps/roadmap` are the
    precedent), and importing its urlconf to then discard it would crash on exactly
    the deployments this exists to support.
    """
    return [path(route, include(urlconf), **kwargs)] if runtime_active(app_label) else []


def docs_root(_request):
    return HttpResponse(
        """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Space Works API</title>
    <script>
      window.location.replace(window.location.hash ? "/redoc/" : "/docs/");
    </script>
    <noscript>
      <meta http-equiv="refresh" content="0; url=/docs/">
      <a href="/docs/">Open Swagger UI</a>
      <a href="/redoc/">Open Redoc</a>
    </noscript>
  </head>
  <body></body>
</html>""",
        content_type="text/html",
    )


from apps.accounts.views_mobile_associations import AssetLinksView, AppleAppSiteAssociationView
from apps.accounts.control_mfa import control_mfa
from apps.accounts.reauthentication_control import control_reauthentication
from apps.operations.control_storage import control_storage

urlpatterns = [
    path(".well-known/assetlinks.json", AssetLinksView.as_view(), name="mobile-assetlinks"),
    path(".well-known/apple-app-site-association", AppleAppSiteAssociationView.as_view(), name="mobile-apple-association"),
    path("", include("apps.makerspaces.public_page_share_urls")),
    *free_tick_paths(settings.SPACEWORKS_DEPLOYMENT_PROFILE),
    path("mfa/reauth/", control_reauthentication, name="control-reauthentication"),
    path("", include("apps.makerspaces.website_urls")),
    *separable("events", "", "apps.events.urls_embed"),  # release 2 L1: framable event card
    path("mfa/control/", control_mfa, name="control-mfa"),
    path(
        "api/v1/backups/download/<uuid:archive_id>/<str:token>",
        BackupArchiveDownloadView.as_view(),
        name="backup-archive-download",
    ),
    path(
        "api/v1/recovery",
        RecoveryStateView.as_view(),
        name="backup-recovery-state",
    ),
    path(
        "api/v1/data-exports/download/<uuid:job_id>/<str:token>",
        DataExportDownloadView.as_view(),
        name="data-export-download",
    ),
    # Spliced, not appended: a deployment that ships no payment surfaces must not answer
    # on the Stripe webhook either. An endpoint that accepts and verifies a charge for an
    # app whose console is gone would settle money nobody can see or reconcile.
    *separable_paths(
        "payments_rail",
        path(
            "api/v1/webhooks/stripe/connect",
            StripeConnectWebhookView.as_view(),
            name="stripe-connect-webhook",
        ),
        path(
            "api/v1/payments/connect/callback",
            StripeConnectCallbackView.as_view(),
            name="stripe-connect-callback",
        ),
        path(
            "api/v1/webhooks/stripe/<str:public_code>",
            StripeWebhookView.as_view(),
            name="stripe-webhook",
        ),
        path(
            "api/v1/webhooks/razorpay/<str:public_code>",
            RazorpayWebhookView.as_view(),
            name="razorpay-webhook",
        ),
    ),
    path('api/v1/', include('apps.machines.urls')),
    path(
        "api/v1/public/organizations/",
        include("apps.organizations.urls_public"),
    ),
    path("api/v1/public/hosting/", include("apps.hosting_requests.urls_public")),
    *separable("events", "api/v1/public/", "apps.events.urls_public"),
    *separable("events", "api/v1/", "apps.events.urls_programme"),
    path("api/v1/", include("apps.accounts.urls_programme")),
    *separable("events", "api/v1/events/", "apps.events.urls_integration"),
    *separable("bookings", "api/v1/public/", "apps.bookings.urls_public"),
    *separable("bookings", "api/v1/booking-integration/", "apps.bookings.urls_integration"),
    *separable("presence", "api/v1/public/", "apps.presence.urls"),
    # The LEDGER is unconditional: money owed, its receipts and its reconciliation
    # outlive any decision about shipping a provider integration.
    path("api/v1/", include("apps.payments.urls")),
    *separable("payments_rail", "api/v1/", "apps.payments_rail.urls"),
    path(
        "api/v1/internal/tls-check",
        TlsCheckView.as_view(),
        name="internal-tls-check",
    ),
    path("", docs_root, name="docs-root"),
    # Mounted at /control/ (not /admin/) so it never collides with the React staff
    # console, which owns /admin on the SPA. The Django admin is the Super Admin
    # control plane and lives on its own dedicated prefix.
    path("control/storage/", admin.site.admin_view(control_storage), name="control-storage"),
    path("control/", admin.site.urls),
    path("api/", include("apps.inventory.urls")),          # existing, unchanged
    # Versioned alias of the public routes. Namespaced so it does NOT collide with the
    # unnamespaced names above — reverse("public-inventory") stays /api/public/...,
    # while /api/v1/public/... is reachable directly (and via "v1:public-inventory").
    path("api/v1/", include(("apps.inventory.urls", "inventory"), namespace="v1")),
    path("api/v1/", include("apps.makerspaces.urls")),
    path("api/v1/", include("apps.makerspaces.public_page_urls")),
    path("api/v1/admin/", include("apps.makerspaces.public_page_editor_urls")),
    path("api/v1/public/organizations/", include("apps.organizations.urls_public_page_collections")),
    *separable("events", "api/v1/", "apps.events.urls_public_codes"),
    path("api/v1/member/", include("apps.payments.urls_member")),
    # Core event-payout ledger: never module/rail/Events gated, so retained obligations
    # stay readable and settleable after the reimbursement add-on or Events is removed.
    path("api/v1/member/event-payouts/", include("apps.payments.event_payouts.urls_member")),
    path("api/v1/admin/makerspaces/<int:makerspace_id>/event-payouts/",
         include("apps.payments.event_payouts.urls_finance")),
    *separable("payments_rail", "api/v1/member/", "apps.payments_rail.urls_member"),
    path("api/v1/", include("apps.hardware_requests.urls")),
    path("api/v1/auth/", include("apps.accounts.urls")),   # staff auth surface
    path("api/v1/admin/", include("apps.admin_api.urls")),
    path("api/v1/admin/", include("apps.organizations.urls_admin")),
    path("api/v1/admin/", include("apps.hosting_requests.urls_staff")),
    # Release 2 L3: the shared card engine (designs, jobs, member-card extras).
    path("api/v1/admin/", include("apps.card_designs.urls_admin")),
    path("api/v1/member/", include("apps.card_designs.urls_member")),
    path("api/v1/public/", include("apps.card_designs.urls_public")),
    # Apple's pass web service: pass-token auth, outside the HMAC-protected public prefixes.
    path("api/v1/wallet/", include("apps.card_designs.urls_wallet")),
    *separable("id_programmes", "api/v1/admin/", "apps.id_programmes.urls_admin"),
    *separable("id_programmes", "api/v1/public/", "apps.id_programmes.urls_public"),
    *separable("id_programmes", "api/v1/member/", "apps.id_programmes.urls_member"),
    *separable("events", "api/v1/admin/", "apps.events.urls_id_cards"),
    *separable("events", "api/v1/member/", "apps.events.urls_id_cards_member"),
    # Mounted at admin_api's own prefix so the paths and route names are unchanged by
    # the relocation, and *after* it so a relocated route can never shadow one that
    # stayed behind. Every warranty pattern is a distinct literal, so ordering is
    # belt-and-braces rather than load-bearing.
    *separable("warranty", "api/v1/admin/", "apps.warranty.urls"),
    *separable("maintenance", "api/v1/admin/", "apps.maintenance.urls"),
    *separable("presence", "api/v1/admin/", "apps.presence.urls_admin"),
    *separable("events", "api/v1/admin/", "apps.events.urls_admin"),
    *separable("events", "api/v1/member/", "apps.events.urls_member"),
    # Reimbursement add-on: removable with its module, and withdrawn with Events.
    *separable("event_reimbursements", "api/v1/member/makerspaces/<int:makerspace_id>/events/<int:pk>/",
               "apps.event_reimbursements.urls_member"),
    *separable("event_reimbursements", "api/v1/admin/events/<int:pk>/", "apps.event_reimbursements.urls_admin"),
    *separable("events", "api/v1/", "apps.events.urls_station"),
    *separable("bookings", "api/v1/admin/", "apps.bookings.urls_admin"),
    # Staff device admin under api/v1/admin/ plus the signed device protocol under
    # api/v1/device/ (covered exactly by apps.devices.route_registry).
    *separable("devices", "api/v1/", "apps.devices.urls"),
    # Phase 9b kiosk Stations: admin lifecycle plus the Station-token session/lease.
    path("api/v1/", include("apps.makerspaces.station_urls")),
    path("api/v1/admin/", include("apps.boxes.urls")),
    path("api/v1/admin/", include("apps.evidence.urls")),
    path("api/v1/", include("apps.operations.urls")),
    path("api/v1/integrations/", include("apps.integrations.urls")),
    *separable("procurement", "api/v1/procurement/", "apps.procurement.urls"),
    *separable("notifications", "api/v1/notifications/", "apps.notifications.urls"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="api-redoc-ui",
    ),
    path(
        "docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

from apps.integrations.messaging.urls import member_urlpatterns as messaging_member_urls
from apps.integrations.messaging.urls import staff_urlpatterns as messaging_staff_urls
urlpatterns += [path("api/v1/", include(messaging_member_urls)), path("api/v1/admin/", include(messaging_staff_urls))]

urlpatterns += [path("api/v1/integrations/messaging/", include("apps.integrations.messaging.urls_webhooks"))]
