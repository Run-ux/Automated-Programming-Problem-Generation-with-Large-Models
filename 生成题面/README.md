# 生成题面 Codex

该目录实现了“规则驱动的四元组生成器”。当前版本采用“规则声明 + 代码执行”架构：规则文件负责声明元信息、审计标签与合同入口，`rule_handlers.py` 负责组织资格判断、规划校验、题面校验与审计事件生成。资格判断阶段会先调用 LLM，并通过角色审查式提示词完成单规则准入审查；handler 继续负责解释结果、执行硬校验和生成审计事件。输入来自 `finiteness_verification/output/pilot/voted/*.json`，生成链路围绕四元组 `input_structure / core_constraints / objective / invariant` 展开，输出包括：

- `output/*.md`：最终 Markdown 题面
- `artifacts/*.json`：规则决策轨迹、实例化四元组和模型返回结果
- `reports/*.md`：每次运行的过程说明

## 流程

1. 读取上游 voted schema，并归一化为四元组
2. 根据 `mode` 与 `planning_rules.json` 整理可用规则
3. 先由 LLM 按角色提示词完成单规则资格审查，再由 handler 解释审查结果并进入排序式规则选择
4. 按候选顺序规划并做代码级规则校验；首选失败时会自动回退到下一候选
5. 把规划结果交给题面生成阶段，要求模型输出严格 JSON，并执行规则专属题面校验
6. 渲染为标准 OJ 风格 Markdown，并把 artifact 与报告落盘

当前启用的模式只有两种：

- `single_seed_extension`
- `same_family_fusion`

`cross_family_fusion` 仅在规则文件中保留占位，本轮不支持运行。

## 运行

安装依赖：

```bash
pip install -r requirements.txt
```

配置环境变量：

```bash
set DASHSCOPE_API_KEY=your_key
```

单题扩展：

```bash
python main.py --mode single --problem-ids CF25E CF360C --variants 2
```

同类融合：

```bash
python main.py --mode same_family --seed-a CF25E --seed-b CF360C --variants 1
```

指定规则：

```bash
python main.py --mode single --problem-ids CF25E --rule-override canonical_witness
```

## CLI

- `--mode single|same_family`
- `--problem-ids <id...>`：仅 `single` 模式使用
- `--seed-a <id>`、`--seed-b <id>`：仅 `same_family` 模式使用
- `--variants <数量>`
- `--theme cyber_city|arcane_lab|interstellar_logistics|campus_ops`
- `--source-dir <schema目录>`
- `--prepared-schema-dir <归一化缓存目录>`
- `--output-dir <md输出目录>`
- `--artifact-dir <json输出目录>`
- `--report-dir <过程报告目录>`
- `--rule-file <规则文件>`
- `--model <模型名>`
- `--base-url <API地址>`
- `--temperature <采样温度>`
- `--seed <随机种子>`
- `--rule-override <rule id>`：可重复传入，也可用逗号分隔

## 规则配置

规则文件为 `planning_rules.json`，顶层结构固定为：

- `version`
- `global_constraints`
- `global_redlines`
- `modes.single_seed_extension`
- `modes.same_family_fusion`
- `modes.cross_family_fusion`

每条规则至少包含以下稳定字段：

- `id`
- `family`
- `audit_tags`
- `handler`

`handler` 会映射到 `rule_handlers.py` 里的实现。规则文件中的声明只有在对应 handler 中有执行逻辑时才真正生效。

## 模式说明

### `single_seed_extension`

首版固定 4 条规则：

- `canonical_witness`
- `construct_or_obstruction`
- `existence_to_counting`
- `minimum_guarantee_under_perturbation`

每次只允许一条主规则。运行时会先对每条规则发起一次角色审查式资格校验，再做排序式规则选择，随后按前 2 到 3 条候选顺序规划；如果前一候选没有通过硬门槛，会自动回退到下一候选。artifact 会记录所有候选尝试与拒绝原因。

### `same_family_fusion`

首版固定 2 条规则：

- `interlocked_constraints`
- `shared_core_objective_upgrade`

运行时必须显式传入 `seed_a` 与 `seed_b`。当前实现会检查：

- 固定 2 题
- 双向对等融合
- 单主核
- 两题各自贡献一项不可删核心义务
- 反串联论证
- 消融论证

## Artifact

artifact 当前围绕规则驱动链路、审计轨迹和实例化四元组组织，核心字段包括：

- `rule_version`
- `difference_plan`
- `predicted_schema_distance`
- `changed_axes_realized`
- `instantiated_schema_snapshot`
- `mode`
- `source_problem_ids`
- `applied_rule`
- `rule_selection_reason`
- `rejected_candidates`
- `algorithmic_delta_claim`
- `shared_core_summary`
- `shared_core_anchors`
- `seed_contributions`
- `fusion_ablation`
- `planning_status`
- `planning_error_reason`
- `planning_feedback`
- `selection_trace`
- `validation_trace`
- `candidate_attempts`

其中 `algorithmic_delta_claim.new_proof_obligation` 表示新增正确性证明，用来描述新题相对种子题多出来的关键证明点。

`distance_breakdown` 只包含 `I / C / O / V / total`。

`selection_trace` 记录每条规则的资格结论、分数、风险标签与尝试顺位。`validation_trace` 记录规划阶段和题面阶段的结构化审计事件。`candidate_attempts` 记录每次候选尝试的状态、失败码与失败原因。

## Schema 合同

`schema_preparer.py` 负责把上游输入归一化为四元组。

planner、提示词、artifact 和题面生成链路只接受四元组与必要元信息。`instantiated_schema` 只允许 `problem_id`、`source`、`input_structure`、`core_constraints`、`objective`、`invariant`，以及可选的 `theme`、`difficulty`。

## 规则开发

新增规则时，除了更新 `planning_rules.json`，还需要同步完成：

- 在 `rule_handlers.py` 注册对应 `handler`
- 实现 `check_eligibility`、`validate_plan`、`validate_problem`
  其中 `check_eligibility` 负责定义审查角色、发起 LLM 准入判断并把结果转成结构化审计记录
- 补对应测试
- 更新文档

详细约定见 [RULES.md](RULES.md)。
