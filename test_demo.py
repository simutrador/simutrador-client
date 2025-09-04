#!/usr/bin/env python3
"""
Test script for SDK demos.

This script validates that the demo files work correctly and can be used
for automated testing in CI/CD pipelines.
"""

import subprocess
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo_test")


def run_command(command: list[str]) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)


def test_offline_demo():
    """Test the offline demo."""
    logger.info("🧪 Testing offline demo...")
    
    exit_code, stdout, stderr = run_command(["uv", "run", "python", "demo_sdk_offline.py"])
    
    if exit_code == 0:
        logger.info("✅ Offline demo passed")
        return True
    else:
        logger.error("❌ Offline demo failed")
        logger.error("Exit code: %d", exit_code)
        logger.error("Stderr: %s", stderr)
        return False


def test_online_demo_without_server():
    """Test the online demo without server (should fail gracefully)."""
    logger.info("🧪 Testing online demo without server...")
    
    exit_code, stdout, stderr = run_command(["uv", "run", "python", "demo_sdk_usage.py"])
    
    # Should fail with exit code 1 but with proper error handling
    if exit_code == 1 and "Check server connectivity" in stderr:
        logger.info("✅ Online demo failed gracefully as expected")
        return True
    else:
        logger.error("❌ Online demo didn't fail as expected")
        logger.error("Exit code: %d", exit_code)
        logger.error("Stderr: %s", stderr)
        return False


def test_import_structure():
    """Test that all imports work correctly."""
    logger.info("🧪 Testing import structure...")
    
    try:
        # Test imports
        from simutrador_client.auth import get_auth_client, AuthenticationError
        from simutrador_client.session import get_session_client, SessionError
        from simutrador_client.settings import get_settings
        
        # Test client initialization
        settings = get_settings()
        auth_client = get_auth_client()
        session_client = get_session_client()
        
        logger.info("✅ All imports and initializations successful")
        return True
        
    except Exception as e:
        logger.error("❌ Import test failed: %s", e)
        return False


def main():
    """Run all demo tests."""
    logger.info("🚀 Running SDK Demo Tests")
    logger.info("=" * 40)
    
    tests = [
        ("Import Structure", test_import_structure),
        ("Offline Demo", test_offline_demo),
        ("Online Demo (No Server)", test_online_demo_without_server),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running: {test_name}")
        if test_func():
            passed += 1
        else:
            logger.error(f"Test failed: {test_name}")
    
    logger.info("\n" + "=" * 40)
    logger.info(f"📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        logger.info("🎉 All tests passed!")
        return 0
    else:
        logger.error("💥 Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
