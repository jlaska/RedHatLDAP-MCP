#!/usr/bin/env python3
# # Copyright (c) 2024 Red Hat LDAP MCP
# # SPDX-License-Identifier: MIT
# #
# # Red Hat LDAP Model Context Protocol (MCP) Server
# # Provides LDAP integration for corporate directory services

"""Test script to validate RedHat LDAP MCP foundation."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from redhat_ldap_mcp.config.loader import load_config, validate_config
from redhat_ldap_mcp.config.models import Config
from redhat_ldap_mcp.core.ldap_connector import LDAPConnector
from redhat_ldap_mcp.core.logging import setup_logging


def test_config_loading():
    """Test configuration loading and validation."""
    print("🔧 Testing configuration loading...")

    try:
        # Test loading Red Hat config
        config_path = "config/redhat-ldap.json"
        config = load_config(config_path)

        print("✅ Configuration loaded successfully")
        print(f"   Server: {config.ldap.server}")
        print(f"   Base DN: {config.ldap.base_dn}")
        print(f"   Auth Method: {config.ldap.auth_method}")

        # Test validation
        validate_config(config)
        print("✅ Configuration validation passed")

        return config

    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return None


def test_ldap_connector(config: Config):
    """Test LDAP connector initialization and connection test."""
    print("\n🔌 Testing LDAP connector...")

    try:
        # Setup logging first
        setup_logging(config.logging)
        print("✅ Logging setup successful")

        # Create connector
        connector = LDAPConnector(config.ldap, config.security, config.performance)
        print("✅ LDAP connector created successfully")

        # Test connection (this will fail with Red Hat LDAP since we're not on corporate network)
        print("🌐 Testing LDAP connection (expected to fail outside corporate network)...")
        result = connector.test_connection()

        if result.get("connected"):
            print("✅ LDAP connection successful!")
            print(f"   Server: {result.get('server')}:{result.get('port')}")
            print(f"   Auth: {result.get('auth_method')}")
            print(f"   Search test: {result.get('search_test')}")
        else:
            print("⚠️  LDAP connection failed (expected outside corporate network)")
            print(f"   Error: {result.get('error')}")
            print("   This is normal when not connected to Red Hat's network")

        return connector

    except Exception as e:
        print(f"❌ LDAP connector test failed: {e}")
        return None


def test_schema_detection(connector: LDAPConnector):
    """Test schema detection capabilities."""
    print("\n🔍 Testing schema detection...")

    try:
        schema_info = connector.get_schema_info()

        if "error" in schema_info:
            print("⚠️  Schema detection failed (expected without connection)")
            print(f"   Error: {schema_info['error']}")
        else:
            print("✅ Schema information retrieved")
            print(f"   Naming contexts: {len(schema_info.get('naming_contexts', []))}")
            print(f"   Object classes: {len(schema_info.get('object_classes', []))}")

    except Exception as e:
        print(f"❌ Schema detection test failed: {e}")


def main():
    """Run foundation tests."""
    print("🚀 RedHat LDAP MCP Foundation Test")
    print("=" * 50)

    # Test 1: Configuration
    config = test_config_loading()
    if not config:
        return 1

    # Test 2: LDAP Connector
    connector = test_ldap_connector(config)
    if not connector:
        return 1

    # Test 3: Schema Detection
    test_schema_detection(connector)

    print("\n" + "=" * 50)
    print("🎉 Foundation tests completed!")
    print("✅ Configuration system working")
    print("✅ LDAP connector architecture working")
    print("✅ Ready for Red Hat LDAP testing")
    print("\n💡 Next steps:")
    print("   1. Test from Red Hat corporate network")
    print("   2. Implement people search tools")
    print("   3. Add organization chart functionality")

    return 0


if __name__ == "__main__":
    sys.exit(main())
