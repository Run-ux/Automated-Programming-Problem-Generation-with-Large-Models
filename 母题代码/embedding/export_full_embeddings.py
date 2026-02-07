"""
导出完整的 embedding 向量为 JSON 格式，用于组会展示
注意：完整的1024维向量会导致文件很大，建议按需导出
"""
import numpy as np
import json
from pathlib import Path

def export_full_embeddings(npz_file="output/schema_embeddings.npz", 
                           output_dir="output/presentation"):
    """
    导出完整的 embedding 数据为多种格式
    
    输出文件：
    1. full_embeddings.json - 包含所有题目的完整1024维向量 (较大)
    2. sample_embeddings.json - 前5个题目的完整向量 (用于展示)
    3. embeddings_summary.json - 统计摘要和可视化数据
    """
    
    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("📊 导出完整 Embedding 数据用于组会展示")
    print("=" * 60)
    
    # 加载数据
    data = np.load(npz_file, allow_pickle=True)
    embeddings = data['embeddings']
    metadata = data['metadata']
    
    total = len(embeddings)
    dim = embeddings.shape[1]
    
    print(f"\n📁 数据概览:")
    print(f"   总题目数: {total}")
    print(f"   向量维度: {dim}")
    print(f"   数据大小: {embeddings.nbytes / 1024 / 1024:.2f} MB")
    
    # ===== 1. 导出前5个题目的完整向量（用于PPT展示） =====
    print(f"\n📝 正在导出样本数据 (前5个题目)...")
    sample_data = {
        "description": "LeetCode题目Schema的Embedding向量表示",
        "model": "Qwen text-embedding-v3",
        "dimension": int(dim),
        "sample_size": min(5, total),
        "schemas": []
    }
    
    for i in range(min(5, total)):
        schema_item = {
            "index": int(metadata[i].get('index', i)),
            "title": metadata[i].get('title', 'Unknown'),
            "slug": metadata[i].get('slug', ''),
            "difficulty": metadata[i].get('difficulty', 'Unknown'),
            "embedding_vector": embeddings[i].tolist(),  # 完整的1024维
            "statistics": {
                "min": float(embeddings[i].min()),
                "max": float(embeddings[i].max()),
                "mean": float(embeddings[i].mean()),
                "std": float(embeddings[i].std()),
                "norm": float(np.linalg.norm(embeddings[i])),
                "non_zero_count": int(np.count_nonzero(embeddings[i]))
            }
        }
        sample_data["schemas"].append(schema_item)
    
    sample_file = output_path / "sample_embeddings.json"
    with open(sample_file, 'w', encoding='utf-8') as f:
        json.dump(sample_data, f, ensure_ascii=False, indent=2)
    print(f"   ✅ 已保存: {sample_file}")
    print(f"   文件大小: {sample_file.stat().st_size / 1024:.1f} KB")
    
    # ===== 2. 导出统计摘要（用于图表展示） =====
    print(f"\n📊 正在生成统计摘要...")
    
    # 计算所有向量的统计信息
    all_stats = {
        "overall": {
            "total_schemas": int(total),
            "embedding_dimension": int(dim),
            "value_range": {
                "min": float(embeddings.min()),
                "max": float(embeddings.max())
            },
            "mean_across_all": float(embeddings.mean()),
            "std_across_all": float(embeddings.std())
        },
        "per_schema_statistics": []
    }
    
    # 每个题目的统计
    for i in range(total):
        stat = {
            "index": int(metadata[i].get('index', i)),
            "title": metadata[i].get('title', 'Unknown'),
            "slug": metadata[i].get('slug', ''),
            "min": float(embeddings[i].min()),
            "max": float(embeddings[i].max()),
            "mean": float(embeddings[i].mean()),
            "std": float(embeddings[i].std()),
            "norm": float(np.linalg.norm(embeddings[i]))
        }
        all_stats["per_schema_statistics"].append(stat)
    
    # 添加相似度矩阵样本（前10个题目之间的相似度）
    if total >= 2:
        print(f"   计算相似度矩阵样本...")
        n_sample = min(10, total)
        from sklearn.metrics.pairwise import cosine_similarity
        
        sample_embeddings = embeddings[:n_sample]
        sim_matrix = cosine_similarity(sample_embeddings)
        
        all_stats["similarity_matrix_sample"] = {
            "description": "前10个题目之间的余弦相似度",
            "size": int(n_sample),
            "titles": [metadata[i].get('title', 'Unknown') for i in range(n_sample)],
            "matrix": sim_matrix.tolist()
        }
    
    summary_file = output_path / "embeddings_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(all_stats, f, ensure_ascii=False, indent=2)
    print(f"   ✅ 已保存: {summary_file}")
    print(f"   文件大小: {summary_file.stat().st_size / 1024:.1f} KB")
    
    # ===== 3. 可选：导出所有题目的完整向量 =====
    print(f"\n❓ 是否导出所有 {total} 个题目的完整向量？")
    print(f"   预估文件大小: {total * dim * 8 / 1024 / 1024 * 1.5:.1f} MB")
    
    choice = input("   输入 y 导出，其他键跳过: ").strip().lower()
    
    if choice == 'y':
        print(f"\n📦 正在导出所有题目的完整向量...")
        full_data = {
            "description": "所有LeetCode题目Schema的完整Embedding向量",
            "model": "Qwen text-embedding-v3",
            "dimension": int(dim),
            "total_schemas": int(total),
            "schemas": []
        }
        
        for i in range(total):
            schema_item = {
                "index": int(metadata[i].get('index', i)),
                "title": metadata[i].get('title', 'Unknown'),
                "slug": metadata[i].get('slug', ''),
                "embedding_vector": embeddings[i].tolist()
            }
            full_data["schemas"].append(schema_item)
            
            if (i + 1) % 100 == 0:
                print(f"   处理进度: {i+1}/{total}")
        
        full_file = output_path / "full_embeddings.json"
        with open(full_file, 'w', encoding='utf-8') as f:
            json.dump(full_data, f, ensure_ascii=False, indent=2)
        print(f"   ✅ 已保存: {full_file}")
        print(f"   文件大小: {full_file.stat().st_size / 1024 / 1024:.1f} MB")
    
    # ===== 4. 生成展示用的可视化数据 =====
    print(f"\n📈 正在生成可视化数据...")
    
    viz_data = {
        "description": "用于组会PPT的可视化数据",
        "dimension_distribution": {
            "description": "每个维度的值分布统计",
            "dimensions": list(range(min(20, dim))),  # 只取前20维作为示例
            "means": [float(embeddings[:, i].mean()) for i in range(min(20, dim))],
            "stds": [float(embeddings[:, i].std()) for i in range(min(20, dim))]
        },
        "norm_distribution": {
            "description": "所有题目的向量模长分布",
            "norms": [float(np.linalg.norm(embeddings[i])) for i in range(total)]
        },
        "top_similar_pairs": []
    }
    
    # 找出最相似的5对题目
    if total >= 2:
        print(f"   寻找最相似的题目对...")
        from sklearn.metrics.pairwise import cosine_similarity
        
        sim_matrix = cosine_similarity(embeddings)
        np.fill_diagonal(sim_matrix, -1)  # 排除自己
        
        # 找出最相似的5对
        flat_indices = np.argsort(sim_matrix.ravel())[-5:][::-1]
        for idx in flat_indices:
            i, j = np.unravel_index(idx, sim_matrix.shape)
            if i < j:  # 避免重复
                pair = {
                    "schema1": {
                        "index": int(i),
                        "title": metadata[i].get('title', 'Unknown')
                    },
                    "schema2": {
                        "index": int(j),
                        "title": metadata[j].get('title', 'Unknown')
                    },
                    "similarity": float(sim_matrix[i, j])
                }
                viz_data["top_similar_pairs"].append(pair)
    
    viz_file = output_path / "visualization_data.json"
    with open(viz_file, 'w', encoding='utf-8') as f:
        json.dump(viz_data, f, ensure_ascii=False, indent=2)
    print(f"   ✅ 已保存: {viz_file}")
    print(f"   文件大小: {viz_file.stat().st_size / 1024:.1f} KB")
    
    # ===== 总结 =====
    print("\n" + "=" * 60)
    print("✅ 导出完成！组会展示文件已准备就绪")
    print("=" * 60)
    print(f"\n📂 输出目录: {output_path.absolute()}")
    print(f"\n📄 生成的文件:")
    print(f"   1. sample_embeddings.json")
    print(f"      → 前5个题目的完整1024维向量（用于详细展示）")
    print(f"   2. embeddings_summary.json")
    print(f"      → 所有题目的统计信息（用于表格展示）")
    print(f"   3. visualization_data.json")
    print(f"      → 可视化数据（用于图表）")
    if choice == 'y':
        print(f"   4. full_embeddings.json")
        print(f"      → 所有题目的完整向量（用于备份/完整展示）")
    
    print(f"\n💡 组会展示建议:")
    print(f"   - 用 sample_embeddings.json 展示具体例子")
    print(f"   - 用 embeddings_summary.json 制作统计表格")
    print(f"   - 用 visualization_data.json 绘制图表")
    print(f"   - 这些JSON文件可以直接用Python/Excel/在线工具打开")
    print("=" * 60)

if __name__ == "__main__":
    export_full_embeddings()
