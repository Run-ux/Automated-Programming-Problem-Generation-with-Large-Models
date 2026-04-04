# AutoProblemGen

本仓库围绕一个核心目标展开：不是让大模型“自由发挥写一道新题”，而是先把已有高质量竞赛题抽象成可操作的 `Problem Schema`，再通过规则驱动的四元组规划生成新题，并用结构化评估去判断它是不是一题真正的新题。

仓库当前包含研究资料、题目采集、Schema/母题实验、有限性验证、题面生成、质量评估，以及若干历史原型。根目录下每个文件夹都对应这条主线中的一个阶段或一个独立实验方向。

## 仓库整体主线

当前最完整的一条工程链路可以概括为：

```text
论文
  -> 明确 Problem Schema、母题、规则设计、评估标准

爬取题目 / 母题代码
  -> 收集原始题目文本
  -> 解析成统一格式
  -> 早期尝试抽取 Schema 和构建母题库

finiteness_verification
  -> 对 I/C/O/V 四维做抽取、归一化、投票、统计
  -> 验证标签集合是否有限、是否可形成稳定分类体系
  -> 为后续生成提供 voted schema 与标签边界

生成题面
  -> 规则规划
  -> 实例化四元组
  -> 调用模型生成结构化题面
  -> 输出 Markdown、artifact、过程报告

题目质量评价
  -> 消费规则决策轨迹与四轴距离
  -> 对生成结果做质量评分、反换皮判定、硬约束检查
  -> 判断是通过、需要返修，还是应直接拒绝
```

另外两个目录属于历史原型或平行实验：

- `自动生成题目初始框架`：早期生成器，重点在“逻辑变异 + 故事包装”。
- `赛题评价模块`：较早的综合评估原型，强调代码执行、鲁棒性与新颖性检测。

## 如何理解这个仓库

如果只看设计思想，可以按下面顺序理解：

1. `论文`：先看问题定义、题目改编思路、Schema 树和论文总结。
2. `爬取题目`、`母题代码`：看题目从哪里来，怎样被清洗成结构化输入。
3. `finiteness_verification`：看 Schema 四维为什么能被抽取、归一化和统计，为什么这个表示是“可控”的。
4. `生成题面`：看当前版本如何把 Schema 变成新题。
5. `题目质量评价`：看生成后怎样筛掉伪新题和低质量题。

## 根目录文件夹详解

## 1. `论文`

这是仓库的研究资料层，保存课题描述、论文 PDF、论文阅读总结、题目改编思考和 `problem_schema_tree.drawio` 这类概念设计文件。

这里的完整流程不是代码流水线，而是研究流水线：

```text
阅读相关工作
  -> 总结已有自动出题、测试数据生成、题目评测方法
  -> 提炼本项目的 Problem Schema 思路
  -> 形成母题、规则、评估准则等概念
  -> 反过来指导工程目录的设计
```

方案思想是先把“什么叫可生成、可验证、可去重的题目”讲清楚，再写代码。这个目录决定了仓库不是一个单纯的 prompt 工程项目，而是一个试图把竞赛题表示成中间层结构的研究型工程。

## 2. `爬取题目`

这是多平台题目采集层，负责从 `Codeforces`、`AtCoder`、`Luogu`、`ICPC` 抓取题目，并统一保存到 `output/` 下。

目录内部主要分为几类内容：

- 平台抓取器：`atcoder/`、`codeforces/`、`icpc/`、`luogu/`
- 公共能力：`common/browser.py`、`common/models.py`、`common/storage.py`、`common/utils.py`
- 入口与配置：`main.py`、`config.py`
- 结果输出：`output/<platform>/...`

它的完整流程是：

```text
main.py 选择平台
  -> 各平台 scraper 抓取题面、链接、标签等信息
  -> common 层做统一建模与存储
  -> 输出到 output/<platform>/
  -> 生成后续模块可直接消费的题目语料
```

方案思想有两点：

1. 先统一“题目数据格式”，再做上层 Schema 抽取。这样后续模块关心的是结构化题目对象，而不是每个平台的页面差异。
2. 抓取层与生成层解耦。生成器并不直接联网找题，而是基于已经落盘的题库做抽取、验证和生成。

这个目录是整个项目的数据入口，也是 `finiteness_verification` Phase 2 做全量封闭分类时的重要输入来源。

* **codeforces**：2201 道
* **icpc**：3149 道
* **luogu**：7903 道

## 3. `母题代码`

这是“母题构建”的实验场，里面有多条早期或平行探索路线，包括爬 LeetCode、用 Qwen 或 Gemini 解析 Schema、把 Schema 向量化并做聚类分析。

目录内部主要包括：

