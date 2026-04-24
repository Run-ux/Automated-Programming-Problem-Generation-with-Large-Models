from __future__ import annotations

import json
from typing import Any


def build_spec_system_prompt() -> str:
    return "\n".join(
        [
            "你是一名算法竞赛题包规格抽取器。",
            "",
            "优先级：忠实抽取题面与 schema 信息 > 保守处理歧义 > 产出可执行规格。",
            "你只能依据题面、new_schema、算法变化声明和 revision_context 中已经暴露的问题工作。",
            "",
            _build_json_hard_constraints(include_code_rules=False),
            "",
            "规格抽取要求：",
            "1. 不要脑补未给出的输入范围、输出唯一性、特殊判题规则或额外保证。",
            "2. 无法确认的信息必须写入 ambiguity_notes，不要为了“完整”而自行补全。",
            "3. execution_spec 要服务后续标准解、oracle、validator、checker 和测试生成器，字段要具体到可执行层面。",
        ]
    )


def build_spec_user_prompt(context: dict[str, Any], revision_context: dict[str, Any] | None = None) -> str:
    payload = {"context": context, "revision_context": revision_context or {}}
    return _compose_prompt(
        intro="请输出 execution_spec。",
        output_contracts={
            "problem_id": "题目标识，优先使用输入上下文中的稳定 ID。",
            "input_contract": "只记录题面或 schema 明示的输入格式、字段含义、边界与显式约束。",
            "output_contract": "记录答案形式、合法性要求、是否允许多解或证书输出；无法确认时不要补设定。",
            "judge_type": "只能是 exact 或 checker。构造题、多解题、证书题、允许任意合法解的题必须使用 checker。",
            "oracle_limits": "给出小规模暴力 oracle 可承受的明确范围，不能写成空泛描述。",
            "test_buckets": "给出后续测试生成要覆盖的测试桶；每项至少体现 name、purpose 与规模意图。",
            "sample_tests": "题面样例的结构化结果；如果没有可靠样例，返回空列表。",
            "performance_limits": "只记录能从题面或 schema 明确推出的数据规模、复杂度或时限信号；未知时保守留空对象。",
            "ambiguity_notes": "集中记录缺失、冲突、无法确定的信息，以及因此采取的保守处理。",
        },
        extra_sections=[
            "抽取准则：",
            "1. 对象字段只保留有依据的键；列表字段缺失时返回 []，对象字段未知时返回最小必要对象或 {}，并在 ambiguity_notes 说明原因。",
            "2. sample_tests 中每项应尽量包含 input，以及能从题面直接读取到的 output、source、purpose。",
            "3. test_buckets 应覆盖基础、边界、随机、对抗、性能这五类与题目相关的测试用例类型，但不要凭空增加题意未支持的维度。",
            _build_revision_guidance(
                revision_context,
                relevant_keys=("failed_hard_checks", "tool_feedback", "solution_feedback", "oracle_feedback", "test_feedback"),
                fallback="若 revision_context 为空，优先保证 execution_spec 首轮可执行且字段定义清晰。",
            ),
        ],
        payload=payload,
    )


def build_code_system_prompt(role: str) -> str:
    return "\n".join(
        [
            f"你是一名算法竞赛题包生成器，当前角色是 {role}。",
            "",
            "最高优先级：接口合同与正确性；其次是保守处理未确认信息；最后才是表达完整。",
            "只根据 execution_spec、题面上下文与 revision_context 中已经暴露的问题生成结果。",
            "请先在内部完成约束抽取、算法选择、边界检查和最小自检，再输出最终 JSON。",
            "不要输出思维链、推导草稿、候选方案列表或任何中间分析过程。",
            "",
            _build_json_hard_constraints(include_code_rules=True),
            "",
            _build_competitive_reasoning_scaffold(),
            "",
            "当前角色目标：",
            _build_role_goal(role),
        ]
    )


