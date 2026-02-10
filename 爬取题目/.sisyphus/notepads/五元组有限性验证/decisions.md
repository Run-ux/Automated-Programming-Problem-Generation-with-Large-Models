# Decisions - 五元组有限性验证

本文件记录架构选择与技术决策。

---


## [2026-02-10T14:49:47] Task 2: Prompt 设计架构决策
- **四维独立抽取**：采用四个独立 prompt 文件，而非一次性五元组抽取
- **System/User 分离**：每个维度提供 build_system_prompt() 和 build_user_prompt(problem) 两个函数
- **JSON Schema 内嵌**：每个 prompt 文件包含对应的 JSON Schema 常量，便于验证和文档
- **约束提取规则**：C 维度 prompt 强制要求从题面全文（description + input + output + constraints）提取约束，避免遗漏业务逻辑约束

## [2026-02-10T16:06:56] 工作流程决策：Task 3 阻塞后的推进策略

### 当前状态
- Task 3 代码已完成（extract.py, normalize.py, vote.py）
- Task 3 Pilot Run 无法执行（API Key 未设置）
- Task 4 严格依赖 Task 3 的 Pilot Run 输出

### 依赖分析
- Task 4 需要 Task 3 的验证输出（50题 voted/ 结果）来：
  1. 确认管线正确性（extract -> normalize -> vote 流程无 bug）
  2. 验证同义词归一化表是否合理
  3. 验证投票机制是否工作正常
- 如果跳过 Task 3 验证直接执行 Task 4（1500题），错误会被放大

### 决策
遵循 "If blocked, document the blocker and move to the next task" 规则，但采用**保守策略**：
1. 创建 Task 4 的分析代码（analyze.py）—— 饱和曲线、统计分析逻辑
2. **不执行实际的 1500 题抽取**（避免在未验证管线的情况下大量 API 调用）
3. 提供清晰的恢复路径（API Key 设置后的执行顺序）

### 理由
- Task 4 的核心价值在于**饱和曲线分析**，而非抽取本身
- 抽取逻辑已在 extract.py 中实现，Task 4 复用相同管线
- 可以先创建分析工具（analyze.py），等 Pilot Run 完成后立即使用

### 恢复路径
1. 用户设置 API Key
2. 运行 Task 3 Pilot Run（50题验证）
3. 检查 voted/ 输出完整性
4. 立即运行 Task 4 Phase 1 抽取（1500题）
5. 使用 analyze.py 生成饱和曲线

---

