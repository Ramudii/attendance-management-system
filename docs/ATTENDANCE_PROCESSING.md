# Attendance Processing Module Documentation

**Author:** Ashan Madusanka (Member 5)  
**Branch:** `feature/attendance-processing`  
**Module:** CS402.3 — Computer Graphics and Visualization

---

## Overview

The Attendance Processing module is the central hub that orchestrates the complete workflow from raw signature detection results through to stored attendance records in the database. It acts as the bridge between:

- **Upstream:** OCR extraction and signature detection
- **Downstream:** Database storage and visualization

### Architecture Position

```
┌─────────────────────────────────────────────────┐
│ Image Processing Pipeline (Member 2)            │
│ - Load, denoise, binarize, edge detection       │
└────────────────┬────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────┐
│ OCR Extraction (Member 3)                       │
│ - Read student index text                       │
│ - Load master student list from XML             │
│ - Provide: headers, extracted students          │
└────────────────┬────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────┐
│ Signature Detection (Member 4)                  │
│ - Analyze signature cells                       │
│ - Determine Present/Absent status               │
│ - Provide: confidence scores, metrics           │
└────────────────┬────────────────────────────────┘
                 │
                 ↓ signature_results
    ╔════════════════════════════════════╗
    ║  ATTENDANCE PROCESSING (YOUR WORK) ║  ⭐
    ║  ════════════════════════════════  ║
    ║                                    ║
    ║ 1. Normalize detection results     ║
    ║ 2. Map students to master list     ║
    ║ 3. Validate data integrity         ║
    ║ 4. Generate reports                ║
    ║ 5. Prepare for database            ║
    ╚════════════════┬═══════════════════╝
                     │
                     ↓ normalized_records
┌─────────────────────────────────────────────────┐
│ Database Management (Member 6)                  │
│ - Store student records                         │
│ - Store attendance records with date/lecturer   │
│ - Track lecture history                         │
└────────────────┬────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────┐
│ Visualization (Member 7)                        │
│ - Generate attendance charts                    │
│ - Show per-student statistics                   │
│ - Produce reports                               │
└─────────────────────────────────────────────────┘
```

---

## Components

### 1. AttendanceProcessor

**File:** `src/attendance/attendance_processor.py`

Normalizes raw signature detection results into a standardized format.

#### Key Methods

```python
process(signature_results, ocr_data) → List[Dict]
    Process signature detection results and normalize to standard format.
    
    Input: Raw detection results from SignatureDetector
    Output: Normalized records with consistent structure
    
validate_records() → bool
    Check all processed records for required fields and data integrity.
    
get_statistics() → Dict
    Generate summary statistics (totals, rates, confidence).
```

#### Output Format

```python
{
    "student_id": "10000409",
    "name": "M S Dilshanika Perera",
    "status": "Present",              # or "Absent"
    "signature_present": True,        # or False
    "confidence": 0.9523,             # 0.0-1.0
    "timestamp": "2026-08-10T21:30:25.123456",
    "metrics": {...},                 # Raw ink analysis
    "found_in_ocr": True,             # Was in OCR extraction?
    "row_index": 0                    # Position in sheet
}
```

### 2. AttendanceManager

**File:** `src/attendance/attendance_manager.py`

Orchestrates the complete attendance workflow.

#### Key Methods

```python
parse_date(date_str) → str (YYYY-MM-DD)
    Parse date from various formats:
    - DD/MM/YYYY or DD-MM-YYYY
    - DD Month YYYY (e.g., "10 August 2026")
    - YYYY/MM/DD or YYYY-MM-DD

map_students(extracted_students, master_students, signature_results) → List[Dict]
    Match signature detection results with master student list.
    Enriches records with student information from XML.
    
    Returns: Complete attendance records ready for database

validate_records(records) → Tuple[bool, List[str]]
    Validate records for:
    - All required fields present
    - Valid status values (Present/Absent)
    - Confidence scores in range 0-1
    
    Returns: (is_valid, error_messages)

record_attendance(image_path, xml_path, extracted_data, signature_results) → Dict
    Complete workflow from raw results to database storage:
    1. Load master student list from XML
    2. Map students to detection results
    3. Validate records
    4. Save to database
    5. Check for duplicates
    
    Returns: Status dict with saved count and records

generate_summary(attendance_records) → Dict
    Create summary statistics:
    - Total students
    - Present/absent counts
    - Attendance rate (%)
    - Average confidence
    - OCR coverage (%)

get_student_attendance_summary(student_no) → Dict
    Query database for individual student's complete attendance history.
    
    Returns: Student info + attendance statistics

generate_console_display(summary) → str
    Format summary as nicely formatted console output.
```

