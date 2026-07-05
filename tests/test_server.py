"""Tests for groundlens MCP server — input validation, formatting, and tool routing."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest
from groundlens.score import DGIResult, SGIResult
from groundlens_mcp.server import (
    CheckInput,
    DGIInput,
    SGIInput,
    _error_response,
    _format_result,
    groundlens_check,
    groundlens_dgi,
    groundlens_sgi,
)
from pydantic import ValidationError

# ─────────────────────────────────────────────────────────────────────────────
# Real result builders (verdict() dispatches on the real dataclasses, so the
# tests must use them — they are pure-Python and need no embedding model).
# ─────────────────────────────────────────────────────────────────────────────


def sgi(value, flagged, q_dist=0.5, ctx_dist=0.5):
    return SGIResult(
        value=value, normalized=0.5, flagged=flagged, q_dist=q_dist, ctx_dist=ctx_dist
    )


def dgi(value, flagged, magnitude=1.0):
    return DGIResult(value=value, normalized=0.5, flagged=flagged, magnitude=magnitude)


# ─────────────────────────────────────────────────────────────────────────────
# Input model validation
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckInput:
    """Validate CheckInput accepts valid data and rejects invalid data."""

    def test_valid_with_context(self):
        inp = CheckInput(
            question="What is covered?",
            response="Fire and flood.",
            context="Policy covers fire and flood.",
        )
        assert inp.question == "What is covered?"
        assert inp.context == "Policy covers fire and flood."

    def test_valid_without_context(self):
        inp = CheckInput(question="Capital of France?", response="Paris.")
        assert inp.context is None

    def test_strips_whitespace(self):
        inp = CheckInput(
            question="  What is covered?  ", response="  Fire and flood.  "
        )
        assert inp.question == "What is covered?"
        assert inp.response == "Fire and flood."

    def test_rejects_empty_question(self):
        with pytest.raises(ValidationError):
            CheckInput(question="", response="Some response.")

    def test_rejects_empty_response(self):
        with pytest.raises(ValidationError):
            CheckInput(question="Some question?", response="")

    def test_rejects_whitespace_only_question(self):
        with pytest.raises(ValidationError):
            CheckInput(question="   ", response="Some response.")

    def test_rejects_whitespace_only_response(self):
        with pytest.raises(ValidationError):
            CheckInput(question="Some question?", response="   ")


class TestSGIInput:
    """Validate SGIInput requires all three fields."""

    def test_valid(self):
        inp = SGIInput(
            question="What is covered?",
            context="Policy covers fire.",
            response="Fire is covered.",
        )
        assert inp.context == "Policy covers fire."

    def test_rejects_empty_context(self):
        with pytest.raises(ValidationError):
            SGIInput(question="What?", context="", response="Answer.")

    def test_rejects_missing_context(self):
        with pytest.raises(ValidationError):
            SGIInput(question="What?", response="Answer.")  # type: ignore[call-arg]


class TestDGIInput:
    """Validate DGIInput requires question and response only."""

    def test_valid(self):
        inp = DGIInput(question="Capital of France?", response="Paris.")
        assert inp.question == "Capital of France?"

    def test_rejects_empty_question(self):
        with pytest.raises(ValidationError):
            DGIInput(question="", response="Paris.")


# ─────────────────────────────────────────────────────────────────────────────
# Result formatting — the canonical VERIFICATION verdict (groundlens.verdict)
# ─────────────────────────────────────────────────────────────────────────────


class TestFormatResultSGI:
    """SGI results render as the plain-language VERIFICATION verdict."""

    def test_supported(self):
        out = json.loads(
            _format_result(sgi(value=1.23, flagged=False, q_dist=0.57, ctx_dist=0.43))
        )
        assert out["verification"] == "Supported by the document"
        assert out["level"] == "ok"
        assert out["flagged"] is False
        assert out["method"] == "Semantic Grounding Index"
        assert out["score"] == 1.23
        assert out["headline"].startswith("VERIFICATION: Supported by the document")
        assert "distance to source" in out["detail"]

    def test_partly_supported(self):
        out = json.loads(_format_result(sgi(value=1.05, flagged=False)))
        assert out["verification"] == "Partly supported"
        assert out["level"] == "review"

    def test_not_supported(self):
        out = json.loads(
            _format_result(sgi(value=0.71, flagged=True, q_dist=0.3, ctx_dist=0.42))
        )
        assert out["verification"] == "Not supported by the document"
        assert out["level"] == "risk"
        assert out["flagged"] is True

    def test_score_two_decimals(self):
        out = json.loads(_format_result(sgi(value=1.239, flagged=False)))
        assert out["score"] == 1.24

    def test_no_jargon_in_verification(self):
        out = json.loads(_format_result(sgi(value=0.5, flagged=True)))
        assert "hallucinat" not in out["verification"].lower()
        assert "grounding" not in out["verification"].lower()


class TestFormatResultDGI:
    """DGI results render as the plain-language VERIFICATION verdict."""

    def test_looks_grounded(self):
        out = json.loads(_format_result(dgi(value=0.45, flagged=False, magnitude=1.0)))
        assert out["verification"] == "Looks grounded"
        assert out["level"] == "ok"
        assert out["method"] == "Directional Grounding Index"
        assert out["score"] == 0.45
        assert "note" in out
        assert "No source" in out["note"]
        assert "commitment" in out["detail"]

    def test_partly_grounded(self):
        out = json.loads(_format_result(dgi(value=0.18, flagged=True)))
        assert out["verification"] == "Partly grounded"
        assert out["level"] == "review"

    def test_not_grounded(self):
        out = json.loads(_format_result(dgi(value=-0.12, flagged=True)))
        assert out["verification"] == "Not grounded"
        assert out["level"] == "risk"


# ─────────────────────────────────────────────────────────────────────────────
# Tool routing — patch compute_sgi/compute_dgi to return real results, so the
# real verdict() renders. _ensure_loaded is patched to skip the model.
# ─────────────────────────────────────────────────────────────────────────────


def _run(coro):
    """Helper to run async tool functions in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestGroundlensCheck:
    """Verify groundlens_check routes to SGI or DGI based on context."""

    @patch("groundlens_mcp.server._ensure_loaded")
    def test_routes_to_sgi_when_context_provided(self, mock_load):
        with patch("groundlens.compute_sgi", return_value=sgi(1.05, False)):
            params = CheckInput(
                question="What is covered?",
                response="Fire and flood.",
                context="Policy covers fire and flood.",
            )
            output = json.loads(_run(groundlens_check(params)))
            assert output["method"] == "Semantic Grounding Index"

    @patch("groundlens_mcp.server._ensure_loaded")
    def test_routes_to_dgi_when_no_context(self, mock_load):
        with patch("groundlens.compute_dgi", return_value=dgi(0.45, False)):
            params = CheckInput(question="Capital of France?", response="Paris.")
            output = json.loads(_run(groundlens_check(params)))
            assert output["method"] == "Directional Grounding Index"

    @patch("groundlens_mcp.server._ensure_loaded")
    def test_routes_to_dgi_when_context_is_whitespace(self, mock_load):
        with patch("groundlens.compute_dgi", return_value=dgi(0.45, False)):
            params = CheckInput(
                question="Capital of France?", response="Paris.", context="   "
            )
            output = json.loads(_run(groundlens_check(params)))
            assert output["method"] == "Directional Grounding Index"


