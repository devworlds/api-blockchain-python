import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure simple, reliable logging system
    """
    # Create logs directory
    os.makedirs("logs", exist_ok=True)

    # Clear existing handlers to avoid conflicts with uvicorn
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Set level
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler for all logs
    file_handler = logging.FileHandler("logs/app.log", mode="a")
    file_handler.setLevel(getattr(logging, log_level.upper()))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Error file handler
    error_handler = logging.FileHandler("logs/error.log", mode="a")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    # Force immediate write
    for handler in root_logger.handlers:
        if hasattr(handler, "flush"):
            handler.flush()


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance
    """
    return logging.getLogger(name)


class LoggerMixin:
    """
    Mixin to add structured logging to classes
    """

    @property
    def logger(self):
        if not hasattr(self, "_logger"):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger


def log_function_call(func_name: str, **kwargs) -> Dict[str, Any]:
    """
    Create a log context for function calls
    """
    return {"function": func_name, "parameters": kwargs, "log_event": "function_call"}


def log_database_operation(operation: str, table: str, **kwargs) -> Dict[str, Any]:
    """
    Create a log context for database operations
    """
    return {
        "operation": operation,
        "table": table,
        "log_event": "database_operation",
        **kwargs,
    }


def log_blockchain_operation(operation: str, **kwargs) -> Dict[str, Any]:
    """
    Create a log context for blockchain operations
    """
    return {"operation": operation, "log_event": "blockchain_operation", **kwargs}


def log_vault_operation(operation: str, **kwargs) -> Dict[str, Any]:
    """
    Create a log context for vault operations
    """
    return {"operation": operation, "log_event": "vault_operation", **kwargs}
