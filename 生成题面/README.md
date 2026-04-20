# 生成题面 Codex

该目录实现了“规则驱动的四元组生成器”。当前版本采用“规则声明 + 代码执行”架构：规则文件负责声明元信息、审计标签与合同入口，`rule_handlers.py` 负责组织资格判断、规划校验、题面校验与审计事件生成。资格判断阶段会先调用 LLM，并通过角色审查式提示词完成单规则准入审查；规划校验和题面校验会先经过代码级通用硬门槛，再由每条规则各自的 LLM 审查提示词完成专属语义审查。默认输入来自 `D:/AutoProblemGen/四元组抽取/output/batch/normalized/*.json`，生成链路围绕四元组 `input_structure / core_constraints / objective / invariant` 展开，输出包括：

- `output/<problem_id>/*.md`：最终 Markdown 题面；`same_family` 模式使用 `output/<seed_a>__<seed_b>/`
- `artifacts/<problem_id>/*.json`：规则决策轨迹、实例化四元组、模型返回结果与迭代摘要；`same_family` 模式使用 `artifacts/<seed_a>__<seed_b>/`
- `reports/<problem_id>/*.md`：单题人工排查报告。成功题会对比原题与新题四元组，失败题会给出失败原因、原题四元组与候选规则结论；`same_family` 模式使用 `reports/<seed_a>__<seed_b>/`
- `artifacts/batch_*.json`：目录批量生成时的整批汇总

## 流程

1. 读取上游四元组 schema
2. 根据 `mode` 与 `planning_rules.json` 整理可用规则
3. 先由 LLM 按角色提示词完成单规则资格审查，再由 handler 解释审查结果并进入排序式规则选择
4. 按候选顺序规划，先执行代码级通用硬门槛，再执行规则专属 LLM 规划审查；首选失败时会自动回退到下一候选
5. 把规划结果交给题面生成阶段，要求模型输出严格 JSON，并在通用结构校验后执行规则专属 LLM 题面审查
6. 若启用质量闭环，调用 `题目质量评价` 生成质量报告，并把结构化 `revision_brief` 回流给下一轮规划和题面生成
7. 渲染为标准 OJ 风格 Markdown，并把 artifact、质量报告、过程报告与迭代摘要落盘

当前启用的模式只有两种：

- `single_seed_extension`
- `same_family_fusion`

`cross_family_fusion` 仅在规则文件中保留占位，本轮不支持运行。

## 运行

安装依赖：

```bash
pip install -r requirements.txt
```

配置环境变量。运行时只读取 [生成题面/.env](/D:/AutoProblemGen/生成题面/.env) 中的这些值。可直接参考 [生成题面/.env.example](/D:/AutoProblemGen/生成题面/.env.example)：

```dotenv
DASHSCOPE_API_KEY=your_key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen3.5-plus
QWEN_EMBEDDING_MODEL=text-embedding-v4
QWEN_TIMEOUT_S=180
```

单题扩展：

```bash
python main.py --mode single --problem-ids CF25E CF360C --variants 2
```

目录批量生成：

```bash
python main.py --mode single --source-dir D:/AutoProblemGen/四元组抽取/output/batch/normalized
```

同类融合：

```bash
python main.py --mode same_family --seed-a CF25E --seed-b CF360C --variants 1
```

指定规则：

```bash
python main.py --mode single --problem-ids CF25E --rule-override canonical_witness
```

自定义超时：

```bash
python main.py --mode single --problem-ids CF25E --timeout 360
```

启用最多 3 轮的质量闭环：

```bash
python main.py --mode single --problem-ids CF25E --quality-iterations 3
```

当 `single` 模式省略 `--problem-ids` 时，系统会把 `--source-dir` 当前层级下的全部 `*.json` 文件视为一批任务，按文件名字典序逐个生成。批量模式要求每个文件显式提供 `problem_id`，并且该值必须与文件名一致。若中途某一题在规划、生成或落盘阶段报错，该题会被记为失败并写入批量汇总，后续题目继续执行；此前已经成功落盘的结果会保留，单题产物继续按题目子目录写入，同时额外在 `artifacts/` 根目录写出 `batch_*.json` 作为整批汇总。

`--quality-iterations` 只对 `single` 模式生效：

