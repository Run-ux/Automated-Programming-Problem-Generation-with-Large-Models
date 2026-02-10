# Problems - 五元组有限性验证

本文件记录未解决的阻塞问题。

---


## [2026-02-10T16:04:19] Task 3: API Key 未设置（阻塞 Pilot Run）

### 问题描述
- DASHSCOPE_API_KEY: NOT_SET
- QWEN_API_KEY: NOT_SET
- 导致 QwenClient 初始化失败，无法调用 API

### 影响范围
- extract.py 无法执行（依赖 Qwen API）
- Pilot Run 暂时无法运行

### 解决方案
已在 README_TASK3.md 提供完整设置指南：
- Windows: `setx DASHSCOPE_API_KEY "your-key"`
- Linux/Mac: `export DASHSCOPE_API_KEY="your-key"`
- 验证命令：`python -c "import os; print('API Key:', 'SET' if os.getenv('DASHSCOPE_API_KEY') else 'NOT SET')"`

### 状态
- 代码已完成（extract.py, normalize.py, vote.py）
- 等待用户设置 API Key 后继续

---


## [2026-02-10T16:04:47] Task 3: API Key 未设置（阻塞 Pilot Run）

### 问题描述
- DASHSCOPE_API_KEY: NOT_SET
- QWEN_API_KEY: NOT_SET
- 导致 QwenClient 初始化失败，无法调用 API

### 影响范围
- extract.py 无法执行（依赖 Qwen API）
- Pilot Run 暂时无法运行

### 解决方案
已在 README_TASK3.md 提供完整设置指南：
- Windows: setx DASHSCOPE_API_KEY "your-key"
- Linux/Mac: export DASHSCOPE_API_KEY="your-key"
- 验证命令：python -c "import os; print('API Key:', 'SET' if os.getenv('DASHSCOPE_API_KEY') else 'NOT SET')"

### 状态
- 代码已完成（extract.py, normalize.py, vote.py）
- 等待用户设置 API Key 后继续

---

