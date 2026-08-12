<div align="center">

# groundlens-mcp

</div>

**This repository is archived. The groundlens MCP connector now ships inside the
library itself.**

```bash
pip install "groundlens[encoder,mcp]"
python -m groundlens.mcp
```

Point your client at that command:

```json
{
  "mcpServers": {
    "groundlens": {
      "command": "python",
      "args": ["-m", "groundlens.mcp"]
    }
  }
}
```

## Why it moved

Keeping the connector in a second package meant keeping a second implementation
of the same thing, and the two drifted. This repository was still serving three
tools — `groundlens_check`, `groundlens_sgi`, `groundlens_dgi` — built on a
metric the project has since withdrawn, and still answering with a verdict and a
threshold that the measurements do not support.

groundlens 3.0.0 exposes one tool, `find_unsupported_words`. It returns the words
your sources least support and the closest span it found for each one. It
returns no verdict and carries no threshold. There is now exactly one
implementation of that, and it lives beside the code it wraps.

## Where things are

- [groundlens](https://github.com/groundlens-dev/groundlens) — the library
- [groundlens.dev](https://groundlens.dev) — what it does and why
- [PyPI](https://pypi.org/project/groundlens/) — `pip install groundlens`

The `groundlens-mcp` package on PyPI is deprecated. Versions up to `2026.5.18`
are yanked; `3.0.0` installs nothing and prints the migration message above.

Apache-2.0.
