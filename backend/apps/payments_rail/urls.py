"""Staff surfaces that talk to a payment provider. Withdrawn by a rail tombstone.

A refund is provider I/O: without the rail there is no vendor to send money back
through, so the route would answer only to fail.
"""

from django.urls import path

from apps.payments.views_refunds import PaymentRefundView
from apps.payments_rail.views_pay_link_checkout import PublicPayLinkCheckoutView

urlpatterns = [
    path(
        "admin/makerspace/<int:makerspace_id>/payments/<int:payment_id>/refund",
        PaymentRefundView.as_view(),
        name="payment-reconciliation-refund",
    ),
    # Lane L5 (X19): an account-less payer pays a pay link's charge online.
    path("public/pay/<str:token>/checkout", PublicPayLinkCheckoutView.as_view(), name="pay-link-checkout"),
]