- `crawler/`：LeetCode 题目抓取
- `parser/`：用 Qwen 解析题目到 Schema
- `Gemini/`：用 Gemini 解析题目到 Schema
- `embedding/`：把 Schema 转成向量，做相似度、聚类、标签提取和可视化
- `output/`：实验输出，如原始题目和可读化 Schema

这里的典型流程是：

```text
抓取原始题目
  -> 用 LLM 解析为 Schema
  -> 生成结构化或可读化结果
  -> 对 Schema 做 embedding
  -> 做聚类、相似度分析、推荐或去重实验
```

方案思想是先探索“母题是否真的可以被抽象、比较、聚类”。也就是在正式生成之前，先回答两个关键问题：

- Schema 能否成为稳定的中间表示；
- 不同题目之间能否在 Schema 空间里衡量相似性，而不只靠题面表述。

这个目录更像研究原型库，很多想法后来被吸收到 `finiteness_verification` 和 `生成题面` 中，但这里仍保留了早期实验脉络。

## 4. `finiteness_verification`

这是当前主线中最关键的中间层，目标不是直接生成题，而是验证 Schema 的四个核心维度 `I/C/O/V` 是否能形成有限、稳定、可归一化的标签集合。

目录内容可以分成五部分：

- 数据：`data/`
- Prompt 模板：`prompts/`
- 抽取与分析脚本：`extract.py`、`normalize.py`、`vote.py`、`analyze.py`、`classify.py`
- 辅助统计脚本：`count_*.py`、`manual_extract_transform.py` 等
- 输出：`output/pilot/`、`output/phase1/`、`output/phase2/`

它的完整流程分三层：

### Pilot

```text
sample_pilot.json
  -> extract.py 多轮抽取 I/C/O/V
  -> normalize.py 归一化标签
  -> vote.py 多轮投票
  -> 得到 pilot/voted/*.json
```

### Phase 1

```text
sample_phase1.json
  -> extract.py
  -> normalize.py
  -> vote.py
  -> analyze.py 画饱和曲线、统计标签增长
  -> 判断四维标签是否有限且趋于稳定
```

### Phase 2

```text
phase1 的标签集合
  -> classify.py 对全量题目做封闭分类
  -> report.py 统计 coverage 与 OTHER 收敛
  -> 判断分类体系是否能覆盖真实题库
```

方案思想非常明确：如果 Schema 维度本身不稳定、标签集合无限扩张，那后面的“受控生成”就是空中楼阁。先验证表示层是否封闭，再谈生成层是否可靠。

换句话说，这个目录回答的是“Schema 能不能当成系统的中间表示”，而不是“模型能不能写出一段像题面的文字”。

它也是 `生成题面` 的直接上游，因为后者当前消费的输入就是这里沉淀出的 voted schema。`finiteness_verification` 负责四元组抽取与归一化，生成器本身不再依赖第五维驱动创新。

## 5. `生成题面`

这是当前版本的正式生成器，围绕四元组 `I/C/O/V`、规则和两阶段 LLM 规划生成结构化题面。当前内部采用“规则声明 + 代码执行”架构。规则资格阶段会先由 LLM 按角色审查式提示词完成单规则准入判断，handler 负责解释结果、执行规划校验、题面校验并生成审计事件。

核心文件包括：

- `main.py`：命令行入口，显式要求 `mode`
- `schema_preparer.py`：做四元组归一化
- `planning_rules.json`：规则与红线
- `rulebook.py`：规则文件读取与模式、规则开关
- `rule_handlers.py`：规则资格审查接入、规划校验、题面校验与审计事件
- `variant_planner.py`：执行规则选择、候选回退与硬门槛校验
- `prompt_builder.py`：构造 planner 与 generator 的两阶段提示词
- `problem_generator.py`：根据实例化四元组生成结构化题目
- `pipeline.py`：把规划、生成、渲染、落盘串起来
- `markdown_renderer.py`：把结构化结果渲染成 OJ 风格 Markdown
- `prepared_schemas/`、`artifacts/`、`output/`、`reports/`：各阶段产物

这里的完整流程是：

```text
读取 voted schema
  -> schema_preparer 归一化为四元组
  -> rule_handlers 发起单规则资格审查
  -> variant_planner 排序并依次尝试前几条候选规则
  -> 通过代码级规则校验后实例化新四元组
  -> problem_generator 让模型输出严格 JSON，并继续执行规则专属题面校验
  -> markdown_renderer 渲染为题面 Markdown
  -> pipeline 保存 markdown、artifact、过程报告
```

当前只启用两个模式：

- `single_seed_extension`
- `same_family_fusion`

`cross_family_fusion` 仅保留文档与规则文件占位，本轮不宣称已支持。

这个目录的方案思想有三个关键点：

