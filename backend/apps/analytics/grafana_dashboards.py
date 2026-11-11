"""Decision 263: the starter Grafana dashboards, one per area, over the curated views only.

Every query names a view of the catalogue (never a table) through ``{schema}``, which the
bundle fills with the space schema or the platform schema. Money covers charges and the
finance ledger and never payouts. An area appears only while its module is on for the space
(the platform bundle carries every area); ``MODULE`` names that switch, ``None`` is core.
"""

AREAS = ("inventory", "machines", "events", "bookings", "money", "membership")
MODULE = {"inventory": None, "machines": "machines", "events": "events", "bookings": "bookings",
          "money": None, "membership": "membership"}
TITLES = {"inventory": "Inventory and loans", "machines": "Machines", "events": "Events",
          "bookings": "Bookings", "money": "Money", "membership": "Membership"}


def _stat(title, sql):
    return ("stat", title, sql, "table")


def _series(title, sql):
    return ("timeseries", title, sql, "time_series")


def _table(title, sql):
    return ("table", title, sql, "table")


def _per_day(view, column, value="count(*)", where=""):
    extra = f" AND {where}" if where else ""
    return (f"SELECT date_trunc('day', {column}) AS time, {value} AS value FROM {{schema}}.{view} "
            f"WHERE $__timeFilter({column}){extra} GROUP BY 1 ORDER BY 1")


def _by(view, column, value="count(*)", where=""):
    clause = f" WHERE {where}" if where else ""
    return f"SELECT {column}, {value} AS value FROM {{schema}}.{view}{clause} GROUP BY 1 ORDER BY 2 DESC"


PANELS = {
    "inventory": (
        _stat("Items in the catalogue", "SELECT count(*) FROM {schema}.inventory_products WHERE NOT is_archived"),
        _stat("Units out on loan", "SELECT coalesce(sum(issued_quantity), 0) FROM {schema}.inventory_products"),
        _series("Borrow requests per day", _per_day("loan_requests", "created_at")),
        _table("Borrow requests by state", _by("loan_requests", "status")),
    ),
    "machines": (
        _stat("Machines in use", "SELECT count(*) FROM {schema}.machines WHERE is_active"),
        _series("Machine jobs per day", _per_day("machine_jobs", "created_at")),
        _series("Machine hours per day", _per_day("machine_usage", "started_at", "sum(duration_minutes) / 60.0")),
        _table("Machine jobs by state", _by("machine_jobs", "status")),
    ),
    "events": (
        _stat("Upcoming events", "SELECT count(*) FROM {schema}.events WHERE starts_at > now()"),
        _series("Registrations per day", _per_day("event_registrations", "created_at")),
        _table("Registrations by state", _by("event_registrations", "status")),
    ),
    "bookings": (
        _series("Bookings per day", _per_day("bookings", "starts_at")),
        _series("Booked hours per day", _per_day("bookings", "starts_at", "sum(duration_minutes) / 60.0")),
        _table("Bookings by state", _by("bookings", "status")),
    ),
    "money": (
        _series("Ledger money in per day", _per_day("finance_ledger", "entry_date", "sum(amount)",
                                                    "kind = 'receipt' AND NOT is_void")),
        _series("Ledger expenses per day", _per_day("finance_ledger", "entry_date", "sum(amount)",
                                                    "kind = 'expense' AND NOT is_void")),
        _table("Charges by state and currency",
               "SELECT status, currency, count(*) AS charges, sum(amount) AS amount FROM {schema}.payments "
               "GROUP BY 1, 2 ORDER BY 1, 2"),
    ),
    "membership": (
        _stat("People with a membership", "SELECT count(*) FROM {schema}.members"),
        _series("New members per day", _per_day("members", "created_at")),
        _table("Membership terms by state", _by("membership_terms", "status")),
    ),
}


def _panel(number, spec, datasource, schema):
    kind, title, sql, fmt = spec
    width = 6 if kind == "stat" else 12
    return {
        "id": number, "type": kind, "title": title,
        "gridPos": {"h": 4 if kind == "stat" else 8, "w": width, "x": 0, "y": number * 8},
        "datasource": datasource,
        "fieldConfig": {"defaults": {}, "overrides": []}, "options": {},
        "targets": [{"refId": "A", "datasource": datasource, "editorMode": "code", "rawQuery": True,
                     "format": fmt, "rawSql": sql.format(schema=schema)}],
    }


def dashboard(area, *, uid, datasource, schema, label):
    """One importable Grafana dashboard model (schemaVersion 39) for an area."""
    panels = [_panel(number, spec, datasource, schema) for number, spec in enumerate(PANELS[area], start=1)]
    return {
        "uid": uid, "title": f"SpaceWorks {label}: {TITLES[area]}", "tags": ["spaceworks", area],
        "timezone": "browser", "schemaVersion": 39, "editable": True, "refresh": "",
        "time": {"from": "now-30d", "to": "now"}, "panels": panels,
    }
