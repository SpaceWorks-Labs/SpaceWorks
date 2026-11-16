"""Fail-closed projection of server error/transaction events before Sentry export."""
import builtins
import math
import re
from datetime import datetime

_BUILTIN_ERRORS = frozenset(name for name in dir(builtins)
                            if isinstance(getattr(builtins, name), type)
                            and issubclass(getattr(builtins, name), BaseException))
_APPROVED_ERRORS = _BUILTIN_ERRORS | frozenset({"ValidationError", "PermissionDenied", "Http404",
                                                "ObjectDoesNotExist", "IntegrityError", "OperationalError"})
_HEX = re.compile(r"^[0-9a-f]{32}$")
_SPAN = re.compile(r"^[0-9a-f]{16}$")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,79}$")
_FILENAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,99}\.py$")
_ISO_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$")
_MAX_TIMESTAMP = 4102444800  # 2100-01-01 UTC


def _timestamp(value):
    """Return a bounded UTC epoch number; never copy untrusted timestamp strings."""
    try:
        if isinstance(value, str):
            if not _ISO_TIMESTAMP.fullmatch(value):
                return None
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                return None
            value = value.timestamp()
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or not 0 <= value <= _MAX_TIMESTAMP):
            return None
        return value
    except (ValueError, OverflowError, OSError):
        return None


def _base(event):
    result = {"platform": "python"}
    event_id = event.get("event_id")
    if isinstance(event_id, str) and _HEX.fullmatch(event_id):
        result["event_id"] = event_id
    timestamp = _timestamp(event.get("timestamp"))
    if timestamp is not None:
        result["timestamp"] = timestamp
    return result


def _frames(value):
    stack = value.get("stacktrace")
    if not isinstance(stack, dict) or not isinstance(stack.get("frames"), list):
        return []
    result = []
    for frame in stack["frames"][-100:]:
        if not isinstance(frame, dict) or frame.get("in_app") is not True:
            continue
        filename, function, lineno = frame.get("filename"), frame.get("function"), frame.get("lineno")
        if not isinstance(filename, str):
            continue
        filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
        if not _FILENAME.fullmatch(filename):
            continue
        if not isinstance(function, str) or not _IDENT.fullmatch(function):
            continue
        if not isinstance(lineno, int) or isinstance(lineno, bool) or not 1 <= lineno <= 1000000:
            continue
        result.append({"filename": filename, "function": function, "lineno": lineno, "in_app": True})
    return result


def _without_attachments(hint):
    if hint is None:
        return True
    if not isinstance(hint, dict):
        return False
    attachments = hint.get("attachments")
    return attachments is None or (type(attachments) in (list, tuple) and len(attachments) == 0)


def before_send(event, hint):
    if not isinstance(event, dict) or not _without_attachments(hint):
        return None
    exception = event.get("exception")
    values = exception.get("values") if isinstance(exception, dict) else None
    if not isinstance(values, list):
        return None
    safe_values = []
    for value in values[-10:]:
        if not isinstance(value, dict) or not isinstance(value.get("type"), str) or value["type"] not in _APPROVED_ERRORS:
            continue
        safe = {"type": value["type"]}
        frames = _frames(value)
        if frames:
            safe["stacktrace"] = {"frames": frames}
        safe_values.append(safe)
    if not safe_values:
        return None
    result = _base(event)
    result["exception"] = {"values": safe_values}
    result["level"] = "error"
    return result


def before_send_transaction(event, hint):
    if not isinstance(event, dict) or not _without_attachments(hint):
        return None
    trace = event.get("contexts", {}).get("trace", {}) if isinstance(event.get("contexts"), dict) else {}
    if not isinstance(trace, dict):
        return None
    trace_id, span_id = trace.get("trace_id"), trace.get("span_id")
    if not (isinstance(trace_id, str) and _HEX.fullmatch(trace_id)
            and isinstance(span_id, str) and _SPAN.fullmatch(span_id)):
        return None
    start, end = _timestamp(event.get("start_timestamp")), _timestamp(event.get("timestamp"))
    if start is None or end is None or start > end:
        return None
    result = _base(event)
    result.update(type="transaction", transaction="[redacted]", start_timestamp=start, timestamp=end,
                  contexts={"trace": {"trace_id": trace_id, "span_id": span_id}})
    return result