def build_standard_solution_prompt(
    context: dict[str, Any],
    spec: dict[str, Any],
    revision_context: dict[str, Any] | None = None,
) -> str:
    payload = {"context": context, "execution_spec": spec, "revision_context": revision_context or {}}
    return _compose_prompt(
        intro="请生成标准解法。",
        output_contracts={
            "code": "完整可运行的 Python 代码字符串，必须实现 solve(input_str: str) -> str。",
            "algorithm": "核心算法概述，需与代码一致。",
            "correctness": "为什么该实现满足 execution_spec 的正确性说明，避免空话。",
            "time_complexity": "时间复杂度，需与 performance_limits 和代码一致。",
            "space_complexity": "空间复杂度，需与代码一致。",
            "notes": "仅记录真正的实现取舍、保守假设或剩余风险，不要重复题意。",
        },
        extra_sections=[
            "实现要求：",
            "1. 先严格服从 execution_spec，再根据 revision_context 修复已暴露问题。",
            "2. 不要输出伪代码、解释性代码块、Markdown 围栏或额外文本。",
            "3. 解析输入和格式化输出必须稳健，不能因为修复某条反馈而改坏已正确路径。",
            "4. 如果 execution_spec.ambiguity_notes 非空，不得私自扩展题意，只能按最保守、最可执行的方式实现。",
            "5. 在内部先列出真正决定算法的约束，判断是否存在多解、构造或证书语义，再确定唯一主算法。",
            "6. 实现前至少在脑中检查 5 类 测试用例：基础、边界、随机、对抗、性能。",
            "7. 输出前做最小自检，确认 code、algorithm、correctness、time_complexity、space_complexity、notes 彼此一致。",
            _build_revision_guidance(
                revision_context,
                relevant_keys=("failed_hard_checks", "solution_feedback"),
                fallback="若 revision_context 为空，优先保证首轮代码正确、稳健且满足复杂度约束。",
            ),
        ],
        payload=payload,
    )


def build_oracle_prompt(
    context: dict[str, Any],
    spec: dict[str, Any],
    revision_context: dict[str, Any] | None = None,
) -> str:
    payload = {"context": context, "execution_spec": spec, "revision_context": revision_context or {}}
    return _compose_prompt(
        intro="请生成小规模暴力 oracle。",
        output_contracts={
            "code": "完整可运行的 Python 代码字符串，必须实现 solve(input_str: str) -> str。",
            "oracle_scope": "清晰描述 oracle 保证正确的小规模范围，并与 execution_spec.oracle_limits 对齐。",
            "method": "暴力、枚举、搜索或直接校验思路；应易于审计。",
            "notes": "只记录 scope、正确性边界或实现取舍，不要重复题意。",
        },
        extra_sections=[
            "实现要求：",
            "1. oracle 可以慢，但必须在声明的 oracle_scope 内优先保证正确性。",
            "2. 尽量与标准解采用不同推理路径，降低同错同挂概率。",
            "3. 禁止使用拍脑袋启发式、未证明贪心或与标准解等价的复杂优化实现。",
            "4. code 不要输出 Markdown 围栏或解释性文本。",
            "5. 先在内部确定 tiny-scope 的真值生成思路，再写代码；不要接受“适用于小规模数据”这类空泛 scope。",
            "6. 优先使用全枚举、状态搜索、直接定义校验或朴素模拟；宁可慢，不可错；宁可笨，不可与标准解同构到一起错。",
            "7. 输出前自检，确认所有依赖的假设都严格落在 oracle_scope 内。",
            _build_revision_guidance(
                revision_context,
                relevant_keys=("failed_hard_checks", "oracle_feedback"),
                fallback="若 revision_context 为空，优先保证 scope 清晰、逻辑独立且可验证。",
            ),
        ],
        payload=payload,
    )


def build_tools_prompt(
    context: dict[str, Any],
    spec: dict[str, Any],
    revision_context: dict[str, Any] | None = None,
) -> str:
    payload = {"context": context, "execution_spec": spec, "revision_context": revision_context or {}}
    return _compose_prompt(
        intro="请生成 validator、checker、test_generator。",
        output_contracts={
            "validator_code": "完整可运行的 Python 代码字符串，必须实现 validate(input_str: str) -> bool。",
            "checker_code": "完整可运行的 Python 代码字符串，必须实现 check(input_str: str, output_str: str, expected_str: str | None) -> bool。",
            "test_generator_code": "完整可运行的 Python 代码字符串，必须实现 generate_tests() -> list[dict]。",
            "notes": "总结 validator/checker/test_generator 的设计口径与测试覆盖策略。",
        },
        extra_sections=[
            "工具职责要求：",
            "1. validator 只验证输入是否合法，不做求解，不依赖隐藏条件；遇到非法输入或异常时返回 False。",
            "2. checker 必须服从 execution_spec.judge_type。exact 时优先基于 expected_str 做规范化比较；checker 时校验输出格式和答案合法性，对尾部空白宽容，但对非法格式严格。",
            "3. test_generator 必须使用 execution_spec.test_buckets，并尽量产出 input、source、purpose、expect_oracle、is_sample、is_large、metadata。",
            "4. 测试覆盖应包含与题目相关的基础测试用例、边界测试用例、随机测试用例、对抗测试用例、性能测试用例；不相关的维度不要硬凑。",
            "5. 不要把题解逻辑塞进 validator 或 checker，也不要让 test_generator 依赖文件系统或外部状态。",
            "6. 先在内部枚举输入合法性规则，再写 validator；先判断 exact 或 checker 的判题语义，再写 checker。",
            "7. test_generator 先做覆盖计划，再生成测试列表；对基础测试用例、边界测试用例、随机测试用例、对抗测试用例、性能测试用例逐项判断是否相关。",
            "8. 若 oracle_limits 支持，应显式标注哪些测试 expect_oracle=True；若存在 surviving_wrong_solutions，应优先补定向反例。",
            _build_revision_guidance(
                revision_context,
                relevant_keys=("failed_hard_checks", "tool_feedback", "test_feedback", "surviving_wrong_solutions"),
                fallback="若 revision_context 为空，优先生成接口正确、职责分离且测试覆盖清晰的工具代码。",
            ),
        ],
        payload=payload,
    )


