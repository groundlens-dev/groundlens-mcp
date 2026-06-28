# Contributing to groundlens-mcp

Thanks for your interest in contributing. This document covers the development
setup, code standards, and the process for submitting changes.

## Development setup

```bash
git clone https://github.com/groundlens-dev/groundlens-mcp.git
cd groundlens-mcp
pip install -e .
pip install pytest pytest-cov pytest-asyncio
```

## Code standards

- **Style:** follow [PEP 8](https://peps.python.org/pep-0008/). Keep code readable and consistent with the surrounding file.
- **Type hints:** add type annotations to public functions and tool handlers.
- **Determinism:** the server must stay deterministic — the same inputs must always produce the same scores. Do not introduce nondeterministic behavior (randomness, time-dependent output) into scoring paths.
- **Docstrings:** document public functions and MCP tools so their purpose and arguments are clear.

## Testing

We use [pytest](https://docs.pytest.org/). All changes must keep the suite green and maintain coverage.

```bash
pytest tests/ -v --cov=groundlens_mcp --cov-report=term-missing
```

CI enforces a **minimum of 75% coverage** (`--cov-fail-under=75`). New functionality should be accompanied by tests.

## Submitting changes

1. Fork the repository and create a feature branch.
2. Make your change, with tests, following the standards above.
3. Ensure `pytest` passes locally and CI is green.
4. Open a pull request describing the change and why. Pull requests are the required path for all changes.

## Reporting issues

- **Bugs and enhancements:** open a [GitHub issue](https://github.com/groundlens-dev/groundlens-mcp/issues) or a [discussion](https://github.com/groundlens-dev/groundlens-mcp/discussions).
- **Security vulnerabilities:** do **not** open a public issue. Follow the process in [SECURITY.md](SECURITY.md).

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating, you agree to uphold it.
