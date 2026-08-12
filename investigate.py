"""
Student Signature Investigation

Compares the same student's signatures across multiple attendance sheets
using SSIM, SIFT and ORB image-similarity methods.

This module uses the existing OCR and Signature Detection modules without
modifying them.

Usage:
    python investigate.py 10000409 data/info.xml data/sample_images/

Example:
    python investigate.py 10000409 data/info.xml data/sample_images/
"""

import argparse
import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
import sys
import os
import json
from datetime import datetime
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from src.ocr.ocr_extractor import OCRExtractor
from src.detection.signature_detector import SignatureDetector
from src.logger import setup_logger


class SignatureInvestigator:
    """Investigate and compare a student's signatures across attendance sheets."""

    #: Signatures are normalised onto this canvas before comparison.
    CANVAS_SIZE = (384, 192)
    #: Hamming distance below which an ORB descriptor pair counts as a match.
    ORB_MAX_DISTANCE = 40

    # Weights and threshold calibrated on the five sample sheets: 45 genuine
    # pairs against 280 impostor pairs, giving AUC 0.73 at the equal-error
    # point (~31% false accepts, ~29% false rejects).
    SSIM_WEIGHT = 0.2
    SIFT_WEIGHT = 0.2
    ORB_WEIGHT = 0.6
    MATCH_THRESHOLD = 31.5

    def __init__(self):
        self.logger = setup_logger('investigator')

        self.signature_storage = 'data/signatures/'
        os.makedirs(self.signature_storage, exist_ok=True)

        self.logger.info("Signature Investigator initialized")

    # ------------------------------------------------------------------
    # Student information
    # ------------------------------------------------------------------

    def get_students_from_xml(self, xml_path):
        """
        Get student information from info.xml using the existing OCR module.

        Args:
            xml_path: Path to info.xml

        Returns:
            Dictionary containing cleaned student information.
        """
        if not os.path.exists(xml_path):
            self.logger.error(f"XML file not found: {xml_path}")
            return {}

        try:
            ocr = OCRExtractor()
            students = ocr.parse_info_xml(xml_path)

            self.logger.info(
                f"Loaded {len(students)} students from XML"
            )

            return students

        except Exception as e:
            self.logger.error(
                f"Failed to read student information: {str(e)}"
            )
            return {}

    # ------------------------------------------------------------------
    # Image handling
    # ------------------------------------------------------------------

    def get_image_files(self, image_directory):
        """
        Get attendance-sheet images from a directory.

        Args:
            image_directory: Directory containing attendance images.

        Returns:
            Sorted list of image paths.
        """
        if not os.path.exists(image_directory):
            self.logger.error(
                f"Image directory not found: {image_directory}"
            )
            return []

        valid_extensions = {
            '.jpg',
            '.jpeg',
            '.png',
            '.bmp',
            '.tiff',
            '.tif'
        }

        image_files = []

        for filename in os.listdir(image_directory):
            extension = os.path.splitext(filename)[1].lower()

            if extension in valid_extensions:
                image_files.append(
                    os.path.join(image_directory, filename)
                )

        return sorted(image_files)

    # ------------------------------------------------------------------
    # Signature extraction
    # ------------------------------------------------------------------

    def extract_signatures_from_sheet(
        self,
        image_path,
        students
    ):
        """
        Detect and extract signature cells from one attendance sheet.

        This uses the existing SignatureDetector without modifying it.

        Args:
            image_path: Attendance sheet image.
            students: Ordered list of student records.

        Returns:
            Dictionary mapping student number to extracted signature data.
        """

        self.logger.info(
            f"Detecting signatures in: {image_path}"
        )

        detector = SignatureDetector(
            save_progress=True
        )

        try:
            # Run the existing signature detection pipeline.
            detection_result = detector.detect(
                image_path,
                students
            )

            if not detection_result.get('success'):
                self.logger.warning(
                    f"Signature detection failed: "
                    f"{detection_result.get('error', 'Unknown error')}"
                )
                return {}

            results = detection_result.get('results', [])

            if not results:
                self.logger.warning(
                    f"No signature results found in {image_path}"
                )
                return {}

            # ----------------------------------------------------------
            # Important:
            #
            # SignatureDetector returns cell_box coordinates after
            # resizing and deskewing the image.
            #
            # We reproduce that same preparation here so that the
            # coordinates correspond to the image we crop.
            # ----------------------------------------------------------

            image = detector.load_image(image_path)

            binary = detector.binarize(image)

            angle = detector.estimate_skew(binary)

            deskewed_image = detector.deskew(
                image,
                angle
            )

            # Recreate the binary/handwriting image used by the
            # detector internally.
            deskewed_binary = detector.binarize(
                deskewed_image
            )

            horizontal, vertical = detector.extract_line_masks(
                deskewed_binary
            )

            handwriting = detector.isolate_handwriting(
                deskewed_binary,
                horizontal,
                vertical
            )

            extracted = {}

            for result in results:

                student_no = str(
                    result.get('student_no', '')
                ).strip()

                if not student_no:
                    continue

                cell_box = result.get('cell_box')

                if not cell_box:
                    self.logger.warning(
                        f"No cell box found for student {student_no}"
                    )
                    continue

                x, y, w, h = cell_box

                # Same padding used by SignatureDetector.
                padding = detector.CELL_PADDING

                height, width = handwriting.shape[:2]

                x0 = max(0, x + padding)
                y0 = max(0, y + padding)

                x1 = min(
                    width,
                    x + w - padding
                )

                y1 = min(
                    height,
                    y + h - padding
                )

                if x1 <= x0 or y1 <= y0:
                    self.logger.warning(
                        f"Invalid signature region for "
                        f"student {student_no}"
                    )
                    continue

                # Crop handwriting-only signature.
                signature_image = handwriting[
                    y0:y1,
                    x0:x1
                ]

                if signature_image.size == 0:
                    continue

                # Save the extracted signature for inspection/debugging.
                safe_student_no = student_no.replace(
                    os.sep,
                    '_'
                )

                sheet_name = Path(
                    image_path
                ).stem

                signature_path = os.path.join(
                    self.signature_storage,
                    f"{safe_student_no}_{sheet_name}.png"
                )

                cv2.imwrite(
                    signature_path,
                    signature_image
                )

                extracted[student_no] = {
                    'student_no': student_no,
                    'name': result.get('name', ''),
                    'signature_present': result.get(
                        'signature_present',
                        False
                    ),
                    'confidence': result.get(
                        'confidence',
                        0.0
                    ),
                    'ink_ratio': result.get(
                        'ink_ratio',
                        0.0
                    ),
                    'cell_box': cell_box,
                    'image': signature_image,
                    'path': signature_path,
                    'sheet': os.path.basename(image_path)
                }

            self.logger.info(
                f"Extracted {len(extracted)} signature cells "
                f"from {os.path.basename(image_path)}"
            )

            return extracted

        except Exception as e:
            self.logger.error(
                f"Signature extraction failed for "
                f"{image_path}: {str(e)}"
            )
            return {}

    # ------------------------------------------------------------------
    # Signature preprocessing
    # ------------------------------------------------------------------

    def preprocess_signature(self, signature_image):
        """
        Preprocess signature image before comparison.

        Args:
            signature_image: Input signature image.

        Returns:
            Tuple containing grayscale/processed image and binary image.
        """

        if signature_image is None:
            return None, None

        if signature_image.size == 0:
            return None, None

        # Convert to grayscale if necessary.
        if len(signature_image.shape) == 3:
            gray = cv2.cvtColor(
                signature_image,
                cv2.COLOR_BGR2GRAY
            )
        else:
            gray = signature_image.copy()

        _, binary = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        # Make sure signature strokes are white.
        if np.mean(binary) > 127:
            binary = cv2.bitwise_not(binary)

        kernel = np.ones(
            (2, 2),
            np.uint8
        )

        binary = cv2.morphologyEx(
            binary,
            cv2.MORPH_CLOSE,
            kernel
        )

        # Crop to the strokes, so position and padding in the cell are ignored.
        points = cv2.findNonZero(binary)

        if points is None:
            return None, None

        x, y, w, h = cv2.boundingRect(points)

        if w < 3 or h < 3:
            return None, None

        ink = binary[y:y + h, x:x + w]

        # Scale onto a fixed canvas, preserving aspect ratio so the stroke
        # shape is compared rather than a stretched version of it.
        canvas_w, canvas_h = self.CANVAS_SIZE
        scale = min(canvas_w / w, canvas_h / h)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))

        resized = cv2.resize(
            ink,
            (new_w, new_h),
            interpolation=cv2.INTER_AREA
        )

        normalized = np.zeros((canvas_h, canvas_w), np.uint8)
        offset_x = (canvas_w - new_w) // 2
        offset_y = (canvas_h - new_h) // 2
        normalized[offset_y:offset_y + new_h, offset_x:offset_x + new_w] = resized

        return normalized, normalized

    # ------------------------------------------------------------------
    # SSIM comparison
    # ------------------------------------------------------------------

    def compare_ssim(self, img1, img2):
        """
        Compare two signatures using SSIM.

        Returns:
            Similarity score from 0 to 100.
        """

        try:
            _, proc1 = self.preprocess_signature(img1)
            _, proc2 = self.preprocess_signature(img2)

            if proc1 is None or proc2 is None:
                return 0.0

            similarity, _ = ssim(
                proc1,
                proc2,
                full=True,
                data_range=255
            )

            return float(similarity * 100)

        except Exception as e:
            self.logger.error(
                f"SSIM comparison failed: {str(e)}"
            )
            return 0.0

    # ------------------------------------------------------------------
    # SIFT / ORB comparison
    # ------------------------------------------------------------------

    def compare_feature_matching(
        self,
        img1,
        img2,
        method='sift'
    ):
        """
        Compare signatures using SIFT or ORB feature matching.

        Args:
            img1: First signature.
            img2: Second signature.
            method: 'sift' or 'orb'.

        Returns:
            Similarity score from 0 to 100.
        """

        try:
            proc1, _ = self.preprocess_signature(img1)
            proc2, _ = self.preprocess_signature(img2)

            if proc1 is None or proc2 is None:
                return 0.0

            proc1 = proc1.astype(np.uint8)
            proc2 = proc2.astype(np.uint8)

            # ----------------------------------------------------------
            # SIFT
            # ----------------------------------------------------------

            if method.lower() == 'sift':

                detector = cv2.SIFT_create()

                kp1, des1 = detector.detectAndCompute(
                    proc1,
                    None
                )

                kp2, des2 = detector.detectAndCompute(
                    proc2,
                    None
                )

                if (
                    des1 is None
                    or des2 is None
                    or len(kp1) == 0
                    or len(kp2) == 0
                ):
                    return 0.0

                matcher = cv2.BFMatcher()

                matches = matcher.knnMatch(
                    des1,
                    des2,
                    k=2
                )

                good_matches = []

                for pair in matches:

                    if len(pair) != 2:
                        continue

                    m, n = pair

                    if m.distance < 0.75 * n.distance:
                        good_matches.append(m)

                denominator = min(
                    len(kp1),
                    len(kp2)
                )

                if denominator == 0:
                    return 0.0

                score = (
                    len(good_matches)
                    / denominator
                    * 100
                )

                return min(float(score), 100.0)

            # ----------------------------------------------------------
            # ORB
            # ----------------------------------------------------------

            else:

                # The defaults (edgeThreshold/patchSize 31) exceed half the
                # canvas height and find no keypoints at all.
                detector = cv2.ORB_create(
                    nfeatures=500,
                    edgeThreshold=5,
                    patchSize=9,
                    fastThreshold=5
                )

                kp1, des1 = detector.detectAndCompute(
                    proc1,
                    None
                )

                kp2, des2 = detector.detectAndCompute(
                    proc2,
                    None
                )

                if (
                    des1 is None
                    or des2 is None
                    or len(kp1) == 0
                    or len(kp2) == 0
                ):
                    return 0.0

                matcher = cv2.BFMatcher(
                    cv2.NORM_HAMMING,
                    crossCheck=True
                )

                matches = matcher.match(
                    des1,
                    des2
                )

                good_matches = [
                    m for m in matches
                    if m.distance < self.ORB_MAX_DISTANCE
                ]

                denominator = min(
                    len(kp1),
                    len(kp2)
                )

                if denominator == 0:
                    return 0.0

                score = (
                    len(good_matches)
                    / denominator
                    * 100
                )

                return min(float(score), 100.0)

        except Exception as e:
            self.logger.error(
                f"{method.upper()} comparison failed: {str(e)}"
            )
            return 0.0

    # ------------------------------------------------------------------
    # Compare two signatures
    # ------------------------------------------------------------------

    def compare_two_signatures(
        self,
        signature1,
        signature2
    ):
        """
        Compare two signature images using all three methods.
        """

        ssim_score = self.compare_ssim(
            signature1,
            signature2
        )

        sift_score = self.compare_feature_matching(
            signature1,
            signature2,
            'sift'
        )

        orb_score = self.compare_feature_matching(
            signature1,
            signature2,
            'orb'
        )

        combined = (
            ssim_score * self.SSIM_WEIGHT
            + sift_score * self.SIFT_WEIGHT
            + orb_score * self.ORB_WEIGHT
        )

        is_match = combined >= self.MATCH_THRESHOLD

        return {
            'ssim_score': round(ssim_score, 2),
            'sift_score': round(sift_score, 2),
            'orb_score': round(orb_score, 2),
            'combined_score': round(combined, 2),
            'is_match': is_match
        }

    # ------------------------------------------------------------------
    # Investigate one student
    # ------------------------------------------------------------------

    def investigate_student(
        self,
        student_no,
        xml_path,
        image_directory
    ):
        """
        Investigate one student's signatures across all attendance sheets.

        Args:
            student_no: Student number.
            xml_path: Path to info.xml.
            image_directory: Directory containing attendance images.
        """

        self.logger.info(
            f"Investigating student: {student_no}"
        )

        # --------------------------------------------------------------
        # Get students from XML
        # --------------------------------------------------------------

        students_dict = self.get_students_from_xml(
            xml_path
        )

        if not students_dict:
            print(
                "❌ Could not load student information."
            )
            return

        student_info = students_dict.get(
            str(student_no)
        )

        if student_info is None:
            print(
                f"❌ Student {student_no} not found in info.xml"
            )
            return

        print("\n" + "=" * 60)
        print("SIGNATURE INVESTIGATION")
        print("=" * 60)
        print(
            f"Student: "
            f"{student_info.get('name', '')}"
        )
        print(
            f"Student Number: {student_no}"
        )
        print("=" * 60)

        # --------------------------------------------------------------
        # Get attendance images
        # --------------------------------------------------------------

        image_files = self.get_image_files(
            image_directory
        )

        if not image_files:
            print(
                "❌ No attendance images found."
            )
            return

        print(
            f"\nFound {len(image_files)} attendance sheet(s)."
        )

        # --------------------------------------------------------------
        # IMPORTANT:
        #
        # SignatureDetector expects students in the same order as the
        # rows on the attendance sheet.
        #
        # We use the cleaned student list from XML.
        # --------------------------------------------------------------

        student_list = list(
            students_dict.values()
        )

        all_signatures = []

        # --------------------------------------------------------------
        # Process every attendance sheet
        # --------------------------------------------------------------

        for image_path in image_files:

            print(
                f"\n🔍 Processing: "
                f"{os.path.basename(image_path)}"
            )

            signatures = self.extract_signatures_from_sheet(
                image_path,
                student_list
            )

            student_signature = signatures.get(
                str(student_no)
            )

            if student_signature is None:

                print(
                    f"   ⚠️ Signature for {student_no} "
                    f"could not be extracted."
                )

                continue

            all_signatures.append(
                student_signature
            )

            present = student_signature[
                'signature_present'
            ]

            confidence = student_signature[
                'confidence'
            ]

            print(
                f"   Signature detected: "
                f"{'YES' if present else 'NO'}"
            )

            print(
                f"   Detection confidence: "
                f"{confidence:.2f}"
            )

            print(
                f"   Saved: "
                f"{student_signature['path']}"
            )

        # --------------------------------------------------------------
        # Need at least two signatures
        # --------------------------------------------------------------

        if len(all_signatures) < 2:

            print(
                "\n⚠️ Not enough signature samples "
                "for comparison."
            )

            print(
                "At least 2 valid signature samples "
                "are required."
            )

            return

        # --------------------------------------------------------------
        # Compare every pair
        # --------------------------------------------------------------

        print(
            f"\n📊 Comparing "
            f"{len(all_signatures)} signature samples..."
        )

        print("-" * 60)

        comparison_results = []

        for i in range(
            len(all_signatures)
        ):

            for j in range(
                i + 1,
                len(all_signatures)
            ):

                signature1 = all_signatures[i]
                signature2 = all_signatures[j]

                result = self.compare_two_signatures(
                    signature1['image'],
                    signature2['image']
                )

                comparison = {
                    'sheet1': signature1['sheet'],
                    'sheet2': signature2['sheet'],
                    'signature1_path': signature1['path'],
                    'signature2_path': signature2['path'],
                    **result
                }

                comparison_results.append(
                    comparison
                )

                print(
                    f"\n📅 "
                    f"{signature1['sheet']} "
                    f"vs "
                    f"{signature2['sheet']}"
                )

                print(
                    f"   SSIM: "
                    f"{result['ssim_score']:.1f}%"
                )

                print(
                    f"   SIFT: "
                    f"{result['sift_score']:.1f}%"
                )

                print(
                    f"   ORB: "
                    f"{result['orb_score']:.1f}%"
                )

                print(
                    f"   Combined: "
                    f"{result['combined_score']:.1f}%"
                )

                print(
                    f"   Match: "
                    f"{'YES' if result['is_match'] else 'NO'}"
                )

        # --------------------------------------------------------------
        # Generate report
        # --------------------------------------------------------------

        self.generate_report(
            student_no,
            student_info,
            comparison_results,
            all_signatures
        )

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_report(
        self,
        student_no,
        student_info,
        results,
        signatures
    ):
        """
        Generate TXT and JSON investigation reports.
        """

        timestamp = datetime.now().strftime(
            '%Y%m%d_%H%M%S'
        )

        report_dir = (
            'reports/investigation'
        )

        os.makedirs(
            report_dir,
            exist_ok=True
        )

        # --------------------------------------------------------------
        # Calculate summary
        # --------------------------------------------------------------

        matches = sum(
            1
            for result in results
            if result['is_match']
        )

        total_pairs = len(results)

        match_rate = (
            matches / total_pairs * 100
            if total_pairs > 0
            else 0
        )

        if total_pairs == 0:

            conclusion = (
                "No comparison results available."
            )

        elif match_rate >= 70:

            conclusion = (
                "Signatures are likely consistent."
            )

        elif match_rate >= 40:

            conclusion = (
                "Signatures show some variation."
            )

        else:

            conclusion = (
                "Signatures show significant variation "
                "- possible forgery."
            )

        # --------------------------------------------------------------
        # Text report
        # --------------------------------------------------------------

        report_path = os.path.join(
            report_dir,
            f'investigation_'
            f'{student_no}_'
            f'{timestamp}.txt'
        )

        with open(
            report_path,
            'w',
            encoding='utf-8'
        ) as file:

            file.write(
                "=" * 60 + "\n"
            )

            file.write(
                "SIGNATURE INVESTIGATION REPORT\n"
            )

            file.write(
                "=" * 60 + "\n"
            )

            file.write(
                f"Generated: "
                f"{datetime.now()}\n"
            )

            file.write(
                f"Student Number: "
                f"{student_no}\n"
            )

            file.write(
                f"Student Name: "
                f"{student_info.get('name', '')}\n"
            )

            file.write(
                f"Signature Samples: "
                f"{len(signatures)}\n"
            )

            file.write(
                "=" * 60 + "\n\n"
            )

            file.write(
                "SIGNATURE SAMPLES:\n"
            )

            file.write(
                "-" * 60 + "\n"
            )

            for signature in signatures:

                file.write(
                    f"\nSheet: "
                    f"{signature['sheet']}\n"
                )

                file.write(
                    f"Signature Present: "
                    f"{'YES' if signature['signature_present'] else 'NO'}\n"
                )

                file.write(
                    f"Detection Confidence: "
                    f"{signature['confidence']:.4f}\n"
                )

                file.write(
                    f"Image: "
                    f"{signature['path']}\n"
                )

            file.write(
                "\n" + "=" * 60 + "\n"
            )

            file.write(
                "COMPARISON RESULTS:\n"
            )

            file.write(
                "-" * 60 + "\n"
            )

            for result in results:

                file.write(
                    f"\n"
                    f"{result['sheet1']} "
                    f"vs "
                    f"{result['sheet2']}:\n"
                )

                file.write(
                    f"  SSIM Score: "
                    f"{result['ssim_score']:.1f}%\n"
                )

                file.write(
                    f"  SIFT Score: "
                    f"{result['sift_score']:.1f}%\n"
                )

                file.write(
                    f"  ORB Score: "
                    f"{result['orb_score']:.1f}%\n"
                )

                file.write(
                    f"  Combined Score: "
                    f"{result['combined_score']:.1f}%\n"
                )

                file.write(
                    f"  Match: "
                    f"{'YES' if result['is_match'] else 'NO'}\n"
                )

            file.write(
                "\n" + "=" * 60 + "\n"
            )

            file.write(
                "SUMMARY\n"
            )

            file.write(
                "=" * 60 + "\n"
            )

            file.write(
                f"Total comparison pairs: "
                f"{total_pairs}\n"
            )

            file.write(
                f"Matching pairs: "
                f"{matches}\n"
            )

            file.write(
                f"Match rate: "
                f"{match_rate:.1f}%\n"
            )

            file.write(
                f"Conclusion: "
                f"{conclusion}\n"
            )

        print(
            f"\n📄 Report saved to: "
            f"{report_path}"
        )

        # --------------------------------------------------------------
        # JSON report
        # --------------------------------------------------------------

        json_path = os.path.join(
            report_dir,
            f'investigation_'
            f'{student_no}_'
            f'{timestamp}.json'
        )

        json_data = {
            'student_no': str(student_no),
            'student_name': student_info.get(
                'name',
                ''
            ),
            'timestamp': timestamp,
            'signature_samples': [
                {
                    'sheet': signature['sheet'],
                    'path': signature['path'],
                    'signature_present':
                        signature['signature_present'],
                    'confidence':
                        signature['confidence'],
                    'ink_ratio':
                        signature['ink_ratio']
                }
                for signature in signatures
            ],
            'comparison_results': results,
            'summary': {
                'total_pairs': total_pairs,
                'matches': matches,
                'match_rate': round(
                    match_rate,
                    2
                ),
                'conclusion': conclusion
            }
        }

        with open(
            json_path,
            'w',
            encoding='utf-8'
        ) as file:

            json.dump(
                json_data,
                file,
                indent=2,
                default=str
            )

        print(
            f"📊 JSON data saved to: "
            f"{json_path}"
        )


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            'Student Signature Investigation'
        ),
        formatter_class=(
            argparse.RawDescriptionHelpFormatter
        ),
        epilog="""
Examples:

  python investigate.py 10000409 data/info.xml data/sample_images/

  python investigate.py 10000409 data/info.xml data/sample_images/
        """
    )

    parser.add_argument(
        'student_no',
        help='Student number to investigate'
    )

    parser.add_argument(
        'xml_path',
        help='Path to info.xml containing student information'
    )

    parser.add_argument(
        'image_directory',
        help=(
            'Directory containing attendance '
            'sheet images'
        )
    )

    args = parser.parse_args()

    investigator = SignatureInvestigator()

    investigator.investigate_student(
        args.student_no,
        args.xml_path,
        args.image_directory
    )


if __name__ == '__main__':
    main()