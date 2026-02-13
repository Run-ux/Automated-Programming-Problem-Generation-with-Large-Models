"""
饱和曲线分析工具：验证标签集合是否"有限且可列"

用法：
    python -m finiteness_verification.analyze \
        --input output/phase1/voted/ \
        --output output/phase1/saturation_curves/

功能：
1. 汇总每维标签集合（从所有 voted JSON 中提取唯一标签）
2. 生成饱和曲线（累计题目数 vs 新增标签数）
3. 计算收敛指标（对数拟合 R²、尾部新增率）
4. 判定"有限可列"（基于阈值）

输出：
- labels_per_dimension.json — 每维的唯一标签集合
- saturation_curves/*.png — 四维饱和曲线图
- metrics.json — 收敛指标（R²、尾部新增率、总标签数）
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import linregress


def logarithmic_fit(x, a, b):
    """对数拟合函数: y = a * log(x) + b"""
    return a * np.log(x) + b


def collect_labels_from_voted(voted_dir: Path, logger: logging.Logger) -> Dict[str, Dict[str, Any]]:
    """
    从 voted/ 目录收集所有标签
    
    Returns:
        {
            "input_structure": {
                "labels": {"array", "graph", "tree", ...},
                "timeline": [(1, "array"), (2, "graph"), ...]  # (题目序号, 新增标签)
            },
            ...
        }
    """
    labels_data = {
        "input_structure": {"labels": set(), "timeline": []},
        "core_constraints": {"labels": set(), "timeline": []},
        "objective": {"labels": set(), "timeline": []},
        "invariant": {"labels": set(), "timeline": []},
    }
    
    voted_files = sorted(voted_dir.glob("*.json"))
    logger.info(f"收集标签：共 {len(voted_files)} 个 voted 文件")
    
    for idx, voted_file in enumerate(voted_files, start=1):
        data = json.loads(voted_file.read_text(encoding="utf-8"))
        
        if "input_structure" in data and data["input_structure"].get("type"):
            label = data["input_structure"]["type"]
            if label not in labels_data["input_structure"]["labels"]:
                labels_data["input_structure"]["labels"].add(label)
                labels_data["input_structure"]["timeline"].append((idx, label))
        
        if "core_constraints" in data:
            for constraint in data["core_constraints"].get("constraints", []):
                label = constraint.get("name")
                if label and label not in labels_data["core_constraints"]["labels"]:
                    labels_data["core_constraints"]["labels"].add(label)
                    labels_data["core_constraints"]["timeline"].append((idx, label))
        
        if "objective" in data and data["objective"].get("type"):
            label = data["objective"]["type"]
            if label not in labels_data["objective"]["labels"]:
                labels_data["objective"]["labels"].add(label)
                labels_data["objective"]["timeline"].append((idx, label))
        
        if "invariant" in data and data["invariant"].get("name"):
            label = data["invariant"]["name"]
            if label not in labels_data["invariant"]["labels"]:
                labels_data["invariant"]["labels"].add(label)
                labels_data["invariant"]["timeline"].append((idx, label))
    
    for dim in labels_data:
        labels_data[dim]["labels"] = sorted(labels_data[dim]["labels"])
    
    logger.info("标签收集完成：")
    for dim, data in labels_data.items():
        logger.info(f"  {dim}: {len(data['labels'])} 个唯一标签")
    
    return labels_data


def generate_saturation_curve(
    timeline: List[Tuple[int, str]], 
    total_problems: int,
    dimension_name: str,
    output_file: Path,
    logger: logging.Logger
) -> Dict[str, Any]:
    """
    生成饱和曲线并计算收敛指标
    
    Args:
        timeline: [(题目序号, 新增标签), ...]
        total_problems: 总题目数
        dimension_name: 维度名称
        output_file: 曲线图输出路径
        logger: 日志记录器
    
    Returns:
        {
            "total_labels": int,
            "r_squared": float,
            "tail_new_rate": float,  # 最后 100 题新增率
            "log_fit_params": {"a": float, "b": float}
        }
    """
    if not timeline:
        logger.warning(f"{dimension_name}: 无有效数据，跳过")
        return {
            "total_labels": 0,
            "r_squared": 0.0,
            "tail_new_rate": 0.0,
            "log_fit_params": None
        }
    
    cumulative_labels = []
    problem_indices = []
    
    for idx, _ in timeline:
        problem_indices.append(idx)
        cumulative_labels.append(len([t for t in timeline if t[0] <= idx]))
    
    if len(problem_indices) < 10:
        logger.warning(f"{dimension_name}: 数据点不足 (<10)，跳过拟合")
        return {
            "total_labels": len(timeline),
            "r_squared": 0.0,
            "tail_new_rate": 0.0,
            "log_fit_params": None
        }
    
    x = np.array(problem_indices)
    y = np.array(cumulative_labels)
    
    try:
        popt, _ = curve_fit(logarithmic_fit, x, y, maxfev=10000)
        a, b = popt
        y_pred = logarithmic_fit(x, a, b)
        
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        
    except Exception as e:
        logger.warning(f"{dimension_name}: 对数拟合失败 ({e})，使用线性拟合")
        slope, intercept, r_value, _, _ = linregress(x, y)
        r_squared = r_value ** 2
        a, b = slope, intercept
    
    tail_window = 100
    tail_start_idx = max(1, total_problems - tail_window)
    new_in_tail = len([t for t in timeline if t[0] >= tail_start_idx])
    tail_new_rate = new_in_tail / tail_window if tail_window > 0 else 0.0
    
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib import rcParams

        rcParams["font.family"] = "sans-serif"
        rcParams["font.sans-serif"] = [
            "Microsoft YaHei",
            "SimHei",
            "Noto Sans CJK SC",
            "WenQuanYi Micro Hei",
            "Arial Unicode MS",
            "DejaVu Sans",
        ]
        rcParams["axes.unicode_minus"] = False
        
        plt.figure(figsize=(10, 6))
        plt.scatter(problem_indices, cumulative_labels, alpha=0.6, label="实际数据")
        
        x_fit = np.linspace(1, total_problems, 500)
        y_fit = logarithmic_fit(x_fit, a, b)
        plt.plot(x_fit, y_fit, 'r--', label=f"对数拟合 (R²={r_squared:.3f})")
        
        plt.xlabel("累计题目数")
        plt.ylabel("累计标签数")
        plt.title(f"{dimension_name} 维度饱和曲线")
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"  {dimension_name}: 曲线已保存到 {output_file.name}")
        
    except ImportError:
        logger.warning(f"{dimension_name}: matplotlib 未安装，跳过图片生成")
    
    return {
        "total_labels": len(timeline),
        "r_squared": float(r_squared),
        "tail_new_rate": float(tail_new_rate),
        "log_fit_params": {"a": float(a), "b": float(b)}
    }


def analyze_saturation(
    labels_data: Dict[str, Dict[str, Any]],
    total_problems: int,
    output_dir: Path,
    logger: logging.Logger
) -> Dict[str, Any]:
    """
    分析所有维度的饱和曲线
    
    Returns:
        {
            "input_structure": {"total_labels": ..., "r_squared": ..., ...},
            "core_constraints": {...},
            "objective": {...},
            "invariant": {...}
        }
    """
    metrics = {}
    
    dimension_names = {
        "input_structure": "I - Input Structure",
        "core_constraints": "C - Core Constraints",
        "objective": "O - Objective",
        "invariant": "V - Invariant"
    }
    
    for dim_key, dim_data in labels_data.items():
        timeline = dim_data["timeline"]
        dim_name = dimension_names[dim_key]
        output_file = output_dir / f"saturation_{dim_key}.png"
        
        logger.info(f"生成饱和曲线: {dim_name}")
        
        metrics[dim_key] = generate_saturation_curve(
            timeline=timeline,
            total_problems=total_problems,
            dimension_name=dim_name,
            output_file=output_file,
            logger=logger
        )
    
    return metrics


def judge_finiteness(metrics: Dict[str, Any], logger: logging.Logger) -> Dict[str, str]:
    """
    判定"有限可列"（基于阈值）
    
    阈值：
    - R² > 0.95 → 强收敛
    - R² > 0.90 → 中等收敛
    - 尾部新增率 < 2% → 饱和
    
    Returns:
        {
            "input_structure": "FINITE" | "UNCERTAIN" | "INFINITE",
            ...
        }
    """
    judgments = {}
    
    for dim, data in metrics.items():
        r2 = data.get("r_squared", 0.0)
        tail_rate = data.get("tail_new_rate", 1.0)
        
        if r2 > 0.95 and tail_rate < 0.02:
            judgment = "FINITE (强收敛 + 饱和)"
        elif r2 > 0.90 and tail_rate < 0.05:
            judgment = "LIKELY_FINITE (中等收敛)"
        elif r2 > 0.80:
            judgment = "UNCERTAIN (收敛趋势明显，需更多数据)"
        else:
            judgment = "UNCERTAIN (收敛不明显)"
        
        judgments[dim] = judgment
        logger.info(f"  {dim}: {judgment} (R²={r2:.3f}, tail_rate={tail_rate:.3%})")
    
    return judgments


def main():
    parser = argparse.ArgumentParser(description="饱和曲线分析")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="voted 结果目录（如 output/phase1/voted/）",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="分析输出目录（如 output/phase1/saturation_curves/）",
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
    
    voted_dir = Path(args.input)
    output_dir = Path(args.output)
    
    if not voted_dir.exists():
        logger.error(f"输入目录不存在：{voted_dir}")
        return
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=== 阶段 1: 收集标签 ===")
    labels_data = collect_labels_from_voted(voted_dir, logger)
    
    total_problems = len(list(voted_dir.glob("*.json")))
    
    labels_output = output_dir.parent / "labels_per_dimension.json"
    labels_output.write_text(
        json.dumps(
            {dim: data["labels"] for dim, data in labels_data.items()},
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )
    logger.info(f"标签集合已保存到：{labels_output}")
    
    logger.info("\n=== 阶段 2: 生成饱和曲线 ===")
    metrics = analyze_saturation(labels_data, total_problems, output_dir, logger)
    
    metrics_output = output_dir / "metrics.json"
    metrics_output.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    logger.info(f"收敛指标已保存到：{metrics_output}")
    
    logger.info("\n=== 阶段 3: 判定有限可列性 ===")
    judgments = judge_finiteness(metrics, logger)
    
    judgment_output = output_dir / "finiteness_judgment.json"
    judgment_output.write_text(
        json.dumps(judgments, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    logger.info(f"判定结果已保存到：{judgment_output}")
    
    logger.info("\n=== 分析完成 ===")
    logger.info(f"饱和曲线图：{output_dir}/saturation_*.png")
    logger.info(f"收敛指标：{metrics_output}")
    logger.info(f"判定结果：{judgment_output}")


if __name__ == "__main__":
    main()
