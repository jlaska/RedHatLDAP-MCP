# # Copyright (c) 2024 Red Hat LDAP MCP
# # SPDX-License-Identifier: MIT
# #
# # Red Hat LDAP Model Context Protocol (MCP) Server
# # Provides LDAP integration for corporate directory services

"""Tests for LDAP connector functionality."""

from unittest.mock import Mock, patch

import pytest
from ldap3.core.exceptions import LDAPException, LDAPSocketOpenError

from redhat_ldap_mcp.config.models import LDAPConfig, PerformanceConfig, SecurityConfig
from redhat_ldap_mcp.core.ldap_connector import LDAPConnector


class TestLDAPConnectorInit:
    """Test LDAP connector initialization."""

    def test_connector_initialization(self):
        """Test basic connector initialization."""
        ldap_config = LDAPConfig(
            server="ldap://test.com", base_dn="dc=test,dc=com", auth_method="anonymous"
        )
        security_config = SecurityConfig()
        performance_config = PerformanceConfig()

        connector = LDAPConnector(ldap_config, security_config, performance_config)

        assert connector.ldap_config.server == "ldap://test.com"
        assert connector.ldap_config.auth_method == "anonymous"
        assert connector._connection is None

    @patch("redhat_ldap_mcp.core.ldap_connector.Server")
    def test_server_setup_without_tls(self, mock_server):
        """Test server setup without TLS."""
        ldap_config = LDAPConfig(
            server="ldap://test.com", base_dn="dc=test,dc=com", auth_method="anonymous"
        )
        security_config = SecurityConfig(enable_tls=False)
        performance_config = PerformanceConfig()

        LDAPConnector(ldap_config, security_config, performance_config)

        mock_server.assert_called_once()
        call_args = mock_server.call_args
        assert call_args[0][0] == "ldap://test.com"
        assert call_args[1]["tls"] is None

    @patch("redhat_ldap_mcp.core.ldap_connector.Server")
    @patch("redhat_ldap_mcp.core.ldap_connector.ldap3.Tls")
    def test_server_setup_with_tls(self, mock_tls, mock_server):
        """Test server setup with TLS enabled."""
        ldap_config = LDAPConfig(
            server="ldaps://test.com",
            base_dn="dc=test,dc=com",
            auth_method="anonymous",
            use_ssl=True,
        )
        security_config = SecurityConfig(enable_tls=True, validate_certificate=True)
        performance_config = PerformanceConfig()

        LDAPConnector(ldap_config, security_config, performance_config)

        mock_tls.assert_called_once()
        mock_server.assert_called_once()


