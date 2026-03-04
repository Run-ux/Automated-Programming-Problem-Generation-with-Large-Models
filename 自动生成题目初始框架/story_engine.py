import random
from typing import Dict, Any

class StoryEngine:
    """
    故事引擎：为逻辑骨架提供叙事背景
    """
    
    THEMES = [
        {
            "id": "cyberpunk",
            "name": "赛博朋克/黑客",
            "keywords": ["数据流", "神经网络", "防火墙", "黑客", "加密", "节点", "带宽"],
            "tone": "冷峻、技术流"
        },
        {
            "id": "magic",
            "name": "魔法王国/炼金术",
            "keywords": ["魔法阵", "元素", "晶石", "咒语", "能量波动", "法师", "符文"],
            "tone": "神秘、古老"
        },
        {
            "id": "space",
            "name": "太空探索/星际物流",
            "keywords": ["空间站", "跃迁引擎", "小行星带", "信号", "殖民地", "资源舱"],
            "tone": "宏大、探索"
        },
        {
            "id": "biology",
            "name": "基因工程/生物学",
            "keywords": ["DNA序列", "蛋白质折叠", "变异", "细胞", "酶", "进化"],
            "tone": "科学、严谨"
        },
        {
            "id": "daily",
            "name": "日常生活/校园",
            "keywords": ["排队", "书架", "超市", "选课", "社团活动", "公交车"],
            "tone": "轻松、亲切"
        }
    ]
    
    def select_theme(self) -> Dict[str, Any]:
        """随机选择一个主题"""
        return random.choice(self.THEMES)

    def generate_narrative_prompt(self, skeleton: Dict[str, Any], theme: Dict[str, Any]) -> str:
        """
        生成用于指导 LLM 进行叙事包装的 Prompt
        """
        input_type = skeleton["input_structure"].get("type", "data structure")
        objective = skeleton["objective"]
        params = skeleton["params"]
        structures = skeleton.get("active_structures", [])
        
        prompt = f"""
请你基于以下【逻辑骨架】和【故事主题】，创作一道算法竞赛题目的题面。

【逻辑骨架 (The Math)】:
1. **源题目 ID**: {skeleton['source_problem']}
2. **核心不变量 (Algorithm Invariant)**: {skeleton['invariant']} (请保证题目核心逻辑符合此描述，不要破坏它)
3. **输入结构**: {input_type}
4. **关键参数设置**: {params}
5. **求解目标**: {objective}
6. **特殊结构要求**: {', '.join(structures) if structures else '无'}

【故事主题 (The Theme)】:
- **主题**: {theme['name']}
- **关键词参考**: {', '.join(theme['keywords'])}
- **风格**: {theme['tone']}

【任务要求】:
1. **Title**: 创作一个符合主题的吸引人的标题。
2. **Description**: 结合主题编写题目背景。将数学概念通过隐喻映射到故事中（例如：数组 -> 能量晶石序列）。**注意：不要直接暴露算法名称**。
3. **Input Format**: 清晰描述输入格式，使用 LaTeX 格式（例如 $N, K$）。
4. **Output Format**: 清晰描述输出格式。
5. **Constraints**: 列出数据范围，特别是 Time Limit (默认 1.0s) 和 Memory Limit (256MB)。
   - 请根据【关键参数设置】中的数值来设定具体的约束范围（例如 $N$ 的大小）。
"""
        return prompt
