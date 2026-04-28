# PyPI Release Runbook

This document tracks the current PyPI release status and the repeatable release
process for `pyslang-mcp`.

The current public alpha installs on Linux with:

```bash
pip install --pre pyslang-mcp
```

The public support statement remains intentionally narrow: local-first, stdio,
read-only, alpha, and Linux-validated.

## Current State

Already in place:

- `pyproject.toml` with Hatchling build backend
- package under `src/pyslang_mcp/`
- console script entry point: `pyslang-mcp`
- runtime dependencies:
  - `mcp>=1.27,<2`
  - `pydantic>=2.8,<3`
  - `pyslang>=10,<11`
- CI across Ubuntu Python 3.11 and 3.12
- macOS Python 3.12 CI for basic compatibility
- stdio MCP protocol smoke in CI
- HDL smoke validation on Ubuntu
- package metadata for the public alpha line
- wheel/sdist package smoke in CI
- manual-only release workflow using PyPI Trusted Publishing
- release workflow gate covering lint, type checks, tests, build checks, and
  installed-wheel MCP stdio smoke
- MCP Registry metadata and package ownership marker
- PyPI project and active Trusted Publisher
- public alpha release line on PyPI

Not yet in place:

- completed MCP Registry publication
- non-alpha schema freeze

## Current Install

```bash
pip install --pre pyslang-mcp
pyslang-mcp --help
```

MCP client config for a PyPI install:

```json
{
  "mcpServers": {
    "pyslang-mcp": {
      "command": "pyslang-mcp",
      "args": []
    }
  }
}
```

`--pre` is required while the latest public release is an alpha. Omit `--pre`
after publishing a stable `0.1.0` or later.

## Linux Feasibility

`pyslang-mcp` itself is pure Python, so its wheel should be platform
independent.

The main Linux availability dependency is `pyslang`. `pyslang` 10.0.0 currently
publishes manylinux wheels for CPython 3.11 and 3.12 on:

- `x86_64`
- `aarch64`

That means normal Linux users on those platforms should not need to build
`slang` locally.

For the current alpha releases, the public Linux support statement is:

- Linux x86_64 and aarch64
- Python 3.11 and 3.12
- local stdio MCP transport

Do not claim broad Windows, hosted, or registry-ready support just because the
package may install elsewhere.

## Completed Launch Work

### 1. Polish package metadata

Done in the repo for the first alpha line:

- add `authors`
- add `maintainers` if different from authors
- add `[project.urls]`, at minimum:
  - `Homepage`
  - `Repository`
  - `Issues`
  - `Documentation`
- add Linux classifier:
  - `Operating System :: POSIX :: Linux`
- consider adding:
  - `Typing :: Typed`
  - `Framework :: Pytest` only if useful
- use modern license metadata if supported by the build backend:
  - `license = "Apache-2.0"`
  - `license-files = ["LICENSE"]`

Keep the development status classifier as alpha while publishing alpha
releases:

```toml
"Development Status :: 3 - Alpha"
```

### 2. Add package smoke CI

Done in `.github/workflows/ci.yml`.

The `package-smoke` job:

1. Build wheel and sdist from a clean checkout.
2. Install the wheel in a fresh virtual environment.
3. Run `pyslang-mcp --help`.
4. Launch the installed console script over stdio.
5. Run MCP `initialize`.
6. Run `tools/list`.
7. Run one representative `tools/call`.

Local command shape:

```bash
python -m pip install --upgrade pip build
python -m build --wheel --sdist
python -m venv /tmp/pyslang-mcp-wheel-smoke
/tmp/pyslang-mcp-wheel-smoke/bin/pip install --pre --no-cache-dir dist/*.whl
/tmp/pyslang-mcp-wheel-smoke/bin/pyslang-mcp --help
```

The stdio portion uses `scripts/package_smoke_stdio.py` and points `command` at
the installed console script.

### 3. Add release workflow

Done in `.github/workflows/release.yml`.

Configured trigger:

- `workflow_dispatch` only

Tag pushes do not publish. A release can only start from a manual GitHub
Actions run. The workflow also checks the triggering actor before doing any
build or publish work. By default, the authorized actor is the repository
owner. If the release account ever differs from the repo owner, set the
repository variable `RELEASE_ACTOR` to that GitHub username.

