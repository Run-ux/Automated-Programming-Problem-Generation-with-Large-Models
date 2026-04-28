from __future__ import annotations

import json
from typing import Any


def build_spec_system_prompt() -> str:
    return "\n\n".join(
        [
            "任务目标：\n你是一名算法竞赛题包规格抽取器。优先级：忠实抽取题面与 schema 信息 > 保守处理歧义 > 产出可执行规格。",
            "硬约束：\n" + _build_json_hard_constraints(include_code_rules=False),
            "\n".join(
                [
                    "执行准则：",
                    "1. 只依据题面、new_schema、算法变化声明和 revision_context 中已经暴露的问题抽取规格。",
                    "2. 未给出的输入范围、输出唯一性、特殊判题规则或额外保证统一记录到 ambiguity_notes。",
                    "3. execution_spec 要服务后续标准解、oracle、validator、checker 和测试生成器，字段要具体到可执行层面。",
                ]
            ),
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
            "3. judge_type 的边界必须明确：唯一标准输出且可规范化比较时使用 exact；构造题、多解题、证书题、任意合法解题使用 checker。",
            "4. oracle_limits 必须是小规模真值程序可执行的具体范围；无法从题面或 schema 推出时给出保守范围并写入 ambiguity_notes。",
            "5. test_buckets 应覆盖基础、边界、随机、对抗、性能这五类与题目相关的测试用例类型，题意不支持的维度写明不适用。",
            _build_revision_guidance(
                revision_context,
                role="SpecExtractor",
                fallback="若 revision_context 为空，优先保证 execution_spec 首轮可执行且字段定义清晰。",
            ),
        ],
        payload=payload,
    )


def build_code_system_prompt(role: str) -> str:
    include_code_rules = role != "SchemaMistakeAnalyzer"
    return "\n\n".join(
        [
            f"任务目标：\n你是一名算法竞赛题包生成器，当前角色是 {role}。\n{_build_role_goal(role)}",
            "硬约束：\n" + _build_json_hard_constraints(include_code_rules=include_code_rules),
            "\n".join(
                [
                    "执行准则：",
                    "1. 最高优先级是接口合同与正确性；其次是保守处理未确认信息；最后才是表达完整。",
                    "2. 只根据 execution_spec、题面上下文与 revision_context 中已经暴露的问题生成结果。",
                    "3. 在内部完成约束抽取、算法选择、边界检查和最小自检，最终只输出 JSON。",
                    "4. 中间推理、草稿和候选方案不写入最终输出。",
                    _build_role_process_scaffold(role),
                ]
            ),
        ]
    )


def build_revision_advisor_system_prompt() -> str:
    return "\n\n".join(
        [
            "任务目标：\n你是一名错误回流修订顾问。你只根据 failure_packet 中的失败证据，输出能直接指导下一轮生成器修复的具体 revision 建议。",
            "硬约束：\n" + _build_json_hard_constraints(include_code_rules=False),
            "\n".join(
                [
                    "执行准则：",
                    "1. 最高优先级是基于证据定位失败机制，禁止泛泛建议。",
                    "2. revision_advice 必须指出应修改的对象、触发失败的具体输入/输出/状态、建议修改方向和验证方式。",
                    "3. 如果证据不足以唯一定位根因，必须说明不可确认点，并给出保守但可执行的下一步修订建议。",
                    "4. 不要要求生成器改动 failure_packet 未命中的角色或已冻结合同，除非证据明确指向接口合同错误。",
                    "5. 禁止输出“检查边界”“修复逻辑”“确认实现”等空泛表述，必须落到具体数据形状、分支、接口或输出义务。",
                ]
            ),
        ]
    )


