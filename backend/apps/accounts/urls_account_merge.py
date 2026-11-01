"""``/api/v1/auth/account-merge/...`` (route names fixed in ``ACCOUNT_MERGE_ROUTES``)."""

from django.urls import path

from apps.accounts.views_account_merge import (
    AccountMergeCancelView, AccountMergeConfirmView, AccountMergePreviewView, AccountMergeProveView,
    AccountMergeResendView, AccountMergeStartView,
)

account_merge_urlpatterns = [
    path("account-merge/start", AccountMergeStartView.as_view(), name="auth-account-merge-start"),
    path("account-merge/<uuid:intent_id>/prove", AccountMergeProveView.as_view(), name="auth-account-merge-prove"),
    path("account-merge/<uuid:intent_id>/resend", AccountMergeResendView.as_view(), name="auth-account-merge-resend"),
    path("account-merge/<uuid:intent_id>/preview", AccountMergePreviewView.as_view(),
         name="auth-account-merge-preview"),
    path("account-merge/<uuid:intent_id>/confirm", AccountMergeConfirmView.as_view(),
         name="auth-account-merge-confirm"),
    path("account-merge/<uuid:intent_id>/cancel", AccountMergeCancelView.as_view(), name="auth-account-merge-cancel"),
]
