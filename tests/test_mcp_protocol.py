#!/usr/bin/env python3
# # Copyright (c) 2024 Red Hat LDAP MCP
# # SPDX-License-Identifier: MIT
# #
# # Red Hat LDAP Model Context Protocol (MCP) Server
# # Provides LDAP integration for corporate directory services

"""Test MCP protocol communication with RedHat LDAP MCP server."""

import json
import os
import subprocess
import sys


def test_mcp_server():
    """Test MCP server protocol communication."""
    print("🔍 Testing MCP Protocol Communication...")

    # Set environment
    env = os.environ.copy()
    env["REDHAT_LDAP_CONFIG"] = "/Users/jlaska/Projects/RedHatLDAP-MCP/config/redhat-ldap.json"

    # Start server process
    cmd = [
        "uv",
        "run",
        "--with",
        "redhat-ldap-mcp @ git+https://github.com/jlaska/RedHatLDAP-MCP.git",
        "python",
        "-m",
        "redhat_ldap_mcp.server",
    ]

    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        # Test 1: Initialize
        print("   📤 Sending initialize request...")
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }

        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()

        # Read response
        response_line = process.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            if "result" in response:
                server_info = response["result"]["serverInfo"]
                print(f"   ✅ Server initialized: {server_info['name']} v{server_info['version']}")
            else:
                print(f"   ❌ Initialize failed: {response}")
                return False

        # Test 2: List tools
        print("   📤 Sending tools/list request...")
        tools_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

        process.stdin.write(json.dumps(tools_request) + "\n")
        process.stdin.flush()

        # Read response
        response_line = process.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            if "result" in response and "tools" in response["result"]:
                tools = response["result"]["tools"]
                print(f"   ✅ Found {len(tools)} tools:")
                for tool in tools[:5]:  # Show first 5 tools
                    print(f"      - {tool['name']}: {tool['description']}")
                if len(tools) > 5:
                    print(f"      ... and {len(tools) - 5} more tools")
            else:
                print(f"   ❌ Tools list failed: {response}")
                return False

        # Test 3: Call a tool
        print("   📤 Testing search_people tool...")
        tool_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "search_people", "arguments": {"query": "jlaska", "max_results": 1}},
        }

        process.stdin.write(json.dumps(tool_request) + "\n")
        process.stdin.flush()

        # Read response
        response_line = process.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            if "result" in response:
                content = response["result"]["content"]
                if content and len(content) > 0:
                    result_text = content[0]["text"]
                    print("   ✅ Tool call successful!")
                    if "jlaska" in result_text.lower():
                        print("   ✅ Found user data in response")
                    else:
                        print("   ⚠️  Response doesn't contain expected user data")
                else:
                    print("   ❌ Empty tool response")
            else:
                print(f"   ❌ Tool call failed: {response}")
                return False

        process.terminate()
        process.wait()

        print("   🎉 All MCP protocol tests passed!")
        return True

    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        if "process" in locals():
            process.terminate()
        return False


if __name__ == "__main__":
    success = test_mcp_server()
    sys.exit(0 if success else 1)
