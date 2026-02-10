"""
数据采样脚本：从三平台题库生成分层样本

任务：
- Phase 1 样本：从 luogu/codeforces/icpc 各抽取 500 题，共约 1500 题
- Pilot 样本：从 Phase 1 样本中随机抽取 50 题（真子集）
- 保证可复现性（固定随机种子）
- 输出格式：JSON，包含必需字段（problem_id, source, title, description, input, output, constraints）
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List

# 固定随机种子以保证可复现性
RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# 路径配置（绝对路径）
BASE_DIR = Path(r"D:\Automated-Programming-Problem-Generation-with-Large-Models")
CRAWL_OUTPUT_DIR = BASE_DIR / "爬取题目" / "output"
SAMPLE_OUTPUT_DIR = BASE_DIR / "finiteness_verification" / "data"

# 采样配置
PHASE1_SAMPLE_SIZE_PER_PLATFORM = 500
PILOT_SAMPLE_SIZE = 50

# 平台配置
PLATFORMS = ["luogu", "codeforces", "icpc"]


def load_index(platform: str) -> List[Dict]:
    """从指定平台的 index.json 加载题目数据"""
    index_path = CRAWL_OUTPUT_DIR / platform / "index.json"
    with open(index_path, encoding="utf-8") as f:
        data = json.load(f)
    print(f"[{platform}] 加载题目数: {len(data)}")
    return data


def extract_required_fields(problem: Dict) -> Dict:
    """提取必需字段（problem_id, source, title, description, input, output, constraints）"""
    return {
        "problem_id": problem["problem_id"],
        "source": problem["source"],
        "title": problem["title"],
        "description": problem["description"],
        "input": problem["input"],
        "output": problem["output"],
        "constraints": problem["constraints"],
    }


def stratified_sample_phase1() -> List[Dict]:
    """
    分层采样生成 Phase 1 样本
    从每个平台均衡采样 500 题（如不足则全量）
    """
    phase1_samples = []
    
    for platform in PLATFORMS:
        # 加载平台数据
        problems = load_index(platform)
        
        # 采样（如数据量不足则全量）
        sample_size = min(PHASE1_SAMPLE_SIZE_PER_PLATFORM, len(problems))
        sampled = random.sample(problems, sample_size)
        
        # 提取必需字段
        sampled_cleaned = [extract_required_fields(p) for p in sampled]
        phase1_samples.extend(sampled_cleaned)
        
        print(f"[{platform}] Phase 1 采样: {sample_size} 题")
    
    print(f"\n[Phase 1] 总计: {len(phase1_samples)} 题")
    return phase1_samples


def subsample_pilot(phase1_samples: List[Dict]) -> List[Dict]:
    """
    从 Phase 1 样本中随机抽取 Pilot 样本（真子集）
    """
    pilot_samples = random.sample(phase1_samples, PILOT_SAMPLE_SIZE)
    print(f"[Pilot] 采样: {PILOT_SAMPLE_SIZE} 题（Phase 1 子集）")
    return pilot_samples


def save_samples(samples: List[Dict], filename: str):
    """保存样本到 JSON 文件"""
    output_path = SAMPLE_OUTPUT_DIR / filename
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)
    print(f"[保存] {filename}: {len(samples)} 题")


def print_statistics(samples: List[Dict], name: str):
    """打印样本统计信息"""
    from collections import Counter
    source_counts = Counter(p["source"] for p in samples)
    print(f"\n{'='*50}")
    print(f"{name} 样本统计:")
    print(f"  总计: {len(samples)} 题")
    for source, count in source_counts.items():
        print(f"  {source}: {count} 题")
    print(f"{'='*50}\n")


def main():
    """主流程"""
    print("="*70)
    print("数据采样流程开始")
    print(f"随机种子: {RANDOM_SEED}")
    print("="*70 + "\n")
    
    # 1. 生成 Phase 1 样本
    print("[步骤 1/4] 生成 Phase 1 样本...")
    phase1_samples = stratified_sample_phase1()
    print_statistics(phase1_samples, "Phase 1")
    
    # 2. 生成 Pilot 样本
    print("[步骤 2/4] 生成 Pilot 样本...")
    pilot_samples = subsample_pilot(phase1_samples)
    print_statistics(pilot_samples, "Pilot")
    
    # 3. 保存 Phase 1 样本
    print("[步骤 3/4] 保存样本文件...")
    save_samples(phase1_samples, "sample_phase1.json")
    
    # 4. 保存 Pilot 样本
    save_samples(pilot_samples, "sample_pilot.json")
    
    print("\n" + "="*70)
    print("数据采样流程完成！")
    print("="*70)


if __name__ == "__main__":
    main()
