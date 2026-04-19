# Contributing

`pyslang-mcp` is still alpha. Keep changes narrow, read-only, and technically honest.

## Development Setup

```bash
python -m venv .venv
./.venv/bin/pip install -e '.[dev]'
```

## Local Checks

```bash
ruff format src tests scripts
ruff check src tests scripts
pyright
pytest --cov=src/pyslang_mcp --cov-report=term-missing:skip-covered -q
```

## Repo Expectations

- Keep all MCP tools read-only.
- Do not allow path access outside the declared `project_root`.
- Prefer small analysis-core changes before MCP wrapper changes.
- Update `README.md` and `AGENTS.md` when implementation reality changes.
- Add or extend fixture-backed tests for behavior changes.
