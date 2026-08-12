#!/usr/bin/env python3
"""SAMS - Attendance visualisation for a single student.

Implements the second program required by the CS402.3 brief:

    $ python infovis.py 001

Reads the attendance recorded by ``sams.py`` from the SQLite database and
writes a summary chart to ``reports/charts/``.

Author: Member 7 - Data Visualization (Pabasara Ashen)
"""

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database.database_manager import DatabaseManager
from src.visualization.chart_generator import ChartGenerator

DEFAULT_DB = 'data/attendance.db'


def fetch_student(db, student_no):
    """Look up one student's name and title.

    Args:
        db: An open :class:`DatabaseManager`.
        student_no: Student index to look up.

    Returns:
        dict | None: Keys 'student_no', 'title', 'name', or None if unknown.
    """
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT student_no, title, name FROM STUDENTS WHERE student_no = ?",
            (student_no,),
        ).fetchone()
    return dict(row) if row else None


def build_session_table(records):
    """Reduce raw attendance rows to one row per session, in a stable order.

    Sessions are keyed on ``image_filename`` rather than ``lecture_date``
    because every sheet is currently written with the same date (the single
    ``<date>`` from info.xml), so dates do not yet distinguish sessions. The
    source image does. Once the date is taken per sheet this grouping still
    holds, and the labels simply become more informative.

    Args:
        records: DataFrame from ``DatabaseManager.get_student_attendance``.

    Returns:
        DataFrame with 'session', 'status' and 'lecture_date' columns.
    """
    if records.empty:
        return pd.DataFrame(columns=['session', 'status', 'lecture_date'])

    table = records.copy()
    table['session'] = (
        table['image_filename']
        .fillna('unknown')
        .map(lambda path: os.path.splitext(os.path.basename(str(path)))[0])
    )

    # Keep the most recently processed row per session, so re-running a sheet
    # corrects the picture instead of double-counting it.
    table = table.sort_values('processed_at').drop_duplicates(
        subset='session', keep='last')

    return table.sort_values('session')[['session', 'status', 'lecture_date']]


def print_summary(student, sessions):
    """Print the text summary that accompanies the chart."""
    name = student['name'] if student else 'Unknown student'
    student_no = student['student_no'] if student else '?'

    print()
    print('=' * 60)
    print('ATTENDANCE SUMMARY')
    print('=' * 60)
    print(f"Student Number : {student_no}")
    print(f"Name           : {name}")
    print('-' * 60)

    for _, row in sessions.iterrows():
        mark = 'Present' if str(row['status']).lower() == 'present' else 'Absent'
        print(f"  {row['session']:<20} {row['lecture_date']:<12} {mark}")

    total = len(sessions)
    present = int((sessions['status'].str.lower() == 'present').sum())
    rate = present / total * 100 if total else 0.0

    print('-' * 60)
    print(f"Sessions attended : {present}/{total}  ({rate:.1f}%)")
    print('=' * 60)

    # Surface the known data defect rather than quietly drawing a wrong chart.
    if total > 1 and sessions['lecture_date'].nunique() == 1:
        print()
        print(f"NOTE: all {total} sessions carry the same date "
              f"({sessions['lecture_date'].iloc[0]}), because sams.py takes the "
              "date from info.xml rather than from each sheet. Sessions are "
              "therefore labelled by source image. A true date axis needs that "
              "fixed first.")


def main():
    parser = argparse.ArgumentParser(
        description='Show the attendance summary for one student.')
    parser.add_argument('student_no',
                        help='Student index, e.g. 10000409')
    parser.add_argument('--db', default=DEFAULT_DB,
                        help=f'Path to the attendance database '
                             f'(default: {DEFAULT_DB})')
    parser.add_argument('--output-dir', default='reports/charts',
                        help='Directory for the generated chart '
                             '(default: reports/charts)')
    parser.add_argument('--no-chart', action='store_true',
                        help='Print the text summary only')
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"Database not found: {args.db}")
        print("Run sams.py on at least one signing sheet first, for example:")
        print("  python sams.py data/sample_images/1.jpeg data/info.xml")
        sys.exit(1)

    db = DatabaseManager(db_path=args.db)

    student = fetch_student(db, args.student_no)
    records = db.get_student_attendance(args.student_no)
    sessions = build_session_table(records)

    if sessions.empty:
        known = student['name'] if student else None
        if known:
            print(f"No attendance recorded yet for {args.student_no} ({known}).")
        else:
            print(f"Student {args.student_no} is not in the database.")
            print("Check the index, or run sams.py to populate the records.")
        sys.exit(1)

    print_summary(student, sessions)

    if not args.no_chart:
        ChartGenerator(output_dir=args.output_dir).generate_student_summary(
            sessions,
            student_no=args.student_no,
            student_name=student['name'] if student else None,
        )


if __name__ == '__main__':
    main()
