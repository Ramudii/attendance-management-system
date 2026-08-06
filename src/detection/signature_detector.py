"""Signature Detection

Locates the signature column of an NSBM signing sheet and reports, for every
student row, whether a signature was written in it.

Pipeline
--------
1. Load and normalise the photograph to a fixed working width.
2. Grey-scale, edge-preserving de-noise, adaptive threshold.
3. Estimate and correct the skew introduced by hand-held phone photography.
4. Recover the printed table lines with directional morphology.
5. Turn those lines into row and column separators, then isolate the
   student table and its rightmost (signature) column.
6. Subtract the printed grid so only handwriting remains, and analyse each
   signature cell with :class:`~src.detection.signature_analyzer.SignatureAnalyzer`.

Integration with the image-processing module
--------------------------------------------
Stages 1 and 2 are delegated to
:class:`~src.image_processing.image_processor.ImageProcessor` (Member 2), so the
project has a single implementation of loading, grey-scaling, de-noising and
thresholding. Stages 3 onwards remain here.

``ImageProcessor.extract_signature_cells`` is deliberately *not* used: it has no
deskew step, so its wide horizontal opening kernel erases the genuine table
lines on a tilted phone photograph and it returns an unreliable number of cells
(3-71 instead of 6 on the sample sheets). This module therefore keeps its own
deskew-and-grid stage. Once that defect is fixed, :meth:`detect_signatures`
already accepts ready-made ROIs and can take over.

Every stage writes a progress image so the report can show the whole
step-by-step process.

Author: Heshan De Silva - Signature Detection
"""

import logging
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from src.detection.signature_analyzer import SignatureAnalyzer
from src.image_processing.image_processor import ImageProcessor


class TableNotFoundError(RuntimeError):
    """Raised when the signing-sheet table cannot be located in an image."""