class TestGroundlensSGI:
    """Verify groundlens_sgi tool calls compute_sgi and formats output."""

    @patch("groundlens_mcp.server._ensure_loaded")
    def test_returns_sgi_result(self, mock_load):
        with patch(
            "groundlens.compute_sgi",
            return_value=sgi(0.85, True, q_dist=0.3, ctx_dist=0.35),
        ):
            params = SGIInput(
                question="What is covered?",
                context="Policy covers fire.",
                response="I'm not sure.",
            )
            output = json.loads(_run(groundlens_sgi(params)))
            assert output["verification"] == "Not supported by the document"
            assert output["level"] == "risk"
            assert output["flagged"] is True
            assert output["score"] == 0.85


class TestGroundlensDGI:
    """Verify groundlens_dgi tool calls compute_dgi and formats output."""

    @patch("groundlens_mcp.server._ensure_loaded")
    def test_returns_dgi_result(self, mock_load):
        with patch("groundlens.compute_dgi", return_value=dgi(0.15, True)):
            params = DGIInput(
                question="Who invented the internet?",
                response="The internet was invented by Napoleon.",
            )
            output = json.loads(_run(groundlens_dgi(params)))
            assert output["verification"] == "Partly grounded"
            assert output["flagged"] is True
            assert output["score"] == 0.15


# ─────────────────────────────────────────────────────────────────────────────
# JSON output structure
# ─────────────────────────────────────────────────────────────────────────────


class TestOutputStructure:
    """Verify all required fields are present in formatted outputs."""

    REQUIRED_FIELDS = {
        "verification",
        "message",
        "headline",
        "level",
        "method",
        "score",
        "flagged",
        "detail",
    }

    def test_sgi_has_all_fields(self):
        out = json.loads(_format_result(sgi(1.0, False)))
        assert self.REQUIRED_FIELDS.issubset(out.keys())
        assert isinstance(out["detail"], str)

    def test_dgi_has_all_fields_plus_note(self):
        out = json.loads(_format_result(dgi(0.5, False)))
        assert self.REQUIRED_FIELDS.issubset(out.keys())
        assert "note" in out

    def test_sgi_output_is_valid_json(self):
        parsed = json.loads(_format_result(sgi(1.0, False)))
        assert isinstance(parsed, dict)

    def test_dgi_output_is_valid_json(self):
        parsed = json.loads(_format_result(dgi(0.5, False)))
        assert isinstance(parsed, dict)


