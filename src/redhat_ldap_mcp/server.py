# # Copyright (c) 2024 Red Hat LDAP MCP
# # SPDX-License-Identifier: MIT
# #
# # Red Hat LDAP Model Context Protocol (MCP) Server
# # Provides LDAP integration for corporate directory services

"""Red Hat LDAP MCP Server implementation using FastMCP."""

import os
from typing import Any

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from .config.loader import load_config
from .core.ldap_connector import LDAPConnector
from .core.logging import get_logger, setup_logging
from .tools.groups import GroupsTool
from .tools.locations import LocationsTool
from .tools.organization import OrganizationTool
from .tools.people_search import PeopleSearchTool

logger = get_logger(__name__)

# Initialize MCP server
mcp = FastMCP("RedHat LDAP MCP")

# Global connector instance
_connector: LDAPConnector | None = None
_config = None


def get_connector() -> LDAPConnector:
    """Get the global LDAP connector instance."""
    global _connector, _config

    if _connector is None:
        if _config is None:
            # Load configuration
            config_path = os.getenv("REDHAT_LDAP_CONFIG", "config/redhat-ldap.json")
            _config = load_config(config_path)
            setup_logging(_config.logging)

        _connector = LDAPConnector(_config.ldap, _config.security, _config.performance)
        logger.info("LDAP connector initialized")

    return _connector


class PersonSummary(BaseModel):
    """Lightweight person summary for organization charts and bulk operations."""

    uid: str = Field(description="Unique identifier")
    cn: str = Field(description="Common name")
    title: str | None = Field(None, description="Job title")
    department: str | None = Field(None, description="Department")
    country: str | None = Field(None, description="Country")


class PersonResult(BaseModel):
    """Person search result model."""

    uid: str = Field(description="Unique identifier")
    dn: str | None = Field(None, description="Distinguished name")
    cn: str = Field(description="Common name")
    display_name: str | None = Field(None, description="Display name")
    given_name: str | None = Field(None, description="First name")
    surname: str | None = Field(None, description="Last name")
    mail: str | None = Field(None, description="Email address")
    title: str | None = Field(None, description="Job title")
    department: str | None = Field(None, description="Department")
    manager: str | None = Field(None, description="Manager's DN")
    office_location: str | None = Field(None, description="Office location")
    phone: str | None = Field(None, description="Phone number")
    mobile: str | None = Field(None, description="Mobile phone")
    city: str | None = Field(None, description="City")
    state: str | None = Field(None, description="State")
    country: str | None = Field(None, description="Country")
    employee_id: str | None = Field(None, description="Employee ID")
    employee_type: str | None = Field(None, description="Employee type")
    cost_center: str | None = Field(None, description="Cost center")
    # Red Hat specific fields
    rhat_job_title: str | None = Field(None, description="Red Hat job title")
    rhat_cost_center: str | None = Field(None, description="Red Hat cost center code")
    rhat_cost_center_desc: str | None = Field(None, description="Red Hat cost center description")
    rhat_location: str | None = Field(None, description="Red Hat location")
    rhat_bio: str | None = Field(None, description="Red Hat bio/profile")
    rhat_geo: str | None = Field(None, description="Red Hat geographical region")
    rhat_organization: str | None = Field(None, description="Red Hat organization")
    rhat_job_role: str | None = Field(None, description="Red Hat job role")
    rhat_team_lead: str | None = Field(None, description="Red Hat team lead")
    rhat_original_hire_date: str | None = Field(None, description="Red Hat original hire date")
    rhat_hire_date: str | None = Field(None, description="Red Hat hire date")
    rhat_worker_id: str | None = Field(None, description="Red Hat worker ID")
    rhat_building_code: str | None = Field(None, description="Red Hat building code")
    rhat_office_location: str | None = Field(None, description="Red Hat office location")


@mcp.tool()
def search_people(
    query: str = Field(description="Search query (name, email, uid, etc.)"),
    max_results: int = Field(default=10, description="Maximum number of results"),
) -> list[PersonResult]:
    """
    Search for people in the corporate directory.

    Supports searching by:
    - Name (first, last, or full name)
    - Email address
    - Username (uid)
    - Employee ID
    - Department
    """
    connector = get_connector()
    tool = PeopleSearchTool(connector)

    try:
        results = tool.search_people(query, max_results)
        return [PersonResult(**person) for person in results]
    except Exception as e:
        logger.error(f"People search failed: {e}")
        raise


@mcp.tool()
def get_person_details(
    identifier: str = Field(description="Person identifier (uid, email, or DN)"),
) -> PersonResult | None:
    """
    Get detailed information about a specific person.

    Args:
        identifier: Can be uid, email address, or full DN
    """
    connector = get_connector()
    tool = PeopleSearchTool(connector)

    try:
        person = tool.get_person_details(identifier)
        return PersonResult(**person) if person else None
    except Exception as e:
        logger.error(f"Get person details failed: {e}")
        raise


class OrganizationNodeSummary(BaseModel):
    """Lightweight organization chart node for reduced token usage."""

    person: PersonSummary = Field(description="Person summary information")
    direct_reports: list["OrganizationNodeSummary"] = Field(
        default=[], description="Direct reports"
    )
    level: int = Field(description="Organizational level")


class OrganizationNode(BaseModel):
    """Organization chart node model."""

    person: PersonResult = Field(description="Person information")
    direct_reports: list["OrganizationNode"] = Field(default=[], description="Direct reports")
    level: int = Field(description="Organizational level")


