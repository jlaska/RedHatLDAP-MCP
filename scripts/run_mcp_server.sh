#!/bin/bash
export REDHAT_LDAP_CONFIG="$PWD/config/redhat-ldap.json"
exec /opt/homebrew/bin/uv run python -m redhat_ldap_mcp.server "$@"
