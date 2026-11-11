"""A staging upload above the free cap can never become an accepted final key."""
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import override_settings
import pytest

from apps.evidence.storage import StorageUnavailable
from apps.private_uploads import finalize, promotion_limit


def test_free_cap_does_not_change_full_document_limit():
    with override_settings(SPACEWORKS_DEPLOYMENT_PROFILE="full", FREE_MAX_PROMOTION_BYTES=16):
        assert promotion_limit(32) == 32
    with override_settings(SPACEWORKS_DEPLOYMENT_PROFILE="free", FREE_MAX_PROMOTION_BYTES=16):
        assert promotion_limit(32) == 16


def test_put_above_free_cap_cannot_be_returned_as_valid_domain_size():
    client = Mock()
    client.head_object.return_value = {"ContentLength":20, "ETag":"etag"}
    storage = SimpleNamespace(_client=lambda:client, object_size=lambda key:None,
                              staging_key=lambda key:"staging/"+key)
    with override_settings(SPACEWORKS_DEPLOYMENT_PROFILE="free", FREE_MAX_PROMOTION_BYTES=16,
                           AWS_STORAGE_BUCKET_NAME="private"):
        with pytest.raises(StorageUnavailable):
            finalize(storage, "documents/key", 32)
    client.put_object.assert_not_called()
    client.copy_object.assert_not_called()
