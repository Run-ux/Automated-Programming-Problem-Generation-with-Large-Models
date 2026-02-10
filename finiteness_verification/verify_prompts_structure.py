"""
结构验证脚本：验证四维 Prompt 构造正确性（不调用真实 API）

从 output/codeforces/index.json 选取 2 道题，
验证四维 prompt 能够正确构造 system/user prompt。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from finiteness_verification.prompts.prompt_input_structure import (
    build_system_prompt as build_i_system,
    build_user_prompt as build_i_user,
    INPUT_STRUCTURE_SCHEMA,
)
from finiteness_verification.prompts.prompt_constraints import (
    build_system_prompt as build_c_system,
    build_user_prompt as build_c_user,
    CONSTRAINTS_SCHEMA,
)
from finiteness_verification.prompts.prompt_objective import (
    build_system_prompt as build_o_system,
    build_user_prompt as build_o_user,
    OBJECTIVE_SCHEMA,
)
from finiteness_verification.prompts.prompt_invariant import (
    build_system_prompt as build_v_system,
    build_user_prompt as build_v_user,
    INVARIANT_SCHEMA,
)


def load_problems(count: int = 2):
    index_path = project_root / "爬取题目" / "output" / "codeforces" / "index.json"
    with open(index_path, encoding="utf-8") as f:
        problems = json.load(f)
    return problems[:count]


def verify_dimension(dimension: str, build_sys, build_usr, schema, problem: dict):
    print(f"\n{'='*60}")
    print(f"验证维度: {dimension}")
    print(f"题目: {problem['problem_id']} - {problem['title']}")
    print(f"{'='*60}")
    
    system_prompt = build_sys()
    user_prompt = build_usr(problem)
    
    assert isinstance(system_prompt, str), "system_prompt 必须是字符串"
    assert isinstance(user_prompt, str), "user_prompt 必须是字符串"
    assert len(system_prompt) > 0, "system_prompt 不能为空"
    assert len(user_prompt) > 0, "user_prompt 不能为空"
    
    print(f"[OK] System Prompt 长度: {len(system_prompt)} 字符")
    print(f"[OK] User Prompt 长度: {len(user_prompt)} 字符")
    
    assert "JSON" in system_prompt or "json" in system_prompt, "system_prompt 必须明确要求 JSON 输出"
    assert problem['title'] in user_prompt, "user_prompt 必须包含题目标题"
    assert problem['description'] in user_prompt, "user_prompt 必须包含题目描述"
    
    print(f"[OK] System Prompt 包含 JSON 输出要求")
    print(f"[OK] User Prompt 包含题目完整信息")
    
    print(f"\nJSON Schema 验证:")
    print(f"  - Required 字段: {schema.get('required', [])}")
    print(f"  - Properties 字段数: {len(schema.get('properties', {}))}")
    
    print(f"\n[OK] 维度 {dimension} 验证通过")
    return system_prompt, user_prompt


def main():
    problems = load_problems(count=2)
    
    dimensions = [
        ("I - Input Structure", build_i_system, build_i_user, INPUT_STRUCTURE_SCHEMA),
        ("C - Core Constraints", build_c_system, build_c_user, CONSTRAINTS_SCHEMA),
        ("O - Objective", build_o_system, build_o_user, OBJECTIVE_SCHEMA),
        ("V - Invariant", build_v_system, build_v_user, INVARIANT_SCHEMA),
    ]
    
    evidence = {
        "validation_status": "success",
        "problems_tested": [],
    }
    
    for problem in problems:
        pid = problem["problem_id"]
        print(f"\n\n{'#'*70}")
        print(f"# 题目: {pid} - {problem['title']}")
        print(f"{'#'*70}")
        
        problem_evidence = {
            "problem_id": pid,
            "title": problem["title"],
            "dimensions": {}
        }
        
        for dim_name, build_sys, build_usr, schema in dimensions:
            try:
                sys_prompt, usr_prompt = verify_dimension(
                    dim_name, build_sys, build_usr, schema, problem
                )
                problem_evidence["dimensions"][dim_name] = {
                    "status": "ok",
                    "system_prompt_length": len(sys_prompt),
                    "user_prompt_length": len(usr_prompt),
                }
            except Exception as e:
                print(f"[FAIL] 验证失败: {e}")
                problem_evidence["dimensions"][dim_name] = {
                    "status": "failed",
                    "error": str(e),
                }
                evidence["validation_status"] = "partial_failure"
        
        evidence["problems_tested"].append(problem_evidence)
    
    evidence_dir = project_root / "爬取题目" / ".sisyphus" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / "task-2-prompt-validation.json"
    
    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)
    
    print(f"\n\n{'='*70}")
    print(f"[OK] 验证完成，证据已保存: {evidence_path}")
    print(f"状态: {evidence['validation_status']}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
