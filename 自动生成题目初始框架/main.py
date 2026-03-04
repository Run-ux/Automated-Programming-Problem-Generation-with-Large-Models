import json
import logging
from pathlib import Path
from datetime import datetime

# 导入本地模块
from config import SOURCE_JSON_DIR, OUTPUT_DIR, TARGET_IDS, API_KEY
from logic_mutator import LogicMutator
from story_engine import StoryEngine
from llm_client import LLMClient

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_schema(problem_id: str) -> dict:
    json_path = SOURCE_JSON_DIR / f"{problem_id}.json"
    if not json_path.exists():
        logger.error(f"Schema file not found: {json_path}")
        return None
    
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_problem(problem_id: str, content: str, suffix: str = ""):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{problem_id}_generated_{timestamp}{suffix}.md"
    filepath = OUTPUT_DIR / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    logger.info(f"Generated problem saved to: {filepath}")

def main():
    logger.info("Starting Problem Generation Pipeline...")
    
    # 初始化组件
    story_engine = StoryEngine()
    llm_client = LLMClient(api_key=API_KEY)
    
    for pid in TARGET_IDS:
        logger.info(f"Processing Problem: {pid}")
        
        # 1. 加载 Schema
        schema = load_schema(pid)
        if not schema:
            continue
            
        # 2. 检查是否有 Transform Space
        if "transform_space" not in schema:
            logger.warning(f"No transform_space found for {pid}, skipping.")
            continue
            
        # 3. 逻辑变异 (生成两个不同的变体)
        mutator = LogicMutator(schema)
        
        for i in range(2): # 为每个题目生成 2 个变体
            logger.info(f"  > Generating Variant {i+1}...")
            
            # 3.1 变异生成骨架
            skeleton = mutator.mutate()
            
            # 3.2 选择故事主题
            theme = story_engine.select_theme()
            logger.info(f"    Theme selected: {theme['name']}")
            
            # 3.3 生成 Prompt
            prompt = story_engine.generate_narrative_prompt(skeleton, theme)
            
            # 3.4 调用 LLM 生成题面
            problem_text = llm_client.generate_problem_text(prompt)
            
            # 3.5 保存结果
            save_problem(pid, problem_text, suffix=f"_v{i+1}_{theme['id']}")
            
    logger.info("All done!")

if __name__ == "__main__":
    main()
