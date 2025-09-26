# # Copyright (c) 2024 Red Hat LDAP MCP
# # SPDX-License-Identifier: MIT
# #
# # Red Hat LDAP Model Context Protocol (MCP) Server
# # Provides LDAP integration for corporate directory services

"""Enhanced LDAP connector for corporate LDAP directories."""

import logging
import ssl
import time
from threading import Lock
from typing import Any

import ldap3
from ldap3 import ALL, ALL_ATTRIBUTES, SUBTREE, Connection, Server
from ldap3.core.exceptions import LDAPBindError, LDAPException, LDAPSocketOpenError

from ..config.models import LDAPConfig, PerformanceConfig, SecurityConfig

logger = logging.getLogger(__name__)


class LDAPConnector:
    """
    Enhanced LDAP connector for corporate directories.

    Provides connection management with support for:
    - Anonymous bind (for read-only corporate directories)
    - Simple bind (username/password)
    - SASL bind (future implementation)
    - Automatic reconnection and retry logic
    - Corporate LDAP optimizations
    """

    def __init__(
        self,
        ldap_config: LDAPConfig,
        security_config: SecurityConfig,
        performance_config: PerformanceConfig,
    ):
        """
        Initialize LDAP connector.

        Args:
            ldap_config: LDAP connection configuration
            security_config: Security configuration
            performance_config: Performance configuration
        """
        self.ldap_config = ldap_config
        self.security_config = security_config
        self.performance_config = performance_config

        self._connection: Connection | None = None
        self._server: Server | None = None
        self._lock = Lock()

        self._setup_server()

    def _setup_server(self) -> None:
        """Setup LDAP server configuration."""
        try:
            # Setup TLS configuration
            tls_config = None
            if self.security_config.enable_tls or self.ldap_config.use_ssl:
                tls_config = ldap3.Tls(
                    validate=(
                        ssl.CERT_REQUIRED
                        if self.security_config.validate_certificate
                        else ssl.CERT_NONE
                    ),
                    ca_certs_file=self.security_config.ca_cert_file,
                )

            # Create server
            self._server = Server(
                self.ldap_config.server,
                get_info=ALL,
                tls=tls_config,
                connect_timeout=self.ldap_config.timeout,
            )

            logger.info(f"Configured LDAP server: {self.ldap_config.server}")

        except Exception as e:
            logger.error(f"Error setting up LDAP server: {e}")
            raise

    def connect(self) -> Connection:
        """
        Establish LDAP connection with retry logic.

        Returns:
            Connection: Active LDAP connection

        Raises:
            LDAPException: If connection fails after all retries
        """
        with self._lock:
            if self._connection and self._connection.bound:
                return self._connection

            last_error = None

            for attempt in range(self.performance_config.max_retries):
                try:
                    logger.debug(f"Attempting LDAP connection (attempt {attempt + 1})")

                    # Create connection based on auth method
                    connection = self._create_connection()

                    # Test the connection
                    if self._test_connection(connection):
                        self._connection = connection
                        logger.info(
                            f"Successfully connected to LDAP server using "
                            f"{self.ldap_config.auth_method} auth"
                        )
                        return connection
                    else:
                        logger.warning(f"Connection test failed on attempt {attempt + 1}")

                except (LDAPSocketOpenError, LDAPBindError) as e:
                    logger.warning(f"Connection failed on attempt {attempt + 1}: {e}")
                    last_error = e

                except Exception as e:
                    logger.error(f"Unexpected error during connection attempt {attempt + 1}: {e}")
                    last_error = e

                # Retry delay (except for last attempt)
                if attempt < self.performance_config.max_retries - 1:
                    logger.debug(f"Retrying in {self.performance_config.retry_delay} seconds")
                    time.sleep(self.performance_config.retry_delay)

            # All attempts failed
            error_msg = (
                f"Failed to connect to LDAP server after "
                f"{self.performance_config.max_retries} attempts"
            )
            if last_error:
                error_msg += f". Last error: {last_error}"

            logger.error(error_msg)
            raise LDAPException(error_msg)

    def _create_connection(self) -> Connection:
        """
        Create LDAP connection based on authentication method.

        Returns:
            Connection: LDAP connection object
        """
        if self.ldap_config.auth_method == "anonymous":
            return self._create_anonymous_connection()
        elif self.ldap_config.auth_method == "simple":
            return self._create_simple_connection()
        elif self.ldap_config.auth_method == "sasl":
            return self._create_sasl_connection()
        else:
            raise ValueError(f"Unsupported authentication method: {self.ldap_config.auth_method}")

    def _create_anonymous_connection(self) -> Connection:
        """Create anonymous LDAP connection."""
        logger.debug("Creating anonymous LDAP connection")

        connection = Connection(
            self._server,
            authentication=ldap3.ANONYMOUS,
            receive_timeout=self.ldap_config.receive_timeout,
            check_names=True,
            raise_exceptions=True,
        )

        return connection

    def _create_simple_connection(self) -> Connection:
        """Create simple bind LDAP connection."""
        logger.debug("Creating simple bind LDAP connection")

        if not self.ldap_config.bind_dn or not self.ldap_config.password:
            raise ValueError("Simple authentication requires bind_dn and password")

        connection = Connection(
            self._server,
            user=self.ldap_config.bind_dn,
            password=self.ldap_config.password,
            authentication=ldap3.SIMPLE,
            receive_timeout=self.ldap_config.receive_timeout,
            check_names=True,
            raise_exceptions=True,
        )

        return connection

    def _create_sasl_connection(self) -> Connection:
        """Create SASL LDAP connection (placeholder for future implementation)."""
        raise NotImplementedError("SASL authentication is not yet implemented")

    def _test_connection(self, connection: Connection) -> bool:
        """
        Test LDAP connection.

        Args:
            connection: Connection to test

        Returns:
            True if connection is working
        """
        try:
            # Bind the connection
            if not connection.bind():
                logger.debug(f"Bind failed: {connection.result}")
                return False

            # Test with different search strategies for corporate LDAP compatibility
            test_strategies = [
                # Strategy 1: Root DSE search (standard but may not work with corporate LDAP)
                {
                    "search_base": self.ldap_config.base_dn,
                    "search_filter": "(objectClass=*)",
                    "search_scope": ldap3.BASE,
                    "attributes": ["namingContexts"],
                    "name": "Root DSE",
                },
                # Strategy 2: Simple base DN search
                {
                    "search_base": self.ldap_config.base_dn,
                    "search_filter": "(objectClass=*)",
                    "search_scope": ldap3.SUBTREE,
                    "attributes": ["objectClass"],
                    "name": "Base DN subtree",
                },
                # Strategy 3: Search for any person object (most likely to work)
                {
                    "search_base": self.ldap_config.base_dn,
                    "search_filter": "(objectClass=person)",
                    "search_scope": ldap3.SUBTREE,
                    "attributes": ["uid"],
                    "name": "Person search",
                },
            ]

            for strategy in test_strategies:
                try:
                    success = connection.search(
                        search_base=strategy["search_base"],
                        search_filter=strategy["search_filter"],
                        search_scope=strategy["search_scope"],
                        attributes=strategy["attributes"],
                        size_limit=1,
                    )

                    if success and connection.entries:
                        logger.debug(
                            f"Connection test successful using {strategy['name']} strategy"
                        )
                        return True
                    elif success:
                        logger.debug(f"{strategy['name']} search succeeded but returned no entries")
                    else:
                        logger.debug(f"{strategy['name']} search failed: {connection.result}")

                except Exception as e:
                    logger.debug(f"{strategy['name']} strategy failed: {e}")
                    continue

            # If all strategies failed, the connection is not working
            logger.debug("All connection test strategies failed")
            return False

        except Exception as e:
            logger.debug(f"Connection test failed: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from LDAP server."""
        with self._lock:
            if self._connection:
                try:
                    self._connection.unbind()
                    logger.info("Disconnected from LDAP server")
                except Exception as e:
                    logger.warning(f"Error during disconnect: {e}")
                finally:
                    self._connection = None

    def search(
        self,
        search_base: str,
        search_filter: str,
        attributes: list[str] | str = ALL_ATTRIBUTES,
        search_scope: str = SUBTREE,
        size_limit: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Perform LDAP search operation with paging support.

        Args:
            search_base: Base DN for search
            search_filter: LDAP filter string
            attributes: Attributes to retrieve
            search_scope: Search scope (SUBTREE, ONELEVEL, BASE)
            size_limit: Maximum number of results (0 = no limit)

        Returns:
            List of LDAP entries as dictionaries

        Raises:
            LDAPException: If search fails
        """
        connection = self.connect()

        try:
            logger.debug(f"Searching: base={search_base}, filter={search_filter}")

            # Apply size limits
            effective_limit = size_limit if size_limit > 0 else self.performance_config.max_results
            paged_size = min(self.performance_config.page_size, effective_limit)

            entries = []
            cookie = None

            while True:
                success = connection.search(
                    search_base=search_base,
                    search_filter=search_filter,
                    search_scope=search_scope,
                    attributes=attributes,
                    paged_size=paged_size,
                    paged_cookie=cookie,
                )

                if not success:
                    logger.error(f"Search failed: {connection.result}")
                    raise LDAPException(f"Search failed: {connection.result}")

                # Process entries
                for entry in connection.entries:
                    entry_dict = self._process_entry(entry)
                    entries.append(entry_dict)

                    # Check size limit
                    if len(entries) >= effective_limit:
                        logger.debug(f"Size limit reached: {effective_limit}")
                        return entries[:effective_limit]

                # Check for more pages
                controls = connection.result.get("controls", {})
                paged_control = controls.get("1.2.840.113556.1.4.319", {})
                cookie = paged_control.get("value", {}).get("cookie")

                if not cookie:
                    break

            logger.debug(f"Search returned {len(entries)} entries")
            return entries

        except Exception as e:
            logger.error(f"Search error: {e}")
            raise

    def _process_entry(self, entry) -> dict[str, Any]:
        """
        Process LDAP entry into dictionary format.

        Args:
            entry: LDAP entry from ldap3

        Returns:
            Dictionary representation of entry
        """
        entry_dict = {"dn": entry.entry_dn, "attributes": {}}

        for attr_name in entry.entry_attributes:
            attr_value = getattr(entry, attr_name)

            if hasattr(attr_value, "value"):
                # Handle ldap3 attribute objects
                value = attr_value.value
            else:
                value = str(attr_value)

            # Handle multi-valued attributes
            if isinstance(value, list) and len(value) == 1:
                entry_dict["attributes"][attr_name] = value[0]
            else:
                entry_dict["attributes"][attr_name] = value

        return entry_dict

    def test_connection(self) -> dict[str, Any]:
        """
        Test LDAP connection and return server information.

        Returns:
            Dictionary with connection test results
        """
        try:
            connection = self.connect()

            # Get server info
            server_info = {
                "connected": True,
                "server": connection.server.host,
                "port": connection.server.port,
                "ssl": connection.server.ssl,
                "bound": connection.bound,
                "auth_method": self.ldap_config.auth_method,
            }

            if self.ldap_config.auth_method != "anonymous":
                server_info["user"] = connection.user

            # Try a simple search to test functionality
            try:
                success = connection.search(
                    search_base=self.ldap_config.base_dn,
                    search_filter="(objectClass=*)",
                    search_scope=ldap3.BASE,
                    attributes=["namingContexts"],
                    size_limit=1,
                )
                server_info["search_test"] = success
                if success and connection.entries:
                    server_info["base_dn_exists"] = True
                else:
                    server_info["base_dn_exists"] = False
            except Exception as e:
                server_info["search_test"] = False
                server_info["search_error"] = str(e)

            logger.info("Connection test successful")
            return server_info

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return {
                "connected": False,
                "error": str(e),
                "auth_method": self.ldap_config.auth_method,
            }

    def get_schema_info(self) -> dict[str, Any]:
        """
        Get LDAP schema information.

        Returns:
            Dictionary with schema information
        """
        try:
            connection = self.connect()

            schema_info = {"object_classes": [], "attributes": [], "naming_contexts": []}

            # Get naming contexts
            if connection.server.info and connection.server.info.naming_contexts:
                schema_info["naming_contexts"] = list(connection.server.info.naming_contexts)

            # Get schema information if available
            if connection.server.info and connection.server.info.schema:
                schema = connection.server.info.schema

                # Get object classes
                if hasattr(schema, "object_classes"):
                    schema_info["object_classes"] = list(schema.object_classes.keys())

                # Get attribute types
                if hasattr(schema, "attribute_types"):
                    schema_info["attributes"] = list(schema.attribute_types.keys())

            return schema_info

        except Exception as e:
            logger.error(f"Schema info retrieval failed: {e}")
            return {"error": str(e)}

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