#### Date Parsing Examples

```python
parse_date("10/08/2026")          → "2026-08-10"
parse_date("10-08-2026")          → "2026-08-10"
parse_date("10 August 2026")      → "2026-08-10"
parse_date("2026-08-10")          → "2026-08-10"
parse_date("10 Aug 2026")         → "2026-08-10"
```

### 3. ReportGenerator

**File:** `src/attendance/report_generator.py`

Generates various attendance reports and export formats.

#### Key Methods

```python
generate_summary(records) → Dict
    Create summary report with:
    - Total students
    - Present/absent counts
    - Attendance rate
    - Average confidence
    - OCR coverage
    - Generation timestamp

generate_detailed_report(records, lecture_date, lecturer) → Dict
    Create comprehensive report including:
    - Summary statistics
    - Lecture metadata
    - Per-student details

export_to_json(records, output_path, lecture_date, lecturer) → bool
    Export attendance records to JSON file.
    
    JSON Structure:
    {
        "summary": {...},
        "lecture_info": {...},
        "students": [...]
    }

export_to_csv(records, output_path, lecture_date, lecturer) → bool
    Export attendance records to CSV file.
    
    CSV Columns:
    student_id, name, status, confidence, signature_present, found_in_ocr
```

---

## Data Flow

### 1. Input from Signature Detection

```python
signature_results = [
    {
        'row_index': 0,
        'student_no': '10000409',
        'name': 'M S Dilshanika Perera',
        'signature_present': True,
        'confidence': 0.9523,
        'metrics': {
            'ink_ratio': 0.12345,
            'ink_pixels': 1234,
            'cell_area': 10000,
            ...
        }
    },
    # ... more results
]
```

### 2. Input from OCR

```python
extracted_data = {
    'header': {
        'module': 'CS402.3 - Computer Graphics and Visualization',
        'lecturer': 'Dr. Rasika Ranaweera',
        'date': '2026-08-10',
        'programme': 'BSc (Hons) in Software Engineering - 2016.1'
    },
    'students': [
        {
            'student_no': '10000409',
            'name': 'M S Dilshanika Perera',
            'title': 'Ms'
        },
        # ... more students
    ]
}
```

### 3. Processing Steps

```
Signature Results
    ↓ (AttendanceProcessor)
Normalize & validate
    ↓ (AttendanceManager)
Map to master list + enrich
    ↓ (AttendanceManager)
Validate data integrity
    ↓ (AttendanceManager)
Generate summary statistics
    ↓ (ReportGenerator)
Export to JSON/CSV
    ↓
Ready for Database & Visualization
```

### 4. Output to Database

```python
for record in attendance_records:
    db.insert_student(
        student_no=record['student_no'],
        name=record['name'],
        title=record.get('title', 'Mr/Ms')
    )
    
    db.insert_attendance(
        student_no=record['student_no'],
        lecture_date='2026-08-10',
        status=record['status'],  # 'Present' or 'Absent'
        lecturer_name='Dr. Rasika Ranaweera',
        module='CS402.3 - Computer Graphics and Visualization',
        image_filename='data/sample_images/1.jpeg',
        confidence=record['confidence']
    )
```

---

## Key Features

### 1. Robust Date Parsing
Handles various date formats automatically:
- European format (DD/MM/YYYY)
- US format (MM/DD/YYYY)
- Full date names (10 August 2026)
- 2-digit years (26 for 2026)

### 2. Student Mapping
- Matches signature detection results by student_no
- Enriches with master student list from XML
- Tracks which students were found in OCR extraction
- Handles missing or extra students gracefully

### 3. Data Validation
- Checks all required fields present
- Validates status values ('Present' or 'Absent')
- Verifies confidence scores in range 0-1
- Reports specific validation errors

### 4. Duplicate Prevention
- Checks if attendance already recorded for student on date
- Skips duplicates to prevent data inconsistency
- Logs duplicate attempts for audit trail

### 5. Statistical Analysis
- Calculates attendance rate (%)
- Computes average detection confidence
- Tracks OCR coverage (% of students found)
- Generates comprehensive summaries

### 6. Multiple Export Formats
- **JSON:** Full metadata + per-student details (for database/visualization)
- **CSV:** Spreadsheet format (for external analysis)
- **Console:** Formatted text output (for immediate feedback)

