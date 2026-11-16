"""Additive inventory metrics with rate recomputation and explicit dimensions."""

from functools import lru_cache


# Tenant-owned product/asset IDs remain dimensions: matching labels are not identities.
GROUPS = {
    "most-lent": ("period", "product_id", "product_name"),
    "asset-usage": ("asset_id", "product_id", "product_name"),
    "loan-throughput": ("period",),
    "inventory-utilisation": ("row_kind", "period", "product_id", "product_name", "asset_id"),
    "damaged-lost": ("product_id", "product_name"),
    "stock-health": ("row_kind", "period", "product_id", "product_name"),
    "request-funnel": ("period", "row_kind", "stage", "approval_bucket"),
    "problem-reports": ("period",),
    "inventory-watch-demand": ("product_id", "product_name"),
    "summary": (),
    "qr-scans": ("period", "context", "target_type", "target_id", "hour_of_week"),
    "inventory-control": ("period", "module_key", "metric_key", "dimension"),
    "consumable-usage": ("period", "source", "material", "measurement_unit", "currency"),
    "consumable-pools": ("pool_id", "material", "measurement_unit"),
    "procurement-performance": ("period", "kind", "status", "item_id", "item_name", "lead_time_bucket", "currency"),
    "stock-transfers": ("period", "source_makerspace_id", "destination_makerspace_id", "status"),
    "stocktake-variance": ("period", "product_id", "asset_id", "item_label"),
}
RATES = {
    "asset-usage": (("utilisation_percent", "days_on_loan", "window_days", 100),),
    "inventory-utilisation": (("utilisation_percent", "issued_quantity", "total_quantity", 100),),
    "damaged-lost": (("damage_rate_percent", "damaged_quantity", "total_quantity", 100),
                     ("loss_rate_percent", "lost_quantity", "total_quantity", 100)),
    "problem-reports": (("average_resolution_hours", "resolution_hours", "resolved_count", 1),),
    "inventory-control": (("rate_percent", "rate_numerator", "rate_denominator", 100),),
    "consumable-pools": (("depletion_percent", "_depleted_quantity", "initial_quantity", 100),),
    "procurement-performance": (("average_order_hours", "order_hours", "order_samples", 1),
                                ("average_receive_hours", "receive_hours", "receive_samples", 1)),
}


@lru_cache(maxsize=None)
def combine_for(key):
    def combine(rows_by_space, *, limit):
        from apps.operations.report_definitions_ab import AB_REPORT_DEFINITIONS
        definition = next(d for d in AB_REPORT_DEFINITIONS if d.key == key)
        dimensions = GROUPS[key]
        computed = {rate[0] for rate in RATES.get(key, ())}
        numeric = set(definition.fields) - set(dimensions) - computed - {"last_activity_at", "makerspace_id"}
        groups = {}
        for _, rows in rows_by_space:
            for source in rows:
                group = tuple(source.get(field) for field in dimensions)
                row = groups.setdefault(group, {field: source.get(field) for field in dimensions})
                for field in numeric:
                    value = source.get(field)
                    if value is not None:
                        row[field] = row.get(field, 0) + value
                if key == "consumable-pools":
                    row["_depleted_quantity"] = row.get("_depleted_quantity", 0) + (
                        source["initial_quantity"] - source["remaining_quantity"])
                if source.get("last_activity_at") is not None:
                    row["last_activity_at"] = max(row.get("last_activity_at") or source["last_activity_at"], source["last_activity_at"])
        for row in groups.values():
            for field, numerator, denominator, factor in RATES.get(key, ()):
                if key == "inventory-utilisation" and row.get("row_kind") == "asset":
                    numerator, denominator = "days_on_loan", "window_days"
                n, d = row.get(numerator, 0), row.get(denominator, 0)
                row[field] = round(float(n / d * factor), 2) if d else None
            row.pop("_depleted_quantity", None)
        rows = sorted(groups.values(), key=lambda row: tuple(str(row.get(field) or "") for field in dimensions))
        ranks = {"most-lent": "total_quantity_lent", "asset-usage": "times_lent",
                 "inventory-watch-demand": "waiting_count", "procurement-performance": "units"}
        if key in ranks:
            rows.sort(key=lambda row: -(row.get(ranks[key]) or 0))
        if key == "stocktake-variance":
            rows.sort(key=lambda row: -abs(row.get("variance_quantity") or 0))
        return rows if limit is None else rows[:limit]
    return combine


def install_strategies(strategies, factory, kinds):
    from apps.operations.report_definitions_ab import AB_REPORT_DEFINITIONS
    for definition in AB_REPORT_DEFINITIONS:
        if not definition.identity_bearing:
            strategies[definition.key] = factory(kinds.WEIGHTED_RATE if definition.key in RATES else kinds.GROUP_SUM,
                GROUPS[definition.key], definition.fields, ordering=GROUPS[definition.key],
                text=tuple((field, "group and carry") for field in GROUPS[definition.key]))
