import logging
import os
import shutil
import tempfile
from unittest.mock import Mock, patch

import pytest

from app.shared.monitoring.logging import (
    LoggerMixin,
    get_logger,
    log_blockchain_operation,
    log_database_operation,
    log_function_call,
    log_vault_operation,
    setup_logging,
)


class TestSetupLogging:
    """Test logging setup functionality"""

    def setup_method(self):
        """Setup for each test"""
        # Create temporary directory for test logs
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

    def teardown_method(self):
        """Cleanup after each test"""
        # Clear logging handlers first to release file handles
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            try:
                handler.close()
                root_logger.removeHandler(handler)
            except:
                pass
        root_logger.handlers.clear()

        os.chdir(self.original_cwd)

        # Try to remove temp directory, ignore errors on Windows
        try:
            shutil.rmtree(self.temp_dir)
        except (PermissionError, OSError):
            # On Windows, files might still be locked
            pass

    def test_setup_logging_default_level(self):
        """Test setup logging with default INFO level"""
        setup_logging()

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) == 3  # console, file, error

        # Check if logs directory was created
        assert os.path.exists("logs")

    def test_setup_logging_debug_level(self):
        """Test setup logging with DEBUG level"""
        setup_logging("DEBUG")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_setup_logging_error_level(self):
        """Test setup logging with ERROR level"""
        setup_logging("ERROR")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.ERROR

    def test_setup_logging_creates_log_files(self):
        """Test that setup creates log files"""
        setup_logging()

        # Log something to trigger file creation
        logger = logging.getLogger("test")
        logger.info("Test message")
        logger.error("Test error")

        # Force flush
        for handler in logging.getLogger().handlers:
            if hasattr(handler, "flush"):
                handler.flush()

        assert os.path.exists("logs/app.log")
        assert os.path.exists("logs/error.log")

    def test_setup_logging_clears_existing_handlers(self):
        """Test that setup clears existing handlers"""
        # Add a handler first
        root_logger = logging.getLogger()
        dummy_handler = logging.StreamHandler()
        root_logger.addHandler(dummy_handler)

        setup_logging()

        # Should have exactly 3 handlers (our new ones)
        assert len(root_logger.handlers) == 3

    def test_setup_logging_handles_existing_logs_dir(self):
        """Test that setup handles existing logs directory"""
        # Create logs directory first
        os.makedirs("logs", exist_ok=True)

        # Should not raise exception
        setup_logging()

        # Should still work
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 3


class TestGetLogger:
    """Test logger getter functionality"""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance"""
        logger = get_logger("test_logger")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_logger"

    def test_get_logger_different_names(self):
        """Test that different names return different loggers"""
        logger1 = get_logger("logger1")
        logger2 = get_logger("logger2")

        assert logger1.name != logger2.name
        assert logger1 is not logger2


class TestLoggerMixin:
    """Test LoggerMixin functionality"""

    def test_logger_mixin_creates_logger(self):
        """Test that LoggerMixin creates a logger with class name"""

        class TestClass(LoggerMixin):
            pass

        instance = TestClass()
        logger = instance.logger

        assert isinstance(logger, logging.Logger)
        assert logger.name == "TestClass"

    def test_logger_mixin_caches_logger(self):
        """Test that LoggerMixin caches the logger instance"""

        class TestClass(LoggerMixin):
            pass

        instance = TestClass()
        logger1 = instance.logger
        logger2 = instance.logger

        assert logger1 is logger2

    def test_logger_mixin_different_classes(self):
        """Test that different classes get different loggers"""

        class TestClass1(LoggerMixin):
            pass

        class TestClass2(LoggerMixin):
            pass

        instance1 = TestClass1()
        instance2 = TestClass2()

        assert instance1.logger.name == "TestClass1"
        assert instance2.logger.name == "TestClass2"
        assert instance1.logger is not instance2.logger


class TestLogContextFunctions:
    """Test log context creation functions"""

    def test_log_function_call(self):
        """Test log_function_call creates correct context"""
        result = log_function_call("test_function", param1="value1", param2="value2")

        expected = {
            "function": "test_function",
            "parameters": {"param1": "value1", "param2": "value2"},
            "log_event": "function_call",
        }
        assert result == expected

    def test_log_function_call_no_params(self):
        """Test log_function_call with no parameters"""
        result = log_function_call("test_function")

        expected = {
            "function": "test_function",
            "parameters": {},
            "log_event": "function_call",
        }
        assert result == expected

    def test_log_database_operation(self):
        """Test log_database_operation creates correct context"""
        result = log_database_operation("INSERT", "users", user_id=123, action="create")

        expected = {
            "operation": "INSERT",
            "table": "users",
            "log_event": "database_operation",
            "user_id": 123,
            "action": "create",
        }
        assert result == expected

    def test_log_blockchain_operation(self):
        """Test log_blockchain_operation creates correct context"""
        result = log_blockchain_operation(
            "send_transaction", tx_hash="0x123", gas_used=21000
        )

        expected = {
            "operation": "send_transaction",
            "log_event": "blockchain_operation",
            "tx_hash": "0x123",
            "gas_used": 21000,
        }
        assert result == expected

    def test_log_vault_operation(self):
        """Test log_vault_operation creates correct context"""
        result = log_vault_operation(
            "get_private_key", key_id="wallet_123", success=True
        )

        expected = {
            "operation": "get_private_key",
            "log_event": "vault_operation",
            "key_id": "wallet_123",
            "success": True,
        }
        assert result == expected
