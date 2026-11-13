"""Decision 242: the own-area Payments queue routes."""

from django.urls import path

from apps.payments.views_area_queue import (
    AreaClaimConfirmView, AreaClaimListView, AreaClaimRejectView, AreaPayLinkView, AreaQueueListView,
    AreaQueueSummaryView, AreaReminderView,
)

_SPACE = "admin/makerspace/<int:makerspace_id>/payments"

AREA_QUEUE_PATTERNS = [
    path(f"{_SPACE}/area-queue", AreaQueueListView.as_view(), name="payment-area-queue"),
    path(f"{_SPACE}/area-queue/summary", AreaQueueSummaryView.as_view(), name="payment-area-queue-summary"),
    path(f"{_SPACE}/area-queue/claims", AreaClaimListView.as_view(), name="payment-area-claims"),
    path(f"{_SPACE}/area-queue/claims/<int:claim_id>/confirm", AreaClaimConfirmView.as_view(),
         name="payment-area-claim-confirm"),
    path(f"{_SPACE}/area-queue/claims/<int:claim_id>/reject", AreaClaimRejectView.as_view(),
         name="payment-area-claim-reject"),
    path(f"{_SPACE}/<int:payment_id>/area-pay-link", AreaPayLinkView.as_view(), name="payment-area-pay-link"),
    path(f"{_SPACE}/<int:payment_id>/area-reminder", AreaReminderView.as_view(), name="payment-area-reminder"),
]
