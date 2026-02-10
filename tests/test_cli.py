from pathlib import Path

import pytest

import cfgfmt.cli as cli
from cfgfmt.formatter import FormatResult


def test_parser_help_contains_chinese_sections() -> None:
    help_text = cli.build_parser().format_help()
    assert "子命令" in help_text
    assert "通用选项" in help_text
    assert "--version" in help_text


def test_format_help_contains_examples(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["format", "--help"])

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "示例:" in out
    assert "--dry-run" in out
    assert "处理控制" in out


def test_error_message_is_chinese(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["format"])

    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "错误:" in err
    assert "提示:" in err
    assert "缺少必需参数" in err


def test_main_missing_directory_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(SystemExit) as exc:
        cli.main(["format", str(missing)])

    assert exc.value.code == 2
    out = capsys.readouterr().out
    assert "失败" in out
    assert "不是目录" in out


def test_strict_failure_skips_write_and_returns_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = tmp_path / "sample.cfg"
    original = 'bind "w" "+forward"\n'
    cfg.write_text(original, encoding="utf-8")

    def fake_format_text(_raw: str, *, options: object) -> FormatResult:
        return FormatResult(
            out_text='bind "w" "+attack"\n',
            changed=True,
            sig_fail_lines=[1],
            stats={},
        )

    monkeypatch.setattr(cli, "format_text", fake_format_text)

    with pytest.raises(SystemExit) as exc:
        cli.main(["format", str(tmp_path)])

    assert exc.value.code == 2
    assert cfg.read_text(encoding="utf-8") == original
    assert list(tmp_path.glob("*.bak.*.cfg")) == []

    out = capsys.readouterr().out
    assert "失败" in out
    assert "严格签名校验失败" in out


def test_check_mode_returns_1_when_changes_needed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "sample.cfg"
    original = 'bind "w" "+forward"\n'
    cfg.write_text(original, encoding="utf-8")

    def fake_format_text(_raw: str, *, options: object) -> FormatResult:
        return FormatResult(
            out_text='bind "w"    "+forward"\n',
            changed=True,
            sig_fail_lines=[],
            stats={},
        )

    monkeypatch.setattr(cli, "format_text", fake_format_text)

    with pytest.raises(SystemExit) as exc:
        cli.main(["format", str(tmp_path), "--check"])

    assert exc.value.code == 1
    assert cfg.read_text(encoding="utf-8") == original
