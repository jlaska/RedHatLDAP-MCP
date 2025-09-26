# RedHat LDAP MCP Server

A specialized Model Context Protocol (MCP) server designed for corporate LDAP directories, with optimizations for Red Hat's LDAP environment and other OpenLDAP-based corporate systems.

## 🎯 Purpose

This MCP server provides read-only access to corporate LDAP directories, enabling AI assistants to:

- Search for people and organizational information
- Navigate corporate hierarchies and reporting structures
- Access contact information and organizational data
- Export directory information for business use

## 🚀 Features

### Corporate LDAP Optimized

- **Anonymous bind support** for read-only corporate directories
- **Red Hat LDAP integration** with rhatPerson schema support
- **Schema auto-detection** for different LDAP environments
- **Corporate hierarchy tools** for org charts and reporting structures

### Read-Only & Secure

- **No modification operations** - purely informational
- **Corporate firewall friendly** - optimized for enterprise networks
- **Flexible authentication** - anonymous, simple, and SASL support planned

### AI Assistant Ready

- **MCP protocol compliance** for Claude, Cursor, and other AI tools
- **Structured responses** with consistent JSON formatting
- **Rich search capabilities** across multiple person attributes
- **Export functionality** for contact lists and org charts

## 🔧 Available MCP Tools

### People Search
- **`search_people`** - Search for people by name, email, uid, department
- **`get_person_details`** - Get detailed information about a specific person

### Organization Charts
- **`get_organization_chart`** - Build hierarchical org charts from any manager
- **`find_manager_chain`** - Get the complete management chain for any person

### Groups & Teams
- **`search_groups`** - Search for groups and teams
- **`get_person_groups`** - Find all groups a person belongs to
- **`get_group_members`** - List all members of a specific group

### Locations & Offices
- **`find_locations`** - Discover office locations and people counts
- **`get_people_at_location`** - Find all colleagues at a specific office

### Utilities
- **`test_connection`** - Test LDAP connectivity and configuration

## 🛠️ Installation

```bash
# Clone the repository
git clone https://github.com/jlaska/RedHatLDAP-MCP.git
cd RedHatLDAP-MCP

# Create virtual environment and install
uv venv
uv pip install -e ".[dev]"
```

## ⚙️ Configuration

Create a configuration file (e.g., `config/redhat-ldap.json`):

```json
{
  "ldap": {
    "server": "ldap://ldap.corp.redhat.com",
    "base_dn": "dc=redhat,dc=com",
    "auth_method": "anonymous",
    "timeout": 30
  },
  "schema": {
    "person_object_class": "rhatPerson",
    "person_search_base": "ou=users,dc=redhat,dc=com",
    "group_search_base": "ou=adhoc,ou=managedGroups,dc=redhat,dc=com",
    "corporate_attributes": [
      "rhatJobTitle", "rhatCostCenter", "rhatLocation",
      "rhatBio", "manager", "rhatGeo"
    ]
  },
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  }
}
```

## 🚀 Usage

### Claude CLI Integration (Recommended)

For the easiest setup with Claude CLI, use the included wrapper script:

```bash
# Add to Claude CLI (from project directory)
claude mcp add redhat-ldap /absolute/path/to/RedHatLDAP-MCP/scripts/run_mcp_server.sh

# Verify connection
claude mcp list

# Use in Claude CLI conversations
claude chat
> What's John Doe's mobile number?
```

The wrapper script automatically configures the environment and uses the local configuration.

### Stdio Mode (for other MCP clients)

```bash
REDHAT_LDAP_CONFIG="config/redhat-ldap.json" uv run python -m redhat_ldap_mcp.server
```

### HTTP Mode (for testing/development)

```bash
REDHAT_LDAP_CONFIG="config/redhat-ldap.json" uv run python -m redhat_ldap_mcp.server_http --host 0.0.0.0 --port 8813
```

## 🔧 MCP Client Configuration

### Claude CLI

```bash
claude mcp add redhat-ldap "scripts/run_mcp_server.sh" -e REDHAT_LDAP_CONFIG=$PWD/config/redhat-ldap.json
```

## 📚 Available Tools

- `search_people` - Find people by name, email, uid, or other attributes
- `get_person_details` - Get detailed information about a specific person
- `get_organization_chart` - Generate hierarchical org charts from any manager
- `find_manager_chain` - Get the complete management chain for any person
- `search_groups` - Search for groups and teams
- `get_person_groups` - Find all groups a person belongs to
- `get_group_members` - List all members of a specific group
- `find_locations` - Discover office locations and people counts
- `get_people_at_location` - Find all colleagues at a specific office
- `test_connection` - Test LDAP connectivity and configuration

## 🧪 Development

```bash
# Run tests
pytest

# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type checking
mypy src/
```

## 📄 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Run the test suite
6. Submit a pull request

## 🙏 Acknowledgments

- Built on the excellent architecture patterns from [ActiveDirectoryMCP](https://github.com/alpadalar/ActiveDirectoryMCP)
- Powered by the [Model Context Protocol](https://github.com/modelcontextprotocol) SDK
- LDAP integration via the [ldap3](https://ldap3.readthedocs.io/) library
