#!/usr/bin/env python3
"""
Script de debug para identificar problemas com pytest no CI
"""
import os
import subprocess
import sys
from pathlib import Path


def debug_pytest_discovery():
    print("🔍 DEBUG: Pytest Test Discovery")
    print("=" * 50)

    # 1. Informações do ambiente
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")

    # 2. Verificar se pytest está instalado
    try:
        import pytest

        print(f"pytest version: {pytest.__version__}")
    except ImportError:
        print("❌ pytest not installed!")
        return

    # 3. Verificar pytest-asyncio
    try:
        import pytest_asyncio

        print(f"pytest-asyncio version: {pytest_asyncio.__version__}")
    except ImportError:
        print("❌ pytest-asyncio not installed!")

    # 4. Verificar estrutura de diretórios
    print("\n📁 Directory structure:")
    tests_dir = Path("tests")
    if tests_dir.exists():
        test_files = list(tests_dir.glob("*.py"))
        print(f"  tests/ directory exists with {len(test_files)} Python files")
        for f in test_files[:5]:  # Show first 5
            print(f"    - {f.name}")
        if len(test_files) > 5:
            print(f"    ... and {len(test_files) - 5} more files")
    else:
        print("  ❌ tests/ directory not found!")
        return

    # 5. Verificar pytest.ini
    print("\n⚙️ pytest.ini:")
    pytest_ini = Path("pytest.ini")
    if pytest_ini.exists():
        with open(pytest_ini, "r") as f:
            content = f.read()
            print(content)
    else:
        print("  ❌ pytest.ini not found!")

    # 6. Testar imports básicos
    print("\n🧪 Testing basic imports:")
    sys.path.insert(0, ".")

    # Test app imports
    try:
        import app

        print("  ✅ app module imports OK")
    except Exception as e:
        print(f"  ❌ app module import failed: {e}")

    # Test specific test file import
    try:
        from tests import test_validators

        print("  ✅ test_validators imports OK")
    except Exception as e:
        print(f"  ❌ test_validators import failed: {e}")

    # 7. Executar pytest com debug
    print("\n🔧 Running pytest with debug flags:")

    debug_commands = [
        "python -m pytest --version",
        "python -m pytest --collect-only --quiet --tb=no tests/",
        "python -m pytest --collect-only --quiet --tb=short tests/test_validators.py",
        "python -c 'import pytest; print(pytest.__file__)'",
    ]

    for cmd in debug_commands:
        print(f"\n  Running: {cmd}")
        try:
            result = subprocess.run(
                cmd.split(), capture_output=True, text=True, timeout=30
            )
            print(f"    Exit code: {result.returncode}")
            if result.stdout:
                print(f"    STDOUT: {result.stdout.strip()}")
            if result.stderr:
                print(f"    STDERR: {result.stderr.strip()}")
        except Exception as e:
            print(f"    ❌ Error: {e}")

    # 8. Check for __pycache__ issues
    print("\n🗂️ Checking for __pycache__ issues:")
    pycache_dirs = list(Path(".").rglob("__pycache__"))
    if pycache_dirs:
        print(f"  Found {len(pycache_dirs)} __pycache__ directories")
        for d in pycache_dirs[:3]:
            print(f"    - {d}")
    else:
        print("  No __pycache__ directories found")


if __name__ == "__main__":
    debug_pytest_discovery()
