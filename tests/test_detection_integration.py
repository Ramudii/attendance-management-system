"""Integration tests: signature detection against the OCR and image-processing modules.

These tests cover the seams between Member 4's detection module and the modules
either side of it, rather than the detection logic itself (see test_detection.py
for that).

Author: Heshan De Silva - Signature Detection
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run_detection import DEFAULT_STUDENTS, load_students
from src.detection import SignatureDetector
from src.image_processing.image_processor import ImageProcessor

INFO_XML = 'data/info.xml'
SHEET = 'data/sample_images/4.jpeg'

# Ground truth read off the printed sheets by eye.
EXPECTED_PRESENT = {
    'data/sample_images/1.jpeg': 6,
    'data/sample_images/2.jpeg': 6,
    'data/sample_images/3.jpeg': 4,
    'data/sample_images/4.jpeg': 4,
    'data/sample_images/5.jpeg': 6,
}

needs_xml = pytest.mark.skipif(
    not os.path.exists(INFO_XML), reason='data/info.xml not available')
needs_sheet = pytest.mark.skipif(
    not os.path.exists(SHEET), reason='sample sheets not available')


class TestRosterFromOCRModule:
    """The roster must come from info.xml via the OCR module's parser."""

    @needs_xml
    def test_loads_six_students(self):
        assert len(load_students(INFO_XML)) == 6

    @needs_xml
    def test_preserves_sheet_order(self):
        numbers = [s['student_no'] for s in load_students(INFO_XML)]
        assert numbers == [
            '10000409', '10009301', '10009302',
            '10009303', '10009304', '10009306',
        ]

    @needs_xml
    def test_names_survive_cleaning(self):
        # DataCleaner.clean_name strips punctuation and title-cases; the roster
        # must still be recognisable afterwards.
        names = [s['name'] for s in load_students(INFO_XML)]
        assert names[0] == 'M S Dilshanika Perera'
        assert 'Wickramanayake' in names[5]

    def test_falls_back_when_xml_missing(self):
        assert load_students('data/does_not_exist.xml') == DEFAULT_STUDENTS

    def test_falls_back_on_empty_roster(self, tmp_path):
        empty = tmp_path / 'empty.xml'
        empty.write_text('<?xml version="1.0"?><attendance_info></attendance_info>')
        assert load_students(str(empty)) == DEFAULT_STUDENTS


class TestDetectionWithOCRRoster:
    """End-to-end: info.xml roster driving detection on the real sheets."""

    @needs_xml
    @needs_sheet
    def test_every_row_is_labelled(self):
        students = load_students(INFO_XML)
        outcome = SignatureDetector(save_progress=False).detect(SHEET, students=students)

        assert outcome['success']
        assert len(outcome['results']) == 6
        assert all(r['student_no'] for r in outcome['results'])

    @needs_xml
    @needs_sheet
    @pytest.mark.parametrize('sheet,expected', sorted(EXPECTED_PRESENT.items()))
    def test_present_counts_match_ground_truth(self, sheet, expected):
        if not os.path.exists(sheet):
            pytest.skip(f'{sheet} not available')

        students = load_students(INFO_XML)
        outcome = SignatureDetector(save_progress=False).detect(sheet, students=students)

        assert outcome['success']
        present = sum(1 for r in outcome['results'] if r['signature_present'])
        assert present == expected