- `0`：关闭质量闭环，保持旧行为
- `1`：生成 1 轮并产出质量报告与迭代摘要
- `2`、`3`：分别表示最多执行 2 轮或 3 轮；若任一轮 `pass`、`reject_invalid`、`schema_insufficient` 或 `difference_insufficient`，流程会提前停止

运行过程中，控制台会输出当前阶段提示，包括参数校验、进入流水线、当前题、当前 variant、规划、题面生成、产物写入与批量完成状态。

## CLI

`main.py` 当前支持的 CLI 参数如下。

| 参数 | 说明 | 默认值 | 适用范围 |
| --- | --- | --- | --- |
| `--mode single\|same_family` | 运行模式，`single` 对应 `single_seed_extension`，`same_family` 对应 `same_family_fusion` | 必填 | 全局 |
| `--problem-ids <id...>` | `single` 模式下指定待生成的 `problem id` 列表；省略时进入目录批量生成 | 空列表 | 仅 `single` |
| `--seed-a <id>` | `same_family` 模式下的第一个种子题 `problem id` | 无 | 仅 `same_family` |
| `--seed-b <id>` | `same_family` 模式下的第二个种子题 `problem id` | 无 | 仅 `same_family` |
| `--variants <数量>` | 每个任务生成的变体数 | `1` | 全局 |
| `--theme <theme id>` | 固定主题，当前可选 `cyber_city`、`arcane_lab`、`interstellar_logistics`、`campus_ops` | 无 | 全局 |
| `--source-dir <schema目录>` | 原始 schema JSON 目录 | `D:/AutoProblemGen/四元组抽取/output/batch/normalized` | 全局 |
| `--output-dir <md输出目录>` | Markdown 题面输出目录 | 见 `config.py` | 全局 |
| `--artifact-dir <json输出目录>` | 结构化产物输出目录 | 见 `config.py` | 全局 |
| `--report-dir <过程报告目录>` | 过程说明 Markdown 输出目录 | 见 `config.py` | 全局 |
| `--rule-file <规则文件>` | 规则 JSON 文件路径 | 见 `config.py` | 全局 |
| `--timeout <秒数>` | 模型接口请求超时秒数 | `QWEN_TIMEOUT_S` 或 `180` | 全局 |
| `--temperature <采样温度>` | 题面生成采样温度 | `0.2` | 全局 |
| `--seed <随机种子>` | 规则规划随机种子 | `20260312` | 全局 |
| `--quality-iterations <轮数>` | 质量闭环轮数，只支持 `0`、`1`、`2`、`3` | `0` | 仅 `single` |
| `--rule-override <rule id>` | 限定可用规则 id，可重复传入，也可用逗号分隔 | 空列表 | 全局 |

参数校验规则：

- `single` 模式下不能传 `--seed-a` 或 `--seed-b`
- `same_family` 模式下必须同时提供 `--seed-a` 和 `--seed-b`
- `same_family` 模式下不能传 `--problem-ids`
- `same_family` 模式下当前不能启用 `--quality-iterations`
- `single` 模式若省略 `--problem-ids`，会按 `--source-dir` 下的全部 `*.json` 文件做批量生成
- 批量模式要求每个 schema 文件都显式包含 `problem_id`，且该值必须与文件名一致

## 规则配置

规则文件为 `planning_rules.json`，顶层结构固定为：

- `version`
- `global_constraints`
- `global_redlines`
- `modes.single_seed_extension`
- `modes.same_family_fusion`
- `modes.cross_family_fusion`

`global_constraints` 当前只保留代码级开关，已生效的字段是：

- `allow_helper_moves`

`global_redlines` 当前只保留：

- `items`

每个 mode 可以声明自己的默认 `planner_output_contract.required_fields`。规则会继承该默认合同，再追加本条规则的增量字段。

每条规则至少包含以下执行字段：

- `id`
- `family`
- `audit_tags`
- `handler`
- `enabled`
- `required_axis_changes.must_change`
- `helpers`
- `planner_output_contract.required_fields`

每条规则还可以包含以下说明字段：

- `summary`
- `eligibility`
- `core_transformation`
- `validation_contract`
- `examples`
- `failure_templates`

`handler` 会映射到 `rule_handlers.py` 里的实现。规则文件中的声明只有在对应 handler 中有执行逻辑时才真正生效。

`helpers` 采用 rule 级结构化定义。每条已启用规则都必须声明自己的全部 helper。planner 选中该规则后，必须在 `applied_helpers` 中逐条兑现这些 helper，不能只选其中一部分。helper 的稳定语义由 `summary` 承担。

