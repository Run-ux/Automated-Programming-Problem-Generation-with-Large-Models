"""
多数投票机制：从 3 轮抽取中选出最一致的结果

用法：
    python -m finiteness_verification.vote \
        --input output/pilot/normalized/ \
        --output output/pilot/voted/

输入：
    normalized/{problem_id}.json（归一化后的多轮结果）

输出：
    voted/{problem_id}.json（投票后的最终结果 + 置信度）
    
    格式：
    {
        "problem_id": "...",
        "source": "...",
        "input_structure": {
            "type": "array",
            "confidence": "3/3" or "2/3" or "1/3",
            "all_rounds": [...]
        },
        "core_constraints": {
            "constraints": [...],
            "all_rounds": [...]
        },
        "objective": {
            "type": "...",
            "confidence": "3/3" or "2/3" or "1/3",
            "all_rounds": [...]
        },
        "invariant": {
            "name": "...",
            "confidence": "3/3" or "2/3" or "1/3",
            "all_rounds": [...]
        }
    }
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


def vote_input_structure(rounds: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    对 Input Structure 维度进行投票
    
    投票字段：type
    
    Args:
        rounds: 3 轮抽取结果（已归一化）
    
    Returns:
        投票结果（包含 type, confidence, all_rounds）
    """
    types = [r["result"].get("type") for r in rounds if r.get("status") == "success"]
    
    if not types:
        return {"type": None, "confidence": "0/3", "all_rounds": rounds}
    
    counter = Counter(types)
    most_common_type, count = counter.most_common(1)[0]
    
    confidence = f"{count}/{len(rounds)}"
    
    voted_result = {
        "type": most_common_type,
        "confidence": confidence,
        "all_rounds": rounds,
    }
    
    if count == len(rounds) and rounds[0].get("status") == "success":
        voted_result.update(rounds[0]["result"])
    
    return voted_result


def vote_core_constraints(rounds: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    对 Core Constraints 维度进行投票
    
    投票字段：constraints[*].name（约束名称集合）
    
    Args:
        rounds: 3 轮抽取结果（已归一化）
    
    Returns:
        投票结果（包含 constraints, all_rounds）
    """
    all_constraint_sets = []
    for r in rounds:
        if r.get("status") == "success":
            constraints = r["result"].get("constraints", [])
            constraint_names = {c["name"] for c in constraints}
            all_constraint_sets.append(constraint_names)
    
    if not all_constraint_sets:
        return {"constraints": [], "all_rounds": rounds}
    
    all_names = set()
    for s in all_constraint_sets:
        all_names.update(s)
    
    voted_constraints = []
    for name in all_names:
        count = sum(1 for s in all_constraint_sets if name in s)
        if count >= 2:
            for r in rounds:
                if r.get("status") == "success":
                    for c in r["result"].get("constraints", []):
                        if c["name"] == name:
                            voted_constraints.append({
                                "name": c["name"],
                                "description": c.get("description", ""),
                                "confidence": f"{count}/{len(rounds)}",
                            })
                            break
                    break
    
    return {
        "constraints": voted_constraints,
        "all_rounds": rounds,
    }


def vote_objective(rounds: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    对 Objective 维度进行投票
    
    投票字段：type
    
    Args:
        rounds: 3 轮抽取结果（已归一化）
    
    Returns:
        投票结果（包含 type, description, confidence, all_rounds）
    """
    types = [r["result"].get("type") for r in rounds if r.get("status") == "success"]
    
    if not types:
        return {"type": None, "confidence": "0/3", "all_rounds": rounds}
    
    counter = Counter(types)
    most_common_type, count = counter.most_common(1)[0]
    
    confidence = f"{count}/{len(rounds)}"
    
    voted_result = {
        "type": most_common_type,
        "confidence": confidence,
        "all_rounds": rounds,
    }
    
    for r in rounds:
        if r.get("status") == "success" and r["result"].get("type") == most_common_type:
            voted_result["description"] = r["result"].get("description", "")
            break
    
    return voted_result


def vote_invariant(rounds: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    对 Invariant 维度进行投票
    
    投票字段：name
    
    Args:
        rounds: 3 轮抽取结果（已归一化）
    
    Returns:
        投票结果（包含 name, description, confidence, all_rounds）
    """
    names = [r["result"].get("name") for r in rounds if r.get("status") == "success"]
    
    if not names:
        return {"name": None, "confidence": "0/3", "all_rounds": rounds}
    
    counter = Counter(names)
    most_common_name, count = counter.most_common(1)[0]
    
    confidence = f"{count}/{len(rounds)}"
    
    voted_result = {
        "name": most_common_name,
        "confidence": confidence,
        "all_rounds": rounds,
    }
    
    for r in rounds:
        if r.get("status") == "success" and r["result"].get("name") == most_common_name:
            voted_result["description"] = r["result"].get("description", "")
            break
    
    return voted_result


def vote_single_problem(normalized_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    对单个题目的四维结果进行投票
    
    Args:
        normalized_data: 归一化后的数据（包含所有维度的所有轮次）
    
    Returns:
        投票后的结果（包含四维投票结果）
    """
    return {
        "problem_id": normalized_data["problem_id"],
        "source": normalized_data["source"],
        "input_structure": vote_input_structure(normalized_data["input_structure"]),
        "core_constraints": vote_core_constraints(normalized_data["core_constraints"]),
        "objective": vote_objective(normalized_data["objective"]),
        "invariant": vote_invariant(normalized_data["invariant"]),
    }


def vote_all_problems(normalized_dir: Path, voted_dir: Path, logger: logging.Logger) -> None:
    """
    对所有题目进行投票
    
    Args:
        normalized_dir: 归一化结果目录
        voted_dir: 投票输出目录
        logger: 日志记录器
    """
    voted_dir.mkdir(parents=True, exist_ok=True)
    
    normalized_files = list(normalized_dir.glob("*.json"))
    logger.info(f"找到 {len(normalized_files)} 个归一化文件")
    
    for normalized_file in normalized_files:
        normalized_data = json.loads(normalized_file.read_text(encoding="utf-8"))
        
        voted_data = vote_single_problem(normalized_data)
        
        output_file = voted_dir / normalized_file.name
        output_file.write_text(
            json.dumps(voted_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    logger.info(f"投票完成：{len(normalized_files)} 题已保存到 {voted_dir}")


def main():
    parser = argparse.ArgumentParser(description="多数投票")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="归一化结果目录（如 output/pilot/normalized/）",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="投票输出目录（如 output/pilot/voted/）",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别",
    )
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger = logging.getLogger(__name__)
    
    normalized_dir = Path(args.input)
    voted_dir = Path(args.output)
    
    if not normalized_dir.exists():
        logger.error(f"输入目录不存在：{normalized_dir}")
        return
    
    vote_all_problems(normalized_dir, voted_dir, logger)
    logger.info("Pilot Run 完成！检查 voted/ 目录查看最终结果")


if __name__ == "__main__":
    main()
