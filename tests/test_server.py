"""Tests for groundlens MCP server — input validation, formatting, and tool routing."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from unittest.mock import patch, MagicMock

import pytest
from pydantic import ValidationError

from groundlens_mcp.server import (
    CheckInput,
    SGIInput,
    DGIInput,
    _format_sgi_result,
    _format_dgi_result,
    groundlens_check,
    groundlens_sgi,
    groundlens_dgi,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fake result objects (mirror groundlens return types)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class FakeSGIResult:
    value: float
    flagged: bool
    q_dist: float
    ctx_dist: float
    explanation: str


@dataclass
class FakeDGIResult:
    value: float
    flagged: bool
    explanation: str


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
        inp = CheckInput(
            question="Capital of France?",
            response="Paris.",
        )
        assert inp.context is None

    def test_strips_whitespace(self):
        inp = CheckInput(
            question="  What is covered?  ",
            response="  Fire and flood.  ",
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
            SGIInput(
                question="What?",
                context="",
                response="Answer.",
            )

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
# Result formatting
# ─────────────────────────────────────────────────────────────────────────────


class TestFormatSGIResult:
    """Verify SGI result formatting produces valid JSON with expected fields."""

    def test_grounded_result(self):
        result = FakeSGIResult(
            value=1.2345,
            flagged=False,
            q_dist=0.5678,
            ctx_dist=0.4321,
            explanation="Response engaged with context.",
        )
        output = json.loads(_format_sgi_result(result))

        assert output["verdict"] == "GROUNDED"
        assert output["flagged"] is False
        assert output["method"] == "SGI (Semantic Grounding Index)"
        assert output["score"] == 1.2345
        assert output["threshold"] == 0.95
        assert output["detail"]["q_dist"] == 0.5678
        assert output["detail"]["ctx_dist"] == 0.4321
        assert output["detail"]["interpretation"] == "Response engaged with context."
        assert "what_this_means" in output

    def test_flagged_result(self):
        result = FakeSGIResult(
            value=0.7123,
            flagged=True,
            q_dist=0.3,
            ctx_dist=0.42,
            explanation="Response stayed near the question.",
        )
        output = json.loads(_format_sgi_result(result))

        assert output["verdict"] == "HALLUCINATION RISK"
        assert output["flagged"] is True
        assert output["score"] == 0.7123
        assert "not be based on the source material" in output["explanation"]

    def test_score_rounding(self):
        result = FakeSGIResult(
            value=0.123456789,
            flagged=False,
            q_dist=0.111111111,
            ctx_dist=0.222222222,
            explanation="Test.",
        )
        output = json.loads(_format_sgi_result(result))

        assert output["score"] == 0.1235
        assert output["detail"]["q_dist"] == 0.1111
        assert output["detail"]["ctx_dist"] == 0.2222


class TestFormatDGIResult:
    """Verify DGI result formatting produces valid JSON with expected fields."""

    def test_grounded_result(self):
        result = FakeDGIResult(
            value=0.4521,
            flagged=False,
            explanation="Positive directional alignment.",
        )
        output = json.loads(_format_dgi_result(result))

        assert output["verdict"] == "GROUNDED"
        assert output["flagged"] is False
        assert output["method"] == "DGI (Directional Grounding Index)"
        assert output["score"] == 0.4521
        assert output["threshold"] == 0.30
        assert output["detail"]["interpretation"] == "Positive directional alignment."

    def test_flagged_result(self):
        result = FakeDGIResult(
            value=0.1234,
            flagged=True,
            explanation="Anomalous displacement pattern.",
        )
        output = json.loads(_format_dgi_result(result))

        assert output["verdict"] == "HALLUCINATION RISK"
        assert output["flagged"] is True
        assert "geometric patterns associated with hallucination" in output["explanation"]


# ─────────────────────────────────────────────────────────────────────────────
# Tool routing (mock groundlens to avoid loading the model)
# ─────────────────────────────────────────────────────────────────────────────


def _run(coro):
    """Helper to run async tool functions in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestGroundlensCheck:
    """Verify groundlens_check routes to SGI or DGI based on context."""

    @patch("groundlens_mcp.server._ensure_loaded")
    @patch("groundlens_mcp.server.compute_sgi", create=True)
    def test_routes_to_sgi_when_context_provided(self, mock_sgi, mock_load):
        fake = FakeSGIResult(
            value=1.05, flagged=False, q_dist=0.5, ctx_dist=0.4,
            explanation="Grounded.",
        )

        with patch("groundlens_mcp.server.compute_sgi", return_value=fake) as m:
            with patch.dict("sys.modules", {"groundlens": MagicMock(compute_sgi=m, compute_dgi=MagicMock())}):
                params = CheckInput(
                    question="What is covered?",
                    response="Fire and flood.",
                    context="Policy covers fire and flood.",
                )
                result = _run(groundlens_check(params))
                output = json.loads(result)

                assert output["method"] == "SGI (Semantic Grounding Index)"
                assert output["verdict"] == "GROUNDED"

    @patch("groundlens_mcp.server._ensure_loaded")
    @patch("groundlens_mcp.server.compute_dgi", create=True)
    def test_routes_to_dgi_when_no_context(self, mock_dgi, mock_load):
        fake = FakeDGIResult(value=0.45, flagged=False, explanation="Grounded.")

        with patch("groundlens_mcp.server.compute_dgi", return_value=fake) as m:
            with patch.dict("sys.modules", {"groundlens": MagicMock(compute_sgi=MagicMock(), compute_dgi=m)}):
                params = CheckInput(
                    question="Capital of France?",
                    response="Paris.",
                )
                result = _run(groundlens_check(params))
                output = json.loads(result)

                assert output["method"] == "DGI (Directional Grounding Index)"

    @patch("groundlens_mcp.server._ensure_loaded")
    @patch("groundlens_mcp.server.compute_dgi", create=True)
    def test_routes_to_dgi_when_context_is_whitespace(self, mock_dgi, mock_load):
        fake = FakeDGIResult(value=0.45, flagged=False, explanation="Grounded.")

        with patch("groundlens_mcp.server.compute_dgi", return_value=fake) as m:
            with patch.dict("sys.modules", {"groundlens": MagicMock(compute_sgi=MagicMock(), compute_dgi=m)}):
                params = CheckInput(
                    question="Capital of France?",
                    response="Paris.",
                    context="   ",
                )
                result = _run(groundlens_check(params))
                output = json.loads(result)

                assert output["method"] == "DGI (Directional Grounding Index)"


