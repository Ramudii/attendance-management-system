"""Attendance processing utilities."""

from typing import Any, Dict, List


class AttendanceProcessor:
    """Process raw attendance records into a structured format."""

    def __init__(self) -> None:
        self.processed_records: List[Dict[str, Any]] = []

    def process(self, raw_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize attendance records into a consistent structure."""
        self.processed_records = []

        for record in raw_records:
            normalized = {
                "student_id": record.get("student_id"),
                "name": record.get("name", "Unknown"),
                "status": record.get("status", "present"),
                "timestamp": record.get("timestamp"),
            }
            self.processed_records.append(normalized)

        return self.processed_records
