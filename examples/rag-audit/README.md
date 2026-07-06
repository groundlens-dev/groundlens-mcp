# RAG grounding audit — with the Groundlens MCP, from your editor

A real, minimal RAG pipeline — **LangChain + Chroma + Claude** — over a current, fact-dense document (the Palantir Q1 2026 10-Q). The pipeline has **no grounding check in it**. You audit its answers for hallucination **from Claude Code**, using the Groundlens MCP, without changing a line of the pipeline.

This is the everyday developer question — *"is my RAG making things up?"* — answered deterministically, in the editor, on demand.

## The stack (what a real dev actually runs)

| Piece | Choice | Why |
|-------|--------|-----|
| Orchestration | **LangChain** | The most-adopted RAG framework by a wide margin. |
| Vector store | **Chroma** | Developer-first, runs locally with no server. (Swap for pgvector/Pinecone in prod.) |
| Embeddings | **all-MiniLM-L6-v2** (local) | No embedding API key needed. |
| Generation | **Claude** (Anthropic) | |
| Grounding audit | **Groundlens MCP** in **Claude Code** | Deterministic, no second LLM. Not in the pipeline — in your editor. |

## Setup

```bash
pip install langchain langchain-community langchain-text-splitters langchain-chroma \
            langchain-anthropic langchain-huggingface chromadb sentence-transformers pypdf
export ANTHROPIC_API_KEY=sk-ant-...        # for the RAG's generation
```

> These are the example's own dependencies (LangChain etc.), not dependencies of `groundlens-mcp`. They're listed here rather than in a committed `requirements.txt` on purpose — a checked-in manifest of the LangChain stack would drag the repo's security scan down with the LangChain ecosystem's CVEs, which have nothing to do with this package.

Download the **Palantir – Q1 2026 Business Update** PDF into `data/` (see `data/README.md`), or drop in any PDF of your own.

> First run downloads the ~90 MB local embedding model; after that it's fast.

## Run the RAG

```bash
python rag.py
```

It indexes the PDF, answers the questions in `questions.txt`, prints them, and logs each turn to `outputs/runs.jsonl` as `{question, retrieved_context, answer}`.

`questions.txt` deliberately mixes two kinds:
- **Grounded** questions (revenue, net income, EPS, cash) — answerable straight from the 10-Q.
- **Bait** questions (market cap, Rule of 40, ShipOS) — *not* in a 10-Q. A weak RAG invents a number here; that's the hallucination you want to catch.

## Audit the grounding (the point)

Follow **[`AUDIT_IN_CLAUDE_CODE.md`](AUDIT_IN_CLAUDE_CODE.md)**: add the Groundlens MCP to Claude Code once, then ask it to run `groundlens_sgi` over `outputs/runs.jsonl`. It returns a per-answer check + score and flags the ungrounded ones — pointing at the exact unsupported sentence.

You audited the whole pipeline's grounding from your editor. No wrapper, no second model, no new infra.

## Why the MCP, and why deterministic

Groundlens scores grounding with embedding geometry (SGI: did the answer engage the retrieved context, or just rephrase the question?), not with a second LLM judge. Same inputs → same score, every time. As an MCP tool it drops straight into Claude Code / Claude Desktop / Cursor — nothing to deploy.

- Groundlens MCP: https://github.com/groundlens-dev/groundlens-mcp
- Groundlens: https://groundlens.dev
