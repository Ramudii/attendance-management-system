"""
Unit Tests: OCR Extraction (Member 3's module)
Author: Member 9 - Testing & QA
Task: 9.2

NOTE FOR THE TEAM:
src/ocr/ocr_extractor.py is currently an EMPTY file - the OCRExtractor
class doesn't exist yet. Importing it will fail, so this whole module is
skipped (not failed) until Member 3 pushes an implementation with:
    class OCRExtractor:
        def extract(self, processed_image) -> dict   # {'header': {...}, 'students': [...]}
        def parse_info_xml(self, xml_path) -> list
"""

import pytest

try:
    from src.ocr.ocr_extractor import OCRExtractor
    HAS_OCR_EXTRACTOR = True
except ImportError:
    HAS_OCR_EXTRACTOR = False

pytestmark = pytest.mark.skipif(
    not HAS_OCR_EXTRACTOR,
    reason="OCRExtractor not implemented yet (src/ocr/ocr_extractor.py is empty) "
           "- Member 3, feature/ocr-extraction"
)


class TestOCRExtractorBasics:

    def test_can_instantiate(self):
        extractor = OCRExtractor()
        assert extractor is not None


class TestOCRExtraction:

    def test_extract_returns_expected_keys(self, sample_image_path):
        from src.image_processing.image_processor import ImageProcessor
        processor = ImageProcessor()
        processed = processor.process(sample_image_path)
        if processed is None:
            pytest.skip("Depends on ImageProcessor.process(), not implemented yet")

        extractor = OCRExtractor()
        extracted = extractor.extract(processed)

        assert extracted is not None
        assert 'header' in extracted
        assert 'students' in extracted

    def test_extract_finds_header_fields(self, sample_image_path):
        from src.image_processing.image_processor import ImageProcessor
        processed = ImageProcessor().process(sample_image_path)
        if processed is None:
            pytest.skip("Depends on ImageProcessor.process()")

        extracted = OCRExtractor().extract(processed)
        assert extracted['header'].get('date')
        assert extracted['header'].get('lecturer')

    def test_extract_finds_most_student_numbers(self, sample_image_path):
        """OCR won't be pixel-perfect, so we only require most rows to be found."""
        from src.image_processing.image_processor import ImageProcessor
        processed = ImageProcessor().process(sample_image_path)
        if processed is None:
            pytest.skip("Depends on ImageProcessor.process()")

        extracted = OCRExtractor().extract(processed)
        found_numbers = {s['student_no'] for s in extracted['students']}
        expected = {'10000409', '10009301', '10009302', '10009303', '10009304', '10009306'}

        overlap = found_numbers & expected
        assert len(overlap) >= len(expected) * 0.6, (
            f"Only found {len(overlap)}/{len(expected)} expected student numbers: {found_numbers}"
        )

    def test_parse_info_xml(self, sample_xml_path):
        extractor = OCRExtractor()
        students = extractor.parse_info_xml(sample_xml_path)
        assert students is not None
        assert len(students) == 6

    def test_parse_empty_info_xml_does_not_crash(self, tmp_path):
        empty_xml = tmp_path / 'empty.xml'
        empty_xml.write_text('<?xml version="1.0"?><students></students>')

        extractor = OCRExtractor()
        try:
            students = extractor.parse_info_xml(str(empty_xml))
        except Exception as e:
            pytest.fail(f"parse_info_xml should handle an empty <students/> gracefully, raised: {e}")
        assert students == [] or students is None
