"""
覆盖率报告生成器：统计封闭分类的覆盖率与 OTHER 收敛情况

用法：
    python -m finiteness_verification.report \
        --input output/phase2/ \
        --output output/phase2/coverage_report.json

功能：
1. 汇总所有平台的分类结果
2. 计算覆盖率（非 OTHER 的比例）
3. 生成 OTHER 收敛曲线（随题目数增加，OTHER 比例的变化）
4. 跨平台对比（Luogu/CF/ICPC 覆盖率一致性）

输出：
- coverage_report.json — 覆盖率统计（整体 + 分维度 + 分平台）
- other_convergence/*.png — OTHER 收敛曲线图
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import numpy as np


def collect_classifications(classified_dirs: Dict[str, Path], logger: logging.Logger) -> Dict[str, List[Dict[str, Any]]]:
    """
    收集所有平台的分类结果
    
    Returns:
        {
            "luogu": [{"problem_id": ..., "input_structure": {...}, ...}, ...],
            "codeforces": [...],
            "icpc": [...]
        }
    """
    all_data = {}
    
    for platform, classified_dir in classified_dirs.items():
        if not classified_dir.exists():
            logger.warning(f"{platform}: 分类结果目录不存在，跳过")
            continue
        
        files = list(classified_dir.glob("*.json"))
        logger.info(f"{platform}: 找到 {len(files)} 个分类结果")
        
        data = []
        for f in files:
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                data.append(d)
            except Exception as e:
                logger.warning(f"  读取失败：{f.name} ({e})")
        
        all_data[platform] = data
    
    return all_data


def calculate_coverage(classifications: List[Dict[str, Any]], logger: logging.Logger) -> Dict[str, Any]:
    """
    计算覆盖率
    
    Returns:
        {
            "total_problems": int,
            "per_dimension": {
                "input_structure": {
                    "coverage_rate": float,
                    "other_rate": float,
                    "other_count": int,
                    "category_distribution": {"array": 100, "graph": 50, "OTHER": 10, ...}
                },
                ...
            }
        }
    """
    dimensions = ["input_structure", "core_constraints", "objective", "invariant"]
    
    coverage = {
        "total_problems": len(classifications),
        "per_dimension": {}
    }
    
    for dim in dimensions:
        categories = defaultdict(int)
        other_count = 0
        total = 0
        
        for problem in classifications:
            if dim in problem:
                category = problem[dim].get("category", "OTHER")
                categories[category] += 1
                total += 1
                if category == "OTHER":
                    other_count += 1
        
        if total > 0:
            coverage_rate = (total - other_count) / total
            other_rate = other_count / total
        else:
            coverage_rate = 0.0
            other_rate = 0.0
        
        coverage["per_dimension"][dim] = {
            "coverage_rate": coverage_rate,
            "other_rate": other_rate,
            "other_count": other_count,
            "total": total,
            "category_distribution": dict(categories)
        }
    
    return coverage


def generate_other_convergence_curve(
    classifications: List[Dict[str, Any]],
    dimension: str,
    output_file: Path,
    logger: logging.Logger
) -> None:
    """
    生成 OTHER 收敛曲线（随题目数增加，OTHER 比例的变化）
    """
    other_rates = []
    problem_counts = []
    
    other_count = 0
    total_count = 0
    
    for idx, problem in enumerate(classifications, start=1):
        if dimension in problem:
            category = problem[dimension].get("category", "OTHER")
            total_count += 1
            if category == "OTHER":
                other_count += 1
        
        if total_count > 0 and idx % 50 == 0:
            other_rates.append(other_count / total_count)
            problem_counts.append(idx)
    
    if total_count > 0:
        other_rates.append(other_count / total_count)
        problem_counts.append(len(classifications))
    
    if not other_rates:
        logger.warning(f"{dimension}: 无数据，跳过曲线生成")
        return
    
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        plt.figure(figsize=(10, 6))
        plt.plot(problem_counts, [r * 100 for r in other_rates], marker='o', markersize=4)
        plt.xlabel("累计题目数")
        plt.ylabel("OTHER 比例 (%)")
        plt.title(f"{dimension} 维度 OTHER 收敛曲线")
        plt.grid(True, alpha=0.3)
        plt.ylim(0, 100)
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"  {dimension}: OTHER 曲线已保存到 {output_file.name}")
        
    except ImportError:
        logger.warning(f"{dimension}: matplotlib 未安装，跳过图片生成")


def main():
    parser = argparse.ArgumentParser(description="覆盖率报告生成")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Phase 2 输出目录（如 output/phase2/）",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="报告输出文件（如 output/phase2/coverage_report.json）",
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
    
    phase2_dir = Path(args.input)
    
    classified_dirs = {
        "luogu": phase2_dir / "classified_luogu",
        "codeforces": phase2_dir / "classified_codeforces",
        "icpc": phase2_dir / "classified_icpc",
    }
    
    logger.info("=== 阶段 1: 收集分类结果 ===")
    all_data = collect_classifications(classified_dirs, logger)
    
    if not all_data:
        logger.error("未找到任何分类结果")
        return
    
    logger.info("\n=== 阶段 2: 计算覆盖率 ===")
    
    report = {
        "per_platform": {},
        "overall": {}
    }
    
    for platform, classifications in all_data.items():
        logger.info(f"计算 {platform} 覆盖率...")
        report["per_platform"][platform] = calculate_coverage(classifications, logger)
    
    all_classifications = []
    for data in all_data.values():
        all_classifications.extend(data)
    
    logger.info("计算整体覆盖率...")
    report["overall"] = calculate_coverage(all_classifications, logger)
    
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    logger.info(f"覆盖率报告已保存到：{output_file}")
    
    logger.info("\n=== 阶段 3: 生成 OTHER 收敛曲线 ===")
    
    other_convergence_dir = phase2_dir / "other_convergence"
    
    dimensions = ["input_structure", "core_constraints", "objective", "invariant"]
    
    for dim in dimensions:
        output_file = other_convergence_dir / f"other_{dim}.png"
        generate_other_convergence_curve(all_classifications, dim, output_file, logger)
    
    logger.info("\n=== 报告生成完成 ===")
    logger.info(f"覆盖率报告：{args.output}")
    logger.info(f"OTHER 收敛曲线：{other_convergence_dir}/other_*.png")
    
    logger.info("\n=== 覆盖率摘要 ===")
    for dim, data in report["overall"]["per_dimension"].items():
        logger.info(f"{dim}:")
        logger.info(f"  覆盖率: {data['coverage_rate']:.1%}")
        logger.info(f"  OTHER 比例: {data['other_rate']:.1%}")


if __name__ == "__main__":
    main()
