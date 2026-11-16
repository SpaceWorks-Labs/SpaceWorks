"""#187A: the platform hosting provider keys are never stored as plaintext."""
import pytest

from apps.managed_hosting.models import PlatformHostingBillingSettings

pytestmark = pytest.mark.django_db


def test_a_raw_write_is_encrypted_on_save_and_reads_back():
    row = PlatformHostingBillingSettings.load()
    row.stripe_secret_key = "sk_test_raw"
    row.save()
    stored = PlatformHostingBillingSettings.objects.values_list("stripe_secret_key", flat=True).get(pk=row.pk)
    assert stored.startswith("fernet:") and "sk_test_raw" not in stored
    assert PlatformHostingBillingSettings.load().secret("stripe_secret_key") == "sk_test_raw"
    row.set_secret("razorpay_key_secret", "rzp_secret")
    row.save()
    assert PlatformHostingBillingSettings.load().secret("razorpay_key_secret") == "rzp_secret"
