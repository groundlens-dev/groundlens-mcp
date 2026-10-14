# groundlens-mcp

**Moved.** The GroundLens MCP server ships inside the `groundlens` package.
This repository is archived, and the `groundlens-mcp` package on PyPI installs
nothing but a message that says so.

```bash
pip install "groundlens[mcp]"
groundlens-mcp
```

```json
{ "mcpServers": { "groundlens": { "command": "groundlens-mcp" } } }
```

With nothing installed, through [uv](https://docs.astral.sh/uv/):

```json
{
  "mcpServers": {
    "groundlens": {
      "command": "uvx",
      "args": ["--from", "groundlens[mcp]", "groundlens-mcp"]
    }
  }
}
```

Keep `--from "groundlens[mcp]"`: a bare `uvx groundlens-mcp` installs this
old package instead of the server.

The server has three tools: `verify_answer`, `verify_run` and
`verify_records`. GroundLens is guardrails for LLM answers: it checks an LLM
answer against its sources without a model, decides PASS, REVIEW or FAIL under
your policy, and keeps a signed record.

- Source: https://github.com/groundlens-dev/groundlens
- Site: https://groundlens.dev
- MCP registry: `io.github.groundlens-dev/groundlens`

Apache-2.0.
