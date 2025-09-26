# # Copyright (c) 2024 Red Hat LDAP MCP
# # SPDX-License-Identifier: MIT
# #
# # Red Hat LDAP Model Context Protocol (MCP) Server
# # Provides LDAP integration for corporate directory services

"""Configuration loader for RedHat LDAP MCP."""

import json
import logging
import os
from pathlib import Path
from typing import Any

from .models import OPENLDAP_DEFAULTS, RED_HAT_LDAP_DEFAULTS, Config

logger = logging.getLogger(__name__)


def load_config(config_path: str | None = None, preset: str | None = None) -> Config:
    """
    Load configuration from JSON file with optional presets.

    Args:
        config_path: Path to configuration file. If None, uses REDHAT_LDAP_CONFIG
                    environment variable.
        preset: Optional preset configuration ('redhat', 'openldap')

    Returns:
        Config: Loaded and validated configuration

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
        json.JSONDecodeError: If config file is not valid JSON
    """
    # Determine config file path
    if config_path is None:
        config_path = os.getenv("REDHAT_LDAP_CONFIG")
        if not config_path:
            raise ValueError(
                "No configuration file specified. Either provide config_path or "
                "set REDHAT_LDAP_CONFIG environment variable."
            )

    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    logger.info(f"Loading configuration from: {config_path}")

    try:
        with open(config_file, encoding="utf-8") as f:
            config_data = json.load(f)

        # Apply preset defaults if specified
        if preset:
            config_data = _apply_preset(config_data, preset)

        # Validate and create config object
        config = Config(**config_data)
        logger.info("Configuration loaded successfully")

        # Log configuration summary (without sensitive data)
        _log_config_summary(config)

        return config

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in configuration file: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        raise


def _apply_preset(config_data: dict[str, Any], preset: str) -> dict[str, Any]:
    """
    Apply preset configuration defaults.

    Args:
        config_data: Base configuration data
        preset: Preset name ('redhat', 'openldap')

    Returns:
        Configuration data with preset defaults applied
    """
    preset_data = {}

    if preset.lower() == "redhat":
        preset_data = RED_HAT_LDAP_DEFAULTS.copy()
        logger.info("Applied Red Hat LDAP preset configuration")
    elif preset.lower() == "openldap":
        preset_data = OPENLDAP_DEFAULTS.copy()
        logger.info("Applied OpenLDAP preset configuration")
    else:
        logger.warning(f"Unknown preset: {preset}. Ignoring.")
        return config_data

    # Merge preset defaults with user config (user config takes precedence)
    merged_config = _deep_merge(preset_data, config_data)
    return merged_config


def _deep_merge(default: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Deep merge two dictionaries, with override taking precedence.

    Args:
        default: Default configuration values
        override: Override configuration values

    Returns:
        Merged configuration dictionary
    """
    result = default.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def _log_config_summary(config: Config) -> None:
    """
    Log configuration summary without sensitive information.

    Args:
        config: Configuration object to summarize
    """
    logger.debug(f"LDAP Server: {config.ldap.server}")
    logger.debug(f"Base DN: {config.ldap.base_dn}")
    logger.debug(f"Auth Method: {config.ldap.auth_method}")
    logger.debug(f"SSL Enabled: {config.ldap.use_ssl}")
    logger.debug(f"Person Object Class: {config.schema.person_object_class}")
    logger.debug(f"Person Search Base: {config.schema.person_search_base}")

    if config.schema.group_search_base:
        logger.debug(f"Group Search Base: {config.schema.group_search_base}")

    logger.debug(f"Logging Level: {config.logging.level}")


def validate_config(config: Config) -> None:
    """
    Perform additional validation on configuration.

    Args:
        config: Configuration to validate

    Raises:
        ValueError: If configuration is invalid
    """
    # Validate authentication method requirements
    if config.ldap.auth_method == "simple":
        if not config.ldap.bind_dn or not config.ldap.password:
            raise ValueError("Simple authentication requires both bind_dn and password")
    elif config.ldap.auth_method == "anonymous":
        if config.ldap.bind_dn or config.ldap.password:
            logger.warning(
                "Anonymous authentication specified but bind_dn/password provided. "
                "They will be ignored."
            )

    # Check SSL configuration consistency
    if config.security.enable_tls or config.ldap.use_ssl:
        if not config.ldap.server.startswith("ldaps://") and not config.security.enable_tls:
            logger.warning(
                "SSL/TLS enabled but server URL doesn't use ldaps:// "
                "and TLS is not explicitly enabled"
            )

    # Validate search bases
    base_dn_lower = config.ldap.base_dn.lower()

    if not config.schema.person_search_base.lower().endswith(base_dn_lower):
        logger.warning(
            f"Person search base {config.schema.person_search_base} "
            f"is not under base DN {config.ldap.base_dn}"
        )

    if config.schema.group_search_base and not config.schema.group_search_base.lower().endswith(
        base_dn_lower
    ):
        logger.warning(
            f"Group search base {config.schema.group_search_base} "
            f"is not under base DN {config.ldap.base_dn}"
        )

    # Check for Red Hat specific configuration
    if "rhat" in config.schema.person_object_class.lower():
        if not any("rhat" in attr.lower() for attr in config.schema.redhat_attributes):
            logger.warning(
                "Red Hat person object class detected but no Red Hat attributes configured"
            )

    logger.info("Configuration validation completed")


def create_sample_config(output_path: str, preset: str = "redhat") -> None:
    """
    Create a sample configuration file.

    Args:
        output_path: Path where to create the sample config
        preset: Preset to use ('redhat' or 'openldap')
    """
    if preset.lower() == "redhat":
        sample_config = {
            "ldap": {
                "server": "ldap://ldap.corp.redhat.com",
                "base_dn": "dc=redhat,dc=com",
                "auth_method": "anonymous",
                "timeout": 30,
                "use_ssl": False,
            },
            "schema": RED_HAT_LDAP_DEFAULTS["schema"],
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        }
    else:  # openldap
        sample_config = {
            "ldap": {
                "server": "ldap://ldap.example.com",
                "base_dn": "dc=example,dc=com",
                "auth_method": "simple",
                "bind_dn": "cn=readonly,dc=example,dc=com",
                "password": "readonly_password",
                "timeout": 30,
                "use_ssl": False,
            },
            "schema": OPENLDAP_DEFAULTS["schema"],
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        }

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(sample_config, f, indent=2, ensure_ascii=False)

    logger.info(f"Sample {preset} configuration created at: {output_path}")
