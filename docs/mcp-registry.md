# MCP Registry Publication

This repo is published to the MCP Registry as
`io.github.ariklapid/pyslang-mcp`.

## Server Identity

Registry server name:

```text
io.github.ariklapid/pyslang-mcp
```

The repo root contains `server.json` with that name and a PyPI package entry
for `pyslang-mcp`.

The README contains the PyPI package ownership marker required by the MCP
Registry:

```html
<!-- mcp-name: io.github.ariklapid/pyslang-mcp -->
```

That marker must be present in the README embedded in the PyPI release used for
registry publication.

## Publish Path

MCP Registry publication is part of the manual `Release` GitHub Actions
workflow:

1. The maintainer starts the workflow manually.
2. The workflow verifies the triggering GitHub actor.
3. The workflow runs the release gate and publishes to PyPI.
4. The workflow waits until the new PyPI release is visible with the MCP marker.
5. If `publish_registry` is enabled, the workflow authenticates with GitHub OIDC
   and publishes `server.json` with `mcp-publisher`.

Tag pushes do not publish to PyPI or the MCP Registry.

If PyPI publication succeeds but registry publication needs to be retried, use
the separate manual `Publish MCP Registry` workflow with the already published
version. That workflow does not upload anything to PyPI.

## Release Checklist

Before running the release workflow:

- bump `pyproject.toml`, `src/pyslang_mcp/__init__.py`, and `server.json` to the
  same version
- update `CHANGELOG.md`
- confirm `README.md` still contains the `mcp-name` marker
- confirm `server.json` describes only the supported local stdio package
- keep the README and release docs aligned with the true registry status

## References

- MCP Registry `server.json`: https://modelcontextprotocol.io/registry/server-json
- MCP Registry publishing: https://modelcontextprotocol.io/registry/publishing
- MCP Registry GitHub Actions: https://modelcontextprotocol.io/registry/github-actions
