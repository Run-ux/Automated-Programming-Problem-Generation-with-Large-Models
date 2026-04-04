"""目标函数维度 Prompt。"""

from __future__ import annotations

from typing import TYPE_CHECKING

try:
    from ..label_vocab import OBJECTIVE_LABELS
    from ..problem_schema import prepare_problem_record
    from .prompt_sections import build_problem_context
except ImportError:
    from label_vocab import OBJECTIVE_LABELS
    from problem_schema import prepare_problem_record
    from prompts.prompt_sections import build_problem_context

if TYPE_CHECKING:
    from typing import Any, Dict


OBJECTIVE_TYPES = [name for name, _ in OBJECTIVE_LABELS]


def build_system_prompt() -> str:
    type_list = ", ".join(OBJECTIVE_TYPES)
    return f"""你是编程竞赛题目目标函数分析专家。

你的任务是识别题目的主要求解目标。

科研定义：
- 目标维度描述题目在输出层面要求返回的主结果类型，不描述采用何种算法实现该目标。
- 该维度区分优化、判定、构造、计数与博弈结果等主要求。
- 输出格式、解释性文字或中间过程不改变主目标类型。
- 题目同时要求最优值与对应方案时，主类型仍按目标本身标注，并通过 requires_solution 表示是否需要输出方案。

硬规则：
1. 只输出严格 JSON 对象，不输出任何解释文字。
2. type 必须复用规范目标词表：{type_list}。
3. 不得把题目情境词直接写进 type 或 target。

证据优先级：
1. 任务句与 Output 分节
2. 题面全文
3. Input 分节
4. Constraints 分节
5. 标题

判别规则：
- enumeration 用于统计方案数、计数结果或取模计数。
- maximize_count 用于最大化可选数量，例如最多能选多少个元素。
- construction 用于输出方案本身。
- feasibility 用于判定存在性或可行性。
- game_outcome 用于先手、后手、平局等博弈结果。
- 题目既要求最优值又要求输出达到该值的方案时，type 仍选目标类型，并把 requires_solution 设为 true。

判别边界：
- enumeration 用于统计合法方案数、可行解数量或取模计数。
- maximize_count 用于最大化可选对象数量，不用于统计全部方案数。
- construction 用于直接输出方案对象。
- feasibility 用于判定是否存在合法解。
- maximize_expected_value 与 minimize_expected_value 用于最大化或最小化期望型目标。
"""


def build_user_prompt(problem: Dict[str, Any]) -> str:
    problem = prepare_problem_record(problem)
    context = build_problem_context(problem)
    type_list = ", ".join(OBJECTIVE_TYPES)
    return f"""请根据下列题目信息识别主要目标。

{context}

字段说明：
1. type 表示主要求解目标的抽象类型。始终从统一词表中选择；所有已知类型都不适配时写 other；只有题目确实存在主目标时填写。常见误填：把输出对象、算法方法或题目情境词写进 type。
2. description 表示当前题目的目标语义摘要。识别出主目标后始终填写；没有单独留空场景。常见误填：照抄输出格式，或把算法过程写进 description。
3. target 表示主目标对象的简短英文名。目标对象能够稳定概括时填写，例如 sum、distance、operations；对象不清晰或没有必要单列时留空。常见误填：把 maximize、minimize、feasibility 这类目标类型写进 target。
4. requires_solution 表示除了目标值之外是否还必须输出达到该目标的方案。题目明确要求输出构造结果、路径、集合或方案时填写 true；只输出数值、计数或 Yes/No 时写 false 或省略。常见误填：因为题目有多组测试或有解释样例就写 true。

请输出 JSON：
{{
  "type": "必须从 {type_list} 中选择",
  "description": "目标的抽象描述",
  "target": "抽象目标对象英文名，可留空",
  "requires_solution": false
}}

要求：
1. 字段说明优先于字段名直觉，不要仅凭命名猜测字段含义。
2. 任务句与 Output 分节的证据权重高于标题。
3. 题目要求计数时用 enumeration，要求最大化数量时用 maximize_count。
4. 判定存在性用 feasibility，要求直接输出方案用 construction。
5. target 与 description 使用抽象算法术语，不写题目情境词。
6. 题目只求值不要求方案时，可省略 requires_solution 或写 false。
"""


OBJECTIVE_SCHEMA = {
    "type": "object",
    "required": ["type", "description"],
    "additionalProperties": True,
    "properties": {
        "type": {
            "type": "string",
            "enum": OBJECTIVE_TYPES,
            "description": "目标类型，必须来自统一目标词表",
        },
        "description": {
            "type": "string",
            "description": "目标函数的中文描述",
        },
        "target": {
            "type": "string",
            "description": "可选扩展字段。目标对象的简短英文名，如 sum 或 distance",
        },
        "requires_solution": {
            "type": "boolean",
            "description": "可选扩展字段。是否除了目标值还要求输出方案",
        },
    },
}