def build_revision_advisor_user_prompt(failure_packet: dict[str, Any]) -> str:
    return _compose_prompt(
        intro="请为该失败诊断输出定向 revision 建议。",
        output_contracts={
            "root_cause": "根据证据判断的失败机制；若不能唯一确定，说明最可能原因和不确定点。",
            "revision_advice": "可直接执行的修订建议，必须具体说明改什么、为什么、用哪个证据验证。",
            "target_roles": "建议作用的生成器角色列表，必须来自 failure_packet.diagnostic.target_roles。",
            "evidence_used": "实际使用的关键信息列表，例如测试来源、输入摘要、输出差异、异常类型或幸存错误解 ID。",
            "confidence": "只能是 low、medium 或 high。",
            "risk_notes": "可能误判、证据不足或改动风险；没有则返回空字符串。",
        },
        extra_sections=[
            "建议质量要求：",
            "1. 针对运行错误，指出异常类型、触发输入和应修正的解析/分支/数据结构路径。",
            "2. 针对输出不一致，指出首个不同 token/行、相关输入结构，并说明应优先核对标准解还是 oracle。",
            "3. 针对 checker/validator/test_generator，指出接口合同、输入合法性或输出合法性谓词的具体冲突。",
            "4. 针对错误解存活，指出幸存错误模式和应新增的反例形状，而不是只说提高覆盖率。",
            "5. 若存在 previous_advice，需要判断新证据是否仍支持该建议；不支持时说明应改用的新建议。",
        ],
        payload={"failure_packet": failure_packet},
    )


def build_standard_solution_prompt(
    context: dict[str, Any],
    spec: dict[str, Any],
    revision_context: dict[str, Any] | None = None,
) -> str:
    payload = {
        "context": _build_code_generation_context(context),
        "execution_spec": spec,
        "revision_context": revision_context or {},
    }
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
            "1. code 只定义 solve(input_str: str) -> str 及必要辅助逻辑，解析输入和格式化输出必须服从 execution_spec。",
            "2. 先严格服从 execution_spec，再根据 revision_context 修复已暴露问题。",
            "3. 如果 execution_spec.ambiguity_notes 非空，只能按最保守、最可执行的方式实现，并在 notes 记录对应假设。",
            "4. 在内部列出真正决定算法的约束，判断是否存在多解、构造或证书语义，再确定唯一主算法。",
            "5. 实现前至少检查 5 类测试用例：基础、边界、随机、对抗、性能。",
            "6. 输出前自检 code、algorithm、correctness、time_complexity、space_complexity、notes 是否彼此一致。",
            _build_revision_guidance(
                revision_context,
                role="StandardSolutionGenerator",
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
    payload = {
        "context": _build_code_generation_context(context),
        "execution_spec": spec,
        "revision_context": revision_context or {},
    }
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
            "1. code 只定义 solve(input_str: str) -> str 及必要辅助逻辑，oracle_scope 必须与 execution_spec.oracle_limits 对齐。",
            "2. oracle 可以慢，但必须在声明的 oracle_scope 内优先保证真值正确。",
            "3. 采用与标准解尽量独立的推理路径，优先使用全枚举、状态搜索、直接定义校验或朴素模拟。",
            "4. tiny-scope 必须具体到输入规模、结构限制或枚举空间，不能写成“适用于小规模数据”。",
            "5. method 和 notes 记录正确性边界，所有依赖假设都必须严格落在 oracle_scope 内。",
            "6. 输出前自检 code、oracle_scope、method、notes 是否彼此一致。",
            _build_revision_guidance(
                revision_context,
                role="OracleGenerator",
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
    payload = {
        "context": _build_code_generation_context(context),
        "execution_spec": spec,
        "revision_context": revision_context or {},
    }
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
            "1. 按 validator -> checker -> test_generator 的顺序设计三段代码，并在 notes 说明三者合同如何对齐。",
            "2. validator 只验证输入是否合法，不做求解，不依赖隐藏条件；非法输入或异常返回 False。",
            "3. checker 必须服从 execution_spec.judge_type。exact 基于 expected_str 做规范化比较；checker 校验输出格式和答案合法性，不能隐含标准解算法。",
            "4. test_generator 必须使用 execution_spec.test_buckets，产出 input、source、purpose、expect_oracle、is_sample、is_large、metadata。",
            "5. test_generator 生成的每个 input 都应能被 validator 接受；若生成非法输入用于负测，必须在 metadata 中显式标记。",
            "6. 测试覆盖按基础、边界、随机、对抗、性能逐项判断是否相关；若 oracle_limits 支持，应显式标注哪些测试 expect_oracle=True。",
            "7. 存在 surviving_wrong_solution_details 时，优先补能区分这些错误模式的定向反例。",
            _build_revision_guidance(
                revision_context,
                role="ToolGenerator",
                fallback="若 revision_context 为空，优先生成接口正确、职责分离且测试覆盖清晰的工具代码。",
            ),
        ],
        payload=payload,
    )


