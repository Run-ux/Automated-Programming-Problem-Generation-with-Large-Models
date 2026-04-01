# 生成题面 Codex

该目录实现了“规则驱动的四元组生成器”。输入来自 `finiteness_verification/output/pilot/voted/*.json`，生成链路围绕四元组 `input_structure / core_constraints / objective / invariant` 展开，输出包括：

- `output/*.md`：最终 Markdown 题面
- `artifacts/*.json`：规则决策轨迹、实例化四元组和模型返回结果
- `reports/*.md`：每次运行的过程说明

## 流程

1. 读取上游 voted schema，并归一化为四元组
2. 根据 `mode` 与 `planning_rules.json` 整理可用规则
3. 先让 LLM 在可用规则中选出最适合当前 schema 的规则，目标是创新度和难度尽可能高
4. 再按选中的规则实例化新四元组；若硬门槛不通过就显式放弃
5. 把规划结果交给题面生成阶段，要求模型输出严格 JSON
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

- `global_constraints`
- `global_redlines`
- `modes.single_seed_extension`
- `modes.same_family_fusion`
- `modes.cross_family_fusion`

## 模式说明

### `single_seed_extension`

首版固定 4 条规则：

- `canonical_witness`
- `construct_or_obstruction`
- `existence_to_counting`
- `minimum_guarantee_under_perturbation`

每次只允许“一主一卡 + 辅助手法”。运行时会先做规则选择，再按选中的规则规划；如果该规则仍无法通过硬门槛，artifact 会显式记录放弃原因。

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

artifact 保留了旧壳字段，便于兼容旧消费者：

- `difference_plan`
- `predicted_schema_distance`
- `changed_axes_realized`
- `instantiated_schema_snapshot`

同时新增了规则驱动链路需要的字段：

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

四轴距离只保留 `I / C / O / V`。为了兼容旧消费者，`distance_breakdown.T = 0.0` 仍会写入 artifact。

## 兼容说明

`schema_preparer.py` 仍负责四元组归一化。若旧 schema 自带 `transform_space`，当前实现只做历史兼容读取，不再把它用于 planner、提示词或 artifact 决策。
