"""
Schema分析工具：相似度计算、聚类、可视化
"""
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans, DBSCAN
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import config

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


def load_embeddings():
    """加载embedding数据"""
    data = np.load(config.EMBEDDINGS_FILE, allow_pickle=True)
    embeddings = data['embeddings']
    metadata = data['metadata']
    print(f"加载了 {len(embeddings)} 个Schema的Embedding")
    print(f"向量维度: {embeddings.shape[1]}")
    return embeddings, metadata


def compute_similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    """计算相似度矩阵"""
    print("计算相似度矩阵...")
    similarity = cosine_similarity(embeddings)
    np.save(config.SIMILARITY_MATRIX_FILE, similarity)
    print(f"保存到: {config.SIMILARITY_MATRIX_FILE}")
    return similarity


def find_similar_schemas(
    embeddings: np.ndarray, 
    metadata: np.ndarray, 
    index: int, 
    top_k: int = 10
) -> List[Tuple[int, str, float]]:
    """找到与指定Schema最相似的k个Schema"""
    target_vec = embeddings[index].reshape(1, -1)
    similarities = cosine_similarity(target_vec, embeddings)[0]
    
    # 排序（排除自己）
    similar_indices = np.argsort(similarities)[::-1][1:top_k+1]
    
    results = []
    for idx in similar_indices:
        title = metadata[idx]['title']
        score = similarities[idx]
        results.append((idx, title, score))
    
    return results


def detect_duplicates(
    embeddings: np.ndarray, 
    metadata: np.ndarray, 
    threshold: float = 0.85
) -> List[Tuple[int, int, float]]:
    """检测高度相似（可能重复）的Schema"""
    print(f"检测相似度 >= {threshold} 的Schema...")
    similarity = cosine_similarity(embeddings)
    
    duplicates = []
    n = len(embeddings)
    for i in range(n):
        for j in range(i+1, n):
            if similarity[i][j] >= threshold:
                duplicates.append((i, j, similarity[i][j]))
    
    print(f"发现 {len(duplicates)} 对高度相似的Schema")
    return duplicates


