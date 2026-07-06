"""Tests for groundlens MCP server — input validation, formatting, and tool routing.

These tests are self-contained: they mock the ``groundlens`` module
(``compute_sgi``, ``compute_dgi``, ``verdict``) so CI needs neither the library
nor its ML stack. The MCP's job is the JSON wiring; the real verdict wording and
thresholds are covered by groundlens's own test suite.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
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
# Lightweight stand-ins for the groundlens types (no library import needed)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class FakeResult:
    """A groundlens result carrier. The tools log ``.value`` and ``.flagged``;
    ``_format_result`` reads ``.flagged`` and hands the object to verdict()."""

    flagged: bool = False
    value: float = 0.0


@dataclass
class FakeVerdict:
    """Mirrors the surface of groundlens.verdict.Verdict used by _format_result."""

    label: str
    message: str
    level: str
    metric_name: str
    score: float
    detail: str
    note: str = ""

    def line(self) -> str:
        abbr = "SGI" if "Semantic" in self.metric_name else "DGI"
        return (
            f"VERIFICATION: {self.label} ({self.metric_name} - {abbr}={self.score:.2f})"
        )


def _gl_module(verdict_obj=None, **compute) -> MagicMock:
    """Build a fake ``groundlens`` module for patch.dict(sys.modules)."""
    m = MagicMock()
    for name, fn in compute.items():
        setattr(m, name, fn)
    if verdict_obj is not None:
        m.verdict = MagicMock(return_value=verdict_obj)
    return m


def _sgi_verdict(label="Supported by the document", level="ok", score=1.23):
    return FakeVerdict(
        label=label,
        message="msg",
        level=level,
        metric_name="Semantic Grounding Index",
        score=score,
        detail="distance to source 0.43, distance to question 0.57",
    )


def _dgi_verdict(label="Looks grounded", level="ok", score=0.41):
    return FakeVerdict(
        label=label,
        message="msg",
        level=level,
        metric_name="Directional Grounding Index",
        score=score,
        detail="commitment (how far the answer moved from the question) 1.02",
        note="No source given — judged by the shape of the answer.",
    )


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
# Result formatting — _format_result maps a verdict into the tool JSON
# ─────────────────────────────────────────────────────────────────────────────


class TestFormatResultSGI:
    """SGI-style verdicts pass through into the JSON payload."""

    def test_supported(self):
        v = _sgi_verdict(label="Supported by the document", level="ok", score=1.23)
        with patch.dict("sys.modules", {"groundlens": _gl_module(verdict_obj=v)}):
            out = json.loads(_format_result(FakeResult(flagged=False)))
        assert out["verification"] == "Supported by the document"
        assert out["level"] == "ok"
        assert out["flagged"] is False
        assert out["method"] == "Semantic Grounding Index"
        assert out["score"] == 1.23
        assert out["headline"].startswith("VERIFICATION: Supported by the document")
        assert "distance to source" in out["detail"]
        assert "note" not in out

    def test_not_supported(self):
        v = _sgi_verdict(
            label="Not supported by the document", level="risk", score=0.71
        )
        with patch.dict("sys.modules", {"groundlens": _gl_module(verdict_obj=v)}):
            out = json.loads(_format_result(FakeResult(flagged=True)))
        assert out["verification"] == "Not supported by the document"
        assert out["level"] == "risk"
        assert out["flagged"] is True

    def test_score_two_decimals(self):
        v = _sgi_verdict(score=1.239)
        with patch.dict("sys.modules", {"groundlens": _gl_module(verdict_obj=v)}):
            out = json.loads(_format_result(FakeResult(flagged=False)))
        assert out["score"] == 1.24


class TestFormatResultDGI:
    """DGI-style verdicts pass through, including the no-source note."""

    def test_looks_grounded(self):
        v = _dgi_verdict(label="Looks grounded", level="ok", score=0.41)
        with patch.dict("sys.modules", {"groundlens": _gl_module(verdict_obj=v)}):
            out = json.loads(_format_result(FakeResult(flagged=False)))
        assert out["verification"] == "Looks grounded"
        assert out["level"] == "ok"
        assert out["method"] == "Directional Grounding Index"
        assert out["score"] == 0.41
        assert "note" in out
        assert out["note"].startswith("No source")
        assert "commitment" in out["detail"]

    def test_not_grounded(self):
        v = _dgi_verdict(label="Not grounded", level="risk", score=-0.12)
        with patch.dict("sys.modules", {"groundlens": _gl_module(verdict_obj=v)}):
            out = json.loads(_format_result(FakeResult(flagged=True)))
        assert out["verification"] == "Not grounded"
        assert out["level"] == "risk"


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
        with patch.dict(
            "sys.modules", {"groundlens": _gl_module(verdict_obj=_sgi_verdict())}
        ):
            out = json.loads(_format_result(FakeResult(flagged=False)))
        assert self.REQUIRED_FIELDS.issubset(out.keys())
        assert isinstance(out["detail"], str)

    def test_dgi_has_all_fields_plus_note(self):
        with patch.dict(
            "sys.modules", {"groundlens": _gl_module(verdict_obj=_dgi_verdict())}
        ):
            out = json.loads(_format_result(FakeResult(flagged=False)))
        assert self.REQUIRED_FIELDS.issubset(out.keys())
        assert "note" in out


# ─────────────────────────────────────────────────────────────────────────────
# Tool routing — mock compute_sgi/compute_dgi + verdict on the groundlens module
# ─────────────────────────────────────────────────────────────────────────────


def _run(coro):
    """Helper to run async tool functions in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestGroundlensCheck:
    """Verify groundlens_check routes to SGI or DGI based on context."""

    @patch("groundlens_mcp.server._ensure_loaded")
    def test_routes_to_sgi_when_context_provided(self, mock_load):
        gl = _gl_module(
            verdict_obj=_sgi_verdict(),
            compute_sgi=MagicMock(return_value=FakeResult(False)),
            compute_dgi=MagicMock(),
        )
        with patch.dict("sys.modules", {"groundlens": gl}):
            params = CheckInput(
                question="What is covered?",
                response="Fire and flood.",
                context="Policy covers fire and flood.",
            )
            output = json.loads(_run(groundlens_check(params)))
            assert output["method"] == "Semantic Grounding Index"

    @patch("groundlens_mcp.server._ensure_loaded")
    def test_routes_to_dgi_when_no_context(self, mock_load):
        gl = _gl_module(
            verdict_obj=_dgi_verdict(),
            compute_sgi=MagicMock(),
            compute_dgi=MagicMock(return_value=FakeResult(False)),
        )
        with patch.dict("sys.modules", {"groundlens": gl}):
            params = CheckInput(question="Capital of France?", response="Paris.")
            output = json.loads(_run(groundlens_check(params)))
            assert output["method"] == "Directional Grounding Index"

    @patch("groundlens_mcp.server._ensure_loaded")
    def test_routes_to_dgi_when_context_is_whitespace(self, mock_load):
        gl = _gl_module(
            verdict_obj=_dgi_verdict(),
            compute_sgi=MagicMock(),
            compute_dgi=MagicMock(return_value=FakeResult(False)),
        )
        with patch.dict("sys.modules", {"groundlens": gl}):
            params = CheckInput(
                question="Capital of France?", response="Paris.", context="   "
            )
            output = json.loads(_run(groundlens_check(params)))
            assert output["method"] == "Directional Grounding Index"


