from .models_user import User



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

from .saved_details.models import (
    AccountSavedDetailsExportJob, MemberSavedAsset, MemberSavedDetail,
    SavedDetailCommandReceipt, SavedDetailsObjectCleanup, SavedDetailUpdateIntent,
)

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
from .models_pii_access import PlatformPiiAccessGrant  # noqa: E402,F401
__all__ += ["PlatformPiiAccessGrant"]

from apps.accounts.models_account_merge import AccountMergeIntent, AccountMergeRecord  # noqa: E402
__all__ += ["AccountMergeIntent", "AccountMergeRecord"]

from apps.accounts.models_webauthn import WebAuthnCeremony, WebAuthnCredential  # noqa: E402
from apps.accounts.models_mfa_grace import StaffMfaGrace  # noqa: E402
from apps.accounts.models_login_risk import KnownDevice, KnownNetwork, SecurityAlert  # noqa: E402
from apps.accounts.models_ip_access import IPAccessRule, IPAutoBlock  # noqa: E402
__all__ += [
    "WebAuthnCeremony", "WebAuthnCredential", "StaffMfaGrace", "KnownDevice", "KnownNetwork",
    "SecurityAlert", "IPAccessRule", "IPAutoBlock",
]