@mcp.tool()
def get_organization_chart(
    manager_id: str = Field(description="Manager identifier (uid, email, or DN)"),
    max_depth: int = Field(default=3, description="Maximum depth to traverse"),
) -> OrganizationNode | None:
    """
    Get organization chart starting from a specific manager.

    Returns a hierarchical view of the organization structure.
    """
    connector = get_connector()
    tool = OrganizationTool(connector)

    try:
        org_data = tool.build_organization_chart(manager_id, max_depth)
        if org_data:
            return OrganizationNode(**org_data)
        return None
    except Exception as e:
        logger.error(f"Organization chart failed: {e}")
        raise


@mcp.tool()
def get_organization_chart_summary(
    manager_id: str = Field(description="Manager identifier (uid, email, or DN)"),
    max_depth: int = Field(default=3, description="Maximum depth to traverse"),
) -> OrganizationNodeSummary | None:
    """
    Get lightweight organization chart for reduced token usage.

    Returns a hierarchical view with minimal person data (uid, name, title, department, country).
    Ideal for large organization charts where token usage is a concern.
    """
    connector = get_connector()
    tool = OrganizationTool(connector)

    try:
        org_data = tool.build_organization_chart_summary(manager_id, max_depth)
        if org_data:
            return OrganizationNodeSummary(**org_data)
        return None
    except Exception as e:
        logger.error(f"Organization chart summary failed: {e}")
        raise


@mcp.tool()
def search_people_summary(
    query: str = Field(description="Search query (name, email, uid, etc.)"),
    max_results: int = Field(default=10, description="Maximum number of results"),
) -> list[PersonSummary]:
    """
    Search for people with lightweight summaries for reduced token usage.

    Returns minimal person data (uid, name, title, department, country) instead of full details.
    Ideal when you need to search many people but don't need comprehensive information.
    """
    connector = get_connector()
    tool = PeopleSearchTool(connector)

    try:
        # Get the search filter
        search_filter = tool._build_search_filter(query)

        # Use summary attributes
        attributes = tool.get_person_summary_attributes()

        results = connector.search(
            search_base=tool._get_people_search_base(),
            search_filter=search_filter,
            attributes=attributes,
            size_limit=max_results,
        )

        people = []
        for entry in results:
            person = tool._process_person_summary(entry)
            if person:
                people.append(PersonSummary(**person))

        return people
    except Exception as e:
        logger.error(f"People summary search failed: {e}")
        raise


@mcp.tool()
def find_manager_chain(
    person_id: str = Field(description="Person identifier (uid, email, or DN)"),
) -> list[PersonResult]:
    """
    Find the management chain for a person (all managers up to the top).
    """
    connector = get_connector()
    tool = OrganizationTool(connector)

    try:
        managers = tool.get_manager_chain(person_id)
        return [PersonResult(**manager) for manager in managers]
    except Exception as e:
        logger.error(f"Manager chain search failed: {e}")
        raise


class GroupInfo(BaseModel):
    """Group information model."""

    cn: str = Field(description="Group name")
    dn: str = Field(description="Group distinguished name")
    description: str | None = Field(None, description="Group description")
    member_count: int = Field(description="Number of members")
    members: list[str] = Field(default=[], description="Member DNs")


@mcp.tool()
def search_groups(
    query: str = Field(description="Group search query"),
    max_results: int = Field(default=10, description="Maximum number of results"),
) -> list[GroupInfo]:
    """
    Search for groups in the directory.
    """
    connector = get_connector()
    tool = GroupsTool(connector)

    try:
        groups = tool.search_groups(query, max_results)
        return [GroupInfo(**group) for group in groups]
    except Exception as e:
        logger.error(f"Group search failed: {e}")
        raise


@mcp.tool()
def get_person_groups(
    person_id: str = Field(description="Person identifier (uid, email, or DN)"),
) -> list[GroupInfo]:
    """
    Get all groups that a person is a member of.
    """
    connector = get_connector()
    tool = GroupsTool(connector)

    try:
        groups = tool.get_person_groups(person_id)
        return [GroupInfo(**group) for group in groups]
    except Exception as e:
        logger.error(f"Person groups search failed: {e}")
        raise


@mcp.tool()
def get_group_members(
    group_name: str = Field(description="Group name or DN"),
) -> list[PersonResult]:
    """
    Get all members of a specific group.
    """
    connector = get_connector()
    tool = GroupsTool(connector)

    try:
        members = tool.get_group_members(group_name)
        return [PersonResult(**member) for member in members]
    except Exception as e:
        logger.error(f"Group members search failed: {e}")
        raise


class LocationInfo(BaseModel):
    """Location information model."""

    name: str = Field(description="Location name")
    address: str | None = Field(None, description="Street address")
    city: str | None = Field(None, description="City")
    state: str | None = Field(None, description="State/Province")
    country: str | None = Field(None, description="Country")
    people_count: int = Field(description="Number of people at this location")


@mcp.tool()
def find_locations(
    query: str | None = Field(None, description="Location search query")
) -> list[LocationInfo]:
    """
    Find office locations and people counts.
    """
    connector = get_connector()
    tool = LocationsTool(connector)

    try:
        locations = tool.find_locations(query)
        return [LocationInfo(**location) for location in locations]
    except Exception as e:
        logger.error(f"Location search failed: {e}")
        raise


@mcp.tool()
def get_people_at_location(
    location: str = Field(description="Location name"),
    max_results: int = Field(default=50, description="Maximum number of results"),
) -> list[PersonResult]:
    """
    Get all people at a specific location.
    """
    connector = get_connector()
    tool = LocationsTool(connector)

    try:
        people = tool.get_people_at_location(location, max_results)
        return [PersonResult(**person) for person in people]
    except Exception as e:
        logger.error(f"People at location search failed: {e}")
        raise


@mcp.tool()
def test_connection() -> dict[str, Any]:
    """
    Test the LDAP connection and return connection status.
    """
    connector = get_connector()

    try:
        result = connector.test_connection()
        return result
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return {"connected": False, "error": str(e)}


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
