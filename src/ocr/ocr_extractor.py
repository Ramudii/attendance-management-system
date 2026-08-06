import os
import logging
from typing import Dict, Any, List, Optional, Union
import numpy as np

# Optional imports for OpenCV and PyTesseract with fallback handling
try:
    import cv2
except ImportError:
    cv2 = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

from src.ocr.xml_parser import XMLParser
from src.ocr.data_cleaner import DataCleaner


class OCRExtractor:


    def __init__(self, tesseract_cmd: Optional[str] = None, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.xml_parser = XMLParser(logger=self.logger)
        self.cleaner = DataCleaner()
        self.tesseract_available = False

        if pytesseract is not None:
            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            try:
                # Test Tesseract installation
                pytesseract.get_tesseract_version()
                self.tesseract_available = True
                self.logger.info("PyTesseract initialized successfully.")
            except Exception as e:
                self.logger.warning(f"PyTesseract installation not detected ({e}). Running in fallback mode.")
        else:
            self.logger.warning("pytesseract library not installed. Running in fallback mode.")

    def parse_info_xml(self, xml_path: str) -> Dict[str, Dict[str, Any]]:
        
        parsed_data = self.xml_parser.parse(xml_path)
        students = parsed_data.get('students', {})

        # Clean student indices and names
        cleaned_students = {}
        for student_no, info in students.items():
            clean_id = self.cleaner.clean_student_no(student_no)
            clean_name = self.cleaner.clean_name(info.get('name', ''))
            cleaned_students[clean_id] = {
                'student_no': clean_id,
                'name': clean_name,
                'title': info.get('title', 'Mr/Ms')
            }

        return cleaned_students

    def extract_text_from_cell(self, cell_image: Union[np.ndarray, str], psm: int = 6) -> str:
        
        if not self.tesseract_available or pytesseract is None:
            self.logger.debug("Tesseract unavailable for cell extraction.")
            return ""

        try:
            if isinstance(cell_image, str):
                if not os.path.exists(cell_image):
                    return ""
                if cv2 is not None:
                    cell_image = cv2.imread(cell_image)

            if isinstance(cell_image, np.ndarray):
                # Preprocess cropped cell if in BGR color space
                if len(cell_image.shape) == 3 and cv2 is not None:
                    cell_image = cv2.cvtColor(cell_image, cv2.COLOR_BGR2GRAY)

                config = f'--psm {psm}'
                raw_text = pytesseract.image_to_string(cell_image, config=config)
                return self.cleaner.clean_text(raw_text)

        except Exception as e:
            self.logger.error(f"Error during Tesseract cell OCR: {e}")

        return ""

    def extract_sheet_data(self, image_path: str, xml_path: str) -> Dict[str, Any]:
        
        self.logger.info(f"Extracting sheet data from image: {image_path} and XML: {xml_path}")

        # Parse master student metadata
        master_students = self.parse_info_xml(xml_path)
        parsed_xml = self.xml_parser.parse(xml_path)

        header = self.cleaner.clean_header(parsed_xml.get('header', {}))
        student_list = list(master_students.values())

        return {
            'header': header,
            'students': student_list,
            'master_students': master_students,
            'image_path': image_path,
            'xml_path': xml_path,
            'success': True
        }
