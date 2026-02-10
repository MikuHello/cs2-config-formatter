# DEV Guide

本文档面向维护者，定义开发流程、工程约束、质量门和本地分发标准。

---

## 1. 项目目标

- 提供稳定的 `.cfg` 空白格式化能力
- 严格保证“不改语义”的设计边界
- 支持批处理与可审计的失败策略

---

## 2. 开发环境

基础要求：

- Python `>=3.9`
- `uv`（推荐）

初始化：

```bash
uv venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
uv pip install -e ".[dev]"
```

---

## 3. 脚本工作流

统一入口：`scripts/dev.ps1`

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 help
```

可用命令：

1. `check`
2. `build`
3. `quick`
4. `release-local`

示例：

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 check
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 build
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 quick
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 release-local -InstallWheel -QuickCheck
```

命令语义：

- `check`：运行 `pytest + ruff + mypy`
- `build`：运行 `uv build + twine check`
- `quick`：运行 `cfgfmt --help` 与 `cfgfmt format --help` 快速验证
- `release-local`：本地分发流程（构建、校验、可选安装 wheel、可选快速验证）

---

## 4. 质量门

合并前必须通过以下检查：

1. `uv run pytest -q`
2. `uv run ruff check .`
3. `uv run mypy cfgfmt`

---

## 5. Git 流程

分支模型：

- 主分支：`main`（始终可发布）
- 工作分支：`feat/*`、`fix/*`、`docs/*`、`refactor/*`、`test/*`、`chore/*`
- 紧急修复分支：`hotfix/*`（从 `main` 拉取）

提交流程：

1. 从最新 `main` 创建工作分支
2. 开发完成后执行质量门：`powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 check`
3. 通过后提交并合并回 `main`
4. 合并后删除工作分支

提交规范：

- 使用 Conventional Commits：`feat:`、`fix:`、`docs:`、`refactor:`、`test:`、`chore:`

合并策略：

- 统一使用 `squash merge`
- 当前不强制 PR 审批规则（后续可按团队规模补充）

版本策略：

- 使用 SemVer：`MAJOR.MINOR.PATCH`
- 版本标签格式：`vX.Y.Z`

发布前本地检查：

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 build
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 release-local -InstallWheel -QuickCheck
```

---

## 6. 行为契约

### 6.1 退出码

`--check/--dry-run`：

- `0`：无待修改且无失败
- `1`：有待修改
- `2`：有失败

非 `--check`：

- `0`：处理完成且无失败
- `2`：有失败

### 6.2 strict 策略

- 格式化后执行去空白签名校验
- strict 失败按文件级失败处理
- strict 失败文件不写回
- `--fail-fast` 下遇首个失败即退出

### 6.3 写入策略

- 原子写入（临时文件 + replace）
- 仅内容变化时写回
- 仅写回前备份
- 备份命名：`<stem>.bak.YYYYMMDD-HHMMSS<suffix>`
- 临时文件命名：`<stem>.tmp.<pid><suffix>`

---

## 7. 项目结构

```text
cs2-config-formatter/
├── cfgfmt/
│   ├── __init__.py
│   ├── cli.py
│   ├── formatter.py
│   ├── fs.py
│   └── io.py
├── tests/
│   ├── test_cli.py
│   ├── test_formatter.py
│   └── test_io.py
├── scripts/
│   └── dev.ps1
├── AI.md
├── README.md
├── DEV.md
└── pyproject.toml
```

---

## 8. 改动守则

当修改 CLI 行为或输出时，必须同时完成：

1. 更新 `tests/test_cli.py`
2. 更新 `README.md` 对应用法/输出说明
3. 若影响契约，更新本文件第 6 节

---

## 9. 本地分发标准流程

构建与校验：

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 build
```

构建 + 安装 + 快速验证：

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 release-local -InstallWheel -QuickCheck
```

---

## 10. 关键决策记录

1. 统一脚本入口  
理由：减少流程分叉与记忆负担，避免多脚本漂移。

2. strict 采用文件级失败策略  
理由：优先安全，不把潜在异常行写回到配置文件。

3. 内部交付优先 wheel  
理由：可复现、易追踪版本，不依赖公网仓库。
