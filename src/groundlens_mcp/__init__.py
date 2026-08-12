"""Deprecated. The groundlens MCP connector now ships inside groundlens itself.

    pip install "groundlens[encoder,mcp]"
    python -m groundlens.mcp

This package exists only so that anyone who still runs ``groundlens-mcp`` gets a
sentence telling them where it went, instead of a stack trace from a server built
on a metric the project has withdrawn.
"""

from __future__ import annotations

import sys

__version__ = "3.0.0"

MESSAGE = """\
groundlens-mcp is deprecated and no longer contains a server.

The connector moved into the library, where there is now exactly one tool,
find_unsupported_words, returning the words your sources least support and the
closest span found for each. No verdict, no threshold.

    pip install "groundlens[encoder,mcp]"
    python -m groundlens.mcp

In your MCP client configuration, replace

    "command": "uvx", "args": ["groundlens-mcp"]

with

    "command": "python", "args": ["-m", "groundlens.mcp"]

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
