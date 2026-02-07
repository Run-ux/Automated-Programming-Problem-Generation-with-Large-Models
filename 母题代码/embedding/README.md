# Schema Embedding 向量化表示系统

## 研究价值

本模块实现了算法题目Schema的语义向量化表示，具有以下研究价值：

### 1. 学术创新性
- **首次提出**将算法题目的结构化描述转换为可计算的向量表示
- 结合了NLP领域的语义理解和算法教育领域的题目分析
- 为算法题目的自动化分析和生成提供了新的技术路径

### 2. 解决的关键问题
- ✅ **可重现性**: 相同Schema生成相同向量，实验结果可复现
- ✅ **相似度计算**: 通过余弦相似度量化题目相似性
- ✅ **自动化评估**: 支持大规模Schema质量分析
- ✅ **聚类与去重**: 自动识别相似题目和重复母题
- ✅ **题目推荐**: 基于向量检索的智能推荐系统

### 3. 潜在应用场景
- 在线编程平台的题目推荐
- 算法竞赛的题目库管理
- 个性化学习路径规划
- 自动化题目生成辅助
- 题目难度评估

## 技术架构

```
schemas.json (原始数据)
    ↓
[Text Preprocessing] 文本预处理
    ↓
[Embedding API] OpenAI/本地模型
    ↓
[Vector Storage] 向量存储 (FAISS/Chroma)
    ↓
[Analysis Tools] 分析工具
    ├── 相似度计算
    ├── 聚类分析
    ├── 可视化
    └── 质量评估
```

## 使用方法

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置千问API密钥
编辑 `config.py` 文件，设置你的千问API密钥：
```python
QWEN_API_KEY = "sk-ac54a665d5ed43b48a5f1a414d88245a"  # 替换为你的密钥
```

### 3. 测试API连接
```bash
python test_qwen_api.py
```
确保API工作正常后再进行大规模处理

### 4. 生成Embedding
```bash
python generate_embeddings.py
```
这将处理所有Schema并生成向量表示

### 5. 进行分析
```bash
python analyze_schemas.py
```
生成相似度矩阵、聚类分析和可视化

### 6. 使用推荐系统
```bash
python recommender.py
```
测试题目推荐和检索功能

## 输出文件

- `schema_embeddings.npz`: 所有Schema的向量表示
- `similarity_matrix.npy`: Schema间的相似度矩阵
- `clusters.json`: 聚类分析结果
- `visualizations/`: 可视化图表

## 研究论文方向

基于本工作可以撰写以下方向的论文：

1. **"基于语义向量的算法题目表示与相似度计算"**
   - 提出Schema向量化方法
   - 验证向量表示的有效性
   - 与传统方法对比

2. **"算法题目的自动聚类与分类体系构建"**
   - 基于Embedding的题目聚类
   - 构建算法题目分类树
   - 发现题目内在关联

3. **"大语言模型驱动的算法题目推荐系统"**
   - 设计向量检索机制
   - 实现个性化推荐
   - 评估推荐效果
