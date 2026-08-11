import pytest
import sqlite3
import pandas as pd
from datetime import datetime, date
from src.database.database_manager import DatabaseManager

@pytest.fixture
def db_manager(tmp_path):
    """Fixture to create an in-memory database for testing."""
    # We use a temporary file instead of :memory: because we want to test directory creation too
    db_file = tmp_path / "test_data" / "attendance.db"
    db_m = DatabaseManager(db_path=str(db_file))
    return db_m

def test_database_initialization(db_manager):
    """Test that the database initializes with the correct tables."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        
        # Check if STUDENTS table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='STUDENTS'")
        assert cursor.fetchone() is not None
        
        # Check if ATTENDANCE table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ATTENDANCE'")
        assert cursor.fetchone() is not None

def test_insert_student(db_manager):
    """Test inserting a new student."""
    db_manager.insert_student("S001", "Mr", "John Doe")
    
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT student_no, title, name FROM STUDENTS WHERE student_no='S001'")
        result = cursor.fetchone()
        
        assert result is not None
        assert result['student_no'] == "S001"
        assert result['title'] == "Mr"
        assert result['name'] == "John Doe"

def test_upsert_student(db_manager):
    """Test updating an existing student."""
    db_manager.insert_student("S001", "Mr", "John Doe")
    # Update title and name
    db_manager.insert_student("S001", "Dr", "John Smith")
    
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT title, name FROM STUDENTS WHERE student_no='S001'")
        result = cursor.fetchone()
        
        assert result['title'] == "Dr"
        assert result['name'] == "John Smith"

def test_insert_students_batch(db_manager):
    """Test batch inserting students."""
    students = [
        ("S002", "Ms", "Jane Doe"),
        ("S003", "Mr", "Bob Builder")
    ]
    db_manager.insert_students_batch(students)
    
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM STUDENTS")
        result = cursor.fetchone()
        assert result[0] == 2

def test_insert_attendance(db_manager):
    """Test inserting an attendance record."""
    db_manager.insert_student("S001", "Mr", "John Doe")
    today = date.today().isoformat()
    db_manager.insert_attendance("S001", today, "Present", "Prof. X", "image1.jpg")
    
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ATTENDANCE WHERE student_no='S001'")
        result = cursor.fetchone()
        
        assert result is not None
        assert result['student_no'] == "S001"
        assert result['lecture_date'] == today
        assert result['status'] == "Present"
        assert result['lecturer_name'] == "Prof. X"

def test_insert_attendance_foreign_key_error(db_manager):
    """Test that foreign key constraint is enforced."""
    today = date.today().isoformat()
    # Should raise error since S999 is not in STUDENTS
    with pytest.raises(sqlite3.Error):
        db_manager.insert_attendance("S999", today, "Present")

def test_insert_attendance_batch(db_manager):
    """Test batch inserting attendance."""
    db_manager.insert_student("S001", "Mr", "John Doe")
    db_manager.insert_student("S002", "Ms", "Jane Doe")
    
    today = date.today().isoformat()
    records = [
        {'student_no': 'S001', 'lecture_date': today, 'status': 'Present', 'lecturer_name': 'Prof. Y', 'image_filename': 'img1.jpg'},
        {'student_no': 'S002', 'lecture_date': today, 'status': 'Absent', 'lecturer_name': 'Prof. Y', 'image_filename': 'img2.jpg'}
    ]
    
    db_manager.insert_attendance_batch(records)
    
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ATTENDANCE")
        result = cursor.fetchone()
        assert result[0] == 2

def test_get_student_attendance(db_manager):
    """Test querying student attendance into a DataFrame."""
    db_manager.insert_student("S001", "Mr", "John Doe")
    today = date.today().isoformat()
    db_manager.insert_attendance("S001", today, "Present")
    
    df = db_manager.get_student_attendance("S001")
    
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert df.iloc[0]['student_no'] == "S001"
    assert df.iloc[0]['status'] == "Present"

def test_get_attendance_by_date(db_manager):
    """Test querying attendance by date into a DataFrame."""
    db_manager.insert_student("S001", "Mr", "John Doe")
    db_manager.insert_student("S002", "Ms", "Jane Doe")
    
    today = date.today().isoformat()
    db_manager.insert_attendance("S001", today, "Present")
    db_manager.insert_attendance("S002", today, "Absent")
    
    df = db_manager.get_attendance_by_date(today)
    
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    # Ensure join worked and 'student_name' column exists
    assert 'student_name' in df.columns
    # Sort or find to check values
    present_row = df[df['student_no'] == "S001"].iloc[0]
    assert present_row['student_name'] == "John Doe"
