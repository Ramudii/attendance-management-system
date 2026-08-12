#!/usr/bin/env python3
import argparse
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
import json

# Add src to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from src.logger import setup_logger
from src.database.database_manager import DatabaseManager
from src.image_processing.image_processor import ImageProcessor
from src.ocr.ocr_extractor import OCRExtractor
from src.ocr.xml_parser import XMLParser
from src.ocr.data_cleaner import DataCleaner
from src.detection import SignatureDetector
from src.attendance.attendance_manager import AttendanceManager


class SAMS:
    """
    Main application class for Student Attendance Management System
    """
    
    def __init__(self, verbose=False):
        """
        Initialize SAMS application
        
        Args:
            verbose: Enable verbose logging
        """
        self.verbose = verbose
        self.logger = setup_logger('sams')
        
        # Setup environment
        self.setup_environment()
        
        # Initialize Database Manager
        try:
            self.db = DatabaseManager()
            self.logger.info("Database connection established")
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            self.db = None
        
        self.logger.info("=" * 60)
        self.logger.info("SAMS - Student Attendance Management System")
        self.logger.info(f"Initialized at: {datetime.now()}")
        self.logger.info("=" * 60)
    
    def setup_environment(self):
        """Setup required directories and environment"""
        self.logger.info("Setting up environment...")
        
        required_dirs = [
            'data',
            'data/database',
            'data/sample_images',
            'reports',
            'reports/progress_images',
            'reports/charts',
            'reports/investigation',
            'tests',
            'tests/test_results',
            'logs',
            'signature_images',
            'docs'
        ]
        
        for directory in required_dirs:
            try:
                os.makedirs(directory, exist_ok=True)
                if self.verbose:
                    self.logger.debug(f"Created directory: {directory}")
            except Exception as e:
                self.logger.warning(f"Could not create {directory}: {e}")
        
        self.logger.info("Environment setup complete")
    
    def load_roster(self, xml_path):
        """
        Load the student roster in sheet order for the signature detector.

        The detector matches each signature cell to a student by row position,
        so the list must preserve the order the students appear in info.xml.

        Args:
            xml_path: Path to info.xml

        Returns:
            list: Dicts with 'student_no' and 'name', in sheet order.
        """
        parsed = XMLParser(logger=self.logger).parse(xml_path)
        cleaner = DataCleaner()

        roster = [
            {
                'student_no': cleaner.clean_student_no(entry.get('student_no', '')),
                'name': cleaner.clean_name(entry.get('name', '')),
            }
            for entry in parsed.get('raw_students', [])
            if entry.get('student_no')
        ]

        self.logger.info(f"Loaded {len(roster)} students from {xml_path}")
        return roster

    def process_attendance(self, image_path, xml_path, lecture_date=None):
        """
        Main attendance processing pipeline

        Args:
            image_path: Path to signing sheet image
            xml_path: Path to info.xml file
            lecture_date: Optional date for this sheet

        Returns:
            dict: Processing results
        """
        self.logger.info(f"Processing attendance from {image_path}")
        self.logger.info(f"Using XML data from {xml_path}")
        
        # Check if files exist
        if not os.path.exists(image_path):
            error_msg = f"Image file not found: {image_path}"
            self.logger.error(error_msg)
            return {'success': False, 'error': error_msg}
        
        if not os.path.exists(xml_path):
            error_msg = f"XML file not found: {xml_path}"
            self.logger.error(error_msg)
            return {'success': False, 'error': error_msg}
        
        try:
            # ---- Step 1: image preprocessing -------------------------------
            # Runs the full preprocessing pipeline. Its main purpose here is to
            # write the per-stage progress images the report requires; the
            # detector re-reads the sheet with its own deskewing pipeline.
            self.logger.info("Step 1/4: Image preprocessing")
            processor = ImageProcessor()
            processor.process(image_path)
            progress_grid = processor.create_progress_grid()

            # ---- Step 2: OCR and roster ------------------------------------
            self.logger.info("Step 2/4: OCR extraction")
            ocr = OCRExtractor(logger=self.logger)
            extracted_data = ocr.extract_sheet_data(image_path, xml_path)

            # ---- Step 3: signature detection -------------------------------
            self.logger.info("Step 3/4: Signature detection")
            roster = self.load_roster(xml_path)
            detector = SignatureDetector(save_progress=True)
            detection = detector.detect(image_path, students=roster)

            if not detection['success']:
                # The detector still returns an all-absent result set, so the
                # run continues and the failure is reported to the user.
                self.logger.warning(
                    f"Detection incomplete: {detection.get('error')}"
                )

            # ---- Step 4: attendance recording ------------------------------
            self.logger.info("Step 4/4: Attendance recording")
            manager = AttendanceManager(db_manager=self.db, logger=self.logger)
            recording = manager.record_attendance(
                image_path,
                xml_path,
                extracted_data,
                detection['results'],
                lecture_date=lecture_date,
            )

            if not recording['success']:
                return {
                    'success': False,
                    'error': recording.get('error', 'Attendance recording failed'),
                    'validation_errors': recording.get('validation_errors', []),
                }

            summary = manager.generate_summary(recording['records'])
            self.logger.info("Processing complete")

            result = {
                'success': True,
                'summary': summary,
                'lecture_date': recording.get('lecture_date'),
                'lecturer': recording.get('lecturer'),
                'saved_count': recording.get('saved_count'),
                'skew_angle': detection.get('skew_angle'),
                'progress_grid': progress_grid,
                'progress_images': detection.get('progress_images', []),
            }

            if not detection['success']:
                result['message'] = (
                    f"Signature detection failed ({detection.get('error')}); "
                    "all students recorded as absent."
                )

            return result

        except Exception as e:
            self.logger.error(f"Error processing attendance: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def process_batch(self, image_dir, xml_path):
        """
        Process multiple images in batch
        
        Args:
            image_dir: Directory containing images
            xml_path: Path to info.xml
            
        Returns:
            dict: Batch processing results
        """
        self.logger.info(f"Batch processing from {image_dir}")
        
        # Get all image files
        image_files = []
        valid_extensions = {'.jpeg', '.jpg', '.png', '.tiff', '.bmp'}
        
        if not os.path.exists(image_dir):
            return {
                'success': False,
                'error': f"Directory not found: {image_dir}"
            }
        
        for file in os.listdir(image_dir):
            ext = os.path.splitext(file)[1].lower()
            if ext in valid_extensions:
                image_files.append(file)
        
        if not image_files:
            return {
                'success': False,
                'error': f"No image files found in {image_dir}"
            }
        
        self.logger.info(f"Found {len(image_files)} images")
        
        results = {}
        for image_file in sorted(image_files):
            image_path = os.path.join(image_dir, image_file)
            self.logger.info(f"Processing: {image_file}")
            
            result = self.process_attendance(image_path, xml_path)
            results[image_file] = result
        
        return {
            'success': True,
            'results': results,
            'total_processed': len(image_files)
        }


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Student Attendance Management System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process single image
  python sams.py data/sample_images/1.jpeg data/info.xml
  
  # Process with verbose output
  python sams.py data/sample_images/1.jpeg data/info.xml --verbose
  
  # Batch process all images
  python sams.py --batch data/sample_images/ data/info.xml
  
  # Save results to JSON
  python sams.py data/sample_images/1.jpeg data/info.xml --output report.json
  
  # Batch with output
  python sams.py --batch data/sample_images/ data/info.xml --output batch_results.json
        """
    )
    
    parser.add_argument('image', 
                       nargs='?',
                       help='Path to signing sheet image file')
    parser.add_argument('info', 
                       nargs='?',
                       help='Path to info.xml file containing student data')
    parser.add_argument('--batch', '-b',
                       help='Process all images in directory')
    parser.add_argument('--verbose', '-v', 
                       action='store_true', 
                       help='Enable verbose output')
    parser.add_argument('--date', '-d',
                       help='Lecture date for this sheet, e.g. 21.06.2019. '
                            'Single-image mode only; in batch mode each sheet '
                            'takes its date from its filename.')
    parser.add_argument('--output', '-o',
                       help='Output file for results (JSON format)')
    
    args = parser.parse_args()
    
    # Setup logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    # Initialize system
    sams = SAMS(verbose=args.verbose)
    
    # Check for batch processing
    if args.batch:
        # With --batch the directory is consumed by the flag, so the XML path
        # lands in the first positional slot instead of the second.
        xml_path = args.info or args.image or 'data/info.xml'
        result = sams.process_batch(args.batch, xml_path)
        
        if result['success']:
            print("\n" + "=" * 60)
            print("BATCH PROCESSING COMPLETE")
            print("=" * 60)
            print(f"Total Images Processed: {result['total_processed']}")
            
            # Display each result
            for image_file, image_result in result['results'].items():
                status = "✅" if image_result['success'] else "❌"
                print(f"\n{status} {image_file}")
                if image_result['success']:
                    summary = image_result['summary']
                    print(f"   Students: {summary['total_students']}")
                    print(f"   Present: {summary['present']}")
                    print(f"   Absent: {summary['absent']}")
                    print(f"   Rate: {summary['attendance_rate']:.1f}%")
                else:
                    print(f"   Error: {image_result.get('error', 'Unknown error')}")
            
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(result, f, indent=2, default=str)
                print(f"\n📁 Results saved to: {args.output}")
        else:
            print(f"\n❌ Batch processing failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
        
        return
    
    # Single image processing
    if not args.image or not args.info:
        parser.print_help()
        sys.exit(1)
    
    # Process single image
    result = sams.process_attendance(args.image, args.info, lecture_date=args.date)
    
    if result['success']:
        summary = result['summary']
        print("\n" + "=" * 60)
        print("ATTENDANCE PROCESSING COMPLETE")
        print("=" * 60)
        print(f"Total Students: {summary['total_students']}")
        print(f"Present: {summary['present']} ✅")
        print(f"Absent: {summary['absent']} ❌")
        print(f"Attendance Rate: {summary['attendance_rate']:.1f}%")
        if result.get('lecture_date'):
            print(f"Lecture Date: {result['lecture_date']}")
        if result.get('skew_angle') is not None:
            print(f"Skew Corrected: {result['skew_angle']}°")
        print("=" * 60)

        # Per-student breakdown - the coursework asks who was present/absent.
        if summary.get('details'):
            print(f"\n{'Student No':<12} {'Name':<32} {'Status':<10} Conf")
            print("-" * 60)
            for record in summary['details']:
                icon = "✅" if record['status'] == 'Present' else "❌"
                print(f"{record['student_no']:<12} "
                      f"{record['name'][:31]:<32} "
                      f"{icon} {record['status']:<7} "
                      f"{record.get('confidence', 0):.2f}")
            print("-" * 60)

        if result.get('progress_grid'):
            print(f"\n📊 Progress images: {result['progress_grid']}")

        if result.get('message'):
            print(f"\nℹ️ {result['message']}")
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            print(f"\n📁 Results saved to: {args.output}")
    else:
        print(f"\n❌ Error: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()