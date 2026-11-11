from apps.accounts.models import NativeAppRegistration


def make_native_app_registration(
    *,
    app_id="org.spaceworks.app",
    platform="apple",
    environment="development",
    makerspace=None,
    status=NativeAppRegistration.Status.APPROVED,
):
    if makerspace is None and status == NativeAppRegistration.Status.APPROVED:
        # One approved deployment registration per platform/environment (DB-enforced).
        existing = NativeAppRegistration.objects.filter(
            makerspace=None, platform=platform, environment=environment, status=status,
        ).first()
        if existing is not None:
            return existing
    registration, _ = NativeAppRegistration.objects.get_or_create(
        makerspace=makerspace,
        app_id=app_id,
        platform=platform,
        environment=environment,
        defaults={
            "verifier_config_key": app_id,
            "status": status,
        },
    )
    return registration
