<!-- mcp-name: io.github.groundlens-dev/groundlens-mcp -->
<div align="center">
  
# Groundlens MCP
  
  [![Python](https://img.shields.io/pypi/pyversions/groundlens-mcp?style=flat-square)](https://pypi.org/project/groundlens-mcp/)
  [![CI](https://img.shields.io/github/actions/workflow/status/groundlens-dev/groundlens-mcp/ci.yml?branch=main&label=CI&style=flat-square)](https://github.com/groundlens-dev/groundlens-mcp/actions)
  [![codecov](https://codecov.io/gh/groundlens-dev/groundlens-mcp/branch/main/graph/badge.svg)](https://codecov.io/gh/groundlens-dev/groundlens-mcp)
  [![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=flat-square)](LICENSE)
  [![OpenSSF Scorecard](https://img.shields.io/ossf-scorecard/github.com/groundlens-dev/groundlens-mcp?style=flat-square&label=OpenSSF%20Scorecard)](https://scorecard.dev/viewer/?uri=github.com/groundlens-dev/groundlens-mcp)
  [![OpenSSF Best Practices](https://www.bestpractices.dev/projects/13396/badge)](https://www.bestpractices.dev/projects/13396)

</div>

MCP server for [groundlens](https://groundlens.dev) — a deterministic **first-stage grounding check** for Claude Desktop, Cursor, Windsurf, and any MCP-compatible client.
It checks whether an answer was drawn from its source, in milliseconds, with no model in the scoring path. Same inputs → same scores, every time.

It is a filter, not a judge. It has a characterized blind spot, and every check says so.

## One-click install

<div align="center">
  
| Tool | Install|
|------|---------------|
| Cursor | [![Install in Cursor](https://img.shields.io/badge/Cursor-Add_MCP-000000?style=flat-square&logo=cursor&logoColor=white)](https://cursor.com/install-mcp?name=groundlens&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJncm91bmRsZW5zLW1jcCJdfQ%3D%3D)|
| VS Code | [![Install in VS Code](https://img.shields.io/badge/VS_Code-Add_MCP-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=groundlens&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22groundlens-mcp%22%5D%7D)|
| VS Code Insiders |  [![Install in VS Code Insiders](https://img.shields.io/badge/VS_Code_Insiders-Add_MCP-24bfa5?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=groundlens&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22groundlens-mcp%22%5D%7D&quality=insiders) |
  
</div>


## What it does

Adds three tools to your AI assistant:

| Tool | What it checks | When to use it |
|------|---------------|----------------|
| `groundlens_check` | Auto-selects the right method | Default — just use this one |
| `groundlens_sgi` | Response vs. source document (SGI) | RAG pipelines, document Q&A |
| `groundlens_dgi` | Response patterns without context (DGI) | Chat, general Q&A |

**SGI** (Semantic Grounding Index) measures whether the response engaged the source material or just rephrased the question. The default triage threshold is 0.95, and it is a starting point, not a verdict: calibrate it on your own grounded distribution. SGI sorts, it does not decide.

**DGI** (Directional Grounding Index) is the context-free fallback. It is the weakest signal here and it has a measured ceiling (see below). Prefer SGI whenever you have the source.

## Install

```bash
pip install groundlens-mcp
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv pip install groundlens-mcp
```

### More clients

**Claude Code** (CLI):

```bash
claude mcp add groundlens -- uvx groundlens-mcp
```

**Claude Desktop, Windsurf, Cline, or any MCP client** — add to its config:

```json
{ "mcpServers": { "groundlens": { "command": "uvx", "args": ["groundlens-mcp"] } } }
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

Example with Cursor:

- [Cursor self-verification loop](examples/cursor-loop/) — drop-in `.cursor/` config + rule that makes Cursor verify every answer with Groundlens.

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

> "Did this ChatGPT answer actually come from the document I gave it?"

The tools return JSON with a plain-language **CHECK** check, a numeric score, and the raw components. The wording comes from `groundlens.check` — the same source of truth used by the library and docs, so it reads identically everywhere.

### Example output

```json
{
  "check": "Not supported by the document",
  "message": "The answer stays closer to the question than to the source, so it may not come from the document. Check it before trusting it.",
  "headline": "CHECK: Not supported by the document (Semantic Grounding Index - SGI=0.87)",
  "level": "risk",
  "method": "Semantic Grounding Index",
  "score": 0.87,
  "flagged": true,
  "detail": "distance to source 0.49, distance to question 0.43"
}
```

The check `level` is `ok` / `review` / `risk` (from the calibrated thresholds). For context-free DGI checks the check reads `Looks grounded` / `Partly grounded` / `Not grounded`, plus a `note` that no source was provided.

Every response also carries `escalate` and `handoff`. **Do not drop them.** A passing check means the answer came from the source. It does not mean the facts are right, and `handoff` says so in plain language:

```json
{
  "check": "Supported by the document",
  "level": "ok",
  "escalate": false,
  "handoff": "Grounding, not facts: a plausible wrong fact in the right frame would pass this check. Verify facts in a second stage."
}
```

A client that renders the check without the handoff silently green-lights the one class of error this method provably cannot see.

## How it works

groundlens uses embedding geometry, with no model in the scoring path, to check **provenance**: did this answer come from its source?

- **SGI** computes `dist(response, question) / dist(response, context)`. If the response moved toward the context, it engaged the source. If it stayed near the question, the context was likely ignored.
- **DGI** projects the question→response displacement onto the mean direction of answers written from a source. Context-free, and coarse.

Both run a single embedding call. No inference. Deterministic.

## The wall, and why there is a second stage

Bin confabulations by how far they sit from the register of a correct answer, and every embedding-similarity method, this one included, declines toward chance as the answer moves *into* register: same vocabulary, same phrasing, one wrong number. At the in-register end classic encoders reach AUROC 0.62 to 0.68 and raw cosine 0.595. With authorship held constant the directional score reaches 0.606, and the ceiling of the whole class is about 0.68.

Entailment does not decline. Across the same bins an NLI cross-encoder holds 0.836, 0.786, 0.837, 0.719, 0.887, and it is strongest exactly where geometry is weakest. **Entailment is the recommended second stage.** This server runs first, on everything, for free, and hands over what it cannot settle.

Full write-up: *The Register Wall: What Similarity-Based Hallucination Detectors Actually Measure* (under review). Read it before relying on any similarity-based detector, including this one.

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
