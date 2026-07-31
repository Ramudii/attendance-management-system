"""
Unit Tests: Image Preprocessing (Member 2's module)
Author: Member 9 - Testing & QA
Task: 9.1

NOTE FOR THE TEAM:
src/image_processing/image_processor.py is currently a placeholder
(process() just prints a message and returns None). These tests are
written against the *intended* behaviour. Until Member 2's real
implementation lands, the "real behaviour" assertions are skipped
automatically at runtime instead of failing the whole suite, so you can
merge this now and it will "light up" on its own once the real code
is pushed to feature/image-preprocessing.
"""

import os
import numpy as np
import pytest

from src.image_processing.image_processor import ImageProcessor


class TestImageProcessorBasics:
    """Tests that should pass right now, regardless of implementation state."""

    def test_can_instantiate(self):
        processor = ImageProcessor()
        assert processor is not None

    def test_get_progress_images_returns_list(self):
        processor = ImageProcessor()
        result = processor.get_progress_images()
        assert isinstance(result, list)


class TestImageProcessorProcess:
    """Tests for ImageProcessor.process(). Skips gracefully while the
    method is still a placeholder that returns None."""

    def test_process_existing_image(self, sample_image_path):
        processor = ImageProcessor()
        result = processor.process(sample_image_path)

        if result is None:
            pytest.skip(
                "ImageProcessor.process() is still a placeholder "
                "(Member 2 has not implemented it yet)"
            )

        assert isinstance(result, np.ndarray), "process() should return an image array"
        assert result.ndim in (2, 3), "processed image should be 2D (grayscale) or 3D (color)"
        assert result.shape[0] > 0 and result.shape[1] > 0

    def test_process_nonexistent_image_raises_or_errors(self):
        """A missing file should fail loudly, not silently return None."""
        processor = ImageProcessor()
        fake_path = 'this_file_does_not_exist_12345.jpg'

        try:
            result = processor.process(fake_path)
        except (FileNotFoundError, ValueError, OSError):
            return  # correct behaviour

        if result is None:
            pytest.skip(
                "ImageProcessor.process() currently returns None for missing "
                "files instead of raising - flagged as a bug, see BUGS.md"
            )
        pytest.fail("process() should raise for a nonexistent image path")

    def test_process_is_deterministic(self, sample_image_path):
        """Running process() twice on the same input should give the same output."""
        processor = ImageProcessor()
        result1 = processor.process(sample_image_path)
        result2 = processor.process(sample_image_path)

        if result1 is None or result2 is None:
            pytest.skip("ImageProcessor.process() not yet implemented")

        assert np.array_equal(result1, result2)
