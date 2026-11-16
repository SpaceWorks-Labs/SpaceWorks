"""Review fix: the contextual equipment modules import in either order (no cycle)."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from apps.hardware_requests import contextual_equipment_common as common
from apps.hardware_requests import contextual_equipment_execution as execution
from apps.hardware_requests import contextual_equipment_service as service

BACKEND = Path(__file__).resolve().parents[2]


def test_shared_symbols_are_one_object_re_exported_from_the_service():
    assert service.ProposalConflict is execution.ProposalConflict is common.ProposalConflict
    assert service._aliases is common._aliases
    assert service._require_same_outcome is common._require_same_outcome
    assert service._create_pending is execution._create_pending


@pytest.mark.parametrize("first", ["contextual_equipment_execution", "contextual_equipment_service"])
def test_either_module_imports_first_in_a_fresh_interpreter(first):
    code = ("import django; django.setup(); "
            f"import apps.hardware_requests.{first}; "
            "from apps.hardware_requests.contextual_equipment_service import create_pending, ProposalConflict")
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings")}
    result = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
