import os
import time
import json
import random
from google import genai
from google.genai import types
from leetcode_schema_extractor.Gemini.config import GEMINI_API_KEY

# ================= 核心修改区域 =================
MODEL_ID = "gemini-2.0-flash-lite" 
# ===============================================

# 实例化 Client
client = genai.Client(api_key=GEMINI_API_KEY)

# 代理设置
os.environ["HTTP_PROXY"] = "http://127.0.0.1:15887"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:15887"

def parse_to_schema_safe(problem_text):
    prompt = f"""
    你是算法题目结构化专家。请将以下力扣题目内容，按照如下五元组结构输出（用JSON格式）：
    Schema = {{
      Input Structure,
      Core Constraint,
      Objective Function,
      Algorithmic Invariant,
      Transformable Parameters
    }}
    题目内容如下：
    {problem_text}
    """
    
    # 重试策略：遇到限流或网络错误自动重试
    max_retries = 3
    
    for i in range(max_retries):
        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.1)
            )
            return response.text

        except Exception as e:
            err_msg = str(e)
            print(f"  ⚠️ 出错 (尝试 {i+1}/{max_retries}): {err_msg[:100]}...")

            # 429 限流处理
            if "429" in err_msg or "quota" in err_msg.lower():
                sleep_time = 10 * (i + 1)
                print(f"  ⏳ 触发限流，强制休眠 {sleep_time} 秒...")
                time.sleep(sleep_time)
            
            # 404 模型未找到处理（自动切换备用）
            elif "404" in err_msg and "NOT_FOUND" in err_msg:
                print("  ❌ 模型名称错误，请检查 MODEL_ID 设置。")
                return None
            
            # 网络断开处理
            else:
                print(f"  🌐 网络波动或未知错误，5秒后重试...")
                time.sleep(5)
                
    return None

def main():
    try:
        with open("problems_raw.json", "r", encoding="utf-8") as f:
            problems = json.load(f)
    except Exception:
        print("找不到 problems_raw.json")
        return

    schemas = []
    total = len(problems)

    print(f"🚀 开始处理，共 {len(problems)} 题")
    print(f"🤖 使用模型: {MODEL_ID}")

    for i, p in enumerate(problems):
        print(f"解析 ({i+1}/{total}): {p['title']}")
        
        result = parse_to_schema_safe(p["content"])
        
        if result:
            schemas.append({"slug": p["slug"], "title": p["title"], "schema": result})
            print("  ✅ 成功")
            # 即使是 Lite 模型，每跑完一个也建议休息 2-3 秒
            time.sleep(2)
        else:
            print("  ❌ 失败，跳过")

    if schemas:
        with open("schemas.json", "w", encoding="utf-8") as f:
            json.dump(schemas, f, ensure_ascii=False, indent=2)
        print(f"💾 已保存 {len(schemas)} 条数据到 schemas.json")

if __name__ == "__main__":
    main()