class TestGroundlensSGI:
    """Verify groundlens_sgi tool calls compute_sgi and formats output."""

    @patch("groundlens_mcp.server._ensure_loaded")
    def test_returns_sgi_result(self, mock_load):
        fake = FakeSGIResult(
            value=0.85, flagged=True, q_dist=0.3, ctx_dist=0.35,
            explanation="Context may have been ignored.",
        )

        with patch.dict("sys.modules", {"groundlens": MagicMock(compute_sgi=MagicMock(return_value=fake))}):
            params = SGIInput(
                question="What is covered?",
                context="Policy covers fire.",
                response="I'm not sure.",
            )
            result = _run(groundlens_sgi(params))
            output = json.loads(result)

            assert output["verdict"] == "HALLUCINATION RISK"
            assert output["flagged"] is True
            assert output["score"] == 0.85


class TestGroundlensDGI:
    """Verify groundlens_dgi tool calls compute_dgi and formats output."""

    @patch("groundlens_mcp.server._ensure_loaded")
    def test_returns_dgi_result(self, mock_load):
        fake = FakeDGIResult(
            value=0.15, flagged=True,
            explanation="Anomalous pattern.",
        )

        with patch.dict("sys.modules", {"groundlens": MagicMock(compute_dgi=MagicMock(return_value=fake))}):
            params = DGIInput(
                question="Who invented the internet?",
                response="The internet was invented by Napoleon.",
            )
            result = _run(groundlens_dgi(params))
            output = json.loads(result)

            assert output["verdict"] == "HALLUCINATION RISK"
            assert output["flagged"] is True
            assert output["score"] == 0.15


# ─────────────────────────────────────────────────────────────────────────────
# JSON output structure
# ─────────────────────────────────────────────────────────────────────────────


class TestOutputStructure:
    """Verify all required fields are present in formatted outputs."""

    REQUIRED_SGI_FIELDS = {
        "verdict", "explanation", "method", "score", "threshold",
        "flagged", "detail", "what_this_means",
    }
    REQUIRED_SGI_DETAIL_FIELDS = {"q_dist", "ctx_dist", "interpretation"}

    REQUIRED_DGI_FIELDS = {
        "verdict", "explanation", "method", "score", "threshold",
        "flagged", "detail", "what_this_means",
    }
    REQUIRED_DGI_DETAIL_FIELDS = {"interpretation"}

    def test_sgi_has_all_fields(self):
        result = FakeSGIResult(
            value=1.0, flagged=False, q_dist=0.5, ctx_dist=0.5,
            explanation="Test.",
        )
        output = json.loads(_format_sgi_result(result))
        assert self.REQUIRED_SGI_FIELDS.issubset(output.keys())
        assert self.REQUIRED_SGI_DETAIL_FIELDS.issubset(output["detail"].keys())

    def test_dgi_has_all_fields(self):
        result = FakeDGIResult(value=0.5, flagged=False, explanation="Test.")
        output = json.loads(_format_dgi_result(result))
        assert self.REQUIRED_DGI_FIELDS.issubset(output.keys())
        assert self.REQUIRED_DGI_DETAIL_FIELDS.issubset(output["detail"].keys())

    def test_sgi_output_is_valid_json(self):
        result = FakeSGIResult(
            value=1.0, flagged=False, q_dist=0.5, ctx_dist=0.5,
            explanation='Contains "quotes" and special chars: <>&',
        )
        output = _format_sgi_result(result)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_dgi_output_is_valid_json(self):
        result = FakeDGIResult(
            value=0.5, flagged=False,
            explanation='Contains "quotes" and special chars: <>&',
        )
        output = _format_dgi_result(result)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)
