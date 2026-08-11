import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

from src.logger import setup_logger

logger = setup_logger(__name__)

class DatabaseManager:
    """
    Manages SQLite database connections and operations for the Student Attendance Management System.
    """
    def __init__(self, db_path="data/attendance.db"):
        self.db_path = db_path
        self._ensure_db_directory()
        self.initialize_database()

    def _ensure_db_directory(self):
        """Ensure the directory for the database file exists."""
        db_file = Path(self.db_path)
        if not db_file.parent.exists():
            try:
                db_file.parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created database directory at {db_file.parent}")
            except Exception as e:
                logger.error(f"Failed to create database directory: {e}")
                raise

    @contextmanager
    def get_connection(self):
        """Context manager for SQLite database connections."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            # Enable foreign key support
            conn.execute("PRAGMA foreign_keys = ON")
            # Set row_factory to sqlite3.Row for dict-like access
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def initialize_database(self):
        """Create tables if they do not exist."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Create STUDENTS table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS STUDENTS (
                        student_no TEXT PRIMARY KEY,
                        title TEXT,
                        name TEXT,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                ''')

                # Create ATTENDANCE table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ATTENDANCE (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_no TEXT,
                        lecture_date DATE,
                        status TEXT,
                        lecturer_name TEXT,
                        image_filename TEXT,
                        processed_at TIMESTAMP,
                        FOREIGN KEY (student_no) REFERENCES STUDENTS (student_no)
                    )
                ''')

                conn.commit()
                logger.info("Database initialized successfully.")
        except sqlite3.Error as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def insert_student(self, student_no, title, name):
        """Insert a new student or update existing one."""
        now = datetime.now().isoformat()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO STUDENTS (student_no, title, name, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(student_no) DO UPDATE SET
                        title=excluded.title,
                        name=excluded.name,
                        updated_at=excluded.updated_at
                ''', (student_no, title, name, now, now))
                conn.commit()
                logger.debug(f"Inserted/Updated student: {student_no}")
        except sqlite3.Error as e:
            logger.error(f"Error inserting student {student_no}: {e}")
            raise

    def insert_students_batch(self, students_data):
        """Insert multiple students in a batch. Data should be list of tuples (student_no, title, name)."""
        now = datetime.now().isoformat()
        records = [(s[0], s[1], s[2], now, now) for s in students_data]
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany('''
                    INSERT INTO STUDENTS (student_no, title, name, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(student_no) DO UPDATE SET
                        title=excluded.title,
                        name=excluded.name,
                        updated_at=excluded.updated_at
                ''', records)
                conn.commit()
                logger.debug(f"Batch inserted {len(records)} students.")
        except sqlite3.Error as e:
            logger.error(f"Error in batch insert students: {e}")
            raise

    def insert_attendance(self, student_no, lecture_date, status, lecturer_name=None, image_filename=None):
        """Insert an attendance record."""
        now = datetime.now().isoformat()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO ATTENDANCE (student_no, lecture_date, status, lecturer_name, image_filename, processed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (student_no, lecture_date, status, lecturer_name, image_filename, now))
                conn.commit()
                logger.debug(f"Inserted attendance for student: {student_no} on {lecture_date}")
        except sqlite3.Error as e:
            logger.error(f"Error inserting attendance for student {student_no}: {e}")
            raise

    def insert_attendance_batch(self, attendance_data):
        """Insert multiple attendance records. Data should be list of dicts."""
        now = datetime.now().isoformat()
        records = [(
            a['student_no'], 
            a['lecture_date'], 
            a['status'], 
            a.get('lecturer_name'), 
            a.get('image_filename'), 
            now
        ) for a in attendance_data]

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany('''
                    INSERT INTO ATTENDANCE (student_no, lecture_date, status, lecturer_name, image_filename, processed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', records)
                conn.commit()
                logger.debug(f"Batch inserted {len(records)} attendance records.")
        except sqlite3.Error as e:
            logger.error(f"Error in batch insert attendance: {e}")
            raise

    def get_student_attendance(self, student_no):
        """Retrieve attendance records for a specific student as a Pandas DataFrame."""
        try:
            with self.get_connection() as conn:
                query = "SELECT * FROM ATTENDANCE WHERE student_no = ?"
                df = pd.read_sql_query(query, conn, params=(student_no,))
                return df
        except Exception as e:
            logger.error(f"Error retrieving attendance for {student_no}: {e}")
            return pd.DataFrame()

    def get_attendance_by_date(self, lecture_date):
        """Retrieve all attendance records for a specific date as a Pandas DataFrame."""
        try:
            with self.get_connection() as conn:
                query = '''
                    SELECT a.*, s.name as student_name
                    FROM ATTENDANCE a
                    LEFT JOIN STUDENTS s ON a.student_no = s.student_no
                    WHERE a.lecture_date = ?
                '''
                df = pd.read_sql_query(query, conn, params=(lecture_date,))
                return df
        except Exception as e:
            logger.error(f"Error retrieving attendance for date {lecture_date}: {e}")
            return pd.DataFrame()