1. 创新来源是规则选择加 planner，并把变化直接落实到实例化四元组。
2. 差异控制只计算四轴距离 `I/C/O/V`，artifact 会显式记录 `distance_breakdown`、`changed_axes_realized` 与 `difference_plan`。
3. artifact 还会记录 `mode`、`source_problem_ids`、`applied_rule`、`rule_selection_reason`、`rejected_candidates`、`algorithmic_delta_claim`，以及 `rule_version`、`selection_trace`、`validation_trace`、`candidate_attempts`。

因此它不是一个“让模型编题”的脚本，而是一个“规则驱动的四元组生成管线”。

## 6. `题目质量评价`

这是当前主线的后验评估模块，直接消费 `生成题面/artifacts/*.json`，结合原题、原始 schema、归一化后的 schema 和生成题面做综合评估。

目录内部的关键组成包括：

- `main.py`：入口
- `problem_quality/evaluator.py`：主评估器
- `problem_quality/judges.py`：质量与反换皮判定器
- `problem_quality/models.py`：报告结构
- `problem_quality/report_renderer.py`：Markdown 报告渲染
- `tests/`：单元测试

它的完整流程是：

```text
读取 original schema / prepared schema / artifact / 可选 markdown
  -> 恢复 difference plan 与 instantiated schema
  -> 做 hard checks
  -> 评估题面完整性、可读性、样例质量、跨段一致性
  -> 比较规则决策轨迹、四轴 schema distance、语义差异、解法迁移风险
  -> 输出 JSON 和 Markdown 评估报告
```

当前口径里，`题目质量评价` 消费的是规则决策轨迹与四轴距离，而不是 `transform_space` 时代的第五维逻辑。这个模块的质量分并不是一个笼统的“好不好”，而是拆成五个维度分别打分，再按权重合成为总分：

- `variant_fidelity`，权重 `0.30`
- `spec_completeness`，权重 `0.25`
- `cross_section_consistency`，权重 `0.20`
- `sample_quality`，权重 `0.15`
- `oj_readability`，权重 `0.10`

### 质量维度说明

`variant_fidelity`

这个维度看“实例化后的 schema 是否真的落到了题面里”。它不是检查文风，而是检查题面是否把计划中的结构变化真实表达出来，比如输入项数量是否和实例化 schema 一致、目标函数是否真的改变、结构选项是否被明确写出。

高分意味着：

- 新题的输入格式、目标、规则定义与 `instantiated_schema` 高度一致；
- `Difference Plan` 里承诺过的变化，题面里都能找到对应表达。

低分通常意味着：

- 题面还在沿用原题的输入组织方式；
- 目标函数看起来变了，但输出要求和判定标准没跟着变；
- 结构变化只存在于 artifact 里，没有体现在题面文字中。

`spec_completeness`

这个维度看“题是不是写完整了”。重点不是创新，而是题面作为一道 OJ 题是否具备基本交付质量。实现里主要关注标题、描述、输入格式、输出格式、约束条件是否齐全。

高分意味着：

- 读者不需要猜测输入输出结构；
- 关键限制条件有显式写出；
- 题意、输入、输出三段能独立支撑做题。

低分通常意味着：

- 缺少输入格式或输出格式；
- 约束写得太少，无法判断复杂度边界；
- 描述有任务，但没有说明结果到底输出什么。

`cross_section_consistency`

这个维度看“题面的各个段落之间有没有互相打架”。它专门抓描述、输入输出、约束、样例之间的不一致，而不是抓措辞问题。

高分意味着：

- 描述中说有几类输入，`input_format` 和样例就真的是那个结构；
- 输出要求、约束、样例解释彼此一致；
- 样例行数、输入项数量、规则描述没有矛盾。

低分通常意味着：

- 题面说输入两行，样例却是三行；
- 描述说要求最小值，输出段落却像是在求计数；
- 结构选项变了，但样例仍保留旧结构。

`sample_quality`

这个维度看样例是否真正服务于题面理解，而不只是凑数。实现里主要看样例数量、是否有解释、样例输入是否和 schema 对齐。

高分意味着：

- 至少有足够的样例覆盖基本情况；
- 样例解释能帮助读者理解规则；
- 样例结构与输入格式完全对齐。

低分通常意味着：

- 样例太少，无法支撑理解；
- 样例没有解释，读者无法确认推导过程；
- 样例行数、字段数和输入格式不一致。

`oj_readability`

这个维度看题面是否像一道正常竞赛题，而不是一段模型生成文本。它关注整体可读性、段落长度是否合理、是否混入题源污染或明显的生成痕迹。

高分意味着：

- 描述长度适中，既不缺核心信息，也不冗长；
- 输入输出段落足够清楚，便于选手快速定位规则；
- 没有原题编号、题源标题、明显复用句式等污染信息。

低分通常意味着：

- 段落过短，像提纲而不是题面；
- 段落过长，掩盖了规则本体；
- 仍残留原题标题语义、来源信息或模板化语言。

### 反换皮维度说明

