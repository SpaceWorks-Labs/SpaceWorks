"""Conditional-write failures must still clean only the attempt's exact key."""

import io
from pathlib import Path
import sys
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
from cloud_setup.errors import SetupError
from cloud_setup.storage_probe import probe_bucket


class ClientError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}


class Store:
    def __init__(self, *, honor_condition=True, uncertain=False):
        self.objects = {"staging/setup-probes/probe-neighbor": b"keep"}
        self.lock = threading.Lock()
        self.honor_condition = honor_condition
        self.uncertain = uncertain
        self.deleted = []

    def put_object(self, **kwargs):
        with self.lock:
            key = kwargs["Key"]
            if key in self.objects and self.honor_condition:
                raise ClientError("PreconditionFailed")
            self.objects[key] = kwargs["Body"]
            if self.uncertain:
                raise OSError("private-sentinel")
            return {}

    def get_object(self, **kwargs):
        return {"Body": io.BytesIO(self.objects[kwargs["Key"]])}

    def delete_object(self, **kwargs):
        self.deleted.append(kwargs)
        self.objects.pop(kwargs["Key"], None)

    def head_object(self, **kwargs):
        if kwargs["Key"] not in self.objects:
            raise ClientError("404")
        return {}

    def get_paginator(self, name):
        return self

    def paginate(self, **kwargs):
        return [{"Versions": [{"Key": key, "VersionId": "one"} for key in self.objects if key.startswith(kwargs["Prefix"])]}]

    def generate_presigned_url(self, *args, **kwargs):
        return "https://store.example/test?signature=private-sentinel"

    def generate_presigned_post(self, **kwargs):
        self.post_options = kwargs
        return {"url": "https://store.example/upload", "fields": {"key": kwargs["Key"]}}


class StorageProbeTests(unittest.TestCase):
    def run_probe(self, store, versioning="never_versioned", method="put"):
        module = ModuleType("botocore.exceptions")
        module.ClientError = ClientError
        response = SimpleNamespace(headers={"Access-Control-Allow-Origin": "https://app.example"})
        class Context:
            def __enter__(self):
                return response
            def __exit__(self, *args):
                pass
        def open_request(request, **kwargs):
            store.cors_method = request.headers["Access-control-request-method"]
            return Context()
        opener = SimpleNamespace(open=open_request)
        with patch.dict(sys.modules, {"botocore.exceptions": module}), patch("cloud_setup.storage_probe.uuid.uuid4", return_value=SimpleNamespace(hex="probe")), patch("cloud_setup.storage_probe.check_url"), patch("cloud_setup.storage_probe.build_opener", return_value=opener), patch("cloud_setup.storage_probe.post_upload") as post:
            result = probe_bucket(store, store, "private", {"versioning": versioning}, "private", {}, {"public_origin": "https://app.example", "presign_method": method})
            store.post_calls = post.call_args_list
            return result

    def test_one_winner_and_private_probe_cleanup(self):
        store = Store()
        result = self.run_probe(store)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(store.objects, {"staging/setup-probes/probe-neighbor": b"keep"})

    def test_provider_ignoring_condition_refused_and_cleaned(self):
        store = Store(honor_condition=False)
        with self.assertRaises(SetupError) as raised:
            self.run_probe(store)
        self.assertEqual(raised.exception.code, "conditional_create_unproven")
        self.assertNotIn("staging/setup-probes/probe", store.objects)

    def test_uncertain_write_is_cleaned_even_without_response(self):
        store = Store(uncertain=True)
        with self.assertRaises(OSError):
            self.run_probe(store)
        self.assertEqual(store.objects, {"staging/setup-probes/probe-neighbor": b"keep"})

    def test_version_history_cleanup_never_deletes_adjacent_key(self):
        store = Store()
        self.run_probe(store, versioning="suspended")
        self.assertEqual(store.objects, {"staging/setup-probes/probe-neighbor": b"keep"})
        self.assertTrue(all(item["Key"] == "staging/setup-probes/probe" for item in store.deleted))
        self.assertTrue(all("VersionId" in item for item in store.deleted))

    def test_post_selection_uses_post_cors_and_size_policy(self):
        store = Store()
        self.run_probe(store, method="post")
        self.assertEqual(store.cors_method, "POST")
        self.assertTrue(any(condition[0] == "content-length-range" for condition in store.post_options["Conditions"] if isinstance(condition, list)))
        self.assertEqual([call.kwargs["oversized"] for call in store.post_calls], [False, True])


if __name__ == "__main__":
    unittest.main()