class SignatureDetector:
    """Detects student signatures on a scanned or photographed signing sheet."""

    #: Photographs are resized to this width before processing.
    WORKING_WIDTH = 1600
    #: Horizontal lines must span at least this fraction of the image width.
    HORIZONTAL_LINE_RATIO = 0.25
    #: Vertical lines must span at least this fraction of the image height.
    VERTICAL_LINE_RATIO = 0.02
    #: Pixels trimmed from each cell edge so printed borders are excluded.
    CELL_PADDING = 6

    def __init__(
        self,
        analyzer: Optional[SignatureAnalyzer] = None,
        progress_dir: str = 'reports/progress_images',
        save_progress: bool = True,
        processor: Optional[ImageProcessor] = None,
    ):
        """
        Args:
            analyzer: Analyser used to score each cell. A default is built
                when omitted.
            progress_dir: Directory that receives the step-by-step images.
            save_progress: Set to False to skip writing progress images.
            processor: Image-processing pipeline used for loading and
                thresholding. A default is built when omitted. Its own progress
                writing is disabled because this class records the steps itself,
                under a per-sheet folder.
        """
        self.analyzer = analyzer or SignatureAnalyzer()
        if processor is None:
            processor = ImageProcessor(save_progress_images=False)
            # Detection narrates its own steps, so the delegate's INFO chatter
            # is redundant here. Warnings and errors still come through.
            # (src/logger.py does not set propagate=False, so anything it emits
            # is printed twice once a root handler is configured.)
            processor.logger.setLevel(logging.WARNING)
        self.processor = processor
        self.progress_dir = progress_dir
        self.save_progress = save_progress
        self.logger = logging.getLogger(__name__)
        self.progress_images: List[str] = []
        self._step = 0
        self._output_dir = progress_dir

    # ------------------------------------------------------------------
    # Progress reporting
    # ------------------------------------------------------------------
    def _reset_progress(self, image_path: str) -> None:
        """Prepare a fresh progress-image folder for one input image."""
        self.progress_images = []
        self._step = 0

        # ImageProcessor keeps every intermediate in memory for its report grid.
        # Detection records its own progress images, so drop the delegate's
        # buffers to stop them accumulating across a batch of sheets.
        self.processor.progress_images.clear()
        self.processor.progress_labels.clear()

        stem = os.path.splitext(os.path.basename(image_path))[0] or 'sheet'
        self._output_dir = os.path.join(self.progress_dir, stem)
        if self.save_progress:
            os.makedirs(self._output_dir, exist_ok=True)

    def _record(self, name: str, image: np.ndarray) -> None:
        """Write one progress image and log the step.

        Args:
            name: Short step name, used in the filename.
            image: Image to write.
        """
        self._step += 1
        message = f"[Detection] Step {self._step}: {name.replace('_', ' ')}"
        self.logger.info(message)
        print(message)
        if not self.save_progress:
            return
        path = os.path.join(self._output_dir, f"{self._step:02d}_{name}.png")
        if cv2.imwrite(path, image):
            self.progress_images.append(path)
        else:
            self.logger.warning(f"Could not write progress image: {path}")

    def get_progress_images(self) -> List[str]:
        """Return the progress images produced by the last detection run."""
        return list(self.progress_images)

    # ------------------------------------------------------------------
    # Image preparation
    # ------------------------------------------------------------------
    def load_image(self, image_path: str) -> np.ndarray:
        """Read an image from disk and scale it to the working width.

        Args:
            image_path: Path to the signing-sheet photograph.

        Returns:
            The resized BGR image.

        Raises:
            FileNotFoundError: If the file is missing or unreadable.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Delegate decoding and format validation to the image-processing
        # module. It signals an unsupported extension or a corrupt file with
        # ValueError; both mean the same thing here as an unreadable image.
        try:
            image = self.processor.load_image(image_path)
        except ValueError as error:
            raise FileNotFoundError(f"Could not decode image: {image_path}") from error

        height, width = image.shape[:2]
        if width != self.WORKING_WIDTH:
            new_height = max(1, int(height * self.WORKING_WIDTH / width))
            image = cv2.resize(image, (self.WORKING_WIDTH, new_height),
                               interpolation=cv2.INTER_AREA)
        return image

    def binarize(self, image: np.ndarray) -> np.ndarray:
        """Produce a binary image in which ink is white and paper is black.

        The grey-scale, de-noise and threshold stages are delegated to the
        image-processing module. Adaptive thresholding is used rather than a
        global (Otsu) threshold because phone photographs carry strong, uneven
        shadows.

        ``ImageProcessor.apply_thresholding`` returns ink as *black* on white
        paper, so the result is inverted: every downstream stage here (line
        morphology, handwriting isolation, ink-ratio measurement) expects ink to
        be the white foreground.

        Args:
            image: BGR image.

        Returns:
            Binary (0/255) single-channel image with white ink.
        """
        gray = self.processor.convert_to_grayscale(image)
        denoised = self.processor.remove_noise(gray, method='bilateral')
        binary = self.processor.apply_thresholding(
            denoised, method='adaptive', block_size=25, constant=15)
        return cv2.bitwise_not(binary)

    def estimate_skew(self, binary: np.ndarray) -> float:
        """Estimate the sheet's rotation from its near-horizontal lines.

        Args:
            binary: Binary image with white ink.

        Returns:
            Skew angle in degrees; 0.0 when no usable lines were found.
        """
        lines = cv2.HoughLinesP(
            binary, 1, np.pi / 720,
            threshold=120,
            minLineLength=binary.shape[1] // 6,
            maxLineGap=20,
        )
        if lines is None or len(lines) == 0:
            self.logger.warning("No lines found for skew estimation; assuming 0 degrees")
            return 0.0

        # OpenCV 4 returns (N, 1, 4) while OpenCV 5 returns (N, 4).
        segments = np.asarray(lines).reshape(-1, 4)
        angles = []
        for x1, y1, x2, y2 in segments:
            angle = np.degrees(np.arctan2(float(y2 - y1), float(x2 - x1)))
            if abs(angle) < 30:
                angles.append(angle)
        if not angles:
            return 0.0
        return float(np.median(angles))

    def deskew(self, image: np.ndarray, angle: float) -> np.ndarray:
        """Rotate an image about its centre to remove skew.

        Args:
            image: Image to rotate.
            angle: Angle in degrees, as returned by :meth:`estimate_skew`.

        Returns:
            The rotated image, same size as the input.
        """
        if abs(angle) < 0.05:
            return image
        height, width = image.shape[:2]
        matrix = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), angle, 1.0)
        return cv2.warpAffine(
            image, matrix, (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

    # ------------------------------------------------------------------
    # Table structure
    # ------------------------------------------------------------------
    def extract_line_masks(self, binary: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Isolate the printed horizontal and vertical rules of the table.

        Opening with a long thin kernel keeps only strokes that run for a
        long distance in one direction, which is exactly what table rules do
        and what handwriting does not.

        Args:
            binary: Binary image with white ink.

        Returns:
            Tuple of (horizontal mask, vertical mask).
        """
        height, width = binary.shape[:2]
        horizontal_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (max(2, width // 25), 1))
        vertical_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (1, max(2, height // 60)))
        horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN,
                                      horizontal_kernel, iterations=2)
        vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN,
                                    vertical_kernel, iterations=2)
        return horizontal, vertical

    @staticmethod
    def _projection_peaks(projection: np.ndarray, minimum: float,
                          merge_gap: int = 4) -> List[int]:
        """Collapse a 1-D projection into a list of line positions.

        Args:
            projection: Per-row or per-column count of white pixels.
            minimum: Count a position as part of a line above this value.
            merge_gap: Positions closer than this belong to the same line.

        Returns:
            Sorted centre positions of the detected lines.
        """
        indices = np.where(projection > minimum)[0]
        if indices.size == 0:
            return []
        groups: List[List[int]] = []
        current = [int(indices[0])]
        for index in indices[1:]:
            index = int(index)
            if index - current[-1] <= merge_gap:
                current.append(index)
            else:
                groups.append(current)
                current = [index]
        groups.append(current)
        return [int(round(float(np.mean(group)))) for group in groups]

    def find_separators(self, horizontal: np.ndarray,
                        vertical: np.ndarray) -> Tuple[List[int], List[int]]:
        """Locate the y positions of row rules and x positions of column rules.

        Args:
            horizontal: Horizontal line mask.
            vertical: Vertical line mask.

        Returns:
            Tuple of (row y-positions, column x-positions).
        """
        height, width = horizontal.shape[:2]
        rows = self._projection_peaks(
            horizontal.sum(axis=1) / 255.0, width * self.HORIZONTAL_LINE_RATIO)
        columns = self._projection_peaks(
            vertical.sum(axis=0) / 255.0, height * self.VERTICAL_LINE_RATIO)
        self.logger.debug(f"Row separators: {rows}")
        self.logger.debug(f"Column separators: {columns}")
        return rows, columns

    @staticmethod
    def _longest_uniform_run(rows: Sequence[int]) -> Tuple[int, int]:
        """Find the longest stretch of evenly spaced row separators.

        The student table is the only block on the sheet with many rows of
        equal height, so this reliably separates it from the date/lecturer
        table above it.

        Args:
            rows: Row separator positions, ascending.

        Returns:
            (start, end) indices into ``rows``, inclusive.
        """
        if len(rows) < 2:
            return 0, max(0, len(rows) - 1)
        gaps = np.diff(np.asarray(rows))
        best = (0, 0)
        start = 0
        while start < len(gaps):
            end = start
            while (end + 1 < len(gaps)
                   and abs(int(gaps[end + 1]) - int(gaps[start]))
                   <= max(4, 0.25 * int(gaps[start]))):
                end += 1
            if (end - start) > (best[1] - best[0]):
                best = (start, end)
            start = end + 1
        return best[0], best[1] + 1

    def locate_signature_cells(
        self,
        rows: Sequence[int],
        columns: Sequence[int],
        expected_students: Optional[int] = None,
    ) -> List[Tuple[int, int, int, int]]:
        """Compute the bounding box of every student's signature cell.

        Args:
            rows: Row separator y-positions.
            columns: Column separator x-positions.
            expected_students: Number of students on the sheet, when known
                from ``info.xml``. Used to drop the printed column-header row.

        Returns:
            List of (x, y, width, height) boxes, top to bottom.

        Raises:
            TableNotFoundError: If the table geometry could not be recovered.
        """
        if len(columns) < 2:
            raise TableNotFoundError(
                f"Need at least 2 column separators, found {len(columns)}")
        if len(rows) < 3:
            raise TableNotFoundError(
                f"Need at least 3 row separators, found {len(rows)}")

        start, end = self._longest_uniform_run(rows)
        table_rows = list(rows[start:end + 1])
        if len(table_rows) < 2:
            raise TableNotFoundError("Could not isolate the student table rows")

        bands = [(table_rows[i], table_rows[i + 1])
                 for i in range(len(table_rows) - 1)]
        bands = self._drop_header_band(bands, expected_students)

        left, right = columns[-2], columns[-1]
        if right - left < 20:
            raise TableNotFoundError(
                f"Signature column is implausibly narrow ({right - left}px)")

        return [(left, top, right - left, bottom - top) for top, bottom in bands]

    @staticmethod
    def _drop_header_band(bands: List[Tuple[int, int]],
                          expected_students: Optional[int]) -> List[Tuple[int, int]]:
        """Discard the printed column-header band from the student table.

        When the sheet's student count is known, the last ``expected_students``
        bands are kept outright. Otherwise the header is identified by its
        height: the printed "No / Student No / ... / Signature" row is set in a
        smaller type size than the signature rows, so it is measurably shorter.
        If the first band is not shorter, the header was already excluded when
        the uniform run was selected and every band is a student row.

        Args:
            bands: (top, bottom) pairs for the student table, top to bottom.
            expected_students: Student count from ``info.xml``, when known.

        Returns:
            The bands that correspond to student rows.
        """
        if expected_students and len(bands) > expected_students:
            return bands[-expected_students:]
        if expected_students or len(bands) < 2:
            return bands

        heights = [bottom - top for top, bottom in bands]
        median_rest = float(np.median(heights[1:]))
        if heights[0] < 0.9 * median_rest:
            return bands[1:]
        return bands

    def isolate_handwriting(self, binary: np.ndarray, horizontal: np.ndarray,
                            vertical: np.ndarray) -> np.ndarray:
        """Remove the printed table rules, leaving handwriting behind.

        Args:
            binary: Binary image with white ink.
            horizontal: Horizontal line mask.
            vertical: Vertical line mask.

        Returns:
            Binary image containing handwriting only.
        """
        grid = cv2.add(horizontal, vertical)
        grid = cv2.dilate(grid, np.ones((3, 3), np.uint8), iterations=1)
        return cv2.subtract(binary, grid)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def detect(
        self,
        image_path: str,
        students: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run the full detection pipeline on one signing sheet.

        Args:
            image_path: Path to the signing-sheet photograph.
            students: Optional student records, ordered as they appear on the
                sheet. Each item should carry a ``student_no`` key; these are
                normally supplied by the OCR/XML module.

        Returns:
            dict with keys ``success``, ``image_path``, ``skew_angle``,
            ``results`` and ``progress_images``. ``results`` is the list
            consumed by ``AttendanceManager.record_attendance``.
        """
        self._reset_progress(image_path)
        expected = len(students) if students else None

        try:
            image = self.load_image(image_path)
            self._record('original_resized', image)

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            self._record('grayscale', gray)

            binary = self.binarize(image)
            self._record('binarized', binary)

            angle = self.estimate_skew(binary)
            self.logger.info(f"Estimated skew: {angle:.3f} degrees")
            image = self.deskew(image, angle)
            binary = self.binarize(image)
            self._record('deskewed_binary', binary)

            horizontal, vertical = self.extract_line_masks(binary)
            self._record('horizontal_lines', horizontal)
            self._record('vertical_lines', vertical)
            self._record('table_grid', cv2.add(horizontal, vertical))

            rows, columns = self.find_separators(horizontal, vertical)
            cells = self.locate_signature_cells(rows, columns, expected)
            self.logger.info(f"Located {len(cells)} signature cells")

            handwriting = self.isolate_handwriting(binary, horizontal, vertical)
            self._record('handwriting_only', handwriting)

            results = self._analyze_cells(handwriting, cells, students)
            self._record('detection_overlay',
                         self._draw_overlay(image, cells, results))

            return {
                'success': True,
                'image_path': image_path,
                'skew_angle': round(angle, 3),
                'results': results,
                'progress_images': self.get_progress_images(),
            }

        except (FileNotFoundError, TableNotFoundError) as error:
            self.logger.error(f"Detection failed for {image_path}: {error}")
            return {
                'success': False,
                'image_path': image_path,
                'error': str(error),
                'results': self._all_absent(students),
                'progress_images': self.get_progress_images(),
            }

    def detect_signatures(
        self,
        rois: Sequence[np.ndarray],
        students: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Score signature cells that another module has already cropped.

        This is the integration path for the image-processing module, which
        supplies ready-made regions of interest.

        Args:
            rois: Signature-cell images, ordered top to bottom. Grey-scale,
                colour and binary images are all accepted.
            students: Optional student records used to attach student numbers.

        Returns:
            The ``results`` list described in :meth:`detect`.
        """
        results: List[Dict[str, Any]] = []
        for index, roi in enumerate(rois):
            cell = self._to_binary_cell(roi)
            verdict = self.analyzer.analyze(cell)
            results.append(self._build_result(index, verdict, students))
        return results

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _to_binary_cell(self, roi: np.ndarray) -> np.ndarray:
        """Normalise an arbitrary ROI into a binary cell with white ink."""
        if roi is None or getattr(roi, 'size', 0) == 0:
            return np.zeros((1, 1), np.uint8)
        if roi.ndim == 3:
            return self.binarize(roi)
        unique = np.unique(roi)
        if unique.size <= 2 and set(unique.tolist()).issubset({0, 255}):
            return roi
        return cv2.adaptiveThreshold(
            roi, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 25, 15)

    def _analyze_cells(
        self,
        handwriting: np.ndarray,
        cells: Sequence[Tuple[int, int, int, int]],
        students: Optional[Sequence[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Analyse every located cell and build the result records."""
        height, width = handwriting.shape[:2]
        pad = self.CELL_PADDING
        results: List[Dict[str, Any]] = []

        for index, (x, y, w, h) in enumerate(cells):
            x0 = max(0, x + pad)
            y0 = max(0, y + pad)
            x1 = min(width, x + w - pad)
            y1 = min(height, y + h - pad)
            cell = handwriting[y0:y1, x0:x1] if x1 > x0 and y1 > y0 \
                else np.zeros((1, 1), np.uint8)
            verdict = self.analyzer.analyze(cell)
            record = self._build_result(index, verdict, students)
            record['cell_box'] = (int(x), int(y), int(w), int(h))
            results.append(record)

        return results

    @staticmethod
    def _build_result(index: int, verdict: Dict[str, Any],
                      students: Optional[Sequence[Dict[str, Any]]]) -> Dict[str, Any]:
        """Attach student identity to one cell verdict."""
        student_no = ''
        name = ''
        if students and index < len(students):
            student = students[index]
            student_no = str(student.get('student_no', '') or '')
            name = str(student.get('name', '') or '')
        return {
            'row_index': index,
            'student_no': student_no,
            'name': name,
            'signature_present': verdict['signature_present'],
            'confidence': verdict['confidence'],
            'ink_ratio': round(verdict['metrics']['ink_ratio'], 5),
            'metrics': verdict['metrics'],
        }

    @staticmethod
    def _all_absent(students: Optional[Sequence[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Fail-safe result set used when detection cannot run.

        Marking everyone absent is the conservative choice: a missed
        signature is corrected by the lecturer, whereas a fabricated one
        would silently record a student as present.
        """
        if not students:
            return []
        return [
            {
                'row_index': index,
                'student_no': str(student.get('student_no', '') or ''),
                'name': str(student.get('name', '') or ''),
                'signature_present': False,
                'confidence': 0.0,
                'ink_ratio': 0.0,
                'metrics': {},
            }
            for index, student in enumerate(students)
        ]

    @staticmethod
    def _draw_overlay(image: np.ndarray,
                      cells: Sequence[Tuple[int, int, int, int]],
                      results: Sequence[Dict[str, Any]]) -> np.ndarray:
        """Draw the detection outcome onto the deskewed sheet for the report."""
        overlay = image.copy()
        for (x, y, w, h), result in zip(cells, results):
            present = result['signature_present']
            colour = (0, 170, 0) if present else (0, 0, 220)
            cv2.rectangle(overlay, (x, y), (x + w, y + h), colour, 2)
            label = f"{result['row_index'] + 1}:{'P' if present else 'A'}"
            cv2.putText(overlay, label, (x + w + 6, y + h - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 1, cv2.LINE_AA)
        return overlay
