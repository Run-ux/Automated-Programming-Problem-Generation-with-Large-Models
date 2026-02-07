"""
Schema 聚类与语义标签提取系统

目的：
1. 将已向量化的题目Schema聚类，发现题目之间的结构相似性
2. 为每个聚类自动生成语义标签（算法类型、解题策略等）
3. 构建题目关系图谱，支持知识管理与推荐
4. 评估聚类质量，优化聚类参数

输出：
- 聚类结果（包含簇ID、代表题、标签等）
- 标签库（自动生成的算法标签及权重）
- 聚类质量评估报告
- 可视化数据（2D/3D展示）
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass, asdict
from collections import Counter, defaultdict
import warnings
warnings.filterwarnings('ignore')

# 机器学习库
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.metrics import (
    silhouette_score, davies_bouldin_score, calinski_harabasz_score,
    silhouette_samples
)
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
from scipy.spatial.distance import pdist, squareform
from scipy.cluster.hierarchy import dendrogram, linkage

# 文本分析库
from sklearn.feature_extraction.text import TfidfVectorizer
from collections import Counter

# 可选：中文分词
try:
    import jieba
except ImportError:
    jieba = None

import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib import rcParams

# 设置中文显示
rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'WenQuanYi Zen Hei']
rcParams['axes.unicode_minus'] = False

import config


@dataclass
class ClusterLabel:
    """聚类标签"""
    cluster_id: int
    primary_label: str          # 主要标签（如"动态规划"）
    secondary_labels: List[str] # 次要标签（如["一维", "最优化"]）
    label_confidence: float     # 标签置信度（0-1）
    size: int                   # 聚类大小
    examples: List[Dict]        # 代表题目


@dataclass
class ClusteringResult:
    """聚类结果"""
    n_clusters: int
    labels: np.ndarray          # 每个样本的聚类标签
    centers: np.ndarray         # 聚类中心
    silhouette_score: float     # 轮廓系数
    davies_bouldin_score: float # DB指数
    calinski_harabasz_score: float # CH指数
    cluster_labels: List[ClusterLabel] # 每个聚类的标签


class SchemaClusterer:
    """Schema聚类与标签提取系统"""
    
    def __init__(self, embeddings: np.ndarray, metadata: np.ndarray, 
                 schemas: List[Dict] = None):
        """
        初始化聚类器
        
        Args:
            embeddings: N×D 向量矩阵（N个Schema，D维向量）
            metadata: N维元数据数组（包含title, slug等）
            schemas: 原始Schema列表（用于标签提取）
        """
        self.embeddings = embeddings
        self.metadata = metadata
        self.schemas = schemas or []
        self.n_samples = len(embeddings)
        
        print(f"✓ 已加载 {self.n_samples} 个Schema的向量表示")
        print(f"  向量维度: {embeddings.shape[1]}")
    
    def find_optimal_k(self, k_range: range = range(5, 51), 
                       method: str = 'silhouette') -> int:
        """
        使用多种指标寻找最优聚类数
        
        Args:
            k_range: 要测试的聚类数范围
            method: 评估方法 ('silhouette', 'davies_bouldin', 'elbow')
        
        Returns:
            最优的聚类数
        """
        print(f"\n🔍 寻找最优聚类数 (K范围: {k_range.start}-{k_range.stop})...")
        
        scores_silhouette = []
        scores_davies_bouldin = []
        scores_calinski = []
        
        for k in k_range:
            print(f"  测试 K={k}...", end='')
            
            # K-means聚类
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(self.embeddings)
            
            # 计算指标
            sil_score = silhouette_score(self.embeddings, labels)
            db_score = davies_bouldin_score(self.embeddings, labels)
            ch_score = calinski_harabasz_score(self.embeddings, labels)
            
            scores_silhouette.append(sil_score)
            scores_davies_bouldin.append(db_score)
            scores_calinski.append(ch_score)
            
            print(f" 轮廓系数={sil_score:.3f}, DB指数={db_score:.3f}")
        
        # 根据方法选择最优K
        if method == 'silhouette':
            optimal_k = list(k_range)[np.argmax(scores_silhouette)]
        elif method == 'davies_bouldin':
            optimal_k = list(k_range)[np.argmin(scores_davies_bouldin)]
        else:  # calinski
            optimal_k = list(k_range)[np.argmax(scores_calinski)]
        
        print(f"\n✓ 推荐聚类数: K={optimal_k}")
        
        # 绘制指标曲线
        self._plot_k_selection(k_range, scores_silhouette, 
                               scores_davies_bouldin, scores_calinski)
        
        return optimal_k
    
    def _plot_k_selection(self, k_range, sil_scores, db_scores, ch_scores):
        """绘制K值选择曲线"""
        fig, axes = plt.subplots(1, 3, figsize=(15, 4))
        
        k_list = list(k_range)
        
        # 轮廓系数
        axes[0].plot(k_list, sil_scores, 'o-', linewidth=2, markersize=6)
        axes[0].set_xlabel('聚类数 K')
        axes[0].set_ylabel('轮廓系数 (越大越好)')
        axes[0].set_title('轮廓系数')
        axes[0].grid(True, alpha=0.3)
        
        # DB指数
        axes[1].plot(k_list, db_scores, 's-', linewidth=2, markersize=6, color='orange')
        axes[1].set_xlabel('聚类数 K')
        axes[1].set_ylabel('DB指数 (越小越好)')
        axes[1].set_title('Davies-Bouldin指数')
        axes[1].grid(True, alpha=0.3)
        
        # CH指数
        axes[2].plot(k_list, ch_scores, '^-', linewidth=2, markersize=6, color='green')
        axes[2].set_xlabel('聚类数 K')
        axes[2].set_ylabel('CH指数 (越大越好)')
        axes[2].set_title('Calinski-Harabasz指数')
        axes[2].grid(True, alpha=0.3)
        
        plt.tight_layout()
        output_path = config.OUTPUT_DIR / 'k_selection_curves.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"✓ K值选择曲线已保存: {output_path}")
        plt.close()
    
    def cluster_kmeans(self, n_clusters: int = None) -> ClusteringResult:
        """
        执行K-means聚类
        
        Args:
            n_clusters: 聚类数（如果为None，自动寻找最优值）
        
        Returns:
            ClusteringResult对象
        """
        if n_clusters is None:
            n_clusters = self.find_optimal_k()
        
        print(f"\n🔄 执行K-means聚类 (K={n_clusters})...")
        
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10, max_iter=300)
        labels = kmeans.fit_predict(self.embeddings)
        centers = kmeans.cluster_centers_
        
        # 计算评估指标
        sil_score = silhouette_score(self.embeddings, labels)
        db_score = davies_bouldin_score(self.embeddings, labels)
        ch_score = calinski_harabasz_score(self.embeddings, labels)
        
        print(f"✓ 聚类完成:")
        print(f"  轮廓系数: {sil_score:.4f} (范围: [-1, 1], 越接近1越好)")
        print(f"  DB指数: {db_score:.4f} (越小越好)")
        print(f"  CH指数: {ch_score:.4f} (越大越好)")
        
        # 为每个聚类生成标签
        cluster_labels = self._generate_cluster_labels(labels, n_clusters)
        
        return ClusteringResult(
            n_clusters=n_clusters,
            labels=labels,
            centers=centers,
            silhouette_score=sil_score,
            davies_bouldin_score=db_score,
            calinski_harabasz_score=ch_score,
            cluster_labels=cluster_labels
        )
    
    def _generate_cluster_labels(self, labels: np.ndarray, 
                                 n_clusters: int) -> List[ClusterLabel]:
        """
        为每个聚类自动生成语义标签
        
        核心思想：
        1. 提取聚类内所有Schema的算法特征（不变量、约束等）
        2. 统计特征频率，得到该聚类的"特征指纹"
        3. 基于特征指纹生成语义标签
        """
        print(f"\n📝 为 {n_clusters} 个聚类生成标签...")
        
        cluster_labels = []
        
        for cluster_id in range(n_clusters):
            # 获取该聚类的所有样本索引
            cluster_indices = np.where(labels == cluster_id)[0]
            cluster_size = len(cluster_indices)
            
            # 提取该聚类的特征
            cluster_features = self._extract_cluster_features(cluster_indices)
            
            # 生成标签
            primary_label, secondary_labels, confidence = \
                self._generate_labels_from_features(cluster_features)
            
            # 选择代表题目（聚类中心最近的几个）
            center = self.embeddings[cluster_indices].mean(axis=0)
            distances = np.linalg.norm(
                self.embeddings[cluster_indices] - center, axis=1
            )
            example_indices = cluster_indices[np.argsort(distances)[:3]]
            
            examples = [
                {
                    'title': self.metadata[idx]['title'],
                    'slug': self.metadata[idx]['slug'],
                    'distance_to_center': float(distances[np.where(cluster_indices == idx)[0][0]])
                }
                for idx in example_indices
            ]
            
            label_obj = ClusterLabel(
                cluster_id=cluster_id,
                primary_label=primary_label,
                secondary_labels=secondary_labels,
                label_confidence=confidence,
                size=cluster_size,
                examples=examples
            )
            cluster_labels.append(label_obj)
            
            print(f"  簇{cluster_id}: {primary_label} ({cluster_size}题) "
                  f"- 置信度{confidence:.1%}")
        
        return cluster_labels
    
    def _extract_cluster_features(self, indices: np.ndarray) -> Dict[str, Counter]:
        """
        从聚类内的Schema提取特征
        
        返回特征计数器，便于统计最常见的特征
        """
        features = {
            'invariants': Counter(),
            'constraints': Counter(),
            'input_types': Counter(),
            'objectives': Counter()
        }
        
        for idx in indices:
            if idx < len(self.schemas):
                schema_item = self.schemas[idx]
                
                # 处理schema结构：可能是 {"schema": {...}} 或直接是 {...}
                if isinstance(schema_item, dict):
                    if 'schema' in schema_item:
                        schema = schema_item.get('schema', {})
                    else:
                        schema = schema_item
                else:
                    continue
                
                if not isinstance(schema, dict):
                    continue
                
                # 提取算法不变量
                invariants = schema.get('Algorithmic Invariant', [])
                if isinstance(invariants, list):
                    for inv in invariants:
                        key = self._simplify_feature(inv)
                        if key:
                            features['invariants'][key] += 1
                
                # 提取核心约束
                constraints = schema.get('Core Constraint', [])
                if isinstance(constraints, list):
                    for con in constraints[:2]:
                        key = self._simplify_feature(con)
                        if key:
                            features['constraints'][key] += 1
                
                # 提取输入结构
                input_struct = schema.get('Input Structure', [])
                if isinstance(input_struct, list) and len(input_struct) > 0:
                    inp = input_struct[0]
                    key = self._simplify_feature(inp)
                    if key:
                        features['input_types'][key] += 1
                
                # 提取目标函数
                objective = schema.get('Objective Function', '')
                if objective:
                    key = self._simplify_feature(objective)
                    if key:
                        features['objectives'][key] += 1
        
        return features
    
    def _simplify_feature(self, text: str) -> str:
        """
        简化特征文本，提取关键词
        例如：
        - "双指针移动，区间合法性单调" → "双指针"
        - "长度为 n 的数组 A[1..n]" → "数组"
        """
        if not isinstance(text, str):
            return ""
        
        text = text.lower()
        
        # 定义关键词映射
        keywords_map = {
            'dp': ['动态规划', 'dp', '动规'],
            '双指针': ['双指针', 'two pointer', '指针'],
            '滑动窗口': ['滑动窗口', 'sliding window', '窗口'],
            '分治': ['分治', '分而治之', 'divide and conquer'],
            '贪心': ['贪心', 'greedy'],
            '图论': ['图', 'graph', 'bfs', 'dfs', '最短路'],
            '树': ['树', 'tree', '二叉树', '遍历'],
            '前缀和': ['前缀和', 'prefix sum'],
            '二分查找': ['二分', 'binary search', '查找'],
            '排序': ['排序', 'sort'],
            '字符串': ['字符串', 'string', 'substring'],
            '数组': ['数组', 'array', 'sequence'],
            '计数': ['计数', 'count'],
            '最大值': ['最大', 'maximum', 'max'],
            '最小值': ['最小', 'minimum', 'min'],
            '求和': ['和', 'sum'],
        }
        
        for category, keywords in keywords_map.items():
            for keyword in keywords:
                if keyword in text:
                    return category
        
        # 如果没有匹配到，返回前20个字符
        return text[:20] if text else ""
    
    def _generate_labels_from_features(self, features: Dict[str, Counter]) \
            -> Tuple[str, List[str], float]:
        """
        基于特征计数生成标签
        
        Returns:
            (主标签, 次标签列表, 置信度)
        """
        # 算法类型优先级映射
        algorithm_keywords = {
            '双指针': ['双指针', '滑动窗口'],
            '动态规划': ['dp', '动态规划'],
            '分治': ['分治'],
            '贪心': ['贪心'],
            '图论': ['图论', '最短路', 'bfs', 'dfs'],
            '树形DP': ['树', 'dp'],
            '前缀和': ['前缀和'],
            '二分': ['二分查找', '二分'],
        }
        
        # 统计算法出现次数
        invariants = features['invariants']
        constraints = features['constraints']
        
        # 提取主要算法标签
        primary_label = '未分类'
        max_count = 0
        
        for algo, keywords in algorithm_keywords.items():
            count = sum(invariants.get(kw, 0) for kw in keywords)
            if count > max_count:
                max_count = count
                primary_label = algo
        
        # 提取次要标签（输入/约束特征）
        secondary_labels = []
        
        input_top = features['input_types'].most_common(1)
        if input_top:
            secondary_labels.append(f"输入:{input_top[0][0]}")
        
        constraints_top = features['constraints'].most_common(2)
        for con, count in constraints_top:
            if count >= 2:
                secondary_labels.append(f"约束:{con}")
        
        objectives_top = features['objectives'].most_common(1)
        if objectives_top:
            secondary_labels.append(f"目标:{objectives_top[0][0]}")
        
        # 计算置信度
        cluster_size = max_count
        confidence = min(0.95, 0.5 + cluster_size / 20)  # 示例置信度计算
        
        return primary_label, secondary_labels[:2], confidence
    
    def visualize_clusters_2d(self, labels: np.ndarray, 
                             cluster_labels: List[ClusterLabel] = None,
                             method: str = 'tsne'):
        """
        2D可视化聚类结果
        
        Args:
            labels: 聚类标签
            cluster_labels: 标签信息（用于注释）
            method: 降维方法 ('tsne' 或 'pca')
        """
        print(f"\n📊 使用{method.upper()}降维到2D进行可视化...")
        
        if method == 'tsne':
            reducer = TSNE(n_components=2, random_state=42, perplexity=min(30, self.n_samples-1))
            coords = reducer.fit_transform(self.embeddings)
            method_name = 't-SNE'
        else:
            reducer = PCA(n_components=2, random_state=42)
            coords = reducer.fit_transform(self.embeddings)
            method_name = 'PCA'
        
        # 绘制
        fig, ax = plt.subplots(figsize=(14, 10))
        
        unique_labels = np.unique(labels)
        colors = plt.cm.tab20(np.linspace(0, 1, len(unique_labels)))
        
        for cluster_id, color in zip(unique_labels, colors):
            mask = labels == cluster_id
            ax.scatter(coords[mask, 0], coords[mask, 1], 
                      c=[color], label=f'簇{cluster_id}', 
                      s=100, alpha=0.6, edgecolors='black', linewidth=0.5)
        
        # 添加标签信息
        if cluster_labels:
            for label_info in cluster_labels:
                cluster_id = label_info.cluster_id
                mask = labels == cluster_id
                cluster_coords = coords[mask]
                center = cluster_coords.mean(axis=0)
                
                ax.annotate(
                    label_info.primary_label,
                    xy=center, xytext=(5, 5),
                    textcoords='offset points',
                    fontsize=10, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.5)
                )
        
        ax.set_xlabel(f'{method_name} 第一主成分', fontsize=12)
        ax.set_ylabel(f'{method_name} 第二主成分', fontsize=12)
        ax.set_title(f'Schema 聚类可视化 ({method_name})', fontsize=14, fontweight='bold')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        output_path = config.OUTPUT_DIR / f'clustering_visualization_{method}.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"✓ 聚类可视化已保存: {output_path}")
        plt.close()
    
    def generate_report(self, result: ClusteringResult) -> str:
        """
        生成聚类分析报告
        """
        report = []
        report.append("=" * 80)
        report.append("Schema 聚类分析报告".center(80))
        report.append("=" * 80)
        report.append("")
        
        # 基本统计
        report.append(f"总样本数: {self.n_samples}")
        report.append(f"聚类数: {result.n_clusters}")
        report.append(f"平均每个聚类的大小: {self.n_samples // result.n_clusters}")
        report.append("")
        
        # 聚类质量指标
        report.append("【聚类质量评估】")
        report.append(f"  轮廓系数 (Silhouette): {result.silhouette_score:.4f}")
        report.append(f"    说明: 范围[-1, 1]，越接近1越好。当前值表示聚类效果{'优秀' if result.silhouette_score > 0.5 else '一般' if result.silhouette_score > 0.3 else '需改进'}")
        report.append(f"  Davies-Bouldin指数 (DB Index): {result.davies_bouldin_score:.4f}")
        report.append(f"    说明: 越小越好，表示聚类之间的分离度较好" if result.davies_bouldin_score < 1.5 else "    说明: 聚类分离度一般，建议优化参数")
        report.append(f"  Calinski-Harabasz指数 (CH Index): {result.calinski_harabasz_score:.2f}")
        report.append(f"    说明: 越大越好，表示聚类内紧凑性好，聚类间分离度大")
        report.append("")
        
        # 聚类标签信息
        report.append("【聚类标签信息】")
        report.append(f"{'簇ID':<5} {'标签':<15} {'置信度':<8} {'大小':<6} {'代表题目':<30}")
        report.append("-" * 70)
        
        for label_info in sorted(result.cluster_labels, key=lambda x: x.size, reverse=True):
            examples_str = " / ".join([ex['title'][:10] for ex in label_info.examples[:2]])
            report.append(
                f"{label_info.cluster_id:<5} "
                f"{label_info.primary_label:<15} "
                f"{label_info.label_confidence:.1%}{'':<2} "
                f"{label_info.size:<6} "
                f"{examples_str:<30}"
            )
        
        report.append("")
        
        # 聚类详细信息
        report.append("【聚类详细信息】")
        for label_info in sorted(result.cluster_labels, key=lambda x: x.size, reverse=True):
            report.append(f"\n【簇{label_info.cluster_id}】: {label_info.primary_label}")
            report.append(f"  大小: {label_info.size}道题")
            report.append(f"  置信度: {label_info.label_confidence:.1%}")
            if label_info.secondary_labels:
                report.append(f"  特征标签: {', '.join(label_info.secondary_labels)}")
            report.append(f"  代表题目:")
            for example in label_info.examples:
                report.append(f"    - {example['title']} (距簇心距离: {example['distance_to_center']:.3f})")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def save_results(self, result: ClusteringResult):
        """保存聚类结果"""
        
        # 保存聚类标签结果（JSON）
        labels_data = {
            'n_clusters': result.n_clusters,
            'quality_metrics': {
                'silhouette_score': float(result.silhouette_score),
                'davies_bouldin_score': float(result.davies_bouldin_score),
                'calinski_harabasz_score': float(result.calinski_harabasz_score)
            },
            'clusters': [
                {
                    'cluster_id': label.cluster_id,
                    'primary_label': label.primary_label,
                    'secondary_labels': label.secondary_labels,
                    'confidence': label.label_confidence,
                    'size': label.size,
                    'examples': label.examples
                }
                for label in result.cluster_labels
            ]
        }
        
        output_path = config.OUTPUT_DIR / 'clustering_labels.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(labels_data, f, ensure_ascii=False, indent=2)
        print(f"✓ 聚类标签已保存: {output_path}")
        
        # 保存聚类分配结果
        assignments = {
            'sample_count': len(result.labels),
            'assignments': {
                int(i): int(result.labels[i])
                for i in range(len(result.labels))
            }
        }
        output_path = config.OUTPUT_DIR / 'clustering_assignments.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(assignments, f, ensure_ascii=False, indent=2)
        print(f"✓ 聚类分配已保存: {output_path}")
        
        # 保存报告
        report = self.generate_report(result)
        output_path = config.OUTPUT_DIR / 'clustering_report.txt'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✓ 聚类报告已保存: {output_path}")
        
        print("\n报告内容:")
        print(report)


def load_data():
    """加载embeddings和metadata"""
    embeddings_file = config.OUTPUT_DIR / 'schema_embeddings.npz'
    
    if not embeddings_file.exists():
        print(f"❌ 找不到embedding文件: {embeddings_file}")
        return None, None, None
    
    data = np.load(embeddings_file, allow_pickle=True)
    embeddings = data['embeddings']
    metadata = data['metadata']
    
    # 加载原始schemas（用于特征提取）
    schemas_file = config.SCHEMAS_FILE
    schemas = None
    if isinstance(schemas_file, str):
        schemas_file = Path(schemas_file)
    if schemas_file.exists():
        with open(schemas_file, 'r', encoding='utf-8') as f:
            schemas = json.load(f)
    else:
        print(f"⚠️  Schema文件不存在: {schemas_file}")
    
    return embeddings, metadata, schemas


def main():
    """主程序"""
    print("\n" + "=" * 80)
    print("Schema 聚类与标签提取系统".center(80))
    print("=" * 80 + "\n")
    
    # 加载数据
    embeddings, metadata, schemas = load_data()
    if embeddings is None:
        return
    
    # 创建聚类器
    clusterer = SchemaClusterer(embeddings, metadata, schemas)
    
    # 找最优K值
    optimal_k = clusterer.find_optimal_k(k_range=range(10, 51, 5))
    
    # 执行聚类
    result = clusterer.cluster_kmeans(n_clusters=optimal_k)
    
    # 2D可视化
    clusterer.visualize_clusters_2d(result.labels, result.cluster_labels, method='tsne')
    clusterer.visualize_clusters_2d(result.labels, result.cluster_labels, method='pca')
    
    # 保存结果
    clusterer.save_results(result)
    
    print("\n✅ 聚类和标签提取完成！")


if __name__ == '__main__':
    main()
