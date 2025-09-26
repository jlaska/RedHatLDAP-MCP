# # Copyright (c) 2024 Red Hat LDAP MCP
# # SPDX-License-Identifier: MIT
# #
# # Red Hat LDAP Model Context Protocol (MCP) Server
# # Provides LDAP integration for corporate directory services

"""Tests for configuration management."""

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch

import pytest

from redhat_ldap_mcp.config.loader import (
    _apply_preset,
    _deep_merge,
    create_sample_config,
    load_config,
    validate_config,
)
from redhat_ldap_mcp.config.models import (
    OPENLDAP_DEFAULTS,
    RED_HAT_LDAP_DEFAULTS,
    Config,
    LDAPConfig,
    LoggingConfig,
    PerformanceConfig,
    SchemaConfig,
)


class TestConfigModels:
    """Test configuration model validation."""

    def test_ldap_config_valid(self):
        """Test valid LDAP configuration."""
        config = LDAPConfig(
            server="ldap://test.example.com", base_dn="dc=test,dc=com", auth_method="anonymous"
        )
        assert config.server == "ldap://test.example.com"
        assert config.auth_method == "anonymous"
        assert config.timeout == 30  # default

    def test_ldap_config_invalid_server(self):
        """Test invalid server URL."""
        with pytest.raises(ValueError, match="Server must start with ldap://"):
            LDAPConfig(server="http://invalid.com", base_dn="dc=test,dc=com")

    def test_schema_config_defaults(self):
        """Test schema configuration defaults."""
        config = SchemaConfig(person_search_base="ou=people,dc=test,dc=com")

        assert config.person_object_class == "person"
        assert config.group_object_class == "groupOfNames"
        assert "uid" in config.corporate_attributes
        assert "cn" in config.corporate_attributes

    def test_redhat_schema_attributes(self):
        """Test Red Hat specific attributes."""
        config = SchemaConfig(person_search_base="ou=users,dc=redhat,dc=com")

        assert "rhatJobTitle" in config.redhat_attributes
        assert "rhatCostCenter" in config.redhat_attributes
        assert "rhatLocation" in config.redhat_attributes

    def test_logging_config_validation(self):
        """Test logging level validation."""
        config = LoggingConfig(level="info")
        assert config.level == "INFO"  # Should be normalized to uppercase

        with pytest.raises(ValueError, match="Level must be one of"):
            LoggingConfig(level="invalid")

    def test_performance_config_validation(self):
        """Test performance configuration validation."""
        config = PerformanceConfig(max_retries=5, page_size=500)
        assert config.max_retries == 5
        assert config.page_size == 500

        with pytest.raises(ValueError, match="Value must be positive"):
            PerformanceConfig(max_retries=0)

    def test_full_config_validation(self):
        """Test complete configuration validation."""
        config_data = {
            "ldap": {
                "server": "ldap://test.com",
                "base_dn": "dc=test,dc=com",
                "auth_method": "anonymous",
            },
            "schema": {"person_search_base": "ou=people,dc=test,dc=com"},
        }

        config = Config(**config_data)
        assert config.ldap.server == "ldap://test.com"
        assert config.schema.person_search_base == "ou=people,dc=test,dc=com"


class TestConfigLoader:
    """Test configuration loading functionality."""

    def test_load_config_from_file(self):
        """Test loading configuration from JSON file."""
        config_data = {
            "ldap": {
                "server": "ldap://test.example.com",
                "base_dn": "dc=test,dc=com",
                "auth_method": "simple",
                "bind_dn": "cn=admin,dc=test,dc=com",
                "password": "secret",
            },
            "schema": {"person_search_base": "ou=people,dc=test,dc=com"},
        }

        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            config = load_config(config_file)
            assert config.ldap.server == "ldap://test.example.com"
            assert config.ldap.auth_method == "simple"
            assert config.schema.person_search_base == "ou=people,dc=test,dc=com"
        finally:
            Path(config_file).unlink()

    def test_load_config_file_not_found(self):
        """Test error handling for missing config file."""
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.json")

    def test_load_config_invalid_json(self):
        """Test error handling for invalid JSON."""
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            config_file = f.name

        try:
            with pytest.raises(json.JSONDecodeError):
                load_config(config_file)
        finally:
            Path(config_file).unlink()

    @patch.dict("os.environ", {"REDHAT_LDAP_CONFIG": "test_config.json"})
    def test_load_config_from_environment(self):
        """Test loading config from environment variable."""
        config_data = {
            "ldap": {
                "server": "ldap://env.test.com",
                "base_dn": "dc=env,dc=com",
                "auth_method": "anonymous",
            },
            "schema": {"person_search_base": "ou=people,dc=env,dc=com"},
        }

        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            with patch.dict("os.environ", {"REDHAT_LDAP_CONFIG": config_file}):
                config = load_config()
                assert config.ldap.server == "ldap://env.test.com"
        finally:
            Path(config_file).unlink()

    def test_apply_redhat_preset(self):
        """Test applying Red Hat LDAP preset."""
        base_config = {
            "ldap": {"server": "ldap://custom.redhat.com", "base_dn": "dc=custom,dc=com"}
        }

        result = _apply_preset(base_config, "redhat")

        # Should have Red Hat schema defaults
        assert result["schema"]["person_object_class"] == "rhatPerson"
        assert "rhatJobTitle" in result["schema"]["redhat_attributes"]

        # Custom config should override defaults
        assert result["ldap"]["server"] == "ldap://custom.redhat.com"

    def test_apply_openldap_preset(self):
        """Test applying OpenLDAP preset."""
        base_config = {"ldap": {"server": "ldap://my.openldap.com", "base_dn": "dc=my,dc=com"}}

        result = _apply_preset(base_config, "openldap")

        # Should have OpenLDAP schema defaults
        assert result["schema"]["person_object_class"] == "inetOrgPerson"
        assert result["ldap"]["server"] == "ldap://my.openldap.com"

    def test_deep_merge(self):
        """Test deep merging of configuration dictionaries."""
        default = {
            "level1": {"level2": {"key1": "default1", "key2": "default2"}, "other": "default_other"}
        }

        override = {"level1": {"level2": {"key1": "override1"}, "new_key": "new_value"}}

        result = _deep_merge(default, override)

        assert result["level1"]["level2"]["key1"] == "override1"  # overridden
        assert result["level1"]["level2"]["key2"] == "default2"  # kept from default
        assert result["level1"]["other"] == "default_other"  # kept from default
        assert result["level1"]["new_key"] == "new_value"  # added from override


