# # Copyright (c) 2024 Red Hat LDAP MCP
# # SPDX-License-Identifier: MIT
# #
# # Red Hat LDAP Model Context Protocol (MCP) Server
# # Provides LDAP integration for corporate directory services

"""People search tool for corporate LDAP directories."""

import re
from typing import Any

from ..core.ldap_connector import LDAPConnector
from ..core.logging import get_logger

logger = get_logger(__name__)


class PeopleSearchTool:
    """Tool for searching and retrieving people information from LDAP."""

    def __init__(self, connector: LDAPConnector):
        """Initialize the people search tool.

        Args:
            connector: LDAP connector instance
        """
        self.connector = connector
        self.config = connector.ldap_config

    def get_person_attributes(self) -> list[str]:
        """
        Get the comprehensive list of attributes to retrieve for person entries.

        Returns:
            List of LDAP attribute names
        """
        # Define base attributes to retrieve
        attributes = [
            "uid",
            "cn",
            "sn",
            "givenName",
            "mail",
            "title",
            "manager",
            "telephoneNumber",
            "mobile",
            "physicalDeliveryOfficeName",
            "l",
            "st",
            "co",
            "employeeNumber",
            "employeeType",
        ]

        # Add schema-specific attributes if available
        if hasattr(self.connector.ldap_config, "schema"):
            schema = self.connector.ldap_config.schema

            # Add corporate attributes
            if hasattr(schema, "corporate_attributes"):
                attributes.extend(schema.corporate_attributes)

            # Add Red Hat specific attributes
            if hasattr(schema, "redhat_attributes"):
                attributes.extend(schema.redhat_attributes)

        return attributes

    def get_person_summary_attributes(self) -> list[str]:
        """
        Get minimal attributes for person summaries to reduce token usage.

        Returns:
            List of essential LDAP attribute names
        """
        return [
            "uid",
            "cn",
            "title",
            "rhatJobTitle",
            "rhatCostCenterDesc",
            "co",  # country
        ]

    def search_people(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        """
        Search for people in the directory.

        Args:
            query: Search query (name, email, uid, etc.)
            max_results: Maximum number of results to return

        Returns:
            List of person dictionaries
        """
        logger.info(f"Searching for people: '{query}' (max {max_results} results)")

        # Build search filter based on query
        search_filter = self._build_search_filter(query)

        # Get comprehensive attributes list
        attributes = self.get_person_attributes()

        try:
            results = self.connector.search(
                search_base=self._get_people_search_base(),
                search_filter=search_filter,
                attributes=attributes,
                size_limit=max_results,
            )

            people = []
            for entry in results:
                person = self._process_person_entry(entry)
                if person:
                    people.append(person)

            logger.info(f"Found {len(people)} people matching '{query}'")
            return people

        except Exception as e:
            logger.error(f"People search failed: {e}")
            raise

    def get_person_details(self, identifier: str) -> dict[str, Any] | None:
        """
        Get detailed information about a specific person.

        Args:
            identifier: Person identifier (uid, email, or DN)

        Returns:
            Person dictionary or None if not found
        """
        logger.info(f"Getting person details for: {identifier}")

        # Determine search filter based on identifier format
        if "@" in identifier:
            # Email address
            search_filter = f"(mail={identifier})"
        elif "=" in identifier and "," in identifier:
            # Looks like a DN, search by exact DN
            search_filter = "(objectClass=person)"
            search_base = identifier
        else:
            # Assume it's a uid
            search_filter = f"(uid={identifier})"

        # Use normal search base unless we have a DN
        search_base = (
            identifier
            if "=" in identifier and "," in identifier
            else self._get_people_search_base()
        )

        try:
            results = self.connector.search(
                search_base=search_base,
                search_filter=search_filter,
                attributes=["*"],  # Get all attributes
                size_limit=1,
            )

            if results:
                person = self._process_person_entry(results[0])
                logger.info(f"Found person: {person.get('cn', 'Unknown')}")
                return person
            else:
                logger.warning(f"No person found for identifier: {identifier}")
                return None

        except Exception as e:
            logger.error(f"Get person details failed: {e}")
            raise

    def _build_search_filter(self, query: str) -> str:
        """
        Build LDAP search filter based on query.

        Args:
            query: Search query

        Returns:
            LDAP filter string
        """
        # Escape special LDAP characters
        escaped_query = re.sub(r"([*()\\])", r"\\\1", query)

        logger.debug(f"Building search filter for query: '{query}' -> escaped: '{escaped_query}'")

        # Check if it looks like an email
        if "@" in query:
            return f"(&(objectClass=person)(mail=*{escaped_query}*))"

        # Check if it looks like a uid (no spaces, alphanumeric)
        if " " not in query and query.replace(".", "").replace("-", "").replace("_", "").isalnum():
            return f"(&(objectClass=person)(|(uid=*{escaped_query}*)(cn=*{escaped_query}*)))"

        # General name search
        parts = escaped_query.split()
        if len(parts) == 1:
            # Single term - search in multiple fields
            term = parts[0]
            return (
                f"(&(objectClass=person)(|(cn=*{term}*)(givenName=*{term}*)"
                f"(sn=*{term}*)(uid=*{term}*)(mail=*{term}*)(title=*{term}*)"
                f"(rhatCostCenterDesc=*{term}*)))"
            )
        elif len(parts) == 2:
            # Two terms - likely first and last name
            first, last = parts
            # Use simple CN search for two names - more reliable than complex OR logic
            search_filter = f"(&(objectClass=person)(cn=*{escaped_query}*))"
            logger.debug(f"Generated two-part filter: {search_filter}")
            return search_filter
        else:
            # Multiple terms - search in common name
            return f"(&(objectClass=person)(cn=*{escaped_query}*))"

    def _get_people_search_base(self) -> str:
        """Get the search base for people searches."""
        # Try to get from schema config first
        if hasattr(self.connector.ldap_config, "schema"):
            schema = self.connector.ldap_config.schema
            if hasattr(schema, "person_search_base"):
                return schema.person_search_base

        # Fall back to common patterns
        base_dn = self.config.base_dn

        # Try common people containers
        people_containers = ["ou=users", "ou=people", "cn=users"]
        for container in people_containers:
            try:
                # Test if this container exists
                test_results = self.connector.search(
                    search_base=f"{container},{base_dn}",
                    search_filter="(objectClass=*)",
                    attributes=["dn"],
                    size_limit=1,
                )
                if test_results:
                    logger.info(f"Using people search base: {container},{base_dn}")
                    return f"{container},{base_dn}"
            except Exception:
                continue

        # Fall back to base DN
        logger.warning(f"Using base DN for people search: {base_dn}")
        return base_dn

    def _process_person_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        """
        Process a person LDAP entry into a standardized format.

        Args:
            entry: Raw LDAP entry

        Returns:
            Processed person dictionary
        """
        dn = entry.get("dn", "")
        attrs = entry.get("attributes", {})

        # Extract uid from DN if not in attributes
        uid = attrs.get("uid")
        if not uid and dn:
            uid_match = re.search(r"uid=([^,]+)", dn)
            if uid_match:
                uid = uid_match.group(1)

        # Build standardized person object
        person = {
            "uid": uid,
            "dn": dn,
            "cn": attrs.get("cn"),
            "display_name": attrs.get("displayName"),
            "given_name": attrs.get("givenName"),
            "surname": attrs.get("sn"),
            "mail": attrs.get("mail"),
            "title": attrs.get("title") or attrs.get("rhatJobTitle"),
            "department": attrs.get("rhatCostCenterDesc"),
            "manager": attrs.get("manager"),
            "phone": attrs.get("telephoneNumber"),
            "mobile": attrs.get("mobile"),
            "office_location": (
                attrs.get("physicalDeliveryOfficeName")
                or attrs.get("rhatLocation")
                or attrs.get("l")  # locality
            ),
            "city": attrs.get("l"),
            "state": attrs.get("st"),
            "country": attrs.get("co"),
            "employee_id": attrs.get("employeeNumber") or attrs.get("rhatWorkerId"),
            "employee_type": attrs.get("employeeType") or attrs.get("rhatPersonType"),
            "cost_center": attrs.get("rhatCostCenter"),
            # Red Hat specific fields
            "rhat_job_title": attrs.get("rhatJobTitle"),
            "rhat_cost_center": attrs.get("rhatCostCenter"),
            "rhat_cost_center_desc": attrs.get("rhatCostCenterDesc"),
            "rhat_location": attrs.get("rhatLocation"),
            "rhat_bio": attrs.get("rhatBio"),
            "rhat_geo": attrs.get("rhatGeo"),
            "rhat_organization": attrs.get("rhatOrganization"),
            "rhat_job_role": attrs.get("rhatJobRole"),
            "rhat_team_lead": attrs.get("rhatTeamLead"),
            "rhat_original_hire_date": self._format_date(attrs.get("rhatOriginalHireDate")),
            "rhat_hire_date": self._format_date(attrs.get("rhatHireDate")),
            "rhat_worker_id": self._format_value(attrs.get("rhatWorkerId")),
            "rhat_building_code": attrs.get("rhatBuildingCode"),
            "rhat_office_location": attrs.get("rhatOfficeLocation"),
        }

        # Clean up None values and empty strings
        person = {k: v for k, v in person.items() if v}

        return person

    def _process_person_summary(self, entry: dict[str, Any]) -> dict[str, Any]:
        """
        Process a person LDAP entry into a lightweight summary format.

        Args:
            entry: Raw LDAP entry

        Returns:
            Processed person summary dictionary
        """
        dn = entry.get("dn", "")
        attrs = entry.get("attributes", {})

        # Extract uid from DN if not in attributes
        uid = attrs.get("uid")
        if not uid and dn:
            uid_match = re.search(r"uid=([^,]+)", dn)
            if uid_match:
                uid = uid_match.group(1)

        # Build lightweight person summary
        summary = {
            "uid": uid,
            "cn": attrs.get("cn"),
            "title": attrs.get("title") or attrs.get("rhatJobTitle"),
            "department": attrs.get("rhatCostCenterDesc"),
            "country": attrs.get("co"),
        }

        # Clean up None values and empty strings
        summary = {k: v for k, v in summary.items() if v}

        return summary

    def _format_date(self, date_value: Any) -> str | None:
        """Format date value to string."""
        if date_value is None:
            return None

        # Handle datetime objects
        if hasattr(date_value, "strftime"):
            return date_value.strftime("%Y-%m-%d")

        # Handle string values
        if isinstance(date_value, str):
            return date_value

        # Convert other types to string
        return str(date_value)

    def _format_value(self, value: Any) -> str | None:
        """Format any value to string."""
        if value is None:
            return None

        # Convert to string
        return str(value)
