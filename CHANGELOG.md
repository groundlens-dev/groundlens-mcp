# Changelog

All notable changes to groundlens-mcp are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
groundlens-mcp uses [Calendar Versioning](https://calver.org/) with the format `YYYY.M.D`.

## 2026.7.4

### Changed

- **License** is now Apache-2.0 across the project (LICENSE, `pyproject.toml`, README badge).

### Fixed

- **`pyproject.toml`**: corrected `build-backend` to `hatchling.build` and the license metadata to the SPDX expression `Apache-2.0`; removed a stale MIT license classifier.

### Added

- **Official MCP Registry** support: `server.json` and the `mcp-name` reference in the README for package-ownership validation.
- **Cursor example** (`examples/cursor-loop/`): a drop-in `.cursor/` config + rule that makes Cursor verify every answer with Groundlens (the self-verification loop).

## 2026.5.18

The 2026.5.x series is the initial public release of the groundlens MCP server.
It exposes deterministic, geometry-based hallucination detection to any
MCP-compatible client (Claude Desktop, Cursor, Windsurf, VS Code).

### Added

- **Three MCP tools** for grounding verification:
  - `groundlens_check` — auto-selects the right method (default).
  - `groundlens_sgi` — Semantic Grounding Index: checks a response against a source document (RAG, document Q&A).
  - `groundlens_dgi` — Directional Grounding Index: checks response patterns without a provided context (chat, general Q&A).
- **Deterministic scoring** — the same inputs always produce the same scores; no second LLM in the loop.
- **One-command install** via `pip install groundlens-mcp` or `uvx groundlens-mcp`, with ready-to-use configuration for Claude Desktop, Cursor, Windsurf, and VS Code.

### Notes

- Upgrade impact: none for existing users within the 2026.5.x series — these are additive, backward-compatible releases.
- See the [README](README.md) for configuration and usage, and [SECURITY.md](SECURITY.md) for the vulnerability-reporting process.
