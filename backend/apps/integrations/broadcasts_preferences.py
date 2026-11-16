"""Saved category choices assign campaign email to the personal resolver."""


def has_personal_choice(makerspace, account, category):
    from .notification_resolution import policy_rows
    from apps.notifications.models_preferences import NotificationPreference
    return policy_rows(NotificationPreference, makerspace).filter(user=account, category=category).exists()
