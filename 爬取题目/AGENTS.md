# AGENTS.md

本文件为仓库内智能代理的统一工作指南。请严格遵循，避免引入未验证的假设。

## 1. 仓库概览
- 项目性质：Python 爬虫工具，抓取竞赛题目并输出 Markdown/JSON。
- 入口脚本：`main.py`（包内相对导入，需以模块方式运行）。
- 主要模块：`codeforces/`、`atcoder/`、`luogu/`、`icpc/`、`common/`。
- 配置中心：`config.py`（速率限制、输出路径、日志格式等）。
- 输出目录：`output/`（按平台分子目录，含 `index.json` 与 `.md`）。

## 2. 规则文件现状（Cursor / Copilot）
当前仓库未发现以下规则文件：
- `.cursorrules`
- `.cursor/rules/*`
- `.github/copilot-instructions.md`
因此本 `AGENTS.md` 为唯一权威规则来源。

## 3. 安装 / 构建 / 运行
### 3.1 依赖安装
仓库根目录包含 `requirements.txt`：
```bash
python -m pip install -r requirements.txt
```

### 3.2 运行入口
`main.py` 使用包内相对导入，必须以模块方式运行。
请在包含包目录的父目录执行：
```bash
python -m 爬取题目.main
```

### 3.3 运行参数
`main.py` 支持以下参数：
- 位置参数 `sources`：指定平台（`codeforces` / `atcoder` / `luogu` / `icpc`）。
- `--max`：限制每个平台抓取数量（用于本地调试）。

示例：
```bash
python -m 爬取题目.main codeforces --max 5
python -m 爬取题目.main luogu icpc --max 10
```

### 3.4 构建 / Lint / 测试命令（现状）
本仓库当前未提供以下配置或命令：
- 构建脚本（如 `Makefile` / `setup.cfg` / `pyproject.toml`）
- Lint 配置（如 `ruff` / `flake8` / `pylint` / `mypy`）
- 测试框架配置（如 `pytest.ini` / `tox.ini` / `unittest` 测试文件）

因此：
- **不存在**可直接运行的 lint 命令。
- **不存在**可直接运行的测试命令。
- **无法**提供“单测单文件/单用例”的现成命令。

如需新增上述能力，请先与维护者确认后再修改配置。

## 4. 代码风格与结构规范
### 4.1 目录与模块
- 使用清晰的分层结构：平台逻辑在各自子包中，通用能力放入 `common/`。
- 新平台抓取器应放入独立子包，并在 `main.py` 中注册。

### 4.2 导入与组织
- 文件首行应包含：`from __future__ import annotations`。
- 导入顺序：标准库 → 第三方库 → 本地包（相对导入）。
- 相对导入优先：如 `from ..common.utils import ...`。
- 避免在模块顶层执行网络请求或 IO 操作。

### 4.3 命名规范
- 函数/变量：`snake_case`。
- 类名：`PascalCase`（如 `BrowserManager`、`ProblemText`）。
- 常量：全大写 + 下划线（如 `CF_API_RATE`）。
- 私有辅助函数使用前缀 `_`。

### 4.4 类型提示
- 采用 Python 类型注解，函数签名应尽量完整。
- 常见类型：`list` / `dict` / `Optional` / `tuple` / `Set`。
- 若函数返回可能为空，使用 `Optional[...]` 或 `| None`。

### 4.5 日志与异常
- 使用 `logging` 模块，禁止 `print`。
- 日志格式与级别统一在 `config.py` 中配置。
- 捕获异常后记录日志，避免静默失败。
- 需要重试的网络请求使用装饰器 `@retry`。

### 4.6 网络请求与速率限制
- 请求必须遵循 `config.py` 中的速率限制常量。
- 使用 `common.utils.create_session()` 创建会话，统一 UA 与请求头。
- 平台爬取逻辑需避免过高并发，尊重平台限制。

### 4.7 文本解析与清洗
- HTML 解析使用 `BeautifulSoup`。
- LaTeX/MathJax 清洗使用 `clean_mathjax()` 与 `strip_mathjax_rendering()`。
- 输出文本尽量保持换行与段落结构，避免过度压缩。

### 4.8 输出与文件
- 输出目录由 `config.py` 定义：`output/` 下按平台分子目录。
- 题目文件名使用 `sanitize_filename()` 处理非法字符。
- 每批次保存后更新 `index.json`（`common.storage.update_index`）。
- 写文件编码固定为 `utf-8`。

## 5. 关键数据模型
所有爬虫输出统一为 `common.models.ProblemText`：
- `problem_id`：唯一 ID（如 `CF123A` / `ABC300_F`）。
- `title` / `description` / `input` / `output` / `constraints`：题目文本字段。
- `source` / `url`：来源与链接。
- `tags` / `difficulty`：标签与难度（可为空）。

新增平台时必须输出该模型，避免自定义结构。

## 6. 运行与调试建议（不涉及新增依赖）
- 本地调试优先使用 `--max` 限制抓取数量。
- 运行后检查 `output/<platform>/` 下的 `.md` 与 `index.json`。
- 若某平台解析失败，优先检查 HTML 结构与选择器。

## 7. 浏览器抓取注意事项
- `common/browser.py` 使用 Playwright 进行网页抓取。
- 代码中引用 `playwright` 与 `playwright_stealth`。
- 若运行到该路径，请确认环境已具备对应依赖与浏览器驱动。

## 8. 变更约束
- 不要在同一变更中进行“重构 + 功能修改”。
- 修复问题时遵循最小改动原则。
- 如需新增依赖或工具配置，必须先与维护者确认。

## 9. 推荐的变更流程（无测试配置前提）
1. 明确要改动的平台与函数范围。
2. 小步提交、逐步验证输出文件是否符合预期。
3. 若引入新字段，确保 `ProblemText` 与 `index.json` 兼容。

## 10. AGENTS 交互要求
- 仅基于仓库中已存在的信息写结论。
- 不编造测试、CI、格式化工具或脚本。
- 不引入未声明的运行方式或目录结构。