def build_validator_prompt(
    context: dict[str, Any],
    spec: dict[str, Any],
    revision_context: dict[str, Any] | None = None,
) -> str:
    payload = {
        "context": _build_code_generation_context(context),
        "execution_spec": spec,
        "revision_context": revision_context or {},
    }
    return _compose_prompt(
        intro="请生成 validator。此阶段只负责输入合法性校验，不生成 checker 或 test_generator。",
        output_contracts={
            "validator_code": "完整可运行的 Python 代码字符串，必须实现 validate(input_str: str) -> bool。",
            "notes": "说明输入合同、边界处理和保守假设，不要重复题意。",
        },
        extra_sections=[
            "validator 职责要求：",
            "1. 只验证输入是否合法，不做求解，不验证输出，不依赖隐藏条件。",
            "2. 严格服从 execution_spec.input_contract、performance_limits 与题面明示约束；信息不足时采用保守校验并在 notes 说明。",
            "3. 非法输入、解析失败、字段数量不匹配、范围越界或异常路径必须返回 False。",
            "4. 合法输入返回 True；函数内部自行捕获可恢复解析异常，禁止静默接受格式错误。",
            "5. 输出前自检 validate(input_str: str) -> bool 接口、异常路径和样例输入是否一致。",
            _build_revision_guidance(
                revision_context,
                role="ValidatorGenerator",
                fallback="若 revision_context 为空，优先生成接口正确、边界清晰且保守的 validator。",
            ),
        ],
        payload=payload,
    )


def build_checker_prompt(
    context: dict[str, Any],
    spec: dict[str, Any],
    validator_artifact: dict[str, Any],
    revision_context: dict[str, Any] | None = None,
) -> str:
    payload = {
        "context": _build_code_generation_context(context),
        "execution_spec": spec,
        "validator_artifact": _artifact_context(validator_artifact),
        "revision_context": revision_context or {},
    }
    return _compose_prompt(
        intro="请生成 checker。此阶段必须基于已生成 validator 的输入合同口径，只生成 checker。",
        output_contracts={
            "checker_code": "完整可运行的 Python 代码字符串，必须实现 check(input_str: str, output_str: str, expected_str: str | None) -> bool。",
            "notes": "说明判题语义、输出合法性谓词和与 validator 的合同衔接。",
        },
        extra_sections=[
            "checker 职责要求：",
            "1. 必须服从 execution_spec.judge_type：exact 题基于 expected_str 做规范化比较；checker 题校验输出格式和答案合法性。",
            "2. 不要把完整标准解算法塞进 checker；只实现判题必须的解析、格式和证书合法性校验。",
            "3. input_str 的解析口径必须与 validator_artifact 保持一致；若输入不合法或输出非法，返回 False。",
            "4. expected_str 为 None 时，只能在 checker 题或确有合法性谓词时忽略标准输出；exact 题缺少 expected_str 应返回 False。",
            "5. 输出前自检 check(input_str, output_str, expected_str) 接口、空输出、多余 token、格式错误和多解语义。",
            _build_revision_guidance(
                revision_context,
                role="CheckerGenerator",
                fallback="若 revision_context 为空，优先生成判题语义明确、与 validator 输入合同一致的 checker。",
            ),
        ],
        payload=payload,
    )


