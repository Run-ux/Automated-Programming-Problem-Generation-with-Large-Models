import random
from typing import Dict, Any, List

class LogicMutator:
    """
    逻辑变异器：基于 Transform Space 生成新的题目骨架
    """
    
    def __init__(self, schema_data: Dict[str, Any]):
        self.original_schema = schema_data
        self.transform_space = schema_data.get("transform_space", {})
        
    def mutate(self) -> Dict[str, Any]:
        """
        执行变异，返回一个新的逻辑骨架 (Logical Skeleton)
        """
        new_skeleton = {
            "source_problem": self.original_schema.get("problem_id"),
            "invariant": self.original_schema.get("invariant", {}), # 不变量保持不变
            "params": {},
            "objective": None,
            "constraints": []
        }
        
        # 1. 数值参数变异 (Numerical Mutation)
        numerical_params = self.transform_space.get("numerical_parameters", {})
        for param_name, config in numerical_params.items():
            min_val = config.get("min")
            max_val = config.get("max")
            # 简单的随机策略：在 min 和 max 之间随机选一个值，或者选择边界值
            val = self._pick_value(min_val, max_val)
            new_skeleton["params"][param_name] = val
            
        # 2. 目标函数变异 (Objective Mutation)
        objective_options = self.transform_space.get("objective_options", [])
        original_objective = self.original_schema.get("objective", {}).get("type", "unknown")
        
        # 尝试选择一个不同于原题的目标，如果没有选项则保持原样
        if objective_options:
             # 有一定概率保持原目标，也有概率变异
            new_objective = random.choice(objective_options)
            new_skeleton["objective"] = new_objective
        else:
            new_skeleton["objective"] = original_objective
            
        # 3. 结构与约束变异 (Structural Mutation)
        structural_options = self.transform_space.get("structural_options", [])
        
        # 随机选择 0-2 个结构变体
        selected_structures = random.sample(structural_options, k=min(len(structural_options), random.randint(0, 1)))
        new_skeleton["active_structures"] = selected_structures
        
        # 4. 组合输入描述 (Input Adjustment)
        # 这里简单地将原输入结构和变异后的参数结合
        new_skeleton["input_structure"] = self.original_schema.get("input_structure", {})
        
        return new_skeleton
    
    def _pick_value(self, min_val, max_val):
        """选择一个有趣的数值"""
        if min_val is None or max_val is None:
            return 100 # Default
        
        strategies = [
            lambda: min_val, # 极小值
            lambda: max_val, # 极大值
            lambda: (min_val + max_val) // 2, # 中间值
            lambda: random.randint(min_val, max_val) # 随机值
        ]
        return random.choice(strategies)()

