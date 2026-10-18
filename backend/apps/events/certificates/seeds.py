"""E validates ARTWORK-owned catalogue data; G installs its read-only provider."""
from rest_framework.exceptions import APIException
from copy import deepcopy
from .layout import normalize_document
from .badge_designs import validate_design

_catalogue = None


class SeedCatalogueUnavailable(APIException):
    status_code = 503
    default_detail = "Default designs are temporarily unavailable."
    default_code = "seed_catalogue_unavailable"


def install_catalogue(provider):
    global _catalogue
    _catalogue = provider


def catalogue(*, kind, theme, stock=None):
    if _catalogue is None:
        raise SeedCatalogueUnavailable()
    seeds = _catalogue(kind=kind, theme=theme, stock=stock)
    result = []
    for seed in seeds:
        source = deepcopy(seed["document"])
        if theme == "dark":
            for layer in source["layers"]:
                if layer.get("colour_token") == "ink":
                    layer["colour_token"] = "cream"
        document = (validate_design(source, stock) if kind == "badge"
                    else normalize_document(source))
        result.append({"seed_id": seed["seed_id"], "seed_version": seed["seed_version"],
                       "theme": theme, "document": document, "stock": stock,
                       "resources": deepcopy(seed["resources"])})
    return result


def install_to_event(event_id, *, actor, seed_id, theme, kind, stock=None):
    """On-demand installation; packaged catalogue imports never write tenant rows."""
    from .seed_installation import install_to_event as install
    return install(event_id, actor=actor, seed_id=seed_id, theme=theme, kind=kind, stock=stock)
