from django.urls import path
from apps.accounts.views_browser_state import BrowserStateView

from apps.accounts.views import (
    ChangePasswordView,
    ForgotPasswordView,
    LoginView,
    LogoutView,
    MeView,
    RefreshView,
    ResetPasswordConfirmView,
)
from apps.accounts.views_registration import (
    EmailVerificationConfirmView,
    EmailVerificationResendView,
    MemberSignUpView,
)
from apps.accounts.views_device import (
    DeviceAttestationChallengeView,
    DeviceGrantDetailView,
    DeviceGrantListView,
    DeviceLoginView,
    DeviceLogoutView,
    DeviceRefreshView,
)
from apps.accounts.views_phone import (
    PhoneLinkConfirmView,
    PhoneLinkStartView,
    PhoneLoginConfirmView,
    PhoneLoginStartView,
    PhoneUnlinkView,
)
from apps.accounts.views_social import (
    AppleSocialLoginView,
    OidcSocialLoginView,
    GoogleSocialLoginView,
    SocialNonceView,
    SocialProviderDetailView,
    SocialProviderListLinkView,
)
from apps.accounts.views_oidc_browser import (
    OidcBrowserCallbackView,
    OidcBrowserStartView,
)
from apps.accounts.views_claim import ClaimRedemptionView
from apps.accounts.views_device_staff import DeviceStaffGrantView
from apps.accounts.views_device_event import DeviceEventGrantView
from apps.accounts.views_logout_all import LogoutAllView
from apps.accounts.views_account_deletion import AccountDeletionView
from apps.accounts.views_account_restore import (
    AccountRestoreEmailView, AccountRestorePhoneView, AccountRestoreSocialStartView, AccountRestoreSocialCompleteView,
)
from apps.accounts.views_github import GithubBrowserCallbackView, GithubBrowserStartView
from apps.accounts.views_social_link_browser import GithubLinkStartView, OidcLinkStartView, SocialLinkCallbackView
from apps.organizations.views_redeem import OrganizationInvitationRedeemView
from apps.organizations.views_self_service import OrganizationSelfServiceView

from apps.accounts.urls_security import auth_urlpatterns
from apps.accounts.urls_account_merge import account_merge_urlpatterns

urlpatterns = [
    path("account/restore/email", AccountRestoreEmailView.as_view(), name="auth-account-restore-email"),
    path("account/restore/phone", AccountRestorePhoneView.as_view(), name="auth-account-restore-phone"),
    path("account/restore/social/start", AccountRestoreSocialStartView.as_view(), name="auth-account-restore-social-start"),
    path("account/restore/social/complete", AccountRestoreSocialCompleteView.as_view(), name="auth-account-restore-social-complete"),
    path("account/deletion", AccountDeletionView.as_view(), name="auth-account-deletion"),
    path("organizations/self-service/", OrganizationSelfServiceView.as_view(), name="auth-organizations-self-service"),
    *auth_urlpatterns,
    *account_merge_urlpatterns,
    path("social/nonce", SocialNonceView.as_view(), name="social-nonce"),
    path("social/google", GoogleSocialLoginView.as_view(), name="social-google"),
    path("social/apple", AppleSocialLoginView.as_view(), name="social-apple"),
    path("social/github/authorize", GithubBrowserStartView.as_view(), name="social-github-browser-start"),
    path("social/github/callback", GithubBrowserCallbackView.as_view(), name="social-github-browser-callback"),
    # Linking from a signed-in session: session-bound attempts that never mint a session.
    path("social/github/link/authorize", GithubLinkStartView.as_view(), name="social-github-link-start"),
    path("social/oidc/<slug:slug>/link/authorize", OidcLinkStartView.as_view(), name="social-oidc-link-start"),
    path("social/link/callback", SocialLinkCallbackView.as_view(), name="social-link-callback"),
    path(
        "social/oidc/callback",
        OidcBrowserCallbackView.as_view(),
        name="social-oidc-browser-callback",
    ),
    path(
        "social/oidc/<slug:slug>/authorize",
        OidcBrowserStartView.as_view(),
        name="social-oidc-browser-start",
    ),
    # Declared before the `<str:provider>` detail route below only by accident of prefix
    # ("social/oidc/..." vs "social/providers/..."), but kept adjacent to its siblings.
    path("social/oidc/<slug:slug>", OidcSocialLoginView.as_view(), name="social-oidc"),
    path("social/providers", SocialProviderListLinkView.as_view(), name="social-providers"),
    path("social/providers/<str:provider>", SocialProviderDetailView.as_view(), name="social-provider-detail"),
    path("device/attestation-challenge", DeviceAttestationChallengeView.as_view(), name="device-attestation-challenge"),
    path("device/login", DeviceLoginView.as_view(), name="device-login"),
    path("device/refresh", DeviceRefreshView.as_view(), name="device-refresh"),
    path("device/logout", DeviceLogoutView.as_view(), name="device-logout"),
    path("device/staff-grant", DeviceStaffGrantView.as_view(), name="device-staff-grant"),
    path("device/event-grant", DeviceEventGrantView.as_view(), name="device-event-grant"),
    path("device/grants", DeviceGrantListView.as_view(), name="device-grants"),
    path("device/grants/<uuid:grant_id>", DeviceGrantDetailView.as_view(), name="device-grant-detail"),
    path("phone/login/start", PhoneLoginStartView.as_view(), name="auth-phone-login-start"),
    path("phone/login/confirm", PhoneLoginConfirmView.as_view(), name="auth-phone-login-confirm"),
    path("phone/link/start", PhoneLinkStartView.as_view(), name="auth-phone-link-start"),
    path("phone/link/confirm", PhoneLinkConfirmView.as_view(), name="auth-phone-link-confirm"),
    path("phone", PhoneUnlinkView.as_view(), name="auth-phone-unlink"),
    path("login", LoginView.as_view(), name="auth-login"),
    path("claim/redeem", ClaimRedemptionView.as_view(), name="auth-claim-redeem"),
    path(
        "organization-invitations/redeem/",
        OrganizationInvitationRedeemView.as_view(),
        name="auth-organization-invitation-redeem",
    ),
    path("refresh", RefreshView.as_view(), name="auth-refresh"),
    path("browser-state", BrowserStateView.as_view(), name="auth-browser-state"),
    path("logout", LogoutView.as_view(), name="auth-logout"),
    path("logout-all", LogoutAllView.as_view(), name="auth-logout-all"),
    path("me", MeView.as_view(), name="auth-me"),
    path("change-password", ChangePasswordView.as_view(), name="auth-change-password"),
    path("forgot-password", ForgotPasswordView.as_view(), name="auth-forgot-password"),
    path("reset-password", ResetPasswordConfirmView.as_view(), name="auth-reset-password"),
    path("member-sign-up", MemberSignUpView.as_view(), name="auth-member-sign-up"),
    path("email-verification/resend", EmailVerificationResendView.as_view(), name="auth-email-verification-resend"),
    path("email-verification/confirm", EmailVerificationConfirmView.as_view(), name="auth-email-verification-confirm"),
]
