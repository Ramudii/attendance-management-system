import re
from typing import Dict, Any, Optional


class DataCleaner:

    @staticmethod
    def clean_student_no(raw_id: str) -> str:
        if not raw_id:
            return ""

        # Remove surrounding whitespace and non-alphanumeric noise
        cleaned = str(raw_id).strip()

        # Fix common OCR misreads (letter O/o -> number 0 in numeric IDs)
        # Match pattern where letter O is surrounded by digits or at start of numbers
        cleaned = re.sub(r'^[Oo](\d+)', r'0\1', cleaned)
        cleaned = re.sub(r'(\d+)[Oo](\d+)', r'\1 0\2', cleaned)

        # Extract core alphanumeric digits
        digits = re.findall(r'\d+', cleaned)
        if digits:
            num_str = "".join(digits)
            # Standardize 1 to 3 digit indices (e.g. 1 -> 001)
            if len(num_str) <= 3:
                return num_str.zfill(3)
            return num_str

        # If purely alphabetical/custom index, clean characters
        cleaned = re.sub(r'[^a-zA-Z0-9]', '', cleaned)
        return cleaned

    @staticmethod
    def clean_name(raw_name: str) -> str:
        if not raw_name:
            return ""

        # Remove noise characters (punctation except spaces/hyphens)
        cleaned = re.sub(r'[^a-zA-Z\s\-]', '', raw_name)
        # Collapse multiple whitespaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        # Title case standard names
        return cleaned.title()

    @staticmethod
    def clean_text(raw_text: str) -> str:
        if not raw_text:
            return ""

        # Replace newlines/tabs with spaces
        cleaned = raw_text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        # Remove unusual ASCII control characters
        cleaned = re.sub(r'[\x00-\x1F\x7F]', '', cleaned)
        # Collapse multiple spaces
        return re.sub(r'\s+', ' ', cleaned).strip()

    @staticmethod
    def clean_header(header_dict: Dict[str, Any]) -> Dict[str, Any]:
        cleaned_header = {}
        for key, val in header_dict.items():
            if isinstance(val, str):
                cleaned_header[key] = DataCleaner.clean_text(val)
            else:
                cleaned_header[key] = val
        return cleaned_header
