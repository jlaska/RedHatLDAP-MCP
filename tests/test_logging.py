# # Copyright (c) 2024 Red Hat LDAP MCP
# # SPDX-License-Identifier: MIT
# #
# # Red Hat LDAP Model Context Protocol (MCP) Server
# # Provides LDAP integration for corporate directory services

"""Tests for logging functionality."""

import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch

from redhat_ldap_mcp.config.models import LoggingConfig
from redhat_ldap_mcp.core.logging import get_logger, log_ldap_operation, setup_logging


class TestLoggingSetup:
    """Test logging setup functionality."""

    def test_setup_logging_console_only(self, caplog):
        """Test logging setup with console handler only."""
        config = LoggingConfig(level="INFO")

        with caplog.at_level(logging.INFO):
            setup_logging(config)

        # Should have setup message
        assert "Logging initialized at level: INFO" in caplog.text

        # Test that logger is working
        logger = logging.getLogger("redhat-ldap-mcp")
        logger.info("Test message")
        assert "Test message" in caplog.text

    def test_setup_logging_with_file(self):
        """Test logging setup with file handler."""
        with NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            log_file = f.name

        try:
            config = LoggingConfig(level="DEBUG", file=log_file)
            setup_logging(config)

            # Test logging to file
            logger = logging.getLogger("redhat-ldap-mcp")
            logger.debug("Debug message")
            logger.info("Info message")

            # Check file content
            with open(log_file) as f:
                content = f.read()
                assert "Debug message" in content
                assert "Info message" in content
                assert "Logging to file:" in content

        finally:
            Path(log_file).unlink()

    def test_setup_logging_file_error(self, caplog):
        """Test logging setup with file error."""
        # Try to log to an invalid path
        config = LoggingConfig(level="INFO", file="/invalid/path/test.log")

        with caplog.at_level(logging.WARNING):
            setup_logging(config)

        assert "Failed to setup file logging" in caplog.text

    def test_setup_logging_custom_format(self):
        """Test logging setup with custom format."""
        custom_format = "%(levelname)s: %(message)s"
        config = LoggingConfig(level="INFO", format=custom_format)

        with patch("redhat_ldap_mcp.core.logging.logging.Formatter") as mock_formatter:
            setup_logging(config)
            mock_formatter.assert_called_with(custom_format)

    def test_setup_logging_clears_existing_handlers(self):
        """Test that setup_logging clears existing handlers."""
        logger = logging.getLogger("redhat-ldap-mcp")

        # Add a dummy handler
        dummy_handler = logging.StreamHandler()
        logger.addHandler(dummy_handler)

        config = LoggingConfig(level="INFO")
        setup_logging(config)

        # Should have cleared old handlers and added new ones
        assert len(logger.handlers) > 0
        assert dummy_handler not in logger.handlers


