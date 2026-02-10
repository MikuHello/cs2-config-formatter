from pathlib import Path

from cfgfmt.io import atomic_write_text, backup_file


def test_backup_and_tmp_names_keep_suffix_with_cfg_in_basename(tmp_path: Path) -> None:
    target = tmp_path / "demo.cfg.old.cfg"
    target.write_text("old\n", encoding="utf-8")

    bak = backup_file(target)
    assert bak.name.startswith("demo.cfg.old.bak.")
    assert bak.name.endswith(".cfg")
    assert bak.read_text(encoding="utf-8") == "old\n"

    atomic_write_text(target, text="new\n", encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "new\n"
    assert list(tmp_path.glob("*.tmp.*.cfg")) == []
