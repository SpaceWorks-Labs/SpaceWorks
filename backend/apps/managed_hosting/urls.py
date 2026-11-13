"""Managed-hosting routes (#187A). Mounted at api/v1/admin/ and api/v1/managed-hosting/;
every view answers 404 while MANAGED_PLANS_ENABLED is off."""

from django.urls import path

from .views_platform import (
    BillingSettingsView, InvoiceListCreateView, InvoicePaymentView, InvoiceVoidView, PlanDetailView,
    PlanListCreateView, SpacePlanView, BulkPlanAssignView,
)
from .views_allowances import StaffAllowancesView
from .views_hosting_type import SpaceHostingTypeView
from .views_limits import RequestRateDetailView, RequestRatesView, SpaceLimitsView
from .views_switch import HostingSwitchView
from .views_limits_bulk import BulkSpaceLimitsView
from .views_limit_defaults import PlatformLimitDefaultsView, SpaceLimitsUsageView
from .views_space import (
    RazorpayHostingCallbackView, SpaceInvoiceCheckoutView, SpaceInvoiceListView, SpacePlanUsageView,
    StripeHostingCallbackView,
)

admin_urlpatterns = [
    path("platform/spaces/<int:makerspace_id>/limits", SpaceLimitsView.as_view(), name="admin-space-limits"),
    path("platform/spaces/<int:makerspace_id>/hosting-type", SpaceHostingTypeView.as_view(),
         name="admin-space-hosting-type"),
    path("platform/request-limits", RequestRatesView.as_view(), name="admin-platform-request-limits"),
    path("platform/request-limits/<str:scope>", RequestRateDetailView.as_view(),
         name="admin-platform-request-limit"),
    path("platform/limit-defaults", PlatformLimitDefaultsView.as_view(), name="admin-platform-limit-defaults"),
    path("platform/hosting-switch", HostingSwitchView.as_view(), name="admin-platform-hosting-switch"),
    path("platform/hosting-plans", PlanListCreateView.as_view(), name="admin-platform-hosting-plans"),
    path("platform/hosting-plans/<int:pk>", PlanDetailView.as_view(), name="admin-platform-hosting-plan"),
    path("platform/spaces/limits-bulk", BulkSpaceLimitsView.as_view(), name="admin-platform-space-limits-bulk"),
    path("platform/spaces/plan-bulk", BulkPlanAssignView.as_view(), name="admin-platform-space-plan-bulk"),
    path("platform/spaces/<int:makerspace_id>/plan", SpacePlanView.as_view(), name="admin-space-plan"),
    path("platform/hosting-invoices", InvoiceListCreateView.as_view(), name="admin-platform-hosting-invoices"),
    path("platform/hosting-invoices/<int:pk>/record-payment", InvoicePaymentView.as_view(),
         name="admin-platform-hosting-invoice-payment"),
    path("platform/hosting-invoices/<int:pk>/void", InvoiceVoidView.as_view(),
         name="admin-platform-hosting-invoice-void"),
    path("platform/hosting-billing-settings", BillingSettingsView.as_view(),
         name="admin-platform-hosting-billing-settings"),
    # #234 addendum 3(a): not switch-gated -- with hosting off it answers 200 with no rows.
    path("makerspace/<int:makerspace_id>/allowances", StaffAllowancesView.as_view(),
         name="admin-makerspace-allowances"),
    path("makerspace/<int:makerspace_id>/limits", SpaceLimitsUsageView.as_view(), name="admin-makerspace-limits"),
    path("makerspace/<int:makerspace_id>/hosting-plan", SpacePlanUsageView.as_view(),
         name="admin-makerspace-hosting-plan"),
    path("makerspace/<int:makerspace_id>/hosting-invoices", SpaceInvoiceListView.as_view(),
         name="admin-makerspace-hosting-invoices"),
    path("makerspace/<int:makerspace_id>/hosting-invoices/<int:invoice_id>/checkout",
         SpaceInvoiceCheckoutView.as_view(), name="admin-makerspace-hosting-invoice-checkout"),
]

webhook_urlpatterns = [
    path("webhooks/stripe", StripeHostingCallbackView.as_view(), name="managed-hosting-stripe-webhook"),
    path("webhooks/razorpay", RazorpayHostingCallbackView.as_view(), name="managed-hosting-razorpay-webhook"),
]
