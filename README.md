# pyslang-mcp

[![CI](https://github.com/ariklapid/pyslang-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/ariklapid/pyslang-mcp/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)
![Transport](https://img.shields.io/badge/transport-stdio-informational)

`pyslang-mcp` is a local Model Context Protocol server that gives AI agents
compiler-backed, read-only context for Verilog and SystemVerilog projects.

It wraps [`pyslang`](https://pypi.org/project/pyslang/) so an MCP client can ask
questions against parsed and elaborated HDL instead of plain text:

- What modules, interfaces, and packages are in this filelist?
- What diagnostics does the compiler frontend report?
- What is the instance hierarchy below this top?
- Where is this symbol declared or referenced?
- Did my include paths, defines, and nested `.f` files resolve as expected?

This is not a simulator, synthesizer, waveform viewer, linter replacement, or
RTL refactoring tool. It is a small semantic analysis service for local HDL
checkouts.

> [!NOTE]
> The project is currently alpha. The package and release workflow are prepared
> for the first PyPI alpha, but it has not been published to PyPI or the MCP
> Registry yet. Until then, use the checkout install below.

## Why ASIC And EDA Engineers Might Care

Most AI coding tools are good at searching text. HDL usually needs more than
that.

In real projects, useful answers often depend on filelists, packages, includes,
defines, generate blocks, and hierarchy. `pyslang-mcp` gives an agent a compact
compiler-backed view of that structure, while keeping the server read-only and
scoped to a project root you provide.

Good fits:

- triaging parse and semantic diagnostics before asking an agent to reason
  about RTL
- checking what a `.f` file expands to
- listing design units in a block or small IP
- finding a declaration without chasing comments and stale grep hits
- getting hierarchy and port-connection context for review/debug prompts
- giving workflow agents HDL context without handing them an EDA runtime

## Quickstart

Clone the repo and install it in editable mode:

```bash
git clone https://github.com/ariklapid/pyslang-mcp.git
cd pyslang-mcp
python -m venv .venv
./.venv/bin/pip install -e '.[dev]'
```

Run the local stdio server:

```bash
./.venv/bin/python -m pyslang_mcp
```

The installed console script works too:

```bash
./.venv/bin/pyslang-mcp
```

Run tests:

```bash
./.venv/bin/pytest
```

## MCP Client Config

Use local `stdio`. The MCP client should launch the server on the same machine,
VM, or dev container that can see your RTL checkout.

```json
{
  "mcpServers": {
    "pyslang-mcp": {
      "command": "/absolute/path/to/pyslang-mcp/.venv/bin/python",
      "args": ["-m", "pyslang_mcp"]
    }
  }
}
```

Tool calls must provide a `project_root`. Source paths, filelists, and include
directories may be absolute or relative, but they must stay under that root.

## Minimal Tool Payloads

Analyze explicit files:

```json
{
  "project_root": "/path/to/rtl-project",
  "files": ["rtl/pkg.sv", "rtl/top.sv"],
  "include_dirs": ["include"],
  "defines": {
    "WIDTH": "32"
  },
  "top_modules": ["top"]
}
```

Analyze a filelist:

```json
{
  "project_root": "/path/to/rtl-project",
  "filelist": "compile/project.f"
}
```

Find a symbol:

```json
{
  "project_root": "/path/to/rtl-project",
  "filelist": "compile/project.f",
  "query": "payload",
  "match_mode": "exact",
  "include_references": true
}
```

## Tools

| Need | Tool |
|---|---|
| Load explicit files | `pyslang_parse_files` |
| Load a `.f` filelist | `pyslang_parse_filelist` |
| Get parse and semantic diagnostics | `pyslang_get_diagnostics` |
| List modules, interfaces, and packages | `pyslang_list_design_units` |
| Inspect one design unit | `pyslang_describe_design_unit` |
| Walk the elaborated instance tree | `pyslang_get_hierarchy` |
| Find declarations and references | `pyslang_find_symbol` |
| Summarize syntax node shapes | `pyslang_dump_syntax_tree_summary` |
| Check preprocessing metadata and excerpts | `pyslang_preprocess_files` |
| Get a compact project overview | `pyslang_get_project_summary` |

Typical flow:

1. Start with `pyslang_parse_filelist` or `pyslang_parse_files`.
2. Run `pyslang_get_diagnostics`.
3. Use `pyslang_list_design_units` to see what the compiler frontend found.
4. Use `pyslang_describe_design_unit`, `pyslang_get_hierarchy`, or
   `pyslang_find_symbol` for the actual review/debug question.

## Filelist Support

The current parser intentionally supports a practical subset used by many RTL
flows:

- source file entries
- nested filelists with `-f` and `-F`
- include directories with `+incdir+...`, `-I dir`, and `-Idir`
- defines with `+define+...`, `-D NAME`, and `-DNAME`

Unsupported filelist tokens are reported in the tool output instead of being
silently ignored.

## Example Agent Prompts

Use this server when compiler-backed context matters:

- "Parse `compile/project.f` with `+define+DEBUG` and group diagnostics by
  source file."
- "List every design unit in this project and identify the likely top modules."
- "From `top`, show the instance hierarchy down to depth 4."
- "Describe module `axi_dma_top`: ports, child instances, and declared names."
- "Find the declaration and references for `payload_valid`."
- "Confirm whether `legacy_widget` is instantiated anywhere the elaborator
  sees it."
- "Show the resolved files, include dirs, defines, and unsupported entries from
  this filelist."

For single-line questions, comments, naming searches, or partial/incomplete
source sets, regular `rg`, editor search, or direct file reading is usually
faster and clearer.

## Guardrails

- Read-only MCP tools. No RTL edits, formatting, simulation, or synthesis.
- Strict project-root scoping. Paths outside `project_root` are rejected.
- Compact JSON responses with truncation metadata for large result sets.
- Process-local cache keyed by project config and tracked file mtimes.
- `pyslang_preprocess_files` is summary-oriented. It returns preprocessing
  metadata and source excerpts, not a guaranteed full standalone preprocessed
  stream.
- `streamable-http` exists only as an explicit experimental local transport; it
  is not a secure hosted deployment mode.

## HDL Example Corpus

The repo includes generated HDL examples under
[`examples/hdl`](./examples/hdl/):

- clean reference projects from single modules to small IP-style examples
- intentionally buggy variants labeled `easy`, `medium`, and `hard`
- local validation hooks for both `pyslang` and `verilator --lint-only`

Run the full corpus validator:

```bash
./.venv/bin/python scripts/validate_hdl_examples.py
```

Run the CI smoke subset:

```bash
./.venv/bin/python scripts/validate_hdl_examples.py --smoke-only
```

## Project Status

Implemented:

- `FastMCP` stdio server
- CLI entrypoint via `python -m pyslang_mcp` and `pyslang-mcp`
- project loader with root checks and `.f` parsing
- pyslang-backed diagnostics, design-unit listing, hierarchy, symbol lookup,
  syntax summaries, and project summaries
- bounded in-memory cache
- fixture-backed tests and Ubuntu CI for Python 3.11 and 3.12
- package smoke CI from a built wheel
- PyPI Trusted Publishing release workflow

Not done yet:

- PyPI Trusted Publisher configuration and first release
- MCP Registry publication
- schema freeze for a non-alpha release
- broad platform validation beyond the current Linux-focused CI path

## Development

Useful commands:

```bash
./.venv/bin/ruff check .
./.venv/bin/pyright
./.venv/bin/pytest
```

Architecture and contribution docs:

- [docs/architecture.md](./docs/architecture.md)
- [CONTRIBUTING.md](./CONTRIBUTING.md)
- [pyslang-mcp-plan.md](./pyslang-mcp-plan.md)

## License

Apache-2.0. See [LICENSE](./LICENSE).
