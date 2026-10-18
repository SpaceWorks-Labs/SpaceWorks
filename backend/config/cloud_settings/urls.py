"""The free tick URLConf must not even be imported under full settings."""


def free_tick_paths(profile):
    if profile != "free":
        return []
    from django.urls import include, path

    # J owns the literal `tick` leaf (no trailing slash) and all view defenses.
    # Missing J code is a startup failure, never a silently unprotected route.
    return [path("api/v1/internal/free/", include("apps.operations.cloud_jobs.tick_urls"))]
