"""G installs a retained-data adapter. Core never imports a removable workflow."""
from .errors import require

_provider = None


def install(provider):
    global _provider
    if _provider is not None and _provider is not provider:
        raise RuntimeError("Payout coordination provider already installed.")
    _provider = provider


def prepare(obligation):
    if obligation.domain_coordination_state == "detached":
        return None
    require(_provider is not None, "payout_coordination_unavailable", status=503)
    return _provider.resolve(obligation=obligation)
