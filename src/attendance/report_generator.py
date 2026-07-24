"""Report generation helpers for attendance data."""

from typing import Any, Dict, List


class ReportGenerator:
    """Generate simple summary reports from attendance records."""

    def __init__(self) -> None:
        self.reports: List[Dict[str, Any]] = []

    def generate_summary(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a basic summary report."""
        total = len(records)
        present = sum(1 for r in records if str(r.get("status", "")).lower() == "present")
        absent = total - present

        summary = {
            "total_students": total,
            "present": present,
            "absent": absent,
        }
        self.reports.append(summary)
        return summary