def build_test_generator_prompt(
    context: dict[str, Any],
    spec: dict[str, Any],
    validator_artifact: dict[str, Any],
    checker_artifact: dict[str, Any],
    revision_context: dict[str, Any] | None = None,
) -> str:
    payload = {
        "context": _build_code_generation_context(context),
        "execution_spec": spec,
        "validator_artifact": _artifact_context(validator_artifact),
        "checker_artifact": _artifact_context(checker_artifact),
        "revision_context": revision_context or {},
    }
    return _compose_prompt(
        intro="请生成 test_generator。此阶段必须基于已生成 validator 与 checker 的合同，只生成测试生成器。",
        output_contracts={
            "test_generator_code": "完整可运行的 Python 代码字符串，必须实现 generate_tests() -> list[dict]。",
            "notes": "说明测试桶覆盖、oracle 标注和与 validator/checker 的合同衔接。",
        },
        extra_sections=[
            "test_generator 职责要求：",
            "1. 必须使用 execution_spec.test_buckets，产出 input、source、purpose、expect_oracle、is_sample、is_large、metadata。",
            "2. 默认生成的每个 input 都应能被 validator_artifact 接受；若生成非法输入用于负测，必须在 metadata 中显式标记。",
            "3. 测试覆盖按基础、边界、随机、对抗、性能逐项判断是否相关；不要为了数量生成重复或低价值用例。",
            "4. 若 oracle_limits 支持，应显式标注哪些测试 expect_oracle=True；大规模或超出 oracle_scope 的测试标注 expect_oracle=False。",
            "5. 存在 surviving_wrong_solution_details 时，优先补能区分这些错误模式的定向反例。",
            "6. 输出前自检 generate_tests() 返回 list[dict]，且字段、输入格式、规模标记与 validator/checker 合同一致。",
            _build_revision_guidance(
                revision_context,
                role="TestGenerator",
                fallback="若 revision_context 为空，优先生成覆盖清晰、可被 validator 接受且 oracle 标注准确的测试生成器。",
            ),
        ],
        payload=payload,
    )


def build_schema_mistake_analysis_prompt(
    context: dict[str, Any],
    spec: dict[str, Any],
    revision_context: dict[str, Any] | None = None,
) -> str:
    payload = {"context": context, "execution_spec": spec, "revision_context": revision_context or {}}
    return _compose_prompt(
        intro="请基于 new_schema 总结真实参赛选手可能犯错的误解点；本阶段只分析误解点，不写代码。",
        output_contracts={
            "mistake_points": "长度为 4 到 6 的列表；每项描述一个可转化为错误解的真实选手误解点。",
            "mistake_points[].mistake_id": "稳定标识，使用小写字母、数字和下划线。",
            "mistake_points[].schema_basis": "该误解点来自 new_schema、execution_spec、difference_plan 或 algorithmic_delta_claim 的哪些具体信号。",
            "mistake_points[].player_visible_misread": "把内部 schema 创新点翻译成选手从题面可见信息出发可能产生的误读。",
            "mistake_points[].wrong_strategy": "选手据此会采用的错误解法策略。",
            "mistake_points[].target_failure_bucket": "目标失败桶，只能从小规模反例、大规模复杂度、边界条件、最坏情况、小规模挑战中选择。",
            "mistake_points[].expected_counterexample_shape": "能击中该错误策略的反例形态，必须具体到输入结构或输出义务。",
            "mistake_points[].triviality_risk": "说明如何避免该误解点退化为空输出、固定输出、首 token 等低价值错误。",
        },
        extra_sections=[
            "分析要求：",
            "1. 优先覆盖 new_schema.objective、new_schema.core_constraints、new_schema.invariant 中的新义务。",
            "2. 重点识别构造输出、证书输出、字典序规范性、耦合约束、区间/树/模结构不变量等容易被真实选手误解的点。",
            "3. schema_basis 可以引用 schema 字段或约束名称，player_visible_misread 必须保持选手视角。",
            "4. 每个误解点都要绑定具体失败桶、部分可通过的自然测试和可击中的反例形态。",
            "5. 每个误解点都必须能进一步写成语法正确、接口正确、可通过部分自然测试的错误解。",
            _build_revision_guidance(
                revision_context,
                role="SchemaMistakeAnalyzer",
                fallback="若 revision_context 为空，优先覆盖 schema 中最能体现创新点的约束、目标和不变量。",
            ),
        ],
        payload=payload,
    )


