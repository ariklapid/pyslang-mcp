from __future__ import annotations

from pathlib import Path
from typing import cast

from pyslang_mcp.cache import AnalysisCache
from pyslang_mcp.types import AnalysisBundle, ProjectConfig


def _project(tmp_path: Path, name: str) -> ProjectConfig:
    file_path = tmp_path / f"{name}.sv"
    file_path.write_text(f"module {name}; endmodule\n", encoding="utf-8")
    return ProjectConfig(
        project_root=tmp_path,
        files=(file_path,),
        include_dirs=(),
        defines=(),
        top_modules=(),
    )


def test_analysis_cache_evicts_oldest_entry(tmp_path: Path) -> None:
    cache = AnalysisCache(max_entries=1)
    first = _project(tmp_path, "first")
    second = _project(tmp_path, "second")
    builds: list[str] = []

    def factory(project: ProjectConfig) -> AnalysisBundle:
        builds.append(project.files[0].name)
        return cast(AnalysisBundle, type("Bundle", (), {"tracked_paths": project.files})())

    cache.get_or_build(first, lambda: factory(first))
    cache.get_or_build(second, lambda: factory(second))
    cache.get_or_build(first, lambda: factory(first))

    assert len(cache) == 1
    assert builds == ["first.sv", "second.sv", "first.sv"]
