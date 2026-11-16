"""Apply stored visibility to the existing privacy-safe public stats projection."""
from copy import deepcopy

from apps.makerspaces.public_stats_catalogue import WIDGETS, source_available

_SECTION_PAYLOADS = {"events": ("events",), "machines": ("machines",), "printing": ("printing",),
                     "lending": ("hardware", "current_loans"), "community": ("community",)}


def _hide(payload, path, kind):
    parent = payload
    for part in path[:-1]:
        if not isinstance(parent, dict):
            return
        parent = parent.get(part)
    if isinstance(parent, dict) and parent.get(path[-1]) is not None:
        parent[path[-1]] = [] if kind == "list" else None


def apply_visibility(makerspace, payload, config):
    """Never create new data or change suppression; remove disabled representations."""
    result = deepcopy(payload)
    shown = set(result["sections"])
    visible = {key: bool(config["visibility"][key] and widget.section in shown
                         and source_available(makerspace, key)) for key, widget in WIDGETS.items()}
    for key, widget in WIDGETS.items():
        if not visible[key]:
            for path in widget.paths:
                _hide(result, path, widget.kind)
    result["metrics"] = [row for row in result["metrics"] if visible[row["key"]]]
    result["headline"] = [row for row in result["headline"] if visible[row["key"]]]
    result["sections"] = [section for section in result["sections"]
                          if any(visible[key] for key, widget in WIDGETS.items() if widget.section == section)]
    for section, names in _SECTION_PAYLOADS.items():
        if section not in result["sections"]:
            for name in names:
                result[name] = None
    result["visibility"] = visible
    return result
