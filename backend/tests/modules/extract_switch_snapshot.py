"""Pull the snapshot JSON out of a `regen_switch_matrix.py` log and write switch_matrix_snapshot.json."""
import json
import pathlib
import sys

log = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
body = log.split("SNAPSHOT-BEGIN\n", 1)[1].split("\nSNAPSHOT-END", 1)[0]
data = json.loads(body.replace("\n", ""))
out = pathlib.Path(__file__).with_name("switch_matrix_snapshot.json")
out.write_text(json.dumps(data, sort_keys=True, indent=1) + "\n", encoding="utf-8")
print("wrote", out, len(data["gates"]), "gated routes")
