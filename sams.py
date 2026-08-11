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
    
    def process_attendance(self, image_path, xml_path):
        """
        Main attendance processing pipeline
        
        Args:
            image_path: Path to signing sheet image
            xml_path: Path to info.xml file
            
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
            # Placeholder for module integration
            # Will be replaced with actual imports when modules are ready
            
            self.logger.info("Step 1: Image Processing (Module needed)")
            self.logger.info("Step 2: OCR Extraction (Module needed)")
            self.logger.info("Step 3: Signature Detection (Module needed)")
            self.logger.info("Step 4: Attendance Recording (Database integration)")
            
            # Example of saving to database (using mock data until modules are ready)
            today = datetime.now().date().isoformat()
            if hasattr(self, 'db') and self.db:
                try:
                    # Mock inserting a student and their attendance
                    self.db.insert_student(student_no="TEST001", title="Mr", name="Test Student")
                    self.db.insert_attendance(
                        student_no="TEST001", 
                        lecture_date=today, 
                        status="Absent", 
                        image_filename=os.path.basename(image_path)
                    )
                    self.logger.info("Successfully recorded mock attendance in database")
                except Exception as e:
                    self.logger.error(f"Database recording error: {e}")
            
            # Mock summary for demonstration
            mock_summary = {
                'total_students': 6,
                'present': 0,
                'absent': 6,
                'attendance_rate': 0.0,
                'details': []
            }
            
            self.logger.info("Processing complete (mock mode)")
            
            return {
                'success': True,
                'summary': mock_summary,
                'message': 'Modules not yet integrated. This is a mock response.'
            }
            
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
        xml_path = args.info or 'info.xml'
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
    result = sams.process_attendance(args.image, args.info)
    
    if result['success']:
        summary = result['summary']
        print("\n" + "=" * 60)
        print("ATTENDANCE PROCESSING COMPLETE")
        print("=" * 60)
        print(f"Total Students: {summary['total_students']}")
        print(f"Present: {summary['present']} ✅")
        print(f"Absent: {summary['absent']} ❌")
        print(f"Attendance Rate: {summary['attendance_rate']:.1f}%")
        print("=" * 60)
        
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