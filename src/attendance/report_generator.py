"""Report generation for attendance data.

Author: Member 5 - Attendance Processing (Ashan Madusanka)
Responsibility: Generate attendance summaries and detailed reports for visualization and database

Generates:
- Summary reports (totals, rates)
- Detailed attendance lists
- Statistics and confidence metrics
- Export-ready formats (JSON, CSV)
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime


class ReportGenerator:
    """Generate comprehensive attendance reports from processed records.
    
    Produces both summary statistics and detailed per-student reports,
    supporting multiple export formats for database storage and visualization.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        """Initialize the report generator.
        
        Args:
            logger: Optional logger instance. Creates one if not provided.
        """
        self.reports: List[Dict[str, Any]] = []
        self.logger = logger or logging.getLogger(__name__)

    def generate_summary(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a comprehensive summary report from attendance records.
        
        Args:
            records: List of attendance records from AttendanceProcessor
            
        Returns:
            Summary dictionary containing:
            - total_students: Total number of students
            - present: Count of present students
            - absent: Count of absent students
            - attendance_rate: Percentage of students present
            - average_confidence: Average detection confidence
            - ocr_coverage: Percentage found in OCR extraction
            - generated_at: Timestamp of report generation
        """
        if not records:
            self.logger.warning("No records provided for summary generation")
            return self._empty_summary()
        
        total = len(records)
        present = sum(1 for r in records if str(r.get("status", "")).lower() == "present")
        absent = total - present
        avg_confidence = sum(r.get("confidence", 0) for r in records) / total if total > 0 else 0
        ocr_found = sum(1 for r in records if r.get("found_in_ocr", False))
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_students": total,
            "present": present,
            "absent": absent,
            "attendance_rate": round((present / total * 100) if total > 0 else 0, 2),
            "average_confidence": round(avg_confidence, 4),
            "ocr_coverage": round((ocr_found / total * 100) if total > 0 else 0, 2),
        }
        
        self.reports.append(summary)
        self.logger.info(f"Generated summary report: {present}/{total} present ({summary['attendance_rate']}%)")
        return summary
    
    def generate_detailed_report(self, records: List[Dict[str, Any]], 
                                lecture_date: Optional[str] = None,
                                lecturer: Optional[str] = None) -> Dict[str, Any]:
        """Generate a detailed per-student attendance report.
        
        Args:
            records: List of processed attendance records
            lecture_date: Date of the lecture
            lecturer: Name of the lecturer
            
        Returns:
            Detailed report with per-student information
        """
        summary = self.generate_summary(records)
        
        detailed = {
            "summary": summary,
            "lecture_info": {
                "date": lecture_date or "Unknown",
                "lecturer": lecturer or "Unknown",
            },
            "students": [
                {
                    "student_id": r.get("student_id"),
                    "name": r.get("name"),
                    "status": r.get("status"),
                    "confidence": r.get("confidence"),
                    "signature_present": r.get("signature_present"),
                    "found_in_ocr": r.get("found_in_ocr"),
                }
                for r in records
            ]
        }
        
        return detailed
    
    def export_to_json(self, records: List[Dict[str, Any]], 
                      output_path: str,
                      lecture_date: Optional[str] = None,
                      lecturer: Optional[str] = None) -> bool:
        """Export attendance records to JSON file.
        
        Args:
            records: List of attendance records
            output_path: Path to save JSON file
            lecture_date: Optional lecture date
            lecturer: Optional lecturer name
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            detailed_report = self.generate_detailed_report(records, lecture_date, lecturer)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(detailed_report, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Successfully exported attendance report to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export JSON report: {e}")
            return False
    
    def export_to_csv(self, records: List[Dict[str, Any]], 
                     output_path: str,
                     lecture_date: Optional[str] = None,
                     lecturer: Optional[str] = None) -> bool:
        """Export attendance records to CSV file.
        
        Args:
            records: List of attendance records
            output_path: Path to save CSV file
            lecture_date: Optional lecture date
            lecturer: Optional lecturer name
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            import csv
            
            if not records:
                self.logger.warning("No records to export to CSV")
                return False
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['student_id', 'name', 'status', 'confidence', 
                            'signature_present', 'found_in_ocr']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                writer.writeheader()
                if lecture_date:
                    writer.writerow({'student_id': f'Date: {lecture_date}'})
                if lecturer:
                    writer.writerow({'student_id': f'Lecturer: {lecturer}'})
                
                for record in records:
                    writer.writerow({
                        'student_id': record.get('student_id'),
                        'name': record.get('name'),
                        'status': record.get('status'),
                        'confidence': record.get('confidence'),
                        'signature_present': record.get('signature_present'),
                        'found_in_ocr': record.get('found_in_ocr'),
                    })
            
            self.logger.info(f"Successfully exported attendance report to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export CSV report: {e}")
            return False
    
    def _empty_summary(self) -> Dict[str, Any]:
        """Return an empty summary structure.
        
        Returns:
            Empty summary dictionary
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "total_students": 0,
            "present": 0,
            "absent": 0,
            "attendance_rate": 0.0,
            "average_confidence": 0.0,
            "ocr_coverage": 0.0,
        }
