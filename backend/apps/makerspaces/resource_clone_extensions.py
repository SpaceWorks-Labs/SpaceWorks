"""Query-free clone child adapters; no infrastructure import of separable apps."""

_extensions = {}


def register_clone_extension(domain, name, copier):
    key = (domain, name)
    if key in _extensions and _extensions[key] is not copier:
        raise RuntimeError(f"Duplicate clone extension: {key}")
    _extensions[key] = copier


def copy_extensions(domain, source, clone, assets):
    # Adapters participate in the caller's durable transaction and asset cleanup.
    for (owner, _), copier in tuple(_extensions.items()):
        if owner == domain:
            copier(source, clone, assets)
