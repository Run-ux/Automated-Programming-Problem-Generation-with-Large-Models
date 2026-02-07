"""
生成Schema的Embedding向量表示（使用千问API）
"""
import json
import time
import numpy as np
import requests
from pathlib import Path
from typing import List, Dict, Any
from tqdm import tqdm
import config


def load_schemas(file_path: str) -> List[Dict[str, Any]]:
    """加载schemas.json文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"成功加载 {len(data)} 个Schema")
    return data


def prepare_text_for_embedding(schema: Dict[str, Any], field: str) -> str:
    """将Schema的某个字段准备为适合embedding的文本"""
    content = schema.get('schema', {}).get(field, '')
    
    # 处理列表类型
    if isinstance(content, list):
        return ' '.join(str(item) for item in content)
    # 处理字符串类型
    elif isinstance(content, str):
        return content
    # 处理字典类型
    elif isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)
    else:
        return str(content)


def get_embedding_qwen(text: str, max_retries: int = 3) -> np.ndarray:
    """
    使用千问API获取文本的embedding
    
    Args:
        text: 输入文本
        max_retries: 最大重试次数
    
    Returns:
        embedding向量（numpy数组）
    """
    headers = {
        "Authorization": f"Bearer {config.QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": config.QWEN_EMBEDDING_MODEL,
        "input": {
            "texts": [text]
        }
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                config.QWEN_API_URL,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                # 千问API返回格式: {"output": {"embeddings": [{"embedding": [...], "text_index": 0}]}}
                if "output" in result and "embeddings" in result["output"]:
                    embedding = result["output"]["embeddings"][0]["embedding"]
                    return np.array(embedding, dtype=np.float32)
                else:
                    print(f"  响应格式异常: {result}")
                    return None
            else:
                print(f"  API错误 {response.status_code}: {response.text[:200]}")
                if response.status_code == 429:  # 限流
                    wait_time = config.RATE_LIMIT_DELAY * (2 ** attempt)
                    print(f"  触发限流，等待 {wait_time} 秒...")
                    time.sleep(wait_time)
                else:
                    time.sleep(config.RATE_LIMIT_DELAY)
                    
        except requests.exceptions.Timeout:
            print(f"  请求超时，重试 {attempt + 1}/{max_retries}")
            time.sleep(config.RATE_LIMIT_DELAY * 2)
        except Exception as e:
            print(f"  请求异常: {e}")
            if attempt < max_retries - 1:
                time.sleep(config.RATE_LIMIT_DELAY)
    
    return None


def get_embedding_local(text: str) -> np.ndarray:
    """使用本地模型获取文本的embedding"""
    try:
        from sentence_transformers import SentenceTransformer
        if not hasattr(get_embedding_local, 'model'):
            get_embedding_local.model = SentenceTransformer(config.LOCAL_MODEL_NAME)
        return get_embedding_local.model.encode(text, convert_to_numpy=True)
    except Exception as e:
        print(f"  本地模型编码失败: {e}")
        return None


def generate_schema_embedding(schema: Dict[str, Any], strategy: str = "weighted") -> Dict[str, np.ndarray]:
    """
    为一个Schema生成向量表示
    
    Args:
        schema: Schema数据
        strategy: 组合策略 ("weighted", "concatenate", "separate")
    
    Returns:
        包含各个字段向量和组合向量的字典
    """
    # 选择embedding函数
    if config.USE_LOCAL_MODEL:
        get_embedding = get_embedding_local
    else:
        get_embedding = get_embedding_qwen  # 使用千问API
    
    embeddings = {}
    fields = ["Input Structure", "Core Constraint", "Objective Function", 
              "Algorithmic Invariant", "Transformable Parameters"]
    
    # 为每个字段生成向量
    for field in fields:
        text = prepare_text_for_embedding(schema, field)
        if text.strip():
            emb = get_embedding(text)
            if emb is not None:
                embeddings[field] = emb
        
        # API限流控制
        if not config.USE_LOCAL_MODEL:
            time.sleep(config.RATE_LIMIT_DELAY)
    
    # 组合策略
    if strategy == "weighted" and len(embeddings) > 0:
        # 加权平均
        combined = np.zeros_like(list(embeddings.values())[0])
        total_weight = 0
        for field, emb in embeddings.items():
            weight = config.FIELD_WEIGHTS.get(field, 0.2)
            combined += emb * weight
            total_weight += weight
        embeddings['combined'] = combined / total_weight if total_weight > 0 else combined
    
    elif strategy == "concatenate" and len(embeddings) > 0:
        # 直接拼接
        embeddings['combined'] = np.concatenate(list(embeddings.values()))
    
    return embeddings


def main():
    """主函数：生成所有Schema的embedding"""
    print("=" * 60)
    print("Schema Embedding 生成系统 (千问API)")
    print("=" * 60)
    
    # 创建输出目录
    Path(config.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    
    # 加载schemas
    schemas = load_schemas(config.SCHEMAS_PATH)
    
    # 存储结果
    all_embeddings = []
    metadata = []
    failed_count = 0
    
    print(f"\n开始生成Embedding (策略: {config.COMBINE_STRATEGY})")
    if config.USE_LOCAL_MODEL:
        print("处理模式: 本地模型")
    else:
        print(f"处理模式: 千问API ({config.QWEN_EMBEDDING_MODEL})")
    print("-" * 60)
    
    # 实时保存：每处理1个就保存一次
    for i, schema in enumerate(tqdm(schemas, desc="生成Embedding")):
        try:
            embeddings = generate_schema_embedding(schema, config.COMBINE_STRATEGY)
            
            if 'combined' in embeddings:
                all_embeddings.append(embeddings['combined'])
                metadata.append({
                    'index': i,
                    'title': schema.get('title', ''),
                    'slug': schema.get('slug', ''),
                    'has_all_fields': len(embeddings) == 6  # 5个字段 + combined
                })
                
                # 实时保存：每处理1个就立即保存
                if all_embeddings:
                    embeddings_array = np.array(all_embeddings)
                    np.savez_compressed(
                        config.EMBEDDINGS_FILE,
                        embeddings=embeddings_array,
                        metadata=np.array(metadata, dtype=object)
                    )
                    # 每10个打印一次保存提示，避免输出过多
                    if (i + 1) % 10 == 0:
                        print(f"\n💾 已保存: {i+1}/{len(schemas)} ({(i+1)/len(schemas)*100:.1f}%) | 文件大小: {Path(config.EMBEDDINGS_FILE).stat().st_size / 1024:.1f} KB")
            else:
                failed_count += 1
                print(f"\n警告: Schema #{i} ({schema.get('title', 'Unknown')}) 生成失败")
                
        except Exception as e:
            failed_count += 1
            print(f"\n错误: Schema #{i} 处理异常: {e}")
    
    # 保存结果
    if all_embeddings:
        print("\n保存Embedding到文件...")
        
        # 保存embedding矩阵
        embeddings_array = np.array(all_embeddings)
        np.savez_compressed(
            config.EMBEDDINGS_FILE,
            embeddings=embeddings_array,
            metadata=np.array(metadata, dtype=object)
        )
        
        # 保存元数据
        metadata_file = Path(config.OUTPUT_DIR) / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 成功生成 {len(all_embeddings)} 个Schema的Embedding")
        print(f"   - 向量维度: {embeddings_array.shape[1]}")
        print(f"   - 失败数量: {failed_count}")
        print(f"   - 保存路径: {config.EMBEDDINGS_FILE}")
        print(f"   - 元数据: {metadata_file}")
    else:
        print("❌ 没有成功生成任何Embedding")
    
    print("\n" + "=" * 60)
    print("处理完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
