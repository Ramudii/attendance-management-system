"""
Unit tests for OCR & Text Extraction Module
Author: Member 3 - OCR & Text Extraction
"""

import os
import sys
import unittest
import tempfile

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ocr.xml_parser import XMLParser
from src.ocr.data_cleaner import DataCleaner
from src.ocr.ocr_extractor import OCRExtractor


class TestOCRModule(unittest.TestCase):

    def test_data_cleaner_student_no(self):
        """Test student index cleaning and normalization."""
        self.assertEqual(DataCleaner.clean_student_no("  001. "), "001")
        self.assertEqual(DataCleaner.clean_student_no("O07"), "007")
        self.assertEqual(DataCleaner.clean_student_no("1"), "001")
        self.assertEqual(DataCleaner.clean_student_no("009"), "009")
        self.assertEqual(DataCleaner.clean_student_no(""), "")

    def test_data_cleaner_name(self):
        """Test student name cleaning and capitalization."""
        self.assertEqual(DataCleaner.clean_name("  john   snow! "), "John Snow")
        self.assertEqual(DataCleaner.clean_name("JAMES BOND"), "James Bond")
        self.assertEqual(DataCleaner.clean_name("andare"), "Andare")

    def test_data_cleaner_text(self):
        """Test general raw OCR text cleaning."""
        self.assertEqual(DataCleaner.clean_text("Hello\nWorld\t!"), "Hello World !")

    def test_xml_parser_sample_creation_and_parse(self):
        """Test sample XML creation and parsing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            xml_file = os.path.join(tmp_dir, 'info.xml')
            parser = XMLParser()

            # Create sample XML
            success = parser.create_sample_xml(xml_file)
            self.assertTrue(success)
            self.assertTrue(os.path.exists(xml_file))

            # Parse generated XML
            data = parser.parse(xml_file)
            self.assertIn('header', data)
            self.assertIn('students', data)
            self.assertEqual(len(data['students']), 3)
            self.assertIn('001', data['students'])
            self.assertEqual(data['students']['001']['name'], 'John Snow')

    def test_ocr_extractor_parse_info_xml(self):
        """Test OCRExtractor parse_info_xml integration."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            xml_file = os.path.join(tmp_dir, 'info.xml')
            extractor = OCRExtractor()
            extractor.xml_parser.create_sample_xml(xml_file)

            students = extractor.parse_info_xml(xml_file)
            self.assertIsInstance(students, dict)
            self.assertIn('001', students)
            self.assertEqual(students['001']['name'], 'John Snow')
            self.assertEqual(students['007']['name'], 'James Bond')
            self.assertEqual(students['009']['name'], 'Andare')

    def test_ocr_extractor_extract_sheet_data(self):
        """Test OCRExtractor extract_sheet_data structure."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            xml_file = os.path.join(tmp_dir, 'info.xml')
            extractor = OCRExtractor()
            extractor.xml_parser.create_sample_xml(xml_file)

            result = extractor.extract_sheet_data('dummy_image.png', xml_file)
            self.assertTrue(result['success'])
            self.assertIn('header', result)
            self.assertIn('students', result)
            self.assertEqual(len(result['students']), 3)


if __name__ == '__main__':
    unittest.main()
