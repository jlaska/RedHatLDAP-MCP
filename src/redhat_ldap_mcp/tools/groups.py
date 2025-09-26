# # Copyright (c) 2024 Red Hat LDAP MCP
# # SPDX-License-Identifier: MIT
# #
# # Red Hat LDAP Model Context Protocol (MCP) Server
# # Provides LDAP integration for corporate directory services

"""Groups and team membership tool for corporate LDAP directories."""

import re
from typing import Any

from ..core.ldap_connector import LDAPConnector
from ..core.logging import get_logger
from .people_search import PeopleSearchTool

logger = get_logger(__name__)


class GroupsTool:
    """Tool for managing groups and team memberships in LDAP."""

    def __init__(self, connector: LDAPConnector):
        """Initialize the groups tool.

        Args:
            connector: LDAP connector instance
        """
        self.connector = connector
        self.people_tool = PeopleSearchTool(connector)

    def search_groups(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        """
        Search for groups in the directory.

        Args:
            query: Search query (group name or description)
            max_results: Maximum number of results

        Returns:
            List of group dictionaries
        """
        logger.info(f"Searching for groups: '{query}' (max {max_results} results)")

        # Build search filter
        escaped_query = re.sub(r"([*()\\])", r"\\\1", query)
        search_filter = f"""(&(objectClass=group)
                            (|(cn=*{escaped_query}*)
                              (description=*{escaped_query}*)
                              (displayName=*{escaped_query}*)))"""

        # Alternative for different group object classes
        alt_filters = [
            f"(&(objectClass=groupOfNames)(|(cn=*{escaped_query}*)(description=*{escaped_query}*)))",
            f"(&(objectClass=groupOfUniqueNames)(|(cn=*{escaped_query}*)(description=*{escaped_query}*)))",
            f"(&(objectClass=posixGroup)(|(cn=*{escaped_query}*)(description=*{escaped_query}*)))",
        ]

        all_results: list[dict[str, Any]] = []

        for filter_str in [search_filter] + alt_filters:
            try:
                results = self.connector.search(
                    search_base=self._get_groups_search_base(),
                    search_filter=filter_str,
                    attributes=[
                        "cn",
                        "dn",
                        "description",
                        "displayName",
                        "member",
                        "uniqueMember",
                        "memberUid",
                        "gidNumber",
                    ],
                    size_limit=max_results,
                )

                for entry in results:
                    group = self._process_group_entry(entry)
                    if group and not any(g["dn"] == group["dn"] for g in all_results):
                        all_results.append(group)

                if all_results:
                    break  # Found results with this filter

            except Exception as e:
                logger.debug(f"Group search filter failed: {filter_str}, error: {e}")
                continue

        logger.info(f"Found {len(all_results)} groups matching '{query}'")
        return all_results[:max_results]

    def get_person_groups(self, person_id: str) -> list[dict[str, Any]]:
        """
        Get all groups that a person is a member of.

        Args:
            person_id: Person identifier (uid, email, or DN)

        Returns:
            List of group dictionaries
        """
        logger.info(f"Finding groups for person: {person_id}")

        # Get person details to get their DN
        person = self.people_tool.get_person_details(person_id)
        if not person:
            logger.warning(f"Person not found: {person_id}")
            return []

        person_dn = person.get("dn")
        person_uid = person.get("uid")

        if not person_dn:
            logger.warning("Person DN not found")
            return []

        groups = []

        # Search by member DN
        groups.extend(self._search_groups_by_member(person_dn, "member"))
        groups.extend(self._search_groups_by_member(person_dn, "uniqueMember"))

        # Search by uid for POSIX groups
        if person_uid:
            groups.extend(self._search_groups_by_member(person_uid, "memberUid"))

        # Remove duplicates
        unique_groups = []
        seen_dns = set()
        for group in groups:
            if group["dn"] not in seen_dns:
                unique_groups.append(group)
                seen_dns.add(group["dn"])

        logger.info(f"Found {len(unique_groups)} groups for person")
        return unique_groups

    def get_group_members(self, group_name: str) -> list[dict[str, Any]]:
        """
        Get all members of a specific group.

        Args:
            group_name: Group name or DN

        Returns:
            List of member person dictionaries
        """
        logger.info(f"Getting members for group: {group_name}")

        # Find the group first
        if "=" in group_name and "," in group_name:
            # Looks like a DN
            group_dn = group_name
            group_filter = "(objectClass=*)"
        else:
            # Group name, search for it
            groups = self.search_groups(group_name, max_results=1)
            if not groups:
                logger.warning(f"Group not found: {group_name}")
                return []
            group_dn = groups[0]["dn"]
            group_filter = "(objectClass=*)"

        try:
            # Get group details with all member attributes
            results = self.connector.search(
                search_base=group_dn,
                search_filter=group_filter,
                attributes=["member", "uniqueMember", "memberUid"],
                size_limit=1,
            )

            if not results:
                logger.warning(f"Group not found: {group_name}")
                return []

            group_entry = results[0]
            attrs = group_entry.get("attributes", {})

            members = []

            # Process different member attribute types
            for member_attr in ["member", "uniqueMember"]:
                member_dns = attrs.get(member_attr, [])
                if isinstance(member_dns, str):
                    member_dns = [member_dns]

                for member_dn in member_dns:
                    try:
                        person = self.people_tool.get_person_details(member_dn)
                        if person:
                            members.append(person)
                    except Exception as e:
                        logger.debug(f"Could not get member details for {member_dn}: {e}")

            # Process memberUid (POSIX groups)
            member_uids = attrs.get("memberUid", [])
            if isinstance(member_uids, str):
                member_uids = [member_uids]

            for uid in member_uids:
                try:
                    person = self.people_tool.get_person_details(uid)
                    if person and not any(m.get("uid") == uid for m in members):
                        members.append(person)
                except Exception as e:
                    logger.debug(f"Could not get member details for uid {uid}: {e}")

            logger.info(f"Found {len(members)} members in group")
            return members

        except Exception as e:
            logger.error(f"Get group members failed: {e}")
            return []

    def get_group_details(self, group_name: str) -> dict[str, Any] | None:
        """
        Get detailed information about a specific group.

        Args:
            group_name: Group name or DN

        Returns:
            Group dictionary or None if not found
        """
        logger.info(f"Getting group details for: {group_name}")

        if "=" in group_name and "," in group_name:
            # Looks like a DN
            search_base = group_name
            search_filter = "(objectClass=*)"
        else:
            # Group name
            search_base = self._get_groups_search_base()
            search_filter = f"(cn={group_name})"

        try:
            results = self.connector.search(
                search_base=search_base, search_filter=search_filter, attributes=["*"], size_limit=1
            )

            if results:
                group = self._process_group_entry(results[0])
                logger.info(f"Found group: {group.get('cn', 'Unknown')}")
                return group
            else:
                logger.warning(f"Group not found: {group_name}")
                return None

        except Exception as e:
            logger.error(f"Get group details failed: {e}")
            return None

    def _search_groups_by_member(
        self, member_identifier: str, member_attr: str
    ) -> list[dict[str, Any]]:
        """
        Search for groups containing a specific member.

        Args:
            member_identifier: Member DN or UID
            member_attr: Member attribute name (member, uniqueMember, memberUid)

        Returns:
            List of group dictionaries
        """
        search_filter = f"({member_attr}={member_identifier})"

        try:
            results = self.connector.search(
                search_base=self._get_groups_search_base(),
                search_filter=search_filter,
                attributes=[
                    "cn",
                    "dn",
                    "description",
                    "displayName",
                    "member",
                    "uniqueMember",
                    "memberUid",
                ],
            )

            groups = []
            for entry in results:
                group = self._process_group_entry(entry)
                if group:
                    groups.append(group)

            return groups

        except Exception as e:
            logger.debug(f"Search groups by member failed: {e}")
            return []

    def _get_groups_search_base(self) -> str:
        """Get the search base for group searches."""
        # Try to get from schema config first
        if hasattr(self.connector.ldap_config, "schema"):
            schema = self.connector.ldap_config.schema
            if hasattr(schema, "group_search_base"):
                return str(schema.group_search_base)

        # Fall back to common patterns
        base_dn = self.connector.ldap_config.base_dn

        # Try common group containers
        group_containers = ["ou=groups", "ou=adhoc,ou=managedGroups", "cn=groups", "ou=group"]

        for container in group_containers:
            try:
                # Test if this container exists
                test_results = self.connector.search(
                    search_base=f"{container},{base_dn}",
                    search_filter="(objectClass=*)",
                    attributes=["dn"],
                    size_limit=1,
                )
                if test_results:
                    logger.info(f"Using groups search base: {container},{base_dn}")
                    return f"{container},{base_dn}"
            except Exception:
                continue

        # Fall back to base DN
        logger.warning(f"Using base DN for groups search: {base_dn}")
        return base_dn

    def _process_group_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        """
        Process a group LDAP entry into a standardized format.

        Args:
            entry: Raw LDAP entry

        Returns:
            Processed group dictionary
        """
        dn = entry.get("dn", "")
        attrs = entry.get("attributes", {})

        # Count members
        member_count = 0
        members = []

        for member_attr in ["member", "uniqueMember", "memberUid"]:
            member_list = attrs.get(member_attr, [])
            if isinstance(member_list, str):
                member_list = [member_list]
            member_count += len(member_list)
            members.extend(member_list)

        group = {
            "cn": attrs.get("cn"),
            "dn": dn,
            "description": attrs.get("description") or attrs.get("displayName"),
            "member_count": member_count,
            "members": members[:50],  # Limit to first 50 for performance
            "gid_number": attrs.get("gidNumber"),
            "object_classes": entry.get("object_classes", []),
        }

        # Clean up None values
        group = {k: v for k, v in group.items() if v is not None}

        return group
