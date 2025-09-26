# # Copyright (c) 2024 Red Hat LDAP MCP
# # SPDX-License-Identifier: MIT
# #
# # Red Hat LDAP Model Context Protocol (MCP) Server
# # Provides LDAP integration for corporate directory services

"""Organization chart tool for corporate LDAP directories."""

from typing import Any

from ..core.ldap_connector import LDAPConnector
from ..core.logging import get_logger
from .people_search import PeopleSearchTool

logger = get_logger(__name__)


class OrganizationTool:
    """Tool for building organization charts and exploring reporting structures."""

    def __init__(self, connector: LDAPConnector):
        """Initialize the organization tool.

        Args:
            connector: LDAP connector instance
        """
        self.connector = connector
        self.people_tool = PeopleSearchTool(connector)

    def build_organization_chart(
        self, manager_id: str, max_depth: int = 3
    ) -> dict[str, Any] | None:
        """
        Build an organization chart starting from a manager.

        Args:
            manager_id: Manager identifier (uid, email, or DN)
            max_depth: Maximum depth to traverse

        Returns:
            Organization chart data structure
        """
        logger.info(f"Building org chart for manager: {manager_id}, depth: {max_depth}")

        # Get the manager's details
        manager = self.people_tool.get_person_details(manager_id)
        if not manager:
            logger.warning(f"Manager not found: {manager_id}")
            return None

        # Build the org chart recursively
        org_node = self._build_org_node(manager, 0, max_depth)
        logger.info(f"Built org chart with {self._count_nodes(org_node)} total people")
        return org_node

    def get_manager_chain(self, person_id: str) -> list[dict[str, Any]]:
        """
        Get the management chain for a person (all managers up to the top).

        Args:
            person_id: Person identifier (uid, email, or DN)

        Returns:
            List of managers from immediate manager to top level
        """
        logger.info(f"Finding manager chain for: {person_id}")

        person = self.people_tool.get_person_details(person_id)
        if not person:
            logger.warning(f"Person not found: {person_id}")
            return []

        managers = []
        current_person = person
        max_levels = 10  # Prevent infinite loops

        for _ in range(max_levels):
            manager_dn = current_person.get("manager")
            if not manager_dn:
                break

            # Get manager details
            manager = self.people_tool.get_person_details(manager_dn)
            if not manager:
                logger.warning(f"Manager not found: {manager_dn}")
                break

            managers.append(manager)
            current_person = manager

            # Check if we've reached the top (manager reports to themselves or no manager)
            if manager.get("manager") == manager_dn or not manager.get("manager"):
                break

        logger.info(f"Found {len(managers)} managers in chain")
        return managers

    def find_direct_reports(self, manager_id: str) -> list[dict[str, Any]]:
        """
        Find all direct reports for a manager.

        Args:
            manager_id: Manager identifier (uid, email, or DN)

        Returns:
            List of direct reports
        """
        logger.info(f"Finding direct reports for: {manager_id}")

        # Get manager details to get their DN
        manager = self.people_tool.get_person_details(manager_id)
        if not manager:
            logger.warning(f"Manager not found: {manager_id}")
            return []

        manager_dn = manager.get("dn")
        if not manager_dn:
            logger.warning("Manager DN not found")
            return []

        # Search for people who report to this manager
        search_filter = f"(manager={manager_dn})"

        try:
            # Use comprehensive attributes list from people search tool
            attributes = self.people_tool.get_person_attributes()

            results = self.connector.search(
                search_base=self.people_tool._get_people_search_base(),
                search_filter=search_filter,
                attributes=attributes,
            )

            direct_reports = []
            for entry in results:
                person = self.people_tool._process_person_entry(entry)
                if person and person.get("uid") != manager.get("uid"):  # Don't include manager
                    direct_reports.append(person)

            logger.info(f"Found {len(direct_reports)} direct reports")
            return direct_reports

        except Exception as e:
            logger.error(f"Direct reports search failed: {e}")
            return []

    def get_team_structure(self, person_id: str, include_peers: bool = True) -> dict[str, Any]:
        """
        Get the team structure around a person (manager, peers, direct reports).

        Args:
            person_id: Person identifier
            include_peers: Whether to include peer information

        Returns:
            Team structure data
        """
        logger.info(f"Getting team structure for: {person_id}")

        person = self.people_tool.get_person_details(person_id)
        if not person:
            return {}

        team_structure = {"person": person, "manager": None, "peers": [], "direct_reports": []}

        # Get manager
        manager_dn = person.get("manager")
        if manager_dn:
            manager = self.people_tool.get_person_details(manager_dn)
            if manager:
                team_structure["manager"] = manager

                # Get peers if requested (other people with same manager)
                if include_peers:
                    peers = self.find_direct_reports(manager_dn)
                    # Remove the person themselves from peers
                    team_structure["peers"] = [
                        peer for peer in peers if peer.get("uid") != person.get("uid")
                    ]

        # Get direct reports
        team_structure["direct_reports"] = self.find_direct_reports(person_id)

        return team_structure

    def _build_org_node(
        self, person: dict[str, Any], current_depth: int, max_depth: int
    ) -> dict[str, Any]:
        """
        Recursively build an organization node.

        Args:
            person: Person data
            current_depth: Current depth in the tree
            max_depth: Maximum depth to traverse

        Returns:
            Organization node
        """
        node = {"person": person, "direct_reports": [], "level": current_depth}

        # If we haven't reached max depth, get direct reports
        if current_depth < max_depth:
            direct_reports = self.find_direct_reports(person.get("uid", ""))

            for report in direct_reports:
                child_node = self._build_org_node(report, current_depth + 1, max_depth)
                node["direct_reports"].append(child_node)

        return node

    def _count_nodes(self, node: dict[str, Any]) -> int:
        """
        Count total nodes in an organization tree.

        Args:
            node: Organization node

        Returns:
            Total count of nodes
        """
        count = 1  # Count this node
        for child in node.get("direct_reports", []):
            count += self._count_nodes(child)
        return count

    def find_common_manager(self, person1_id: str, person2_id: str) -> dict[str, Any] | None:
        """
        Find the common manager between two people.

        Args:
            person1_id: First person identifier
            person2_id: Second person identifier

        Returns:
            Common manager or None if not found
        """
        logger.info(f"Finding common manager between {person1_id} and {person2_id}")

        # Get manager chains for both people
        chain1 = self.get_manager_chain(person1_id)
        chain2 = self.get_manager_chain(person2_id)

        if not chain1 or not chain2:
            return None

        # Convert to sets of UIDs for easier comparison
        managers1 = {mgr.get("uid") for mgr in chain1 if mgr.get("uid")}
        managers2 = {mgr.get("uid") for mgr in chain2 if mgr.get("uid")}

        # Find intersection (common managers)
        common_manager_uids = managers1.intersection(managers2)

        if not common_manager_uids:
            return None

        # Return the lowest level common manager (first in either chain)
        for manager in chain1:
            if manager.get("uid") in common_manager_uids:
                logger.info(f"Found common manager: {manager.get('cn')}")
                return manager

        return None
