"""Tests for the signature detection module.

Run with:
    python -m pytest tests/test_detection.py -v

Author: Heshan De Silva - Signature Detection
"""

import os
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.detection import (
    SignatureAnalyzer,
    SignatureDetector,
    SignatureMetrics,
    TableNotFoundError,
)

SAMPLES_DIR = os.path.join('data', 'sample_images')

STUDENTS = [
    {'student_no': '10000409', 'name': 'M S Dilshanika Perera'},
    {'student_no': '10009301', 'name': 'C W M A Shehan Abeyrathne'},
    {'student_no': '10009302', 'name': 'B A K M Chithrananda'},
    {'student_no': '10009303', 'name': 'W Shashini Minosha De Silva'},
    {'student_no': '10009304', 'name': 'K L Udara Maduranga Liyanage'},
    {'student_no': '10009306', 'name': 'Hansa Anuradha Wickramanayake'},
]

# Whether each signature cell contains handwritten ink, verified by eye against
# the five sheets in "CGV Signing Sheets.zip".
#
# Note on 2.jpeg row 6: the cell holds a hand-written "ab" annotation rather
# than a signature. Ink *is* present, so the detector correctly reports ink;
# distinguishing an annotation from a signature is outside this module's scope
# and is handled by the recognition stage (investigate.py).
INK_GROUND_TRUTH = {
    '1.jpeg': [True, True, True, True, True, True],
    '2.jpeg': [True, True, True, True, True, True],
    '3.jpeg': [True, False, False, True, True, True],
    '4.jpeg': [True, False, True, False, True, True],
    '5.jpeg': [True, True, True, True, True, True],
}


def make_cell(width=200, height=40, strokes=()):
    """Build a synthetic binary signature cell.

    Args:
        width: Cell width in pixels.
        height: Cell height in pixels.
        strokes: Iterable of ((x1, y1), (x2, y2)) line endpoints.

    Returns:
        Binary image with white ink on a black background.
    """
    cell = np.zeros((height, width), np.uint8)
    for start, end in strokes:
        cv2.line(cell, start, end, 255, 3)
    return cell


# ----------------------------------------------------------------------
# SignatureAnalyzer - unit tests
# ----------------------------------------------------------------------
class TestSignatureAnalyzer:
    """Unit tests for the ink measurement and decision logic."""

    def setup_method(self):
        self.analyzer = SignatureAnalyzer()

    def test_blank_cell_is_absent(self):
        result = self.analyzer.analyze(make_cell())
        assert result['signature_present'] is False
        assert result['metrics']['ink_ratio'] == 0.0
        assert result['confidence'] == 1.0

    def test_signed_cell_is_present(self):
        cell = make_cell(strokes=[((20, 30), (150, 10)), ((30, 10), (120, 32))])
        result = self.analyzer.analyze(cell)
        assert result['signature_present'] is True
        assert result['metrics']['ink_ratio'] > 0
        assert result['metrics']['component_count'] >= 1

    def test_single_speck_is_ignored_as_noise(self):
        cell = make_cell()
        cell[20, 100] = 255
        result = self.analyzer.analyze(cell)
        assert result['signature_present'] is False

    def test_empty_array_is_handled(self):
        result = self.analyzer.analyze(np.zeros((0, 0), np.uint8))
        assert result['signature_present'] is False

    def test_none_is_handled(self):
        result = self.analyzer.analyze(None)
        assert result['signature_present'] is False

    def test_metrics_dict_is_serialisable(self):
        metrics = self.analyzer.measure(make_cell(strokes=[((10, 20), (180, 20))]))
        data = metrics.to_dict()
        assert 'bounding_boxes' not in data
        assert isinstance(data['ink_ratio'], float)

    def test_threshold_is_configurable(self):
        cell = make_cell(strokes=[((10, 20), (40, 20))])
        strict = SignatureAnalyzer(min_ink_ratio=0.9)
        assert strict.analyze(cell)['signature_present'] is False
        assert SignatureAnalyzer().analyze(cell)['signature_present'] is True

    def test_metrics_defaults(self):
        metrics = SignatureMetrics()
        assert metrics.ink_ratio == 0.0
        assert metrics.bounding_boxes == []


