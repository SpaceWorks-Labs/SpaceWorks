from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest


def test_sdk_thread_keeps_original_writer_and_operation_guard(settings, monkeypatch):
    from apps import storage_clients
    from apps.operations import cloud_runtime
    from apps.backup.cloud_continuity import operation_guard
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.AWS_ACCESS_KEY_ID = "key"
    settings.AWS_SESSION_TOKEN = ""
    handlers = {}
    client = SimpleNamespace(meta=SimpleNamespace(events=SimpleNamespace(register=lambda event, callback: handlers.setdefault(event, callback))))
    monkeypatch.setattr(storage_clients.boto3, "client", lambda *args, **kwargs: client)
    monkeypatch.setattr("apps.storage_capabilities.budget.client_options", lambda: {})
    monkeypatch.setattr("apps.storage_capabilities.runtime.capabilities_for", lambda *args, **kwargs: None)
    monkeypatch.setattr(cloud_runtime, "managed", lambda: True)
    checked = []
    def check():
        checked.append(cloud_runtime._writer.get().row.generation)
    monkeypatch.setattr(cloud_runtime, "check", check)
    alive = [True]
    def assert_valid():
        if not alive[0]:
            raise RuntimeError("original guard lost")
    original = SimpleNamespace(row=SimpleNamespace(generation=1))
    token = cloud_runtime._writer.set(original)
    try:
        with operation_guard(SimpleNamespace(assert_valid=assert_valid)):
            storage_clients.s3_client("s3")
    finally:
        cloud_runtime._writer.reset(token)
    replacement = cloud_runtime._writer.set(SimpleNamespace(row=SimpleNamespace(generation=2)))
    callback = handlers["before-parameter-build.s3"]
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(callback, params={"Bucket": "private"}, context={}, model=SimpleNamespace(name="HeadObject")).result()
            assert checked and set(checked) == {1}
            alive[0] = False
            with pytest.raises(RuntimeError, match="original guard lost"):
                pool.submit(callback, params={"Bucket": "private"}, context={}, model=SimpleNamespace(name="HeadObject")).result()
    finally:
        cloud_runtime._writer.reset(replacement)
