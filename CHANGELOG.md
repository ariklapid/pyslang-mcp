# Changelog

## Unreleased

## 0.1.0a3 - 2026-04-28

- Added MCP Registry package verification metadata and `server.json`.
- Hardened the release workflow so PyPI publishing depends on lint, type,
  tests, build checks, and an installed-wheel MCP stdio smoke.
- Added MCP Registry publishing after the PyPI release job.
- Restricted release publishing to a manually triggered GitHub Actions workflow.

## 0.1.0a2 - 2026-04-28

- Added an explicit `httpx>=0.27.1,<0.29` runtime bound so
  `pip install --pre pyslang-mcp` does not resolve to incompatible `httpx` 1.0
  development releases through transitive MCP dependencies.

## 0.1.0a1 - 2026-04-28

- Added typed MCP tool result schemas and structured tool errors.
- Bounded the process-local analysis cache with LRU-style eviction.
- Improved filelist comment handling, test isolation, and repo docs hygiene.
- Added evaluation and contribution artifacts expected for the alpha-to-release path.
- Prepared the first PyPI alpha with package metadata, wheel smoke CI, and a
  Trusted Publishing release workflow.
