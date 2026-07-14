# Changelog

All notable changes to groundlens-mcp are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
groundlens-mcp uses [Calendar Versioning](https://calver.org/) with the format `YYYY.M.D`.

## 2026.7.13 -- The handoff ships, and the vocabulary follows the science

### Added

- **`escalate` and `handoff` in every tool response.** The JSON payload now carries
  the second-stage signal from `groundlens.check`. A passing check states, in the
  response itself, that grounding is not fact-checking and that a plausible wrong
  fact in the right frame would pass. Without this, an agent reading a passing
  check reports "not hallucinated" to its user on exactly the class of error the
  method provably cannot see. Requires `groundlens>=2026.7.13`.
- **The register wall in the README**: the per-bin decline (0.62 to 0.68 in
  register, raw cosine 0.595), the authorship-matched ceiling (directional score
  0.606, class ceiling ~0.68), and entailment (0.887 in register) named as the
  recommended second stage.

### Fixed

- **The shipped Cursor rule was broken.** `examples/cursor-loop/.cursor/rules/grounding-loop.mdc`
  told the agent to read a `verdict` field with values `GROUNDED` / `HALLUCINATION RISK`.
  The server has returned `check` / `message` / `level` since 2026.7.6, so anyone
  following the rule was parsing fields that do not exist. Rewritten against the
  real contract, including the handoff.
- **A capability that does not exist.** `examples/rag-audit` claimed Groundlens
  "points at the exact unsupported sentence". It returns one score per answer, not
  span-level attribution, and it does not catch a figure invented inside the
  document's own frame. Both corrected.
- Removed the uncited loop-experiment figures (43% / 40% / 19%) from
  `examples/cursor-loop/README.md`: no dataset, no control, no source.

### Changed

- Tool titles, docstrings and parameter descriptions no longer say "hallucination
  detection". This is a grounding check: provenance and semantic disengagement,
  not factual truth. The docstrings are what an agent reads before telling a user
  their answer is "verified", so they now say plainly what a pass does and does
  not mean.
- `groundlens_dgi` is documented as a coarse triage signal with a measured ceiling,
  not a risk verdict. The line "a negative score means high hallucination risk" is
  gone.
- `server.json` description and version updated (not yet published to the MCP
  registry, so nothing is frozen there).
- Default thresholds in the README are stated as triage starting points, not
  verdicts.

## 2026.7.6

### Changed

- **Tool output now renders the canonical `CHECK`** from
  `groundlens.check` (requires `groundlens>=2026.7.6`). The three tools return
  a plain-language `check` label (`Supported by the document` / `Partly
  supported` / `Not supported by the document` for SGI; `Looks grounded` /
  `Partly grounded` / `Not grounded` for DGI), a `message`, a `level`
  (`ok`/`review`/`risk`), the score, and the raw components in `detail`. Replaces
  the previous `GROUNDED` / `HALLUCINATION RISK` wording. The phrasing is now
  identical across the library, the docs, and both MCP servers — a single source
  of truth. No jargon in the user-facing label.

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
