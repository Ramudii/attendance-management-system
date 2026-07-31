"""
System Test: All 5 Real Signing Sheets
Author: Member 9 - Testing & QA
Task: 9.6

Runs the pipeline against every real scanned sheet in
data/sample_images/ (1.jpeg - 5.jpeg) and writes a report to
tests/test_results/sample_sheets_report.json.

Requires a real info.xml next to the images (data/info.xml) - whoever
owns the sample data should add one. Until then this is skipped with a
clear message rather than failing the build.
"""

import os
import json
import pytest

from src.image_processing.image_processor import ImageProcessor

try:
    from src.ocr.ocr_extractor import OCRExtractor
    HAS_OCR = True
except ImportError:
    HAS_OCR = False


INFO_XML = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'data', 'info.xml')
)
RESULTS_DIR = os.path.join(os.path.dirname(__file__), 'test_results')


@pytest.mark.skipif(not HAS_OCR, reason="OCRExtractor not implemented yet")
@pytest.mark.skipif(not os.path.exists(INFO_XML), reason=f"Missing {INFO_XML} - add the real student roster XML")
class TestAllSampleSheets:

    def test_process_every_sample_sheet(self, real_sample_images):
        os.makedirs(RESULTS_DIR, exist_ok=True)
        processor = ImageProcessor()
        extractor = OCRExtractor()

        report = {}
        for image_path in real_sample_images:
            name = os.path.basename(image_path)
            try:
                processed = processor.process(image_path)
                if processed is None:
                    report[name] = {'status': 'skipped', 'reason': 'ImageProcessor not implemented'}
                    continue
                extracted = extractor.extract(processed)
                report[name] = {
                    'status': 'ok',
                    'students_found': len(extracted.get('students', [])),
                    'header': extracted.get('header'),
                }
            except Exception as e:
                report[name] = {'status': 'error', 'error': str(e)}

        with open(os.path.join(RESULTS_DIR, 'sample_sheets_report.json'), 'w') as f:
            json.dump(report, f, indent=2, default=str)

        errors = {k: v for k, v in report.items() if v['status'] == 'error'}
        assert not errors, f"Errors while processing sample sheets: {errors}"