def build_weak_player_prompt(
    statement_only_context: dict[str, Any],
    revision_context: dict[str, Any] | None = None,
) -> str:
    payload = {"statement_context": statement_only_context, "revision_context": revision_context or {}}
    return _compose_prompt(
        intro="你现在扮演编码能力较弱、容易误解边界的参赛选手。",
        output_contracts={
            "wrong_solutions": "长度为 3 到 5 的列表；优先生成 5 份，以覆盖不同失败桶。",
            "wrong_solutions[].solution_id": "候选错误解的稳定标识。",
            "wrong_solutions[].code": "完整可运行的 Python 代码字符串，必须实现 solve(input_str: str) -> str。",
            "wrong_solutions[].player_profile": "选手画像，如样例拟合型、贪心过度自信型、复杂度误判型、边界粗心型、实现细节薄弱型。",
            "wrong_solutions[].target_failure_bucket": "目标失败桶，只能从小规模反例、大规模复杂度、边界条件、最坏情况、小规模挑战中选择最贴切的一类。",
            "wrong_solutions[].bug_type": "错误类型，如边界误判、错误贪心、复杂度误判、解析误读等。",
            "wrong_solutions[].expected_failure": "具体说明它会在哪类测试上失败。",
            "wrong_solutions[].source": "建议填写 weak_llm_player。",
        },
        extra_sections=[
            "行为要求：",
            "1. 只能根据题面和样例写代码，不能假设隐藏 schema、隐藏数据范围或内部规格。",
            "2. 生成的错误解要像真实选手代码：语法正确、接口正确、能通过部分直观测试，但在关键边界或思路上犯错。",
            "3. 默认优先生成 5 份错误解，分别面向这些失败桶：小规模样例/直观用例可过但隐藏小规模反例不过、大规模复杂度不过、边界条件不过、最坏情况不过、小规模但结构刁钻的用例不过。",
            "4. 每份错误解应选择不同参赛选手画像，例如样例拟合型、贪心过度自信型、复杂度误判型、边界粗心型、实现细节薄弱型；player_profile 必须与代码里的错误来源一致。",
            "5. 先模拟一种常见但错误的理解，再据此写代码；错误来源应来自边界、贪心、复杂度、重复值、排序稳定性、索引偏移或输入格式误读等真实误判。",
            "6. 多个候选应覆盖不同 bug 类型和 target_failure_bucket，避免同质化，也不要复用 rule-based 已覆盖的低价值错误模式。",
            "7. 不要生成空输出、固定输出、首 token 输出、明显瞎写这类低价值垃圾错误解；这些类型已有 rule-based 池补齐。",
            "8. 错误解必须有竞争力：能通过样例或部分自然测试，但会被对应失败桶中的针对性测试击中。",
            _build_revision_guidance(
                revision_context,
                relevant_keys=("test_feedback", "surviving_wrong_solutions"),
                fallback="若 revision_context 为空，优先生成独立、真实、容易被针对性测试击中的错误模式。",
            ),
        ],
        payload=payload,
    )


def _compose_prompt(
    *,
    intro: str,
    output_contracts: dict[str, str],
    extra_sections: list[str],
    payload: dict[str, Any],
) -> str:
    sections = [
        intro,
        _build_output_contract_section(output_contracts),
        *[section for section in extra_sections if section],
        "下面是输入上下文，请据此工作：",
        json.dumps(payload, ensure_ascii=False, indent=2),
    ]
    return "\n\n".join(section for section in sections if section)


