import re, json
from pathlib import Path
from apps.makerspaces.capability_definitions import FEATURE_DEFINITIONS
from apps.makerspaces.capability_validation import default_enabled_features
src = Path("/workspace/frontend/src/lib/features.ts").read_text(encoding="utf-8")
body = src.split("FEATURE_DEFINITIONS: readonly FeatureDefinition[] = [", 1)[1].split("];", 1)[0]
m = set()
for line in body.splitlines():
    x = re.search(r'key:\s*"([^"]+)",\s*parent_module:\s*(null|"[^"]*"),\s*label:\s*"([^"]+)"', line)
    if x:
        k, p, l = x.groups(); m.add((k, None if p == "null" else json.loads(p), l))
e = {(d.key, d.parent_module, d.label) for d in FEATURE_DEFINITIONS if d.frontend_exposed}
print("missing in fe", sorted(e - m)); print("extra in fe", sorted(m - e))
print(len(FEATURE_DEFINITIONS)); print(default_enabled_features())
