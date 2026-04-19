# Maximum-Coverage Plan for `pyslang-mcp`

This document lays out how `pyslang-mcp` evolves from a narrow V1 surface
(10 tools) into a broadly useful HDL-analysis server (~40 tools across 10
namespaces). The target is that any semantic question `pyslang` can
answer has a named tool, a stable schema, and an efficient reverse-index
path — so an agent wired to this MCP is strictly better off than one
invoking `pyslang` via ad-hoc Python.

Companion documents:

- [`../pyslang-mcp-plan.md`](../pyslang-mcp-plan.md) — original V1 scope
- [`./architecture.md`](./architecture.md) — current microarchitecture
- [`../REMOTE_DEPLOYMENT.md`](../REMOTE_DEPLOYMENT.md) — hosted-deployment direction

## Framing

Today's 10 tools cover a single agent loop: load → diagnose → inventory
→ walk → find → summarize. That is fine for project overviews, but
every second-order question falls off the edge:

- "What's the resolved type of signal X?"
- "Where is module Y instantiated?"
- "What drives port P on instance I?"
- "Does this generate branch elaborate?"
- "Give me the canonical preprocessed text."

Each of those sends the agent to `python -c "import pyslang; …"` — and
the MCP stops being load-bearing.

**Goal:** any semantic question `pyslang` can answer should have a named
tool, grouped by domain, backed by reverse indices so chained queries
stay cheap. Target surface: **~40 tools across 10 namespaces**, roughly
4× today's.

## Design Principles

1. **Schema-first.** Every tool has a Pydantic input and output model;
   every result is composable with another tool via stable IDs.
2. **Namespaced tool names.** `pyslang_parse_*`, `pyslang_diag_*`,
   `pyslang_hier_*`, `pyslang_sym_*`, `pyslang_type_*`, `pyslang_pp_*`,
   `pyslang_elab_*`, `pyslang_proc_*`, `pyslang_sva_*`, `pyslang_cov_*`,
   `pyslang_cfg_*`, `pyslang_query_*`. Agents pick from groups.
3. **Reverse-indexed.** One pass after `build_analysis` produces:
   `name→[decls]`, `location→node`, `symbol→[drivers]`,
   `symbol→[loads]`, `module→[instantiations]`, `type→[uses]`. Stored on
   `AnalysisBundle`. Every lookup becomes O(1) or O(log n).
4. **Composable URIs.** Tools return opaque IDs like
   `pyslang://project/<config_hash>/symbol/<hier_path>` that flow into
   later tool calls without re-parsing.
5. **Honest surfaces.** If `pyslang` cannot do something cleanly, say so
   in the tool description — never silently produce lossy output.

## Target Tool Surface, by Tier

### Tier A — Highest-impact gaps (M6)

**Symbol and type resolution** (6)

- `pyslang_sym_describe(symbol_path)` — declaration, type, attributes
- `pyslang_sym_drivers(symbol_path)` — who writes it
- `pyslang_sym_loads(symbol_path)` — who reads it
- `pyslang_sym_references(symbol_path)` — every AST-accurate reference
- `pyslang_type_resolve(symbol_or_expr)` — canonical type, packed and
  unpacked dimensions
- `pyslang_type_describe(type_name)` — struct members, enum members,
  typedef chain

**Location-driven navigation** (3)

- `pyslang_query_at(file, line, col)` — what symbol or expression lives
  here
- `pyslang_query_goto_def(symbol_path)` — canonical declaration
- `pyslang_query_goto_impl(symbol_path)` — class method body

**Instance and hierarchy depth** (4)

- `pyslang_hier_describe_instance(hier_path)` — resolved parameters,
  all port connections, generate state
- `pyslang_hier_instantiations_of(module_name)` — reverse map
- `pyslang_hier_get_port_connection(hier_path, port)` — per-port detail
- `pyslang_hier_walk(from_path, depth, filters)` — parameterized
  traversal

### Tier B — Closes the `preprocess_files` honesty caveat (M7)

**Source and preprocessing** (4)

- `pyslang_pp_get_text(file, [range])` — real preprocessed text, not a
  summary
- `pyslang_pp_macro_expansions(file)` — resolved macro bodies with
  source locations
- `pyslang_pp_include_graph()` — full include dependency graph
- `pyslang_pp_resolve_include(name, from_file)` — which file resolves

**Diagnostics depth** (3)

- `pyslang_diag_filter(code, severity, path)` — server-side filter
- `pyslang_diag_group_by(code|file|severity)` — aggregated buckets
- `pyslang_diag_explain(code)` — `pyslang`-native explanation of a
  diagnostic code

### Tier C — Elaboration semantics (M8)

**Parameters / generate / defparam / bind / config** (6)

- `pyslang_elab_list_generate_blocks(scope)`
- `pyslang_elab_generate_state(hier_path)` — did it elaborate
- `pyslang_elab_parameter_value(hier_path)` — resolved final value
- `pyslang_elab_list_defparams(project)`
- `pyslang_cfg_list_binds(project)`
- `pyslang_cfg_effective_top(project)`

### Tier D — Procedural, assertions, coverage (M9, M11)

**Procedural** (4)

- `pyslang_proc_list_blocks(module)` — always_ff / always_comb /
  always_latch / initial / final
- `pyslang_proc_describe(hier_path)` — sensitivity list, assigned
  signals
