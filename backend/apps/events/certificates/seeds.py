"""E validates ARTWORK-owned catalogue data; G installs its read-only provider."""
from rest_framework.exceptions import APIException
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
        document = (validate_design(seed["document"], stock) if kind == "badge"
                    else normalize_document(seed["document"]))
        result.append({"seed_id": seed["seed_id"], "seed_version": seed["seed_version"],
                       "theme": theme, "document": document, "stock": stock})
    return result
