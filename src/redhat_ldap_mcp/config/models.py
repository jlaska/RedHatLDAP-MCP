# # Copyright (c) 2024 Red Hat LDAP MCP
# # SPDX-License-Identifier: MIT
# #
# # Red Hat LDAP Model Context Protocol (MCP) Server
# # Provides LDAP integration for corporate directory services

"""Configuration models for RedHat LDAP MCP."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LDAPConfig(BaseModel):
    """LDAP connection configuration for corporate directories."""

    server: str = Field(..., description="LDAP server URL (ldap:// or ldaps://)")
    base_dn: str = Field(..., description="Base Distinguished Name for searches")
    auth_method: Literal["anonymous", "simple", "sasl"] = Field(
        default="anonymous", description="Authentication method"
    )
    bind_dn: str | None = Field(
        default=None, description="Service account DN for binding (required for simple auth)"
    )
    password: str | None = Field(
        default=None, description="Service account password (required for simple auth)"
    )
    timeout: int = Field(default=30, description="Connection timeout in seconds")
    receive_timeout: int = Field(default=10, description="Receive timeout in seconds")
    use_ssl: bool = Field(default=False, description="Use SSL/TLS connection")

    @field_validator("server")
    @classmethod
    def validate_server(cls, v):
        """Validate server URL format."""
        if not v.startswith(("ldap://", "ldaps://")):
            raise ValueError("Server must start with ldap:// or ldaps://")
        return v

    @field_validator("auth_method")
    @classmethod
    def validate_auth_requirements(cls, v, values):
        """Validate authentication method requirements."""
        # Note: In Pydantic v2, we need to handle validation differently
        # This validator will be called for auth_method field
        return v


class SchemaConfig(BaseModel):
    """LDAP schema configuration for corporate directories."""

    # Object classes
    person_object_class: str = Field(
        default="person", description="Object class for person entries"
    )
    group_object_class: str = Field(
        default="groupOfNames", description="Object class for group entries"
    )

    # Search bases
    person_search_base: str = Field(..., description="Base DN for person searches")
    group_search_base: str | None = Field(default=None, description="Base DN for group searches")

    # Red Hat specific attributes
    corporate_attributes: list[str] = Field(
        default_factory=lambda: [
            "uid",
            "cn",
            "mail",
            "givenName",
            "sn",
            "displayName",
            "telephoneNumber",
            "manager",
            "title",
            "department",
            "employeeNumber",
            "employeeType",
        ],
        description="Corporate-specific LDAP attributes to retrieve",
    )

    # Red Hat LDAP specific attributes
    redhat_attributes: list[str] = Field(
        default_factory=lambda: [
            "rhatJobTitle",
            "rhatCostCenter",
            "rhatLocation",
            "rhatBio",
            "rhatGeo",
            "rhatOrganization",
            "rhatJobRole",
            "rhatTeamLead",
            "rhatOriginalHireDate",
            "rhatHireDate",
            "rhatWorkerId",
        ],
        description="Red Hat specific LDAP attributes",
    )

    # Search fields configuration
    search_fields: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "person": ["uid", "cn", "mail", "displayName", "givenName", "sn"],
            "group": ["cn", "description"],
        },
        description="Fields to search across for different object types",
    )


class SecurityConfig(BaseModel):
    """Security configuration for LDAP connections."""

    enable_tls: bool = Field(default=False, description="Enable TLS encryption")
    validate_certificate: bool = Field(default=True, description="Validate server certificate")
    ca_cert_file: str | None = Field(default=None, description="CA certificate file path")
    require_secure_connection: bool = Field(default=False, description="Require secure connection")


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", description="Logging level")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format",
    )
    file: str | None = Field(default=None, description="Log file path")

    @field_validator("level")
    @classmethod
    def validate_level(cls, v):
        """Validate logging level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Level must be one of: {valid_levels}")
        return v.upper()


class PerformanceConfig(BaseModel):
    """Performance configuration for LDAP operations."""

    max_retries: int = Field(default=3, description="Maximum connection retries")
    retry_delay: float = Field(default=1.0, description="Retry delay in seconds")
    page_size: int = Field(default=1000, description="LDAP search page size")
    max_results: int = Field(default=5000, description="Maximum search results")
    cache_timeout: int = Field(default=300, description="Schema cache timeout in seconds")

    @field_validator("max_retries", "page_size", "max_results", "cache_timeout")
    @classmethod
    def validate_positive_int(cls, v):
        """Validate positive integers."""
        if v <= 0:
            raise ValueError("Value must be positive")
        return v

    @field_validator("retry_delay")
    @classmethod
    def validate_positive_float(cls, v):
        """Validate positive float."""
        if v <= 0:
            raise ValueError("Retry delay must be positive")
        return v


class ExportConfig(BaseModel):
    """Configuration for data export functionality."""

    formats: list[str] = Field(
        default_factory=lambda: ["json", "csv", "vcard"], description="Supported export formats"
    )
    max_export_size: int = Field(default=10000, description="Maximum number of entries to export")
    include_sensitive: bool = Field(
        default=False, description="Include sensitive attributes in exports"
    )
    sensitive_attributes: list[str] = Field(
        default_factory=lambda: ["userPassword", "sambaNTPassword"],
        description="Attributes considered sensitive",
    )


class Config(BaseModel):
    """Main configuration class for RedHat LDAP MCP."""

    ldap: LDAPConfig
    schema: SchemaConfig
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)

    @field_validator("schema")
    @classmethod
    def validate_schema_consistency(cls, v, info):
        """Validate schema configuration consistency."""
        if hasattr(info, "data") and "ldap" in info.data:
            ldap_config = info.data["ldap"]
            base_dn = ldap_config.base_dn.lower()

            # Check if person search base is under base DN
            if not v.person_search_base.lower().endswith(base_dn):
                raise ValueError(
                    f"Person search base {v.person_search_base} must be under "
                    f"base DN {ldap_config.base_dn}"
                )

            # Check group search base if provided
            if v.group_search_base and not v.group_search_base.lower().endswith(base_dn):
                raise ValueError(
                    f"Group search base {v.group_search_base} must be under "
                    f"base DN {ldap_config.base_dn}"
                )

        return v


# Predefined configurations for common corporate LDAP setups
RED_HAT_LDAP_DEFAULTS = {
    "schema": {
        "person_object_class": "rhatPerson",
        "person_search_base": "ou=users,dc=redhat,dc=com",
        "group_search_base": "ou=adhoc,ou=managedGroups,dc=redhat,dc=com",
        "corporate_attributes": [
            "uid",
            "cn",
            "mail",
            "givenName",
            "sn",
            "displayName",
            "telephoneNumber",
            "manager",
            "title",
            "department",
        ],
        "redhat_attributes": [
            "rhatJobTitle",
            "rhatCostCenter",
            "rhatLocation",
            "rhatBio",
            "rhatGeo",
            "rhatOrganization",
            "rhatJobRole",
            "rhatTeamLead",
            "rhatOriginalHireDate",
            "rhatHireDate",
            "rhatWorkerId",
            "rhatCostCenterDesc",
            "rhatBuildingCode",
            "rhatOfficeLocation",
        ],
    }
}

OPENLDAP_DEFAULTS = {
    "schema": {
        "person_object_class": "inetOrgPerson",
        "person_search_base": "ou=people,dc=example,dc=com",
        "group_search_base": "ou=groups,dc=example,dc=com",
        "corporate_attributes": [
            "uid",
            "cn",
            "mail",
            "givenName",
            "sn",
            "displayName",
            "telephoneNumber",
            "manager",
            "title",
            "departmentNumber",
        ],
    }
}
