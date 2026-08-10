"""Attendance processing utilities.

Author: Member 5 - Attendance Processing (Ashan Madusanka)
Responsibility: Normalize and process attendance records from signature detection and OCR
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime


class AttendanceProcessor:
    """Process raw attendance records from signature detection into structured format.
    
    Takes the results from signature detection and OCR extraction, normalizes them,
    and creates a standardized attendance record format for database storage.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        """Initialize the attendance processor.
        
        Args:
            logger: Optional logger instance. Creates one if not provided.
        """
        self.processed_records: List[Dict[str, Any]] = []
        self.logger = logger or logging.getLogger(__name__)

    def process(self, signature_results: List[Dict[str, Any]], 
                ocr_data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Normalize signature detection results into attendance records.
        
        Args:
            signature_results: List of detection results from SignatureDetector.
                Each record should contain:
                - row_index: Position in the sheet
                - student_no: Student ID
                - name: Student name
                - signature_present: Boolean presence detection
                - confidence: Confidence score (0-1)
                - metrics: Detailed ink analysis metrics
            ocr_data: Optional OCR extracted data for enrichment
            
        Returns:
            List of normalized attendance records with keys:
            - student_id: Unique student identifier
            - name: Student name
            - status: 'Present' or 'Absent'
            - signature_present: Boolean from detection
            - confidence: Detection confidence score
            - timestamp: Processing timestamp
            - metrics: Raw detection metrics
            - found_in_ocr: Whether student found in OCR extraction
        """
        self.processed_records = []
        self.logger.info(f"Processing {len(signature_results)} signature detection results")
        
        if not signature_results:
            self.logger.warning("No signature results provided for processing")
            return self.processed_records

        for result in signature_results:
            try:
                normalized = self._normalize_record(result, ocr_data)
                self.processed_records.append(normalized)
            except Exception as e:
                self.logger.error(f"Error processing record for {result.get('student_no')}: {e}")
                continue

        self.logger.info(f"Successfully processed {len(self.processed_records)} records")
        return self.processed_records
    
    def _normalize_record(self, detection_result: Dict[str, Any], 
                         ocr_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Normalize a single detection result into standard format.
        
        Args:
            detection_result: Single result from SignatureDetector
            ocr_data: Optional OCR data for enrichment
            
        Returns:
            Normalized attendance record
        """
        student_no = detection_result.get("student_no", "")
        signature_present = detection_result.get("signature_present", False)
        confidence = detection_result.get("confidence", 0.0)
        
        # Determine attendance status based on signature detection
        status = "Present" if signature_present else "Absent"
        
        # Check if student was found in OCR extraction
        found_in_ocr = True
        if ocr_data and ocr_data.get('students'):
            ocr_students = ocr_data.get('students', {})
            found_in_ocr = student_no in ocr_students
        
        normalized = {
            "student_id": student_no,
            "name": detection_result.get("name", "Unknown"),
            "status": status,
            "signature_present": signature_present,
            "confidence": round(float(confidence), 4),
            "timestamp": datetime.now().isoformat(),
            "metrics": detection_result.get("metrics", {}),
            "found_in_ocr": found_in_ocr,
            "row_index": detection_result.get("row_index", -1),
        }
        
        return normalized
    
    def validate_records(self) -> bool:
        """Validate all processed records for required fields.
        
        Returns:
            True if all records are valid, False otherwise
        """
        required_fields = ['student_id', 'name', 'status', 'signature_present']
        
        for i, record in enumerate(self.processed_records):
            for field in required_fields:
                if field not in record:
                    self.logger.error(f"Record {i} missing required field: {field}")
                    return False
                    
            if record['status'] not in ['Present', 'Absent']:
                self.logger.error(f"Record {i} has invalid status: {record['status']}")
                return False
        
        self.logger.info(f"Validation passed for {len(self.processed_records)} records")
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get summary statistics of processed records.
        
        Returns:
            Dictionary with attendance statistics
        """
        if not self.processed_records:
            return {
                'total': 0,
                'present': 0,
                'absent': 0,
                'attendance_rate': 0.0,
                'avg_confidence': 0.0
            }
        
        total = len(self.processed_records)
        present = sum(1 for r in self.processed_records if r['status'] == 'Present')
        absent = total - present
        avg_confidence = sum(r.get('confidence', 0) for r in self.processed_records) / total if total > 0 else 0
        
        return {
            'total': total,
            'present': present,
            'absent': absent,
            'attendance_rate': round((present / total) * 100, 2) if total > 0 else 0.0,
            'avg_confidence': round(avg_confidence, 4)
        }
