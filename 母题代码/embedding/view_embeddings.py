"""
查看和检查 schema_embeddings.npz 文件的内容
"""
import numpy as np
from pathlib import Path
import json

def view_embeddings(file_path="output/schema_embeddings.npz"):
    """查看embedding文件的详细信息"""
    
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        print(f"   请确保文件路径正确，当前工作目录: {Path.cwd()}")
        return
    
    print("="*60)
    print("📊 Schema Embeddings 文件查看器")
    print("="*60)
    
    # 文件基本信息
    file_size = file_path.stat().st_size
    print(f"\n📁 文件信息:")
    print(f"   路径: {file_path.absolute()}")
    print(f"   大小: {file_size / 1024:.2f} KB ({file_size / 1024 / 1024:.2f} MB)")
    print(f"   修改时间: {file_path.stat().st_mtime}")
    
    # 加载数据
    try:
        data = np.load(file_path, allow_pickle=True)
        print(f"\n✅ 文件加载成功!")
        
        # 显示包含的数组
        print(f"\n📦 包含的数据:")
        for key in data.files:
            print(f"   - {key}")
        
        # 显示embedding信息
        if 'embeddings' in data:
            embeddings = data['embeddings']
            print(f"\n🎯 Embeddings 详情:")
            print(f"   数量: {len(embeddings)} 个Schema")
            print(f"   维度: {embeddings.shape[1]} 维向量")
            print(f"   数据类型: {embeddings.dtype}")
            print(f"   内存占用: {embeddings.nbytes / 1024 / 1024:.2f} MB")
            print(f"   向量范围: [{embeddings.min():.4f}, {embeddings.max():.4f}]")
            
            # 显示第一个向量的样本
            print(f"\n📝 第一个Schema的向量样本 (前10个值):")
            print(f"   {embeddings[0][:10]}")
        
        # 显示metadata信息
        if 'metadata' in data:
            metadata = data['metadata']
            print(f"\n📋 Metadata 详情:")
            print(f"   数量: {len(metadata)} 个条目")
            
            # 显示前5个题目
            print(f"\n🏆 已处理的Schema (前10个):")
            for i, item in enumerate(metadata[:10]):
                title = item['title'] if isinstance(item, dict) else item.get('title', 'Unknown')
                print(f"   {i+1}. {title}")
            
            if len(metadata) > 10:
                print(f"   ... 还有 {len(metadata) - 10} 个")
            
            # 显示最后处理的几个
            if len(metadata) > 10:
                print(f"\n🔄 最近处理的Schema (后5个):")
                for i, item in enumerate(metadata[-5:], start=len(metadata)-4):
                    title = item['title'] if isinstance(item, dict) else item.get('title', 'Unknown')
                    print(f"   {i}. {title}")
        
        # 统计信息
        print(f"\n📈 统计信息:")
        if 'embeddings' in data:
            emb = data['embeddings']
            print(f"   平均值: {emb.mean():.6f}")
            print(f"   标准差: {emb.std():.6f}")
            print(f"   中位数: {np.median(emb):.6f}")
        
        # 完成度
        if 'metadata' in data:
            total_expected = 1000  # 从之前的进度条看到是1000个
            current = len(metadata)
            progress = current / total_expected * 100
            print(f"\n⏱️  处理进度:")
            print(f"   已完成: {current}/{total_expected} ({progress:.1f}%)")
            print(f"   剩余: {total_expected - current} 个")
        
    except Exception as e:
        print(f"\n❌ 读取文件时出错: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)

def export_to_json(npz_file="output/schema_embeddings.npz", 
                   json_file="output/embeddings_preview.json"):
    """导出部分数据为JSON格式，方便查看"""
    
    try:
        data = np.load(npz_file, allow_pickle=True)
        
        preview = {
            "total_schemas": len(data['embeddings']),
            "embedding_dimension": data['embeddings'].shape[1],
            "schemas": []
        }
        
        # 只导出前10个作为预览
        for i in range(min(10, len(data['metadata']))):
            item = {
                "index": int(data['metadata'][i].get('index', i)),
                "title": data['metadata'][i].get('title', 'Unknown'),
                "slug": data['metadata'][i].get('slug', ''),
                "embedding_sample": data['embeddings'][i][:10].tolist(),  # 只保存前10个值
                "embedding_stats": {
                    "min": float(data['embeddings'][i].min()),
                    "max": float(data['embeddings'][i].max()),
                    "mean": float(data['embeddings'][i].mean())
                }
            }
            preview["schemas"].append(item)
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(preview, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 已导出预览数据到: {json_file}")
        print(f"   你可以用文本编辑器打开这个JSON文件查看")
        
    except Exception as e:
        print(f"❌ 导出失败: {e}")

if __name__ == "__main__":
    print("\n选择操作:")
    print("1. 查看 embedding 文件详情")
    print("2. 导出为JSON格式（只导出前10个作为预览）")
    print("3. 两者都执行")
    
    choice = input("\n请选择 (1/2/3): ").strip()
    
    if choice in ['1', '3']:
        view_embeddings()
    
    if choice in ['2', '3']:
        print()
        export_to_json()
