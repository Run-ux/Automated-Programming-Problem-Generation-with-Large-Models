# Learnings - 五元组有限性验证

本文件记录执行过程中发现的约定、模式与最佳实践。

---

## [2026-02-10 14:38] Task 0: 确认爬取数据存在

### 发现
- 爬取数据已存在于 `output/` 目录
- 三平台数据完整：
  - codeforces: 2,201 题
  - icpc: 3,149 题
  - luogu: 7,903 题
  - **总计: 13,253 题**

### 约定
- 所有验证证据保存在 `.sisyphus/evidence/task-{N}-*.txt`
- 路径引用统一使用 `{REPO_ROOT}` 占位符，执行时替换为绝对路径

---


## [] Task 1: 数据采样完成
- Phase 1 样本: 1500 题（luogu/codeforces/icpc 各 500）
- Pilot 样本: 50 题（Phase 1 子集）
- 随机种子: 42（可复现）
- 输出路径: finiteness_verification/data/sample_*.json
- 验证证据: .sisyphus/evidence/task-1-sample-stats.txt

## [2026-02-10T14:43:06+08:00] Task 1: 数据采样完成
- Phase 1 样本: 1500 题（luogu/codeforces/icpc 各 500）
- Pilot 样本: 50 题（Phase 1 子集）
- 随机种子: 42（可复现）
- 输出路径: finiteness_verification/data/sample_*.json
- 验证证据: .sisyphus/evidence/task-1-sample-stats.txt

## [2026-02-10T14:49:37] Task 2: Prompt 设计完成
- 四维独立 prompt 已创建：I/C/O/V
- C 维 prompt 明确要求从题面全文提取约束（description + input + output + constraints）
- qwen_client.py 已修正 lstrip bug（使用 removeprefix 替代 lstrip）
- 验证测试通过：2 道题 x 4 维度 = 8 个 prompt 全部构造正确
- 证据文件：.sisyphus/evidence/task-2-prompt-validation.json
## [2026-02-10 14:38] Wave 1 完成

### Task 1: 数据采样
- Phase 1 样本: 1500 题（luogu: 500, codeforces: 500, icpc_gym: 500）
- Pilot 样本: 50 题（Phase 1 子集）
- 随机种子: 42（可复现）
- 字段完整性: 7 个必需字段全部包含

### Task 2: Prompt 设计
- 四维独立 prompt 已创建（I/C/O/V）
- C 维 prompt 明确要求从题面全文提取约束（description+input+output+constraints）
- qwen_client.py 已修正 lstrip bug（使用 removeprefix）
- 验证测试通过（2 题 × 4 维度 = 8 prompts）

### 关键决策记录
- 维度独立抽取：每个维度单独 prompt，避免一次性五元组抽取的一致性问题
- System/User 分离：遵循 ICPC 项目范式
- 约束提取规则：从题面全文提取（不仅依赖 constraints 字段）

---


## [2026-02-10T16:04:13] Task 3: Pilot Run 核心代码创建完成

### 创建的文件
- extract.py (9024 bytes) - 主抽取管线，支持多轮采样、断点续传、速率限制
- normalize.py (8183 bytes) - 同义词归一化，统一不同表达
- vote.py (8525 bytes) - 多数投票机制，选择最一致的结果
- README_TASK3.md (5174 bytes) - 完整的使用说明和故障排查指南

### 关键设计决策
- RateLimiter 本地实现（复用爬虫项目模式）：确保 API 调用间隔 ≥ 1 秒
- 断点续传机制：通过检查输出文件是否存在，跳过已完成任务
- 输出目录三层结构：raw/ → normalized/ → voted/
- CLI 参数设计：--input, --output, --rounds, --resume, --log-level

### 同义词归一化策略
- 四维独立同义词表（SYNONYM_MAP）
- I 维：1d array/sequence/list → array, directed_graph/undirected_graph → graph
- C 维：distinct_count_leq_k/unique_count_leq_k → distinct_leq_k
- O 维：maximize_length/maximise_length → max_length
- V 维：two_pointer/2_pointer → two_pointers, sliding_window_monotonicity → monotonicity

### 投票机制
- I/O/V 维度：基于 type/name 字段进行 Counter 投票
- C 维度：基于约束名称集合投票，出现 ≥2 次的约束保留
- 置信度标注：3/3（一致）、2/3（多数）、1/3（分歧）

### 验证结果
- 所有文件语法检查通过（py_compile）
- CLI 帮助信息正常显示
- 模块导入结构正确（以 -m 模式运行）

### 阻塞问题（已记录）
- API Key 未设置（DASHSCOPE_API_KEY 和 QWEN_API_KEY 均为 NOT_SET）
- 需用户设置后才能运行 Pilot Run
- 已在 README_TASK3.md 中提供详细设置指南

