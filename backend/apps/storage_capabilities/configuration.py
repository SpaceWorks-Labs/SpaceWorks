"""Bounded, strict versioned configuration; never contains credentials."""

import json
import re
from pathlib import Path

from .contracts import CapabilityError, StorageCapabilities, StorageIdentity

FEATURES = (
    "list_delete_versions", "conditional_create", "copy", "multipart",
    "object_lock", "cors_management",
)
VERSIONS = {"enabled", "never_versioned", "suspended", "unknown"}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CapabilityError("storage_configuration_duplicate_key")
        result[key] = value
    return result


def read_configuration(path):
    try:
        with Path(path).open("rb") as handle:
            raw = handle.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise CapabilityError("storage_configuration_too_large")
        document = json.loads(raw, object_pairs_hook=_unique)
    except (OSError, ValueError, UnicodeError, RecursionError):
        raise CapabilityError("storage_configuration_unreadable") from None
    if (
        not isinstance(document, dict) or set(document) != {"version", "buckets"}
        or type(document["version"]) is not int or document["version"] != 1
        or not isinstance(document["buckets"], dict)
        or not {"private", "public_image"}.issubset(document["buckets"])
        or any(name not in {"private", "public_image", "anchor"}
               and not re.fullmatch(r"offsite_[a-z0-9_-]{1,64}", name) for name in document["buckets"])
    ):
        raise CapabilityError("storage_configuration_invalid")
    contracts = {name: _contract(value, allow_no_upload=name not in {"private", "public_image"})
                 for name, value in document["buckets"].items()}
    identities = [value.identity.fingerprint for value in contracts.values()]
    if len(identities) != len(set(identities)):
        raise CapabilityError("storage_bucket_identity_collision")
    if contracts["private"].public_delivery != "private":
        raise CapabilityError("storage_private_bucket_public")
    if contracts["public_image"].public_delivery != "public":
        raise CapabilityError("storage_public_delivery_invalid")
    if "anchor" in contracts and contracts["anchor"].public_delivery != "private":
        raise CapabilityError("storage_anchor_bucket_public")
    if any(value.public_delivery != "private" for name, value in contracts.items() if name.startswith("offsite_")):
        raise CapabilityError("storage_offsite_bucket_public")
    return contracts


def _contract(value, *, allow_no_upload=False):
    required = {
        "endpoint", "region", "bucket", "generation", "presign_methods", "versioning",
        "staging_policy", "public_delivery", *FEATURES,
    }
    if not isinstance(value, dict) or not required.issubset(value):
        raise CapabilityError("storage_contract_invalid")
    if set(value) - required - {"max_object_bytes"}:
        raise CapabilityError("storage_contract_unknown_field")
    generation = value["generation"]
    methods = value["presign_methods"]
    if type(generation) is not int or not 1 <= generation <= 2147483647:
        raise CapabilityError("storage_generation_invalid")
    if (
        not isinstance(methods, list) or (not methods and not allow_no_upload)
        or any(not isinstance(method, str) or method not in ("put", "post") for method in methods)
        or len(methods) != len(set(methods))
    ):
        raise CapabilityError("storage_presign_methods_invalid")
    if not isinstance(value["versioning"], str) or value["versioning"] not in VERSIONS:
        raise CapabilityError("storage_versioning_invalid")
    if any(value[name] is not None and type(value[name]) is not bool for name in FEATURES):
        raise CapabilityError("storage_feature_invalid")
    if value["staging_policy"] != "private":
        raise CapabilityError("storage_staging_must_be_private")
    if not isinstance(value["public_delivery"], str) or value["public_delivery"] not in {"private", "public"}:
        raise CapabilityError("storage_public_delivery_invalid")
    maximum = value.get("max_object_bytes")
    if maximum is not None and (type(maximum) is not int or maximum < 1):
        raise CapabilityError("storage_object_limit_invalid")
    if value["versioning"] in {"enabled", "suspended"} and not value["list_delete_versions"]:
        raise CapabilityError("storage_history_listing_required")
    if value["object_lock"] and value["versioning"] != "enabled":
        raise CapabilityError("storage_object_lock_requires_versioning")
    return StorageCapabilities(
        identity=StorageIdentity.build(value["endpoint"], value["region"], value["bucket"]),
        generation=generation, presign_methods=frozenset(methods),
        versioning=value["versioning"], staging_policy=value["staging_policy"],
        public_delivery=value["public_delivery"], max_object_bytes=maximum,
        **{name: value[name] for name in FEATURES},
    )