class TestConfigValidation:
    """Test configuration validation logic."""

    def test_validate_simple_auth_requirements(self):
        """Test validation of simple authentication requirements."""
        # Valid simple auth config
        config = Config(
            ldap=LDAPConfig(
                server="ldap://test.com",
                base_dn="dc=test,dc=com",
                auth_method="simple",
                bind_dn="cn=admin,dc=test,dc=com",
                password="secret",
            ),
            schema=SchemaConfig(person_search_base="ou=people,dc=test,dc=com"),
        )

        # Should not raise exception
        validate_config(config)

    def test_validate_simple_auth_missing_credentials(self):
        """Test validation failure for simple auth without credentials."""
        config = Config(
            ldap=LDAPConfig(
                server="ldap://test.com",
                base_dn="dc=test,dc=com",
                auth_method="simple",
                # Missing bind_dn and password
            ),
            schema=SchemaConfig(person_search_base="ou=people,dc=test,dc=com"),
        )

        with pytest.raises(ValueError, match="Simple authentication requires"):
            validate_config(config)

    def test_validate_anonymous_auth_with_credentials_warning(self, caplog):
        """Test warning when anonymous auth has unnecessary credentials."""
        config = Config(
            ldap=LDAPConfig(
                server="ldap://test.com",
                base_dn="dc=test,dc=com",
                auth_method="anonymous",
                bind_dn="cn=admin,dc=test,dc=com",  # Should trigger warning
                password="secret",
            ),
            schema=SchemaConfig(person_search_base="ou=people,dc=test,dc=com"),
        )

        validate_config(config)
        assert "Anonymous authentication specified but bind_dn/password provided" in caplog.text


class TestSampleConfigGeneration:
    """Test sample configuration file generation."""

    def test_create_redhat_sample_config(self):
        """Test creating Red Hat sample configuration."""
        with NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        try:
            create_sample_config(output_path, preset="redhat")

            # Verify file was created and has correct content
            with open(output_path) as f:
                config_data = json.load(f)

            assert config_data["ldap"]["server"] == "ldap://ldap.corp.redhat.com"
            assert config_data["schema"]["person_object_class"] == "rhatPerson"
            assert "rhatJobTitle" in config_data["schema"]["redhat_attributes"]

        finally:
            Path(output_path).unlink()

    def test_create_openldap_sample_config(self):
        """Test creating OpenLDAP sample configuration."""
        with NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        try:
            create_sample_config(output_path, preset="openldap")

            # Verify file was created and has correct content
            with open(output_path) as f:
                config_data = json.load(f)

            assert config_data["ldap"]["auth_method"] == "simple"
            assert config_data["schema"]["person_object_class"] == "inetOrgPerson"
            assert config_data["ldap"]["bind_dn"] == "cn=readonly,dc=example,dc=com"

        finally:
            Path(output_path).unlink()


class TestPresetDefaults:
    """Test predefined configuration presets."""

    def test_redhat_defaults_structure(self):
        """Test Red Hat defaults have expected structure."""
        assert "schema" in RED_HAT_LDAP_DEFAULTS
        schema = RED_HAT_LDAP_DEFAULTS["schema"]

        assert schema["person_object_class"] == "rhatPerson"
        assert schema["person_search_base"] == "ou=users,dc=redhat,dc=com"
        assert schema["group_search_base"] == "ou=adhoc,ou=managedGroups,dc=redhat,dc=com"

        # Check Red Hat specific attributes
        assert "rhatJobTitle" in schema["redhat_attributes"]
        assert "rhatCostCenter" in schema["redhat_attributes"]
        assert "rhatWorkerId" in schema["redhat_attributes"]

    def test_openldap_defaults_structure(self):
        """Test OpenLDAP defaults have expected structure."""
        assert "schema" in OPENLDAP_DEFAULTS
        schema = OPENLDAP_DEFAULTS["schema"]

        assert schema["person_object_class"] == "inetOrgPerson"
        assert schema["person_search_base"] == "ou=people,dc=example,dc=com"
        assert schema["group_search_base"] == "ou=groups,dc=example,dc=com"

        # Should have standard corporate attributes but no Red Hat specific ones
        assert "uid" in schema["corporate_attributes"]
        assert "cn" in schema["corporate_attributes"]
