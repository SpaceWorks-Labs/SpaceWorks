"""The one authored list of supported locales (phase 8 i18n).

``supported_locales.json`` beside this file is the single source: Django's ``LANGUAGES``,
the model field choices and the frontend's generated ``src/generated/locales.ts`` all come
from it, so the two stacks can never carry different lists. The list is code-defined, never
read from the environment. Adding a language is one registry entry plus one catalogue per
stack (``docs/i18n.md``).

This module must not import Django settings: ``config/settings.py`` imports it.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

REGISTRY_PATH = Path(__file__).with_name("supported_locales.json")
SYSTEM_LOCALE = "en"
# A simple BCP-47-style code: a 2-3 letter language, then optional script/region subtags.
_CODE = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


class LocaleRegistryError(ValueError):
    pass


@lru_cache(maxsize=1)
def supported_locales():
    """The validated registry as a tuple of ``(code, label)`` pairs, system locale first."""
    raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise LocaleRegistryError("supported_locales.json must be a non-empty list.")
    entries, seen = [], set()
    for entry in raw:
        code, label = (entry or {}).get("code"), (entry or {}).get("label")
        if not isinstance(code, str) or not _CODE.match(code) or code != code.lower():
            raise LocaleRegistryError(f"Invalid locale code in registry: {code!r}")
        if not isinstance(label, str) or not label.strip():
            raise LocaleRegistryError(f"Locale {code!r} needs a label.")
        if code in seen:
            raise LocaleRegistryError(f"Duplicate locale code in registry: {code!r}")
        seen.add(code)
        entries.append((code, label))
    if entries[0][0] != SYSTEM_LOCALE:
        raise LocaleRegistryError(f"The system locale {SYSTEM_LOCALE!r} must be listed first.")
    return tuple(entries)


def supported_codes():
    return tuple(code for code, _label in supported_locales())


def django_languages():
    """``settings.LANGUAGES`` and the model field choices."""
    return [(code, label) for code, label in supported_locales()]


def locale_list_payload():
    """The ``supported_locales`` list sent in bootstrap and auth payloads."""
    return [{"code": code, "label": label} for code, label in supported_locales()]


def canonicalize(value):
    """The registry code for ``value`` (case and ``_``/``-`` variants accepted), else None.

    A region variant falls back to its base language when only the base is supported, so
    ``en-US`` and ``en_gb`` both become ``en``.
    """
    if not isinstance(value, str):
        return None
    candidate = value.strip().replace("_", "-").lower()
    if not candidate or not _CODE.match(candidate):
        return None
    codes = supported_codes()
    if candidate in codes:
        return candidate
    base = candidate.split("-", 1)[0]
    return base if base in codes else None
