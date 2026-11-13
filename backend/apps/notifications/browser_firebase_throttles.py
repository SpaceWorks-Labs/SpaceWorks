"""Cheap read checks have a separate budget from possession challenges."""
from rest_framework.throttling import UserRateThrottle


class BrowserFirebaseReadThrottle(UserRateThrottle):
    scope = "browser-firebase-read"

    def get_rate(self):
        return "120/hour"