### 下一步
1. 用户设置 API Key
2. 运行 Pilot Run（50 题 × 4 维 × 3 轮 = 600 次 API 调用）
3. 验证输出完整性（50 个 voted JSON 文件）
4. 继续 Task 4（Phase 1 全量抽取）

---


## [2026-02-10T16:04:47] Task 3: Pilot Run 核心代码创建完成

### 创建的文件
- extract.py (9024 bytes) - 主抽取管线，支持多轮采样、断点续传、速率限制
- normalize.py (8183 bytes) - 同义词归一化，统一不同表达
- vote.py (8525 bytes) - 多数投票机制，选择最一致的结果
- README_TASK3.md (5174 bytes) - 完整的使用说明和故障排查指南

### 关键设计决策
- RateLimiter 本地实现（复用爬虫项目模式）：确保 API 调用间隔 >= 1 秒
- 断点续传机制：通过检查输出文件是否存在，跳过已完成任务
- 输出目录三层结构：raw/ -> normalized/ -> voted/
- CLI 参数设计：--input, --output, --rounds, --resume, --log-level

### 同义词归一化策略
- 四维独立同义词表（SYNONYM_MAP）
- I 维：1d array/sequence/list -> array, directed_graph/undirected_graph -> graph
- C 维：distinct_count_leq_k/unique_count_leq_k -> distinct_leq_k
- O 维：maximize_length/maximise_length -> max_length
- V 维：two_pointer/2_pointer -> two_pointers, sliding_window_monotonicity -> monotonicity

### 投票机制
- I/O/V 维度：基于 type/name 字段进行 Counter 投票
- C 维度：基于约束名称集合投票，出现 >=2 次的约束保留
- 置信度标注：3/3（一致）、2/3（多数）、1/3（分歧）

### 验证结果
- 所有文件语法检查通过（py_compile）
- CLI 帮助信息正常显示
- 模块导入结构正确（以 -m 模式运行）

### 阻塞问题（已记录）
- API Key 未设置（DASHSCOPE_API_KEY 和 QWEN_API_KEY 均为 NOT_SET）
- 需用户设置后才能运行 Pilot Run
- 已在 README_TASK3.md 中提供详细设置指南

### 下一步
1. 用户设置 API Key
2. 运行 Pilot Run（50 题 x 4 维 x 3 轮 = 600 次 API 调用）
3. 验证输出完整性（50 个 voted JSON 文件）
4. 继续 Task 4（Phase 1 全量抽取）

---


## [2026-02-10T16:10:30] Task 4: 饱和曲线分析工具创建完成

### 创建的文件
- analyze.py (10,247 bytes) - 饱和曲线分析、收敛指标计算、有限性判定
- README_TASK4.md - Phase 1 全量抽取与分析流程说明

### 核心算法
1. **标签收集算法**：
   - 从 voted/ 目录遍历所有 JSON
   - 提取每维的唯一标签（I: type, C: constraints[*].name, O: type, V: name）
   - 记录时间线：(题目序号, 新增标签)

2. **饱和曲线生成**：
   - X 轴：累计题目数
   - Y 轴：累计标签数
   - 拟合函数：对数函数 y = a * log(x) + b
   - 回退：若对数拟合失败，使用线性拟合

3. **收敛指标**：
   - R²（拟合优度）：衡量曲线收敛程度
   - 尾部新增率：最后 100 题中新增标签数 / 100
   - 总标签数：该维度的唯一标签总数

4. **有限性判定阈值**：
   - FINITE: R² > 0.95 且尾部新增率 < 2%
   - LIKELY_FINITE: R² > 0.90 且尾部新增率 < 5%
   - UNCERTAIN: R² > 0.80 或收敛不明显

### 输出文件
- labels_per_dimension.json — 每维标签集合（可扩展的归一化词表）
- saturation_curves/*.png — 四维饱和曲线图（matplotlib 可视化）
- metrics.json — 收敛指标（R²、tail_rate、total_labels、log_fit_params）
- finiteness_judgment.json — 判定结果（FINITE/LIKELY_FINITE/UNCERTAIN）

### 依赖验证
- numpy: OK
- scipy: OK
- matplotlib: OK

### 预期结果
- I 维：FINITE（数据结构类型有限：array, graph, tree, string, matrix 等）
- O 维：FINITE/LIKELY_FINITE（优化目标类型有限：min/max + length/cost/sum/path 等）
- C 维：LIKELY_FINITE（原子约束有限，但组合可能较多）
- V 维：UNCERTAIN/LIKELY_FINITE（算法不变量种类较多，需更多数据）

### 下一步
1. 等待 Task 3 Pilot Run 完成验证
2. 运行 Phase 1 抽取（1500 题 × 3 轮 = 18000 次 API 调用，约 5 小时）
3. 运行 analyze.py 生成饱和曲线
4. 根据判定结果决定是否需要 Task 5 封闭分类

---

