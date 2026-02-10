"""IO helpers (strict read, backup, atomic write)."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class IOOptions:
    encoding: str = "utf-8"
    backup: bool = True


def read_text_strict(path: Path, *, encoding: str) -> str:
    """Read text with strict decoding (no guessing, no ignoring errors)."""
    return path.read_text(encoding=encoding, errors="strict")


def atomic_write_text(path: Path, *, text: str, encoding: str) -> None:
    """Atomically replace file contents using a temporary *.tmp.<pid>.cfg file."""
    pid = os.getpid()
    # keep original suffix and avoid replacing intermediate ".cfg" fragments in basename
    tmp_path = path.with_name(f"{path.stem}.tmp.{pid}{path.suffix}")
    tmp_path.write_text(text, encoding=encoding, errors="strict")
    os.replace(tmp_path, path)


def backup_file(path: Path) -> Path:
    """Create a timestamped backup next to the file, keeping .cfg suffix."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak_name = f"{path.stem}.bak.{ts}{path.suffix}"
    bak_path = path.with_name(bak_name)
    shutil.copy2(path, bak_path)
    return bak_path
