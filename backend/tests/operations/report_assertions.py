"""Reusable disclosure backstop for report previews and decoded artifacts.

Call after decoding CSV/XLSX/PDF or JSON. This supplements the schema allowlist:
an allowed column must not contain an accidentally nested credential/payload.
Assertion messages deliberately omit the matching value.
"""

import re
from collections.abc import Mapping


_CREDENTIAL = re.compile(
    r"secret|token|password|private[_ -]?key|webhook[_ -]?url|api[_ -]?key|smtp|client[_ -]?secret",
    re.IGNORECASE,
)
_RAW_CONTENT = re.compile(
    r"^(?:raw[_ -]?)?(?:audit[_ -]?meta|meta(?:data)?|delivery[_ -]?payload|payload|"
    r"message[_ -]?body|text[_ -]?body|html[_ -]?body|(?:feedback[_ -]?)?answers?)$",
    re.IGNORECASE,
)


def assert_report_disclosure_safe(value, *, aggregate=True, path="response"):
    """Walk decoded data, including headers, nested records and metadata.

Envelope ``meta`` is allowed; raw audit/delivery content inside that envelope is
not. Aggregate feedback answers and free-text message bodies are never metrics.
"""
    if isinstance(value, Mapping):
        for key, item in value.items():
            label = str(key)
            assert not _CREDENTIAL.search(label), f"Credential-like report key at {path}"
            envelope = label == "meta" and path == "response"
            assert not (aggregate and _RAW_CONTENT.fullmatch(label) and not envelope), (
                f"Raw content report key at {path}"
            )
            assert_report_disclosure_safe(item, aggregate=aggregate, path=f"{path}.{label}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            assert_report_disclosure_safe(item, aggregate=aggregate, path=f"{path}[{index}]")
    elif isinstance(value, (str, bytes)):
        text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
        assert not _CREDENTIAL.search(text), f"Credential-like report value at {path}"
        assert not (aggregate and _RAW_CONTENT.fullmatch(text)), f"Raw content report label at {path}"
