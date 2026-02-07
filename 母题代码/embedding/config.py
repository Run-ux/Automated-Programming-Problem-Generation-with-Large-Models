"""
配置文件 - Embedding系统配置
"""

from pathlib import Path

# 阿里云千问 API 配置（推荐）
QWEN_API_KEY = "sk-ac54a665d5ed43b48a5f1a414d88245a"  # 你的千问API密钥
QWEN_EMBEDDING_MODEL = "text-embedding-v3"  # 千问embedding模型
QWEN_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
EMBEDDING_DIMENSION = 1024  # text-embedding-v3实际返回: 1024维

# 使用千问API
USE_QWEN = True

# 备选：OpenAI API 配置
OPENAI_API_KEY = "sk-your-openai-api-key-here"
OPENAI_MODEL = "text-embedding-3-large"

# 备选：本地模型
USE_LOCAL_MODEL = False
LOCAL_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# LOCAL_MODEL_NAME = "BAAI/bge-large-zh-v1.5"  # 中文优化模型

# 输入输出路径
SCHEMAS_PATH = Path("../output/schemas_readable.json")
OUTPUT_DIR = Path("./output")
EMBEDDINGS_FILE = OUTPUT_DIR / "schema_embeddings.npz"
SIMILARITY_MATRIX_FILE = OUTPUT_DIR / "similarity_matrix.npy"
CLUSTERS_FILE = OUTPUT_DIR / "clusters.json"
SCHEMAS_FILE = SCHEMAS_PATH

# 向量化策略
COMBINE_STRATEGY = "weighted"  # 可选: "concatenate", "weighted", "separate"
FIELD_WEIGHTS = {
    "Input Structure": 0.2,
    "Core Constraint": 0.25,
    "Objective Function": 0.15,
    "Algorithmic Invariant": 0.25,
    "Transformable Parameters": 0.15
}

# 聚类参数
N_CLUSTERS = 30  # K-means聚类数量
SIMILARITY_THRESHOLD = 0.85  # 相似度阈值（用于去重）

# API 调用参数
BATCH_SIZE = 100  # 批量处理大小
RATE_LIMIT_DELAY = 0.5  # API调用间隔（秒）
MAX_RETRIES = 3  # 最大重试次数
