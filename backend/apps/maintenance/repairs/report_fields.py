"""Columns of the repairs report family (RP-5).

Kept apart from the builders so the operations registry can declare the reports without
importing the repairs authority at registry load.
"""

WORK_ORDER_FIELDS = ("work_order_id", "area", "subject_type", "subject_name", "machine_type", "title", "priority",
                     "status", "due_on", "overdue", "days_open", "assigned", "issue_id", "created_at")
WORKLOAD_FIELDS = ("technician", "technician_kind", "open_jobs", "in_progress", "overdue", "fixed_in_period")
REPAIR_TIME_FIELDS = ("area", "machine_type", "reported", "fixed", "open", "average_hours_to_fix",
                      "median_hours_to_fix")
PARTS_FIELDS = ("area", "kind", "part", "product_id", "quantity", "issues", "last_recorded_at")
