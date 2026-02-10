"""CLI entrypoint for cfgfmt.

Subcommand: format
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from . import __version__
from .fs import DiscoverOptions, collect_cfg_files, DEFAULT_EXCLUDES
from .io import IOOptions, read_text_strict, backup_file, atomic_write_text
from .formatter import (
    FormatOptions,
    format_text,
    ALIGN_MODE_DEFAULT,
    TAB_WIDTH_DEFAULT,
    KEY_CAP_DEFAULT,
    COMMENT_CAP_DEFAULT,
    SPECIAL_ALIGN_KEYS_DEFAULT,
)


@dataclass
class FileResult:
    path: Path
    status: str  # OK / CHANGED / WOULD / FAILED
    message: str = ""
    sig_fail_lines: list[int] | None = None


class CfgFmtArgumentParser(argparse.ArgumentParser):
    """中文化 argparse 错误输出。"""

    @staticmethod
    def _translate_error(message: str) -> str:
        required = re.match(r"the following arguments are required: (.+)", message)
        if required:
            return f"缺少必需参数: {required.group(1)}"

        unrecognized = re.match(r"unrecognized arguments: (.+)", message)
        if unrecognized:
            return f"无法识别的参数: {unrecognized.group(1)}"

        invalid_choice = re.match(r"argument (.+): invalid choice: (.+) \(choose from (.+)\)", message)
        if invalid_choice:
            return (
                f"参数 {invalid_choice.group(1)} 的取值无效: {invalid_choice.group(2)}，"
                f"可选值为 {invalid_choice.group(3)}"
            )

        return message

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        zh_message = self._translate_error(message)
        self.exit(
            2,
            f"错误: {zh_message}\n提示: 使用 `cfgfmt format --help` 查看完整帮助。\n",
        )


def _split_excludes(values: list[str] | None) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    for v in values:
        parts = [p.strip() for p in v.split(",")]
        out.extend([p for p in parts if p])
    return out


def build_parser() -> argparse.ArgumentParser:
    p = CfgFmtArgumentParser(
        prog="cfgfmt",
        description="CS2 .cfg 配置格式化工具（只处理空白与对齐，不改配置语义）",
    )
    p._positionals.title = "位置参数"
    p._optionals.title = "通用选项"
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(
        dest="cmd",
        required=True,
        title="子命令",
        description="可用子命令",
        metavar="CMD",
    )

    fmt = sub.add_parser(
        "format",
        help="格式化目录下的 *.cfg 文件",
        description="批量格式化目录下的 .cfg 文件；默认原地写回，支持 --check 只检查。",
        epilog=(
            "示例:\n"
            "  cfgfmt format ./cfg\n"
            "  cfgfmt format ./cfg --check\n"
            "  cfgfmt format ./cfg --exclude \"**/autoexec.cfg,**/run_async.cfg\"\n"
            "  cfgfmt format ./cfg --fail-fast"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    fmt._positionals.title = "位置参数"
    fmt._optionals.title = "通用选项"

    fmt.add_argument("dir", type=Path, help="要扫描的根目录")

    control = fmt.add_argument_group("处理控制")
    control.add_argument("--no-recursive", action="store_true", help="仅处理当前目录，不递归子目录")
    control.add_argument("--check", action="store_true", help="只检查，不写回；若有文件需要格式化则退出码为 1")
    control.add_argument("--dry-run", dest="check", action="store_true", help="等同于 --check")
    control.add_argument("--fail-fast", action="store_true", help="遇到第一个失败后立即退出")
    control.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="排除 glob 规则（可逗号分隔，也可重复传入）",
    )

    io_group = fmt.add_argument_group("输入输出")
    io_group.add_argument("--no-backup", action="store_true", help="关闭写回前备份（默认开启备份）")
    io_group.add_argument("--encoding", default="utf-8", help="读取/写入编码（默认 utf-8）")

    output = fmt.add_argument_group("输出控制")
    out_mode = output.add_mutually_exclusive_group()
    out_mode.add_argument("-q", "--quiet", action="store_true", help="简洁输出：仅显示失败项和汇总")
    out_mode.add_argument("-v", "--verbose", action="store_true", help="详细输出：显示更多上下文信息")

    fmt_group = fmt.add_argument_group("格式化参数")
    fmt_group.add_argument("--align", choices=["global", "block"], default=ALIGN_MODE_DEFAULT, help="对齐模式")
    fmt_group.add_argument("--tab-width", type=int, default=TAB_WIDTH_DEFAULT, help="TAB 替换空格数")
    fmt_group.add_argument("--key-cap", type=int, default=KEY_CAP_DEFAULT, help="命令 key 对齐最大宽度")
    fmt_group.add_argument("--comment-cap", type=int, default=COMMENT_CAP_DEFAULT, help="注释列对齐最大宽度")
    fmt_group.add_argument("--no-echo-tables", action="store_true", help="关闭 echo 表格自动对齐")

    return p


def run_format(args: argparse.Namespace) -> int:
    root = args.dir.resolve()
    if not root.exists() or not root.is_dir():
        print(f"失败      {args.dir}  (不是目录)")
        return 2

    excludes = list(DEFAULT_EXCLUDES)
    excludes.extend(_split_excludes(args.exclude))

    discover = DiscoverOptions(recursive=not args.no_recursive, excludes=tuple(excludes))
    files = collect_cfg_files(root, discover)
    if args.verbose:
        print(
            f"信息      root={root} recursive={discover.recursive} files={len(files)} "
            f"encoding={args.encoding} backup={not args.no_backup}"
        )

    ioopt = IOOptions(encoding=args.encoding, backup=not args.no_backup)

    fmtopt = FormatOptions(
        align_mode=args.align,
        tab_width=args.tab_width,
        key_cap=args.key_cap,
        comment_cap=args.comment_cap,
        special_align_keys=set(SPECIAL_ALIGN_KEYS_DEFAULT),
        echo_align_tables=not args.no_echo_tables,
    )

    results: list[FileResult] = []
    any_change_needed = False
    any_failed = False

    for path in files:
        try:
            raw = read_text_strict(path, encoding=ioopt.encoding)
            fr = format_text(raw, options=fmtopt)

            if fr.sig_fail_lines:
                any_failed = True
                shown = ",".join(map(str, fr.sig_fail_lines[:10]))
                more = "" if len(fr.sig_fail_lines) <= 10 else f" (+{len(fr.sig_fail_lines)-10})"
                msg = f"严格签名校验失败，行号: {shown}{more}"
                results.append(FileResult(path, "FAILED", msg, sig_fail_lines=fr.sig_fail_lines))
                if args.fail_fast:
                    break
                continue

            if not fr.changed:
                results.append(FileResult(path, "OK"))
                continue

            any_change_needed = True
            if args.check:
                results.append(FileResult(path, "WOULD"))
                continue

            if ioopt.backup:
                backup_file(path)

            atomic_write_text(path, text=fr.out_text, encoding=ioopt.encoding)
            results.append(FileResult(path, "CHANGED"))
        except Exception as e:
            any_failed = True
            results.append(FileResult(path, "FAILED", str(e)))
            if args.fail_fast:
                break

    # Print per-file lines
    for r in results:
        if args.quiet and r.status != "FAILED":
            continue
        if r.status == "OK":
            print(f"正常      {r.path}")
        elif r.status == "CHANGED":
            extra = ""
            if r.sig_fail_lines:
                extra = f"  (sig-fallback lines: {len(r.sig_fail_lines)})"
            print(f"已修改    {r.path}{extra}")
        elif r.status == "WOULD":
            print(f"待修改    {r.path}")
        else:
            print(f"失败      {r.path}  ({r.message})")

    changed = sum(1 for r in results if r.status == "CHANGED")
    ok = sum(1 for r in results if r.status == "OK")
    would = sum(1 for r in results if r.status == "WOULD")
    failed = sum(1 for r in results if r.status == "FAILED")
    print(f"汇总: 已修改={changed} 正常={ok} 待修改={would} 失败={failed}")

    if any_failed:
        return 2
    if args.check and any_change_needed:
        return 1
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "format":
        code = run_format(args)
    else:
        code = 2

    raise SystemExit(code)


if __name__ == "__main__":
    main()
