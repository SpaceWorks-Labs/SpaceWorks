"""Display settings shared by a paired screen and the public page (decision 325a): validation and privacy.

Privacy only ever narrows. `profiles` is what Here now showed before settings existed (open profiles by
name, everyone else a count), so no choice here can be less private than the old behaviour.
"""
from django.utils.translation import gettext

from .models_display import LAYOUTS, MAX_REFRESH, MAX_ROTATION, MIN_REFRESH, MIN_ROTATION, PANELS, PRIVACY_LEVELS, THEMES
from .policy import PresenceError


def _choice(values, key, allowed):
    if values[key] not in allowed:
        raise PresenceError(f"invalid_{key}", gettext("That choice is not available."))
    return values[key]


def clean_panels(panels):
    if (not isinstance(panels, list) or not panels or len(set(panels)) != len(panels)
            or any(p not in PANELS for p in panels)):
        raise PresenceError("invalid_panels", gettext("Choose at least one valid panel, each once."))
    return panels


def clean_refresh(seconds):
    if type(seconds) is not int or not MIN_REFRESH <= seconds <= MAX_REFRESH:
        raise PresenceError("invalid_refresh", gettext("Refresh must be between %(lo)s and %(hi)s seconds.")
                            % {"lo": MIN_REFRESH, "hi": MAX_REFRESH})
    return seconds


def clean_slide_seconds(value):
    if not isinstance(value, dict) or any(k not in PANELS for k in value):
        raise PresenceError("invalid_slide_seconds", gettext("Slide seconds must name valid panels."))
    for seconds in value.values():
        if type(seconds) is not int or not MIN_ROTATION <= seconds <= MAX_ROTATION:
            raise PresenceError("invalid_slide_seconds", gettext("Rotation must be between %(lo)s and %(hi)s seconds.")
                                % {"lo": MIN_ROTATION, "hi": MAX_ROTATION})
    return value


def clean_display_settings(values):
    """The layout/theme/privacy/refresh/slide fields present in `values`, validated."""
    result = {}
    for key, allowed in (("layout", LAYOUTS), ("theme", THEMES), ("privacy", PRIVACY_LEVELS)):
        if key in values:
            result[key] = _choice(values, key, allowed)
    if "refresh_seconds" in values:
        result["refresh_seconds"] = clean_refresh(values["refresh_seconds"])
    if "slide_seconds" in values:
        result["slide_seconds"] = clean_slide_seconds(values["slide_seconds"])
    return result


def apply_privacy(here_now, privacy):
    """Narrow a Here now payload. `profiles` returns it untouched."""
    if not here_now or privacy == "profiles":
        return here_now
    total = here_now["total"]
    if privacy == "counts":
        return {**here_now, "people": [], "others_count": total}
    people = [{"handle": None, "display_name": str(card["display_name"]).split(" ")[0], "avatar_url": None,
               "headline": "", "status": None, "skills": [], "presence_status": card["presence_status"],
               "since": card["since"]} for card in here_now["people"]]
    return {**here_now, "people": people}
