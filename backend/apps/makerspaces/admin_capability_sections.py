"""Group the /control/ capability matrix by area (the same `module_registry.GROUPS` the console uses).

The matrix posts one flat list of `module:*` / `feature:*` values; this only decides how the
checkboxes are laid out (area -> module -> its features), so search, counts and the
collapsible areas have somewhere to hang. It never changes a value or a name.
"""

from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.module_registry import BY_KEY, GROUPS
from config.locale_resolution import display


def capability_sections(options):
    """`options`: widget option dicts (value, label, selected). Returns sections of modules with their features."""
    by_value = {option["value"]: option for option in options}
    modules = {value.removeprefix("module:"): option for value, option in by_value.items() if value.startswith("module:")}
    features = {value.removeprefix("feature:"): option for value, option in by_value.items() if value.startswith("feature:")}
    children = {}
    for key, option in features.items():
        parent = getattr(FEATURES.get(key), "parent_module", None)
        children.setdefault(parent if parent in modules else None, []).append(option)

    def entry(key):
        definition = BY_KEY.get(key)
        return {"option": modules[key], "core": bool(definition and definition.is_core), "features": children.get(key, [])}

    sections = []
    for group in GROUPS:
        keys = [key for key in modules if getattr(BY_KEY.get(key), "group", None) == group.key]
        if keys:
            sections.append({"key": group.key, "label": display(group.label), "description": display(group.description),
                             "modules": [entry(key) for key in keys]})
    unknown = [key for key in modules if key not in BY_KEY]
    if unknown:
        sections.append({"key": "other", "label": "Unrecognised", "description": "Kept so saving never drops them.",
                         "modules": [entry(key) for key in unknown]})
    if children.get(None):
        sections.append({"key": "general", "label": "General features", "description": "Features that need no area.",
                         "modules": [], "loose_features": children[None]})
    for section in sections:
        section["total"] = sum(1 + len(m["features"]) for m in section["modules"]) + len(section.get("loose_features", []))
    return sections
