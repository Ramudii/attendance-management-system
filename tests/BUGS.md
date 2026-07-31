# Bug & Edge-Case Tracker — Testing & QA (Member 9)

Log every bug found while running the test suite here. Update the
**Status** column as fixes land (Task 9.8), and reference the test that
caught it so we can prove regression coverage.

| ID | Found In | Description | Severity | Status | Fixed By | Test That Catches It |
|----|----------|--------------|----------|--------|----------|------------------------|
| BUG-001 | `ImageProcessor.process()` | Returns `None` silently for a non-existent image path instead of raising `FileNotFoundError` — callers can't tell "not implemented" apart from "file missing". | Medium | Open | Member 2 | `test_preprocessing.py::test_process_nonexistent_image_raises_or_errors` |
| BUG-002 | `DatabaseManager.__init__` | Doesn't accept a `db_path` argument yet, so every instance is independent / non-persistent — blocks integration testing of Step 4 (attendance recording). | High | Open | Member 5 | `test_database.py::TestDatabaseManagerIntendedInterface` |
| BUG-003 | `src/ocr/ocr_extractor.py` | File is empty — `OCRExtractor` class doesn't exist, so nothing downstream (detection, attendance, integration) can be exercised end-to-end. | High | Open | Member 3 | `test_ocr.py` (whole module skipped) |
| BUG-004 | `src/detection/signature_detector.py` | File is empty — `SignatureDetector` class doesn't exist yet. | High | Open | Member 4 | `test_detection.py` (whole module skipped) |
| BUG-005 | `src/attendance/attendance_manager.py` | File is empty — `AttendanceManager` class doesn't exist yet. | High | Open | Member 6 | `test_integration.py::TestFullPipeline` (skipped at Step 4) |
| BUG-006 | `data/` | No `info.xml` roster file is checked in, so the "run against all 5 real signing sheets" system test (9.6) can't execute. | Low | Open | Data owner | `test_sample_sheets.py` |

## How to add a new bug
1. Run `python tests/run_tests.py` and note which test failed (not skipped — an actual `FAILED`).
2. Add a row above with a fresh `BUG-0XX` ID.
3. If possible, tighten or add a test in `tests/` that reproduces it so it can't silently regress.
4. When someone fixes it, change Status to `Fixed`, fill in `Fixed By`, and confirm the linked test now passes (not skips).

## Edge cases explicitly covered by the suite
- Non-existent image path (`test_preprocessing.py`, `test_integration.py`)
- Empty `<students></students>` XML (`test_ocr.py`, `test_integration.py`)
- Unknown / invalid student number lookup (`test_database.py`, `test_integration.py`)
- Signature-less cell should not be flagged as signed (`test_detection.py`)
