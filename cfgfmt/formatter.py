"""CS2 .cfg whitespace formatter/aligner (core logic).

Notes
-----
- Whitespace-only formatting: spaces/TABs/trailing whitespace/final newline.
- No semantic changes: command tokens (non-whitespace chars) must remain identical.
- Strict signature check: for every line, `sig_no_ws(old) == sig_no_ws(new)` must hold,
  otherwise that line falls back to original (detab+rstrip) and the line number is recorded.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# =========================
# 默认配置（可被 CLI 覆盖）
# =========================

ALIGN_MODE_DEFAULT = "global"  # global / block
TAB_WIDTH_DEFAULT = 4
KEY_CAP_DEFAULT = 40
COMMENT_CAP_DEFAULT = 90

SPECIAL_ALIGN_KEYS_DEFAULT = {"bind", "alias"}
ECHO_ALIGN_TABLES_DEFAULT = True

# 默认排除规则（递归扫描时避免误处理备份/临时/旧版本/历史产物）
DEFAULT_EXCLUDES = [
    "**/.git/**",
    "**/*.bak*.cfg",
    "**/*.tmp*.cfg",
    "**/*.old*.cfg",
    "**/*_out.cfg",
]


# =========================
# 格式化器核心（尽量保持你原来的实现）
# =========================


def vis_width(s: str) -> int:
    """估算控制台等宽字体下的显示宽度：中文/全角算 2，组合字符算 0，其它算 1。"""

    w = 0
    for ch in s:
        if unicodedata.combining(ch):
            continue
        ea = unicodedata.east_asian_width(ch)
        w += 2 if ea in ("W", "F") else 1
    return w


WS_RE = re.compile(r"[ \t\r\f\v]+")


def detab(s: str, tab_width: int) -> str:
    return s.replace("\t", " " * tab_width)


def rstrip_ws(s: str) -> str:
    return s.rstrip(" \t\r\f\v")


def sig_no_ws(s: str) -> str:
    return WS_RE.sub("", s)


def find_comment_pos_outside_quotes(s: str):
    """找到引号外的 // 位置；找不到返回 None。"""
    in_quote = False
    for i in range(len(s) - 1):
        ch = s[i]
        if ch == '"':
            in_quote = not in_quote
            continue
        if (not in_quote) and s[i : i + 2] == "//":
            return i
    return None


def split_indent_key_rest(code_part: str):
    """拆成 (indent, key, rest)"""
    s = code_part
    n = len(s)
    i = 0
    while i < n and s[i].isspace():
        i += 1
    if i >= n:
        return None

    indent = s[:i]
    j = i
    while j < n and (not s[j].isspace()):
        j += 1
    key = s[i:j]

    rest_raw = s[j:]
    # echo 行：key 后空白可能用于 ASCII 缩进，必须原样保留
    if key.lower() == "echo":
        rest = rest_raw
    else:
        k = 0
        while k < len(rest_raw) and rest_raw[k].isspace():
            k += 1
        rest = rest_raw[k:]
    return indent, key, rest


def split_two_quoted(rest: str):
    """尝试从 rest 中提取前两个引号字符串："..." "..."。失败返回 None。"""

    s = rest
    n = len(s)
    i = 0
    while i < n and s[i].isspace():
        i += 1
    if i >= n or s[i] != '"':
        return None

    # first quoted
    j = i + 1
    while j < n and s[j] != '"':
        j += 1
    if j >= n:
        return None
    q1 = s[i : j + 1]

    k = j + 1
    while k < n and s[k].isspace():
        k += 1
    if k >= n or s[k] != '"':
        return None

    # second quoted
    m = k + 1
    while m < n and s[m] != '"':
        m += 1
    if m >= n:
        return None
    q2 = s[k : m + 1]
    tail = s[m + 1 :]
    return q1, q2, tail


