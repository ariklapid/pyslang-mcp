"""Core pyslang-backed analysis functions."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Literal

from pyslang import (
    Bag,
    Compilation,
    CompilationOptions,
    DiagnosticEngine,
    PreprocessorOptions,
    SourceManager,
    SyntaxTree,
)

from .cache import project_hash
from .serializers import (
    ensure_jsonable_paths,
    limit_list,
    project_config_json,
    relative_path,
    stabilize_json,
    top_counts,
)
from .types import (
    AnalysisBundle,
    AnalysisIndices,
    JsonValue,
    ProjectConfig,
    ProjectStatusInfo,
    SearchIndexEntry,
)

MatchMode = Literal["exact", "contains", "startswith"]


def build_analysis(project: ProjectConfig) -> AnalysisBundle:
    """Compile a normalized project config into a reusable analysis bundle."""

    source_manager = SourceManager()
    for include_dir in project.include_dirs:
        source_manager.addUserDirectories(str(include_dir))

    bag = Bag()
    if project.include_dirs or project.defines:
        pp_options = PreprocessorOptions()
        if project.include_dirs:
            pp_options.additionalIncludePaths = [str(path) for path in project.include_dirs]
        predefines = []
        for key, value in project.defines:
            predefines.append(key if value is None else f"{key}={value}")
        if predefines:
            pp_options.predefines = predefines
        bag.preprocessorOptions = pp_options
    if project.top_modules:
        compilation_options = CompilationOptions()
        compilation_options.topModules = set(project.top_modules)
        bag.compilationOptions = compilation_options

    compilation = Compilation(bag)
    syntax_trees: dict[Path, Any] = {}
    for file_path in project.files:
        tree = SyntaxTree.fromFile(str(file_path), source_manager, bag)
        syntax_trees[file_path] = tree
        compilation.addSyntaxTree(tree)

    diagnostics = tuple(compilation.getAllDiagnostics())
    tracked_paths = _tracked_paths(project, source_manager)
    bundle = AnalysisBundle(
        project=project,
        project_hash=project_hash(project),
        source_manager=source_manager,
        bag=bag,
        compilation=compilation,
        syntax_trees=syntax_trees,
        diagnostic_engine=DiagnosticEngine(source_manager),
        diagnostics=diagnostics,
        project_status=ProjectStatusInfo(
            status="ok",
            unresolved_references=0,
            diagnostic_count=len(diagnostics),
            error_count=0,
        ),
        tracked_paths=tracked_paths,
        indices=AnalysisIndices(),
    )
    bundle.project_status = _project_status(bundle)
    bundle.indices = _build_indices(bundle)
    return bundle


def parse_summary(bundle: AnalysisBundle) -> dict[str, Any]:
    """Return a concise parse summary for explicit file mode."""

    return _with_project_status(
        bundle,
        {
            "project": project_config_json(bundle.project),
            "parse": _base_summary(bundle),
        },
    )


def filelist_summary(bundle: AnalysisBundle) -> dict[str, Any]:
    """Return a concise parse summary for filelist mode."""

    return _with_project_status(
        bundle,
        {
            "project": project_config_json(bundle.project),
            "parse": _base_summary(bundle),
            "filelist": {
                "primary_input": (
                    relative_path(bundle.project.project_root, bundle.project.primary_input)
                    if bundle.project.primary_input
                    else None
                ),
                "filelists": ensure_jsonable_paths(
                    bundle.project.filelists, bundle.project.project_root
                ),
                "unsupported_entries": list(bundle.project.unsupported_filelist_entries),
            },
        },
    )


def get_project_summary(
    bundle: AnalysisBundle,
    *,
    max_diagnostics: int = 50,
    max_design_units: int = 200,
    max_depth: int = 6,
    max_children: int = 100,
) -> dict[str, Any]:
    """Return a compact project-wide summary."""

    diagnostics = get_diagnostics(bundle, max_items=max_diagnostics)
    units = list_design_units(bundle, max_items=max_design_units)
    hierarchy = get_hierarchy(bundle, max_depth=max_depth, max_children=max_children)
    summary = _with_project_status(
        bundle,
        {
            "project": project_config_json(bundle.project),
            "summary": _base_summary(bundle),
            "diagnostics": diagnostics["summary"],
            "design_units": units["summary"],
            "top_instances": hierarchy["summary"]["top_instances"],
            "tracked_paths": ensure_jsonable_paths(
                bundle.tracked_paths, bundle.project.project_root
            ),
            "limits": {
                "max_diagnostics": max_diagnostics,
                "max_design_units": max_design_units,
                "max_depth": max_depth,
                "max_children": max_children,
            },
        },
    )
    return summary


def get_diagnostics(bundle: AnalysisBundle, *, max_items: int = 200) -> dict[str, Any]:
    """Return parse and semantic diagnostics."""

    diagnostics = [_serialize_diagnostic(bundle, diagnostic) for diagnostic in bundle.diagnostics]
    diagnostics_json, truncation = limit_list(diagnostics, max_items=max_items)
    severity_counts = Counter(
        str(entry["severity"]).lower() for entry in diagnostics if entry.get("severity")
    )
    return _with_project_status(
        bundle,
        {
            "project_root": bundle.project.project_root.as_posix(),
            "summary": {
                "total": len(diagnostics),
                "severity_counts": dict(sorted(severity_counts.items())),
                "truncation": truncation,
            },
            "diagnostics": diagnostics_json,
        },
    )


def list_design_units(bundle: AnalysisBundle, *, max_items: int = 200) -> dict[str, Any]:
    """List project-local modules, interfaces, and packages."""

    units = list(bundle.indices.design_unit_records)
    units_json, truncation = limit_list(units, max_items=max_items)
    type_counts = Counter(str(unit["kind"]) for unit in units)
    return _with_project_status(
        bundle,
        {
            "summary": {
                "total": len(units),
                "by_kind": dict(sorted(type_counts.items())),
                "truncation": truncation,
            },
            "design_units": units_json,
        },
    )


def describe_design_unit(bundle: AnalysisBundle, *, name: str) -> dict[str, Any]:
    """Describe a single project-local design unit by exact name."""

    local_records = list(bundle.indices.design_unit_records)
    exact_matches = list(bundle.indices.design_unit_records_by_name.get(name, ()))
    if len(exact_matches) != 1:
        suggestions = [
            record
            for record in local_records
            if _matches_text(
                query=name,
                match_mode="contains",
                candidates=(
                    str(record["name"]),
                    str(record["hierarchical_path"]),
                    str(record["lexical_path"]),
                ),
            )
            or str(record["name"]).lower() == name.lower()
            or str(record["name"]).lower().startswith(name.lower())
        ][:10]
        return _with_project_status(
            bundle,
            {
                "query": name,
                "found": False,
                "ambiguous": len(exact_matches) > 1,
                "candidates": exact_matches or suggestions,
                "design_unit": None,
            },
        )

    selected_path = str(exact_matches[0]["hierarchical_path"])
    cached_description = bundle.indices.design_unit_description_cache.get(selected_path)
    if cached_description is not None:
        return _with_project_status(bundle, dict(cached_description))

    symbol = bundle.indices.design_unit_symbol_by_key[(name, selected_path)]
    syntax_json = _design_unit_syntax_json(bundle, symbol)
    member_counts = Counter(_collect_member_kinds(syntax_json.get("members", [])))
    description = {
        "query": name,
        "found": True,
        "ambiguous": False,
        "candidates": [],
        "design_unit": {
            "name": symbol.name,
            "kind": getattr(getattr(symbol, "definitionKind", None), "name", symbol.kind.name),
            "symbol_kind": symbol.kind.name,
            "hierarchical_path": str(symbol.hierarchicalPath),
            "lexical_path": str(symbol.lexicalPath),
            "location": _serialize_location(bundle, symbol.location),
            "ports": _extract_ports(syntax_json),
            "member_kind_counts": dict(sorted(member_counts.items())),
            "child_instances": _extract_child_instances(syntax_json),
            "declared_names": _extract_declared_names(syntax_json),
            "instance_count": getattr(symbol, "instanceCount", None),
        },
    }
    bundle.indices.design_unit_description_cache[selected_path] = description
    return _with_project_status(bundle, description)


def get_hierarchy(
    bundle: AnalysisBundle,
    *,
    max_depth: int = 8,
    max_children: int = 100,
) -> dict[str, Any]:
    """Return the elaborated instance hierarchy from `root.topInstances`."""

    instance_map = bundle.indices.instance_map
    children_map = bundle.indices.children_map

    def build_node(path: str, depth: int) -> dict[str, Any]:
        instance = instance_map[path]
        child_paths = children_map.get(path, ())
        node = _serialize_instance(bundle, instance)
        if depth >= max_depth:
            if child_paths:
                node["children"] = []
                node["truncated_children"] = len(child_paths)
            return node

        limited_children = child_paths[:max_children]
        node["children"] = [build_node(child_path, depth + 1) for child_path in limited_children]
        if len(child_paths) > len(limited_children):
            node["truncated_children"] = len(child_paths) - len(limited_children)
        return node

    top_paths = bundle.indices.top_instance_paths
    hierarchy = [build_node(path, depth=1) for path in top_paths if path in instance_map]
    return _with_project_status(
        bundle,
        {
            "summary": {
                "top_instances": [node["hierarchical_path"] for node in hierarchy],
                "total_instances": len(instance_map),
                "max_depth_requested": max_depth,
            },
            "hierarchy": hierarchy,
        },
    )


def find_symbol(
    bundle: AnalysisBundle,
    *,
    query: str,
    match_mode: MatchMode = "exact",
    include_references: bool = True,
    max_results: int = 100,
) -> dict[str, Any]:
    """Find declarations and references matching a symbol name or hierarchical path."""

    declarations = _matching_index_payloads(
        entries=bundle.indices.declaration_entries,
        exact_index=bundle.indices.declaration_exact,
        query=query,
        match_mode=match_mode,
    )
    references = (
        _matching_index_payloads(
            entries=bundle.indices.reference_entries,
            exact_index=bundle.indices.reference_exact,
            query=query,
            match_mode=match_mode,
        )
        if include_references
        else []
    )
    limited_declarations, decl_truncation = limit_list(declarations, max_items=max_results)
    limited_references, ref_truncation = limit_list(references, max_items=max_results)
    return _with_project_status(
        bundle,
        {
            "query": query,
            "match_mode": match_mode,
            "declarations": limited_declarations,
            "references": limited_references,
            "summary": {
                "declaration_count": len(declarations),
                "reference_count": len(references),
                "declaration_truncation": decl_truncation,
                "reference_truncation": ref_truncation,
            },
        },
    )


def dump_syntax_tree_summary(
    bundle: AnalysisBundle,
    *,
    max_files: int = 50,
    max_node_kinds: int = 40,
) -> dict[str, Any]:
    """Summarize syntax tree shapes without dumping raw ASTs."""

    file_summaries: list[dict[str, Any]] = []
    for file_path, tree in sorted(bundle.syntax_trees.items()):
        kind_counts: Counter[str] = Counter()

        def visit(node: Any, _kind_counts: Counter[str] = kind_counts) -> bool:
            _kind_counts[node.kind.name] += 1
            return True

        tree.root.visit(visit)
        top_level_members = [member.kind.name for member in getattr(tree.root, "members", [])]
        includes = [
            {
                "path": include.path,
                "is_system": include.isSystem,
            }
            for include in tree.getIncludeDirectives()
        ]
        file_summaries.append(
            {
                "file": relative_path(bundle.project.project_root, file_path),
                "root_kind": tree.root.kind.name,
                "top_level_members": top_level_members,
                "node_kind_counts": top_counts(kind_counts, max_items=max_node_kinds),
                "include_directives": includes,
            }
        )

    limited_files, truncation = limit_list(file_summaries, max_items=max_files)
    return _with_project_status(
        bundle,
        {
            "summary": {
                "file_count": len(file_summaries),
                "truncation": truncation,
            },
            "files": limited_files,
        },
    )


def preprocess_files(
    bundle: AnalysisBundle,
    *,
    max_files: int = 50,
    max_excerpt_lines: int = 12,
) -> dict[str, Any]:
    """Return conservative preprocessing metadata and source excerpts."""

    results: list[dict[str, Any]] = []
    for file_path, tree in sorted(bundle.syntax_trees.items()):
        source_text = file_path.read_text(encoding="utf-8")
        excerpt = "\n".join(source_text.splitlines()[:max_excerpt_lines])
        results.append(
            {
                "file": relative_path(bundle.project.project_root, file_path),
                "include_directives": [
                    {
                        "path": include.path,
                        "is_system": include.isSystem,
                    }
                    for include in tree.getIncludeDirectives()
                ],
                "source_excerpt": excerpt,
            }
        )

    limited_results, truncation = limit_list(results, max_items=max_files)
    return _with_project_status(
        bundle,
        {
            "mode": "summary_only",
            "note": (
                "This tool returns preprocessing metadata and source excerpts. "
                "A full standalone preprocessed text stream is not claimed here."
            ),
            "summary": {
                "file_count": len(results),
                "truncation": truncation,
            },
            "effective_defines": {key: value for key, value in bundle.project.defines},
            "files": limited_results,
        },
    )


def _base_summary(bundle: AnalysisBundle) -> dict[str, Any]:
    severity_counts = Counter(
        _serialize_diagnostic(bundle, diagnostic)["severity"] for diagnostic in bundle.diagnostics
    )
    return {
        "file_count": len(bundle.project.files),
        "include_dir_count": len(bundle.project.include_dirs),
        "define_count": len(bundle.project.defines),
        "top_module_count": len(bundle.project.top_modules),
        "diagnostic_count": len(bundle.diagnostics),
        "diagnostic_severity_counts": dict(sorted(severity_counts.items())),
    }


def _with_project_status(bundle: AnalysisBundle, payload: dict[str, Any]) -> dict[str, Any]:
    return stabilize_json(
        {
            "project_status": {
                "status": bundle.project_status.status,
                "unresolved_references": bundle.project_status.unresolved_references,
                "diagnostic_count": bundle.project_status.diagnostic_count,
                "error_count": bundle.project_status.error_count,
            },
            **payload,
        }
    )


def _project_status(bundle: AnalysisBundle) -> ProjectStatusInfo:
    error_count = sum(1 for diagnostic in bundle.diagnostics if bool(diagnostic.isError()))
    unresolved_references = sum(
        1
        for diagnostic in bundle.diagnostics
        if bool(diagnostic.isError())
        and _looks_like_unresolved_reference(_format_diagnostic_message(bundle, diagnostic))
    )
    if unresolved_references > 0:
        status: Literal["ok", "degraded", "incomplete"] = "incomplete"
    elif bundle.diagnostics:
        status = "degraded"
    else:
        status = "ok"
    return ProjectStatusInfo(
        status=status,
        unresolved_references=unresolved_references,
        diagnostic_count=len(bundle.diagnostics),
        error_count=error_count,
    )


def _looks_like_unresolved_reference(message: str) -> bool:
    message_lower = message.lower()
    patterns = (
        "undeclared",
        "unresolved",
        "unknown",
        "not declared",
        "could not resolve",
        "not found",
        "does not refer to a visible declaration",
        "no member named",
        "invalid type name",
    )
    return any(pattern in message_lower for pattern in patterns)


def _design_unit_symbols(bundle: AnalysisBundle) -> list[Any]:
    return [*bundle.compilation.getDefinitions(), *bundle.compilation.getPackages()]


def _serialize_diagnostic(bundle: AnalysisBundle, diagnostic: Any) -> dict[str, Any]:
    location = _serialize_location(bundle, diagnostic.location)
    severity = bundle.diagnostic_engine.getSeverity(diagnostic.code, diagnostic.location).name
    return {
        "code": str(diagnostic.code),
        "severity": severity.lower(),
        "message": _format_diagnostic_message(bundle, diagnostic),
        "args": [str(argument) for argument in diagnostic.args],
        "location": location,
        "line_excerpt": _line_excerpt(bundle, location),
        "is_error": bool(diagnostic.isError()),
    }


def _serialize_location(bundle: AnalysisBundle, location: Any) -> dict[str, Any] | None:
    if location is None:
        return None
    try:
        full_path = Path(bundle.source_manager.getFullPath(location.buffer)).resolve(strict=False)
    except Exception:
        return None
    if not full_path.exists():
        return None
    try:
        full_path.relative_to(bundle.project.project_root)
    except ValueError:
        return None
    return {
        "path": relative_path(bundle.project.project_root, full_path),
        "line": bundle.source_manager.getLineNumber(location),
        "column": bundle.source_manager.getColumnNumber(location),
    }


def _serialize_range_location(bundle: AnalysisBundle, source_range: Any) -> dict[str, Any] | None:
    location = _serialize_location(bundle, source_range.start)
    if location is None:
        return None
    location["end_line"] = bundle.source_manager.getLineNumber(source_range.end)
    location["end_column"] = bundle.source_manager.getColumnNumber(source_range.end)
    return location


def _line_excerpt(bundle: AnalysisBundle, location: dict[str, Any] | None) -> str | None:
    if location is None:
        return None
    path = bundle.project.project_root / str(location["path"])
    line_number = int(location["line"])
    return _read_line(Path(path), line_number)


def _read_line(path: Path, line_number: int) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    if line_number < 1 or line_number > len(lines):
        return None
    return lines[line_number - 1].rstrip()


def _format_diagnostic_message(bundle: AnalysisBundle, diagnostic: Any) -> str:
    message = bundle.diagnostic_engine.getMessage(diagnostic.code)
    arguments = [str(argument) for argument in diagnostic.args]
    try:
        return message.format(*arguments)
    except (IndexError, KeyError, ValueError):
        replacements = iter(arguments)
        return re.sub(r"(?<!\{)\{\}(?!\})", lambda _: next(replacements, "{}"), message)


def _serialize_design_unit_record(bundle: AnalysisBundle, symbol: Any) -> dict[str, Any] | None:
    location = _serialize_location(bundle, symbol.location)
    if location is None:
        return None
    return {
        "name": symbol.name,
        "kind": getattr(getattr(symbol, "definitionKind", None), "name", symbol.kind.name),
        "symbol_kind": symbol.kind.name,
        "hierarchical_path": str(symbol.hierarchicalPath),
        "lexical_path": str(symbol.lexicalPath),
        "instance_count": getattr(symbol, "instanceCount", None),
        "location": location,
    }


def _tracked_paths(project: ProjectConfig, source_manager: Any) -> tuple[Path, ...]:
    tracked: set[Path] = set(project.files) | set(project.filelists)
    for buffer_id in source_manager.getAllBuffers():
        full_path = Path(source_manager.getFullPath(buffer_id)).resolve(strict=False)
        if full_path == Path(".") or not full_path.exists():
            continue
        try:
            full_path.relative_to(project.project_root)
        except ValueError:
            continue
        tracked.add(full_path)
    return tuple(sorted(tracked))


def _serialize_instance(bundle: AnalysisBundle, instance: Any) -> dict[str, Any]:
    return {
        "name": instance.name,
        "definition": getattr(getattr(instance, "definition", None), "name", None),
        "hierarchical_path": str(instance.hierarchicalPath),
        "location": _serialize_location(bundle, instance.location),
        "port_connections": [
            {
                "port": connection.port.name,
                "expression_kind": connection.expression.kind.name,
                "snippet": _source_snippet(bundle, connection.expression.sourceRange),
                "symbol": getattr(getattr(connection.expression, "symbol", None), "name", None),
            }
            for connection in instance.portConnections
        ],
    }


def _source_snippet(bundle: AnalysisBundle, source_range: Any, *, limit: int = 80) -> str | None:
    if source_range is None:
        return None
    try:
        text = bundle.source_manager.getSourceText(source_range.start.buffer)
    except Exception:
        return None
    snippet = text[source_range.start.offset : source_range.end.offset].replace("\x00", "").strip()
    return snippet[:limit] if snippet else None


def _build_indices(bundle: AnalysisBundle) -> AnalysisIndices:
    design_unit_symbols = tuple(sorted(_design_unit_symbols(bundle), key=lambda item: item.name))

    design_unit_records: list[dict[str, JsonValue]] = []
    design_unit_records_by_name: defaultdict[str, list[dict[str, JsonValue]]] = defaultdict(list)
    design_unit_symbol_by_key: dict[tuple[str, str], Any] = {}
    for symbol in design_unit_symbols:
        record = _serialize_design_unit_record(bundle, symbol)
        if record is None:
            continue
        design_unit_records.append(record)
        design_unit_records_by_name[str(record["name"])].append(record)
        design_unit_symbol_by_key[(str(record["name"]), str(record["hierarchical_path"]))] = symbol

    declaration_entries: list[SearchIndexEntry] = []
    declaration_exact: defaultdict[str, list[dict[str, JsonValue]]] = defaultdict(list)
    declaration_seen: set[tuple[str, str, str | None]] = set()
    for symbol in design_unit_symbols:
        entry = _declaration_entry(bundle=bundle, symbol=symbol, seen=declaration_seen)
        if entry is not None:
            declaration_entries.append(entry)
            _add_exact_payload(declaration_exact, entry)

    reference_entries: list[SearchIndexEntry] = []
    reference_exact: defaultdict[str, list[dict[str, JsonValue]]] = defaultdict(list)
    reference_seen: set[tuple[str, str, str | None, str | None]] = set()

    def visit(symbol: Any) -> bool:
        if getattr(symbol, "name", None):
            entry = _declaration_entry(bundle=bundle, symbol=symbol, seen=declaration_seen)
            if entry is not None:
                declaration_entries.append(entry)
                _add_exact_payload(declaration_exact, entry)
        for entry in _collect_reference_entries(bundle=bundle, symbol=symbol, seen=reference_seen):
            reference_entries.append(entry)
            _add_exact_payload(reference_exact, entry)
        return True

    bundle.compilation.getRoot().visit(visit)
    instance_map, children_map, top_instance_paths = _instance_index(bundle)

    return AnalysisIndices(
        design_unit_symbols=design_unit_symbols,
        design_unit_records=tuple(design_unit_records),
        design_unit_records_by_name={
            name: tuple(records) for name, records in design_unit_records_by_name.items()
        },
        design_unit_symbol_by_key=design_unit_symbol_by_key,
        declaration_entries=tuple(declaration_entries),
        declaration_exact={name: tuple(records) for name, records in declaration_exact.items()},
        reference_entries=tuple(reference_entries),
        reference_exact={name: tuple(records) for name, records in reference_exact.items()},
        instance_map=instance_map,
        children_map=children_map,
        top_instance_paths=top_instance_paths,
    )


def _instance_index(
    bundle: AnalysisBundle,
) -> tuple[dict[str, Any], dict[str | None, tuple[str, ...]], tuple[str, ...]]:
    instance_map: dict[str, Any] = {}
    children_map_lists: defaultdict[str | None, list[str]] = defaultdict(list)

    def visit(symbol: Any) -> bool:
        if getattr(symbol, "kind", None) and symbol.kind.name == "Instance":
            path = str(symbol.hierarchicalPath)
            instance_map[path] = symbol
            parent = path.rsplit(".", 1)[0] if "." in path else None
            children_map_lists[parent].append(path)
        return True

    bundle.compilation.getRoot().visit(visit)
    children_map = {
        parent: tuple(sorted(child_paths)) for parent, child_paths in children_map_lists.items()
    }
    top_instance_paths = tuple(
        str(instance.hierarchicalPath) for instance in bundle.compilation.getRoot().topInstances
    )
    return instance_map, children_map, top_instance_paths


def _matches_text(query: str, match_mode: MatchMode, candidates: Any) -> bool:
    query_lower = query.lower()
    for candidate in candidates:
        if candidate is None:
            continue
        candidate_lower = candidate.lower()
        if match_mode == "exact" and candidate_lower == query_lower:
            return True
        if match_mode == "contains" and query_lower in candidate_lower:
            return True
        if match_mode == "startswith" and candidate_lower.startswith(query_lower):
            return True
    return False


def _normalized_candidates(candidates: set[str | None]) -> tuple[str, ...]:
    normalized = {
        candidate.strip().lower()
        for candidate in candidates
        if isinstance(candidate, str) and candidate.strip()
    }
    return tuple(sorted(normalized))


def _symbol_search_candidates(symbol: Any) -> set[str | None]:
    return {
        getattr(symbol, "name", None),
        str(getattr(symbol, "hierarchicalPath", "")),
        str(getattr(symbol, "lexicalPath", "")),
    }


def _leaf_type_name(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if "::" in cleaned:
        cleaned = cleaned.rsplit("::", 1)[-1]
    if "." in cleaned:
        cleaned = cleaned.rsplit(".", 1)[-1]
    cleaned = cleaned.strip()
    return cleaned or None


def _declaration_entry(
    *,
    bundle: AnalysisBundle,
    symbol: Any,
    seen: set[tuple[str, str, str | None]],
) -> SearchIndexEntry | None:
    location = _serialize_location(bundle, getattr(symbol, "location", None))
    path = str(getattr(symbol, "hierarchicalPath", getattr(symbol, "name", "")))
    kind = getattr(getattr(symbol, "kind", None), "name", type(symbol).__name__)
    key = (kind, path, location["path"] if location else None)
    if key in seen:
        return None
    seen.add(key)
    payload: dict[str, JsonValue] = {
        "name": getattr(symbol, "name", None),
        "kind": kind,
        "hierarchical_path": path,
        "lexical_path": str(getattr(symbol, "lexicalPath", getattr(symbol, "name", ""))),
        "location": location,
    }
    return SearchIndexEntry(
        candidates=_normalized_candidates(
            {
                getattr(symbol, "name", None),
                path,
                str(getattr(symbol, "lexicalPath", getattr(symbol, "name", ""))),
            }
        ),
        payload=payload,
    )


def _collect_reference_entries(
    *,
    bundle: AnalysisBundle,
    symbol: Any,
    seen: set[tuple[str, str, str | None, str | None]],
) -> list[SearchIndexEntry]:
    entries: list[SearchIndexEntry] = []
    symbol_type_name = type(symbol).__name__

    if symbol_type_name == "NamedValueExpression" and getattr(symbol, "symbol", None):
        referenced_symbol = symbol.symbol
        entry = _make_reference_entry(
            bundle=bundle,
            search_candidates=_symbol_search_candidates(referenced_symbol),
            source_kind="named_value",
            target_symbol=referenced_symbol,
            location=_serialize_range_location(bundle, symbol.sourceRange),
            snippet=_source_snippet(bundle, symbol.sourceRange),
            seen=seen,
        )
        if entry is not None:
            entries.append(entry)

    if symbol_type_name == "WildcardImportSymbol":
        package_name = getattr(symbol, "packageName", None)
        entry = _make_reference_entry(
            bundle=bundle,
            search_candidates={package_name},
            source_kind="package_import",
            target_symbol=getattr(symbol, "package", None) or symbol,
            location=_serialize_location(bundle, getattr(symbol, "location", None)),
            snippet=_source_snippet(bundle, getattr(symbol.syntax, "sourceRange", None)),
            seen=seen,
        )
        if entry is not None:
            entries.append(entry)

    if symbol_type_name == "InstanceSymbol":
        definition = getattr(symbol, "definition", None)
        if definition is not None:
            location = _serialize_location(bundle, getattr(symbol, "location", None))
            entry = _make_reference_entry(
                bundle=bundle,
                search_candidates=_symbol_search_candidates(definition),
                source_kind="instance_definition",
                target_symbol=definition,
                location=location,
                snippet=_line_excerpt(bundle, location),
                seen=seen,
            )
            if entry is not None:
                entries.append(entry)

    declared_type = getattr(symbol, "declaredType", None)
    declared_type_syntax = getattr(declared_type, "typeSyntax", None)
    if (
        symbol_type_name in {"VariableSymbol", "PortSymbol", "TypeAliasType"}
        and declared_type_syntax
    ):
        type_text = str(getattr(symbol, "type", "")) or str(
            getattr(getattr(declared_type, "type", None), "canonicalType", "")
        )
        declared_type_text = _source_snippet(bundle, declared_type_syntax.sourceRange)
        entry = _make_reference_entry(
            bundle=bundle,
            search_candidates={
                type_text,
                declared_type_text,
                _leaf_type_name(type_text),
                _leaf_type_name(declared_type_text),
            },
            source_kind="declared_type",
            target_symbol=symbol,
            location=_serialize_location(bundle, getattr(symbol, "location", None)),
            snippet=_source_snippet(bundle, declared_type_syntax.sourceRange),
            seen=seen,
        )
        if entry is not None:
            entries.append(entry)

    return entries


def _make_reference_entry(
    *,
    bundle: AnalysisBundle,
    search_candidates: set[str | None],
    source_kind: str,
    target_symbol: Any,
    location: dict[str, Any] | None,
    snippet: str | None,
    seen: set[tuple[str, str, str | None, str | None]],
) -> SearchIndexEntry | None:
    target_path = str(
        getattr(target_symbol, "hierarchicalPath", getattr(target_symbol, "name", ""))
    )
    target_kind = getattr(target_symbol, "kind", None)
    key = (
        source_kind,
        target_path,
        location["path"] if location else None,
        snippet,
    )
    if key in seen:
        return None
    seen.add(key)
    payload: dict[str, JsonValue] = {
        "name": getattr(target_symbol, "name", None),
        "target_kind": target_kind.name
        if target_kind is not None
        else type(target_symbol).__name__,
        "target_path": target_path,
        "reference_kind": source_kind,
        "location": location,
        "snippet": snippet,
    }
    return SearchIndexEntry(
        candidates=_normalized_candidates(
            search_candidates
            | {
                getattr(target_symbol, "name", None),
                target_path,
            }
        ),
        payload=payload,
    )


def _add_exact_payload(
    exact_index: defaultdict[str, list[dict[str, JsonValue]]],
    entry: SearchIndexEntry,
) -> None:
    for candidate in entry.candidates:
        exact_index[candidate].append(entry.payload)


def _matching_index_payloads(
    *,
    entries: tuple[SearchIndexEntry, ...],
    exact_index: dict[str, tuple[dict[str, JsonValue], ...]],
    query: str,
    match_mode: MatchMode,
) -> list[dict[str, JsonValue]]:
    if match_mode == "exact":
        return list(exact_index.get(query.lower(), ()))
    return [
        entry.payload
        for entry in entries
        if _matches_text(query=query, match_mode=match_mode, candidates=entry.candidates)
    ]


def _design_unit_syntax_json(bundle: AnalysisBundle, symbol: Any) -> dict[str, Any]:
    return json.loads(symbol.syntax.to_json())


def _collect_member_kinds(members: list[dict[str, Any]]) -> list[str]:
    kinds: list[str] = []
    for member in members:
        kind = member.get("kind")
        if isinstance(kind, str):
            kinds.append(kind)
    return kinds


def _extract_ports(syntax_json: dict[str, Any]) -> list[dict[str, Any]]:
    header = syntax_json.get("header", {})
    port_list = header.get("ports", {})
    ports: list[dict[str, Any]] = []
    for port in port_list.get("ports", []):
        if not isinstance(port, dict):
            continue
        if port.get("kind") not in {"ImplicitAnsiPort", "ExplicitAnsiPort"}:
            continue
        declarator = port.get("declarator", {})
        header_json = port.get("header", {})
        name = (
            declarator.get("name", {}).get("text")
            or port.get("name", {}).get("text")
            or port.get("externalName", {}).get("text")
        )
        if not name:
            continue
        direction = header_json.get("direction", {}).get("text")
        data_type = header_json.get("dataType", {}).get("kind")
        ports.append(
            {
                "name": name,
                "direction": direction,
                "data_type_kind": data_type,
            }
        )
    return ports


def _extract_child_instances(syntax_json: dict[str, Any]) -> list[dict[str, Any]]:
    instances: list[dict[str, Any]] = []
    for member in syntax_json.get("members", []):
        if not isinstance(member, dict) or member.get("kind") != "HierarchyInstantiation":
            continue
        definition_name = member.get("type", {}).get("text")
        for instance in member.get("instances", []):
            if not isinstance(instance, dict):
                continue
            instance_name = instance.get("decl", {}).get("name", {}).get("text")
            if instance_name:
                instances.append({"name": instance_name, "definition": definition_name})
    return instances


def _extract_declared_names(syntax_json: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for member in syntax_json.get("members", []):
        if not isinstance(member, dict):
            continue
        kind = member.get("kind")
        if kind == "DataDeclaration":
            for declarator in member.get("declarators", []):
                if isinstance(declarator, dict):
                    name = declarator.get("name", {}).get("text")
                    if name:
                        names.append(name)
        elif kind == "TypeAliasDeclaration":
            name = member.get("name", {}).get("text")
            if name:
                names.append(name)
    return names
