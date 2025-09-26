#!/usr/bin/env python3
# # Copyright (c) 2024 Red Hat LDAP MCP
# # SPDX-License-Identifier: MIT
# #
# # Red Hat LDAP Model Context Protocol (MCP) Server
# # Provides LDAP integration for corporate directory services

"""
Test script for validating RedHat LDAP MCP with actual Red Hat LDAP environment.
"""

import sys

from redhat_ldap_mcp.config.loader import load_config
from redhat_ldap_mcp.core.ldap_connector import LDAPConnector
from redhat_ldap_mcp.tools.groups import GroupsTool
from redhat_ldap_mcp.tools.locations import LocationsTool
from redhat_ldap_mcp.tools.organization import OrganizationTool
from redhat_ldap_mcp.tools.people_search import PeopleSearchTool


def test_ldap_connection():
    """Test basic LDAP connection."""
    print("🔗 Testing LDAP Connection...")

    try:
        config = load_config("config/redhat-ldap.json")
        connector = LDAPConnector(config.ldap, config.security, config.performance)

        # Test connection
        result = connector.test_connection()
        print(f"   ✅ Connection: {result}")

        return connector
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return None


def check_people_search(connector):
    """Test people search functionality."""
    print("\n👥 Testing People Search...")

    try:
        tool = PeopleSearchTool(connector)

        # Search for your own account
        print("   Searching for 'jlaska'...")
        results = tool.search_people("jlaska", max_results=5)
        print(f"   ✅ Found {len(results)} people")

        if results:
            person = results[0]
            print(
                f"   📝 First result: {person.get('cn', 'Unknown')} ({person.get('uid', 'No UID')})"
            )

            # Test getting detailed info
            details = tool.get_person_details("jlaska")
            if details:
                mail = details.get("mail", "No email")
                location = details.get("office_location", "Unknown location")
                print(f"   📋 Details: {mail} at {location}")

        return True
    except Exception as e:
        print(f"   ❌ People search failed: {e}")
        return False


def check_organization_tools(connector):
    """Test organization tools."""
    print("\n🏢 Testing Organization Tools...")

    try:
        tool = OrganizationTool(connector)

        # Test finding your manager chain
        print("   Finding manager chain for 'jlaska'...")
        managers = tool.get_manager_chain("jlaska")
        print(f"   ✅ Found {len(managers)} managers in chain")

        for i, manager in enumerate(managers):
            name = manager.get("cn", "Unknown")
            uid = manager.get("uid", "No UID")
            print(f"   📊 Level {i+1}: {name} ({uid})")

        return True
    except Exception as e:
        print(f"   ❌ Organization tools failed: {e}")
        return False


def check_groups_tools(connector):
    """Test groups functionality."""
    print("\n👫 Testing Groups Tools...")

    try:
        tool = GroupsTool(connector)

        # Find groups for jlaska
        print("   Finding groups for 'jlaska'...")
        groups = tool.get_person_groups("jlaska")
        print(f"   ✅ Found {len(groups)} groups")

        for group in groups[:3]:  # Show first 3 groups
            name = group.get("cn", "Unknown")
            count = group.get("member_count", 0)
            print(f"   🏷️  Group: {name} ({count} members)")

        return True
    except Exception as e:
        print(f"   ❌ Groups tools failed: {e}")
        return False


def check_locations_tools(connector):
    """Test locations functionality."""
    print("\n📍 Testing Locations Tools...")

    try:
        tool = LocationsTool(connector)

        # Find locations
        print("   Finding all locations...")
        locations = tool.find_locations()
        print(f"   ✅ Found {len(locations)} locations")

        for location in locations[:5]:  # Show first 5 locations
            name = location.get("name", "Unknown")
            count = location.get("people_count", 0)
            print(f"   🏢 Location: {name} ({count} people)")

        return True
    except Exception as e:
        print(f"   ❌ Locations tools failed: {e}")
        return False


def main():
    """Main test function."""
    print("🚀 RedHat LDAP MCP - Real Environment Test")
    print("=" * 50)

    # Test connection
    connector = test_ldap_connection()
    if not connector:
        print("\n❌ Cannot proceed without LDAP connection")
        sys.exit(1)

    # Test all tools
    tests = [
        check_people_search,
        check_organization_tools,
        check_groups_tools,
        check_locations_tools,
    ]

    passed = 0
    for test_func in tests:
        try:
            if test_func(connector):
                passed += 1
        except Exception as e:
            print(f"   ❌ Test {test_func.__name__} crashed: {e}")

    print(f"\n📊 Test Summary: {passed}/{len(tests)} tests passed")

    if passed == len(tests):
        print("🎉 All tests passed! RedHat LDAP MCP is working correctly!")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

    # Cleanup
    connector.disconnect()


if __name__ == "__main__":
    main()
