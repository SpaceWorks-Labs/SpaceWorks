"""The base view of every signed Device Adapter API route: the signed device protocol plus the adapter throttles.

Printer and label routes keep ``SignedDeviceView`` (the deployment baseline only); adapter routes add a per-device
scope, and the credential-testing routes a tighter one on top (decision 336c, ``apps.devices.throttles``).
"""
from apps.devices.throttles import ADAPTER_THROTTLES, CREDENTIAL_THROTTLES
from apps.devices.views_printer_common import SignedDeviceView


class SignedAdapterView(SignedDeviceView):
    throttle_classes = ADAPTER_THROTTLES


class SignedCredentialView(SignedAdapterView):
    throttle_classes = CREDENTIAL_THROTTLES
