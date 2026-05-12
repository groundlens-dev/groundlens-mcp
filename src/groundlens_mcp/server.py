"""
groundlens MCP Server

Exposes LLM hallucination detection as MCP tools for Claude Desktop,
Cursor, Windsurf, and any MCP-compatible client.

Three tools:
  - groundlens_check: auto-selects SGI or DGI based on whether context is provided
  - groundlens_sgi: explicit context-based grounding verification (RAG)
  - groundlens_dgi: explicit context-free grounding verification (chat)

Uses the groundlens library (same code as `pip install groundlens`).
All scoring is deterministic — same inputs, same scores, every time.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict

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
    """Input for the main hallucination check tool."""

    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(
        ...,
        description="The question that was asked to the LLM (e.g., 'What does our insurance policy cover?')",
        min_length=1,
        max_length=10000,
    )
    response: str = Field(
        ...,
        description="The LLM's response to evaluate for hallucination",
        min_length=1,
        max_length=50000,
    )
    context: Optional[str] = Field(
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
            "The groundlens library is not installed. "
            "Run: pip install groundlens"
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

def _format_sgi_result(result) -> str:
    """Format an SGIResult into a human-readable + machine-parseable response."""
    verdict = "GROUNDED" if not result.flagged else "HALLUCINATION RISK"
    plain = (
        "The response appears to be grounded in the source material."
        if not result.flagged
        else "The response may not be based on the source material provided."
    )

    return json.dumps(
        {
            "verdict": verdict,
            "explanation": plain,
            "method": "SGI (Semantic Grounding Index)",
            "score": round(result.value, 4),
            "threshold": 0.95,
            "flagged": result.flagged,
            "detail": {
                "q_dist": round(result.q_dist, 4),
                "ctx_dist": round(result.ctx_dist, 4),
                "interpretation": result.explanation,
            },
            "what_this_means": (
                "SGI measures whether the response engaged with the source context "
                "or just rephrased the question. "
                "Score > 0.95 = context was used. Score < 0.95 = context may have been ignored."
            ),
        },
        indent=2,
    )


def _format_dgi_result(result) -> str:
    """Format a DGIResult into a human-readable + machine-parseable response."""
    verdict = "GROUNDED" if not result.flagged else "HALLUCINATION RISK"
    plain = (
        "The response follows patterns typical of grounded, factual answers."
        if not result.flagged
        else "The response shows geometric patterns associated with hallucination."
    )

    return json.dumps(
        {
            "verdict": verdict,
            "explanation": plain,
            "method": "DGI (Directional Grounding Index)",
            "score": round(result.value, 4),
            "threshold": 0.30,
            "flagged": result.flagged,
            "detail": {
                "interpretation": result.explanation,
            },
            "what_this_means": (
                "DGI measures whether the question-to-response displacement "
                "aligns with patterns seen in verified grounded responses. "
                "Score > 0.30 = grounded pattern. Score < 0.30 = anomalous pattern."
            ),
        },
        indent=2,
    )


def _error_response(message: str) -> str:
    """Return a structured JSON error that the LLM can interpret."""
    return json.dumps(
        {
            "verdict": "ERROR",
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
        "title": "Check for LLM Hallucination",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def groundlens_check(params: CheckInput) -> str:
    """Check whether an LLM response is hallucinated or grounded.

    This is the main tool. It automatically selects the right method:
    - If context is provided: uses SGI (Semantic Grounding Index) to check
      whether the response actually used the source material.
    - If no context: uses DGI (Directional Grounding Index) to check whether
      the response follows patterns typical of grounded answers.

    Both methods are deterministic — same inputs always produce the same score.
    No second LLM is used. Scoring is based on embedding geometry.

    Args:
        params (CheckInput): The question, response, and optional context.

    Returns:
        str: JSON with verdict (GROUNDED or HALLUCINATION RISK), score,
             method used, explanation, and interpretation guidance.

    Examples:
        - "Check if this ChatGPT answer about our policy is accurate"
          → provide question + response + the policy document as context
        - "Is this response hallucinated?"
          → provide question + response (no context needed)
    """
    try:
        _ensure_loaded()
    except RuntimeError as exc:
        logger.error("Model load failed during groundlens_check: %s", exc)
        return _error_response(str(exc))

    from groundlens import compute_sgi, compute_dgi

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
            output = _format_sgi_result(result)
        else:
            result = compute_dgi(
                question=params.question,
                response=params.response,
            )
            output = _format_dgi_result(result)
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
        method, result.value, result.flagged, elapsed_ms,
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
    """Check whether an LLM response is grounded in a source document (SGI).

    SGI (Semantic Grounding Index) measures whether the response engaged with
    the provided context or stayed anchored to the question. This is the method
    to use for RAG pipeline verification — did the model actually use the
    retrieved documents?

    The score is a ratio: dist(response, question) / dist(response, context).
    A high ratio means the response moved toward the context (grounded).
    A low ratio means it stayed near the question (possibly ignored the context).

    Args:
        params (SGIInput): The question, source context, and LLM response.

    Returns:
        str: JSON with verdict, SGI score, distances, and interpretation.

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
        len(params.question), len(params.context), len(params.response),
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
        result.value, result.flagged, elapsed_ms,
    )
    return _format_sgi_result(result)


@mcp.tool(
    name="groundlens_dgi",
    annotations={
        "title": "DGI — Directional Grounding Check",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def groundlens_dgi(params: DGIInput) -> str:
    """Check whether an LLM response shows hallucination patterns (DGI).

    DGI (Directional Grounding Index) measures whether the question-to-response
    displacement aligns with the direction characteristic of verified grounded
    responses. No source context is needed — this works for open-ended chat,
    general Q&A, or any situation where you just have a question and answer.

    A positive score means the displacement aligns with grounded patterns.
    A score below 0.30 means the response is geometrically anomalous.
    A negative score means high hallucination risk.

    Args:
        params (DGIInput): The question and LLM response.

    Returns:
        str: JSON with verdict, DGI score, and interpretation.

    Examples:
        - Checking a chatbot's answer to a factual question
        - Screening LLM outputs before showing them to users
        - Batch-evaluating model responses for quality
    """
    try:
        _ensure_loaded()
    except RuntimeError as exc:
        logger.error("Model load failed during groundlens_dgi: %s", exc)
        return _error_response(str(exc))

    from groundlens import compute_dgi

    logger.info(
        "groundlens_dgi: question=%d chars, response=%d chars",
        len(params.question), len(params.response),
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
        result.value, result.flagged, elapsed_ms,
    )
    return _format_dgi_result(result)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Run the groundlens MCP server (stdio transport)."""
    logger.info("groundlens MCP server starting...")
    mcp.run()


if __name__ == "__main__":
    main()
