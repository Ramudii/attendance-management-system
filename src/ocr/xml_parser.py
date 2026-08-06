import os
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional


class XMLParser:

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    def parse(self, xml_path: str) -> Dict[str, Any]:
        
        result = {
            'header': {
                'module': 'CS402.3',
                'lecturer': 'Unknown',
                'date': ''
            },
            'students': {},
            'raw_students': []
        }

        if not os.path.exists(xml_path):
            self.logger.warning(f"XML file not found: {xml_path}. Generating default metadata.")
            return result

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            # Parse Header / Lecture Metadata
            header_node = root.find('header')
            if header_node is None:
                header_node = root.find('info')
            if header_node is None:
                header_node = root.find('lecture')

            if header_node is not None:
                for child in header_node:
                    result['header'][child.tag.lower()] = (child.text or '').strip()

            # Parse Students
            students_parent = root.find('students')
            if students_parent is None:
                students_parent = root
            for elem in students_parent.iter():
                if elem.tag.lower() in ('student', 'record'):
                    student_info = self._parse_student_element(elem)
                    student_no = student_info.get('student_no')
                    if student_no:
                        result['students'][student_no] = student_info
                        result['raw_students'].append(student_info)

            # If no students found under iteration tag, try direct children of root
            if not result['students']:
                for child in root:
                    if child.tag.lower() not in ('header', 'info', 'lecture'):
                        student_info = self._parse_student_element(child)
                        student_no = student_info.get('student_no')
                        if student_no:
                            result['students'][student_no] = student_info
                            result['raw_students'].append(student_info)

            self.logger.info(f"Successfully parsed {len(result['students'])} students from {xml_path}")

        except ET.ParseError as e:
            self.logger.error(f"XML syntax error in {xml_path}: {e}")
        except Exception as e:
            self.logger.error(f"Error reading XML file {xml_path}: {e}")

        return result

    def _parse_student_element(self, elem: ET.Element) -> Dict[str, Any]:
        data = {
            'student_no': '',
            'name': '',
            'title': 'Mr/Ms'
        }

        for child in elem:
            tag = child.tag.lower()
            val = (child.text or '').strip()
            if tag in ('index', 'student_index', 'student_no', 'id', 'no', 'number'):
                data['student_no'] = val
            elif tag in ('name', 'full_name', 'student_name'):
                data['name'] = val
            elif tag in ('title', 'salutation'):
                data['title'] = val
            else:
                data[tag] = val

        # Fallback if attributes were used instead of sub-elements
        if not data['student_no']:
            data['student_no'] = elem.get('index') or elem.get('id') or elem.get('student_no') or ''
        if not data['name']:
            data['name'] = elem.get('name') or ''

        return data

    def create_sample_xml(self, output_path: str) -> bool:
    
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<attendance_info>
    <header>
        <module>CS402.3 - Computer Graphics and Visualization</module>
        <lecturer>Dr. Rasika Ranaweera</lecturer>
        <date>2026-08-06</date>
    </header>
    <students>
        <student>
            <index>001</index>
            <name>John Snow</name>
            <title>Mr</title>
        </student>
        <student>
            <index>007</index>
            <name>James Bond</name>
            <title>Mr</title>
        </student>
        <student>
            <index>009</index>
            <name>Andare</name>
            <title>Mr</title>
        </student>
    </students>
</attendance_info>
"""
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            self.logger.info(f"Sample info.xml created at: {output_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create sample info.xml at {output_path}: {e}")
            return False