def is_separator_comment_line(line: str) -> bool:
    """识别“分割线注释行”（用于 block 分块边界）。"""

    s = line.lstrip()
    if not s.startswith("//"):
        return False
    body = s[2:].lstrip()
    if not body.startswith("+"):
        return False
    if "*" in body:
        return True
    deco = sum(1 for c in body if c in "#-_=+|")
    ratio = deco / max(1, len(body))
    return ratio >= 0.60 and len(body) >= 10


def is_block_boundary_B(line: str) -> bool:
    """边界策略 B：空行 / echo; / 分割线注释行 视作边界。"""

    s = line.strip().lower()
    if s == "":
        return True
    if s == "echo;":
        return True
    if is_separator_comment_line(line):
        return True
    return False


@dataclass
class FormatOptions:
    align_mode: str = ALIGN_MODE_DEFAULT
    tab_width: int = TAB_WIDTH_DEFAULT
    key_cap: int = KEY_CAP_DEFAULT
    comment_cap: int = COMMENT_CAP_DEFAULT
    special_align_keys: set[str] | None = None
    echo_align_tables: bool = ECHO_ALIGN_TABLES_DEFAULT


@dataclass
class FormatResult:
    out_text: str
    changed: bool
    sig_fail_lines: list[int]
    stats: dict


