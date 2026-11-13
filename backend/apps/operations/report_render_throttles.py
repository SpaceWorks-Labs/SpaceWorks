from rest_framework.throttling import SimpleRateThrottle


class ReportRenderThrottle(SimpleRateThrottle):
    scope = "report_render"
    rate = "30/hour"

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return None
        return self.cache_format % {"scope": self.scope, "ident": user.pk}
