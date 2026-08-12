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

    def crop_to_page(self, gray_image):
        """
        Crop a photograph down to the sheet of paper.

        The desk and shadow around the page are darker than the paper, and
        survive the line morphology as huge blobs that swamp the real table
        lines, so they are removed before anything else.

        Args:
            gray_image: Grayscale photograph.

        Returns:
            tuple: (x, y, w, h) of the page, or the full frame if not found.
        """
        h, w = gray_image.shape[:2]
        _, paper = cv2.threshold(
            gray_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
        paper = cv2.morphologyEx(paper, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(
            paper, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return 0, 0, w, h

        x, y, cw, ch = cv2.boundingRect(max(contours, key=cv2.contourArea))
        if cw * ch < 0.30 * w * h:
            return 0, 0, w, h
        return x, y, cw, ch

    def estimate_skew(self, binary_image, max_angle=15.0):
        """
        Estimate the sheet's rotation from its near-horizontal lines.

        Args:
            binary_image: Binary image with white ink.
            max_angle: Ignore lines steeper than this many degrees.

        Returns:
            float: Skew angle in degrees, 0.0 when no usable lines were found.
        """
        h, w = binary_image.shape[:2]
        lines = cv2.HoughLinesP(
            binary_image, 1, np.pi / 720,
            threshold=100,
            minLineLength=max(40, w // 6),
            maxLineGap=20,
        )
        if lines is None or len(lines) == 0:
            return 0.0

        angles = []
        for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
            angle = np.degrees(np.arctan2(float(y2 - y1), float(x2 - x1)))
            if abs(angle) <= max_angle:
                angles.append(angle)

        return float(np.median(angles)) if angles else 0.0

    def extract_signature_cells(self, image, min_row_height=None, debug=False):
        """
        Detect the signing-sheet table grid and extract the signature column
        cells (one ROI per student row).

        The page is cropped out of the photograph and deskewed first: a wide
        opening kernel needs a line straight to within about a pixel across its
        whole length, so on a tilted photo it erases the very table lines it is
        meant to find.

        Args:
            image: Grayscale, colour or binary image of the sheet.
            min_row_height: Ignore rows shorter than this, in pixels of the
                supplied image. Defaults to 1.5% of the page height.
            debug: When True, also saves a visualisation of the detected grid.

        Returns:
            list[numpy.ndarray]: Signature-cell ROIs ordered top-to-bottom, cut
                from the cropped and deskewed page. Empty when no table is found.
        """
        gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        x, y, page_w, page_h = self.crop_to_page(gray)
        page = gray[y:y + page_h, x:x + page_w]

        # Adaptive rather than Otsu: phone photos carry uneven shadow.
        ink = cv2.adaptiveThreshold(
            cv2.bilateralFilter(page, 9, 75, 75), 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 15
        )

        angle = self.estimate_skew(ink)
        if abs(angle) > 0.05:
            centre = (page_w / 2, page_h / 2)
            rotation = cv2.getRotationMatrix2D(centre, angle, 1.0)
            page = cv2.warpAffine(page, rotation, (page_w, page_h),
                                  flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_REPLICATE)
            ink = cv2.adaptiveThreshold(
                cv2.bilateralFilter(page, 9, 75, 75), 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 15
            )

        if min_row_height is None:
            min_row_height = max(8, int(page_h * 0.015))

        horiz_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (max(10, page_w // 12), 1))
        horizontal = cv2.morphologyEx(ink, cv2.MORPH_OPEN, horiz_kernel)

        vert_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (1, max(10, page_h // 40)))
        vertical = cv2.morphologyEx(ink, cv2.MORPH_OPEN, vert_kernel)

        if debug:
            self.save_progress(cv2.bitwise_or(horizontal, vertical), "06_table_grid")

        # Absolute span thresholds, so one large blob elsewhere on the page
        # cannot suppress the genuine lines.
        row_lines = self._peaks(horizontal.sum(axis=1), 255 * page_w * 0.25)
        col_lines = self._peaks(vertical.sum(axis=0), 255 * page_h * 0.02)

        if len(row_lines) < 2 or len(col_lines) < 2:
            self.logger.warning(
                "Table grid not detected (rows=%d, cols=%d); returning no cells",
                len(row_lines), len(col_lines),
            )
            return []

        # Signature column = right-most column of a plausible width.
        min_col_width = page_w * 0.08
        column = None
        for left, right in zip(col_lines[:-1], col_lines[1:]):
            if right - left >= min_col_width:
                column = (left, right)
        if column is None:
            self.logger.warning("No column wide enough to be the signature column")
            return []

        spans = [(top, bottom) for top, bottom in zip(row_lines[:-1], row_lines[1:])
                 if bottom - top >= min_row_height]
        spans = self._uniform_run(spans)

        if not spans:
            self.logger.warning("No student rows found in the table")
            return []

        # Trim the printed borders out of each cell, or they read as ink.
        pad = max(4, int(np.median([b - a for a, b in spans]) * 0.15))

        x_left, x_right = column
        cells = [page[top + pad:bottom - pad, x_left + pad:x_right - pad]
                 for top, bottom in spans]

        self.logger.info(
            "Extracted %d signature-cell ROIs (col x=%d..%d)",
            len(cells), x_left, x_right,
        )
        return cells

    @staticmethod
    def _uniform_run(spans, tolerance=0.12):
        """
        Keep the longest consecutive run of similarly-tall rows.

        The sheet carries a lecture-details table and a column-header row above
        the student rows; those differ in height, so the student block is the
        longest run of consistent ones.

        Args:
            spans: (top, bottom) pairs ordered down the page.
            tolerance: Allowed deviation from the run's median height.

        Returns:
            list: The selected subset of ``spans``.
        """
        best, current = [], []
        for span in spans:
            height = span[1] - span[0]
            if current:
                median = np.median([b - a for a, b in current])
                if abs(height - median) <= tolerance * median:
                    current.append(span)
                    continue
                if len(current) > len(best):
                    best = current
                current = []
            current.append(span)

        return current if len(current) > len(best) else best

    @staticmethod
    def _peaks(profile, min_value, min_gap=5):
        """
        Find line positions in a 1-D projection profile.

        Positions at or above ``min_value`` are grouped into runs and each run
        reported once, at its centre. Stepping through a run in fixed strides
        would report one thick line, or one dark band, as many separate lines.
        """
        above = np.where(profile >= min_value)[0]
        if len(above) == 0:
            return []

        runs = np.split(above, np.where(np.diff(above) > min_gap)[0] + 1)
        return [int(round(run.mean())) for run in runs]

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
        signature_cells = self.extract_signature_cells(denoised, debug=True)

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