def format_cmd_lines(
    cmd_recs,
    *,
    key_cap: int,
    comment_cap: int,
    tab_width: int,
    special_align_keys: set[str],
    echo_align_tables: bool,
    stats: dict,
):
    """对一组记录做对齐（cmd_recs 内不包含 boundary 行）。"""

    def inc(k, n=1):
        stats[k] = stats.get(k, 0) + n

    # 统计 key 宽度（只对真正命令行参与；且要求有 rest 才对齐 value）
    key_widths = []
    for r in cmd_recs:
        if r["kind"] != "cmd":
            continue
        if r["rest"] != "":
            key_widths.append(len(r["indent"]) + len(r["key"]))
    max_key = min(max(key_widths), key_cap) if key_widths else 0
    value_col = max_key + 1

    # bind/alias 等“双引号对齐”统计
    q1_lens = []
    for r in cmd_recs:
        if r["kind"] != "cmd" or r["rest"] == "":
            continue
        if r["key_lower"] not in special_align_keys:
            continue
        twoq = split_two_quoted(r["rest"])
        if twoq:
            q1_lens.append(len(twoq[0]))
    max_q1_len = max(q1_lens) if q1_lens else 0
    second_col = value_col + max_q1_len + 1

    # echo 菜单表格对齐
    def is_echo_table_candidate(rec) -> bool:
        if not echo_align_tables:
            return False
        if rec.get("kind") != "cmd":
            return False
        if rec.get("comment"):
            return False
        if rec.get("key_lower", rec.get("key", "").lower()) != "echo":
            return False

        raw_rest = rec.get("rest", "")
        body = raw_rest.strip()
        if "|" not in body:
            return False

        if body.startswith("~~~"):
            return False
        if "【" in body and "】" in body and ("*" in body or "~" in body):
            return False

        pipe_cnt = body.count("|")
        has_cjk = re.search(r"[\u4e00-\u9fff]", body) is not None
        has_alnum = re.search(r"[A-Za-z0-9]", body) is not None
        has_art_chunk = re.search(r"[_/\\]{2,}", body) is not None
        if (not has_cjk and not has_alnum and pipe_cnt <= 3):
            return False
        if (not has_cjk and has_art_chunk and pipe_cnt <= 2):
            return False

        return True

    echo_rows = []
    echo_col_widths: list[int] = []
    max_cols = 0
    for r in cmd_recs:
        if not is_echo_table_candidate(r):
            continue
        body = r["rest"].strip()
        leading_pipe = body.startswith("|")
        trailing_pipe = body.endswith("|")
        core = body.strip("|") if (leading_pipe or trailing_pipe) else body
        fields = [f.strip() for f in core.split("|")]
        r["_echo_fields"] = fields
        r["_echo_lead"] = leading_pipe
        r["_echo_trail"] = trailing_pipe
        if not (leading_pipe or trailing_pipe):
            echo_rows.append(fields)
            max_cols = max(max_cols, len(fields))

    if echo_rows and max_cols > 0:
        echo_col_widths = [0] * max_cols
        for fields in echo_rows:
            for i, f in enumerate(fields):
                echo_col_widths[i] = max(echo_col_widths[i], vis_width(f))

    code_fmts: list[str | None] = []
    code_lens_for_comment = []
    for r in cmd_recs:
        if r["kind"] != "cmd":
            code_fmts.append(None)
            continue

        indent, key, rest = r["indent"], r["key"], r["rest"]
        key_lower = r.get("key_lower", key.lower())

        if key_lower == "echo":
            if is_echo_table_candidate(r) and echo_col_widths:
                fields = r.get("_echo_fields") or []
                lead = r.get("_echo_lead", False)
                trail = r.get("_echo_trail", False)
                if lead or trail:
                    body_mid = " | ".join(fields).strip()
                    body_fmt = ("| " if lead else "") + body_mid + (" |" if trail else "")
                else:
                    padded = []
                    for i, f in enumerate(fields):
                        w = echo_col_widths[i] if i < len(echo_col_widths) else vis_width(f)
                        padded.append(f + (" " * max(0, w - vis_width(f))))
                    body_fmt = " | ".join(padded).rstrip()
                code_fmt = indent + key + " " + body_fmt
                inc("echo_table_aligned")
            else:
                code_fmt = indent + key if rest == "" else (indent + key + rest)
            code_fmts.append(code_fmt)
            if r.get("comment"):
                code_lens_for_comment.append(len(code_fmt))
            continue

        if rest == "":
            code_fmt = indent + key
            inc("cmd_no_rest")
        else:
            left_len = len(indent) + len(key)
            pad1 = max(1, value_col - left_len)
            twoq = split_two_quoted(rest) if key_lower in special_align_keys else None
            if twoq:
                q1, q2, tail = twoq
                cur_after_q1 = left_len + pad1 + len(q1)
                pad2 = max(1, second_col - cur_after_q1)
                code_fmt = indent + key + (" " * pad1) + q1 + (" " * pad2) + q2 + tail
                inc("special_two_quote_aligned")
            else:
                code_fmt = indent + key + (" " * pad1) + rest
                inc("cmd_value_aligned")

        code_fmts.append(code_fmt)
        if r.get("comment"):
            code_lens_for_comment.append(len(code_fmt))

    comment_target = (
        min(max(code_lens_for_comment), comment_cap) if code_lens_for_comment else None
    )

    out = []
    for r, code_fmt in zip(cmd_recs, code_fmts):
        orig = r["orig"]
        lineno = r.get("lineno")
        normalized_orig = rstrip_ws(detab(orig, tab_width))

        if r["kind"] != "cmd":
            new_line = r["line"]
            if sig_no_ws(orig) != sig_no_ws(new_line):
                stats.setdefault("sig_fail_lines", []).append(lineno)
                new_line = normalized_orig
            out.append(new_line)
            continue

        assert code_fmt is not None
        comment = r.get("comment", "")
        if comment:
            if comment_target is not None and len(code_fmt) <= comment_target:
                pad = max(1, (comment_target + 1) - len(code_fmt))
                new_line = code_fmt + (" " * pad) + comment
                inc("comment_aligned")
            else:
                new_line = code_fmt + " " + comment
        else:
            new_line = code_fmt

        new_line = rstrip_ws(detab(new_line, tab_width))
        if sig_no_ws(orig) != sig_no_ws(new_line):
            stats.setdefault("sig_fail_lines", []).append(lineno)
            new_line = normalized_orig
        out.append(new_line)

    return out


