"""
Image Processing Pipeline
Author: Member 2 - Image Preprocessing (Tharusha Rasath)

Full preprocessing pipeline for the Student Attendance Management System (SAMS).
Takes a raw photograph of a signing sheet and produces clean, binarised images
plus extracted signature-cell ROIs that the OCR and Signature-Detection modules
consume downstream.

Pipeline stages:
    load -> grayscale -> denoise -> (threshold | edges) -> ROI extraction

Every stage records an intermediate image via ``save_progress`` so the report
builder can show before/after screenshots of the pipeline.
"""

import os
from pathlib import Path

import cv2
import numpy as np
import matplotlib.pyplot as plt

# The project ships a shared logger (src/logger.py). Fall back to a plain
# logger if this module is imported outside the package (e.g. ad-hoc scripts).
try:
    from src.logger import get_logger
except Exception:  # pragma: no cover - import fallback
    import logging

    def get_logger(name):
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(name)


# File extensions we are willing to read.
SUPPORTED_EXTENSIONS = {".jpeg", ".jpg", ".png", ".tiff", ".tif", ".bmp"}


class ImageProcessor:
    """Complete image preprocessing pipeline for signing-sheet photographs."""

    def __init__(self, progress_dir="reports/progress_images", save_progress_images=True):
        """
        Args:
            progress_dir: Directory where intermediate images are written.
            save_progress_images: When False, images are kept in memory only
                (useful for unit tests so the disk is not touched).
        """
        self.logger = get_logger("image_processor")
        self.progress_dir = progress_dir
        self.save_progress_images = save_progress_images

        # Ordered record of every intermediate step for report generation.
        self.progress_images = []
        self.progress_labels = []

        if self.save_progress_images:
            os.makedirs(self.progress_dir, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Task 2.1 - Image reading with format handling                       #
    # ------------------------------------------------------------------ #
    def load_image(self, image_path):
        """
        Load an image from disk with format validation and error handling.

        Args:
            image_path: Path to the image file.

        Returns:
            numpy.ndarray: Loaded image in BGR colour order.

        Raises:
            FileNotFoundError: If the path does not exist.
            ValueError: If the extension is unsupported or the file cannot be
                decoded by OpenCV.
        """
        path = Path(image_path)

        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported image format '{path.suffix}'. "
                f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
            )

        # cv2.imread silently returns None on a corrupt/unreadable file.
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Could not decode image (corrupt or empty): {image_path}")

        self.logger.info(f"Loaded image {path.name} with shape {image.shape}")
        self.save_progress(image, "01_original")
        return image

    # ------------------------------------------------------------------ #
    # Task 2.2 - Grayscale conversion                                     #
    # ------------------------------------------------------------------ #
    def convert_to_grayscale(self, image):
        """
        Convert a colour image to single-channel grayscale.

        Args:
            image: Input image (BGR). If already grayscale it is returned as-is.

        Returns:
            numpy.ndarray: Single-channel grayscale image.
        """
        if image.ndim == 2:
            return image

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        self.logger.info("Converted image to grayscale")
        self.save_progress(gray, "02_grayscale")
        return gray

    # ------------------------------------------------------------------ #
    # Task 2.3 - Binarisation / thresholding (adaptive & Otsu)            #
    # ------------------------------------------------------------------ #
    def apply_thresholding(self, gray_image, method="otsu", block_size=11, constant=2):
        """
        Binarise a grayscale image.

        Args:
            gray_image: Single-channel grayscale image.
            method: 'otsu' (global automatic), 'adaptive' (local Gaussian) or
                'binary' (fixed threshold at 127).
            block_size: Neighbourhood size for adaptive thresholding. Must be an
                odd number > 1; it is coerced to the nearest valid value.
            constant: Constant subtracted from the local mean in adaptive mode.

        Returns:
            numpy.ndarray: Binary image with values in {0, 255}.
        """
        if gray_image.ndim != 2:
            raise ValueError("apply_thresholding expects a grayscale image")

        if method == "otsu":
            # Otsu ignores the manual threshold and picks the optimum from the
            # image histogram - ideal for the varied lighting in phone photos.
            _, binary = cv2.threshold(
                gray_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
            label = "03_binary_otsu"

        elif method == "adaptive":
            # Adaptive handles uneven illumination / shadows across the page.
            block_size = max(3, block_size | 1)  # force odd, >= 3
            binary = cv2.adaptiveThreshold(
                gray_image,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                block_size,
                constant,
            )
            label = "03_binary_adaptive"

        elif method == "binary":
            _, binary = cv2.threshold(gray_image, 127, 255, cv2.THRESH_BINARY)
            label = "03_binary_simple"

        else:
            raise ValueError(f"Unknown thresholding method: {method}")

        self.logger.info(f"Applied thresholding (method={method})")
        self.save_progress(binary, label)
        return binary

    # ------------------------------------------------------------------ #
    # Task 2.4 - Noise removal (blurring / filtering)                     #
    # ------------------------------------------------------------------ #
    def remove_noise(self, image, method="median", kernel_size=5):
        """
        Reduce noise while preserving edges as much as possible.

        Args:
            image: Input image (grayscale or colour).
            method: 'median' (salt & pepper), 'gaussian' (general smoothing) or
                'bilateral' (edge-preserving).
            kernel_size: Kernel size for median/gaussian. Coerced to odd.

        Returns:
            numpy.ndarray: Denoised image with the same shape as the input.
        """
        if method == "median":
            kernel_size = max(3, kernel_size | 1)
            denoised = cv2.medianBlur(image, kernel_size)
            label = "04_denoised_median"

        elif method == "gaussian":
            kernel_size = max(3, kernel_size | 1)
            denoised = cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)
            label = "04_denoised_gaussian"

        elif method == "bilateral":
            denoised = cv2.bilateralFilter(image, 9, 75, 75)
            label = "04_denoised_bilateral"

        else:
            raise ValueError(f"Unknown noise removal method: {method}")

        self.logger.info(f"Removed noise (method={method}, kernel={kernel_size})")
        self.save_progress(denoised, label)
        return denoised

    # ------------------------------------------------------------------ #
    # Task 2.5 - Edge detection (Canny & Sobel)                           #
    # ------------------------------------------------------------------ #
    def detect_edges(self, image, low_threshold=50, high_threshold=150, method="canny"):
        """
        Detect edges - used to locate the table grid of the signing sheet.

        Args:
            image: Grayscale input image.
            low_threshold: Lower hysteresis threshold for Canny.
            high_threshold: Upper hysteresis threshold for Canny.
            method: 'canny' or 'sobel'.

        Returns:
            numpy.ndarray: 8-bit edge map.
        """
        if method == "canny":
            edges = cv2.Canny(image, low_threshold, high_threshold)
            label = "05_edges_canny"

        elif method == "sobel":
            # Combine horizontal and vertical gradients into a magnitude image.
            sobelx = cv2.Sobel(image, cv2.CV_64F, 1, 0, ksize=3)
            sobely = cv2.Sobel(image, cv2.CV_64F, 0, 1, ksize=3)
            magnitude = np.sqrt(sobelx**2 + sobely**2)
            edges = np.uint8(np.clip(magnitude, 0, 255))
            label = "05_edges_sobel"

        else:
            raise ValueError(f"Unknown edge detection method: {method}")

        self.logger.info(f"Detected edges (method={method})")
        self.save_progress(edges, label)
        return edges

    # ------------------------------------------------------------------ #
    # Task 2.6 - ROI extraction for signature cells                       #
    # ------------------------------------------------------------------ #
    def extract_roi(self, image, x, y, width, height):
        """
        Extract a rectangular Region Of Interest, clamped to image bounds.

        Args:
            image: Input image.
            x, y: Top-left corner coordinates.
            width, height: ROI dimensions.

        Returns:
            numpy.ndarray: Cropped ROI.
        """
        h, w = image.shape[:2]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(w, x + width), min(h, y + height)

        if x1 <= x0 or y1 <= y0:
            raise ValueError(
                f"ROI ({x},{y},{width},{height}) does not overlap image {w}x{h}"
            )

        return image[y0:y1, x0:x1]

    def extract_signature_cells(self, binary_image, min_row_height=25, debug=False):
        """
        Detect the signing-sheet table grid and extract the signature column
        cells (one ROI per student row).

        The table is found by isolating long horizontal and vertical lines with
        morphological opening, then combining them to recover the grid. The
        signature column is assumed to be the right-most column of the table
        (matching the SAMS signing-sheet layout).

        Args:
            binary_image: Binary (or grayscale) image of the sheet.
            min_row_height: Ignore detected rows shorter than this (removes noise).
            debug: When True, also saves a visualisation of the detected grid.

        Returns:
            list[numpy.ndarray]: Signature-cell ROIs ordered top-to-bottom.
                Returns an empty list if no table structure is found.
        """
        # Work on an inverted binary so grid lines become white foreground.
        gray = binary_image if binary_image.ndim == 2 else cv2.cvtColor(
            binary_image, cv2.COLOR_BGR2GRAY
        )
        _, inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        h, w = inv.shape

        # Horizontal lines: open with a wide, 1px-tall kernel.
        horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(10, w // 15), 1))
        horizontal = cv2.morphologyEx(inv, cv2.MORPH_OPEN, horiz_kernel)

        # Vertical lines: open with a tall, 1px-wide kernel.
        vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(10, h // 15)))
        vertical = cv2.morphologyEx(inv, cv2.MORPH_OPEN, vert_kernel)

        grid = cv2.bitwise_or(horizontal, vertical)
        if debug:
            self.save_progress(grid, "06_table_grid")

        # Row boundaries = y positions where horizontal lines are dense.
        row_profile = horizontal.sum(axis=1)
        row_lines = self._peaks(row_profile, threshold_ratio=0.3, min_gap=min_row_height)

        # Column boundaries = x positions where vertical lines are dense.
        col_profile = vertical.sum(axis=0)
        col_lines = self._peaks(col_profile, threshold_ratio=0.3, min_gap=20)

        if len(row_lines) < 2 or len(col_lines) < 2:
            self.logger.warning(
                "Table grid not detected (rows=%d, cols=%d); returning no cells",
                len(row_lines),
                len(col_lines),
            )
            return []

        # Signature column = between the last two vertical grid lines.
        x_left, x_right = col_lines[-2], col_lines[-1]

        cells = []
        for top, bottom in zip(row_lines[:-1], row_lines[1:]):
            if bottom - top < min_row_height:
                continue
            cells.append(binary_image[top:bottom, x_left:x_right])

        self.logger.info(
            "Extracted %d signature-cell ROIs (col x=%d..%d)",
            len(cells),
            x_left,
            x_right,
        )
        return cells

    @staticmethod
    def _peaks(profile, threshold_ratio=0.3, min_gap=15):
        """
        Find line positions in a 1-D projection profile.

        A position counts as a line when its value exceeds
        ``threshold_ratio * max(profile)``. Positions closer than ``min_gap`` are
        merged so a single thick line is reported once.
        """
        if profile.max() == 0:
            return []
        threshold = profile.max() * threshold_ratio
        candidates = np.where(profile > threshold)[0]
        if len(candidates) == 0:
            return []

        lines = [int(candidates[0])]
        for pos in candidates[1:]:
            if pos - lines[-1] >= min_gap:
                lines.append(int(pos))
        return lines

    # ------------------------------------------------------------------ #
    # Task 2.7 - Progress capture & report grid                           #
    # ------------------------------------------------------------------ #
    def save_progress(self, image, step_name):
        """
        Record an intermediate image for the report.

        Args:
            image: Image to record.
            step_name: Human-readable step label (also the output filename).
        """
        self.progress_images.append(image.copy())
        self.progress_labels.append(step_name)

        if self.save_progress_images:
            save_path = os.path.join(self.progress_dir, f"{step_name}.png")
            if not cv2.imwrite(save_path, image):
                self.logger.warning(f"Failed to write progress image: {save_path}")

    def get_progress_images(self):
        """Return a list of (label, image) tuples captured so far."""
        return list(zip(self.progress_labels, self.progress_images))

    def create_progress_grid(self, save_path="reports/progress_grid.png"):
        """
        Assemble every captured step into a single labelled grid for the report.

        Args:
            save_path: Output path for the grid PNG.

        Returns:
            str | None: The save path, or None if there was nothing to plot.
        """
        n_images = len(self.progress_images)
        if n_images == 0:
            self.logger.warning("No progress images to build grid from")
            return None

        cols = 4
        rows = (n_images + cols - 1) // cols

        fig, axes = plt.subplots(rows, cols, figsize=(15, rows * 3))
        axes = np.atleast_1d(axes).flatten()

        for i, (label, img) in enumerate(self.get_progress_images()):
            cmap = "gray" if img.ndim == 2 else None
            display = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            axes[i].imshow(display, cmap=cmap)
            axes[i].set_title(label, fontsize=10)
            axes[i].axis("off")

        for i in range(n_images, len(axes)):
            axes[i].axis("off")

        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        plt.tight_layout()
        plt.savefig(save_path, dpi=200, bbox_inches="tight")
        plt.close(fig)

        self.logger.info(f"Saved progress grid to {save_path}")
        return save_path

    # ------------------------------------------------------------------ #
    # Orchestration                                                       #
    # ------------------------------------------------------------------ #
    def process(self, image_path):
        """
        Run the full preprocessing pipeline on a single sheet.

        Args:
            image_path: Path to the input image.

        Returns:
            dict: {
                'gray', 'denoised', 'binary', 'edges': numpy.ndarray,
                'signature_cells': list[numpy.ndarray],
            }
        """
        original = self.load_image(image_path)
        gray = self.convert_to_grayscale(original)
        denoised = self.remove_noise(gray, method="median", kernel_size=3)
        edges = self.detect_edges(denoised, 50, 150, method="canny")
        binary = self.apply_thresholding(denoised, method="adaptive")
        signature_cells = self.extract_signature_cells(gray, debug=True)

        self.logger.info(
            "Pipeline complete: %d signature cells extracted", len(signature_cells)
        )

        return {
            "gray": gray,
            "denoised": denoised,
            "binary": binary,
            "edges": edges,
            "signature_cells": signature_cells,
        }


if __name__ == "__main__":
    # Quick manual smoke test against the bundled sample images.
    import sys

    sample = sys.argv[1] if len(sys.argv) > 1 else "data/sample_images/1.jpeg"
    processor = ImageProcessor()
    result = processor.process(sample)
    processor.create_progress_grid()
    print(f"Done. Extracted {len(result['signature_cells'])} signature cells.")