已启用规则的 `required_axis_changes.must_change` 必须与该规则全部 helper 的 `target_axes` 并集完全一致。在 helper 全量强制应用的前提下，这个并集就是规则的实际硬合同。

`validation_contract` 当前仍主要服务规则专属 LLM 审查，不参与代码级硬校验。代码级硬校验目前集中在 required fields、helper 全量兑现、变化轴门槛和通用结构门槛。

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
- `new_schema_snapshot`
- `mode`
- `source_problem_ids`
- `applied_rule`
- `rule_selection_reason`
- `rejected_candidates`
- `algorithmic_delta_claim`
- `applied_helpers`
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

`distance_breakdown` 当前采用 `Schema Distance V2`，顶层字段为：

- `distance_version`
- `backend`
- `total`
- `axis_scores`
- `components`

其中 `axis_scores` 仍使用 `I / C / O / V` 四轴，`components` 会展开：

- `input_tree_distance`
- `constraint_match_distance`
- `objective_type_distance`
- `objective_text_distance`
- `invariant_match_distance`

`backend=embedding` 表示距离由远端 embedding 计算驱动。若 embedding 调用失败、客户端缺失或返回结构异常，流程会直接报错，不再回退到词法相似度。

`selection_trace` 记录每条规则的资格结论、分数、风险标签与尝试顺位。`validation_trace` 记录规划阶段和题面阶段的结构化审计事件，其中包含规则专属 LLM 审查的证据摘录。`candidate_attempts` 记录每次候选尝试的状态、失败码与失败原因。`applied_helpers` 记录当前规则的全部 helper 如何落到变化轴、schema 变更、创新度提升与难度提升上。

启用质量闭环后，单轮 artifact 还会新增 `iteration` 字段：

- `run_id`
- `round_index`
- `requested_rounds`
- `previous_artifact_path`
- `previous_quality_report_path`
- `revision_context_snapshot`

各轮题面和 artifact 会分别以 `_round1`、`_round2`、`_round3` 结尾落盘。每个 variant 还会额外写出 `*_iteration_summary.json`，其中包含：

- 每轮 artifact 路径
- 每轮 markdown 路径
- 每轮质量报告路径
- 每轮总体状态与分数
- 最终采用轮次
- 停止原因

目录批量生成会额外产出 `batch_*.json`。其中会记录：

- `source_dir`
- `task_order`
- `task_count`
- `completed_count`
- `failed_count`
- `status`
- `failed_problem_id`
- `failed_reason`
- `started_at`
- `finished_at`
- `items`

`items` 会按执行顺序列出每个 problem id 的状态、错误信息，以及该题生成出的 markdown、artifact、report 路径。

`reports/<problem_id>/*.md` 只承担人工阅读职责，不再重复展开 artifact 中的完整审计轨迹。成功题报告会用表格对比原题与新题的输入结构、核心约束、求解目标和关键不变量；失败题报告会保留原题四元组、失败原因、候选规则结论与建议方向。`same_family` 模式使用 `reports/<seed_a>__<seed_b>/`。

质量闭环模式下，每道题对应的报告子目录下还会新增 `*_quality_report.json` 与 `*_quality_report.md`。对应轮次的 artifact、题面 Markdown 与 `*_iteration_summary.json` 会分别进入同名题目子目录下的 `artifacts/` 与 `output/`。第二轮不会直接复用第一轮 Markdown 报告原文，而是只消费其中的结构化 `revision_brief`。

## Schema 合同

planner、提示词、artifact 和题面生成链路只接受四元组与必要元信息。`new_schema` 只允许 `problem_id`、`source`、`input_structure`、`core_constraints`、`objective`、`invariant`，以及可选的 `theme`、`difficulty`。

## 规则开发

新增规则时，除了更新 `planning_rules.json`，还需要同步完成：

- 在 `rule_handlers.py` 注册对应 `handler`
- 实现 `check_eligibility`、`validate_plan`、`validate_problem`
  其中 `check_eligibility` 负责定义资格审查角色并发起 LLM 准入判断；`validate_plan` 和 `validate_problem` 负责先执行通用硬门槛，再发起规则专属 LLM 审查，并把结果转成结构化审计记录
- 补对应测试
- 更新文档

详细约定见 [RULES.md](RULES.md)。
