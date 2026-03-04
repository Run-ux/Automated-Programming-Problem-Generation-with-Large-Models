import json
import logging
import http.client
from typing import Dict, Any

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LLMClient:
    """
    调用阿里云 DashScope (Qwen) API
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        # 如果使用 dashscope 库：
        try:
            import dashscope
            dashscope.api_key = api_key
            self.use_sdk = True
        except ImportError:
            self.use_sdk = False
            logger.warning("dashscope SDK not installed, falling back to HTTP requests if implemented (not fully implemented here)")

    def generate_problem_text(self, prompt: str) -> str:
        """调用 LLM 生成文本"""
        if self.use_sdk:
            import dashscope
            from dashscope import Generation
            
            messages = [
                {'role': 'system', 'content': '你是一位专业的算法竞赛出题人，擅长将通过数学模型转化为生动有趣的题目描述。'},
                {'role': 'user', 'content': prompt}
            ]
            
            try:
                response = Generation.call(
                    model='qwen-max',
                    messages=messages,
                    result_format='message',  # 返回格式
                )
                
                if response.status_code == http.client.OK:
                    return response.output.choices[0]['message']['content']
                else:
                    logger.error(f"API调用失败: {response.code} - {response.message}")
                    return f"Error: API调用失败 - {response.message}"
            except Exception as e:
                logger.error(f"Generate Error: {e}")
                return f"Error: {e}"
        else:
            return "Error: Dashscope SDK is required. Please install `dashscope`."