def format_text(raw_text: str, *, options: FormatOptions) -> FormatResult:
    """格式化单个 cfg 文本，返回格式化后的文本与统计/失败行号。"""

    # 记录原始换行风格
    newline = "\r\n" if "\r\n" in raw_text else "\n"
    keep_final_newline = raw_text.endswith("\n") or raw_text.endswith("\r\n")

    lines = raw_text.splitlines()
    stats: dict = {
        "total_lines": len(lines),
        "align_mode": options.align_mode,
        "sig_fail_lines": [],
    }

    # 预解析
    recs = []
    for i, orig in enumerate(lines, start=1):
        line = rstrip_ws(detab(orig, options.tab_width))

        if options.align_mode == "block" and is_block_boundary_B(line):
            recs.append({"kind": "boundary", "orig": orig, "line": line, "lineno": i})
            continue

        if line.lstrip().startswith("//"):
            recs.append({"kind": "pass", "orig": orig, "line": line, "lineno": i})
            continue
        if line.strip() == "":
            recs.append({"kind": "boundary", "orig": orig, "line": line, "lineno": i})
            continue

        cpos = find_comment_pos_outside_quotes(line)
        if cpos is None:
            code_part, comment_part = line, ""
        else:
            code_part, comment_part = rstrip_ws(line[:cpos]), line[cpos:]

        ikr = split_indent_key_rest(code_part)
        if ikr is None:
            recs.append({"kind": "pass", "orig": orig, "line": line, "lineno": i})
            continue

        indent, key, rest = ikr
        recs.append(
            {
                "kind": "cmd",
                "orig": orig,
                "line": line,
                "indent": indent,
                "key": key,
                "key_lower": key.lower(),
                "rest": rest,
                "comment": comment_part,
                "lineno": i,
            }
        )

    out_lines = []

    def handle_boundary(r):
        # boundary 行只 detab + rstrip，再做签名校验；失败行号记录
        new_line = r["line"]
        if sig_no_ws(r["orig"]) != sig_no_ws(new_line):
            stats["sig_fail_lines"].append(r.get("lineno"))
            new_line = rstrip_ws(detab(r["orig"], options.tab_width))
        out_lines.append(new_line)

    special_align_keys = options.special_align_keys or set(SPECIAL_ALIGN_KEYS_DEFAULT)

    if options.align_mode == "global":
        chunk = [r for r in recs if r["kind"] != "boundary"]
        formatted = format_cmd_lines(
            chunk,
            key_cap=options.key_cap,
            comment_cap=options.comment_cap,
            tab_width=options.tab_width,
            special_align_keys=special_align_keys,
            echo_align_tables=options.echo_align_tables,
            stats=stats,
        )
        it = iter(formatted)
        for r in recs:
            if r["kind"] == "boundary":
                handle_boundary(r)
            else:
                out_lines.append(next(it))
    elif options.align_mode == "block":
        block: list[dict[str, object]] = []
        for r in recs:
            if r["kind"] == "boundary":
                if block:
                    out_lines.extend(
                        format_cmd_lines(
                            block,
                            key_cap=options.key_cap,
                            comment_cap=options.comment_cap,
                            tab_width=options.tab_width,
                            special_align_keys=special_align_keys,
                            echo_align_tables=options.echo_align_tables,
                            stats=stats,
                        )
                    )
                    block.clear()
                handle_boundary(r)
            else:
                block.append(r)
        if block:
            out_lines.extend(
                format_cmd_lines(
                    block,
                    key_cap=options.key_cap,
                    comment_cap=options.comment_cap,
                    tab_width=options.tab_width,
                    special_align_keys=special_align_keys,
                    echo_align_tables=options.echo_align_tables,
                    stats=stats,
                )
            )
            block.clear()
    else:
        raise ValueError('ALIGN_MODE 只能是 "global" 或 "block"')

    out_text = newline.join(out_lines)
    if keep_final_newline:
        out_text += newline

    changed = out_text != raw_text
    sig_fail_lines = [x for x in stats.get("sig_fail_lines", []) if isinstance(x, int)]
    return FormatResult(out_text=out_text, changed=changed, sig_fail_lines=sig_fail_lines, stats=stats)
