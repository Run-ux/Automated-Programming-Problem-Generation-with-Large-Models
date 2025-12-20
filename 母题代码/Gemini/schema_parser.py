import google.generativeai as genai
from leetcode_schema_extractor.Gemini.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

def parse_to_schema(problem_text):
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
    model = genai.GenerativeModel('models/gemini-2.5-pro')
    response = model.generate_content(prompt)
    return response.text if hasattr(response, 'text') else str(response)
