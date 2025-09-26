# # Copyright (c) 2024 Red Hat LDAP MCP
# # SPDX-License-Identifier: MIT
# #
# # Red Hat LDAP Model Context Protocol (MCP) Server
# # Provides LDAP integration for corporate directory services

"""Integration tests for RedHat LDAP MCP server tools."""

from unittest.mock import Mock, patch

import pytest

from redhat_ldap_mcp.tools.groups import GroupsTool
from redhat_ldap_mcp.tools.locations import LocationsTool
from redhat_ldap_mcp.tools.organization import OrganizationTool
from redhat_ldap_mcp.tools.people_search import PeopleSearchTool


class TestMCPServerTools:
    """Test suite for MCP server tools."""

    @pytest.fixture
    def mock_ldap_results(self):
        """Mock LDAP search results for testing."""
        return [
            {
                "dn": "uid=jlaska,ou=users,dc=redhat,dc=com",
                "attributes": {
                    "uid": "jlaska",
                    "cn": "James Laska",
                    "givenName": "James",
                    "sn": "Laska",
                    "mail": "jlaska@redhat.com",
                    "title": "Senior Software Engineer",
                    "department": "Engineering",
                    "manager": "uid=manager1,ou=users,dc=redhat,dc=com",
                    "rhatLocation": "Boston",
                    "telephoneNumber": "+1-555-0123",
                    "rhatJobTitle": "Principal Engineer",
                    "rhatCostCenter": "12345",
                },
            }
        ]

    @pytest.fixture
    def mock_connector(self, mock_ldap_results):
        """Mock LDAP connector for testing."""
        mock_conn = Mock()
        mock_conn.search.return_value = mock_ldap_results
        mock_conn.test_connection.return_value = {
            "connected": True,
            "server": "ldap.corp.redhat.com",
            "port": 389,
        }
        mock_conn.ldap_config = Mock()
        mock_conn.ldap_config.base_dn = "dc=redhat,dc=com"
        return mock_conn

    def test_people_search_tool(self, mock_connector):
        """Test the PeopleSearchTool functionality."""
        tool = PeopleSearchTool(mock_connector)
        results = tool.search_people("James Laska", max_results=10)

        assert len(results) == 1
        assert results[0]["uid"] == "jlaska"
        assert results[0]["cn"] == "James Laska"
        assert results[0]["mail"] == "jlaska@redhat.com"
        assert results[0]["title"] == "Senior Software Engineer"
        assert results[0]["department"] == "Engineering"

        # Verify LDAP search was called
        mock_connector.search.assert_called_once()

    def test_get_person_details_tool(self, mock_connector):
        """Test the get_person_details functionality."""
        tool = PeopleSearchTool(mock_connector)
        result = tool.get_person_details("jlaska")

        assert result["uid"] == "jlaska"
        assert result["cn"] == "James Laska"
        assert result["office_location"] == "Boston"

        # Verify LDAP search was called
        mock_connector.search.assert_called_once()

    def test_organization_tool(self, mock_connector):
        """Test the OrganizationTool functionality."""
        tool = OrganizationTool(mock_connector)

        # Test finding direct reports
        reports = tool.find_direct_reports("manager1")
        assert isinstance(reports, list)

        # Test building org chart
        org_chart = tool.build_organization_chart("manager1", max_depth=2)
        # org_chart could be None if person not found, that's OK for this test
        assert org_chart is None or isinstance(org_chart, dict)

    def test_attribute_consistency_between_tools(self, mock_connector):
        """Test that organization tool uses same comprehensive attributes as people search tool."""
        # Mock schema to include extended attributes
        mock_schema = Mock()
        mock_schema.corporate_attributes = ["rhatWorkerId", "rhatPersonType"]
        mock_schema.redhat_attributes = [
            "rhatJobTitle",
            "rhatCostCenter",
            "rhatGeo",
            "rhatLocation",
        ]
        mock_connector.ldap_config.schema = mock_schema

        people_tool = PeopleSearchTool(mock_connector)
        org_tool = OrganizationTool(mock_connector)

        # Get expected attributes from people search tool
        expected_attributes = people_tool.get_person_attributes()

        # Mock to capture attributes used by organization tool
        captured_attributes = []

        def mock_search(*args, **kwargs):
            captured_attributes.extend(kwargs.get("attributes", []))
            return []

        # Mock the organization tool's dependencies
        org_tool.people_tool.get_person_details = Mock(
            return_value={"uid": "manager1", "dn": "uid=manager1,ou=users,dc=redhat,dc=com"}
        )
        org_tool.people_tool._get_people_search_base = Mock(
            return_value="ou=users,dc=redhat,dc=com"
        )
        mock_connector.search = mock_search

        # Call find_direct_reports to trigger attribute usage
        org_tool.find_direct_reports("manager1")

        # Verify comprehensive attributes are used including location fields
        location_attrs = [
            "l",
            "st",
            "co",
            "physicalDeliveryOfficeName",
            "mobile",
            "employeeNumber",
            "employeeType",
        ]
        for attr in location_attrs:
            assert attr in captured_attributes, f"Missing location attribute: {attr}"

        # Verify the captured attributes match expected attributes
        assert set(captured_attributes) == set(
            expected_attributes
        ), f"Attribute mismatch. Expected: {expected_attributes}, Got: {captured_attributes}"

    def test_groups_tool(self, mock_connector):
        """Test the GroupsTool functionality."""
        # Mock group search results
        mock_connector.search.return_value = [
            {
                "dn": "cn=engineers,ou=groups,dc=redhat,dc=com",
                "attributes": {
                    "cn": "engineers",
                    "description": "Engineering Team",
                    "member": ["uid=jlaska,ou=users,dc=redhat,dc=com"],
                },
            }
        ]

        tool = GroupsTool(mock_connector)
        groups = tool.search_groups("engineers", max_results=10)

        assert len(groups) == 1
        assert groups[0]["cn"] == "engineers"

    def test_locations_tool(self, mock_connector):
        """Test the LocationsTool functionality."""
        tool = LocationsTool(mock_connector)

        # Test finding locations
        locations = tool.find_locations("Boston")
        assert isinstance(locations, list)

        # Test getting people at location
        people = tool.get_people_at_location("Boston", max_results=50)
        assert isinstance(people, list)


class TestMCPServerConfiguration:
    """Test MCP server configuration."""

    @patch("redhat_ldap_mcp.server.load_config")
    @patch("redhat_ldap_mcp.server.setup_logging")
    def test_server_configuration_loading(self, mock_setup_logging, mock_load_config):
        """Test that server configuration loads correctly."""
        # This test verifies the imports and basic structure work
        from redhat_ldap_mcp import server

        assert hasattr(server, "mcp")
        assert server.mcp is not None


if __name__ == "__main__":
    pytest.main([__file__])
