# Audit your RAG's grounding — from your editor, in 30 seconds

Your `rag.py` pipeline has **no grounding check** in it. You don't need to add one. You audit it from Claude Code with the Groundlens MCP.

## One-time setup

Add the Groundlens MCP to Claude Code (once):

```bash
claude mcp add groundlens -- uvx groundlens-mcp
```

## The workflow

1. **Run the RAG** so it produces answers to audit:
   ```bash
   python rag.py
   ```
   This writes `outputs/runs.jsonl` — one line per answer, each with `question`, `retrieved_context`, and `answer`.

2. **Open this folder in Claude Code** and paste this:

   > Read `outputs/runs.jsonl`. For each entry, call the `groundlens_sgi` tool with `question` = the question, `response` = the answer, and `context` = the retrieved_context. Build a table with columns: question, verdict, score. Flag every entry below the grounded threshold, and for each flagged one quote the exact sentence in the answer that the context does not support.

3. **Watch what happens.** Claude Code calls the Groundlens MCP once per row — deterministically, no second LLM grading the output — and hands you a grounding report:
   - The three **grounded** questions (revenue, Rule of 40, ShipOS) pass with high SGI.
   - The three **bait** questions (net margin, new-customer count, market cap) are **not in the report**. If your RAG invented a number, Groundlens flags it `HALLUCINATION RISK` and points at the unsupported sentence. If your RAG correctly said "I don't know," it passes — and now you have proof.

## Why this is the sell

You just audited an entire RAG pipeline's grounding **without touching the pipeline** — no wrapper, no second model, no new infra, no eval framework to stand up. The check lives in your editor, runs on demand, and gives the same score every time.

That is the day-to-day: you're debugging "why is my bot making things up?", and instead of squinting at logs, you ask your editor to grade the grounding for you.
