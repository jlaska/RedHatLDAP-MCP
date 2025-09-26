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

### Stdio Mode (for MCP clients)

```bash
REDHAT_LDAP_CONFIG="config/redhat-ldap.json" uv run python -m redhat_ldap_mcp.server
```

### HTTP Mode (for testing/development)

```bash
REDHAT_LDAP_CONFIG="config/redhat-ldap.json" uv run python -m redhat_ldap_mcp.server_http --host 0.0.0.0 --port 8813
```

## 🔧 MCP Client Configuration

### Claude Desktop / Cursor

```json
{
  "mcpServers": {
    "redhat-ldap": {
      "command": "uv",
      "args": ["run", "python", "-m", "redhat_ldap_mcp.server"],
      "cwd": "/path/to/RedHatLDAP-MCP",
      "env": {
        "REDHAT_LDAP_CONFIG": "/path/to/config/redhat-ldap.json"
      }
    }
  }
}
```

## 📚 Available Tools

- `search_people` - Find people by name, email, or other attributes
- `lookup_person` - Get detailed information about a specific person
- `get_org_chart` - Generate organizational hierarchy charts
- `find_by_manager` - Find direct reports for a manager
- `search_by_location` - Find people by office or geographic location
- `get_cost_centers` - List organizational cost centers
- `export_contacts` - Export contact information in various formats

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
