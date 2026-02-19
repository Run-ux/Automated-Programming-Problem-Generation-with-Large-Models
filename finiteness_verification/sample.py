"""
数据采样脚本：从三平台题库生成分层样本（改进版）

任务：
- Phase 1 样本：3000题，每平台 1000 题
  - Codeforces: 按 difficulty（难度分档）和 tags 分布均匀抽样
  - Luogu: 按 difficulty 分布均匀抽样
  - ICPC: 随机抽样（无 difficulty/tags）
- Pilot 样本：从 Phase 1 样本中随机抽取 50 题（真子集）
- 保证可复现性（固定随机种子）

分层策略：
1. Codeforces: 
   - Primary: difficulty 分档 (1500-1800, 1800-2100, 2100-2400, 2400-2700, 2700+)
   - Secondary: 确保 tags 多样性
2. Luogu:
   - 按 difficulty 字符串分层（省选/NOI-, 提高+/省选-, NOI/NOI+/CTSC）
3. ICPC:
   - 随机抽样（数据无 difficulty/tags）
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List, Any, Counter
from collections import defaultdict

# 固定随机种子以保证可复现性
RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# 路径配置（绝对路径）
BASE_DIR = Path(r"D:\Automated-Programming-Problem-Generation-with-Large-Models")
CRAWL_OUTPUT_DIR = BASE_DIR / "爬取题目" / "output"
SAMPLE_OUTPUT_DIR = BASE_DIR / "finiteness_verification" / "data"

# 采样配置
PHASE1_SAMPLE_SIZE_PER_PLATFORM = 1000  # 每平台 1000 题，总计 3000 题
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
    """提取必需字段"""
    return {
        "problem_id": problem["problem_id"],
        "source": problem["source"],
        "title": problem["title"],
        "description": problem["description"],
        "input": problem["input"],
        "output": problem["output"],
        "constraints": problem["constraints"],
    }


def get_difficulty_bucket_cf(difficulty: int | str | None) -> str:
    """
    Codeforces 难度分档
    1500-3500 的范围分为 5 档
    """
    if difficulty is None:
        return "unknown"
    # 转换为整数
    try:
        diff = int(difficulty)
    except (ValueError, TypeError):
        return "unknown"
    
    if diff < 1800:
        return "1500-1800"
    elif diff < 2100:
        return "1800-2100"
    elif diff < 2400:
        return "2100-2400"
    elif diff < 2700:
        return "2400-2700"
    else:
        return "2700+"


def stratified_sample_codeforces(problems: List[Dict], sample_size: int) -> List[Dict]:
    """
    Codeforces 分层抽样策略：
    1. 按 difficulty 分层（每档至少保证一定数量）
    2. 在每档内尽量保证 tags 多样性
    """
    # 按 difficulty 分档
    buckets = defaultdict(list)
    for p in problems:
        diff = p.get("difficulty")
        bucket = get_difficulty_bucket_cf(diff)
        buckets[bucket].append(p)
    
    print(f"[codeforces] 难度分档分布:")
    for bucket in ["1500-1800", "1800-2100", "2100-2400", "2400-2700", "2700+", "unknown"]:
        print(f"  {bucket}: {len(buckets.get(bucket, []))} 题")
    
    # 计算每档的目标数量（按原始分布比例，但保证每档至少有一定基数）
    total = len(problems)
    bucket_sizes = {}
    
    # 策略：优先保证各难度档都有代表，然后按比例分配
    min_per_bucket = sample_size // 10  # 每档至少 10%
    remaining = sample_size
    
    valid_buckets = [b for b in buckets.keys() if len(buckets[b]) > 0]
    
    # 先给每档分配最小值
    for bucket in valid_buckets:
        bucket_sizes[bucket] = min(min_per_bucket, len(buckets[bucket]))
        remaining -= bucket_sizes[bucket]
    
    # 剩余按原始比例分配
    remaining_total = sum(len(buckets[b]) - bucket_sizes[b] for b in valid_buckets)
    if remaining_total > 0:
        for bucket in valid_buckets:
            available = len(buckets[bucket]) - bucket_sizes[bucket]
            if available > 0:
                extra = int(remaining * available / remaining_total)
                bucket_sizes[bucket] += extra
    
    # 调整以确保总和恰好为 sample_size
    current_total = sum(bucket_sizes.values())
    if current_total < sample_size:
        # 从最大的桶补充
        largest_bucket = max(valid_buckets, key=lambda b: len(buckets[b]))
        bucket_sizes[largest_bucket] += (sample_size - current_total)
    
    # 在每档内进行抽样，同时考虑 tags 多样性
    sampled = []
    for bucket, target_size in bucket_sizes.items():
        bucket_problems = buckets[bucket]
        if len(bucket_problems) <= target_size:
            # 如果该档题目不足，全部取用
            sampled.extend(bucket_problems)
        else:
            # 按 tags 多样性优先抽样
            # 统计该档所有 tags
            tag_count = defaultdict(int)
            for p in bucket_problems:
                for tag in p.get("tags", []):
                    tag_count[tag] += 1
            
            # 按 tag 覆盖率排序（优先选择能覆盖更多未选 tag 的题目）
            selected = []
            selected_tags = set()
            remaining_problems = bucket_problems.copy()
            
            # 贪心选择：每次选择能覆盖最多新 tag 的题目
            while len(selected) < target_size and remaining_problems:
                best_problem = None
                best_new_tags = -1
                
                for p in remaining_problems:
                    p_tags = set(p.get("tags", []))
                    new_tags = len(p_tags - selected_tags)
                    if new_tags > best_new_tags:
                        best_new_tags = new_tags
                        best_problem = p
                
                if best_problem:
                    selected.append(best_problem)
                    selected_tags.update(best_problem.get("tags", []))
                    remaining_problems.remove(best_problem)
                else:
                    break
            
            # 如果还没抽够，随机补充
            if len(selected) < target_size and remaining_problems:
                needed = target_size - len(selected)
                selected.extend(random.sample(remaining_problems, min(needed, len(remaining_problems))))
            
            sampled.extend(selected[:target_size])
    
    print(f"[codeforces] 分层抽样完成: {len(sampled)} 题")
    return sampled


def stratified_sample_luogu(problems: List[Dict], sample_size: int) -> List[Dict]:
    """
    洛谷分层抽样策略：
    按 difficulty 字符串分层，每层按比例抽样
    """
    # 按 difficulty 分组
    buckets = defaultdict(list)
    for p in problems:
        diff = p.get("difficulty", "unknown")
        if not diff or diff == "":
            diff = "unknown"
        buckets[diff].append(p)
    
    print(f"[luogu] 难度分档分布:")
    for bucket, items in sorted(buckets.items(), key=lambda x: -len(x[1])):
        print(f"  {bucket}: {len(items)} 题")
    
    # 按比例抽样
    total = len(problems)
    sampled = []
    
    for bucket, bucket_problems in buckets.items():
        # 该层的目标数量（按原始比例）
        target = int(sample_size * len(bucket_problems) / total)
        # 确保至少抽 1 题（如果该层有题且总样本足够）
        if target == 0 and len(bucket_problems) > 0 and sample_size > len(sampled) + len(buckets):
            target = 1
        
        if len(bucket_problems) <= target:
            sampled.extend(bucket_problems)
        else:
            sampled.extend(random.sample(bucket_problems, target))
    
    # 调整以确保总数恰好为 sample_size
    if len(sampled) < sample_size:
        # 从剩余题目中随机补充
        remaining = [p for p in problems if p not in sampled]
        needed = sample_size - len(sampled)
        if remaining:
            sampled.extend(random.sample(remaining, min(needed, len(remaining))))
    elif len(sampled) > sample_size:
        # 随机截断
        sampled = random.sample(sampled, sample_size)
    
    print(f"[luogu] 分层抽样完成: {len(sampled)} 题")
    return sampled


def random_sample_icpc(problems: List[Dict], sample_size: int) -> List[Dict]:
    """
    ICPC 随机抽样（无 difficulty/tags 信息）
    """
    print(f"[icpc] 题目总数: {len(problems)}")
    
    if len(problems) <= sample_size:
        sampled = problems
    else:
        sampled = random.sample(problems, sample_size)
    
    print(f"[icpc] 随机抽样完成: {len(sampled)} 题")
    return sampled


def stratified_sample_phase1() -> List[Dict]:
    """
    分层采样生成 Phase 1 样本
    总计 3000 题，每平台 1000 题
    """
    phase1_samples = []
    
    for platform in PLATFORMS:
        # 加载平台数据
        problems = load_index(platform)
        
        # 根据平台选择抽样策略
        if platform == "codeforces":
            sampled = stratified_sample_codeforces(problems, PHASE1_SAMPLE_SIZE_PER_PLATFORM)
        elif platform == "luogu":
            sampled = stratified_sample_luogu(problems, PHASE1_SAMPLE_SIZE_PER_PLATFORM)
        else:  # icpc
            sampled = random_sample_icpc(problems, PHASE1_SAMPLE_SIZE_PER_PLATFORM)
        
        # 提取必需字段
        sampled_cleaned = [extract_required_fields(p) for p in sampled]
        phase1_samples.extend(sampled_cleaned)
        
        print(f"[{platform}] Phase 1 采样: {len(sampled)} 题\n")
    
    print(f"[Phase 1] 总计: {len(phase1_samples)} 题")
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
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
    for source, count in sorted(source_counts.items()):
        print(f"  {source}: {count} 题")
    print(f"{'='*50}\n")


def print_detailed_statistics():
    """打印详细的抽样后统计（验证分布均匀性）"""
    print("\n" + "="*70)
    print("Phase 1 样本详细分布验证")
    print("="*70)
    
    # 加载原始数据以对比
    for platform in PLATFORMS:
        problems = load_index(platform)
        sample = json.load(open(SAMPLE_OUTPUT_DIR / "sample_phase1.json", encoding="utf-8"))
        sample_ids = {p["problem_id"] for p in sample if p["source"].startswith(platform)}
        sampled_problems = [p for p in problems if p["problem_id"] in sample_ids]
        
        print(f"\n[{platform}] 样本分布:")
        
        if platform == "codeforces":
            buckets = defaultdict(int)
            for p in sampled_problems:
                buckets[get_difficulty_bucket_cf(p.get("difficulty"))] += 1
            print("  Difficulty 分布:")
            for b in ["1500-1800", "1800-2100", "2100-2400", "2400-2700", "2700+", "unknown"]:
                print(f"    {b}: {buckets.get(b, 0)} 题")
                
        elif platform == "luogu":
            buckets = defaultdict(int)
            for p in sampled_problems:
                diff = p.get("difficulty", "unknown")
                if not diff:
                    diff = "unknown"
                buckets[diff] += 1
            print("  Difficulty 分布:")
            for b, c in sorted(buckets.items()):
                print(f"    {b}: {c} 题")
        
        else:  # icpc
            print(f"  随机抽取: {len(sampled_problems)} 题")


def main():
    """主流程"""
    print("="*70)
    print("数据采样流程开始（分层抽样版）")
    print(f"随机种子: {RANDOM_SEED}")
    print(f"目标样本量: {PHASE1_SAMPLE_SIZE_PER_PLATFORM * 3} 题（每平台 {PHASE1_SAMPLE_SIZE_PER_PLATFORM} 题）")
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
    
    # 5. 打印详细统计
    print("[步骤 4/4] 验证分布均匀性...")
    print_detailed_statistics()
    
    print("\n" + "="*70)
    print("数据采样流程完成！")
    print("="*70)


if __name__ == "__main__":
    main()