class TestGetLogger:
    """Test get_logger functionality."""

    def test_get_logger_basic(self):
        """Test basic logger retrieval."""
        logger = get_logger("test_module")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "redhat-ldap-mcp.test_module"

    def test_get_logger_different_names(self):
        """Test getting loggers with different names."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        assert logger1.name == "redhat-ldap-mcp.module1"
        assert logger2.name == "redhat-ldap-mcp.module2"
        assert logger1 != logger2

    def test_get_logger_same_name_returns_same_logger(self):
        """Test that same name returns same logger instance."""
        logger1 = get_logger("same_module")
        logger2 = get_logger("same_module")

        assert logger1 is logger2


class TestLDAPOperationLogging:
    """Test LDAP operation audit logging."""

    def test_log_ldap_operation_success(self, caplog):
        """Test logging successful LDAP operation."""
        with caplog.at_level(logging.INFO):
            log_ldap_operation(
                operation="search",
                dn="uid=test,ou=people,dc=test,dc=com",
                success=True,
                details="Found 5 entries",
            )

        assert "LDAP SEARCH: SUCCESS" in caplog.text
        assert "uid=test,ou=people,dc=test,dc=com" in caplog.text
        assert "Found 5 entries" in caplog.text

    def test_log_ldap_operation_failure(self, caplog):
        """Test logging failed LDAP operation."""
        with caplog.at_level(logging.WARNING):
            log_ldap_operation(
                operation="bind",
                dn="cn=admin,dc=test,dc=com",
                success=False,
                details="Invalid credentials",
            )

        assert "LDAP BIND: FAILURE" in caplog.text
        assert "cn=admin,dc=test,dc=com" in caplog.text
        assert "Invalid credentials" in caplog.text

    def test_log_ldap_operation_without_details(self, caplog):
        """Test logging LDAP operation without details."""
        with caplog.at_level(logging.INFO):
            log_ldap_operation(operation="connect", dn="", success=True)

        log_text = caplog.text
        assert "LDAP CONNECT: SUCCESS" in log_text
        assert "Details:" not in log_text

    def test_log_ldap_operation_case_insensitive(self, caplog):
        """Test that operation names are converted to uppercase."""
        with caplog.at_level(logging.INFO):
            log_ldap_operation(
                operation="modify", dn="uid=user,ou=people,dc=test,dc=com", success=True
            )

        assert "LDAP MODIFY: SUCCESS" in caplog.text

    def test_log_ldap_operation_audit_logger(self):
        """Test that LDAP operations use audit logger."""
        with patch("redhat_ldap_mcp.core.logging.get_logger") as mock_get_logger:
            mock_logger = logging.getLogger("test-audit")
            mock_get_logger.return_value = mock_logger

            log_ldap_operation("test", "dn", True)

            mock_get_logger.assert_called_once_with("audit")


class TestLoggingLevels:
    """Test different logging levels."""

    def test_debug_level_logging(self, caplog):
        """Test debug level logging."""
        config = LoggingConfig(level="DEBUG")
        setup_logging(config)

        logger = get_logger("test")

        with caplog.at_level(logging.DEBUG):
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")

        assert "Debug message" in caplog.text
        assert "Info message" in caplog.text
        assert "Warning message" in caplog.text
        assert "Error message" in caplog.text

    def test_info_level_logging(self, caplog):
        """Test info level logging."""
        config = LoggingConfig(level="INFO")
        setup_logging(config)

        logger = get_logger("test")

        with caplog.at_level(logging.DEBUG):
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")

        # Debug should not appear at INFO level
        assert "Debug message" not in caplog.text
        assert "Info message" in caplog.text
        assert "Warning message" in caplog.text

    def test_warning_level_logging(self, caplog):
        """Test warning level logging."""
        config = LoggingConfig(level="WARNING")
        setup_logging(config)

        logger = get_logger("test")

        with caplog.at_level(logging.DEBUG):
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")

        # Only warning and above should appear
        assert "Debug message" not in caplog.text
        assert "Info message" not in caplog.text
        assert "Warning message" in caplog.text
        assert "Error message" in caplog.text


class TestLoggingIntegration:
    """Test logging integration scenarios."""

    def test_logging_with_unicode(self, caplog):
        """Test logging with unicode characters."""
        config = LoggingConfig(level="INFO")
        setup_logging(config)

        logger = get_logger("unicode_test")

        with caplog.at_level(logging.INFO):
            logger.info("Testing unicode: 中文 🎉 café")

        assert "Testing unicode: 中文 🎉 café" in caplog.text

    def test_logging_with_long_messages(self, caplog):
        """Test logging with very long messages."""
        config = LoggingConfig(level="INFO")
        setup_logging(config)

        logger = get_logger("long_test")
        long_message = "x" * 1000

        with caplog.at_level(logging.INFO):
            logger.info(f"Long message: {long_message}")

        assert "Long message:" in caplog.text
        assert "x" * 100 in caplog.text  # Should contain part of the long message

    def test_concurrent_logging_setup(self):
        """Test that multiple setup calls don't cause issues."""
        config1 = LoggingConfig(level="INFO")
        config2 = LoggingConfig(level="DEBUG")

        # Multiple setups should not cause errors
        setup_logging(config1)
        setup_logging(config2)

        logger = get_logger("concurrent_test")
        # Should work without errors
        logger.info("Test message")