# ----------------------------------------------------------------------
# SignatureDetector - unit tests
# ----------------------------------------------------------------------
class TestSignatureDetectorUnits:
    """Unit tests for the geometry helpers, without touching disk."""

    def setup_method(self):
        self.detector = SignatureDetector(save_progress=False)

    def test_missing_file_returns_failure(self):
        outcome = self.detector.detect('does/not/exist.jpeg', students=STUDENTS)
        assert outcome['success'] is False
        assert len(outcome['results']) == len(STUDENTS)
        assert all(r['signature_present'] is False for r in outcome['results'])

    def test_projection_peaks_groups_adjacent_positions(self):
        projection = np.zeros(100)
        projection[10:13] = 50
        projection[60:62] = 50
        peaks = SignatureDetector._projection_peaks(projection, 10)
        assert peaks == [11, 60]

    def test_projection_peaks_empty(self):
        assert SignatureDetector._projection_peaks(np.zeros(50), 10) == []

    def test_longest_uniform_run_finds_evenly_spaced_block(self):
        rows = [10, 100, 145, 190, 235, 280]
        start, end = SignatureDetector._longest_uniform_run(rows)
        assert rows[start:end + 1] == [100, 145, 190, 235, 280]

    def test_locate_cells_rejects_too_few_columns(self):
        with pytest.raises(TableNotFoundError):
            self.detector.locate_signature_cells([10, 50, 90], [100], None)

    def test_locate_cells_rejects_too_few_rows(self):
        with pytest.raises(TableNotFoundError):
            self.detector.locate_signature_cells([10], [100, 300], None)

    def test_locate_cells_rejects_narrow_signature_column(self):
        with pytest.raises(TableNotFoundError):
            self.detector.locate_signature_cells(
                [10, 50, 90, 130], [100, 110], None)

    def test_locate_cells_drops_header_band(self):
        rows = [0, 30, 75, 120, 165]          # header band + 3 uniform bands
        columns = [0, 200, 400]
        cells = self.detector.locate_signature_cells(rows, columns, None)
        assert len(cells) == 3
        assert all(cell[0] == 200 and cell[2] == 200 for cell in cells)

    def test_locate_cells_keeps_all_bands_when_none_is_a_header(self):
        """Equal-height bands mean the header was already excluded."""
        rows = [100, 145, 190, 235]
        columns = [0, 200, 400]
        cells = self.detector.locate_signature_cells(rows, columns, None)
        assert len(cells) == 3

    def test_drop_header_band_removes_the_shorter_first_band(self):
        bands = [(0, 30), (30, 75), (75, 120), (120, 165)]
        kept = SignatureDetector._drop_header_band(bands, None)
        assert kept == [(30, 75), (75, 120), (120, 165)]

    def test_drop_header_band_keeps_uniform_bands(self):
        bands = [(0, 45), (45, 90), (90, 135)]
        assert SignatureDetector._drop_header_band(bands, None) == bands

    def test_locate_cells_honours_expected_student_count(self):
        rows = [0, 30, 75, 120, 165]
        columns = [0, 200, 400]
        cells = self.detector.locate_signature_cells(rows, columns, expected_students=2)
        assert len(cells) == 2

    def test_deskew_is_a_no_op_for_tiny_angles(self):
        image = np.zeros((50, 50, 3), np.uint8)
        assert self.detector.deskew(image, 0.01) is image

    def test_detect_signatures_accepts_prebuilt_rois(self):
        rois = [
            make_cell(),
            make_cell(strokes=[((20, 30), (150, 10))]),
        ]
        results = self.detector.detect_signatures(rois, students=STUDENTS)
        assert [r['signature_present'] for r in results] == [False, True]
        assert results[0]['student_no'] == '10000409'
        assert results[1]['student_no'] == '10009301'

    def test_detect_signatures_without_students(self):
        results = self.detector.detect_signatures([make_cell()])
        assert results[0]['student_no'] == ''
        assert results[0]['row_index'] == 0


# ----------------------------------------------------------------------
# Integration - the five supplied signing sheets
# ----------------------------------------------------------------------
@pytest.mark.skipif(not os.path.isdir(SAMPLES_DIR),
                    reason='Sample images are not available')
class TestSignatureDetectorIntegration:
    """End-to-end tests against the real signing sheets."""

    def setup_method(self):
        self.detector = SignatureDetector(save_progress=False)

    @pytest.mark.parametrize('filename', sorted(INK_GROUND_TRUTH))
    def test_detection_matches_ground_truth(self, filename):
        path = os.path.join(SAMPLES_DIR, filename)
        if not os.path.exists(path):
            pytest.skip(f'{filename} not present')

        outcome = self.detector.detect(path, students=STUDENTS)
        assert outcome['success'] is True, outcome.get('error')

        detected = [r['signature_present'] for r in outcome['results']]
        assert detected == INK_GROUND_TRUTH[filename], (
            f"{filename}: expected {INK_GROUND_TRUTH[filename]}, got {detected}")

    @pytest.mark.parametrize('filename', sorted(INK_GROUND_TRUTH))
    def test_six_rows_are_located(self, filename):
        path = os.path.join(SAMPLES_DIR, filename)
        if not os.path.exists(path):
            pytest.skip(f'{filename} not present')
        outcome = self.detector.detect(path, students=STUDENTS)
        assert len(outcome['results']) == 6

    @pytest.mark.parametrize('filename', sorted(INK_GROUND_TRUTH))
    def test_student_numbers_are_attached(self, filename):
        path = os.path.join(SAMPLES_DIR, filename)
        if not os.path.exists(path):
            pytest.skip(f'{filename} not present')
        outcome = self.detector.detect(path, students=STUDENTS)
        expected = [s['student_no'] for s in STUDENTS]
        assert [r['student_no'] for r in outcome['results']] == expected

    @pytest.mark.parametrize('filename', sorted(INK_GROUND_TRUTH))
    def test_skew_is_within_a_sane_range(self, filename):
        path = os.path.join(SAMPLES_DIR, filename)
        if not os.path.exists(path):
            pytest.skip(f'{filename} not present')
        outcome = self.detector.detect(path, students=STUDENTS)
        assert abs(outcome['skew_angle']) < 15

    def test_progress_images_are_written(self, tmp_path):
        path = os.path.join(SAMPLES_DIR, '1.jpeg')
        if not os.path.exists(path):
            pytest.skip('1.jpeg not present')
        detector = SignatureDetector(progress_dir=str(tmp_path), save_progress=True)
        outcome = detector.detect(path, students=STUDENTS)
        assert len(outcome['progress_images']) >= 8
        assert all(os.path.exists(p) for p in outcome['progress_images'])

    def test_result_shape_matches_attendance_manager_contract(self):
        """AttendanceManager reads 'student_no' and 'signature_present'."""
        path = os.path.join(SAMPLES_DIR, '1.jpeg')
        if not os.path.exists(path):
            pytest.skip('1.jpeg not present')
        outcome = self.detector.detect(path, students=STUDENTS)
        for result in outcome['results']:
            assert isinstance(result['student_no'], str)
            assert isinstance(result['signature_present'], bool)


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
