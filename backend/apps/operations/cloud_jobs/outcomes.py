"""Domain sweeps may report isolated failures instead of raising on the first row."""


class TaskReportedFailure(Exception):
    pass


def require_success(result):
    if isinstance(result, dict) and type(result.get("failed")) is int and result["failed"] > 0:
        raise TaskReportedFailure()
    return result
