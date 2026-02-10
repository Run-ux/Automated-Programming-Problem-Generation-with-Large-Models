# 项目结构分析

本项目为 Python 爬虫工具，按平台与通用模块分层组织，入口脚本位于仓库根目录。

## 目录与文件

```
.
├─ atcoder/
│  ├─ __init__.py
│  └─ scraper.py
├─ codeforces/
│  ├─ __init__.py
│  ├─ __pycache__/
│  └─ scraper.py
├─ common/
│  ├─ __init__.py
│  ├─ __pycache__/
│  ├─ browser.py
│  ├─ models.py
│  ├─ storage.py
│  └─ utils.py
├─ icpc/
│  ├─ __init__.py
│  ├─ __pycache__/
│  └─ scraper.py
├─ luogu/
│  ├─ __init__.py
│  ├─ __pycache__/
│  └─ scraper.py
├─ output/
├─ __init__.py
├─ __pycache__/
├─ AGENTS.md
├─ config.py
├─ main.py
├─ requirements.txt
└─ schema五元组定义.md
```

## 结构要点

- 平台模块：`atcoder/`、`codeforces/`、`icpc/`、`luogu/` 各自维护抓取逻辑，统一入口由 `main.py` 调度。
- 通用能力：`common/` 汇聚浏览器访问、模型定义、存储与通用工具，供各平台复用。
- 配置中心：`config.py` 负责速率限制、输出路径、日志格式等全局配置。
- 输出目录：`output/` 为抓取结果落盘目录，按平台分子目录。
- 项目元信息：`requirements.txt` 管理依赖，`AGENTS.md` 为仓库内工作规范说明。
