"""
groundlens MCP Server

Exposes a deterministic first-stage grounding check as MCP tools for Claude
Desktop, Cursor, Windsurf, and any MCP-compatible client.

Scope, and it decides how the result must be used: this checks whether a
response was DRAWN FROM ITS SOURCE. It does not check whether the response is
TRUE. A plausible wrong fact stated in the right frame (right topic, right
terminology, one wrong number) passes this check by design. That is a measured
blind spot, not a bug: every embedding-similarity method, this one included,
declines toward chance as a false answer adopts the register of a true one.
Entailment models do not. Every check therefore carries an ``escalate`` flag and
a ``handoff`` line naming what it cannot settle.

Three tools:
  - groundlens_check: auto-selects SGI or DGI based on whether context is provided
  - groundlens_sgi: context-based grounding check (RAG)
  - groundlens_dgi: context-free grounding signal (chat), coarse, with a known ceiling

Uses the groundlens library (same code as `pip install groundlens`).
All scoring is deterministic — same inputs, same scores, every time.
"""

from __future__ import annotations

import json
import logging
import time

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger("groundlens-mcp")
logger.setLevel(logging.INFO)

if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    logger.addHandler(_handler)

# ─────────────────────────────────────────────────────────────────────────────
# Server
# ─────────────────────────────────────────────────────────────────────────────

mcp = FastMCP("groundlens_mcp")


# ─────────────────────────────────────────────────────────────────────────────
# Input models
# ─────────────────────────────────────────────────────────────────────────────


class CheckInput(BaseModel):
    """Input for the main grounding check tool."""

    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(
        ...,
        description="The question that was asked to the LLM (e.g., 'What does our insurance policy cover?')",
        min_length=1,
        max_length=10000,
    )
    response: str = Field(
        ...,
        description="The LLM's response to check for grounding (was it drawn from the source?)",
        min_length=1,
        max_length=50000,
    )
    context: str | None = Field(
        default=None,
        description=(
            "Source material the LLM was given (e.g., a document, "
            "retrieved RAG chunks, or any reference text). "
            "If provided, uses SGI (context grounding). "
            "If omitted, uses DGI (directional grounding)."
        ),
        max_length=100000,
    )


class SGIInput(BaseModel):
    """Input for explicit SGI (context-based) grounding check."""

    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(
        ...,
        description="The question asked to the LLM",
        min_length=1,
        max_length=10000,
    )
    context: str = Field(
        ...,
        description="The source document or retrieved chunks the LLM was given",
        min_length=1,
        max_length=100000,
    )
    response: str = Field(
        ...,
        description="The LLM's response to evaluate",
        min_length=1,
        max_length=50000,
    )


