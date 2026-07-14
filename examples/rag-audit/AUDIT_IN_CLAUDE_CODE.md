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

   > Read `outputs/runs.jsonl`. For each entry, call the `groundlens_sgi` tool with `question` = the question, `response` = the answer, and `context` = the retrieved_context. Build a table with columns: question, check, score, escalate. Then, for every entry with `escalate: true`, read the answer against the context yourself and quote the sentence the context does not support. Groundlens tells you *which answers* to look at; the reading is still yours.

3. **Watch what happens.** Claude Code calls the Groundlens MCP once per row — deterministically, no second LLM grading the output — and hands you a grounding report:
   - The **grounded** questions (revenue, net income, EPS, cash) pass with high SGI.
   - The **bait** questions (market cap, Rule of 40, ShipOS) are **not in a 10-Q**. If your RAG answered them anyway, the answer had to come from somewhere other than the document, and Groundlens returns `Not supported by the document` with `escalate: true`. If your RAG correctly said "I don't know", it passes, and now you have proof.
   - What it does **not** do: point at a sentence. Groundlens returns one score per answer, not span-level attribution. And it will **not** catch a number invented *inside* the document's own frame. An answer that copies the 10-Q's structure and vocabulary and changes one figure is drawn from the document, and it passes. That case escalates: read the `handoff` field and send it to an entailment check, a lookup against the filing, or a human.

## Why this is the sell

You just audited an entire RAG pipeline's grounding **without touching the pipeline** — no wrapper, no second model, no new infra, no eval framework to stand up. The check lives in your editor, runs on demand, and gives the same score every time.

That is the day-to-day: you're debugging "why is my bot making things up?", and instead of squinting at logs, you ask your editor to grade the grounding for you.