---

## Integration Guide

### With OCR Module (Member 3)

```python
# Get master student list
from src.ocr.ocr_extractor import OCRExtractor
ocr = OCRExtractor()
master_students = ocr.parse_info_xml('data/info.xml')

# Pass to AttendanceManager
manager = AttendanceManager(db_manager)
records = manager.map_students(
    extracted_students=ocr_data['students'],
    master_students=master_students,
    signature_results=signature_results
)
```

### With Signature Detection (Member 4)

```python
from src.detection.signature_detector import SignatureDetector

detector = SignatureDetector()
signature_results = detector.detect(image, students=student_list)

# Pass to AttendanceProcessor
processor = AttendanceProcessor()
normalized = processor.process(signature_results, ocr_data)
```

### With Database (Member 6)

```python
from src.database.database_manager import DatabaseManager

db = DatabaseManager()
manager = AttendanceManager(db_manager=db)

result = manager.record_attendance(
    image_path='data/sample_images/1.jpeg',
    xml_path='data/info.xml',
    extracted_data=ocr_data,
    signature_results=signature_results
)

print(f"Saved {result['saved_count']} records to database")
```

### With Visualization (Member 7)

```python
from src.attendance.report_generator import ReportGenerator

generator = ReportGenerator()
summary = generator.generate_summary(attendance_records)

# Export for visualization
generator.export_to_json(
    records=attendance_records,
    output_path='reports/attendance_report.json',
    lecture_date='2026-08-10',
    lecturer='Dr. Rasika Ranaweera'
)
```

---

## Error Handling

The module handles various error scenarios gracefully:

### Missing Master Student List
- Returns error but continues processing
- Marks students as "Unknown" with role placeholder

### Invalid Date Formats
- Logs warning and uses current date as fallback
- Continues with other records

### Database Connection Issues
- Logs error but returns processed records
- Allows offline processing with export capability

### Validation Failures
- Returns list of specific validation errors
- Includes partial results for troubleshooting
- Does not abort; continues with valid records

### Missing Signatures/Students
- Logs debug message per student
- Sets status to 'Absent' for missing signatures
- Tracks OCR coverage for audit

---

## Testing Checklist

- [ ] Date parsing with all supported formats
- [ ] Student mapping with 100% coverage
- [ ] Duplicate detection and skipping
- [ ] Confidence score ranges (0-1)
- [ ] Status validation (Present/Absent only)
- [ ] JSON export with valid structure
- [ ] CSV export with correct headers
- [ ] Console output formatting
- [ ] Database integration (when available)
- [ ] Error handling with partial results

---

## Code Example: Complete Workflow

```python
from src.attendance.attendance_manager import AttendanceManager
from src.attendance.attendance_processor import AttendanceProcessor
from src.attendance.report_generator import ReportGenerator
from src.database.database_manager import DatabaseManager

# Initialize components
db = DatabaseManager()
manager = AttendanceManager(db_manager=db)
processor = AttendanceProcessor()
generator = ReportGenerator()

# Process attendance (end-to-end)
result = manager.record_attendance(
    image_path='data/sample_images/1.jpeg',
    xml_path='data/info.xml',
    extracted_data=ocr_data,
    signature_results=signature_results
)

if result['success']:
    # Generate summary
    summary = generator.generate_summary(result['records'])
    
    # Export reports
    generator.export_to_json(
        records=result['records'],
        output_path='reports/attendance.json',
        lecture_date=result['lecture_date'],
        lecturer=result['lecturer']
    )
    
    generator.export_to_csv(
        records=result['records'],
        output_path='reports/attendance.csv',
        lecture_date=result['lecture_date'],
        lecturer=result['lecturer']
    )
    
    # Display results
    print(manager.generate_console_display(summary))
else:
    print(f"Error: {result['error']}")
```

---

## Summary

The Attendance Processing module:

✅ Normalizes signature detection results  
✅ Maps students to master list  
✅ Validates data integrity  
✅ Handles multiple date formats  
✅ Generates comprehensive summaries  
✅ Exports to multiple formats  
✅ Integrates with database  
✅ Provides detailed error reporting  
✅ Prevents duplicate records  
✅ Tracks processing confidence

Your contribution is **critical to the entire system** - it transforms raw detection data into actionable attendance records!

---

**Ready for Integration** ✅  
Awaiting OCR (Member 3) and Signature Detection (Member 4) completion for full end-to-end testing.
