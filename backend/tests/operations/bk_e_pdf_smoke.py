"""Run with ReportLab installed; no Django/database required."""
from pathlib import Path
from apps.operations.reports_booking_pdf import render_pdf


class Provenance:
    def items(self):
        return [("generated_by", "qa-staff"), ("makerspace_id", "1"),
                ("report_key", "booking-resource-utilization-pdf"),
                ("filters", '{"subject_kind":"bookable_space","subject_id":5,"timezone":"Asia/Kolkata"}')]


if __name__ == "__main__":
    target = Path(__file__).with_name(".bk-e-pdf-smoke.pdf")
    target.write_bytes(render_pdf([["space_name", "reserved_hours"],
        ["Caf\u00e9 \u03b1 - " + "Long resource name " * 9, "4.00"]],
        provenance=Provenance(), title="Resource reservation utilization"))
    print(target)
