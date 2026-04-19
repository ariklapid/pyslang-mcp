"""In-memory project analysis cache keyed by config plus tracked mtimes."""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from .serializers import project_config_json
from .types import AnalysisBundle, ProjectConfig


@dataclass(slots=True)
class _CacheEntry:
    project_hash: str
    mtimes: tuple[tuple[str, int], ...]
    bundle: AnalysisBundle


class AnalysisCache:
    """Bounded process-local analysis cache."""

    def __init__(self, *, max_entries: int = 16) -> None:
        self._entries: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._lock = RLock()
        self._max_entries = max(1, max_entries)

    def get_or_build(
        self,
        project: ProjectConfig,
        factory: Callable[[], AnalysisBundle],
    ) -> AnalysisBundle:
        """Return a cached analysis bundle when tracked inputs have not changed."""

        cache_key = self._project_hash(project)
        with self._lock:
            entry = self._entries.get(cache_key)
            if entry is not None:
                if entry.mtimes == self._snapshot_mtimes(entry.bundle.tracked_paths):
                    self._entries.move_to_end(cache_key)
                    return entry.bundle
                self._entries.pop(cache_key, None)

        bundle = factory()
        new_entry = _CacheEntry(
            project_hash=cache_key,
            mtimes=self._snapshot_mtimes(bundle.tracked_paths),
            bundle=bundle,
        )
        with self._lock:
            self._entries[cache_key] = new_entry
            self._entries.move_to_end(cache_key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
        return bundle

    def clear(self) -> None:
        """Drop all cached entries."""

        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        """Return the number of live cache entries."""

        with self._lock:
            return len(self._entries)

    def _project_hash(self, project: ProjectConfig) -> str:
        payload = json.dumps(project_config_json(project), sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _snapshot_mtimes(self, paths: tuple[Path, ...]) -> tuple[tuple[str, int], ...]:
        mtimes: list[tuple[str, int]] = []
        for path in sorted(paths):
            mtime_ns = path.stat().st_mtime_ns if path.exists() else -1
            mtimes.append((path.as_posix(), mtime_ns))
        return tuple(mtimes)


DEFAULT_CACHE = AnalysisCache(max_entries=16)