# ─────────────────────────────────────────────────────────────────────────────
# Error handling
# ─────────────────────────────────────────────────────────────────────────────


class TestErrorResponse:
    """Verify _error_response produces structured JSON errors."""

    def test_returns_valid_json(self):
        output = json.loads(_error_response("Something went wrong."))
        assert output["verdict"] == "ERROR"
        assert output["explanation"] == "Something went wrong."
        assert output["flagged"] is None
        assert output["score"] is None

    def test_special_characters_in_message(self):
        output = json.loads(_error_response('Error: "bad input" <>&'))
        assert isinstance(output, dict)
        assert '"bad input"' in output["explanation"]


class TestModelLoadFailure:
    """Verify tools return friendly errors when model loading fails."""

    def test_check_returns_error_on_load_failure(self):
        with patch(
            "groundlens_mcp.server._ensure_loaded",
            side_effect=RuntimeError("Could not load the embedding model."),
        ):
            params = CheckInput(question="Test?", response="Test answer.")
            output = json.loads(_run(groundlens_check(params)))
            assert output["verdict"] == "ERROR"
            assert "embedding model" in output["explanation"]

    def test_sgi_returns_error_on_load_failure(self):
        with patch(
            "groundlens_mcp.server._ensure_loaded",
            side_effect=RuntimeError("groundlens library is not installed"),
        ):
            params = SGIInput(
                question="Test?", context="Some context.", response="Answer."
            )
            output = json.loads(_run(groundlens_sgi(params)))
            assert output["verdict"] == "ERROR"
            assert "not installed" in output["explanation"]

    def test_dgi_returns_error_on_load_failure(self):
        with patch(
            "groundlens_mcp.server._ensure_loaded",
            side_effect=RuntimeError("model download was interrupted"),
        ):
            params = DGIInput(question="Test?", response="Answer.")
            output = json.loads(_run(groundlens_dgi(params)))
            assert output["verdict"] == "ERROR"
            assert "interrupted" in output["explanation"]


class TestScoringFailure:
    """Verify tools return friendly errors when scoring throws."""

    @patch("groundlens_mcp.server._ensure_loaded")
    def test_check_sgi_scoring_error(self, mock_load):
        def boom(**kwargs):
            raise ValueError("embedding dimension mismatch")

        with patch.dict(
            "sys.modules",
            {"groundlens": MagicMock(compute_sgi=boom, compute_dgi=MagicMock())},
        ):
            params = CheckInput(
                question="What?", response="Answer.", context="Some doc."
            )
            output = json.loads(_run(groundlens_check(params)))
            assert output["verdict"] == "ERROR"
            assert "Scoring failed" in output["explanation"]
            assert "embedding dimension mismatch" in output["explanation"]

    @patch("groundlens_mcp.server._ensure_loaded")
    def test_check_dgi_scoring_error(self, mock_load):
        def boom(**kwargs):
            raise RuntimeError("out of memory")

        with patch.dict(
            "sys.modules",
            {"groundlens": MagicMock(compute_sgi=MagicMock(), compute_dgi=boom)},
        ):
            params = CheckInput(question="What?", response="Answer.")
            output = json.loads(_run(groundlens_check(params)))
            assert output["verdict"] == "ERROR"
            assert "out of memory" in output["explanation"]

    @patch("groundlens_mcp.server._ensure_loaded")
    def test_sgi_scoring_error(self, mock_load):
        def boom(**kwargs):
            raise TypeError("unexpected type")

        with patch.dict("sys.modules", {"groundlens": MagicMock(compute_sgi=boom)}):
            params = SGIInput(question="What?", context="Doc.", response="Answer.")
            output = json.loads(_run(groundlens_sgi(params)))
            assert output["verdict"] == "ERROR"
            assert "unexpected type" in output["explanation"]

    @patch("groundlens_mcp.server._ensure_loaded")
    def test_dgi_scoring_error(self, mock_load):
        def boom(**kwargs):
            raise Exception("generic failure")

        with patch.dict("sys.modules", {"groundlens": MagicMock(compute_dgi=boom)}):
            params = DGIInput(question="What?", response="Answer.")
            output = json.loads(_run(groundlens_dgi(params)))
            assert output["verdict"] == "ERROR"
            assert "generic failure" in output["explanation"]
