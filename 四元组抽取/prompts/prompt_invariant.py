"""算法不变量维度 Prompt。"""

from __future__ import annotations

from typing import TYPE_CHECKING

try:
    from ..label_vocab import (
        INVARIANT_EVIDENCE_SOURCES,
        INVARIANT_LABELS,
    )
    from ..problem_schema import prepare_problem_record
    from .prompt_sections import build_problem_context
except ImportError:
    from label_vocab import (
        INVARIANT_EVIDENCE_SOURCES,
        INVARIANT_LABELS,
    )
    from problem_schema import prepare_problem_record
    from prompts.prompt_sections import build_problem_context

if TYPE_CHECKING:
    from typing import Any, Dict


SOLUTION_CODE_KEYS = [
    "standard_solution_code",
    "reference_solution",
]

INVARIANT_NAMES = [name for name, _ in INVARIANT_LABELS]


def build_system_prompt() -> str:
    invariant_names = ", ".join(INVARIANT_NAMES)
    return f"""你是编程竞赛算法不变量分析专家。

你的任务是抽取标准解法对应的关键算法不变量。

科研定义：
- 算法不变量指标准解法在计算过程中持续维护、反复利用或作为正确性依据的稳定性质。
- 该维度要求证据能够落实到状态定义、转移关系、边界推进、守恒关系、可合并关系或交换性质等可检验对象。
- 变量名、模板代码、容器选择、输入输出细节不属于不变量。
- 证据不足时返回空结果。

硬规则：
1. 只输出严格 JSON 对象，不输出任何解释文字。
2. name 必须优先复用规范不变量词表：{invariant_names}。
3. 若现有词表无法准确覆盖当前题目的关键稳定性质，允许创建新的抽象标签。
4. 新标签必须使用小写英文加下划线格式，并保持算法术语风格。
5. 不得把题目情境词直接写进 name、properties 的键名或 evidence_source。

证据优先级：
1. 标准解法代码
2. 题面全文
3. Input 分节
4. Constraints 分节
5. Output 分节
6. 标题

抽取边界：
- 有标准解法代码时，以代码为主证据，重点读取状态定义、循环推进方向、维护量、转移关系、合并规则。
- 没有代码时，只保留题面能够明确支撑的结构性质；证据不足时返回 {{"invariants": []}}。
- 变量名、宏定义、模板封装、输入输出写法不计入不变量。
- 无充分证据时宁可少报，不补报。
- properties 只写稳定、可机械理解的细粒度事实；拿不准就写空对象。
- evidence_source 只允许使用 statement、solution_code、both。

判别边界：
- monotonicity 用于指针、边界、答案下界或决策前沿沿单一方向推进的性质。
- state_transition 用于状态定义与转移关系构成的稳定维护规律。
- exchange_argument 只在替换某个局部选择后仍能保持可行性或最优性时使用。
- flow_conservation 用于流量守恒、质量守恒或等价的平衡关系。
- interval_additivity 与 interval_mergeable 只在区间量可以分解或合并时使用。
- 最优子结构、贪心选择或分治范式若无法落实为稳定维护关系，不单列为不变量标签，应写入 description。
"""


def _get_standard_solution_code(problem: Dict[str, Any]) -> str:
    for key in SOLUTION_CODE_KEYS:
        value = problem.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            code_value = value.get("code")
            if isinstance(code_value, str) and code_value.strip():
                return code_value.strip()
    return ""


def build_user_prompt(problem: Dict[str, Any]) -> str:
    problem = prepare_problem_record(problem)
    solution_code = _get_standard_solution_code(problem)
    context = build_problem_context(problem, solution_code=solution_code)
    invariant_names = ", ".join(INVARIANT_NAMES)
    return f"""请根据下列题目信息抽取关键算法不变量。

{context}

字段说明：
1. invariants[].name 表示不变量的抽象标签。现有词表能够覆盖时填写规范标签；只有明确存在语义缺口时才新建标签；证据不足时整条不变量不出现。常见误填：把贪心、二分、DP 这类算法范式直接写进 name。
2. invariants[].description 表示该不变量为何成立以及它稳定约束了什么。存在该不变量项时始终填写；只有整条不变量不存在时才不出现。常见误填：复述代码步骤，却没有说明稳定维护的性质。
3. invariants[].properties 表示可机械理解的细粒度事实。能够明确抽出稳定布尔性质或局部结构事实时填写；拿不准时写空对象。常见误填：把长句解释、变量名或题目情境词塞进 properties。
4. invariants[].evidence_source 表示证据来自题面、标准解法代码或两者。证据来源清晰时填写；返回空数组时不出现。常见误填：把置信度、推理过程或不在允许集合中的值写进去。

请输出 JSON：
{{
  "invariants": [
    {{
      "name": "优先复用规范标签，例如 {invariant_names}",
      "description": "该不变量为何成立，以及它约束了什么",
      "properties": {{}},
      "evidence_source": "solution_code"
    }}
  ]
}}

要求：
1. 字段说明优先于字段名直觉，不要仅凭命名猜测字段含义。
2. 有标准解法代码时，代码是主证据；没有代码时，只保留题面可直接支撑的结构性质。
3. name 优先对齐现有规范标签；若词表无法准确覆盖当前不变量，允许新建一个抽象标签。
4. 新标签保持小写英文加下划线格式，不写题目情境词。
5. 变量名、模板封装、宏定义、输入输出写法不计入不变量。
6. 重点读取状态定义、循环推进方向、维护量、转移关系、合并规则。
7. properties 拿不准就写空对象。
8. 证据不足时返回 {{"invariants": []}}。
"""


INVARIANT_SCHEMA = {
    "type": "object",
    "required": ["invariants"],
    "additionalProperties": True,
    "properties": {
        "invariants": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "description", "properties"],
                "additionalProperties": True,
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "不变量类型，如 monotonicity, state_transition, exchange_argument",
                    },
                    "description": {
                        "type": "string",
                        "description": "不变量的中文描述",
                    },
                    "properties": {
                        "type": "object",
                        "description": "稳定、可机械理解的细粒度事实",
                        "additionalProperties": True,
                    },
                    "evidence_source": {
                        "type": "string",
                        "enum": INVARIANT_EVIDENCE_SOURCES,
                        "description": "可选扩展字段。证据来源，取值为 statement、solution_code、both",
                    },
                },
            },
        }
    },
}