def build_schema_aware_wrong_solution_prompt(
    context: dict[str, Any],
    spec: dict[str, Any],
    mistake_points: list[dict[str, Any]],
    revision_context: dict[str, Any] | None = None,
) -> str:
    payload = {
        "context": context,
        "execution_spec": spec,
        "mistake_points": mistake_points,
        "revision_context": revision_context or {},
    }
    return _compose_prompt(
        intro="请根据给定误解点，模拟真实参赛选手写出 schema-aware 错误解代码。",
        output_contracts={
            "wrong_solutions": "长度为 3 到 5 的列表；每份错误解必须绑定一个 mistake_id。",
            "wrong_solutions[].solution_id": "候选错误解的稳定标识。",
            "wrong_solutions[].mistake_id": "必须引用输入 mistake_points 中存在的 mistake_id。",
            "wrong_solutions[].code": "完整可运行的 Python 代码字符串，必须实现 solve(input_str: str) -> str。",
            "wrong_solutions[].player_profile": "选手画像，如构造义务漏读型、证书输出误读型、规范顺序忽略型、耦合约束简化型。",
            "wrong_solutions[].target_failure_bucket": "目标失败桶，应与绑定误解点保持一致。",
            "wrong_solutions[].bug_type": "错误类型，如构造遗漏、证书误读、规范性遗漏、约束耦合误判、边界误判等。",
            "wrong_solutions[].expected_failure": "具体说明它会在哪类测试或输出义务上失败。",
            "wrong_solutions[].schema_signals": "该错误解利用到的 schema 信号名称列表，用于审计和论文分析。",
        },
        extra_sections=[
            "错误解生成要求：",
            "1. 代码必须像真实选手提交：语法正确、接口正确、能通过部分直观测试，但会被绑定误解点对应的反例击中。",
            "2. 只能从 mistake_points 中选择 mistake_id 并按其误解点写代码，不新增隐藏误解点、隐藏题意或隐藏数据范围。",
            "3. 可以内部利用 new_schema 定位创新点，但代码和 expected_failure 应表现为选手对题面义务的自然误读。",
            "4. 每份错误解必须绑定具体 target_failure_bucket，说明可通过的自然测试和会失败的定向反例。",
            "5. 多个错误解应覆盖不同 mistake_id，避免同质化；优先覆盖 objective、core_constraints、invariant 中的新义务。",
            _build_revision_guidance(
                revision_context,
                role="SchemaAwareWrongSolutionGenerator",
                fallback="若 revision_context 为空，优先生成能压测 schema 创新点且具有真实选手风格的错误解。",
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
            "6. 多个候选应覆盖不同 bug 类型和 target_failure_bucket，避免同质化。",
            "7. 每份错误解必须有竞争力：能通过样例或部分自然测试，但会被对应失败桶中的针对性测试击中。",
            "8. expected_failure 要具体描述失败输入结构或输出义务。",
            _build_revision_guidance(
                revision_context,
                role="WeakPlayerGenerator",
                fallback="若 revision_context 为空，优先生成独立、真实、容易被针对性测试击中的错误模式。",
            ),
        ],
        payload=payload,
    )


def _build_code_generation_context(context: dict[str, Any]) -> dict[str, Any]:
    compact_context = {
        "problem_id": context.get("problem_id", ""),
        "statement_markdown": str(context.get("statement_markdown", "")).strip(),
    }
    new_schema = context.get("new_schema")
    if isinstance(new_schema, dict) and new_schema:
        compact_context["new_schema"] = new_schema
    algorithmic_delta_claim = context.get("algorithmic_delta_claim")
    if algorithmic_delta_claim:
        compact_context["algorithmic_delta_claim"] = algorithmic_delta_claim
    difference_plan = context.get("difference_plan")
    if isinstance(difference_plan, dict) and difference_plan:
        compact_context["difference_plan"] = difference_plan
    applied_rule = str(context.get("applied_rule", "")).strip()
    if applied_rule:
        compact_context["applied_rule"] = applied_rule
    return compact_context


def _compose_prompt(
    *,
    intro: str,
    output_contracts: dict[str, str],
    extra_sections: list[str],
    payload: dict[str, Any],
) -> str:
    guideline_sections: list[str] = []
    revision_section = ""
    for section in extra_sections:
        if not section:
            continue
        if section.startswith("修订上下文要求："):
            revision_section = section.removeprefix("修订上下文要求：").strip()
        else:
            guideline_sections.append(section)
    if not revision_section:
        revision_section = "当前没有结构化 revision_context；按首轮生成目标工作。"

    sections = [
        "任务目标：\n" + intro,
        "输出合同：\n" + _build_output_contract_section(output_contracts),
        "硬约束：\n" + _build_json_hard_constraints(include_code_rules=False),
        "执行准则：\n" + "\n".join(guideline_sections),
        "修订上下文要求：\n" + revision_section,
        "输入上下文：",
        json.dumps(payload, ensure_ascii=False, indent=2),
    ]
    return "\n\n".join(section for section in sections if section)


def _build_json_hard_constraints(*, include_code_rules: bool) -> str:
    lines = [
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


def _build_schema_mistake_scaffold() -> str:
    return "\n".join(
        [
            "内部分析流程：",
            "1. 先抽取 new_schema 中相对普通题面最容易被误读的新义务。",
            "2. 再把内部 schema 信号翻译成选手从题面出发可能产生的自然误解。",
            "3. 判断该误解是否能写成可运行、能过部分测试、可被定向反例击中的错误解。",
            "4. 剔除空输出、固定输出、首 token、故意破坏格式等低价值错误模式。",
            "5. 输出前确认每个误解点都有明确 schema_basis 和 expected_counterexample_shape。",
        ]
    )


def _build_role_process_scaffold(role: str) -> str:
    if role == "SchemaMistakeAnalyzer":
        return _build_schema_mistake_scaffold()
    return _build_competitive_reasoning_scaffold()


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
        "ValidatorGenerator": (
            "只生成 validator。严格校验输入格式、字段数量、边界和显式约束；不做求解、不校验输出，非法输入或异常必须返回 False。"
        ),
        "CheckerGenerator": (
            "只生成 checker。严格服从 execution_spec.judge_type，校验输出格式和答案合法性；不得隐含完整标准解算法，并与 validator 的输入解析口径保持一致。"
        ),
        "TestGenerator": (
            "只生成 test_generator。围绕 execution_spec.test_buckets 构造高价值测试，默认所有生成输入都应被 validator 接受，并正确标注 oracle 与大规模测试。"
        ),
        "WeakPlayerGenerator": (
            "生成像真实参赛选手会写出的错误解：先模拟错误理解路径，再写出接口正确、语法正确但逻辑有缺陷的代码，并让这些缺陷能被针对性测试击中。"
        ),
        "SchemaMistakeAnalyzer": (
            "基于 new_schema、difference_plan、algorithmic_delta_claim 与 execution_spec，提炼真实选手可能误读的创新点；只输出误解点，不写代码。"
        ),
        "SchemaAwareWrongSolutionGenerator": (
            "根据已确认的 schema-aware 误解点，模拟真实参赛选手写出可运行但有针对性缺陷的错误解，避免低价值垃圾错误。"
        ),
    }
    return role_goals.get(role, "生成满足接口合同、与上下文一致且可执行的结果。")


def _artifact_context(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        "name": value.get("name", ""),
        "role": value.get("role", ""),
        "code": value.get("code", ""),
        "metadata": value.get("metadata", {}),
    }


def _build_output_contract_section(output_contracts: dict[str, str]) -> str:
    lines = ["JSON 对象必须包含以下键："]
    for key, description in output_contracts.items():
        lines.append(f"- {key}: {description}")
    return "\n".join(lines)


def _build_revision_guidance(
    revision_context: dict[str, Any] | None,
    *,
    role: str,
    fallback: str,
) -> str:
    revision_context = revision_context or {}
    active_revision_context = revision_context.get("active_revision_context")
    if isinstance(active_revision_context, dict) and not any(
        key in revision_context for key in ("summary", "role_diagnostics", "surviving_wrong_solution_details")
    ):
        merged_context = dict(active_revision_context)
        for key in ("revision_mode", "baseline_repair_mode", "current_artifact", "frozen_contract_summary"):
            if key in revision_context:
                merged_context[key] = revision_context[key]
        revision_context = merged_context
    if not _has_structured_revision_context(revision_context):
        return "修订上下文要求：\n" + f"- 当前没有结构化 revision_context；{fallback}"

    guidance: list[str] = []
    if revision_context.get("revision_mode") == "incremental_patch":
        guidance.append(
            "当前是增量修订轮：你不是重做题包，只能修 active_revision_context 中仍未解决的问题，且只能处理命中当前角色的问题；已解决历史问题不得再次作为修改依据；输出仍需是完整替换产物。"
        )
    if revision_context.get("baseline_repair_mode") is True:
        guidance.append(
            "当前基线未通过；只修复基础自洽相关的 blocker/high 问题，错误解池、schema 误解点和非命中工具组件视为冻结，不要为了提高 kill_rate 或扩展错误解覆盖去改动未命中的组件。"
        )

    failed_hard_checks = _dedupe_strings(_stringify_items(revision_context.get("failed_hard_checks")))
    if failed_hard_checks:
        guidance.append("优先修复 blocker 类问题：" + "、".join(failed_hard_checks))

    summary = _format_summary(revision_context.get("summary"))
    if summary:
        guidance.append("失败概览：" + summary)

    role_items = _diagnostics_for_role(revision_context, role)
    if role_items:
        guidance.append(f"{role} 定向诊断：" + "；".join(_format_diagnostic(item) for item in role_items))

    survivor_text = _format_surviving_wrong_solution_details(revision_context.get("surviving_wrong_solution_details"))
    if survivor_text and role in {"ToolGenerator", "TestGenerator", "WeakPlayerGenerator", "SchemaMistakeAnalyzer", "SchemaAwareWrongSolutionGenerator"}:
        guidance.append("仍存活的错误解详情：" + survivor_text + "。请优先针对这些错误模式补足区分度。")

    current_artifact_text = _format_current_artifact(revision_context.get("current_artifact"))
    if current_artifact_text:
        guidance.append("当前工作副本摘要：" + current_artifact_text + "。应在此基础上做最小必要修改，并输出完整替换结果。")

    frozen_contract_text = _format_frozen_contract(revision_context.get("frozen_contract_summary"))
    if frozen_contract_text:
        guidance.append("已通过路径的冻结合同：" + frozen_contract_text + "。除非 active 诊断明确要求，不要改变这些接口语义。")

    known_good_text = _format_known_good_case_summaries(revision_context.get("known_good_case_summaries"))
    if known_good_text:
        guidance.append("known-good 回归合同：" + known_good_text + "。候选必须保持这些已通过路径全部通过。")

    if not guidance:
        return "修订上下文要求：\n" + f"- 当前没有可执行修订项；{fallback}"

    guidance.append("语义上只修 active 诊断命中的问题，未命中行为视为冻结合同；无法在不改接口/合同的情况下修复时，在 notes 中返回结构性诊断，不要硬改既有接口。")
    return "修订上下文要求：\n" + "\n".join(f"- {item}" for item in guidance)


def _has_structured_revision_context(revision_context: dict[str, Any]) -> bool:
    return any(
        key in revision_context
        for key in ("summary", "role_diagnostics", "surviving_wrong_solution_details", "active_revision_context")
    )


def _diagnostics_for_role(revision_context: dict[str, Any], role: str) -> list[dict[str, Any]]:
    role_diagnostics = revision_context.get("role_diagnostics")
    if not isinstance(role_diagnostics, dict):
        return []
    items = role_diagnostics.get(role, [])
    if not items and role in {"ValidatorGenerator", "CheckerGenerator", "TestGenerator"}:
        items = role_diagnostics.get("ToolGenerator", [])
    return [item for item in items if isinstance(item, dict)]


def _format_summary(summary: Any) -> str:
    if not isinstance(summary, list):
        return ""
    parts: list[str] = []
    for item in summary[:6]:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category", "")).strip()
        count = item.get("count", 0)
        severity = str(item.get("severity", "")).strip()
        sources = _stringify_items(item.get("representative_sources"))
        source_text = f"，代表测试：{', '.join(sources)}" if sources else ""
        if category:
            parts.append(f"{category} x{count} [{severity}]{source_text}")
    return "；".join(parts)


def _format_diagnostic(diagnostic: dict[str, Any]) -> str:
    category = str(diagnostic.get("category", "")).strip()
    severity = str(diagnostic.get("severity", "")).strip()
    title = str(diagnostic.get("title", "")).strip()
    detail = str(diagnostic.get("detail", "")).strip()
    fix_hint = str(diagnostic.get("fix_hint", "")).strip()
    advisor_text = _format_advisor_revision(diagnostic.get("advisor_revision"))
    evidence = diagnostic.get("evidence") if isinstance(diagnostic.get("evidence"), dict) else {}
    test = evidence.get("test") if isinstance(evidence.get("test"), dict) else {}
    source = str(test.get("source") or evidence.get("test_source") or "").strip()
    diff_text = _format_diff(diagnostic.get("diff"))
    parts = [part for part in [f"[{severity}] {category}", title, detail] if part]
    if source:
        parts.append(f"测试来源：{source}")
    if diff_text:
        parts.append(diff_text)
    if advisor_text:
        parts.append("advisor修订建议：" + advisor_text)
    elif fix_hint and "advisor_revision" not in diagnostic:
        parts.append("修复建议：" + fix_hint)
    return "，".join(parts)


def _format_advisor_revision(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    advice = str(value.get("revision_advice", "")).strip()
    if not advice:
        return ""
    root_cause = str(value.get("root_cause", "")).strip()
    confidence = str(value.get("confidence", "")).strip()
    parts = []
    if root_cause:
        parts.append("根因：" + root_cause)
    parts.append("建议：" + advice)
    if confidence:
        parts.append("置信度：" + confidence)
    return "；".join(parts)


def _format_diff(diff: Any) -> str:
    if not isinstance(diff, dict):
        return ""
    token = diff.get("first_different_token") if isinstance(diff.get("first_different_token"), dict) else {}
    line = diff.get("first_different_line") if isinstance(diff.get("first_different_line"), dict) else {}
    chunks: list[str] = []
    if token:
        chunks.append(f"首个不同 token#{token.get('index')}: standard={token.get('standard')!r}, oracle={token.get('oracle')!r}")
    if line:
        chunks.append(f"首个不同行#{line.get('index')}: standard={line.get('standard')!r}, oracle={line.get('oracle')!r}")
    return "；".join(chunks)


def _format_surviving_wrong_solution_details(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    parts: list[str] = []
    for item in value[:5]:
        if not isinstance(item, dict):
            continue
        solution_id = str(item.get("solution_id", "")).strip()
        bug_type = str(item.get("bug_type", "")).strip()
        reason = str(item.get("reason", "")).strip()
        passed = _stringify_items(item.get("passed_tests"))
        killed = _stringify_items(item.get("killed_tests"))
        if solution_id:
            parts.append(
                f"{solution_id}"
                f"（bug_type={bug_type or '未知'}，原因={reason or '当前测试未杀死'}，"
                f"通过={','.join(passed) or '无'}，击杀={','.join(killed) or '无'}）"
            )
    return "；".join(parts)


def _format_current_artifact(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return ""
    parts: list[str] = []
    for key in [
        "execution_spec",
        "standard_solution",
        "oracle_solution",
        "validator",
        "checker",
        "test_generator",
        "schema_mistake_points",
        "wrong_solutions",
    ]:
        if key not in value:
            continue
        item = value.get(key)
        if isinstance(item, dict):
            code_length = item.get("code_length")
            code = str(item.get("code", ""))
            if code_length is None:
                code_length = len(code)
            code_text = f"，代码长度={code_length}" if code_length else ""
            if item.get("code_truncated"):
                code_text += "，已截断"
            parts.append(f"{key}({item.get('name') or item.get('problem_id') or '已存在'}{code_text})")
        elif isinstance(item, list):
            parts.append(f"{key}(数量={len(item)})")
        else:
            parts.append(f"{key}(已存在)")
    return "；".join(parts[:8])


def _format_frozen_contract(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return ""
    parts: list[str] = []
    for key in ["problem_id", "judge_type", "input_contract", "output_contract", "oracle_limits", "performance_limits"]:
        if key in value:
            text = json.dumps(value.get(key), ensure_ascii=False, sort_keys=True)
            parts.append(f"{key}={text[:180]}")
    return "；".join(parts)


def _format_known_good_case_summaries(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    parts: list[str] = []
    for item in value[:5]:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source", "")).strip()
        purpose = str(item.get("purpose", "")).strip()
        flags = []
        if item.get("is_sample"):
            flags.append("sample")
        if item.get("is_large"):
            flags.append("large")
        if item.get("expect_oracle"):
            flags.append("oracle")
        label = source or purpose
        if label:
            flag_text = f" [{' / '.join(flags)}]" if flags else ""
            parts.append(f"{label}{flag_text}")
    return "；".join(parts)


def _stringify_items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
