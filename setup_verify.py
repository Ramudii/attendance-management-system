#!/usr/bin/env python3

import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import os
import importlib
import subprocess
from datetime import datetime

def check_python_version():
    """Check Python version"""
    version = sys.version_info
    print(f"Python Version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ required!")
        return False
    
    print("✅ Python version OK")
    return True

def check_directories():
    """Check if all required directories exist"""
    required_dirs = [
        'src',
        'src/image_processing',
        'src/ocr',
        'src/detection',
        'src/database',
        'src/attendance',
        'src/visualization',
        'tests',
        'data',
        'data/database',
        'data/sample_images',
        'reports',
        'reports/progress_images',
        'logs'
    ]
    
    all_exist = True
    for directory in required_dirs:
        if os.path.exists(directory):
            print(f"✅ {directory}/")
        else:
            print(f"❌ {directory}/ (Missing)")
            all_exist = False
    
    return all_exist

def check_files():
    """Check if all required files exist"""
    required_files = [
        'sams.py',
        'requirements.txt',
        '.gitignore',
        'README.md',
        'src/logger.py',
        'src/__init__.py'
    ]
    
    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} (Missing)")
            all_exist = False
    
    return all_exist

def check_git():
    """Check git repository status"""
    try:
        result = subprocess.run(['git', 'status'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Git repository OK")
            return True
    except:
        print("❌ Git repository not found")
        return False

def main():
    """Run all checks"""
    print("="*60)
    print("SAMS - SETUP VERIFICATION")
    print(f"Date: {datetime.now()}")
    print("="*60)
    
    checks = [
        ("Python Version", check_python_version()),
        ("Directories", check_directories()),
        ("Files", check_files()),
        ("Git Repository", check_git())
    ]
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    all_passed = True
    for name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ All checks passed! System is ready.")
        print("\nNext Steps:")
        print("1. Create virtual environment: python -m venv venv")
        print("2. Activate: source venv/bin/activate (or venv\\Scripts\\activate on Windows)")
        print("3. Install: pip install -r requirements.txt")
        print("4. Start coding!")
    else:
        print("\n❌ Some checks failed. Please fix the issues above.")
    
    return all_passed

if __name__ == "__main__":
    sys.exit(0 if main() else 1)