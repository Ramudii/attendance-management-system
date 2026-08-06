"""
Unit tests for the image preprocessing pipeline.
Author: Member 2 - Image Preprocessing (Tharusha Rasath)

Run with:
    python -m pytest tests/test_preprocessing.py -v
    python -m unittest tests.test_preprocessing
"""

import os
import sys
import unittest

import cv2
import numpy as np

# Make the project root importable when run directly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.image_processing.image_processor import ImageProcessor


class TestImageProcessor(unittest.TestCase):
    """Unit tests for each preprocessing stage."""

    def setUp(self):
        # save_progress_images=False keeps tests off the filesystem.
        self.processor = ImageProcessor(save_progress_images=False)

        # Synthetic 100x100 image with a white square on a black background.
        self.test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.rectangle(self.test_image, (20, 20), (80, 80), (255, 255, 255), -1)
        self.test_path = "test_image.jpg"
        cv2.imwrite(self.test_path, self.test_image)

    def tearDown(self):
        if os.path.exists(self.test_path):
            os.remove(self.test_path)

    # ---- Task 2.1: loading ------------------------------------------- #
    def test_load_image_success(self):
        image = self.processor.load_image(self.test_path)
        self.assertIsNotNone(image)
        self.assertEqual(image.shape, (100, 100, 3))

    def test_load_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.processor.load_image("does_not_exist.jpg")

    def test_load_unsupported_extension_raises(self):
        with open("note.txt", "w") as f:
            f.write("not an image")
        try:
            with self.assertRaises(ValueError):
                self.processor.load_image("note.txt")
        finally:
            os.remove("note.txt")

    # ---- Task 2.2: grayscale ----------------------------------------- #
    def test_grayscale_conversion(self):
        gray = self.processor.convert_to_grayscale(self.test_image)
        self.assertEqual(gray.ndim, 2)

    def test_grayscale_idempotent(self):
        gray = self.processor.convert_to_grayscale(self.test_image)
        # Passing an already-gray image back must not raise or change dims.
        self.assertEqual(self.processor.convert_to_grayscale(gray).ndim, 2)

    # ---- Task 2.3: thresholding -------------------------------------- #
    def test_thresholding_otsu_is_binary(self):
        gray = cv2.cvtColor(self.test_image, cv2.COLOR_BGR2GRAY)
        binary = self.processor.apply_thresholding(gray, "otsu")
        self.assertTrue(np.all(np.isin(np.unique(binary), [0, 255])))

    def test_thresholding_adaptive_is_binary(self):
        gray = cv2.cvtColor(self.test_image, cv2.COLOR_BGR2GRAY)
        binary = self.processor.apply_thresholding(gray, "adaptive")
        self.assertTrue(np.all(np.isin(np.unique(binary), [0, 255])))

    def test_thresholding_rejects_colour_image(self):
        with self.assertRaises(ValueError):
            self.processor.apply_thresholding(self.test_image, "otsu")

    # ---- Task 2.4: noise removal ------------------------------------- #
    def test_noise_removal_preserves_shape(self):
        gray = cv2.cvtColor(self.test_image, cv2.COLOR_BGR2GRAY)
        noisy = gray.copy()
        noise_mask = np.zeros(gray.shape, dtype=bool)
        noise_mask[::7, ::7] = True  # deterministic salt & pepper
        noisy[noise_mask] = 255 - noisy[noise_mask]
        denoised = self.processor.remove_noise(noisy, "median")
        self.assertEqual(denoised.shape, gray.shape)

    def test_noise_removal_methods(self):
        gray = cv2.cvtColor(self.test_image, cv2.COLOR_BGR2GRAY)
        for method in ("median", "gaussian", "bilateral"):
            out = self.processor.remove_noise(gray, method)
            self.assertEqual(out.shape, gray.shape)

    # ---- Task 2.5: edge detection ------------------------------------ #
    def test_edges_canny_finds_square_border(self):
        gray = cv2.cvtColor(self.test_image, cv2.COLOR_BGR2GRAY)
        edges = self.processor.detect_edges(gray, method="canny")
        self.assertGreater(np.count_nonzero(edges), 0)

    def test_edges_sobel_is_uint8(self):
        gray = cv2.cvtColor(self.test_image, cv2.COLOR_BGR2GRAY)
        edges = self.processor.detect_edges(gray, method="sobel")
        self.assertEqual(edges.dtype, np.uint8)

    # ---- Task 2.6: ROI extraction ------------------------------------ #
    def test_extract_roi_dimensions(self):
        roi = self.processor.extract_roi(self.test_image, 20, 20, 60, 60)
        self.assertEqual(roi.shape[:2], (60, 60))

    def test_extract_roi_clamps_out_of_bounds(self):
        # Requested region exceeds the image; result must be clamped, not crash.
        roi = self.processor.extract_roi(self.test_image, 80, 80, 100, 100)
        self.assertEqual(roi.shape[:2], (20, 20))

    def test_extract_signature_cells_returns_list(self):
        gray = cv2.cvtColor(self.test_image, cv2.COLOR_BGR2GRAY)
        cells = self.processor.extract_signature_cells(gray)
        self.assertIsInstance(cells, list)

    # ---- Task 2.7: progress tracking --------------------------------- #
    def test_progress_is_recorded(self):
        self.processor.load_image(self.test_path)
        self.processor.convert_to_grayscale(self.test_image)
        progress = self.processor.get_progress_images()
        self.assertGreaterEqual(len(progress), 2)
        labels = [label for label, _ in progress]
        self.assertIn("01_original", labels)

    # ---- Full pipeline ----------------------------------------------- #
    def test_full_pipeline_returns_expected_keys(self):
        result = self.processor.process(self.test_path)
        for key in ("gray", "denoised", "binary", "edges", "signature_cells"):
            self.assertIn(key, result)
        self.assertEqual(result["gray"].ndim, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