The workflow:

1. Verifies the manual release actor.
2. Checks that the requested version matches `pyproject.toml`,
   `src/pyslang_mcp/__init__.py`, and `server.json`.
3. Checks the MCP Registry README ownership marker.
4. Validates `server.json` against the MCP Registry schema.
5. Runs formatting, lint, type checks, full tests, MCP stdio protocol smoke,
   and HDL smoke.
6. Builds wheel and sdist.
7. Runs `twine check`.
8. Installs the wheel in a fresh virtual environment.
9. Runs the installed console script and installed MCP stdio smoke.
10. Publishes with PyPI Trusted Publishing.
11. Optionally publishes `server.json` to the MCP Registry after the new PyPI
    release is visible with the ownership marker.

Use PyPI Trusted Publishing instead of a long-lived API token.

The publish job needs:

```yaml
permissions:
  id-token: write
```

Then use `pypa/gh-action-pypi-publish` without `username` or `password`.

### 4. Configure PyPI Trusted Publishing

Done. The first upload consumed the pending publisher and created the active
PyPI project.

PyPI configuration:

- PyPI project name: `pyslang-mcp`
- GitHub owner: `ariklapid`
- GitHub repository: `pyslang-mcp`
- workflow filename: `release.yml`
- environment: `pypi`

Using a GitHub environment is strongly recommended so publishing can require
manual approval and can be restricted to trusted branches.

For future releases, keep the active publisher bound to the same workflow and
environment.

### 5. Versioning

Before running the release workflow, bump the package version in:

- `pyproject.toml`
- `src/pyslang_mcp/__init__.py`
- `server.json`
- `CHANGELOG.md`

The release workflow refuses to publish if the manually entered version does
not match the committed metadata.

### 6. Public docs

The package is live. Public install docs now use:

```bash
pip install --pre pyslang-mcp
```

and:

```json
{
  "mcpServers": {
    "pyslang-mcp": {
      "command": "pyslang-mcp",
      "args": []
    }
  }
}
```

Keep the checkout-based install path for contributors.

## Future Release Checklist

Before running the release workflow:

- `ruff format --check src tests scripts`
- `ruff check src tests scripts`
- `pyright`
- `pytest`
- `pytest -q tests/test_mcp_stdio.py`
- `pytest -q tests/test_hdl_smoke.py`
- `python -m build --wheel --sdist`
- `python -m twine check dist/*`
- package smoke passes from a wheel install
- README does not claim registry or hosted availability
- changelog has release notes
- version is bumped

Publish from GitHub Actions only:

1. Push the release commit to `main`.
2. Open Actions -> Release -> Run workflow.
3. Enter the exact version from `pyproject.toml`.
4. Leave `publish_registry` enabled when `server.json` should be published to
   the MCP Registry after PyPI succeeds.

Do not use a tag push as a publish mechanism.

If the PyPI publish job succeeds but the MCP Registry job needs a retry, run
the manual `Publish MCP Registry` workflow with the already published version.
That workflow validates the PyPI marker and `server.json` before calling
`mcp-publisher`, and it does not attempt another PyPI upload.

Verify after publish:

```bash
python -m venv /tmp/pyslang-mcp-pypi-check
/tmp/pyslang-mcp-pypi-check/bin/pip install --upgrade pip
/tmp/pyslang-mcp-pypi-check/bin/pip install --pre pyslang-mcp
/tmp/pyslang-mcp-pypi-check/bin/pyslang-mcp --help
```

If publishing `0.1.0` instead of an alpha version, omit `--pre`.

## Risks

- `pyslang` wheel availability defines the practical Linux install matrix.
- A broken release file cannot be overwritten on PyPI; publish a new version
  instead.
- Trusted Publishing protects against stored token leakage, but the release
  workflow itself must be treated as sensitive infrastructure.

## References

- Python Packaging User Guide: https://packaging.python.org/en/latest/tutorials/packaging-projects/
- PyPI pending trusted publishers: https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/
- PyPI trusted publisher setup: https://docs.pypi.org/trusted-publishers/adding-a-publisher/
- GitHub OIDC for PyPI: https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-pypi
- PyPI trusted publishing security model: https://docs.pypi.org/trusted-publishers/security-model/
