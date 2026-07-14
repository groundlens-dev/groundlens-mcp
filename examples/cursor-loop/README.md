# The Loop — Groundlens self-verification inside Cursor

A tiny, real demo: Cursor drafts an answer, then **checks it against Groundlens (an external, deterministic grounding verifier) before trusting it.** No second LLM grades the answer — Groundlens uses embedding geometry, so the same inputs always give the same score.

The idea behind it: *a model cannot be its own judge of truth. The anchor has to come from outside the model.*

---

## What's in this folder

```
groundlens-loop-demo/
├── .cursor/
│   ├── mcp.json                  → registers the Groundlens MCP server
│   └── rules/grounding-loop.mdc  → the rule that makes Cursor verify every answer
├── demo/
│   ├── source.md                 → the "source of truth" for the demo
│   └── try-these.md              → prompts to paste into Cursor chat
└── README.md                     → you are here
```

---

## First time with Cursor? Step by step

**0. Install Cursor** (if you haven't): https://cursor.com — download, install, open.

**1. Make the Groundlens server runnable.** The config uses `uvx` (runs the tool without a permanent install). Install `uv` once:

```bash
# macOS
brew install uv
# or, any platform:
pip install uv
```

*Prefer plain pip?* Then run `pip install groundlens-mcp` and edit `.cursor/mcp.json` to use `"command": "groundlens-mcp"` with `"args": []`.

> First run downloads a ~100 MB embedding model, so the first check takes a few seconds. After that it's fast.

**2. Open this folder in Cursor.** `File → Open Folder…` → pick `groundlens-loop-demo`.

**3. Turn the MCP server on.** Cursor detects `.cursor/mcp.json` automatically. Go to **Settings → Cursor Settings → MCP (or "Tools")**, find **groundlens**, and make sure it's toggled **on** (green). You should see its three tools: `groundlens_check`, `groundlens_sgi`, `groundlens_dgi`. If it's not there, restart Cursor.

**4. The rule is already active.** `.cursor/rules/grounding-loop.mdc` is set to *always apply*, so the agent will verify factual answers on its own — you don't have to ask.

**5. Try it.** Open the chat (**Cmd + L** on macOS / **Ctrl + L**), make sure you're in **Agent** mode, and paste the prompts from [`demo/try-these.md`](demo/try-these.md), one at a time. Watch the agent: draft → call a Groundlens tool → show the CHECK, the score, and the handoff line.

---

## What you should see

- An answer drawn from the source ends with something like `Grounding: Supported by the document (SGI = 4.64)`, followed by the handoff line: *grounding, not facts. A plausible wrong fact in the right frame would pass this check.*
- An answer **not supported by the source** comes back `Not supported by the document`, with `escalate: true`, and the agent tells you so instead of inventing facts.

Both halves are the point. The model stops being its own judge of provenance, and the check stops pretending to be a judge of truth.

---

## Why this matters (the research behind it)

A model asked to check its own output is grading its own homework with the same pen. The anchor has to come from outside, and it has to be cheap enough to run on everything. That is what this loop is.

It is also bounded, and the boundary is published. Groundlens checks whether an answer came from its source. On a wrong fact stated in the right frame it declines toward chance, like every embedding-similarity method. Entailment models do not, and that is the second stage the handoff points you to.

- Groundlens: https://groundlens.dev · MCP server: https://github.com/groundlens-dev/groundlens-mcp
- The geometry behind SGI/DGI: arXiv:2512.13771 · the model dynamics: *Rotational Dynamics of Factual Constraint Processing*, arXiv:2603.13259
- What this method cannot do, and why: *The Register Wall: What Similarity-Based Hallucination Detectors Actually Measure* (under review)

---

## Troubleshooting

- **groundlens not listed under MCP:** restart Cursor; confirm `uv`/`uvx` (or `groundlens-mcp`) is on your PATH by running `uvx groundlens-mcp --help` in a terminal.
- **First answer is slow:** that's the one-time model download (~100 MB). Later calls are fast.
- **Agent answers without checking:** make sure you're in **Agent** mode (not plain chat), and that the `groundlens` MCP toggle is green.
