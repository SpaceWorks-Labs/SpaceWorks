"""Explicit query-free startup composition, called only for installed Events."""


def install():
    from . import certificate_registration, form_registration, photo_registration, pages_registration
    from . import prefill_registration, readiness_registration, asset_registration
    from apps.events.judging.ports import install as install_judging
    from apps.events.judging.provider_runtime import JudgingProviders
    from apps.events.judging.provider_notices import register as register_judging_notices
    install_judging(JudgingProviders())
    register_judging_notices()
    certificate_registration.install()
    form_registration.install()
    photo_registration.install()
    pages_registration.install()
    prefill_registration.install()
    readiness_registration.install()
    asset_registration.install()
