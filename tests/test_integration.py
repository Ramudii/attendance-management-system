"""
Integration Tests — full attendance pipeline
Author: Member 9 - Testing & QA
Task: 9.5

Wires the real modules together end-to-end:
    OCRExtractor.extract_sheet_data()
        -> SignatureDetector.detect()
        -> AttendanceManager.record_attendance()
        -> AttendanceManager.generate_summary()

Unlike the unit tests (which test each module in isolation with mocks/
synthetic data), these tests exercise the actual seams between modules
using one of the real signing sheets in data/sample_images/.
"""

import os
import sys
import shutil
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ocr.ocr_extractor import OCRExtractor
from src.detection.signature_detector import SignatureDetector
from src.attendance.attendance_manager import AttendanceManager
from src.database.database_manager import DatabaseManager

IMAGE_PATH = 'data/sample_images/1.jpeg'
XML_PATH = 'data/info.xml'


@pytest.fixture(scope='module')
def db_path():
    """Isolated, throwaway database file for this test module only."""
    tmp_dir = tempfile.mkdtemp()
    path = os.path.join(tmp_dir, 'integration_test.db')
    yield path
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture(scope='module')
def pipeline_result(db_path):
    """Run the full pipeline once and share the result across tests
    in this module (each real sheet takes a few seconds to process)."""
    ocr = OCRExtractor()
    extracted = ocr.extract_sheet_data(IMAGE_PATH, XML_PATH)

    detector = SignatureDetector()
    detection = detector.detect(IMAGE_PATH, extracted['students'])

    db = DatabaseManager(db_path=db_path)
    manager = AttendanceManager(db_manager=db)

    attendance = manager.record_attendance(
        IMAGE_PATH, XML_PATH, extracted, detection['results']
    )
    summary = manager.generate_summary(attendance.get('records', []))

    return {
        'extracted': extracted,
        'detection': detection,
        'attendance': attendance,
        'summary': summary,
        'manager': manager,
    }


class TestFullPipeline:
    """End-to-end pipeline against a real signing sheet."""

    def test_ocr_extraction_succeeds(self, pipeline_result):
        extracted = pipeline_result['extracted']
        assert extracted['success'] is True
        assert len(extracted['students']) > 0
        assert 'lecturer' in extracted['header']

    def test_signature_detection_succeeds(self, pipeline_result):
        detection = pipeline_result['detection']
        assert detection['success'] is True
        assert len(detection['results']) > 0
        for result in detection['results']:
            assert 'student_no' in result
            assert 'signature_present' in result

    def test_attendance_recording_succeeds(self, pipeline_result):
        attendance = pipeline_result['attendance']
        assert attendance['success'] is True, attendance.get('error')
        assert len(attendance.get('records', [])) > 0

    def test_summary_matches_record_count(self, pipeline_result):
        summary = pipeline_result['summary']
        attendance = pipeline_result['attendance']
        assert summary['total_students'] == len(attendance['records'])
        assert summary['present'] + summary['absent'] == summary['total_students']
        assert 0.0 <= summary['attendance_rate'] <= 100.0

    def test_records_were_persisted_to_database(self, pipeline_result, db_path):
        db = DatabaseManager(db_path=db_path)
        records = pipeline_result['attendance']['records']
        first_student_no = records[0]['student_no']
        df = db.get_student_attendance(first_student_no)
        assert not df.empty


class TestPipelineEdgeCases:
    """Failure paths across module boundaries (Task 9.7 candidates)."""

    def test_missing_image_is_handled(self):
        detector = SignatureDetector()
        result = detector.detect('data/sample_images/does_not_exist.jpeg', [])
        assert result['success'] is False

    def test_missing_xml_falls_back_to_default_metadata(self, db_path):
        """OCRExtractor doesn't raise for a missing XML — it logs a warning
        and generates default metadata instead. This test documents that
        as intentional graceful-degradation behaviour."""
        ocr = OCRExtractor()
        extracted = ocr.extract_sheet_data(IMAGE_PATH, 'data/does_not_exist.xml')
        assert extracted['success'] is True
        assert extracted['students'] == [] or isinstance(extracted['students'], list)

    def test_empty_signature_results_all_marked_absent(self, db_path):
        ocr = OCRExtractor()
        extracted = ocr.extract_sheet_data(IMAGE_PATH, XML_PATH)

        db = DatabaseManager(db_path=db_path)
        manager = AttendanceManager(db_manager=db)

        attendance = manager.record_attendance(
            IMAGE_PATH, XML_PATH, extracted, signature_results=[]
        )
        assert attendance['success'] is True
        assert all(r['status'] == 'Absent' for r in attendance['records'])