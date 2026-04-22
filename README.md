# AutoProblemGen

## 当前仓库结构

| 目录                        | 定位                                                                                           | 当前状态               |
| --------------------------- | ---------------------------------------------------------------------------------------------- | ---------------------- |
| `论文`                    | 研究资料、论文阅读、Problem Schema 设计与改编思路                                              | 研究设计层             |
| `爬取题目`                | 从 Codeforces、AtCoder、Luogu、ICPC 等来源采集题目并落盘                                       | 数据入口               |
| `四元组抽取`              | 从单题 schema JSON 抽取并归一化 `input_structure / core_constraints / objective / invariant` | 当前生成链路的默认上游 |
| `finiteness_verification` | 通过 Pilot、Phase 1、Phase 2 验证四维标签集合是否有限、稳定、可覆盖                            | 标签体系验证           |
| `生成题面`                | 基于四元组、规则文件和两阶段 LLM 规划生成结构化题面                                            | 当前生成器             |
| `题目质量评价`            | 对生成 artifact 做题面质量评分、反换皮判定、硬约束检查，并输出 `revision_brief`              | 当前质量闭环           |
| `题包生成验证`            | 生成标准解、oracle、validator、checker、测试生成器和错误解池，并真实执行验证                   | 当前交付验证           |

## 主线流程

### 1. 数据采集

`爬取题目` 负责从多个平台抓取题目，并以统一格式保存到 `output/<platform>/`。当前已有题库规模包括：

- `codeforces`：2201 道
- `icpc`：3149 道
- `luogu`：7903 道

这些数据既服务于有限性验证，也为后续 curated schema 输入提供原始题目来源。

### 2. 四元组抽取

`四元组抽取` 是当前生成链路的直接上游，默认输入来自：

```text
爬取题目/output/imandra_curated_schema_inputs/*.json
```

它把单题题面与可选标准解法抽取成四个稳定维度：

- `input_structure`：输入载体、组件、长度、取值范围与结构性质
- `core_constraints`：题目必须满足的核心约束
- `objective`：求解目标、目标类型与目标对象
- `invariant`：题面或代码可支撑的稳定维护性质

典型流程：

```powershell
cd D:\AutoProblemGen\四元组抽取

python extract.py --input D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs --output output\batch\ --resume

python normalize.py --input output\batch\raw\ --output output\batch\normalized\ --embedding-threshold 0.85
```

最终可消费结果位于：

```text
四元组抽取/output/batch/normalized/*.json
```

详细字段约定见 [`四元组抽取/README.md`](四元组抽取/README.md)。

### 3. 有限性验证

`finiteness_verification` 不是当前生成器的默认输入目录，而是用于验证 `I/C/O/V` 标签体系是否足够稳定：

- `Pilot`：小样本多轮抽取、归一化、投票
- `Phase 1`：3000 题样本抽取并绘制饱和曲线
- `Phase 2`：使用 Phase 1 标签集对全量题库做封闭分类与覆盖率报告

这个模块回答的是“Schema 四维能否形成可控中间表示”，而不是直接生成题面。详细流程见：

- [`finiteness_verification/README_PHASE1.md`](finiteness_verification/README_PHASE1.md)
- [`finiteness_verification/README_PHASE2.md`](finiteness_verification/README_PHASE2.md)

## 5. `生成题面`

`生成题面` 是当前正式生成器。它读取归一化四元组，结合 `planning_rules.json` 和规则 handler 完成规则资格审查、规划校验、题面生成、题面审查与产物落盘。

当前支持的运行模式：

- `single_seed_extension`：CLI 中对应 `--mode single`
- `same_family_fusion`：CLI 中对应 `--mode same_family`

`cross_family_fusion` 仅保留规则文件占位，当前不宣称支持运行。

单题生成示例：

```powershell
cd D:\AutoProblemGen\生成题面

python main.py --mode single --problem-ids CF25E --variants 1
```

目录批量生成示例：

```powershell
python main.py --mode single --source-dir D:\AutoProblemGen\四元组抽取\output\batch\normalized
```

同类融合示例：

```powershell
python main.py --mode same_family --seed-a CF25E --seed-b CF360C --variants 1
```

可选质量闭环：

```powershell
python main.py --mode single --problem-ids CF25E --quality-iterations 3
```

质量闭环只在 `single_seed_extension` 中启用。正常阶段最多执行 `--quality-iterations` 指定的 1 到 3 轮；`revise_quality` 和 `reject_as_retheme` 会把结构化 `revision_brief` 回流给下一轮规划与题面生成。若某轮 `overall.status` 为 `pass`，生成器还会检查五个质量维度 `variant_fidelity`、`spec_completeness`、`cross_section_consistency`、`sample_quality`、`oj_readability` 是否全部为 5 分。

当 `pass` 但五维未满分时，流程进入满分打磨阶段：复用上一轮 `VariantPlan` 和同一个 `new_schema`，不再调用 planner，也不重新生成 schema，只允许重写题面内容并继续评测。追加轮数由 `--quality-full-score-max-iterations` 控制，默认 10 轮；仍未满分时以 `full_score_iteration_limit_reached` 停止。

主要输出：