def perform_clustering(
    embeddings: np.ndarray, 
    metadata: np.ndarray, 
    n_clusters: int = None
) -> Dict:
    """执行K-means聚类"""
    if n_clusters is None:
        n_clusters = config.N_CLUSTERS
    
    print(f"执行K-means聚类 (k={n_clusters})...")
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)
    
    # 统计每个簇的题目
    clusters = {}
    for i, label in enumerate(labels):
        label = int(label)
        if label not in clusters:
            clusters[label] = []
        clusters[label].append({
            'index': int(i),
            'title': metadata[i]['title'],
            'slug': metadata[i]['slug']
        })
    
    # 保存聚类结果
    with open(config.CLUSTERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(clusters, f, ensure_ascii=False, indent=2)
    
    print(f"聚类完成，保存到: {config.CLUSTERS_FILE}")
    return clusters


def visualize_embeddings_2d(
    embeddings: np.ndarray, 
    metadata: np.ndarray,
    labels: np.ndarray = None,
    method: str = 'tsne'
):
    """2D可视化embedding"""
    print(f"使用{method.upper()}进行降维可视化...")
    
    if method == 'tsne':
        from sklearn.manifold import TSNE
        reducer = TSNE(n_components=2, random_state=42, perplexity=30)
    elif method == 'umap':
        import umap
        reducer = umap.UMAP(n_components=2, random_state=42)
    else:
        from sklearn.decomposition import PCA
        reducer = PCA(n_components=2, random_state=42)
    
    coords_2d = reducer.fit_transform(embeddings)
    
    # 绘图
    plt.figure(figsize=(14, 10))
    
    if labels is not None:
        scatter = plt.scatter(
            coords_2d[:, 0], 
            coords_2d[:, 1],
            c=labels,
            cmap='tab20',
            alpha=0.6,
            s=50
        )
        plt.colorbar(scatter, label='Cluster')
    else:
        plt.scatter(
            coords_2d[:, 0], 
            coords_2d[:, 1],
            alpha=0.6,
            s=50
        )
    
    plt.title(f'Schema Embedding 2D Visualization ({method.upper()})', fontsize=16)
    plt.xlabel('Dimension 1')
    plt.ylabel('Dimension 2')
    plt.grid(True, alpha=0.3)
    
    # 保存
    output_path = Path(config.OUTPUT_DIR) / f'visualization_{method}.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"保存可视化图: {output_path}")
    plt.close()


def analyze_cluster_characteristics(clusters: Dict, metadata: np.ndarray):
    """分析每个簇的特征"""
    print("\n" + "="*60)
    print("聚类分析结果")
    print("="*60)
    
    cluster_sizes = [(k, len(v)) for k, v in clusters.items()]
    cluster_sizes.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\n共 {len(clusters)} 个簇")
    print(f"最大簇: {cluster_sizes[0][1]} 个Schema")
    print(f"最小簇: {cluster_sizes[-1][1]} 个Schema")
    print(f"平均每簇: {np.mean([s for _, s in cluster_sizes]):.1f} 个Schema")
    
    # 显示前5个最大的簇
    print("\n前5个最大的簇:")
    for cluster_id, size in cluster_sizes[:5]:
        print(f"\n簇 {cluster_id} ({size} 个题目):")
        for item in clusters[str(cluster_id)][:5]:
            print(f"  - {item['title']}")
        if size > 5:
            print(f"  ... 还有 {size-5} 个题目")


def generate_analysis_report(
    embeddings: np.ndarray,
    metadata: np.ndarray,
    similarity_matrix: np.ndarray,
    clusters: Dict
):
    """生成分析报告"""
    report = {
        "total_schemas": len(embeddings),
        "embedding_dimension": embeddings.shape[1],
        "n_clusters": len(clusters),
        "statistics": {
            "mean_similarity": float(np.mean(similarity_matrix[np.triu_indices_from(similarity_matrix, k=1)])),
            "median_similarity": float(np.median(similarity_matrix[np.triu_indices_from(similarity_matrix, k=1)])),
            "max_similarity": float(np.max(similarity_matrix[np.triu_indices_from(similarity_matrix, k=1)])),
            "min_similarity": float(np.min(similarity_matrix[np.triu_indices_from(similarity_matrix, k=1)]))
        },
        "cluster_sizes": {k: len(v) for k, v in clusters.items()}
    }
    
    report_path = Path(config.OUTPUT_DIR) / "analysis_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n分析报告保存到: {report_path}")
    return report


def main():
    """主分析流程"""
    print("="*60)
    print("Schema Embedding 分析系统")
    print("="*60)
    
    # 加载数据
    embeddings, metadata = load_embeddings()
    
    # 1. 计算相似度矩阵
    similarity_matrix = compute_similarity_matrix(embeddings)
    
    # 2. 检测重复/高度相似的Schema
    duplicates = detect_duplicates(embeddings, metadata, config.SIMILARITY_THRESHOLD)
    if duplicates:
        print("\n高度相似的Schema对:")
        for i, j, score in duplicates[:10]:
            print(f"  {metadata[i]['title']} <-> {metadata[j]['title']}: {score:.4f}")
    
    # 3. 聚类分析
    clusters = perform_clustering(embeddings, metadata)
    analyze_cluster_characteristics(clusters, metadata)
    
    # 4. 可视化
    kmeans = KMeans(n_clusters=config.N_CLUSTERS, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)
    
    print("\n生成可视化图表...")
    visualize_embeddings_2d(embeddings, metadata, labels, method='tsne')
    visualize_embeddings_2d(embeddings, metadata, labels, method='pca')
    
    # 5. 生成报告
    report = generate_analysis_report(embeddings, metadata, similarity_matrix, clusters)
    
    print("\n" + "="*60)
    print("分析完成!")
    print("="*60)
    print(f"\n关键统计:")
    print(f"  - 平均相似度: {report['statistics']['mean_similarity']:.4f}")
    print(f"  - 最高相似度: {report['statistics']['max_similarity']:.4f}")
    print(f"  - 聚类数量: {report['n_clusters']}")
    
    # 示例：查找相似题目
    print("\n示例：查找与第一个Schema最相似的题目")
    similar = find_similar_schemas(embeddings, metadata, 0, top_k=5)
    print(f"与 '{metadata[0]['title']}' 最相似的题目:")
    for idx, title, score in similar:
        print(f"  {score:.4f} - {title}")


if __name__ == "__main__":
    main()
