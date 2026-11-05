"""Managed-hosting routes (#187A). Mounted at api/v1/admin/ and api/v1/managed-hosting/;
every view answers 404 while MANAGED_PLANS_ENABLED is off."""

from django.urls import path

from .views_platform import (
    BillingSettingsView, InvoiceListCreateView, InvoicePaymentView, InvoiceVoidView, PlanDetailView,
    PlanListCreateView, SpacePlanView,
)
from .views_space import (
    RazorpayHostingCallbackView, SpaceInvoiceCheckoutView, SpaceInvoiceListView, SpacePlanUsageView,
    StripeHostingCallbackView,
)

admin_urlpatterns = [
    path("platform/hosting-plans", PlanListCreateView.as_view(), name="admin-platform-hosting-plans"),
    path("platform/hosting-plans/<int:pk>", PlanDetailView.as_view(), name="admin-platform-hosting-plan"),
    path("platform/spaces/<int:makerspace_id>/plan", SpacePlanView.as_view(), name="admin-space-plan"),
    path("platform/hosting-invoices", InvoiceListCreateView.as_view(), name="admin-platform-hosting-invoices"),
    path("platform/hosting-invoices/<int:pk>/record-payment", InvoicePaymentView.as_view(),
         name="admin-platform-hosting-invoice-payment"),
    path("platform/hosting-invoices/<int:pk>/void", InvoiceVoidView.as_view(),
         name="admin-platform-hosting-invoice-void"),
    path("platform/hosting-billing-settings", BillingSettingsView.as_view(),
         name="admin-platform-hosting-billing-settings"),
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
