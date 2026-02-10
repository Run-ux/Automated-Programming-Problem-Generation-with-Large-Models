"""
主抽取管线：对样本题目进行多轮抽取（3x 采样 + 多数投票）

用法：
    python -m finiteness_verification.extract \
        --input data/sample_pilot.json \
        --output output/pilot/ \
        --rounds 3 \
        [--resume]

输出目录结构：
    output/pilot/
    ├── raw/          # 原始抽取结果（每题每维每轮独立文件）
    ├── normalized/   # 归一化后的结果
    ├── voted/        # 多数投票后的最终结果
    └── logs/         # 日志和进度记录
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

from finiteness_verification.qwen_client import QwenClient
from finiteness_verification.prompts import (
    prompt_input_structure,
    prompt_constraints,
    prompt_objective,
    prompt_invariant,
)


# ---------------------------------------------------------------------------
# RateLimiter（复用爬虫项目的限速逻辑）
# ---------------------------------------------------------------------------
class RateLimiter:
    """速率限制器：确保两次请求间隔不小于指定时间"""
    
    def __init__(self, min_interval: float = 1.0):
        self.min_interval = min_interval
        self._last_request_time: float = 0.0

    def wait(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_time = time.time()


# ---------------------------------------------------------------------------
# 维度配置（四维独立抽取）
# ---------------------------------------------------------------------------
DIMENSIONS = {
    "input_structure": {
        "key": "I",
        "module": prompt_input_structure,
    },
    "core_constraints": {
        "key": "C",
        "module": prompt_constraints,
    },
    "objective": {
        "key": "O",
        "module": prompt_objective,
    },
    "invariant": {
        "key": "V",
        "module": prompt_invariant,
    },
}


# ---------------------------------------------------------------------------
# 主抽取逻辑
# ---------------------------------------------------------------------------
def extract_single_dimension(
    client: QwenClient,
    problem: Dict[str, Any],
    dimension_name: str,
    round_num: int,
    rate_limiter: RateLimiter,
    logger: logging.Logger,
) -> Dict[str, Any]:
    """
    对单个题目的单个维度进行一次抽取
    
    Args:
        client: Qwen API 客户端
        problem: 题目字典（包含 problem_id, title, description, input, output, constraints）
        dimension_name: 维度名称（如 input_structure, core_constraints 等）
        round_num: 抽取轮次（1, 2, 3）
        rate_limiter: 速率限制器
        logger: 日志记录器
    
    Returns:
        抽取结果（JSON 对象）
    """
    dim_config = DIMENSIONS[dimension_name]
    module = dim_config["module"]
    
    system_prompt = module.build_system_prompt()
    user_prompt = module.build_user_prompt(problem)
    
    logger.info(
        f"  [{dimension_name}] Round {round_num} - {problem['problem_id']}"
    )
    
    # 速率限制
    rate_limiter.wait()
    
    try:
        result = client.chat_json(system_prompt, user_prompt)
        return {
            "problem_id": problem["problem_id"],
            "source": problem["source"],
            "dimension": dimension_name,
            "round": round_num,
            "result": result,
            "status": "success",
        }
    except Exception as e:
        logger.error(f"    ERROR: {e}")
        return {
            "problem_id": problem["problem_id"],
            "source": problem["source"],
            "dimension": dimension_name,
            "round": round_num,
            "result": {},
            "status": "failed",
            "error": str(e),
        }


def extract_all_rounds(
    client: QwenClient,
    problems: List[Dict[str, Any]],
    output_dir: Path,
    rounds: int,
    resume: bool,
    logger: logging.Logger,
) -> None:
    """
    对所有题目进行 N 轮抽取（每题每维 N 次）
    
    输出文件命名规则：
        raw/{problem_id}_{dimension}_round{N}.json
    
    Args:
        client: Qwen API 客户端
        problems: 题目列表
        output_dir: 输出根目录
        rounds: 抽取轮次（默认 3）
        resume: 是否断点续传（跳过已存在的文件）
        logger: 日志记录器
    """
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    rate_limiter = RateLimiter(min_interval=1.0)  # API 限速 1 秒/次
    
    total_tasks = len(problems) * len(DIMENSIONS) * rounds
    completed = 0
    skipped = 0
    
    logger.info(f"开始抽取：{len(problems)} 题 × {len(DIMENSIONS)} 维 × {rounds} 轮 = {total_tasks} 次调用")
    
    for problem in problems:
        problem_id = problem["problem_id"]
        logger.info(f"Processing: {problem_id}")
        
        for dim_name in DIMENSIONS:
            for round_num in range(1, rounds + 1):
                # 输出文件路径
                output_file = raw_dir / f"{problem_id}_{dim_name}_round{round_num}.json"
                
                # 断点续传：跳过已存在的文件
                if resume and output_file.exists():
                    logger.debug(f"    Skipping (already exists): {output_file.name}")
                    skipped += 1
                    completed += 1
                    continue
                
                # 执行抽取
                result = extract_single_dimension(
                    client, problem, dim_name, round_num, rate_limiter, logger
                )
                
                # 保存结果
                output_file.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                
                completed += 1
                
                if completed % 10 == 0:
                    logger.info(f"  Progress: {completed}/{total_tasks} ({100*completed/total_tasks:.1f}%)")
    
    logger.info(f"抽取完成：{completed} 个任务（跳过 {skipped} 个已存在文件）")


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="五元组抽取管线（多轮采样）")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="输入样本文件路径（如 data/sample_pilot.json）",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="输出目录路径（如 output/pilot/）",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=3,
        help="每题每维抽取轮次（默认 3）",
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
        help="日志级别（默认 INFO）",
    )
    
    args = parser.parse_args()
    
    # 配置日志
    output_dir = Path(args.output)
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "extract.log"
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    logger = logging.getLogger(__name__)
    
    # 读取样本数据
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"输入文件不存在：{input_path}")
        return
    
    problems = json.loads(input_path.read_text(encoding="utf-8"))
    logger.info(f"读取样本：{len(problems)} 题")
    
    # 初始化 Qwen 客户端
    try:
        client = QwenClient()
        logger.info("Qwen 客户端初始化成功")
    except RuntimeError as e:
        logger.error(f"Qwen 客户端初始化失败：{e}")
        logger.error("请设置环境变量 DASHSCOPE_API_KEY 或 QWEN_API_KEY")
        return
    
    # 执行抽取
    extract_all_rounds(
        client=client,
        problems=problems,
        output_dir=output_dir,
        rounds=args.rounds,
        resume=args.resume,
        logger=logger,
    )
    
    logger.info(f"所有结果已保存到：{output_dir / 'raw'}")
    logger.info("下一步：运行 normalize.py 进行归一化，然后运行 vote.py 进行多数投票")


if __name__ == "__main__":
    main()