class TestLDAPConnectorAuth:
    """Test LDAP connector authentication methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.ldap_config = LDAPConfig(
            server="ldap://test.com", base_dn="dc=test,dc=com", auth_method="anonymous"
        )
        self.security_config = SecurityConfig()
        self.performance_config = PerformanceConfig(max_retries=1)  # Fast tests

    @patch("redhat_ldap_mcp.core.ldap_connector.Connection")
    def test_create_anonymous_connection(self, mock_connection):
        """Test creating anonymous connection."""
        connector = LDAPConnector(self.ldap_config, self.security_config, self.performance_config)

        connector._create_anonymous_connection()

        mock_connection.assert_called_once()
        call_kwargs = mock_connection.call_args[1]
        assert call_kwargs["authentication"] == "ANONYMOUS"

    @patch("redhat_ldap_mcp.core.ldap_connector.Connection")
    def test_create_simple_connection(self, mock_connection):
        """Test creating simple bind connection."""
        self.ldap_config.auth_method = "simple"
        self.ldap_config.bind_dn = "cn=admin,dc=test,dc=com"
        self.ldap_config.password = "secret"

        connector = LDAPConnector(self.ldap_config, self.security_config, self.performance_config)

        connector._create_simple_connection()

        mock_connection.assert_called_once()
        call_kwargs = mock_connection.call_args[1]
        assert call_kwargs["user"] == "cn=admin,dc=test,dc=com"
        assert call_kwargs["password"] == "secret"
        assert call_kwargs["authentication"] == "SIMPLE"

    def test_create_simple_connection_missing_credentials(self):
        """Test simple connection without credentials raises error."""
        self.ldap_config.auth_method = "simple"
        # Missing bind_dn and password

        connector = LDAPConnector(self.ldap_config, self.security_config, self.performance_config)

        with pytest.raises(ValueError, match="Simple authentication requires"):
            connector._create_simple_connection()

    def test_create_sasl_connection_not_implemented(self):
        """Test SASL connection raises NotImplementedError."""
        self.ldap_config.auth_method = "sasl"

        connector = LDAPConnector(self.ldap_config, self.security_config, self.performance_config)

        with pytest.raises(NotImplementedError, match="SASL authentication is not yet implemented"):
            connector._create_sasl_connection()

    def test_create_connection_invalid_method(self):
        """Test invalid authentication method raises error."""
        self.ldap_config.auth_method = "invalid"

        connector = LDAPConnector(self.ldap_config, self.security_config, self.performance_config)

        with pytest.raises(ValueError, match="Unsupported authentication method"):
            connector._create_connection()


class TestLDAPConnectorConnection:
    """Test LDAP connector connection management."""

    def setup_method(self):
        """Set up test fixtures."""
        self.ldap_config = LDAPConfig(
            server="ldap://test.com", base_dn="dc=test,dc=com", auth_method="anonymous"
        )
        self.security_config = SecurityConfig()
        self.performance_config = PerformanceConfig(max_retries=2, retry_delay=0.1)

    @patch("redhat_ldap_mcp.core.ldap_connector.Connection")
    def test_connection_success(self, mock_connection_class):
        """Test successful connection."""
        # Mock successful connection
        mock_connection = Mock()
        mock_connection.bind.return_value = True
        mock_connection.search.return_value = True
        mock_connection.bound = True
        mock_connection_class.return_value = mock_connection

        connector = LDAPConnector(self.ldap_config, self.security_config, self.performance_config)

        connection = connector.connect()

        assert connection == mock_connection
        assert connector._connection == mock_connection
        mock_connection.bind.assert_called_once()

    @patch("redhat_ldap_mcp.core.ldap_connector.Connection")
    def test_connection_bind_failure(self, mock_connection_class):
        """Test connection bind failure."""
        # Mock failed bind
        mock_connection = Mock()
        mock_connection.bind.return_value = False
        mock_connection.result = {"description": "bind failed"}
        mock_connection_class.return_value = mock_connection

        connector = LDAPConnector(self.ldap_config, self.security_config, self.performance_config)

        with pytest.raises(LDAPException, match="Failed to connect to LDAP server"):
            connector.connect()

    @patch("redhat_ldap_mcp.core.ldap_connector.Connection")
    @patch("redhat_ldap_mcp.core.ldap_connector.time.sleep")  # Speed up test
    def test_connection_retry_logic(self, mock_sleep, mock_connection_class):
        """Test connection retry logic."""
        # Mock connection that fails first attempt, succeeds second
        mock_connection = Mock()
        mock_connection.bind.side_effect = [False, True]  # Fail, then succeed
        mock_connection.search.return_value = True
        mock_connection.bound = True
        mock_connection_class.return_value = mock_connection

        connector = LDAPConnector(self.ldap_config, self.security_config, self.performance_config)

        connection = connector.connect()

        assert connection == mock_connection
        assert mock_connection.bind.call_count == 2
        mock_sleep.assert_called_once_with(0.1)  # retry_delay

    @patch("redhat_ldap_mcp.core.ldap_connector.Connection")
    def test_connection_socket_error(self, mock_connection_class):
        """Test connection socket error handling."""
        # Mock socket error
        mock_connection_class.side_effect = LDAPSocketOpenError("Connection refused")

        connector = LDAPConnector(self.ldap_config, self.security_config, self.performance_config)

        with pytest.raises(LDAPException, match="Failed to connect to LDAP server"):
            connector.connect()

    def test_disconnect(self):
        """Test disconnection."""
        connector = LDAPConnector(self.ldap_config, self.security_config, self.performance_config)

        # Mock existing connection
        mock_connection = Mock()
        connector._connection = mock_connection

        connector.disconnect()

        mock_connection.unbind.assert_called_once()
        assert connector._connection is None

    def test_disconnect_with_error(self):
        """Test disconnection with error."""
        connector = LDAPConnector(self.ldap_config, self.security_config, self.performance_config)

        # Mock connection that raises error on unbind
        mock_connection = Mock()
        mock_connection.unbind.side_effect = Exception("Unbind error")
        connector._connection = mock_connection

        # Should not raise exception
        connector.disconnect()
        assert connector._connection is None


class TestLDAPConnectorSearch:
    """Test LDAP connector search functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.ldap_config = LDAPConfig(
            server="ldap://test.com", base_dn="dc=test,dc=com", auth_method="anonymous"
        )
        self.security_config = SecurityConfig()
        self.performance_config = PerformanceConfig(page_size=2, max_results=5)

        self.connector = LDAPConnector(
            self.ldap_config, self.security_config, self.performance_config
        )

    @patch.object(LDAPConnector, "connect")
    def test_search_success(self, mock_connect):
        """Test successful search operation."""
        # Mock connection and search results
        mock_connection = Mock()
        mock_connection.search.return_value = True
        mock_connection.result = {}

        # Mock LDAP entries
        mock_entry1 = Mock()
        mock_entry1.entry_dn = "uid=user1,ou=people,dc=test,dc=com"
        mock_entry1.entry_attributes = ["uid", "cn"]
        mock_entry1.uid = Mock()
        mock_entry1.uid.value = "user1"
        mock_entry1.cn = Mock()
        mock_entry1.cn.value = "User One"

        mock_entry2 = Mock()
        mock_entry2.entry_dn = "uid=user2,ou=people,dc=test,dc=com"
        mock_entry2.entry_attributes = ["uid", "cn"]
        mock_entry2.uid = Mock()
        mock_entry2.uid.value = "user2"
        mock_entry2.cn = Mock()
        mock_entry2.cn.value = "User Two"

        mock_connection.entries = [mock_entry1, mock_entry2]
        mock_connect.return_value = mock_connection

        results = self.connector.search(
            search_base="ou=people,dc=test,dc=com", search_filter="(objectClass=person)"
        )

        assert len(results) == 2
        assert results[0]["dn"] == "uid=user1,ou=people,dc=test,dc=com"
        assert results[0]["attributes"]["uid"] == "user1"
        assert results[0]["attributes"]["cn"] == "User One"

    @patch.object(LDAPConnector, "connect")
    def test_search_failure(self, mock_connect):
        """Test search failure handling."""
        # Mock connection with failed search
        mock_connection = Mock()
        mock_connection.search.return_value = False
        mock_connection.result = {"description": "search failed"}
        mock_connect.return_value = mock_connection

        with pytest.raises(LDAPException, match="Search failed"):
            self.connector.search(
                search_base="ou=people,dc=test,dc=com", search_filter="(objectClass=person)"
            )

    @patch.object(LDAPConnector, "connect")
    def test_search_with_size_limit(self, mock_connect):
        """Test search with size limit."""
        # Mock connection with many results
        mock_connection = Mock()
        mock_connection.search.return_value = True
        mock_connection.result = {}

        # Create 3 mock entries
        mock_entries = []
        for i in range(3):
            mock_entry = Mock()
            mock_entry.entry_dn = f"uid=user{i},ou=people,dc=test,dc=com"
            mock_entry.entry_attributes = ["uid"]
            mock_entry.uid = Mock()
            mock_entry.uid.value = f"user{i}"
            mock_entries.append(mock_entry)

        mock_connection.entries = mock_entries
        mock_connect.return_value = mock_connection

        # Search with limit of 2
        results = self.connector.search(
            search_base="ou=people,dc=test,dc=com",
            search_filter="(objectClass=person)",
            size_limit=2,
        )

        assert len(results) == 2

    def test_process_entry(self):
        """Test entry processing."""
        # Create mock entry
        mock_entry = Mock()
        mock_entry.entry_dn = "uid=test,ou=people,dc=test,dc=com"
        mock_entry.entry_attributes = ["uid", "cn", "memberOf"]

        # Mock attribute values
        mock_entry.uid = Mock()
        mock_entry.uid.value = "testuser"
        mock_entry.cn = Mock()
        mock_entry.cn.value = "Test User"
        mock_entry.memberOf = Mock()
        mock_entry.memberOf.value = ["group1", "group2"]  # Multi-valued

        result = self.connector._process_entry(mock_entry)

        assert result["dn"] == "uid=test,ou=people,dc=test,dc=com"
        assert result["attributes"]["uid"] == "testuser"
        assert result["attributes"]["cn"] == "Test User"
        assert result["attributes"]["memberOf"] == ["group1", "group2"]

    def test_process_entry_single_value_list(self):
        """Test processing entry with single-value list."""
        mock_entry = Mock()
        mock_entry.entry_dn = "uid=test,ou=people,dc=test,dc=com"
        mock_entry.entry_attributes = ["mail"]

        # Single value in list should be extracted
        mock_entry.mail = Mock()
        mock_entry.mail.value = ["test@example.com"]

        result = self.connector._process_entry(mock_entry)

        assert result["attributes"]["mail"] == "test@example.com"  # Extracted from list


