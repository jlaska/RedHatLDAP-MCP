# # Copyright (c) 2024 Red Hat LDAP MCP
# # SPDX-License-Identifier: MIT
# #
# # Red Hat LDAP Model Context Protocol (MCP) Server
# # Provides LDAP integration for corporate directory services

"""HTTP server implementation for RedHat LDAP MCP development and testing."""

import argparse
import os

from .config.loader import load_config
from .core.logging import get_logger, setup_logging
from .server import mcp

logger = get_logger(__name__)


def main():
    """Run the MCP server in HTTP mode for development/testing."""
    parser = argparse.ArgumentParser(description="RedHat LDAP MCP HTTP Server")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8814, help="Port to bind to")
    parser.add_argument("--path", default="/redhat-ldap-mcp", help="URL path prefix")

    args = parser.parse_args()

    # Initialize configuration if not already done
    config_path = os.getenv("REDHAT_LDAP_CONFIG", "config/redhat-ldap.json")
    try:
        config = load_config(config_path)
        setup_logging(config.logging)
        logger.info(f"Loaded configuration from {config_path}")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise

    # Start HTTP server
    logger.info(f"Starting HTTP server on {args.host}:{args.port}{args.path}")
    mcp.run(transport="http", host=args.host, port=args.port, path=args.path)


if __name__ == "__main__":
    main()