- `pyslang_proc_sensitivity(hier_path)`
- `pyslang_proc_driven_signals(hier_path)`

**Assertions (SVA)** (3)

- `pyslang_sva_list(scope)` — assert / assume / cover / restrict
- `pyslang_sva_describe(hier_path)` — property and sequence
  decomposition
- `pyslang_sva_disablement(hier_path)` — disable-iff context

**Coverage and random** (4)

- `pyslang_cov_list_covergroups(scope)`
- `pyslang_cov_describe_covergroup(hier_path)`
- `pyslang_cov_list_constraints(class_name)`
- `pyslang_cov_describe_constraint(hier_path)`

### Tier E — Composition and agent efficiency (M12)

- `pyslang_query_batch([tool_calls])` — multiple read-only calls in one
  round-trip, shared compilation
- `pyslang_query_index_status()` — index state, cache hit rate, stale
  files — lets an agent plan
- `pyslang_query_explain(hier_path)` — human-readable narrative of what
  is at a path

## Milestones

| # | Milestone | Tools added | Why now |
|---|---|---|---|
| **M6** | Symbol/type + location nav | 9 | #1 gap; unlocks "go to def / type of X" flows |
| **M7** | PP parity + diagnostics depth | 7 | Closes `preprocess_files` honesty caveat; diagnostics at scale |
| **M8** | Elaboration semantics | 6 | The questions simulators answer: generate/param/defparam/bind/config |
| **M9** | Procedural + assertions | 7 | Needed for RTL review and verification agents |
| **M10** | Reverse indices + URI scheme | infra | Makes M6–M9 affordable at scale |
| **M11** | Coverage / random / constraints | 4 | Verification-side completeness |
| **M12** | Batch + agent-planning helpers | 3 | Token efficiency at scale |

**Sequencing rationale.** M6 first because every deep question lands
there; without it the MCP remains inferior to a REPL for anything
beyond inventory. M10 is the infrastructure M6–M9 depend on — ship
indices as an internal detail with M6 and expose them through
`query_index_status` in M12. M7 closes the one explicit README caveat
(`preprocess_files` summary-only). M11 and M12 are
composition/verification layers and can trail the RTL core.

## Infrastructure Required

- **Reverse-index pass.** After `build_analysis`, a one-pass walk
  populates dicts on `AnalysisBundle`. Cost: once per cold cache entry;
  amortized across every tool call on that bundle.
- **Symbol URI scheme.** Opaque string IDs so outputs of tool A flow
  into inputs of tool B without re-parsing paths. URIs include the
  project config hash so stale URIs from a previous compilation cannot
  silently resolve.
- **Per-tool-args cache.** Layered inside `AnalysisCache`:
  `{(project_hash, tool_name, frozen_args): result}`. Repeated identical
  queries become free.
- **Schema freeze policy.** Once a tool ships in a minor, its result
  model is additive-only. Major bumps for removals. Document at the top
  of each `schemas.py` model group.
- **Lexer / preprocessor option surface.** Expose `LexerOptions` and
  richer `PreprocessorOptions` through the project loader — today it is
  a subset.
- **`tools/list` grouping.** Add a custom `x-namespace` field to each
  tool's annotations so IDE UIs can render collapsible groups.

## Testing and Evaluation

- Each new tool ships with: Pydantic schema, unit test on the
  `multi_file` fixture, MCP-level test through `server.call_tool`, and
  a golden JSON snapshot.
- `evaluation.xml` grows from 10 to roughly 50 Q/A pairs, with at least
  one question per namespace that requires chaining 2–3 tools (forcing
  reverse-index use).
- The HDL corpus adds fixtures exercising generate blocks, classes,
  SVA, covergroups, interfaces with modports, binds, and configs. The
  APB timer is the seed for M8; a small UVM-ish verification block is
  the seed for M9 and M11.
- Performance benchmark fixture: a 5k-line SV project. Targets: cold
  tool call under 2s, warm tool call under 100ms, index build under
  500ms, resident memory under 500MB.

## Non-Goals (scope protection)

- No simulation, synthesis, static timing analysis, or formal.
- No code editing or refactoring (would break read-only discipline).
- No autofix generation.
- No interactive debugger state.
- No re-testing of `pyslang` itself — we wrap, we do not re-validate
  upstream.

## Success Criteria

The MCP earns its keep when every one of these holds:

1. **A CLI agent with `python` + `pyslang` cannot answer a typical
   RTL-analysis question faster than the MCP.** Measured on a benchmark
   set of 20 realistic questions; the MCP should win at least 15.
2. **Every question in `evaluation.xml` chains 2+ tools.** Single-tool
   answers indicate missing composition.
3. **Cold-query latency on a 5k-line project is under 2s; warm is
   under 100ms.** Without reverse indices this is unreachable.
4. **At least 3 MCP clients (Claude Desktop, Cursor, Claude Code) ship
   a working config.** Coverage is useless without reach.

## Relationship to Existing Plans

- `pyslang-mcp-plan.md` remains the V1 scope record; this document
  supersedes it only from M6 onward.
- `AGENTS.md` V1 tool list is authoritative for the 10 shipped tools.
  As tools in this plan ship, `AGENTS.md` should update alongside.
- `REMOTE_DEPLOYMENT.md` is orthogonal. Hosted mode reuses whichever
  tool surface the local server exposes.
