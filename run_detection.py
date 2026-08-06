#!/usr/bin/env python3
"""Stand-alone driver for the signature detection module.

Lets the signature-detection work be demonstrated and tested on its own,
before the OCR and attendance modules are integrated into ``sams.py``.

Usage:
    python run_detection.py data/sample_images/1.jpeg
    python run_detection.py --all
    python run_detection.py --all --output detection_results.json

Author: Heshan De Silva - Signature Detection
"""

import argparse
import glob
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.detection import SignatureDetector
from src.ocr.data_cleaner import DataCleaner
from src.ocr.xml_parser import XMLParser

DEFAULT_INFO_XML = 'data/info.xml'

# Fallback roster, used only when info.xml is missing or unreadable so that the
# detector can still be demonstrated stand-alone.
DEFAULT_STUDENTS = [
    {'student_no': '10000409', 'name': 'M S Dilshanika Perera'},
    {'student_no': '10009301', 'name': 'C W M A Shehan Abeyrathne'},
    {'student_no': '10009302', 'name': 'B A K M Chithrananda'},
    {'student_no': '10009303', 'name': 'W Shashini Minosha De Silva'},
    {'student_no': '10009304', 'name': 'K L Udara Maduranga Liyanage'},
    {'student_no': '10009306', 'name': 'Hansa Anuradha Wickramanayake'},
]


def load_students(xml_path):
    """Load the roster from ``info.xml`` using the OCR module's parser.

    Reading the roster needs no OCR engine, so ``XMLParser`` and ``DataCleaner``
    are used directly rather than ``OCRExtractor`` (which additionally requires a
    working Tesseract install). ``OCRExtractor.parse_info_xml`` is a thin wrapper
    around exactly these two calls.

    Args:
        xml_path: Path to info.xml.

    Returns:
        list[dict]: Students in sheet order, each with 'student_no' and 'name'.
            Falls back to DEFAULT_STUDENTS when the file yields no records.
    """
    if not os.path.exists(xml_path):
        print(f"[Detection] info.xml not found at {xml_path}; using built-in roster.")
        return DEFAULT_STUDENTS

    parsed = XMLParser().parse(xml_path)
    cleaner = DataCleaner()

    # 'raw_students' preserves document order, which is the sheet row order.
    students = [
        {
            'student_no': cleaner.clean_student_no(entry.get('student_no', '')),
            'name': cleaner.clean_name(entry.get('name', '')),
        }
        for entry in parsed.get('raw_students', [])
        if entry.get('student_no')
    ]

    if not students:
        print(f"[Detection] No students parsed from {xml_path}; using built-in roster.")
        return DEFAULT_STUDENTS

    print(f"[Detection] Loaded {len(students)} students from {xml_path}")
    return students


def print_report(outcome):
    """Print one sheet's detection outcome as a table."""
    print('\n' + '=' * 72)
    print(f"SIGNATURE DETECTION - {os.path.basename(outcome['image_path'])}")
    print('=' * 72)

    if not outcome['success']:
        print(f"FAILED: {outcome['error']}")
        return

    print(f"Skew corrected: {outcome['skew_angle']} degrees")
    print(f"Progress images: {len(outcome['progress_images'])}")
    print('-' * 72)
    print(f"{'#':<3} {'Student No':<12} {'Name':<32} {'Status':<8} {'Ink':<8} Conf")
    print('-' * 72)

    for result in outcome['results']:
        status = 'Present' if result['signature_present'] else 'Absent'
        print(f"{result['row_index'] + 1:<3} "
              f"{result['student_no']:<12} "
              f"{result['name'][:31]:<32} "
              f"{status:<8} "
              f"{result['ink_ratio']:<8.4f} "
              f"{result['confidence']:.2f}")

    present = sum(1 for r in outcome['results'] if r['signature_present'])
    total = len(outcome['results'])
    rate = (present / total * 100) if total else 0.0
    print('-' * 72)
    print(f"Present: {present}/{total}  ({rate:.1f}%)")


def main():
    parser = argparse.ArgumentParser(
        description='Detect signatures on NSBM signing sheets')
    parser.add_argument('image', nargs='?', help='Path to a signing-sheet image')
    parser.add_argument('--all', action='store_true',
                        help='Process every image in data/sample_images/')
    parser.add_argument('--info', default=DEFAULT_INFO_XML,
                        help='Path to info.xml holding the student roster '
                             f'(default: {DEFAULT_INFO_XML})')
    parser.add_argument('--output', '-o', help='Write results to a JSON file')
    parser.add_argument('--no-progress', action='store_true',
                        help='Skip writing progress images')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable debug logging')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format='%(levelname)s - %(name)s - %(message)s')

    if args.all:
        paths = sorted(glob.glob('data/sample_images/*.jpeg') +
                       glob.glob('data/sample_images/*.jpg') +
                       glob.glob('data/sample_images/*.png'))
    elif args.image:
        paths = [args.image]
    else:
        parser.print_help()
        sys.exit(1)

    if not paths:
        print('No images found.')
        sys.exit(1)

    students = load_students(args.info)

    detector = SignatureDetector(save_progress=not args.no_progress)
    outcomes = []
    for path in paths:
        outcome = detector.detect(path, students=students)
        print_report(outcome)
        outcomes.append(outcome)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as handle:
            json.dump(outcomes, handle, indent=2, default=str)
        print(f"\nResults written to {args.output}")

    sys.exit(0 if all(o['success'] for o in outcomes) else 1)


if __name__ == '__main__':
    main()
