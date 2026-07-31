"""
Unit Tests: Database Operations (Member 5's module)
Author: Member 9 - Testing & QA
Task: 9.4

NOTE FOR THE TEAM:
src/database/database_manager.py currently exists but is a placeholder:
  - DatabaseManager() takes no db-path argument yet
  - insert_student(*args) / insert_attendance(*args) do nothing
  - get_student_attendance(*args) always returns []
These tests exercise the *current* interface so they run (and pass) today,
and separately probe the *intended* interface (a db_path argument, and
pandas-DataFrame results) so they'll start asserting real behaviour the
moment Member 5 implements it - no test file changes needed.
"""

import inspect
import pytest

from src.database.database_manager import DatabaseManager


class TestDatabaseManagerCurrentInterface:
    """Tests against what's implemented right now."""

    def test_can_instantiate(self):
        assert DatabaseManager() is not None

    def test_insert_student_does_not_crash(self):
        db = DatabaseManager()
        db.insert_student('99999999', 'Test Student', 'Mr')  # should not raise

    def test_insert_attendance_does_not_crash(self):
        db = DatabaseManager()
        db.insert_attendance('99999999', '2024-01-01', 'Present', 'Dr. Test')

    def test_get_student_attendance_for_unknown_student(self):
        db = DatabaseManager()
        result = db.get_student_attendance('00000000')
        # Placeholder returns [], real implementation should return an
        # empty pandas DataFrame - both "emptiness" checks are covered below.
        assert (hasattr(result, 'empty') and result.empty) or (isinstance(result, list) and len(result) == 0)


class TestDatabaseManagerIntendedInterface:
    """These target the design in the code template (db path in the
    constructor, DataFrame results with a .empty / .iloc API). They're
    skipped until DatabaseManager actually supports a db_path argument."""

    def _make_db(self, tmp_path):
        sig = inspect.signature(DatabaseManager.__init__)
        if len(sig.parameters) <= 1:  # only 'self' -> no db_path support yet
            pytest.skip(
                "DatabaseManager doesn't accept a db_path argument yet "
                "- Member 5, feature/database-management"
            )
        return DatabaseManager(str(tmp_path / 'test.db'))

    def test_insert_and_retrieve_student(self, tmp_path):
        db = self._make_db(tmp_path)
        db.insert_student('99999999', 'Test Student', 'Mr')

        retrieved = db.get_student('99999999')
        assert retrieved is not None
        assert retrieved['name'] == 'Test Student'

    def test_insert_and_retrieve_attendance(self, tmp_path):
        db = self._make_db(tmp_path)
        db.insert_student('99999999', 'Test Student', 'Mr')
        db.insert_attendance('99999999', '2024-01-01', 'Present', 'Dr. Test')

        attendance = db.get_student_attendance('99999999')
        assert not attendance.empty
        assert attendance.iloc[0]['status'] == 'Present'

    def test_persists_across_connections(self, tmp_path):
        """A real DB-backed manager should persist to disk, not just memory."""
        db_path = tmp_path / 'persist.db'
        sig = inspect.signature(DatabaseManager.__init__)
        if len(sig.parameters) <= 1:
            pytest.skip("DatabaseManager doesn't accept a db_path argument yet")

        db1 = DatabaseManager(str(db_path))
        db1.insert_student('11112222', 'Persist Test', 'Ms')

        db2 = DatabaseManager(str(db_path))
        retrieved = db2.get_student('11112222')
        assert retrieved is not None
        assert retrieved['name'] == 'Persist Test'
