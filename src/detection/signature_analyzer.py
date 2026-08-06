"""Signature Analysis

Measures the ink content of a single signature cell and converts those
measurements into a present/absent decision with a confidence score.

Author: Heshan De Silva - Signature Detection
"""

import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict

import cv2
import numpy as np


@dataclass
class SignatureMetrics:
    """Quantitative description of the ink found inside one signature cell."""

    ink_ratio: float = 0.0
    ink_pixels: int = 0
    cell_area: int = 0
    component_count: int = 0
    largest_component_area: int = 0
    horizontal_span: float = 0.0
    vertical_span: float = 0.0
    bounding_boxes: list = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable view of the metrics."""
        data = asdict(self)
        data.pop('bounding_boxes')
        return data


class SignatureAnalyzer:
    """Turns a binary signature-cell image into a present/absent verdict.

    The analyser deliberately keeps no state between cells so that the same
    instance can be reused for every row of every sheet.
    """

    #: Fraction of the cell that must be covered in ink for a signature.
    DEFAULT_MIN_INK_RATIO = 0.010
    #: Connected components smaller than this are treated as sensor noise.
    DEFAULT_MIN_COMPONENT_AREA = 12
    #: At least one stroke must be this large for the cell to count as signed.
    DEFAULT_MIN_LARGEST_COMPONENT = 25

    def __init__(
        self,
        min_ink_ratio: float = DEFAULT_MIN_INK_RATIO,
        min_component_area: int = DEFAULT_MIN_COMPONENT_AREA,
        min_largest_component: int = DEFAULT_MIN_LARGEST_COMPONENT,
    ):
        self.min_ink_ratio = min_ink_ratio
        self.min_component_area = min_component_area
        self.min_largest_component = min_largest_component
        self.logger = logging.getLogger(__name__)

    def clean_cell(self, cell: np.ndarray) -> np.ndarray:
        """Remove salt-and-pepper noise left over from adaptive thresholding.

        Args:
            cell: Binary cell image where ink is white (255).

        Returns:
            The de-noised binary cell.
        """
        if cell.size == 0:
            return cell
        kernel = np.ones((2, 2), np.uint8)
        return cv2.morphologyEx(cell, cv2.MORPH_OPEN, kernel)

    def measure(self, cell: np.ndarray) -> SignatureMetrics:
        """Compute ink statistics for a binary signature cell.

        Args:
            cell: Binary cell image where ink is white (255).

        Returns:
            A populated :class:`SignatureMetrics`.
        """
        metrics = SignatureMetrics()
        if cell is None or cell.size == 0:
            return metrics

        cell = self.clean_cell(cell)
        metrics.cell_area = int(cell.size)

        count, _, stats, _ = cv2.connectedComponentsWithStats(cell, connectivity=8)

        height, width = cell.shape[:2]
        for index in range(1, count):
            area = int(stats[index, cv2.CC_STAT_AREA])
            if area < self.min_component_area:
                continue
            box_w = int(stats[index, cv2.CC_STAT_WIDTH])
            box_h = int(stats[index, cv2.CC_STAT_HEIGHT])
            metrics.component_count += 1
            metrics.ink_pixels += area
            metrics.largest_component_area = max(metrics.largest_component_area, area)
            metrics.horizontal_span = max(metrics.horizontal_span, box_w / max(width, 1))
            metrics.vertical_span = max(metrics.vertical_span, box_h / max(height, 1))
            metrics.bounding_boxes.append((
                int(stats[index, cv2.CC_STAT_LEFT]),
                int(stats[index, cv2.CC_STAT_TOP]),
                box_w,
                box_h,
            ))

        metrics.ink_ratio = metrics.ink_pixels / max(metrics.cell_area, 1)
        return metrics

    def decide(self, metrics: SignatureMetrics) -> Dict[str, Any]:
        """Convert metrics into a present/absent verdict.

        A cell counts as signed when it carries enough ink *and* at least one
        stroke is large enough to rule out a stray speck or a scanning artefact.

        Args:
            metrics: Output of :meth:`measure`.

        Returns:
            dict with ``signature_present``, ``confidence`` and ``metrics``.
        """
        enough_ink = metrics.ink_ratio >= self.min_ink_ratio
        real_stroke = metrics.largest_component_area >= self.min_largest_component
        present = bool(enough_ink and real_stroke)

        if present:
            # Scale confidence so that twice the threshold is full confidence.
            confidence = min(1.0, metrics.ink_ratio / (2.0 * self.min_ink_ratio))
        else:
            confidence = 1.0 - min(1.0, metrics.ink_ratio / self.min_ink_ratio)

        return {
            'signature_present': present,
            'confidence': round(float(confidence), 4),
            'metrics': metrics.to_dict(),
        }

    def analyze(self, cell: np.ndarray) -> Dict[str, Any]:
        """Measure a cell and decide in one call.

        Args:
            cell: Binary cell image where ink is white (255).

        Returns:
            dict with ``signature_present``, ``confidence`` and ``metrics``.
        """
        return self.decide(self.measure(cell))
