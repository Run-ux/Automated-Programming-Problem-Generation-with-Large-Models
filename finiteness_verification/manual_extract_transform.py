"""
手动提取 Transform Space 维度的脚本
仅针对指定的两个题目运行
"""
import glob
import json
import os
import re
from pathlib import Path
from typing import Dict, Any

from finiteness_verification.qwen_client import QwenClient
from finiteness_verification.prompts import prompt_transform_space

# 配置
MD_DIR = Path(r"d:\超级无敌宇宙霹雳连时不时卷时不时摆烂的农批大学习\出算法题目\auto\爬下来的题目\爬下来的题目\codeforces")
JSON_DIR = Path(r"d:\超级无敌宇宙霹雳连时不时卷时不时摆烂的农批大学习\出算法题目\auto\Automated-Programming-Problem-Generation-with-Large-Models\finiteness_verification\output\pilot\voted")
TARGET_IDS = ["CF25E", "CF360C"]

def parse_md_file(file_path: Path) -> Dict[str, str]:
    """简单的 Markdown 解析器"""
    content = file_path.read_text(encoding="utf-8")
    
    # 提取各个部分
    parts = {}
    
    # 标题通常在第一行
    lines = content.split('\n')
    parts['title'] = lines[0].strip()
    
    # 使用简单的切分逻辑
    sections = ['Input', 'Output', 'Constraints']
    current_content = []
    current_section = 'description'
    
    # 从第二行开始遍历
    for line in lines[1:]:
        stripped = line.strip()
        if stripped in sections:
            # 保存上一部分
            parts[current_section] = '\n'.join(current_content).strip()
            current_section = stripped.lower()
            current_content = []
        else:
            current_content.append(line)
            
    # 保存最后一部分
    parts[current_section] = '\n'.join(current_content).strip()
    
    return parts

def extract_transform_space(client: QwenClient, problem_data: Dict[str, Any]) -> Dict[str, Any]:
    """调用 API 提取 Transform Space"""
    system_prompt = prompt_transform_space.build_system_prompt()
    user_prompt = prompt_transform_space.build_user_prompt(problem_data)
    
    print(f"正在提取 {problem_data.get('title', 'Unknown')} 的 Transform Space...")
    try:
        response = client.chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1 # 使用较低温度以获得确定的结果
        )
        return response
    except Exception as e:
        print(f"提取失败: {e}")
        return {}

def main():
    # 初始化客户端 (需要环境变量 DASHSCOPE_API_KEY)
    try:
        client = QwenClient()
    except Exception as e:
        print(f"客户端初始化失败: {e}")
        print("请确保已设置 DASHSCOPE_API_KEY 环境变量")
        return

    for problem_id in TARGET_IDS:
        md_path = MD_DIR / f"{problem_id}.md"
        json_path = JSON_DIR / f"{problem_id}.json"
        
        if not md_path.exists():
            print(f"找不到 Markdown 文件: {md_path}")
            continue
            
        if not json_path.exists():
            print(f"找不到 JSON 文件: {json_path}")
            continue
            
        # 1. 解析题目内容
        problem_data = parse_md_file(md_path)
        
        # 2. 调用 LLM 提取 Transform Space
        transform_space = extract_transform_space(client, problem_data)
        
        if not transform_space:
            print(f"跳过 {problem_id} (提取结果为空)")
            continue
            
        # 3. 更新 JSON 文件
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 添加新维度
            data['transform_space'] = transform_space
            
            # 写回文件
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            print(f"成功更新 {problem_id} 的 JSON 文件")
            
        except Exception as e:
            print(f"更新文件失败: {e}")

if __name__ == "__main__":
    main()
