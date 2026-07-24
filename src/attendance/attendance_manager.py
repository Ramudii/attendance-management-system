"""Attendance Processing Logic
Author: Member 6 - Attendance Processing
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd


class AttendanceManager:
    """Manages attendance processing and recording"""

    def __init__(self, db_manager):
        self.db = db_manager
        self.logger = logging.getLogger(__name__)

        self.date_patterns = [
            r'(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})',
            r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{2,4})',
            r'(\d{2,4})[./-](\d{1,2})[./-](\d{1,2})',
        ]

        self.months = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }

    def parse_date(self, date_str: str) -> str:
        """Parse date from various formats."""
        if not date_str:
            return datetime.now().strftime('%Y-%m-%d')

        date_str = date_str.strip()

        for pattern in self.date_patterns:
            match = re.search(pattern, date_str, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    if len(groups[0]) == 4:
                        year, month, day = groups
                    elif len(groups[2]) == 4:
                        day, month, year = groups
                        try:
                            month = int(month)
                        except ValueError:
                            month = self.months.get(month[:3].lower(), 1)
                    else:
                        if int(groups[0]) > 12:
                            day, month, year = groups
                        else:
                            month, day, year = groups
                    day = int(day)
                    month = int(month)
                    year = int(year)
                    if year < 100:
                        year = 2000 + year if year < 30 else 1900 + year
                    return f"{year:04d}-{month:02d}-{day:02d}"
        self.logger.warning(f"Could not parse date: {date_str}, using current date")
        return datetime.now().strftime('%Y-%m-%d')

    def display_progress(self, step: str, current: int, total: int) -> None:
        """Display progress for attendance processing."""
        message = f"[Attendance] Step {current}/{total}: {step}"
        self.logger.info(message)
        print(message)

    def map_students(
        self,
        extracted_students: List[Dict[str, Any]],
        master_students: Dict[str, Dict[str, Any]],
        signature_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Map extracted student rows to the master student list."""
        self.display_progress('Mapping students to master list', 1, 5)
        signature_lookup = {
            result['student_no']: result.get('signature_present', False)
            for result in signature_results or []
        }
        attendance_records: List[Dict[str, Any]] = []
        for student_no, student_info in master_students.items():
            extracted = next(
                (s for s in extracted_students if s.get('student_no') == student_no),
                None
            )
            if extracted:
                signature_present = signature_lookup.get(student_no, False)
                status = 'Present' if signature_present else 'Absent'
            else:
                status = 'Absent'
                self.logger.debug(f"Student {student_no} missing from extracted sheet")
            attendance_records.append({
                'student_no': student_no,
                'name': student_info.get('name', 'Unknown'),
                'title': student_info.get('title', ''),
                'status': status,
                'found_in_ocr': extracted is not None,
                'signature_present': signature_lookup.get(student_no, False)
            })
        self.logger.info(f"Mapped {len(attendance_records)} attendance records")
        return attendance_records

    def record_attendance(
        self,
        image_path: str,
        xml_path: str,
        extracted_data: Dict[str, Any],
        signature_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Record attendance and save the results in the database."""
        self.display_progress('Starting attendance recording', 1, 5)
        from src.ocr.ocr_extractor import OCRExtractor
        ocr = OCRExtractor()
        master_students = ocr.parse_info_xml(xml_path)
        self.display_progress('Master list loaded', 2, 5)
        attendance_records = self.map_students(
            extracted_data.get('students', []),
            master_students,
            signature_results,
        )
        date_str = extracted_data.get('header', {}).get('date', '')
        lecture_date = self.parse_date(date_str)
        lecturer_name = extracted_data.get('header', {}).get('lecturer', 'Unknown')
        self.display_progress('Saving attendance records to database', 3, 5)
        for record in attendance_records:
            if hasattr(self.db, 'attendance_exists'):
                exists = self.db.attendance_exists(
                    student_no=record['student_no'],
                    lecture_date=lecture_date,
                )
                if exists:
                    self.logger.debug(f"Skipping duplicate attendance for {record['student_no']} on {lecture_date}")
                    continue
            self.db.insert_student(
                record['student_no'],
                record['name'],
                record['title']
            )
            self.db.insert_attendance(
                student_no=record['student_no'],
                lecture_date=lecture_date,
                status=record['status'],
                lecturer_name=lecturer_name,
                image_filename=image_path
            )
        self.display_progress('Attendance records saved', 4, 5)
        self.logger.info(f"Recorded {len(attendance_records)} attendance records")
        self.display_progress('Attendance processing completed', 5, 5)
        return attendance_records

    def generate_summary(self, attendance_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics for attendance results."""
        self.display_progress('Generating attendance summary', 5, 5)
        total = len(attendance_records)
        if total == 0:
            return {
                'total_students': 0,
                'present': 0,
                'absent': 0,
                'attendance_rate': 0,
                'details': []
            }
        present_count = sum(1 for a in attendance_records if a.get('status') == 'Present')
        absent_count = total - present_count
        return {
            'total_students': total,
            'present': present_count,
            'absent': absent_count,
            'attendance_rate': (present_count / total) * 100,
            'details': attendance_records
        }

    def get_student_attendance_summary(self, student_no: str) -> Dict[str, Any]:
        """Get an individual student's attendance summary."""
        student = self.db.get_student(student_no)
        if not student:
            return {'error': f'Student {student_no} not found'}
        df = self.db.get_student_attendance(student_no)
        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame(df)
        if df.empty:
            return {
                'student': student,
                'total_lectures': 0,
                'present': 0,
                'absent': 0,
                'attendance_rate': 0,
                'records': []
            }
        total = len(df)
        present = len(df[df['status'] == 'Present'])
        absent = total - present
        return {
            'student': student,
            'total_lectures': total,
            'present': present,
            'absent': absent,
            'attendance_rate': (present / total) * 100,
            'records': df.to_dict('records')
        }

    def generate_console_display(self, summary: Dict[str, Any]) -> str:
        """Create a formatted console display for attendance summary."""
        lines = [
            '=' * 60,
            'ATTENDANCE SUMMARY',
            '=' * 60,
            f"Total Students: {summary['total_students']}",
            f"Present: {summary['present']} ✅",
            f"Absent: {summary['absent']} ❌",
            f"Attendance Rate: {summary['attendance_rate']:.1f}%",
            '=' * 60,
            '\n📋 Details:',
            '-' * 60,
            f"{'Student No':<12} {'Name':<30} {'Status':<10}",
            '-' * 60,
        ]
        for record in summary.get('details', []):
            status_icon = '✅' if record.get('status') == 'Present' else '❌'
            lines.append(
                f"{record.get('student_no', ''):<12} "
                f"{record.get('name', '')[:29]:<30} "
                f"{status_icon} {record.get('status', ''):<10}"
            )
        lines.append('=' * 60)
        return '\n'.join(lines)
