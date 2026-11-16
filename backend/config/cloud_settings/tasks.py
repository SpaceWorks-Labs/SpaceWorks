"""Explicit cloud task selection; the legacy host/full branch changes nothing."""

from cloud_contracts.deployment import DeploymentSelection


def task_settings(env, selection: DeploymentSelection, *, profile="", scheduler="") -> dict:
    if selection.mode == "host" and not profile and not scheduler:
        return {}  # preserve the existing fallback, eager, cache and beat settings
    broker = env("CELERY_BROKER_URL", default="")
    cache = env("CACHE_URL", default="")
    live = env("LIVE_REDIS_URL", default="")
    result = env("CELERY_RESULT_BACKEND", default="")
    profile = profile or ("brokerless" if selection.is_free or not broker else "redis")
    scheduler = scheduler or ("tick" if selection.is_free else (
        "beat" if profile == "redis" else "loop"
    ))
    if profile not in ("redis", "brokerless"):
        raise ValueError("CLOUD_TASK_PROFILE must be redis or brokerless.")
    allowed = ("tick",) if selection.is_free else (
        ("beat",) if profile == "redis" else ("loop", "external")
    )
    if scheduler not in allowed:
        raise ValueError("CLOUD_SCHEDULER conflicts with the selected deployment/task profile.")
    eager = env.bool("CELERY_TASK_ALWAYS_EAGER", default=profile == "brokerless")
    if selection.is_free and profile != "brokerless":
        raise ValueError("The free profile requires brokerless tasks.")
    if profile == "brokerless":
        if any((broker, cache, live, result)) or not eager:
            raise ValueError("Brokerless tasks require empty broker/cache/live/result URLs and eager tasks.")
    elif not broker or eager:
        raise ValueError("Redis tasks require a broker and non-eager tasks.")
    elif not broker.startswith(("redis://", "rediss://")):
        raise ValueError("The cloud Redis broker must use redis:// or rediss://.")
    return {
        "CLOUD_TASK_PROFILE": profile,
        "CLOUD_SCHEDULER": scheduler,
        "CELERY_BROKER_URL": broker,
        "CELERY_TASK_ALWAYS_EAGER": eager,
        "CELERY_RESULT_BACKEND": result or None,
        "CACHE_URL": cache or broker,
        "LIVE_REDIS_URL": live,
    }
