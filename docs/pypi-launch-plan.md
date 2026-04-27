# PyPI Launch Plan

This plan tracks the work needed to make `pyslang-mcp` installable by anyone
on Linux with:

```bash
pip install pyslang-mcp
```

The first public package should stay technically honest: local-first, stdio,
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

Not yet in place:

- PyPI project
- PyPI Trusted Publisher
- release workflow
- wheel/sdist package smoke
- release notes process
- public install docs that assume PyPI availability

## Linux Feasibility

`pyslang-mcp` itself is pure Python, so its wheel should be platform
independent.

The main Linux availability dependency is `pyslang`. `pyslang` 10.0.0 currently
publishes manylinux wheels for CPython 3.11 and 3.12 on:

- `x86_64`
- `aarch64`

That means normal Linux users on those platforms should not need to build
`slang` locally.

For the first PyPI release, the public Linux support statement should be:

- Linux x86_64 and aarch64
- Python 3.11 and 3.12
- local stdio MCP transport

Do not claim broad Windows, hosted, or registry-ready support just because the
package may install elsewhere.

## Required Pre-Release Work

### 1. Polish package metadata

Update `pyproject.toml` before release:

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

Keep the development status classifier as alpha for the first release:

```toml
"Development Status :: 3 - Alpha"
```

### 2. Add package smoke CI

Add a `package-smoke` job before publishing.

It should:

1. Build wheel and sdist from a clean checkout.
2. Install the wheel in a fresh virtual environment.
3. Run `pyslang-mcp --help`.
4. Launch the installed console script over stdio.
5. Run MCP `initialize`.
6. Run `tools/list`.
7. Run one representative `tools/call`.

Minimum command shape:

```bash
python -m pip install --upgrade pip build
python -m build --wheel --sdist
python -m venv /tmp/pyslang-mcp-wheel-smoke
/tmp/pyslang-mcp-wheel-smoke/bin/pip install dist/*.whl
/tmp/pyslang-mcp-wheel-smoke/bin/pyslang-mcp --help
```

The stdio portion can reuse the client helper pattern in
`tests/test_mcp_stdio.py`, but point `command` at the installed console script.

### 3. Add release workflow

Create `.github/workflows/release.yml`.

Recommended trigger:

- `workflow_dispatch` for the first release
- tags like `v*` after the first release process is proven

The workflow should:

1. Check out the repository.
2. Set up Python 3.12.
3. Install build tooling.
4. Build wheel and sdist.
5. Upload the built distributions as an artifact.
6. Publish with PyPI Trusted Publishing.

Use PyPI Trusted Publishing instead of a long-lived API token.

The publish job needs:

```yaml
permissions:
  id-token: write
```

Then use `pypa/gh-action-pypi-publish` without `username` or `password`.

### 4. Configure PyPI Trusted Publishing

Because `pyslang-mcp` is not published yet, create a pending trusted publisher
on PyPI.

Suggested PyPI configuration:

- PyPI project name: `pyslang-mcp`
- GitHub owner: `ariklapid`
- GitHub repository: `pyslang-mcp`
- workflow filename: `release.yml`
- environment: `pypi`

Using a GitHub environment is strongly recommended so publishing can require
manual approval and can be restricted to trusted branches/tags.

Important: a pending publisher does not reserve the package name. Publish soon
after creating it.

### 5. Decide first public version

Current version:

```toml
version = "0.1.0a0"
```

Recommended first PyPI version:

```toml
version = "0.1.0a1"
```

Use an alpha version while schemas, docs, and client setup are still settling.
Move to `0.1.0` only when the package surface is stable enough that normal
users should install it without opting into pre-release semantics.

### 6. Update docs at release time

After the package is live, update `README.md`:

```bash
pip install pyslang-mcp
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

## Release Checklist

Before tagging:

- `ruff format --check src tests`
- `ruff check src tests`
- `pyright`
- `pytest`
- `pytest -q tests/test_mcp_stdio.py`
- `pytest -q tests/test_hdl_smoke.py`
- package smoke passes from a wheel install
- README does not claim registry or hosted availability
- changelog has release notes
- version is bumped

Tag:

```bash
git tag v0.1.0a1
git push origin v0.1.0a1
```

Verify after publish:

```bash
python -m venv /tmp/pyslang-mcp-pypi-check
/tmp/pyslang-mcp-pypi-check/bin/pip install --upgrade pip
/tmp/pyslang-mcp-pypi-check/bin/pip install --pre pyslang-mcp
/tmp/pyslang-mcp-pypi-check/bin/pyslang-mcp --help
```

If publishing `0.1.0` instead of an alpha version, omit `--pre`.

## Risks

- Package name can be claimed before the pending publisher is used.
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
