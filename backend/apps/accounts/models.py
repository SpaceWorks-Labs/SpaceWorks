from django.db import models
from .models_user import User

# MERGE-RECON(A): move these O lifecycle fields into models_user with forward guards.
# Contribute to T's concrete model; defining a second User would lose kind constraints.
for _field_name in ("deletion_requested_at", "deletion_purge_after", "purge_started_at",
                    "account_restored_at", "account_purged_at"):
    User.add_to_class(_field_name, models.DateTimeField(null=True, blank=True))
User.add_to_class("deletion_email_ciphertext", models.TextField(blank=True, default=""))
User.add_to_class("deletion_username", models.CharField(max_length=150, blank=True, default=""))



from apps.accounts.models_email import EmailVerificationChallenge, DailyOtpEmailCounter  # noqa: E402

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
from apps.accounts.models_attestation import PlatformAttestationSettings  # noqa: E402
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

__all__ = [
    'DeviceActivityDay',
    'AttestationVerificationLog',

    'ReauthenticationSession',
    'UserMFA',
    'MFAChallenge',
    'StaffInvitation',
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
    'PlatformAttestationSettings',
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

from apps.accounts.models_account_purge import (  # noqa: E402
    AccountPurgeProgress, AccountPurgeObject, AppleRefreshCredential, AppleRevocation,
)
__all__ += ["AccountPurgeProgress", "AccountPurgeObject", "AppleRefreshCredential", "AppleRevocation"]

from apps.accounts.models_account_restore import AccountRestoreIntent  # noqa: E402
__all__ += ["AccountRestoreIntent"]
from .models_activity import DeviceActivityDay, AttestationVerificationLog  # noqa: F401
