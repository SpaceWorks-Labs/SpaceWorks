from django.urls import path

from apps.accounts.views_mfa import (
    MFAConfirmView, MFADisableView, MFAEnrollmentView, MFARecoveryView, MFAStatusView, MFAVerifyView,
)
from apps.accounts.views_reauthentication import (
    ReauthenticationView, ReauthenticationSocialStartView, ReauthenticationSocialCompleteView,
    ReauthenticationEnrollmentEmailView, ReauthenticationEnrollmentConfirmView,
    ReauthenticationSocialFactorView, ReauthenticationPhoneStartView, ReauthenticationPhoneConfirmView,
)
from apps.accounts.passkeys.urls import urlpatterns as passkey_urlpatterns
from apps.accounts.views_mfa_reset import StaffMfaResetView
from apps.accounts.views_staff_invitations import (
    StaffInvitationAcceptView, StaffInvitationListView, StaffInvitationResendView, StaffInvitationRevokeView,
)

auth_urlpatterns = [
    path("reauth", ReauthenticationView.as_view(), name="auth-reauth"),
    path("reauth/social/start", ReauthenticationSocialStartView.as_view(), name="auth-reauth-social-start"),
    path("reauth/social/complete", ReauthenticationSocialCompleteView.as_view(), name="auth-reauth-social-complete"),
    path("reauth/social/factor", ReauthenticationSocialFactorView.as_view(), name="auth-reauth-social-factor"),
    path("reauth/phone/start", ReauthenticationPhoneStartView.as_view(), name="auth-reauth-phone-start"),
    path("reauth/phone/confirm", ReauthenticationPhoneConfirmView.as_view(), name="auth-reauth-phone-confirm"),
    path("reauth/enrollment/email", ReauthenticationEnrollmentEmailView.as_view(), name="auth-reauth-enrollment-email"),
    path("reauth/enrollment/confirm", ReauthenticationEnrollmentConfirmView.as_view(), name="auth-reauth-enrollment-confirm"),
    path("mfa", MFAStatusView.as_view(), name="auth-mfa"),
    path("mfa/enroll", MFAEnrollmentView.as_view(), name="auth-mfa-enroll"),
    path("mfa/confirm", MFAConfirmView.as_view(), name="auth-mfa-confirm"),
    path("mfa/verify", MFAVerifyView.as_view(), name="auth-mfa-verify"),
    path("mfa/recovery", MFARecoveryView.as_view(), name="auth-mfa-recovery"),
    path("mfa/disable", MFADisableView.as_view(), name="auth-mfa-disable"),
    path("staff-invitations/accept", StaffInvitationAcceptView.as_view(), name="auth-staff-invitation-accept"),
    *passkey_urlpatterns,
]

admin_urlpatterns = [
    path("makerspaces/<int:makerspace_id>/staff-invitations", StaffInvitationListView.as_view(), name="admin-staff-invitations"),
    path("makerspaces/<int:makerspace_id>/staff-invitations/<int:invitation_id>/revoke", StaffInvitationRevokeView.as_view(), name="admin-staff-invitation-revoke"),
    path("makerspaces/<int:makerspace_id>/staff-invitations/<int:invitation_id>/resend", StaffInvitationResendView.as_view(), name="admin-staff-invitation-resend"),
    # S-A: the MFA-reset rule (U-A1 fixed the name; U-B's staff-roles API owns the rest).
    path("makerspaces/<int:makerspace_id>/staff-roles/<int:membership_id>/mfa-reset", StaffMfaResetView.as_view(),
         name="admin-staff-roles-mfa-reset"),
]