class TestGroundlensSGI:
    """Verify groundlens_sgi tool calls compute_sgi and formats output."""

    @patch("groundlens_mcp.server._ensure_loaded")
    def test_returns_sgi_result(self, mock_load):
        gl = _gl_module(
            verdict_obj=_sgi_verdict(
                label="Not supported by the document", level="risk", score=0.85
            ),
            compute_sgi=MagicMock(return_value=FakeResult(True)),
        )
        with patch.dict("sys.modules", {"groundlens": gl}):
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
        gl = _gl_module(
            verdict_obj=_dgi_verdict(
                label="Partly grounded", level="review", score=0.15
            ),
            compute_dgi=MagicMock(return_value=FakeResult(True)),
        )
        with patch.dict("sys.modules", {"groundlens": gl}):
            params = DGIInput(
                question="Who invented the internet?",
                response="The internet was invented by Napoleon.",
            )
            output = json.loads(_run(groundlens_dgi(params)))
            assert output["verification"] == "Partly grounded"
            assert output["flagged"] is True
            assert output["score"] == 0.15


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
            {"groundlens": _gl_module(compute_sgi=boom, compute_dgi=MagicMock())},
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
            {"groundlens": _gl_module(compute_sgi=MagicMock(), compute_dgi=boom)},
        ):
            params = CheckInput(question="What?", response="Answer.")
            output = json.loads(_run(groundlens_check(params)))
            assert output["verdict"] == "ERROR"
            assert "out of memory" in output["explanation"]

    @patch("groundlens_mcp.server._ensure_loaded")
    def test_sgi_scoring_error(self, mock_load):
        def boom(**kwargs):
            raise TypeError("unexpected type")

        with patch.dict("sys.modules", {"groundlens": _gl_module(compute_sgi=boom)}):
            params = SGIInput(question="What?", context="Doc.", response="Answer.")
            output = json.loads(_run(groundlens_sgi(params)))
            assert output["verdict"] == "ERROR"
            assert "unexpected type" in output["explanation"]

    @patch("groundlens_mcp.server._ensure_loaded")
    def test_dgi_scoring_error(self, mock_load):
        def boom(**kwargs):
            raise Exception("generic failure")

        with patch.dict("sys.modules", {"groundlens": _gl_module(compute_dgi=boom)}):
            params = DGIInput(question="What?", response="Answer.")
            output = json.loads(_run(groundlens_dgi(params)))
            assert output["verdict"] == "ERROR"
            assert "generic failure" in output["explanation"]