class TestPreprocessingDelegation:
    """Loading and thresholding must go through the image-processing module."""

    def test_builds_a_processor_by_default(self):
        assert isinstance(SignatureDetector(save_progress=False).processor,
                          ImageProcessor)

    def test_accepts_an_injected_processor(self):
        processor = ImageProcessor(save_progress_images=False)
        detector = SignatureDetector(save_progress=False, processor=processor)
        assert detector.processor is processor

    @needs_sheet
    def test_delegates_load_and_threshold(self):
        """A spying processor proves the delegate is really on the hot path."""
        calls = []

        class SpyProcessor(ImageProcessor):
            def load_image(self, path):
                calls.append('load_image')
                return super().load_image(path)

            def convert_to_grayscale(self, image):
                calls.append('convert_to_grayscale')
                return super().convert_to_grayscale(image)

            def remove_noise(self, image, method='median', kernel_size=5):
                calls.append(f'remove_noise:{method}')
                return super().remove_noise(image, method, kernel_size)

            def apply_thresholding(self, gray, method='otsu', block_size=11, constant=2):
                calls.append(f'apply_thresholding:{method}')
                return super().apply_thresholding(gray, method, block_size, constant)

        spy = SpyProcessor(save_progress_images=False)
        outcome = SignatureDetector(save_progress=False, processor=spy).detect(SHEET)

        assert outcome['success']
        assert 'load_image' in calls
        assert 'convert_to_grayscale' in calls
        assert 'remove_noise:bilateral' in calls
        assert 'apply_thresholding:adaptive' in calls

    @needs_sheet
    def test_binarize_returns_white_ink(self):
        """Downstream morphology needs ink as the white foreground.

        ImageProcessor.apply_thresholding emits black-ink-on-white, so binarize
        must invert it. Paper dominates the page, hence ink stays a minority of
        the pixels.
        """
        detector = SignatureDetector(save_progress=False)
        binary = detector.binarize(detector.load_image(SHEET))

        assert set(np.unique(binary)).issubset({0, 255})
        white_fraction = (binary == 255).mean()
        assert 0.0 < white_fraction < 0.5

    @needs_sheet
    def test_progress_buffers_do_not_leak_across_sheets(self):
        """The delegate caches every intermediate; detect() must reset it."""
        detector = SignatureDetector(save_progress=False)
        detector.detect(SHEET)
        after_first = len(detector.processor.progress_images)
        detector.detect(SHEET)
        assert len(detector.processor.progress_images) == after_first

    def test_missing_file_still_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            SignatureDetector(save_progress=False).load_image('data/nope.jpeg')

    def test_unsupported_format_is_reported_as_unreadable(self, tmp_path):
        """ImageProcessor raises ValueError; detect() only handles FileNotFoundError."""
        bogus = tmp_path / 'sheet.txt'
        bogus.write_text('not an image')
        with pytest.raises(FileNotFoundError):
            SignatureDetector(save_progress=False).load_image(str(bogus))


class TestImageProcessorROIContract:
    """The detector must accept whatever ROIs the preprocessing module emits.

    NOTE: ImageProcessor.extract_signature_cells currently returns an unreliable
    number of cells on the real photographs (3-71 instead of 6), so these tests
    assert the *contract* holds - no crashes, one result per ROI - rather than a
    particular count. Detection therefore uses its own deskew-and-grid stage in
    SignatureDetector.detect(); this path is kept working so it can take over
    once the preprocessing ROI bug is fixed.
    """

    @needs_sheet
    def test_accepts_rois_from_image_processor(self):
        processed = ImageProcessor(save_progress_images=False).process(SHEET)
        rois = processed['signature_cells']

        results = SignatureDetector(save_progress=False).detect_signatures(rois)

        assert len(results) == len(rois)
        assert all('signature_present' in r for r in results)
        assert all(0.0 <= r['confidence'] <= 1.0 for r in results)

    def test_accepts_grayscale_colour_and_binary_rois(self):
        blank = np.full((40, 200), 255, dtype=np.uint8)
        colour = np.full((40, 200, 3), 255, dtype=np.uint8)
        binary = np.zeros((40, 200), dtype=np.uint8)

        results = SignatureDetector(save_progress=False).detect_signatures(
            [blank, colour, binary])

        assert len(results) == 3

    def test_handles_empty_roi_list(self):
        assert SignatureDetector(save_progress=False).detect_signatures([]) == []

    @needs_xml
    def test_attaches_roster_to_rois(self):
        students = load_students(INFO_XML)
        rois = [np.full((40, 200), 255, dtype=np.uint8) for _ in range(6)]

        results = SignatureDetector(save_progress=False).detect_signatures(
            rois, students=students)

        assert [r['student_no'] for r in results] == [
            s['student_no'] for s in students]
