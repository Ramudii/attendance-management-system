#!/usr/bin/env python3
"""
Test Runner & Report Generator
Author: Member 9 - Testing & QA
Task: 9.6 / 9.7

Runs the whole pytest suite (with coverage) and writes a timestamped,
human-readable report to tests/test_results/, so there's a paper trail
of test runs to attach to the coursework submission.

Usage:
    python tests/run_tests.py
"""

import subprocess
import sys
import os
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RESULTS_DIR = os.path.join(ROOT, 'tests', 'test_results')


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = os.path.join(RESULTS_DIR, f'test_report_{timestamp}.txt')

    cmd = [
        sys.executable, '-m', 'pytest', 'tests/',
        '--cov=src', '--cov-report=term-missing',
        '-v', '--tb=short',
    ]

    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    output = result.stdout + '\n' + result.stderr

    header = [
        '=' * 70,
        'SAMS TEST EXECUTION REPORT',
        '=' * 70,
        f'Date: {datetime.now()}',
        f'Python: {sys.version.split()[0]}',
        '=' * 70,
        '',
    ]

    with open(report_path, 'w') as f:
        f.write('\n'.join(header))
        f.write(output)

    print(output)
    print(f"\nReport saved to: {report_path}")
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
