from django.urls import path

from apps.notifications.views import (
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
    NotificationUnreadCountView,
)

app_name = "notifications"

from .views_inbox import InboxFamiliesView, InboxListView, InboxReadAllView, InboxReadView, InboxUnreadView
from .views_inbox_snooze import InboxArchiveView, InboxRestoreView, InboxSnoozeView
from .views_browser_alerts import BrowserAlertKeyView, BrowserAlertSubscriptionView
from .views_browser_firebase import BrowserFirebaseBeginView, BrowserFirebaseConfirmView
from .views_browser_firebase_config import BrowserFirebaseConfigView
from .views_browser_firebase_resume import BrowserFirebaseResumeView
from .views_browser_firebase_global_resume import BrowserFirebaseGlobalResumeView
from .views_preferences import MemberPreferenceView, OneClickUnsubscribeView

from .views_broadcasts import BroadcastCreateView, AnnouncementFeedView

urlpatterns = [
    path("broadcasts/<int:makerspace_id>", BroadcastCreateView.as_view(), name="broadcast-create"),
    path("announcements/<int:makerspace_id>", AnnouncementFeedView.as_view(), name="announcement-feed"),
    path("inbox/<int:makerspace_id>", InboxListView.as_view(), name="inbox-list"),
    path("inbox/<int:makerspace_id>/families", InboxFamiliesView.as_view(), name="inbox-families"),
    path("inbox/<int:makerspace_id>/unread-count", InboxUnreadView.as_view(), name="inbox-count"),
    path("inbox/<int:makerspace_id>/read-all", InboxReadAllView.as_view(), name="inbox-read-all"),
    path("inbox/<int:makerspace_id>/<int:pk>/read", InboxReadView.as_view(), name="inbox-read"),
    path("inbox/<int:makerspace_id>/<int:pk>/snooze", InboxSnoozeView.as_view(), name="inbox-snooze"),
    path("inbox/<int:makerspace_id>/<int:pk>/archive", InboxArchiveView.as_view(), name="inbox-archive"),
    path("inbox/<int:makerspace_id>/<int:pk>/restore", InboxRestoreView.as_view(), name="inbox-restore"),
    path("browser-alerts/key", BrowserAlertKeyView.as_view(), name="browser-alert-key"),
    path("browser-firebase/may-resume", BrowserFirebaseGlobalResumeView.as_view(), name="browser-firebase-global-may-resume"),
    path("browser-firebase/<int:makerspace_id>/config", BrowserFirebaseConfigView.as_view(), name="browser-firebase-config"),
    path("browser-firebase/<int:makerspace_id>/may-resume", BrowserFirebaseResumeView.as_view(), name="browser-firebase-may-resume"),
    path("browser-firebase/<int:makerspace_id>/challenge", BrowserFirebaseBeginView.as_view(), name="browser-firebase-challenge"),
    path("browser-firebase/<int:makerspace_id>/confirm", BrowserFirebaseConfirmView.as_view(), name="browser-firebase-confirm"),
    path("browser-alerts/<int:makerspace_id>", BrowserAlertSubscriptionView.as_view(), name="browser-alert-subscriptions"),
    path("preferences/<int:makerspace_id>", MemberPreferenceView.as_view(), name="member-preferences"),
    path("unsubscribe/<str:token>", OneClickUnsubscribeView.as_view(), name="one-click-unsubscribe"),
    path(
        "makerspace/<int:makerspace_id>",
        NotificationListView.as_view(),
        name="notifications-list",
    ),
    path(
        "makerspace/<int:makerspace_id>/unread-count",
        NotificationUnreadCountView.as_view(),
        name="notifications-unread-count",
    ),
    path(
        "makerspace/<int:makerspace_id>/read-all",
        NotificationMarkAllReadView.as_view(),
        name="notifications-read-all",
    ),
    path(
        "makerspace/<int:makerspace_id>/<int:pk>/read",
        NotificationMarkReadView.as_view(),
        name="notifications-read",
    ),
]
