# CS2 Config Formatter

`cs2-config-formatter` 是一个面向 **Counter-Strike 2 (CS2)** 的 `.cfg` 文本格式化工具。

- 只处理空白与对齐：空格、TAB、行尾空白、末尾换行、对齐列
- 不修改配置语义：不重写命令、不重排逻辑、不增删指令
- 支持目录递归批处理
- 内置 strict 安全校验，避免潜在危险写回

---

## 目录

- [安装](#安装)
- [快速开始](#快速开始)
- [命令参考](#命令参考)
- [输出与退出码](#输出与退出码)
- [默认行为](#默认行为)
- [常见问题](#常见问题)
- [内部使用与分发](#内部使用与分发)
- [开发文档](#开发文档)

---

## 安装

### 方式一：`uv`（推荐）

```bash
uv venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
uv pip install -e .
```

### 方式二：`pip`

```bash
python -m pip install -e .
```

安装后可执行：

```bash
cfgfmt --help
cfgfmt format --help
```

---

## 快速开始

### 1) 直接格式化并写回

```bash
cfgfmt format ./cfg
```

### 2) 只检查不写回（CI / 提交前检查）

```bash
cfgfmt format ./cfg --check
# 等同
cfgfmt format ./cfg --dry-run
```

### 3) 排除文件

```bash
cfgfmt format ./cfg --exclude "**/autoexec.cfg,**/run_async.cfg"
```

### 4) strict 失败立即退出

```bash
cfgfmt format ./cfg --fail-fast
```

### 5) 输出模式

```bash
cfgfmt format ./cfg --quiet
cfgfmt format ./cfg --verbose
```

---

## 命令参考

### `cfgfmt format <dir>`

核心参数：

- `--check` / `--dry-run`：仅检查，发现可改时返回退出码 `1`
- `--fail-fast`：遇到首个失败立刻退出
- `--exclude`：排除 glob，支持多次传入或逗号分隔
- `--no-recursive`：仅处理当前目录，不递归
- `--encoding`：指定读取/写入编码（默认 `utf-8`）
- `--no-backup`：关闭写回前备份
- `--quiet`：简洁输出
- `--verbose`：详细输出
- `--align`：对齐模式（`global` / `block`）
- `--tab-width` / `--key-cap` / `--comment-cap` / `--no-echo-tables`：格式化细项

---

## 输出与退出码

### 单文件状态

- `正常`：无需改动
- `已修改`：已写回
- `待修改`：仅检查模式下需要改动
- `失败`：读取失败、写入失败、strict 失败等

### 汇总行示例

```text
汇总: 已修改=2 正常=10 待修改=0 失败=1
```

### 退出码

`--check/--dry-run` 模式：

- `0`：无待修改且无失败
- `1`：存在待修改
- `2`：出现失败

非 `--check` 模式：

- `0`：处理完成且无失败
- `2`：出现失败

---

## 默认行为

- 默认扫描：`**/*.cfg`
- 默认排除：
- `**/.git/**`
- `**/*.bak*.cfg`
- `**/*.tmp*.cfg`
- `**/*.old*.cfg`
- `**/*_out.cfg`
- 保留原始换行风格（LF/CRLF）
- 保留原文件是否有末尾换行
- 仅在内容变化时写回
- 写回前默认创建备份

---

## 常见问题

### 1) 提示“不是目录”

`cfgfmt format` 的目标必须是存在的目录路径。

### 2) strict 失败是什么意思

格式化后会做去空白签名校验。若某行新旧签名不一致，文件会标记为 `失败`，并跳过写回。

### 3) strict 是否等于完整语义校验

不是。strict 保证的是“非空白字符签名一致”，不是解释器级别的语义证明。

---

## 内部使用与分发

如果你不打算发布 PyPI，可使用 wheel 内部分发：

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 release-local
```

或安装 wheel 后做快速验证：

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 release-local -InstallWheel -QuickCheck
```

---

## 开发文档

开发流程、质量门、项目结构、维护约定请见 `DEV.md`。