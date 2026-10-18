from django.db import models
from .models_user import User


class EmailVerificationChallenge(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="email_challenges"
    )
    email = models.CharField(max_length=254)
    code_digest = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "email", "expires_at"]),
            models.Index(
                fields=["user", "email"],
                condition=models.Q(consumed_at__isnull=True),
                name="email_challenge_active_idx",
            ),
        ]

    def is_usable(self, now):
        return (
            self.consumed_at is None
            and self.failed_attempts < 5
            and self.expires_at > now
        )


class DailyOtpEmailCounter(models.Model):
    day = models.DateField(unique=True)
    count = models.PositiveIntegerField(default=0)


from apps.accounts.models_devices import (  # noqa: E402
    DeviceAttestationChallenge,
    DeviceEnvironment,
    DeviceGrant,
    DevicePlatform,
    DeviceRefreshFamily,
    DeviceRefreshToken,
    NativeAppRegistration,
)
from apps.accounts.models_login_methods import PlatformLoginMethods  # noqa: E402
from apps.accounts.models_claim import MemberClaimCode  # noqa: E402
from apps.accounts.models_oidc_browser import OidcBrowserAttempt  # noqa: E402
from apps.accounts.models_phone import (  # noqa: E402
    PhoneChallengePurpose,
    PhoneVerificationChallenge,
)
from apps.accounts.models_password_reset import (  # noqa: E402
    PasswordResetEnvelope,
    PasswordResetEnvelopeStatus,
)
from apps.accounts.models_social import (  # noqa: E402
    PlatformSocialAuthSettings,
    SocialClientPlatform,
    SocialDelivery,
    SocialIdentity,
    SocialLoginNonce,
    SocialProvider,
    SocialSurface,
)

from apps.accounts.models_mfa import UserMFA, MFAChallenge  # noqa: E402
from apps.accounts.models_reauthentication import ReauthenticationSession  # noqa: E402
from apps.accounts.models_staff_invitations import StaffInvitation  # noqa: E402

from .saved_details.models import (
    AccountSavedDetailsExportJob, MemberSavedAsset, MemberSavedDetail,
    SavedDetailCommandReceipt, SavedDetailsObjectCleanup, SavedDetailUpdateIntent,
)

__all__ = [
    'ReauthenticationSession',
    'UserMFA',
    'MFAChallenge',
    'StaffInvitation',
    "UserMFA", "MFAChallenge", "StaffInvitation",
    'DailyOtpEmailCounter',
    'DeviceAttestationChallenge',
    'DeviceEnvironment',
    'DeviceGrant',
    'DevicePlatform',
    'DeviceRefreshFamily',
    'DeviceRefreshToken',
    'EmailVerificationChallenge',
    'MemberClaimCode',
    'NativeAppRegistration',
    'OidcBrowserAttempt',
    'PhoneChallengePurpose',
    'PhoneVerificationChallenge',
    'PasswordResetEnvelope',
    'PasswordResetEnvelopeStatus',
    'PlatformLoginMethods',
    'PlatformSocialAuthSettings',
    'SocialClientPlatform',
    'SocialDelivery',
    'SocialIdentity',
    'SocialLoginNonce',
    'SocialProvider',
    'SocialSurface',
    'User',
]
