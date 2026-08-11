# Bug & Edge-Case Tracker — Testing & QA (Member 9)

Log every bug found while running the test suite here. Update the
**Status** column as fixes land (Task 9.8), and reference the test that
catches it so we have proof of regression coverage.

| ID | Found In | Description | Severity | Status | Fixed By | Test That Catches It |
|----|----------|--------------|----------|--------|----------|------------------------|
| BUG-001 | `AttendanceManager.record_attendance()` | Called `db.insert_student(student_no, name, title)` but `DatabaseManager.insert_student()` expects `(student_no, title, name)` — arguments were swapped, so names and titles were written to the wrong columns. | Medium | Fixed | Member 9 | `test_integration.py::TestFullPipeline::test_records_were_persisted_to_database` |
| BUG-002 | `AttendanceManager.record_attendance()` | Called `db.insert_attendance()` with `module=` and `confidence=` keyword arguments that don't exist on `DatabaseManager.insert_attendance()`. This raised a `TypeError` on every single record, which was silently swallowed by a broad `except Exception` in the save loop — `record_attendance()` still reported `success: True`, but **zero attendance records were ever actually saved to the database**. | High | Fixed | Member 9 | `test_integration.py::TestFullPipeline::test_records_were_persisted_to_database` |

## How to add a new bug
1. Run `python -m pytest tests/ -v` and note which test failed (not skipped — an actual `FAILED`).
2. Add a row above with a fresh `BUG-0XX` ID.
3. If possible, tighten or add a test in `tests/` that reproduces it so it can't silently regress.
4. When someone fixes it, change Status to `Fixed`, fill in `Fixed By`, and confirm the linked test now passes.

## How BUG-001/002 were found
`record_attendance()` reported `success: True` and a plausible-looking
summary even though nothing was reaching the database — because the
`except Exception: continue` in the save loop hides the real error.
Unit tests (9.1-9.4) test each module in isolation, so they never call
`AttendanceManager` against a real `DatabaseManager` and couldn't catch
this. It only surfaced once the full-pipeline integration test (9.5)
independently re-queried the database after the pipeline claimed
success, instead of just trusting the returned `success` flag.

**Recommendation for the team:** narrow that `except Exception` to log
the actual exception message (`self.logger.error(..., exc_info=True)`)
so this class of bug fails loudly next time instead of silently.

## Edge cases explicitly covered by the suite
- Non-existent image path (`test_preprocessing.py`, `test_integration.py`)
- Non-existent XML path — confirmed as intentional graceful fallback
  to default metadata rather than a crash (`test_integration.py`)
- Empty `<students></students>` XML (`test_ocr.py`)
- Unknown / invalid student number lookup (`test_database.py`)
- Empty signature-detection results — everyone correctly marked absent
  rather than the pipeline crashing (`test_integration.py`)
- All 5 real signing sheets processed end-to-end without crashing,
  with plausible and *varying* attendance rates per sheet, not just
  synthetic test data (`test_sample_sheets.py`)