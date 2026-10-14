"""Moved. The GroundLens MCP server ships inside the groundlens package.

    pip install "groundlens[mcp]"
    groundlens-mcp

This package exists only so that anyone who still runs the old
``groundlens-mcp`` package gets a sentence telling them where the server went,
instead of a stack trace.
"""

from __future__ import annotations

import sys

__version__ = "3.0.2"

MESSAGE = """\
The groundlens-mcp package is retired. The GroundLens MCP server now ships
inside the groundlens package, with three tools: verify_answer, verify_run
and verify_records.

    pip install "groundlens[mcp]"
    groundlens-mcp

In your MCP client configuration, use

    "command": "groundlens-mcp"

or, with uv and nothing installed,

    "command": "uvx", "args": ["--from", "groundlens[mcp]", "groundlens-mcp"]

https://github.com/groundlens-dev/groundlens
"""


def main() -> int:
    """Print where the connector went and exit non-zero.

    stderr, never stdout: an MCP client speaks the protocol over stdout, and a
    tombstone that writes there would look like a malformed message rather than
    a message.
    """
    print(MESSAGE, file=sys.stderr)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
