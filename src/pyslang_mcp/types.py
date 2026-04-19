"""Shared internal types for pyslang-mcp."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """Normalized, read-only project configuration."""

    project_root: Path
    files: tuple[Path, ...]
    include_dirs: tuple[Path, ...]
    defines: tuple[tuple[str, str | None], ...]
    top_modules: tuple[str, ...]
    filelists: tuple[Path, ...] = ()
    source: Literal["files", "filelist"] = "files"
    primary_input: Path | None = None
    unsupported_filelist_entries: tuple[str, ...] = ()

    def defines_dict(self) -> dict[str, str | None]:
        return dict(self.defines)


@dataclass(slots=True)
class ProjectStatusInfo:
    """High-level health signal for an analyzed project."""

    status: Literal["ok", "degraded", "incomplete"]
    unresolved_references: int
    diagnostic_count: int
    error_count: int


@dataclass(slots=True)
class SearchIndexEntry:
    """Indexed payload with pre-normalized string candidates for search."""

    candidates: tuple[str, ...]
    payload: dict[str, JsonValue]


@dataclass(slots=True)
class AnalysisIndices:
    """Reverse indices derived from a compiled project bundle."""

    design_unit_symbols: tuple[Any, ...] = ()
    design_unit_records: tuple[dict[str, JsonValue], ...] = ()
    design_unit_records_by_name: dict[str, tuple[dict[str, JsonValue], ...]] = field(
        default_factory=dict
    )
    design_unit_symbol_by_key: dict[tuple[str, str], Any] = field(default_factory=dict)
    declaration_entries: tuple[SearchIndexEntry, ...] = ()
    declaration_exact: dict[str, tuple[dict[str, JsonValue], ...]] = field(default_factory=dict)
    reference_entries: tuple[SearchIndexEntry, ...] = ()
    reference_exact: dict[str, tuple[dict[str, JsonValue], ...]] = field(default_factory=dict)
    instance_map: dict[str, Any] = field(default_factory=dict)
    children_map: dict[str | None, tuple[str, ...]] = field(default_factory=dict)
    top_instance_paths: tuple[str, ...] = ()
    design_unit_description_cache: dict[str, dict[str, JsonValue]] = field(default_factory=dict)


@dataclass(slots=True)
class AnalysisBundle:
    """Fully prepared pyslang analysis state."""

    project: ProjectConfig
    project_hash: str
    source_manager: Any
    bag: Any
    compilation: Any
    syntax_trees: dict[Path, Any]
    diagnostic_engine: Any
    diagnostics: tuple[Any, ...]
    project_status: ProjectStatusInfo
    tracked_paths: tuple[Path, ...]
    indices: AnalysisIndices
