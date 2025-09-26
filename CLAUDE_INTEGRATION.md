# Claude CLI Integration Guide

This guide explains how to integrate the RedHat LDAP MCP server with Claude CLI using the `claude mcp add` command.

## Prerequisites

1. **Claude CLI installed** - Get it from [Claude CLI](https://github.com/anthropics/claude-cli)
2. **Python 3.10+** with uv package manager
3. **Access to your corporate LDAP server**

## Quick Start

### Option 1: Install from Local Development

If you have the repository locally:

```bash
# Navigate to the project directory
cd /path/to/RedHatLDAP-MCP

# Install the package in development mode
uv pip install -e .

# Add to Claude CLI
claude mcp add redhat-ldap \
  --module redhat_ldap_mcp.server \
  --env REDHAT_LDAP_CONFIG="/path/to/RedHatLDAP-MCP/config/redhat-ldap.json"
```

### Option 2: Install from Git Repository

```bash
# Add directly from Git repository
claude mcp add redhat-ldap \
  --module redhat_ldap_mcp.server \
  --package "redhat-ldap-mcp @ git+https://github.com/jlaska/RedHatLDAP-MCP.git" \
  --env REDHAT_LDAP_CONFIG="/path/to/your/redhat-ldap-config.json"
```

## Configuration

### 1. Create Configuration File

Create a configuration file for your LDAP environment:

```bash
mkdir -p ~/.config/redhat-ldap-mcp
```

Create `~/.config/redhat-ldap-mcp/config.json`:

```json
{
  "ldap": {
    "server": "ldap://your-ldap-server.corp.com",
    "base_dn": "dc=corp,dc=com",
    "auth_method": "anonymous",
    "timeout": 30,
    "receive_timeout": 10,
    "use_ssl": false
  },
  "schema": {
    "person_object_class": "person",
    "group_object_class": "groupOfNames",
    "person_search_base": "ou=users,dc=corp,dc=com",
    "group_search_base": "ou=groups,dc=corp,dc=com",
    "corporate_attributes": [
      "uid", "cn", "mail", "givenName", "sn", "displayName",
      "telephoneNumber", "manager", "title", "department",
      "employeeNumber", "employeeType"
    ],
    "search_fields": {
      "person": ["uid", "cn", "mail", "displayName", "givenName", "sn"],
      "group": ["cn", "description"]
    }
  },
  "security": {
    "enable_tls": false,
    "validate_certificate": false,
    "require_secure_connection": false
  },
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  },
  "performance": {
    "max_retries": 3,
    "retry_delay": 1.0,
    "page_size": 100,
    "max_results": 1000,
    "cache_timeout": 300
  },
  "export": {
    "formats": ["json", "csv"],
    "max_export_size": 5000,
    "include_sensitive": false,
    "sensitive_attributes": ["userPassword"]
  }
}
```

### 2. Red Hat LDAP Specific Configuration

For Red Hat corporate LDAP, use this configuration:

```json
{
  "ldap": {
    "server": "ldap://ldap.corp.redhat.com",
    "base_dn": "dc=redhat,dc=com",
    "auth_method": "anonymous",
    "timeout": 30,
    "receive_timeout": 10,
    "use_ssl": false
  },
  "schema": {
    "person_object_class": "rhatPerson",
    "group_object_class": "groupOfNames",
    "person_search_base": "ou=users,dc=redhat,dc=com",
    "group_search_base": "ou=adhoc,ou=managedGroups,dc=redhat,dc=com",
    "corporate_attributes": [
      "uid", "cn", "mail", "givenName", "sn", "displayName",
      "telephoneNumber", "manager", "title", "rhatCostCenterDesc",
      "employeeNumber", "employeeType"
    ],
    "redhat_attributes": [
      "rhatJobTitle", "rhatCostCenter", "rhatLocation", "rhatBio",
      "rhatGeo", "rhatOrganization", "rhatJobRole", "rhatTeamLead",
      "rhatOriginalHireDate", "rhatHireDate", "rhatWorkerId",
      "rhatCostCenterDesc", "rhatBuildingCode", "rhatOfficeLocation"
    ],
    "search_fields": {
      "person": ["uid", "cn", "mail", "displayName", "givenName", "sn"],
      "group": ["cn", "description"]
    }
  },
  "security": {
    "enable_tls": false,
    "validate_certificate": false,
    "require_secure_connection": false
  },
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  },
  "performance": {
    "max_retries": 3,
    "retry_delay": 1.0,
    "page_size": 100,
    "max_results": 1000,
    "cache_timeout": 300
  },
  "export": {
    "formats": ["json", "csv"],
    "max_export_size": 5000,
    "include_sensitive": false,
    "sensitive_attributes": ["userPassword"]
  }
}
```

### 3. Add to Claude CLI

```bash
claude mcp add redhat-ldap \
  --module redhat_ldap_mcp.server \
  --package "redhat-ldap-mcp @ git+https://github.com/jlaska/RedHatLDAP-MCP.git" \
  --env REDHAT_LDAP_CONFIG="$HOME/.config/redhat-ldap-mcp/config.json"
```

## Available Tools

Once configured, you'll have access to these LDAP tools in Claude:

### People & Organization
- **search_people** - Search for people by name, email, or uid
- **get_person_details** - Get detailed information about a specific person
- **get_manager_chain** - Get the management hierarchy for a person
- **find_direct_reports** - Find people who report to a specific manager
- **get_team_members** - Get all members of a team under a manager

### Groups & Locations
- **search_groups** - Search for LDAP groups
- **get_group_members** - Get members of a specific group
- **get_person_groups** - Get groups that a person belongs to
- **find_locations** - Find all office locations
- **get_location_details** - Get details about a specific location

### Administration
- **test_ldap_connection** - Test LDAP server connectivity
- **export_search_results** - Export search results to JSON/CSV

## Usage Examples

After integration, you can use these tools in Claude:

```
"Find my manager chain"
"Who are the people in the Boston office?"
"Search for John Smith in the directory"
"What groups is alice@company.com a member of?"
"Export all people in the Engineering department to CSV"
```

## Troubleshooting

### Connection Issues
1. Verify LDAP server URL and port
2. Check network connectivity to LDAP server
3. Ensure proper authentication method
4. Review firewall settings

### Configuration Issues
1. Validate JSON syntax in config file
2. Check file permissions on config file
3. Verify LDAP schema attributes match your directory
4. Test with minimal configuration first

### Testing Your Setup

Test the configuration manually:

```bash
# Navigate to project directory
cd /path/to/RedHatLDAP-MCP

# Test connection
uv run python -c "
from redhat_ldap_mcp.config.loader import load_config
from redhat_ldap_mcp.core.ldap_connector import LDAPConnector

config = load_config('$HOME/.config/redhat-ldap-mcp/config.json')
connector = LDAPConnector(config.ldap, config.security, config.performance)
result = connector.test_connection()
print('Connection test:', result)
"
```

## Security Notes

- Use anonymous bind only for read-only corporate directories
- For write operations, configure proper authentication
- Consider using TLS for production environments
- Exclude sensitive attributes in export configurations
- Regularly review access logs

## Support

For issues and feature requests, visit: https://github.com/jlaska/RedHatLDAP-MCP/issues
