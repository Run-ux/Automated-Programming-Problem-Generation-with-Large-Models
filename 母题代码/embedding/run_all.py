"""
一键运行脚本：完整的Embedding生成和分析流程
"""
import sys
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """运行命令并显示进度"""
    print("\n" + "="*60)
    print(f"🚀 {description}")
    print("="*60)
    result = subprocess.run(cmd, shell=True, capture_output=False, text=True)
    if result.returncode == 0:
        print(f"✅ {description} 完成!")
    else:
        print(f"❌ {description} 失败! 请检查错误信息")
        return False
    return True

def main():
    """主流程"""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║     Schema Embedding 自动化处理系统 (千问API版本)       ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # 检查输出目录
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # 步骤1: 测试API
    print("\n步骤 1/3: 测试千问API连接")
    print("这将验证API密钥是否有效...")
    choice = input("是否执行API测试? (y/n): ")
    if choice.lower() == 'y':
        if not run_command("python test_qwen_api.py", "API连接测试"):
            print("\n⚠️  API测试失败，请先解决API问题再继续")
            return
    
    # 步骤2: 生成Embedding
    print("\n步骤 2/3: 生成所有Schema的Embedding")
    print("⚠️  注意：这可能需要30-60分钟，取决于Schema数量")
    print("   - 每个Schema的5个字段都会生成向量")
    print("   - API调用有延迟控制，避免限流")
    choice = input("是否开始生成Embedding? (y/n): ")
    if choice.lower() == 'y':
        if not run_command("python generate_embeddings.py", "Embedding生成"):
            print("\n⚠️  生成失败，请检查错误信息")
            return
        
        # 检查输出文件
        embedding_file = output_dir / "schema_embeddings.npz"
        if embedding_file.exists():
            print(f"\n✅ Embedding文件已生成: {embedding_file}")
            print(f"   文件大小: {embedding_file.stat().st_size / 1024 / 1024:.2f} MB")
        else:
            print("\n❌ 未找到输出文件，生成可能失败")
            return
    else:
        # 检查是否已有embedding文件
        embedding_file = output_dir / "schema_embeddings.npz"
        if not embedding_file.exists():
            print("\n⚠️  未找到已生成的Embedding文件，无法继续分析")
            return
    
    # 步骤3: 分析结果
    print("\n步骤 3/3: 分析Embedding数据")
    print("这将生成:")
    print("  - 相似度矩阵")
    print("  - 聚类结果")
    print("  - 可视化图表")
    print("  - 统计报告")
    choice = input("是否进行分析? (y/n): ")
    if choice.lower() == 'y':
        run_command("python analyze_schemas.py", "数据分析")
    
    # 步骤4: 测试推荐系统
    print("\n额外步骤: 测试推荐系统")
    choice = input("是否测试推荐系统? (y/n): ")
    if choice.lower() == 'y':
        run_command("python recommender.py", "推荐系统演示")
    
    # 完成
    print("\n" + "="*60)
    print("🎉 所有任务完成!")
    print("="*60)
    print("\n生成的文件:")
    print(f"  📁 {output_dir}/")
    for file in output_dir.glob("*"):
        size = file.stat().st_size / 1024
        print(f"    - {file.name} ({size:.1f} KB)")
    
    print("\n下一步:")
    print("  1. 查看 output/analysis_report.json 了解统计信息")
    print("  2. 查看 output/visualization_*.png 查看可视化结果")
    print("  3. 查看 output/clusters.json 查看聚类结果")
    print("\n📝 可以开始撰写论文了!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断执行")
    except Exception as e:
        print(f"\n\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
