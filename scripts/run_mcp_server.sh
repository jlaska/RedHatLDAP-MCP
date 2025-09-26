#!/bin/bash
cd /Users/jlaska/Projects/RedHatLDAP-MCP || exit
export REDHAT_LDAP_CONFIG="/Users/jlaska/Projects/RedHatLDAP-MCP/config/redhat-ldap.json"
exec /opt/homebrew/bin/uv run python -m redhat_ldap_mcp.server "$@"
