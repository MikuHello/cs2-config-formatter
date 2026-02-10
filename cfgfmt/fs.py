"""File discovery (collect *.cfg, apply exclude rules)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import fnmatch

DEFAULT_EXCLUDES = [
    "**/.git/**",
    "**/*.bak*.cfg",
    "**/*.tmp*.cfg",
    "**/*.old*.cfg",
    "**/*_out.cfg",
]

@dataclass(frozen=True)
class DiscoverOptions:
    recursive: bool = True
    excludes: tuple[str, ...] = tuple(DEFAULT_EXCLUDES)

def _normalize_relpath(path: Path, root: Path) -> str:
    rel = path.relative_to(root).as_posix()
    return rel

def is_excluded(path: Path, root: Path, patterns: list[str]) -> bool:
    rel = _normalize_relpath(path, root)
    # also match with a leading '**/' convenience
    for pat in patterns:
        p = pat.strip()
        if not p:
            continue
        if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch("/" + rel, p) or fnmatch.fnmatch(rel, p.lstrip("./")):
            return True
    return False

def collect_cfg_files(root: Path, options: DiscoverOptions) -> list[Path]:
    root = root.resolve()
    patterns = list(options.excludes)

    files: list[Path] = []
    if options.recursive:
        it = root.rglob("*.cfg")
    else:
        it = root.glob("*.cfg")

    for p in it:
        if p.is_dir():
            continue
        if is_excluded(p, root, patterns):
            continue
        files.append(p)

    files.sort()
    return files
