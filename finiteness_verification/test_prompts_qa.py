"""
QA 验证脚本：测试四维独立抽取 Prompt

从 output/codeforces/index.json 选取 2 道题，分别运行 I/C/O/V 四维抽取，
验证 prompt 输出合法 JSON 且包含必需字段。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from finiteness_verification.qwen_client import QwenClient
from finiteness_verification.prompts.prompt_input_structure import (
    build_system_prompt as build_i_system,
    build_user_prompt as build_i_user,
)
from finiteness_verification.prompts.prompt_constraints import (
    build_system_prompt as build_c_system,
    build_user_prompt as build_c_user,
)
from finiteness_verification.prompts.prompt_objective import (
    build_system_prompt as build_o_system,
    build_user_prompt as build_o_user,
)
from finiteness_verification.prompts.prompt_invariant import (
    build_system_prompt as build_v_system,
    build_user_prompt as build_v_user,
)


def load_problems(count: int = 2):
    index_path = project_root / "爬取题目" / "output" / "codeforces" / "index.json"
    with open(index_path, encoding="utf-8") as f:
        problems = json.load(f)
    return problems[:count]


def test_dimension(client: QwenClient, dimension: str, build_sys, build_usr, problem: dict):
    print(f"\n{'='*60}")
    print(f"测试维度: {dimension}")
    print(f"题目: {problem['problem_id']} - {problem['title']}")
    print(f"{'='*60}")
    
    system_prompt = build_sys()
    user_prompt = build_usr(problem)
    
    print(f"\nSystem Prompt 长度: {len(system_prompt)} 字符")
    print(f"User Prompt 长度: {len(user_prompt)} 字符")
    
    try:
        result = client.chat_json(system_prompt, user_prompt)
        print(f"\n✓ 成功获取 JSON 输出")
        print(f"输出字段: {list(result.keys())}")
        print(f"\n完整输出:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result
    except Exception as e:
        print(f"\n✗ 调用失败: {e}")
        return None


def main():
    problems = load_problems(count=2)
    client = QwenClient()
    
    evidence = {}
    
    dimensions = [
        ("I - Input Structure", build_i_system, build_i_user),
        ("C - Core Constraints", build_c_system, build_c_user),
        ("O - Objective", build_o_system, build_o_user),
        ("V - Invariant", build_v_system, build_v_user),
    ]
    
    for problem in problems:
        pid = problem["problem_id"]
        evidence[pid] = {}
        
        print(f"\n\n{'#'*70}")
        print(f"# 题目: {pid} - {problem['title']}")
        print(f"{'#'*70}")
        
        for dim_name, build_sys, build_usr in dimensions:
            result = test_dimension(client, dim_name, build_sys, build_usr, problem)
            evidence[pid][dim_name] = result
    
    evidence_dir = project_root / "爬取题目" / ".sisyphus" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / "task-2-prompt-samples.json"
    
    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)
    
    print(f"\n\n{'='*70}")
    print(f"✓ 证据已保存: {evidence_path}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
