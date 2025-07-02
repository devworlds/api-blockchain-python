#!/usr/bin/env python3
"""
Test runner script for CI/CD environments
Enhanced version with better diagnostics and CI compatibility
"""
import os
import subprocess
import sys
from pathlib import Path


def setup_environment():
    """Setup the environment for testing"""
    # Get the script directory (project root)
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)

    # Set PYTHONPATH to current directory
    os.environ["PYTHONPATH"] = str(script_dir)

    # Also add to sys.path for immediate effect
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

    return script_dir


def check_test_files(project_root):
    """Check if test files exist and are readable"""
    tests_dir = project_root / "tests"

    if not tests_dir.exists():
        print(f"❌ Tests directory not found: {tests_dir}")
        return False, []

    test_files = list(tests_dir.glob("test_*.py"))
    if not test_files:
        print(f"❌ No test files found in: {tests_dir}")
        return False, []

    print(f"✅ Found {len(test_files)} test files:")
    for test_file in sorted(test_files):
        print(f"  - {test_file.name}")

    return True, test_files


def verify_imports(project_root):
    """Verify that we can import the app module"""
    try:
        import app

        print(f"✅ Successfully imported app module from: {app.__file__}")
        return True
    except ImportError as e:
        print(f"❌ Failed to import app module: {e}")
        return False


def run_pytest_with_explicit_files(project_root, test_files):
    """Run pytest with explicit test file paths"""
    print("\n🧪 Running pytest with explicit test files...")

    # Build command with explicit test file paths
    test_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "--cov=app",
        "--cov-report=xml",
        "--cov-report=term-missing",
        "-v",
        "--tb=short",
    ]

    # Add each test file explicitly
    for test_file in test_files:
        test_cmd.append(str(test_file))

    print(f"Test command: {' '.join(test_cmd)}")
    result = subprocess.run(test_cmd)
    return result.returncode == 0


def run_pytest_with_diagnostics(project_root):
    """Run pytest with comprehensive diagnostics"""
    tests_dir = project_root / "tests"

    # First, try to collect tests only
    print("\n🔍 Testing pytest collection...")
    collect_cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(tests_dir),
        "--collect-only",
        "-q",
    ]

    print(f"Collection command: {' '.join(collect_cmd)}")
    collect_result = subprocess.run(collect_cmd, capture_output=True, text=True)

    if collect_result.returncode != 0:
        print(f"❌ Test collection failed:")
        print(f"STDOUT: {collect_result.stdout}")
        print(f"STDERR: {collect_result.stderr}")
        return False

    print(f"✅ Test collection successful:")
    print(collect_result.stdout)

    # Now run the actual tests
    print("\n🧪 Running tests with coverage...")
    test_cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(tests_dir),
        "--cov=app",
        "--cov-report=xml",
        "--cov-report=term-missing",
        "-v",
        "--tb=short",
    ]

    print(f"Test command: {' '.join(test_cmd)}")
    result = subprocess.run(test_cmd)
    return result.returncode == 0


def main():
    """Main test runner function"""
    print("🚀 Starting Enhanced CI Test Runner")
    print("=" * 60)

    # Setup environment
    project_root = setup_environment()

    # Print diagnostic information
    print(f"📁 Working directory: {os.getcwd()}")
    print(f"🐍 Python executable: {sys.executable}")
    print(f"📦 Python version: {sys.version}")
    print(f"🔧 PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")
    print(f"📂 Project root: {project_root}")
    print(f"🔍 sys.path entries:")
    for i, path in enumerate(sys.path[:5]):  # Show first 5 entries
        print(f"  [{i}] {path}")

    # Check if test files exist
    tests_found, test_files = check_test_files(project_root)
    if not tests_found:
        print("❌ Test file check failed")
        sys.exit(1)

    # Check if app directory exists
    app_dir = project_root / "app"
    if not app_dir.exists():
        print(f"❌ App directory not found: {app_dir}")
        sys.exit(1)

    print(f"✅ App directory found: {app_dir}")

    # Verify we can import the app module
    if not verify_imports(project_root):
        print("⚠️ Warning: Cannot import app module, but continuing...")

    # Try multiple approaches
    success = False

    # Approach 1: Standard pytest with tests directory
    print("\n" + "=" * 50)
    print("🔄 Approach 1: Standard pytest with tests directory")
    success = run_pytest_with_diagnostics(project_root)

    if not success:
        # Approach 2: Explicit test file paths
        print("\n" + "=" * 50)
        print("🔄 Approach 2: Explicit test file paths")
        success = run_pytest_with_explicit_files(project_root, test_files)

    if success:
        print("\n✅ All tests passed successfully!")
        sys.exit(0)
    else:
        print("\n❌ All approaches failed")

        # Final diagnostic: List directory contents
        print("\n🔍 Final diagnostics:")
        print(f"Contents of {project_root}:")
        for item in sorted(project_root.iterdir()):
            print(f"  {item.name}{'/' if item.is_dir() else ''}")

        tests_dir = project_root / "tests"
        if tests_dir.exists():
            print(f"\nContents of {tests_dir}:")
            for item in sorted(tests_dir.iterdir()):
                print(f"  {item.name}")

        sys.exit(1)


if __name__ == "__main__":
    main()