class TestLDAPConnectorTestConnection:
    """Test LDAP connector connection testing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.ldap_config = LDAPConfig(
            server="ldap://test.com", base_dn="dc=test,dc=com", auth_method="anonymous"
        )
        self.security_config = SecurityConfig()
        self.performance_config = PerformanceConfig()

        self.connector = LDAPConnector(
            self.ldap_config, self.security_config, self.performance_config
        )

    @patch.object(LDAPConnector, "connect")
    def test_connection_test_success(self, mock_connect):
        """Test successful connection test."""
        # Mock successful connection
        mock_connection = Mock()
        mock_connection.server.host = "test.com"
        mock_connection.server.port = 389
        mock_connection.server.ssl = False
        mock_connection.bound = True
        mock_connection.search.return_value = True
        mock_connection.entries = [Mock()]  # Has results

        mock_connect.return_value = mock_connection

        result = self.connector.test_connection()

        assert result["connected"] is True
        assert result["server"] == "test.com"
        assert result["port"] == 389
        assert result["ssl"] is False
        assert result["bound"] is True
        assert result["auth_method"] == "anonymous"
        assert result["search_test"] is True
        assert result["base_dn_exists"] is True

    @patch.object(LDAPConnector, "connect")
    def test_connection_test_failure(self, mock_connect):
        """Test connection test failure."""
        # Mock connection failure
        mock_connect.side_effect = LDAPException("Connection failed")

        result = self.connector.test_connection()

        assert result["connected"] is False
        assert result["error"] == "Connection failed"
        assert result["auth_method"] == "anonymous"

    @patch.object(LDAPConnector, "connect")
    def test_connection_test_search_failure(self, mock_connect):
        """Test connection test with search failure."""
        # Mock connection success but search failure
        mock_connection = Mock()
        mock_connection.server.host = "test.com"
        mock_connection.server.port = 389
        mock_connection.server.ssl = False
        mock_connection.bound = True
        mock_connection.search.side_effect = Exception("Search error")

        mock_connect.return_value = mock_connection

        result = self.connector.test_connection()

        assert result["connected"] is True
        assert result["search_test"] is False
        assert result["search_error"] == "Search error"


class TestLDAPConnectorContextManager:
    """Test LDAP connector context manager functionality."""

    def test_context_manager(self):
        """Test connector as context manager."""
        ldap_config = LDAPConfig(
            server="ldap://test.com", base_dn="dc=test,dc=com", auth_method="anonymous"
        )
        security_config = SecurityConfig()
        performance_config = PerformanceConfig()

        with patch.object(LDAPConnector, "disconnect") as mock_disconnect:
            with LDAPConnector(ldap_config, security_config, performance_config) as connector:
                assert isinstance(connector, LDAPConnector)

            mock_disconnect.assert_called_once()
