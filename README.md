# GROUNDLENS-MCP

MCP server for [groundlens](https://groundlens.dev) — LLM hallucination detection for Claude Desktop, Cursor, Windsurf, and any MCP-compatible client.

No second LLM. Deterministic. Same inputs → same scores, every time.

[![PyPI](https://img.shields.io/pypi/v/groundlens-mcp?style=flat-square)](https://pypi.org/project/groundlens-mcp/)
[![CI](https://img.shields.io/github/actions/workflow/status/groundlens-dev/groundlens-mcp/ci.yml?branch=main&style=flat-square&label=tests)](https://github.com/groundlens-dev/groundlens-mcp/actions/workflows/ci.yml)
[![codecov](https://img.shields.io/codecov/c/github/groundlens-dev/groundlens-mcp?style=flat-square)](https://codecov.io/gh/groundlens-dev/groundlens-mcp)
[![Python](https://img.shields.io/pypi/pyversions/groundlens-mcp?style=flat-square)](https://pypi.org/project/groundlens-mcp/)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

## What it does

Adds three tools to your AI assistant:

| Tool | What it checks | When to use it |
|------|---------------|----------------|
| `groundlens_check` | Auto-selects the right method | Default — just use this one |
| `groundlens_sgi` | Response vs. source document (SGI) | RAG pipelines, document Q&A |
| `groundlens_dgi` | Response patterns without context (DGI) | Chat, general Q&A |

**SGI** (Semantic Grounding Index) measures whether the response actually used the source material or just rephrased the question. Score > 0.95 = grounded.

**DGI** (Directional Grounding Index) measures whether the response follows geometric patterns typical of grounded answers. Score > 0.30 = grounded.

## Install

```bash
pip install groundlens-mcp
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv pip install groundlens-mcp
```

## Configure your client

### Claude Desktop

Add to your `claude_desktop_config.json`:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

- **Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "groundlens": {
      "command": "groundlens-mcp"
    }
  }
}
```

If you installed with `uv` and the command isn't on your PATH:

```json
{
  "mcpServers": {
    "groundlens": {
      "command": "uv",
      "args": ["run", "groundlens-mcp"]
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "groundlens": {
      "command": "groundlens-mcp"
    }
  }
}
```

### Windsurf

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "groundlens": {
      "command": "groundlens-mcp"
    }
  }
}
```

## How to use

Once configured, ask your ai assistant:

> "Check if this response is hallucinated"

> "Is this answer grounded in the document I provided?"

> "Run a hallucination check on this ChatGPT output"

The tools return JSON with a verdict (`GROUNDED` or `HALLUCINATION RISK`), a numeric score, and a plain-language explanation.

### Example output

```json
{
  "verdict": "HALLUCINATION RISK",
  "explanation": "The response may not be based on the source material provided.",
  "method": "SGI (Semantic Grounding Index)",
  "score": 0.8721,
  "threshold": 0.95,
  "flagged": true,
  "detail": {
    "q_dist": 0.4312,
    "ctx_dist": 0.4945,
    "interpretation": "Response stayed close to the question rather than engaging with the context."
  }
}
```

## How it works

groundlens uses embedding geometry — not a second LLM — to detect hallucinations:

- **SGI** computes `dist(response, question) / dist(response, context)`. If the response moved toward the context, it's grounded. If it stayed near the question, the context was likely ignored.
- **DGI** projects the question→response displacement onto the mean direction of verified grounded pairs. Positive alignment = grounded pattern.

Both methods run a single embedding call. No model inference for evaluation. Deterministic.

## First-call latency

The first tool call downloads and loads the sentence-transformer model (~100MB). Subsequent calls are fast. The model is loaded lazily so your MCP client doesn't slow down on startup.

## Running from source

```bash
git clone https://github.com/groundlens-dev/groundlens-mcp.git
cd groundlens-mcp
pip install -e .
groundlens-mcp
```

Or:

```bash
python -m groundlens_mcp
```

## Links

- [groundlens library](https://github.com/groundlens-dev/groundlens) — `pip install groundlens`
- [Documentation](https://docs.groundlens.dev)
- [Website](https://groundlens.dev)
- [Demo](https://huggingface.co/spaces/groundlens/groundlens-demo)

## License

MIT
