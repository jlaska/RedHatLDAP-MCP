# # Copyright (c) 2024 Red Hat LDAP MCP
# # SPDX-License-Identifier: MIT
# #
# # Red Hat LDAP Model Context Protocol (MCP) Server
# # Provides LDAP integration for corporate directory services

"""Logging configuration and utilities for RedHat LDAP MCP."""

import logging
import sys

from ..config.models import LoggingConfig


def setup_logging(config: LoggingConfig) -> None:
    """
    Setup logging configuration.

    Args:
        config: Logging configuration
    """
    # Create logger
    logger = logging.getLogger("redhat-ldap-mcp")
    logger.setLevel(getattr(logging, config.level))

    # Clear any existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(config.format)

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(getattr(logging, config.level))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if config.file:
        try:
            file_handler = logging.FileHandler(config.file, encoding="utf-8")
            file_handler.setLevel(getattr(logging, config.level))
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.info(f"Logging to file: {config.file}")
        except Exception as e:
            logger.warning(f"Failed to setup file logging: {e}")

    logger.info(f"Logging initialized at level: {config.level}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(f"redhat-ldap-mcp.{name}")


def log_ldap_operation(operation: str, dn: str, success: bool, details: str | None = None) -> None:
    """
    Log LDAP operation for audit purposes.

    Args:
        operation: Operation name (e.g., 'search', 'bind')
        dn: Distinguished name involved
        success: Whether operation succeeded
        details: Additional details or error message
    """
    logger = get_logger("audit")

    status = "SUCCESS" if success else "FAILURE"
    log_msg = f"LDAP {operation.upper()}: {status} - DN: {dn}"

    if details:
        log_msg += f" - Details: {details}"

    if success:
        logger.info(log_msg)
    else:
        logger.warning(log_msg)