class DGIInput(BaseModel):
    """Input for explicit DGI (context-free) grounding check."""

    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(
        ...,
        description="The question asked to the LLM",
        min_length=1,
        max_length=10000,
    )
    response: str = Field(
        ...,
        description="The LLM's response to evaluate",
        min_length=1,
        max_length=50000,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Lazy model loading — import groundlens only when first tool is called.
# This avoids loading the sentence-transformer model (~100MB) at server
# startup, which matters for MCP clients that enumerate tools on connect.
# ─────────────────────────────────────────────────────────────────────────────

_loaded = False


def _ensure_loaded() -> None:
    """Load the groundlens embedding model on first use.

    Logs timing so the user can see why the first call takes longer.
    Raises RuntimeError with a friendly message if loading fails.
    """
    global _loaded
    if _loaded:
        return

    logger.info(
        "Loading embedding model for the first time "
        "(~100 MB download on first run, ~5 s on subsequent starts)..."
    )
    load_start = time.perf_counter()

    try:
        import groundlens  # noqa: F401 — triggers model download if needed

        # Warm up with a trivial call to ensure model is fully loaded
        from groundlens import compute_dgi

        compute_dgi(question="warmup", response="warmup")

    except ImportError as exc:
        logger.error("groundlens library not installed: %s", exc)
        raise RuntimeError(
            "The groundlens library is not installed. Run: pip install groundlens"
        ) from exc
    except Exception as exc:
        logger.error("Failed to load embedding model: %s", exc)
        raise RuntimeError(
            "Could not load the embedding model. "
            "This usually means the model download was interrupted. "
            f"Try again or check your network connection. Detail: {exc}"
        ) from exc

    elapsed = time.perf_counter() - load_start
    logger.info("Model loaded in %.1f s — ready for requests.", elapsed)
    _loaded = True


# ─────────────────────────────────────────────────────────────────────────────
# Result formatting
# ─────────────────────────────────────────────────────────────────────────────


def _format_result(result) -> str:
    """Render a groundlens SGI/DGI result as the canonical CHECK.

    All wording comes from ``groundlens.check`` — the single source of truth
    shared with the library, the docs, and the remote MCP — so the phrasing is
    identical everywhere. The plain ``check`` label and ``message`` are
    what a person reads; ``score``, ``level``, ``flagged`` and ``detail`` are for
    programmatic use.

    ``escalate`` and ``handoff`` are the important pair. A passing check means the
    response engaged its source, not that its facts are right, and ``handoff``
    says so in plain language. A client that renders the check without the handoff
    will silently green-light the one class of error this method provably cannot
    see. Requires groundlens >= 2026.7.13.
    """
    from groundlens import check as _check

    v = _check(result)
    payload = {
        "check": v.label,  # e.g. "Supported by the document"
        "message": v.message,  # plain, jargon-free explanation
        "headline": v.line(),  # "CHECK: <label> (<name> - <ABBR>=x.xx)"
        "level": v.level,  # "ok" | "review" | "risk"
        "method": v.metric_name,  # "Semantic Grounding Index" / "Directional Grounding Index"
        "score": round(v.score, 2),
        "flagged": result.flagged,
        "escalate": v.escalate,  # True when geometry cannot settle this case
        "handoff": v.handoff,  # what the second stage has to do. Never omit it.
        "detail": v.detail,  # raw components (q_dist/ctx_dist or magnitude)
    }
    if v.note:
        payload["note"] = (
            v.note
        )  # DGI: "No source given — judged by the shape of the answer."
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _error_response(message: str) -> str:
    """Return a structured JSON error that the LLM can interpret."""
    return json.dumps(
        {
            "check": "ERROR",
            "explanation": message,
            "flagged": None,
            "score": None,
        },
        indent=2,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────────────────────────────────────


@mcp.tool(
    name="groundlens_check",
    annotations={
        "title": "Check grounding against a source",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def groundlens_check(params: CheckInput) -> str:
    """Check whether an LLM response was drawn from its source. Grounding, not truth.

    This is the main tool. It automatically selects the right method:
    - If context is provided: uses SGI (Semantic Grounding Index) to check
      whether the response actually engaged the source material.
    - If no context: uses DGI (Directional Grounding Index), a coarse signal
      with a known ceiling.

    Both are deterministic — same inputs always produce the same score. No model
    in the scoring path. Scoring is embedding geometry.

    IMPORTANT — how to report the result. A passing check means the response
    ENGAGED ITS SOURCE. It does NOT mean the facts are correct. A plausible wrong
    fact stated in the right frame (right topic, right terminology, one wrong
    number or date) will pass. Do not tell the user a passing check means the
    answer is "verified", "accurate" or "not hallucinated". Always surface the
    ``handoff`` field, and when ``escalate`` is true, say so: the case needs a
    second stage (an entailment check, a lookup against the source, or a judge).

    Args:
        params (CheckInput): The question, response, and optional context.

    Returns:
        str: JSON with a plain-language CHECK (Supported / Partly supported / Not
             supported by the document, or Looks grounded / Partly grounded / Not
             grounded), score, level, method, message, ``escalate``, ``handoff``,
             and the raw components.

    Examples:
        - "Did this ChatGPT answer actually come from our policy document?"
          → provide question + response + the policy document as context
        - "Did this answer engage its source at all?"
          → provide question + response (no context needed)
    """
    try:
        _ensure_loaded()
    except RuntimeError as exc:
        logger.error("Model load failed during groundlens_check: %s", exc)
        return _error_response(str(exc))

    from groundlens import compute_dgi, compute_sgi

    has_context = params.context is not None and params.context.strip() != ""
    method = "SGI" if has_context else "DGI"
    logger.info(
        "groundlens_check: method=%s question=%d chars, response=%d chars%s",
        method,
        len(params.question),
        len(params.response),
        f", context={len(params.context)} chars" if has_context else "",
    )

    start = time.perf_counter()
    try:
        if has_context:
            result = compute_sgi(
                question=params.question,
                context=params.context,
                response=params.response,
            )
            output = _format_result(result)
        else:
            result = compute_dgi(
                question=params.question,
                response=params.response,
            )
            output = _format_result(result)
    except Exception as exc:
        logger.error("Scoring failed in groundlens_check: %s", exc, exc_info=True)
        return _error_response(
            f"Scoring failed: {exc}. "
            "This may happen with very short or unusual input. "
            "Try rephrasing or providing more text."
        )

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "groundlens_check complete: %s score=%.4f flagged=%s (%.0f ms)",
        method,
        result.value,
        result.flagged,
        elapsed_ms,
    )
    return output


@mcp.tool(
    name="groundlens_sgi",
    annotations={
        "title": "SGI — Context Grounding Check",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def groundlens_sgi(params: SGIInput) -> str:
    """Check whether an LLM response engaged a source document (SGI). Provenance, not truth.

    SGI (Semantic Grounding Index) measures whether the response engaged with
    the provided context or stayed anchored to the question. This is the method
    to use for RAG pipeline verification — did the model actually use the
    retrieved documents?

    The score is a ratio: dist(response, question) / dist(response, context).
    A high ratio means the response moved toward the context.
    A low ratio means it stayed near the question (possibly ignored the context).

    IMPORTANT: this measures PROVENANCE. An answer that borrows the source's
    vocabulary and structure but changes one figure will pass. Surface the
    ``handoff`` field and escalate fact-level verification to a second stage.

    Args:
        params (SGIInput): The question, source context, and LLM response.

    Returns:
        str: JSON with a plain-language CHECK, the SGI score, and the two distances.

    Examples:
        - Verifying a RAG chatbot used the retrieved documents
        - Checking if a summary is faithful to the source text
        - Auditing whether context was ignored in a customer support bot
    """
    try:
        _ensure_loaded()
    except RuntimeError as exc:
        logger.error("Model load failed during groundlens_sgi: %s", exc)
        return _error_response(str(exc))

    from groundlens import compute_sgi

    logger.info(
        "groundlens_sgi: question=%d chars, context=%d chars, response=%d chars",
        len(params.question),
        len(params.context),
        len(params.response),
    )

    start = time.perf_counter()
    try:
        result = compute_sgi(
            question=params.question,
            context=params.context,
            response=params.response,
        )
    except Exception as exc:
        logger.error("SGI scoring failed: %s", exc, exc_info=True)
        return _error_response(
            f"SGI scoring failed: {exc}. "
            "This may happen with very short or unusual input. "
            "Try rephrasing or providing more text."
        )

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "groundlens_sgi complete: score=%.4f flagged=%s (%.0f ms)",
        result.value,
        result.flagged,
        elapsed_ms,
    )
    return _format_result(result)


@mcp.tool(
    name="groundlens_dgi",
    annotations={
        "title": "DGI — coarse grounding signal, no source",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def groundlens_dgi(params: DGIInput) -> str:
    """Coarse context-free grounding signal, for when no source is available (DGI).

    DGI (Directional Grounding Index) compares the question-to-response
    displacement against the direction typical of answers written from a source.
    No context is needed, so it works for open-ended chat and general Q&A.

    IMPORTANT: this is the weakest signal here and it has a measured ceiling. With
    authorship held constant it reaches AUROC 0.606, and the ceiling of the entire
    embedding-similarity class is about 0.68. It is a ranking signal for triage,
    not a detector, and it is not a risk verdict. Prefer ``groundlens_sgi``
    whenever a source is available. Never report a DGI score as evidence that an
    answer is true or false.

    Args:
        params (DGIInput): The question and LLM response.

    Returns:
        str: JSON with a plain-language CHECK, the DGI score, the magnitude,
             ``escalate`` and ``handoff``.

    Examples:
        - Ranking a batch of chat answers so a reviewer starts with the worst
        - Screening outputs when no source document exists
    """
    try:
        _ensure_loaded()
    except RuntimeError as exc:
        logger.error("Model load failed during groundlens_dgi: %s", exc)
        return _error_response(str(exc))

    from groundlens import compute_dgi

    logger.info(
        "groundlens_dgi: question=%d chars, response=%d chars",
        len(params.question),
        len(params.response),
    )

    start = time.perf_counter()
    try:
        result = compute_dgi(
            question=params.question,
            response=params.response,
        )
    except Exception as exc:
        logger.error("DGI scoring failed: %s", exc, exc_info=True)
        return _error_response(
            f"DGI scoring failed: {exc}. "
            "This may happen with very short or unusual input. "
            "Try rephrasing or providing more text."
        )

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "groundlens_dgi complete: score=%.4f flagged=%s (%.0f ms)",
        result.value,
        result.flagged,
        elapsed_ms,
    )
    return _format_result(result)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Run the groundlens MCP server (stdio transport)."""
    logger.info("groundlens MCP server starting...")
    mcp.run()


if __name__ == "__main__":
    main()
