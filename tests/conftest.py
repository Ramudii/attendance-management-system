"""
Shared pytest fixtures for the SAMS test suite
Author: Member 9 - Testing & QA

These fixtures build a synthetic signing-sheet image and a matching
info.xml so every test module (preprocessing, OCR, detection, database,
integration) can share the exact same test data instead of re-creating it.
"""

import os
import sys
import tempfile
import shutil
import numpy as np
import cv2
import pytest

# Make "src.xxx" importable no matter where pytest is invoked from
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Ground-truth student list used across all tests. Keep this in one place
# so every test module (and the OCR / detection modules once they exist)
# agree on what "correct" looks like.
TEST_STUDENTS = [
    ('1', '10000409', 'Ms', 'M S Dilshanika Perera', True),
    ('2', '10009301', 'Mr', 'C W M A Shehan Abeyrathne', True),
    ('3', '10009302', 'Mr', 'B A K M Chithrananda', False),
    ('4', '10009303', 'Ms', 'W Shashini Minosha De Silva', True),
    ('5', '10009304', 'Mr', 'K L Udara Maduranga Liyanage', False),
    ('6', '10009306', 'Mr', 'Hansa Anuradha Wickramanayake', True),
]


@pytest.fixture(scope="session")
def test_data_dir():
    """A temp directory that lives for the whole test session."""
    d = tempfile.mkdtemp(prefix="sams_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(scope="session")
def sample_image_path(test_data_dir):
    """Builds a synthetic signing sheet so tests don't depend on OCR
    working on the real scanned images in data/sample_images/."""
    path = os.path.join(test_data_dir, 'synthetic_sheet.jpg')

    img = np.full((600, 800, 3), 255, dtype=np.uint8)

    cv2.putText(img, 'DATE: 12.07.2019', (50, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    cv2.putText(img, 'Lecture Name: DR. Rasika', (50, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

    headers = ['No', 'Student No', 'Title', 'Student Name', 'Signature']
    for i, header in enumerate(headers):
        cv2.putText(img, header, (50 + i * 150, 130),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

    for i, (no, student_no, title, name, has_sig) in enumerate(TEST_STUDENTS):
        y = 170 + i * 50
        cv2.putText(img, no, (50, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        cv2.putText(img, student_no, (150, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        cv2.putText(img, title, (300, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        cv2.putText(img, name[:20], (400, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        if has_sig:
            cv2.putText(img, 'Sig', (600, y), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 0.5, (0, 0, 0), 1)

    cv2.imwrite(path, img)
    return path


@pytest.fixture(scope="session")
def sample_xml_path(test_data_dir):
    """Matching info.xml for the synthetic sheet."""
    path = os.path.join(test_data_dir, 'info.xml')

    students_xml = "\n".join(
        f"""    <student>
        <student_number>{sno}</student_number>
        <title>{title}</title>
        <name>{name}</name>
    </student>"""
        for (_no, sno, title, name, _sig) in TEST_STUDENTS
    )

    xml_content = f'<?xml version="1.0" encoding="UTF-8"?>\n<students>\n{students_xml}\n</students>'

    with open(path, 'w') as f:
        f.write(xml_content)
    return path


@pytest.fixture(scope="session")
def ground_truth_signatures():
    """student_no -> whether they actually signed, from TEST_STUDENTS."""
    return {sno: has_sig for (_no, sno, _title, _name, has_sig) in TEST_STUDENTS}


@pytest.fixture
def real_sample_images():
    """Paths to the 5 real scanned signing sheets in data/sample_images/,
    used by the 'test on all 5 signing sheets' task (9.6)."""
    base = os.path.join(os.path.dirname(__file__), '..', 'data', 'sample_images')
    base = os.path.abspath(base)
    if not os.path.isdir(base):
        pytest.skip(f"data/sample_images not found at {base}")
    images = sorted(
        os.path.join(base, f) for f in os.listdir(base)
        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
    )
    if not images:
        pytest.skip("No sample images found in data/sample_images/")
    return images
