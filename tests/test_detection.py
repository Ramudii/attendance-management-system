"""
Unit Tests: Signature Detection (Member 4's module)
Author: Member 9 - Testing & QA
Task: 9.3

NOTE FOR THE TEAM:
src/detection/signature_detector.py is currently an EMPTY file. This
whole module is skipped until Member 4 pushes an implementation with:
    class SignatureDetector:
        def detect_signature(self, image, cell_box) -> dict          # single cell
        def detect_all_signatures(self, image, students, table) -> list
"""

import pytest

try:
    from src.detection.signature_detector import SignatureDetector
    HAS_DETECTOR = True
except ImportError:
    HAS_DETECTOR = False

pytestmark = pytest.mark.skipif(
    not HAS_DETECTOR,
    reason="SignatureDetector not implemented yet (src/detection/signature_detector.py is empty) "
           "- Member 4, feature/signature-detection"
)


class MockTable:
    """Fake table structure standing in for the real OCR-derived layout,
    so detection tests don't depend on OCR being finished first."""

    def get_cell(self, row, col):
        x = 50 + col * 150
        y = 170 + row * 50
        return (x, y, 140, 40)


class TestSignatureDetectorBasics:

    def test_can_instantiate(self):
        assert SignatureDetector() is not None


class TestSignatureDetection:

    def test_detect_all_signatures_returns_one_result_per_student(
        self, sample_image_path, ground_truth_signatures
    ):
        import cv2
        image = cv2.imread(sample_image_path)
        students = [{'student_no': sno} for sno in ground_truth_signatures]

        detector = SignatureDetector()
        results = detector.detect_all_signatures(image, students, MockTable())

        assert len(results) == len(students)
        for result in results:
            assert 'signature_present' in result
            assert 'confidence' in result
            assert 0.0 <= result['confidence'] <= 1.0

    def test_detection_accuracy_against_ground_truth(
        self, sample_image_path, ground_truth_signatures
    ):
        """We don't demand perfection from CV signature detection, but flag
        it as a bug if accuracy drops below a reasonable threshold."""
        import cv2
        image = cv2.imread(sample_image_path)
        students = [{'student_no': sno} for sno in ground_truth_signatures]

        detector = SignatureDetector()
        results = detector.detect_all_signatures(image, students, MockTable())

        correct = 0
        for result in results:
            expected = ground_truth_signatures.get(result['student_no'])
            if expected is not None and result['signature_present'] == expected:
                correct += 1

        accuracy = correct / len(students)
        assert accuracy >= 0.5, (
            f"Signature detection accuracy is {accuracy:.0%}, expected at least 50% "
            f"on the synthetic test sheet - see BUGS.md"
        )

    def test_empty_cell_has_low_confidence_signature_false(self, sample_image_path):
        import cv2
        image = cv2.imread(sample_image_path)
        detector = SignatureDetector()

        # (10009302 has no signature drawn in the synthetic sheet)
        result = detector.detect_signature(image, MockTable().get_cell(2, 4))
        assert result['signature_present'] is False
