"""Attendance Processing Logic

Author: Member 5 - Attendance Processing (Ashan Madusanka)
Responsibility: Manage attendance workflow, date parsing, student mapping, and database integration

This module orchestrates the complete attendance processing pipeline:
1. Parse lecture metadata and student information (from OCR)
2. Map signature detection results to master student list
3. Validate and enrich attendance data
4. Record results to database for visualization

Integrates with:
- OCRExtractor (Member 3): Provides student data and lecture metadata
- SignatureDetector (Member 4): Provides signature detection results
- DatabaseManager (Member 6): Stores attendance records
"""

import logging
import re
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    import pandas as pd
except ImportError:
    pd = None


class AttendanceManager:
    """Manages complete attendance processing and recording workflow.
    
    Orchestrates the pipeline from raw signature detection results through
    to stored attendance records in the database.
    """

    def __init__(self, db_manager: Optional[Any] = None, 
                 logger: Optional[logging.Logger] = None) -> None:
        """Initialize the attendance manager.
        
        Args:
            db_manager: Database manager instance for persistence
            logger: Optional logger instance. Creates one if not provided.
        """
        self.db = db_manager
        self.logger = logger or logging.getLogger(__name__)

        # Date parsing patterns for various formats
        self.date_patterns = [
            r'(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})',  # DD/MM/YYYY or DD-MM-YYYY
            r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{2,4})',     # DD Month YYYY
            r'(\d{2,4})[./-](\d{1,2})[./-](\d{1,2})',   # YYYY/MM/DD
        ]

        # Month name to number mapping
        self.months = {
            'jan': 1, 'january': 1,
            'feb': 2, 'february': 2,
            'mar': 3, 'march': 3,
            'apr': 4, 'april': 4,
            'may': 5,
            'jun': 6, 'june': 6,
            'jul': 7, 'july': 7,
            'aug': 8, 'august': 8,
            'sep': 9, 'september': 9,
            'oct': 10, 'october': 10,
            'nov': 11, 'november': 11,
            'dec': 12, 'december': 12
        }
    
    def parse_date(self, date_str: str) -> str:
        """Parse date string from various formats to YYYY-MM-DD.
        
        Supports formats like:
        - DD/MM/YYYY or DD-MM-YYYY
        - DD Month YYYY (e.g., 10 August 2026)
        - YYYY/MM/DD or YYYY-MM-DD
        
        Args:
            date_str: Date string in various formats
            
        Returns:
            Parsed date in YYYY-MM-DD format, or current date if parsing fails
        """
        if not date_str:
            return datetime.now().strftime('%Y-%m-%d')

        date_str = date_str.strip()

        # Try each pattern
        for pattern in self.date_patterns:
            match = re.search(pattern, date_str, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    try:
                        day, month, year = None, None, None
                        
                        # Determine format based on group positions
                        if len(groups[0]) == 4:  # YYYY at start
                            year, month, day = groups
                        elif len(groups[2]) == 4:  # YYYY at end
                            # Check if middle group is month name or number
                            day, month, year = groups
                            try:
                                month = int(month)
                            except ValueError:
                                month = self.months.get(str(month)[:3].lower(), 1)
                        else:  # Determine from magnitude
                            if int(groups[0]) > 12:
                                day, month, year = groups
                            else:
                                month, day, year = groups
                        
                        # Convert to integers
                        day = int(day)
                        month = int(month) if isinstance(month, int) else self.months.get(str(month)[:3].lower(), 1)
                        year = int(year)
                        
                        # Handle 2-digit years
                        if year < 100:
                            year = 2000 + year if year < 30 else 1900 + year
                        
                        # Validate ranges
                        if 1 <= month <= 12 and 1 <= day <= 31 and year >= 1900:
                            return f'{year:04d}-{month:02d}-{day:02d}'
                    
                    except (ValueError, TypeError) as e:
                        self.logger.debug(f'Error parsing date: {e}')
                        continue
        
        self.logger.warning(f'Could not parse date: {date_str}, using current date')
        return datetime.now().strftime('%Y-%m-%d')
    
    def display_progress(self, step: str, current: int, total: int) -> None:
        """Display progress message for attendance processing.
        
        Args:
            step: Description of current step
            current: Current step number
            total: Total number of steps
        """
        message = f'[Attendance] Step {current}/{total}: {step}'
        self.logger.info(message)
        print(message)
    
    def map_students(self,
                    extracted_students: List[Dict[str, Any]],
                    master_students: Dict[str, Dict[str, Any]],
                    signature_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Map extracted student rows to master student list and signature results.
        
        Matches students from signature detection results with the master student list
        from XML, enriching with OCR extracted data.
        
        Args:
            extracted_students: Students found in OCR extraction
            master_students: Master student list from XML (keyed by student_no)
            signature_results: Signature detection results from SignatureDetector
            
        Returns:
            List of attendance records with complete student information
        """
        self.display_progress('Mapping students to master list', 1, 4)
        
        # Build lookup for signature results
        signature_lookup = {
            result['student_no']: {
                'signature_present': result.get('signature_present', False),
                'confidence': result.get('confidence', 0.0),
                'metrics': result.get('metrics', {}),
                'row_index': result.get('row_index', -1),
            }
            for result in (signature_results or [])
        }
        
        attendance_records: List[Dict[str, Any]] = []
        
        for student_no, student_info in master_students.items():
            # Find if student was in OCR extraction
            extracted = next(
                (s for s in extracted_students if s.get('student_no') == student_no),
                None
            )
            
            # Get signature detection results
            sig_data = signature_lookup.get(student_no, {})
            signature_present = sig_data.get('signature_present', False)
            
            # Determine attendance status
            status = 'Present' if signature_present else 'Absent'
            
            if not extracted:
                self.logger.debug(f'Student {student_no} not found in OCR extraction')
            
            # Build comprehensive attendance record
            record = {
                'student_no': student_no,
                'name': student_info.get('name', 'Unknown'),
                'title': student_info.get('title', 'Mr/Ms'),
                'status': status,
                'found_in_ocr': extracted is not None,
                'signature_present': signature_present,
                'confidence': sig_data.get('confidence', 0.0),
                'metrics': sig_data.get('metrics', {}),
                'row_index': sig_data.get('row_index', -1),
                'processing_timestamp': datetime.now().isoformat(),
            }
            attendance_records.append(record)
        
        self.logger.info(f'Mapped {len(attendance_records)} students to attendance records')
        return attendance_records
    
    def validate_records(self, records: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """Validate attendance records for required fields and data integrity.
        
        Args:
            records: List of attendance records to validate
            
        Returns:
            Tuple of (is_valid: bool, errors: List[str])
        """
        errors = []
        required_fields = ['student_no', 'name', 'status', 'signature_present']
        valid_statuses = ['Present', 'Absent']
        
        for i, record in enumerate(records):
            # Check required fields
            for field in required_fields:
                if field not in record:
                    errors.append(f'Record {i}: Missing required field "{field}"')
            
            # Check status validity
            if record.get('status') not in valid_statuses:
                errors.append(f'Record {i}: Invalid status "{record.get("status")}"')
            
            # Check confidence range
            confidence = record.get('confidence', 0)
            if not (0 <= confidence <= 1):
                errors.append(f'Record {i}: Confidence out of range: {confidence}')
        
        if errors:
            for error in errors:
                self.logger.error(error)
        else:
            self.logger.info(f'Validation passed for {len(records)} records')
        
        return len(errors) == 0, errors
    
    def record_attendance(self,
                         image_path: str,
                         xml_path: str,
                         extracted_data: Dict[str, Any],
                         signature_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Record attendance to database with complete workflow.
        
        Args:
            image_path: Path to the processed image
            xml_path: Path to the XML student list
            extracted_data: OCR extracted data (with header and students)
            signature_results: Signature detection results
            
        Returns:
            Dictionary with recording status and results
        """
        self.display_progress('Starting attendance recording workflow', 1, 4)
        
        try:
            # Import OCR for parsing master student list
            from src.ocr.ocr_extractor import OCRExtractor
            ocr = OCRExtractor(logger=self.logger)
            master_students = ocr.parse_info_xml(xml_path)
            
            self.display_progress('Master student list loaded', 2, 4)
            
            # Map students
            attendance_records = self.map_students(
                extracted_data.get('students', []),
                master_students,
                signature_results,
            )
            
            # Validate records
            is_valid, errors = self.validate_records(attendance_records)
            if not is_valid:
                return {
                    'success': False,
                    'error': 'Validation failed',
                    'validation_errors': errors,
                    'records': attendance_records
                }
            
            # Extract metadata
            header = extracted_data.get('header', {})
            date_str = header.get('date', '')
            lecture_date = self.parse_date(date_str)
            lecturer_name = header.get('lecturer', 'Unknown')
            module = header.get('module', 'Unknown')
            
            self.display_progress('Saving attendance records to database', 3, 4)
            
            # Save to database
            saved_count = 0
            if self.db:
                for record in attendance_records:
                    try:
                        # Check for duplicates if db supports it
                        if hasattr(self.db, 'attendance_exists'):
                            exists = self.db.attendance_exists(
                                student_no=record['student_no'],
                                lecture_date=lecture_date,
                            )
                            if exists:
                                self.logger.debug(
                                    f'Skipping duplicate: {record["student_no"]} on {lecture_date}'
                                )
                                continue
                        
                        # Insert student record
                        self.db.insert_student(
                            record['student_no'],
                            record['name'],
                            record.get('title', 'Mr/Ms')
                        )
                        
                        # Insert attendance record
                        self.db.insert_attendance(
                            student_no=record['student_no'],
                            lecture_date=lecture_date,
                            status=record['status'],
                            lecturer_name=lecturer_name,
                            module=module,
                            image_filename=image_path,
                            confidence=record.get('confidence', 0.0),
                        )
                        saved_count += 1
                    except Exception as e:
                        self.logger.error(f'Error recording attendance for {record["student_no"]}: {e}')
                        continue
                
                self.logger.info(f'Successfully recorded {saved_count}/{len(attendance_records)} records')
            else:
                saved_count = len(attendance_records)
            
            self.display_progress('Attendance recording completed', 4, 4)
            
            return {
                'success': True,
                'saved_count': saved_count,
                'total_count': len(attendance_records),
                'lecture_date': lecture_date,
                'lecturer': lecturer_name,
                'module': module,
                'records': attendance_records
            }
        
        except Exception as e:
            self.logger.error(f'Error in attendance recording: {e}')
            return {
                'success': False,
                'error': str(e),
            }
    
    def generate_summary(self, attendance_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics for attendance results.
        
        Args:
            attendance_records: List of processed attendance records
            
        Returns:
            Dictionary with summary statistics
        """
        if not attendance_records:
            return {
                'total_students': 0,
                'present': 0,
                'absent': 0,
                'attendance_rate': 0.0,
                'average_confidence': 0.0,
                'details': []
            }
        
        total = len(attendance_records)
        present_count = sum(1 for a in attendance_records if a.get('status') == 'Present')
        absent_count = total - present_count
        avg_confidence = sum(a.get('confidence', 0) for a in attendance_records) / total
        
        return {
            'total_students': total,
            'present': present_count,
            'absent': absent_count,
            'attendance_rate': round((present_count / total) * 100, 2),
            'average_confidence': round(avg_confidence, 4),
            'details': attendance_records
        }
    
    def get_student_attendance_summary(self, student_no: str) -> Dict[str, Any]:
        """Get an individual student's attendance summary from database.
        
        Args:
            student_no: Student ID to query
            
        Returns:
            Dictionary with student attendance statistics
        """
        if not self.db:
            return {'error': 'Database manager not available'}
        
        try:
            student = self.db.get_student(student_no) if hasattr(self.db, 'get_student') else None
            attendance_data = self.db.get_student_attendance(student_no)
            
            # Handle different return types
            if isinstance(attendance_data, list):
                records = attendance_data
            elif pd and isinstance(attendance_data, pd.DataFrame):
                records = attendance_data.to_dict('records')
            else:
                records = []
            
            if not records:
                return {
                    'student': student,
                    'total_lectures': 0,
                    'present': 0,
                    'absent': 0,
                    'attendance_rate': 0.0,
                    'records': []
                }
            
            total = len(records)
            present = sum(1 for r in records if r.get('status') == 'Present')
            absent = total - present
            
            return {
                'student': student,
                'total_lectures': total,
                'present': present,
                'absent': absent,
                'attendance_rate': round((present / total) * 100, 2),
                'records': records
            }
        
        except Exception as e:
            self.logger.error(f'Error retrieving attendance for {student_no}: {e}')
            return {'error': str(e)}
    
    def generate_console_display(self, summary: Dict[str, Any]) -> str:
        """Create a formatted console display for attendance summary.
        
        Args:
            summary: Summary dictionary from generate_summary()
            
        Returns:
            Formatted string for console output
        """
        lines = [
            '=' * 70,
            'ATTENDANCE PROCESSING SUMMARY',
            '=' * 70,
            f"Total Students: {summary.get('total_students', 0)}",
            f"Present: {summary.get('present', 0)} ✅",
            f"Absent: {summary.get('absent', 0)} ❌",
            f"Attendance Rate: {summary.get('attendance_rate', 0):.1f}%",
            f"Average Confidence: {summary.get('average_confidence', 0):.4f}",
            '=' * 70,
        ]
        
        details = summary.get('details', [])
        if details:
            lines.extend([
                '📋 Detailed Attendance:',
                '-' * 70,
                f"{'Student No':<15} {'Name':<30} {'Status':<10} {'Conf':<8}",
                '-' * 70,
            ])
            
            for record in details:
                status_icon = '✅' if record.get('status') == 'Present' else '❌'
                lines.append(
                    f"{record.get('student_no', ''):<15} "
                    f"{record.get('name', '')[:29]:<30} "
                    f"{status_icon} {record.get('status', ''):<10} "
                    f"{record.get('confidence', 0):.4f}"
                )
        
        lines.append('=' * 70)
        return '\n'.join(lines)