除了上面的质量分，这个模块还单独计算“它是不是只是在换皮”：

- `schema_distance`：看原始 schema 和实例化 schema 的结构差异有多大。
- `semantic_difference`：看新题的任务语义是否真的和原题拉开距离。
- `solution_transfer_risk`：看熟悉原题的选手，是否几乎能不改思路直接套原解。
- `surface_retheme_risk`：看变化是否主要停留在故事包装、名词替换和表层措辞。

这里的核心思想是：即使题面写得很完整，只要熟悉原题的人几乎可以直接平移原解，它仍然会被判成 `reject_as_retheme`。因此这个模块把“题写得好不好”和“题到底新不新”分开处理。

### 最终状态含义

评估结果最终会落到四种状态：

- `pass`：质量分和差异分都过线，且没有关键硬错误。
- `revise_quality`：题目基本不是换皮，但题面质量还不够，需要补齐说明、修正不一致或改进样例。
- `reject_as_retheme`：结构差异不足，或解法迁移风险太高，本质上仍是同题换皮。
- `reject_invalid`：评估输入不完整，或生成结果本身无效，无法进入正常审稿阶段。

当前实现里，`quality_score < 80` 往往会进入 `revise_quality`；`divergence_score < 70`、生成阶段出现 `difference_insufficient`，或者反换皮判定直接失败，则会进入 `reject_as_retheme`。

方案思想是“双重把关”：

- 一层是硬约束，检查生成状态、差异计划、原题是否成功解析等客观条件；
- 一层是软判断，评估这道题是不是足够完整、够像 OJ 题、又没有退化成换皮题。

这个目录体现了仓库的一个重要立场：生成不是终点，评估才是闭环。只有在反换皮判定和质量评分上都站得住，生成结果才算可用。

## 7. `自动生成题目初始框架`

这是本项目较早的一版自动出题原型。相较于当前的 `生成题面`，它更强调“逻辑变异器 + 故事引擎”的组合。

核心文件包括：

- `logic_mutator.py`：根据 `Transform Space` 改动数学骨架
- `story_engine.py`：把抽象结构包装成魔法、科幻、日常等主题
- `llm_client.py`：调用模型生成题面
- `main.py`：串联流程
- `output/`：示例生成结果

完整流程是：

```text
读取 schema
  -> logic_mutator 调整参数、目标、约束
  -> story_engine 给出题面包装主题
  -> llm_client 生成 Markdown 题面
  -> 输出到 output/
```

方案思想偏向验证“Schema 驱动生成是否可行”。它证明了只要有一个可变的五元组表示，模型确实可以围绕该表示写出一版题面。

但它的局限也很明显：

- 对差异度没有当前版本那么强的显式控制；
- 对“是否只是换皮”的判定较弱；
- 中间产物不如当前 `artifact + report` 体系完整。

因此它更适合被理解为主线生成器的前身。

## 8. `赛题评价模块`

这是一个更早的独立评估实验，主体文件是 `ape_system.py`。它实现了一个 Schema 增强版的 APE-System，尝试从数据合法性、鲁棒性、可解性、结构新颖性等角度自动打分。

它的大致流程是：

```text
读取 problem.json
  -> 归一化 schema
  -> 校验测试数据是否符合 schema
  -> 用代码执行和 hack 思路做鲁棒性测试
  -> 判断题面与 schema 的对齐度
  -> 计算结构新颖性
  -> 输出 problem_report.json
```

方案思想是把“评估”尽量做成接近评测系统的形式，而不是只靠文本审稿。它会涉及代码执行、验证器调用、embedding、新颖性分析等能力。

从仓库整体定位看，这个目录更像当前 `题目质量评价` 之前的一次系统化探索。它展示了项目一度尝试把“题目评价”做成强执行型流水线，而不仅是语言模型打分。

## 当前各目录在主线中的角色

如果只关心“现在应该看哪些目录”，可以这样理解：

- 研究设计层：`论文`
- 数据采集层：`爬取题目`
- 母题与表示实验层：`母题代码`
- 表示验证层：`finiteness_verification`
- 当前生成层：`生成题面`
- 当前评估层：`题目质量评价`
- 历史原型：`自动生成题目初始框架`、`赛题评价模块`

## 这套方案的核心思想

整个仓库的统一思想可以浓缩为四句话：

1. 不从零写题，而是从高质量题库里抽象母题。
2. 不直接让模型自由改写，而是在 Schema 四元组上做规则驱动的规划生成。
3. 不靠题面字面相似度去重，而是在 Schema 层面衡量差异。
4. 不把生成视为完成，而是要经过结构化质量评估和反换皮判定。

因此，这个仓库本质上是在构建一条“题目数据 -> Schema 中间表示 -> 有限性验证 -> 受控生成 -> 质量闭环”的完整路径。
