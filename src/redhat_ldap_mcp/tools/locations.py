# # Copyright (c) 2024 Red Hat LDAP MCP
# # SPDX-License-Identifier: MIT
# #
# # Red Hat LDAP Model Context Protocol (MCP) Server
# # Provides LDAP integration for corporate directory services

"""Locations and office directory tool for corporate LDAP directories."""

import re
from collections import defaultdict
from typing import Any

from ..core.ldap_connector import LDAPConnector
from ..core.logging import get_logger
from .people_search import PeopleSearchTool

logger = get_logger(__name__)


class LocationsTool:
    """Tool for finding office locations and people at those locations."""

    def __init__(self, connector: LDAPConnector):
        """Initialize the locations tool.

        Args:
            connector: LDAP connector instance
        """
        self.connector = connector
        self.people_tool = PeopleSearchTool(connector)

    def find_locations(self, query: str | None = None) -> list[dict[str, Any]]:
        """
        Find office locations and people counts.

        Args:
            query: Optional location search query

        Returns:
            List of location dictionaries with people counts
        """
        logger.info(f"Finding locations with query: {query}")

        # Get all people with location information
        location_attrs = [
            "physicalDeliveryOfficeName",
            "rhatLocation",
            "l",
            "st",
            "co",
            "postalAddress",
            "street",
        ]

        search_filter = "(objectClass=person)"
        if query:
            escaped_query = re.sub(r"([*()\\])", r"\\\1", query)
            location_filters = [
                f"(physicalDeliveryOfficeName=*{escaped_query}*)",
                f"(rhatLocation=*{escaped_query}*)",
                f"(l=*{escaped_query}*)",
                f"(st=*{escaped_query}*)",
                f"(co=*{escaped_query}*)",
            ]
            search_filter = f"(&(objectClass=person)(|{''.join(location_filters)}))"

        try:
            results = self.connector.search(
                search_base=self.people_tool._get_people_search_base(),
                search_filter=search_filter,
                attributes=["uid", "cn"] + location_attrs,
            )

            # Group people by location
            location_counts: dict[str, dict[str, Any]] = defaultdict(
                lambda: {"people": [], "cities": set(), "states": set(), "countries": set()}
            )

            for entry in results:
                attrs = entry.get("attributes", {})
                person_uid = attrs.get("uid")
                person_cn = attrs.get("cn")

                if not person_uid:
                    continue

                # Extract location information
                office = (
                    attrs.get("physicalDeliveryOfficeName")
                    or attrs.get("rhatLocation")
                    or attrs.get("l")
                )

                if office:
                    people_list = location_counts[office]["people"]
                    if isinstance(people_list, list):
                        people_list.append({"uid": person_uid, "cn": person_cn})

                    # Add geographic information
                    city = attrs.get("l")
                    state = attrs.get("st")
                    country = attrs.get("co")

                    if city:
                        cities_set = location_counts[office]["cities"]
                        if hasattr(cities_set, "add"):
                            cities_set.add(city)
                    if state:
                        states_set = location_counts[office]["states"]
                        if hasattr(states_set, "add"):
                            states_set.add(state)
                    if country:
                        countries_set = location_counts[office]["countries"]
                        if hasattr(countries_set, "add"):
                            countries_set.add(country)

            # Convert to location list
            locations = []
            for location_name, data in location_counts.items():
                if not location_name:
                    continue

                location_info = {
                    "name": location_name,
                    "people_count": len(data["people"]),
                    "city": ", ".join(sorted(data["cities"])) if data["cities"] else None,
                    "state": ", ".join(sorted(data["states"])) if data["states"] else None,
                    "country": ", ".join(sorted(data["countries"])) if data["countries"] else None,
                }

                # Clean up None values
                location_info = {k: v for k, v in location_info.items() if v}
                locations.append(location_info)

            # Sort by people count (descending)
            locations.sort(key=lambda x: x.get("people_count", 0), reverse=True)  # type: ignore[return-value,arg-type]

            logger.info(f"Found {len(locations)} locations")
            return locations

        except Exception as e:
            logger.error(f"Location search failed: {e}")
            return []

    def get_people_at_location(self, location: str, max_results: int = 50) -> list[dict[str, Any]]:
        """
        Get all people at a specific location.

        Args:
            location: Location name
            max_results: Maximum number of results

        Returns:
            List of person dictionaries
        """
        logger.info(f"Getting people at location: {location}")

        escaped_location = re.sub(r"([*()\\])", r"\\\1", location)

        # Search for people at this location
        search_filter = f"""(&(objectClass=person)
                            (|(physicalDeliveryOfficeName=*{escaped_location}*)
                              (rhatLocation=*{escaped_location}*)
                              (l=*{escaped_location}*)))"""

        try:
            results = self.connector.search(
                search_base=self.people_tool._get_people_search_base(),
                search_filter=search_filter,
                attributes=[
                    "uid",
                    "cn",
                    "sn",
                    "givenName",
                    "mail",
                    "title",
                    "department",
                    "telephoneNumber",
                    "physicalDeliveryOfficeName",
                    "rhatLocation",
                    "l",
                    "st",
                    "co",
                ],
                size_limit=max_results,
            )

            people = []
            for entry in results:
                person = self.people_tool._process_person_entry(entry)
                if person:
                    people.append(person)

            # Sort by name
            people.sort(key=lambda x: x.get("cn", ""))

            logger.info(f"Found {len(people)} people at location '{location}'")
            return people

        except Exception as e:
            logger.error(f"People at location search failed: {e}")
            return []

    def get_location_hierarchy(self) -> dict[str, Any]:
        """
        Get a hierarchical view of locations (country -> state -> city -> office).

        Returns:
            Hierarchical location structure
        """
        logger.info("Building location hierarchy")

        try:
            results = self.connector.search(
                search_base=self.people_tool._get_people_search_base(),
                search_filter="(objectClass=person)",
                attributes=["uid", "physicalDeliveryOfficeName", "rhatLocation", "l", "st", "co"],
            )

            # Build hierarchy
            hierarchy: dict[str, Any] = defaultdict(
                lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
            )

            for entry in results:
                attrs = entry.get("attributes", {})

                country = attrs.get("co", "Unknown")
                state = attrs.get("st", "Unknown")
                city = attrs.get("l", "Unknown")
                office = (
                    attrs.get("physicalDeliveryOfficeName")
                    or attrs.get("rhatLocation")
                    or "Unknown"
                )

                hierarchy[country][state][city][office] += 1

            # Convert to regular dict for JSON serialization
            result: dict[str, Any] = {}
            for country, states in hierarchy.items():
                result[country] = {}
                for state, cities in states.items():
                    result[country][state] = {}
                    for city, offices in cities.items():
                        result[country][state][city] = dict(offices)

            logger.info("Built location hierarchy")
            return result

        except Exception as e:
            logger.error(f"Location hierarchy build failed: {e}")
            return {}

    def find_nearest_colleagues(
        self, person_id: str, max_results: int = 10
    ) -> list[dict[str, Any]]:
        """
        Find colleagues in the same location as a person.

        Args:
            person_id: Person identifier
            max_results: Maximum number of results

        Returns:
            List of colleague dictionaries
        """
        logger.info(f"Finding colleagues near: {person_id}")

        # Get person's location
        person = self.people_tool.get_person_details(person_id)
        if not person:
            logger.warning(f"Person not found: {person_id}")
            return []

        person_location = person.get("office_location")
        if not person_location:
            logger.warning(f"No location found for person: {person_id}")
            return []

        # Find other people at the same location
        colleagues = self.get_people_at_location(person_location, max_results + 1)

        # Remove the person themselves from the results
        colleagues = [
            colleague for colleague in colleagues if colleague.get("uid") != person.get("uid")
        ]

        return colleagues[:max_results]

    def get_location_stats(self) -> dict[str, Any]:
        """
        Get statistics about office locations.

        Returns:
            Location statistics
        """
        logger.info("Calculating location statistics")

        locations = self.find_locations()

        if not locations:
            return {}

        total_people = sum(loc["people_count"] for loc in locations)

        stats = {
            "total_locations": len(locations),
            "total_people_with_location": total_people,
            "largest_location": (
                max(locations, key=lambda x: x["people_count"]) if locations else None
            ),
            "average_people_per_location": total_people / len(locations) if locations else 0,
            "locations_by_size": {
                "large": len([loc for loc in locations if loc["people_count"] >= 100]),
                "medium": len([loc for loc in locations if 20 <= loc["people_count"] < 100]),
                "small": len([loc for loc in locations if loc["people_count"] < 20]),
            },
        }

        logger.info("Calculated location statistics")
        return stats
