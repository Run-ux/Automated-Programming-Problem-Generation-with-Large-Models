"""
为组会生成可视化图表
需要安装：pip install matplotlib seaborn numpy
"""
import json
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

output_dir = Path('output/presentation/figures')
output_dir.mkdir(exist_ok=True, parents=True)

print("=" * 60)
print("📊 生成组会展示图表")
print("=" * 60)

# 1. 读取数据
print("\n📂 读取数据...")
with open('output/presentation/embeddings_summary.json', 'r', encoding='utf-8') as f:
    summary = json.load(f)

with open('output/presentation/visualization_data.json', 'r', encoding='utf-8') as f:
    viz = json.load(f)

# ============ 图1: 相似度矩阵热力图 ============
print("\n🎨 生成图1: 相似度矩阵热力图...")
sim_matrix = np.array(summary['similarity_matrix_sample']['matrix'])
titles = summary['similarity_matrix_sample']['titles']

plt.figure(figsize=(12, 10))
mask = np.triu(np.ones_like(sim_matrix, dtype=bool), k=1)  # 只显示下三角
sns.heatmap(sim_matrix, 
            mask=mask,
            xticklabels=[t[:8] + '...' if len(t) > 8 else t for t in titles],
            yticklabels=[t[:8] + '...' if len(t) > 8 else t for t in titles],
            annot=True, fmt='.3f', cmap='RdYlGn', 
            vmin=0.5, vmax=1.0, cbar_kws={'label': '余弦相似度'})
plt.title('题目相似度矩阵 (前10个题目)', fontsize=16, pad=20)
plt.xlabel('题目', fontsize=12)
plt.ylabel('题目', fontsize=12)
plt.tight_layout()
plt.savefig(output_dir / 'similarity_heatmap.png', dpi=300, bbox_inches='tight')
print(f"   ✅ 已保存: {output_dir / 'similarity_heatmap.png'}")

# ============ 图2: 向量模长分布 ============
print("\n🎨 生成图2: 向量模长分布...")
norms = viz['norm_distribution']['norms']

plt.figure(figsize=(10, 6))
plt.hist(norms, bins=15, color='skyblue', edgecolor='black', alpha=0.7, linewidth=1.5)
plt.axvline(np.mean(norms), color='red', linestyle='--', linewidth=2, 
            label=f'均值: {np.mean(norms):.2f}')
plt.axvline(np.median(norms), color='orange', linestyle='--', linewidth=2, 
            label=f'中位数: {np.median(norms):.2f}')
plt.xlabel('向量模长 (L2 Norm)', fontsize=13)
plt.ylabel('题目数量', fontsize=13)
plt.title('题目向量模长分布', fontsize=16, pad=15)
plt.legend(fontsize=11)
plt.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(output_dir / 'norm_distribution.png', dpi=300, bbox_inches='tight')
print(f"   ✅ 已保存: {output_dir / 'norm_distribution.png'}")

# ============ 图3: 维度分布 ============
print("\n🎨 生成图3: 前20个维度的分布特征...")
means = viz['dimension_distribution']['means']
stds = viz['dimension_distribution']['stds']
dims = viz['dimension_distribution']['dimensions']

plt.figure(figsize=(14, 6))
x = np.arange(len(dims))
plt.bar(x, means, yerr=stds, capsize=4, color='coral', alpha=0.8, 
        edgecolor='black', linewidth=1.2, error_kw={'linewidth': 1.5})
plt.xlabel('维度索引', fontsize=13)
plt.ylabel('平均值 ± 标准差', fontsize=13)
plt.title('向量前20个维度的统计特征', fontsize=16, pad=15)
plt.xticks(x, dims)
plt.axhline(0, color='gray', linestyle='--', linewidth=1)
plt.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(output_dir / 'dimension_distribution.png', dpi=300, bbox_inches='tight')
print(f"   ✅ 已保存: {output_dir / 'dimension_distribution.png'}")

