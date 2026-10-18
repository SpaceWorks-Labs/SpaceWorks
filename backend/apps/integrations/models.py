from .models_timing import NotificationTimingPolicy
from .notification_enums import (
    CHANNEL_MODULE_KEYS,
    ChatNotificationChannel,
    NonEmailNotificationChannel,
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationFeature,
)
from .models_email import (
    DailyEmailCounter,
    EmailLog,
    EmailNotificationMute,
    EmailTemplate,
    PlatformEmailSettings,
)
from .models_notifications import (
    DailyNotificationCounter,
    NotificationDeliveryLog,
    NotificationPreference,
)
from .models_chat_templates import ChatTemplate
from .models_machine_templates import MachineTypeEmailTemplate
from .models_destinations import (
    DestinationCategoryScope,
    DestinationMachineScope,
    DestinationMachineTypeScope,
    NotificationDestination,
)
from .models_push import PlatformPushSettings, PushDevice
from .models_suppression import EmailSuppression
from .models_recipients import (
    NotificationRecipient,
    NotificationRecipientKind,
    RecipientCategoryScope,
    RecipientMachineScope,
    RecipientMachineTypeScope,
)
from .models_sms import (
    DailyOtpSmsCounter,
    PlatformSmsSettings,
    SmsProviderChoice,
)

__all__ = [
    'SmsSendLog',
    'PushDeliveryAttempt',
    'EmailProviderEvent',

    'CHANNEL_MODULE_KEYS',
    'ChatNotificationChannel',
    'ChatTemplate',
    'DailyEmailCounter',
    'DailyNotificationCounter',
    'DailyOtpSmsCounter',
    'DestinationCategoryScope',
    'DestinationMachineScope',
    'DestinationMachineTypeScope',
    'EmailLog',
    'EmailSuppression',
    'EmailNotificationMute',
    'EmailTemplate',
    'MachineTypeEmailTemplate',
    'NonEmailNotificationChannel',
    'NotificationChannel',
    'NotificationDeliveryLog',
    'NotificationDeliveryStatus',
    'NotificationDestination',
    'NotificationFeature',
    'NotificationPreference',
    'NotificationTimingPolicy',
    'NotificationRecipient',
    'NotificationRecipientKind',
    'PlatformEmailSettings',
    'PlatformPushSettings',
    'RecipientCategoryScope',
    'RecipientMachineScope',
    'RecipientMachineTypeScope',
    'PlatformSmsSettings',
    'PushDevice',
    'SmsProviderChoice',
]

from .models_contract import NotificationDelivery, NotificationEnvelope
from .models_endpoints import ChannelConfiguration, NotificationEndpoint, NotificationEndpointChallenge, WhatsAppTemplate

__all__ += ["NotificationDelivery", "NotificationEnvelope", "ChannelConfiguration", "NotificationEndpoint",
            "NotificationEndpointChallenge", "WhatsAppTemplate"]
from .models_notification_media import NotificationMediaGrant

__all__ += ["NotificationMediaGrant"]
# MERGE-RECON(M): retain legacy messaging models until mapped history/ingress cutover.
from .models_tracking import SmsSendLog, PushDeliveryAttempt, EmailProviderEvent  # noqa: F401
from .models_messaging_settings import (
    PlatformWhatsAppSettings, MakerspaceMessagingSettings, MessagingSenderIdentity,
    MessagingSenderCredential, WhatsAppTemplateBinding,
)
from .models_messaging_consent import (
    MessagingConsent, MessagingSuppression, MessagingRecipientAlias, MessagingRecipientCorrelation,
)
from .models_messaging_delivery import MessagingDelivery, MessagingWebhookEvent

__all__ += ["PlatformWhatsAppSettings", "MakerspaceMessagingSettings", "MessagingSenderIdentity",
            "MessagingSenderCredential", "WhatsAppTemplateBinding", "MessagingConsent",
            "MessagingSuppression", "MessagingRecipientAlias", "MessagingRecipientCorrelation",
            "MessagingDelivery", "MessagingWebhookEvent"]
