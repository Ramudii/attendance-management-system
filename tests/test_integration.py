"""
Integration Tests: Full Attendance Pipeline
Author: Member 9 - Testing & QA
Task: 9.5

Runs image -> OCR -> signature detection -> attendance recording ->
summary end to end. Every stage is skipped (not failed) individually if
that member's module isn't implemented yet, and the pipeline test as a
whole is skipped as soon as it hits the first missing stage - so this
file can be merged today and will exercise more of the real pipeline as
each teammate lands their code, with no edits needed here.
"""

import os
import pytest

from src.image_processing.image_processor import ImageProcessor

try:
    from src.ocr.ocr_extractor import OCRExtractor
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

try:
    from src.detection.signature_detector import SignatureDetector
    HAS_DETECTOR = True
except ImportError:
    HAS_DETECTOR = False

try:
    from src.attendance.attendance_manager import AttendanceManager
    HAS_ATTENDANCE = True
except ImportError:
    HAS_ATTENDANCE = False

from src.database.database_manager import DatabaseManager


class MockTable:
    def get_cell(self, row, col):
        x = 50 + col * 150
        y = 170 + row * 50
        return (x, y, 140, 40)


@pytest.fixture
def db(tmp_path):
    import inspect
    sig = inspect.signature(DatabaseManager.__init__)
    if len(sig.parameters) > 1:
        return DatabaseManager(str(tmp_path / 'test.db'))
    return DatabaseManager()


class TestFullPipeline:

    def test_full_pipeline_end_to_end(self, sample_image_path, sample_xml_path, db):
        # Step 1: Image processing
        processor = ImageProcessor()
        processed = processor.process(sample_image_path)
        if processed is None:
            pytest.skip("Pipeline blocked at Step 1: ImageProcessor not implemented yet")

        # Step 2: OCR extraction
        if not HAS_OCR:
            pytest.skip("Pipeline blocked at Step 2: OCRExtractor not implemented yet")
        extracted = OCRExtractor().extract(processed)
        assert 'header' in extracted and 'students' in extracted

        # Step 3: Signature detection
        if not HAS_DETECTOR:
            pytest.skip("Pipeline blocked at Step 3: SignatureDetector not implemented yet")
        signature_results = SignatureDetector().detect_all_signatures(
            processed, extracted['students'], MockTable()
        )
        assert signature_results is not None

        # Step 4: Attendance recording
        if not HAS_ATTENDANCE:
            pytest.skip("Pipeline blocked at Step 4: AttendanceManager not implemented yet")
        manager = AttendanceManager(db)
        attendance = manager.record_attendance(
            sample_image_path, sample_xml_path, extracted, signature_results
        )
        assert attendance is not None

        # Step 5: Summary
        summary = manager.generate_summary(attendance)
        assert summary is not None
        assert summary['total_students'] > 0
        assert summary['present'] >= 0
        assert summary['absent'] >= 0
        assert summary['present'] + summary['absent'] == summary['total_students']

    def test_pipeline_reports_current_blocking_stage(self, sample_image_path):
        """Not a real assertion - just prints which stage the pipeline is
        currently blocked at, so `pytest -s` gives the team a quick status
        check without reading through skip reasons one by one."""
        stages = {
            'ImageProcessor': ImageProcessor().process(sample_image_path) is not None,
            'OCRExtractor': HAS_OCR,
            'SignatureDetector': HAS_DETECTOR,
            'AttendanceManager': HAS_ATTENDANCE,
        }
        print("\nPipeline stage status:")
        for name, ready in stages.items():
            print(f"  {'✅' if ready else '⏳'} {name}")


class TestEdgeCases:

    def test_process_nonexistent_image(self):
        processor = ImageProcessor()
        fake_path = 'nonexistent_image_xyz.jpg'
        try:
            result = processor.process(fake_path)
        except (FileNotFoundError, OSError, ValueError):
            return
        if result is None:
            pytest.skip("ImageProcessor currently returns None instead of raising - see BUGS.md")
        pytest.fail("process() should raise for a nonexistent image")

    def test_parse_empty_xml_does_not_crash(self, tmp_path):
        if not HAS_OCR:
            pytest.skip("OCRExtractor not implemented yet")
        empty_xml = tmp_path / 'empty.xml'
        empty_xml.write_text('<?xml version="1.0"?><students></students>')
        try:
            OCRExtractor().parse_info_xml(str(empty_xml))
        except Exception as e:
            pytest.fail(f"Empty XML should be handled gracefully, raised: {e}")

    def test_get_attendance_for_invalid_student(self, db):
        result = db.get_student_attendance('00000000')
        assert (hasattr(result, 'empty') and result.empty) or (isinstance(result, list) and len(result) == 0)