# ============ 图4: 最相似题目对条形图 ============
print("\n🎨 生成图4: 最相似题目对...")
top_pairs = viz['top_similar_pairs']

if len(top_pairs) > 0:
    plt.figure(figsize=(12, 7))
    
    labels = [f"{pair['schema1']['title'][:6]}...\nvs\n{pair['schema2']['title'][:6]}..." 
              for pair in top_pairs]
    similarities = [pair['similarity'] for pair in top_pairs]
    
    colors = ['#2ecc71' if s >= 0.9 else '#f39c12' if s >= 0.85 else '#e74c3c' 
              for s in similarities]
    
    bars = plt.barh(range(len(labels)), similarities, color=colors, 
                    edgecolor='black', linewidth=1.5, alpha=0.8)
    
    # 添加数值标签
    for i, (bar, sim) in enumerate(zip(bars, similarities)):
        plt.text(sim + 0.01, i, f'{sim:.3f}', 
                va='center', fontsize=11, fontweight='bold')
    
    plt.yticks(range(len(labels)), labels, fontsize=10)
    plt.xlabel('余弦相似度', fontsize=13)
    plt.title('最相似的题目对 (Top 5)', fontsize=16, pad=15)
    plt.xlim([0.75, 1.0])
    plt.axvline(0.85, color='red', linestyle='--', linewidth=1.5, 
                alpha=0.6, label='相似阈值 (0.85)')
    plt.legend(fontsize=11)
    plt.grid(axis='x', alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / 'top_similar_pairs.png', dpi=300, bbox_inches='tight')
    print(f"   ✅ 已保存: {output_dir / 'top_similar_pairs.png'}")

# ============ 图5: 统计摘要表格图 ============
print("\n🎨 生成图5: 统计摘要表格...")
stats = summary['per_schema_statistics'][:10]  # 前10个

fig, ax = plt.subplots(figsize=(14, 8))
ax.axis('tight')
ax.axis('off')

table_data = []
table_data.append(['索引', '题目', '最小值', '最大值', '均值', '模长'])
for stat in stats:
    table_data.append([
        str(stat['index']),
        stat['title'][:10] + '...' if len(stat['title']) > 10 else stat['title'],
        f"{stat['min']:.4f}",
        f"{stat['max']:.4f}",
        f"{stat['mean']:.6f}",
        f"{stat['norm']:.2f}"
    ])

table = ax.table(cellText=table_data, cellLoc='center', loc='center',
                colWidths=[0.08, 0.25, 0.15, 0.15, 0.17, 0.15])
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1, 2)

# 设置表头样式
for i in range(6):
    cell = table[(0, i)]
    cell.set_facecolor('#3498db')
    cell.set_text_props(weight='bold', color='white')

# 交替行颜色
for i in range(1, len(table_data)):
    for j in range(6):
        cell = table[(i, j)]
        if i % 2 == 0:
            cell.set_facecolor('#ecf0f1')

plt.title('题目向量统计信息表 (前10个)', fontsize=16, pad=20, fontweight='bold')
plt.savefig(output_dir / 'statistics_table.png', dpi=300, bbox_inches='tight')
print(f"   ✅ 已保存: {output_dir / 'statistics_table.png'}")

# ============ 总结 ============
print("\n" + "=" * 60)
print("✅ 所有图表生成完成！")
print("=" * 60)
print(f"\n📂 输出目录: {output_dir.absolute()}")
print(f"\n📊 生成的图表:")
print(f"   1. similarity_heatmap.png - 相似度矩阵热力图")
print(f"   2. norm_distribution.png - 向量模长分布直方图")
print(f"   3. dimension_distribution.png - 维度特征柱状图")
print(f"   4. top_similar_pairs.png - 最相似题目对条形图")
print(f"   5. statistics_table.png - 统计信息表格")
print(f"\n💡 这些PNG图片可以直接插入PPT！")
print("=" * 60)
