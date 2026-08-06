"""
Generate intermediate progress images for the project report (Task 2.7).
Author: Member 2 - Image Preprocessing (Tharusha Rasath)

Runs the full pipeline over every sample signing sheet and writes:
    reports/progress_images/<step>.png   - per-stage screenshots
    reports/progress_grid.png            - combined labelled grid
    reports/signature_cells/<sheet>/     - extracted signature ROIs

Usage:
    python -m src.image_processing.generate_report_images
"""

import os
import glob

import cv2

from src.image_processing.image_processor import ImageProcessor


def main(sample_dir="data/sample_images", out_dir="reports"):
    samples = sorted(glob.glob(os.path.join(sample_dir, "*.jpeg")))
    if not samples:
        print(f"No sample images found in {sample_dir}")
        return

    print(f"Processing {len(samples)} sample sheets...")
    for sample in samples:
        name = os.path.splitext(os.path.basename(sample))[0]
        processor = ImageProcessor(
            progress_dir=os.path.join(out_dir, "progress_images", name)
        )
        result = processor.process(sample)

        # Save the labelled grid per sheet.
        grid_path = os.path.join(out_dir, "progress_grid.png")
        if name == os.path.splitext(os.path.basename(samples[0]))[0]:
            processor.create_progress_grid(grid_path)

        # Save each extracted signature cell.
        cells_dir = os.path.join(out_dir, "signature_cells", name)
        os.makedirs(cells_dir, exist_ok=True)
        for i, cell in enumerate(result["signature_cells"], start=1):
            cv2.imwrite(os.path.join(cells_dir, f"cell_{i:02d}.png"), cell)

        print(
            f"  {name}: {len(result['signature_cells'])} signature cells "
            f"-> {cells_dir}"
        )

    print("Done. Report images written under", out_dir)


if __name__ == "__main__":
    main()
