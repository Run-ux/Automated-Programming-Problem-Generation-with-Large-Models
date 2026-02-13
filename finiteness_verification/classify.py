"""
封闭集合分类器：基于 Phase 1 标签集合对全量题目进行分类

用法：
    python -m finiteness_verification.classify \
        --labels output/phase1/labels_per_dimension.json \
        --input 爬取题目/output/luogu/index.json \
        --output output/phase2/classified/ \
        --platform luogu

功能：
1. 读取 Phase 1 的标签集合作为封闭候选列表
2. 对每道题目进行单轮分类（从候选列表中选择 + OTHER 兜底）
3. 输出分类结果（包含置信度）

与 extract.py 的区别：
- extract.py: 开放抽取（LLM 自由输出）
- classify.py: 封闭分类（从预定义列表中选择）
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

from finiteness_verification.qwen_client import QwenClient


class RateLimiter:
    def __init__(self, min_interval: float = 1.0):
        self.min_interval = min_interval
        self._last_request_time: float = 0.0

    def wait(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_time = time.time()


def build_classification_prompt(
    problem: Dict[str, Any],
    dimension: str,
    labels: List[str],
) -> tuple[str, str]:
    """
    构建封闭分类 prompt
    
    Returns:
        (system_prompt, user_prompt)
    """
    dimension_names = {
        "input_structure": "输入结构（Input Structure）",
        "core_constraints": "核心约束（Core Constraints）",
        "objective": "优化目标（Objective）",
        "invariant": "算法不变量（Invariant）",
    }
    
    dim_name = dimension_names[dimension]
    
    system_prompt = f"""你是编程竞赛题目分类专家。

你的任务是将题目归类到预定义的 {dim_name} 类别中。

分类规则：
1. 从候选列表中选择最匹配的类别
2. 如果没有合适的类别，选择 "OTHER"
3. 输出严格的 JSON 格式：{{"category": "选中的类别", "confidence": "high/medium/low"}}
4. 不要输出解释文字，只输出 JSON
5. 分类时关注题目的算法本质，忽略具体情境包装（如角色名、物品名等），从算法/数据结构角度选择类别

置信度标准：
- high: 非常确定该类别
- medium: 可能是该类别，但不完全确定
- low: 勉强匹配或选择 OTHER
"""
    
    labels_str = "\n".join([f"- {label}" for label in labels])
    
    user_prompt = f"""请将以下题目归类到 {dim_name} 的候选类别中。

候选类别列表：
{labels_str}
- OTHER（如果上述类别都不合适）

题目信息：
标题：{problem.get('title', 'N/A')}

题目描述：
{problem.get('description', '')}

输入格式：
{problem.get('input', '')}

输出格式：
{problem.get('output', '')}

约束条件：
{problem.get('constraints', '')}

---

请输出 JSON：
{{
    "category": "从候选列表中选择的类别（或 OTHER）",
    "confidence": "high | medium | low"
}}
"""
    
    return system_prompt, user_prompt


def classify_single_problem(
    client: QwenClient,
    problem: Dict[str, Any],
    dimension: str,
    labels: List[str],
    rate_limiter: RateLimiter,
    logger: logging.Logger,
) -> Dict[str, Any]:
    """
    对单个题目的单个维度进行分类
    """
    system_prompt, user_prompt = build_classification_prompt(problem, dimension, labels)
    
    logger.debug(f"  [{dimension}] {problem['problem_id']}")
    
    rate_limiter.wait()
    
    try:
        result = client.chat_json(system_prompt, user_prompt)
        category = result.get("category", "OTHER")
        confidence = result.get("confidence", "low")
        
        return {
            "problem_id": problem["problem_id"],
            "source": problem.get("source", "unknown"),
            "dimension": dimension,
            "category": category,
            "confidence": confidence,
            "status": "success",
        }
    except Exception as e:
        logger.error(f"    ERROR: {e}")
        return {
            "problem_id": problem["problem_id"],
            "source": problem.get("source", "unknown"),
            "dimension": dimension,
            "category": "OTHER",
            "confidence": "low",
            "status": "failed",
            "error": str(e),
        }


def classify_all_problems(
    client: QwenClient,
    problems: List[Dict[str, Any]],
    labels_per_dimension: Dict[str, List[str]],
    output_dir: Path,
    platform: str,
    resume: bool,
    logger: logging.Logger,
) -> None:
    """
    对所有题目进行四维分类
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    rate_limiter = RateLimiter(min_interval=1.0)
    
    total_tasks = len(problems) * 4
    completed = 0
    skipped = 0
    
    logger.info(f"开始分类：{len(problems)} 题 × 4 维 = {total_tasks} 次分类")
    
    for problem in problems:
        problem_id = problem.get("problem_id", problem.get("id", "unknown"))
        output_file = output_dir / f"{problem_id}.json"
        
        if resume and output_file.exists():
            logger.debug(f"Skipping (already exists): {problem_id}")
            skipped += 4
            completed += 4
            continue
        
        classifications = {
            "problem_id": problem_id,
            "source": platform,
            "input_structure": {},
            "core_constraints": {},
            "objective": {},
            "invariant": {},
        }
        
        for dim in labels_per_dimension:
            labels = labels_per_dimension[dim] + ["OTHER"]
            
            result = classify_single_problem(
                client, problem, dim, labels, rate_limiter, logger
            )
            
            classifications[dim] = {
                "category": result["category"],
                "confidence": result["confidence"],
                "status": result["status"],
            }
            
            completed += 1
        
        output_file.write_text(
            json.dumps(classifications, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        if completed % 20 == 0:
            logger.info(f"  Progress: {completed}/{total_tasks} ({100*completed/total_tasks:.1f}%)")
    
    logger.info(f"分类完成：{completed} 个任务（跳过 {skipped} 个已存在文件）")


def main():
    parser = argparse.ArgumentParser(description="封闭集合分类")
    parser.add_argument(
        "--labels",
        type=str,
        required=True,
        help="Phase 1 标签集合文件（如 output/phase1/labels_per_dimension.json）",
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="输入题目索引文件（如 爬取题目/output/luogu/index.json）",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="分类输出目录（如 output/phase2/classified_luogu/）",
    )
    parser.add_argument(
        "--platform",
        type=str,
        required=True,
        choices=["luogu", "codeforces", "icpc"],
        help="平台名称",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="断点续传：跳过已存在的文件",
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
    
    labels_file = Path(args.labels)
    if not labels_file.exists():
        logger.error(f"标签文件不存在：{labels_file}")
        return
    
    labels_per_dimension = json.loads(labels_file.read_text(encoding="utf-8"))
    logger.info(f"读取标签集合：{sum(len(v) for v in labels_per_dimension.values())} 个标签")
    
    input_file = Path(args.input)
    if not input_file.exists():
        logger.error(f"输入文件不存在：{input_file}")
        return
    
    problems = json.loads(input_file.read_text(encoding="utf-8"))
    logger.info(f"读取题目：{len(problems)} 题")
    
    try:
        client = QwenClient()
        logger.info("Qwen 客户端初始化成功")
    except RuntimeError as e:
        logger.error(f"Qwen 客户端初始化失败：{e}")
        return
    
    output_dir = Path(args.output)
    
    classify_all_problems(
        client=client,
        problems=problems,
        labels_per_dimension=labels_per_dimension,
        output_dir=output_dir,
        platform=args.platform,
        resume=args.resume,
        logger=logger,
    )
    
    logger.info(f"所有结果已保存到：{output_dir}")
    logger.info("下一步：运行 report.py 生成覆盖率报告")


if __name__ == "__main__":
    main()
