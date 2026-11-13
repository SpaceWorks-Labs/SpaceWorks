"""Rebuild `switch_matrix_snapshot.json` (run only when the route table or module registry changed).

Not collected by default (the name is not `test_*`); run it by path through the shared lock:

    bash testlock.sh sw-regen backend/tests/modules/regen_switch_matrix.py

It takes ~10 minutes and FAILS on purpose, printing the JSON between BEGIN/END markers in the log (the isolated runner
copies the repo, so a written file would not reach the worktree). Extract with
`python backend/tests/modules/extract_switch_snapshot.py <log>`; then run `test_switch_matrix_snapshot_guard`.
"""

import json

import pytest

from tests.modules.switch_matrix_helpers import compute_route_map, encode_map

pytestmark = [pytest.mark.django_db, pytest.mark.timeout(3000)]


def test_regenerate_snapshot():
    text = json.dumps(encode_map(compute_route_map()), sort_keys=True, indent=0)
    chunks = [text[i:i + 200] for i in range(0, len(text), 200)]
    pytest.fail("\nSNAPSHOT-BEGIN\n" + "\n".join(chunks) + "\nSNAPSHOT-END\n", pytrace=False)
