import os
from pathlib import Path

# 配置 API Key
API_KEY = "sk-d43ba17c869c407ba8f32b4d2c538fcb"

# 设置环境变量，供 dashscope 使用
os.environ["DASHSCOPE_API_KEY"] = API_KEY

# 路径配置
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
SOURCE_JSON_DIR = PROJECT_ROOT / "finiteness_verification" / "output" / "pilot" / "voted"
OUTPUT_DIR = BASE_DIR / "output"

# 确保输出目录存在
OUTPUT_DIR.mkdir(exist_ok=True)

# 目标题目 ID
TARGET_IDS = ["CF25E", "CF360C"]
