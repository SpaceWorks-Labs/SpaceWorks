#!/usr/bin/env python3
"""Build a source-only diagnostic capsule; images need no host script mount."""
import base64
import json
from pathlib import Path

FILES = ("runtime-probes.py", "probe-common.py", "probe-services.py",
         "probe-storage.py", "probe-integrations.py")


def main():
    root = Path(__file__).resolve().parent
    files = {name.replace("-", "_"): (root / name).read_text(encoding="utf-8") for name in FILES}
    encoded = base64.b64encode(json.dumps(files).encode()).decode("ascii")
    print("import base64,json,pathlib,runpy,sys,tempfile\n"
          "with tempfile.TemporaryDirectory(prefix='spaceworks-probes-') as work:\n"
          f" files=json.loads(base64.b64decode('{encoded}'))\n"
          " for name, source in files.items(): pathlib.Path(work,name).write_text(source,encoding='utf-8')\n"
          " sys.path.insert(0,work)\n"
          " runpy.run_path(str(pathlib.Path(work,'runtime_probes.py')),run_name='__main__')")


if __name__ == "__main__":
    main()