- `生成题面/output/<problem_id>/*.md`：最终 Markdown 题面
- `生成题面/artifacts/<problem_id>/*.json`：规则决策、实例化四元组、模型返回与迭代摘要
- `生成题面/reports/<problem_id>/*.md`：人工排查报告
- `生成题面/artifacts/batch_*.json`：批量生成汇总

artifact 会记录 `mode`、`source_problem_ids`、`applied_rule`、`rule_selection_reason`、`rejected_candidates`、`algorithmic_delta_claim`、`applied_helpers`、`selection_trace`、`validation_trace`、`candidate_attempts` 与 `distance_breakdown`。启用质量闭环后还会增加 `iteration` 元信息和 `*_iteration_summary.json`，其中包含每轮质量报告路径、质量维度分数、迭代阶段、最终采用轮次与停止原因。

详细 CLI、规则合同和 artifact 字段见 [`生成题面/README.md`](生成题面/README.md)。

## 6. `题目质量评价`

`题目质量评价` 直接消费 `生成题面` 的 artifact，并结合源 schema 与原题做综合评估。

它会输出两类结论：

- 题面质量：`variant_fidelity`、`spec_completeness`、`cross_section_consistency`、`sample_quality`、`oj_readability`
- 反换皮判断：`schema_distance`、`semantic_difference`、`solution_transfer_risk`、`surface_retheme_risk`

最终状态包括：

- `pass`
- `revise_quality`
- `reject_as_retheme`
- `reject_invalid`

评估器还会输出结构化 `revision_brief`。当 `生成题面` 启用 `--quality-iterations` 时，该摘要会回流给下一轮规划和题面生成；默认单轮生成不会强制进入闭环。

运行示例：

```powershell
cd D:\AutoProblemGen\题目质量评价

python main.py ^
  --schema D:\AutoProblemGen\四元组抽取\output\batch\normalized\CF1513D.json ^
  --artifact D:\AutoProblemGen\生成题面\artifacts\CF1513D\CF1513D_v1_campus_ops_20260420_215028_round1.json
```

详细合同见 [`题目质量评价/README.md`](题目质量评价/README.md)。

### 6. 题包生成验证

`题包生成验证` 是当前链路的后续交付验证模块。它接收生成题面的 artifact 与 Markdown 题面，生成并执行：

- `execution_spec.json`
- `standard_solution.py`
- `oracle_solution.py`
- `validator.py`
- `checker.py`
- `test_generator.py`
- `wrong_solutions/`
- `execution_report.json`

运行示例：

```powershell
cd D:\AutoProblemGen\题包生成验证

python main.py ^
  --artifact D:\AutoProblemGen\生成题面\artifacts\...\round1.json ^
  --markdown D:\AutoProblemGen\生成题面\output\...\round1.md ^
  --rounds 3
```

默认输出：

```text
题包生成验证/output/<problem_id>/<run_id>/
  round1/
  round2/
  final/
  iteration_summary.json
```

v1 只支持 Python 代码执行，不自动修改上游题面。若题面或输出合同存在歧义，报告会标记为 `statement_revision_required` 或相关失败类型，由上游生成流程处理。详细说明见 [`题包生成验证/README.md`](题包生成验证/README.md)。

## Schema Distance V2

生成器当前使用结构化距离衡量原始 schema 与实例化 schema 的差异：

```text
total = 0.25 * I + 0.30 * C + 0.25 * O + 0.20 * V
```

四轴含义：

- `I`：输入结构距离，基于输入树编辑距离
- `C`：核心约束距离，基于集合匹配
- `O`：目标函数距离，由目标类型距离和目标文本距离组合
- `V`：不变量距离，基于集合匹配

`distance_breakdown` 顶层字段包括：

- `distance_version`
- `backend`
- `total`
- `axis_scores`
- `components`

当前 `生成题面` 模块要求 embedding 后端可用；embedding 客户端缺失、调用失败或返回结构异常时会直接报错，不再回退到词法相似度。

`changed_axes_realized` 使用固定阈值判断变化是否落地：

- `I >= 0.18`
- `C >= 0.25`
- `O >= 0.18`
- `V >= 0.18`

## 环境配置

当前几个主线模块都采用模块级 `.env` 配置，优先读取各自目录下的 `.env`，可参考对应 `.env.example`：

- `四元组抽取/.env.example`
- `生成题面/.env.example`
- `题目质量评价/.env.example`

常用配置项：

```dotenv
DASHSCOPE_API_KEY=your_key
QWEN_API_KEY=your_key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen3.6-plus
QWEN_EMBEDDING_MODEL=text-embedding-v4
QWEN_TIMEOUT_S=180
```

不同模块的默认模型、超时与输出目录以各自 `config.py` 为准。

## 测试

当前仓库按模块维护测试。常用命令：

```powershell
python -m unittest discover -s D:\AutoProblemGen\生成题面\tests -v

python -m unittest discover -s D:\AutoProblemGen\题目质量评价\tests -v

python -m unittest discover -s D:\AutoProblemGen\题包生成验证\tests -v
```

`四元组抽取` 可运行：

```powershell
cd D:\AutoProblemGen\四元组抽取

python verify_prompts_structure.py
python -m unittest test_normalize.py
```
