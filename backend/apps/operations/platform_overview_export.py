"""CSV of the platform overview (#183A): one long row per figure, totals beside the breakdown.

Columns: block, metric, label, unit, timing, scope (space | total | platform), space id,
space name, currency, value. Space names pass through the formula-injection guard every
report export uses; no person data exists in the overview to export.
"""

import csv
from io import StringIO

from apps.operations.report_exports import _export_cell

HEADER = ("block", "metric", "label", "unit", "timing", "scope", "makerspace_id", "makerspace", "currency", "value")


def overview_rows(data):
    names = {space["id"]: space["name"] for space in data["spaces"]}
    for block in data["blocks"]:
        metrics = block["metrics"]
        for row in block["rows"]:
            for metric in metrics:
                value = None if row["values"] is None else row["values"].get(metric["key"])
                yield _row(block, metric, "space", row["makerspace_id"], names, "", "off" if row["values"] is None else value)
        for metric in metrics:
            yield _row(block, metric, "total", None, names, "", block["totals"].get(metric["key"]))
        for metric in block["platform_metrics"]:
            yield _row(block, metric, "platform", None, names, "", metric["value"])
    money = data.get("money")
    if money:
        for entry in money["currencies"]:
            for row in entry["rows"]:
                yield from _money(money, entry["currency"], "space", row["makerspace_id"], names, row)
            yield from _money(money, entry["currency"], "total", None, names, entry["totals"])
    for module in data["modules"]:
        yield ("modules", module["key"], module["label"], "count", "snapshot", "total", "", "", "", module["on_in"])


def _row(block, metric, scope, space_id, names, currency, value):
    return (block["key"], metric["key"], metric["label"], metric["unit"], metric["timing"], scope,
            "" if space_id is None else space_id, names.get(space_id, ""), currency, "" if value is None else value)


def _money(money, currency, scope, space_id, names, figures):
    for metric in money["metrics"]:
        value = figures["charges"] if metric["key"] == "charges" else figures["amounts"][metric["key"]]
        yield _row(money, metric, scope, space_id, names, currency, value)


def overview_csv(data):
    buffer = StringIO()
    writer = csv.writer(buffer)
    window = data["window"]
    starts = window["starts_at"].isoformat() if window["starts_at"] else "all-time"
    buffer.write(f"# SpaceWorks platform overview period={window['preset']} from={starts} "
                 f"to={window['ends_at'].isoformat()} include_excluded={str(data['include_excluded']).lower()}\r\n")
    writer.writerow(HEADER)
    count = 0
    for row in overview_rows(data):
        writer.writerow([_export_cell(value) for value in row])
        count += 1
    return buffer.getvalue(), count