def _build_json_hard_constraints(*, include_code_rules: bool) -> str:
    lines = [
        "通用硬约束：",
        "1. 只输出严格 JSON 对象，不要输出 Markdown、代码围栏或 JSON 之外的解释。",
        "2. 不要编造题面、schema、execution_spec 或 revision_context 中不存在的设定。",
    ]
    if include_code_rules:
        lines.extend(
            [
                "3. JSON 中的代码字段必须是 Python 3 标准库代码，禁止第三方依赖。",
                "4. 代码禁止读写文件、访问网络、启动子进程、读取环境变量。",
                "5. 不要在导入阶段执行求解逻辑；只能定义函数、常量和必要辅助逻辑。",
            ]
        )
    else:
        lines.append("3. 若信息不足，保守留空并在 ambiguity_notes 中说明。")
    return "\n".join(lines)


def _build_competitive_reasoning_scaffold() -> str:
    return "\n".join(
        [
            "内部解题流程：",
            "1. 先抽取输入、输出、判题方式与复杂度约束。",
            "2. 再识别决定算法的核心不变量、关键分类讨论与边界条件。",
            "3. 选择最简单且能满足约束的正确算法，不要保留未验证的备选方案。",
            "4. 实现前做一次边界覆盖检查。",
            "5. 输出前做最小自检，确认代码、复杂度说明与 notes 一致。",
        ]
    )


def _build_role_goal(role: str) -> str:
    role_goals = {
        "StandardSolutionGenerator": (
            "生成与 execution_spec 严格一致的标准解。先在内部完成“约束抽取 -> 算法选择 -> 正确性检查 -> 复杂度核对 -> 边界自检”，"
            "优先选择最稳健、最容易证明正确、最不容易被边界击穿且复杂度达标的方案，并在修复 revision_context 暴露问题时避免回归已正确路径。"
        ),
        "OracleGenerator": (
            "生成小规模、易审计、与标准解尽量独立的暴力 oracle。先在内部判定合适的暴力空间，再选择枚举、搜索、判定或朴素模拟路径；宁可慢，不可错。"
        ),
        "ToolGenerator": (
            "生成职责分离的 validator、checker、test_generator。先在内部拆分三者职责，再确定覆盖矩阵和判题语义；不要把题解逻辑塞进工具代码。"
        ),
        "WeakPlayerGenerator": (
            "生成像真实参赛选手会写出的错误解：先模拟错误理解路径，再写出接口正确、语法正确但逻辑有缺陷的代码，并让这些缺陷能被针对性测试击中。"
        ),
    }
    return role_goals.get(role, "生成满足接口合同、与上下文一致且可执行的结果。")


def _build_output_contract_section(output_contracts: dict[str, str]) -> str:
    lines = ["输出 JSON 对象，必须包含以下键："]
    for key, description in output_contracts.items():
        lines.append(f"- {key}: {description}")
    return "\n".join(lines)


def _build_revision_guidance(
    revision_context: dict[str, Any] | None,
    *,
    relevant_keys: tuple[str, ...],
    fallback: str,
) -> str:
    revision_context = revision_context or {}
    guidance: list[str] = []

    failed_hard_checks = _stringify_items(revision_context.get("failed_hard_checks"))
    if "failed_hard_checks" in relevant_keys and failed_hard_checks:
        guidance.append("优先修复 blocker 类问题：" + "、".join(failed_hard_checks))

    feedback_labels = {
        "solution_feedback": "标准解反馈",
        "oracle_feedback": "oracle 反馈",
        "tool_feedback": "工具反馈",
        "test_feedback": "测试反馈",
    }
    for key in ("solution_feedback", "oracle_feedback", "tool_feedback", "test_feedback"):
        if key not in relevant_keys:
            continue
        items = _stringify_items(revision_context.get(key))
        if items:
            guidance.append(f"{feedback_labels[key]}：" + "；".join(items))

    if "surviving_wrong_solutions" in relevant_keys:
        survivors = _stringify_items(revision_context.get("surviving_wrong_solutions"))
        if survivors:
            guidance.append("仍存活的错误解：" + "、".join(survivors) + "。请优先针对这些错误模式补足区分度。")

    if not guidance:
        return fallback

    guidance.append("只修已经暴露的问题，不要回归已经正确的接口、字段和已通过路径。")
    return "revision_context 行动指令：\n" + "\n".join(f"{index}. {item}" for index, item in enumerate(guidance, start=1))


def _stringify_items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []
