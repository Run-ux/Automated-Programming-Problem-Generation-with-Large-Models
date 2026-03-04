import subprocess
import sys
import time
import random
import json
import re
from typing import List, Dict, Any, Tuple, Optional

try:
    import openai
except ImportError:
    print("Error: 'openai' module not found. Please install it using: pip install openai")
    sys.exit(1)

class LLMClient:
    """
    大模型客户端封装类。
    负责与阿里云 Qwen (DashScope) API 进行交互，提供文本生成、代码生成和向量嵌入功能。
    """
    def __init__(self):
        self.client = openai.OpenAI(
            api_key="sk-0d4a5227a9c34856a77b4eb83cf81ab9", 
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

    def generate_text(self, prompt: str, model: str = "qwen-plus") -> str:
        """
        调用大模型生成文本回复。
        
        Args:
            prompt: 提示词
            model: 模型名称，默认为 qwen-plus
            
        Returns:
            str: 模型生成的文本内容
        """
        print(f"  [LLM-Text] Calling Qwen ({model})...")
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant for evaluating coding problems."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"API Error: {e}")
            return ""

    def generate_code(self, prompt: str, model: str = "qwen-plus") -> str:
        """
        调用大模型生成代码，并自动提取 Markdown 代码块中的内容。
        
        Args:
            prompt: 提示词
            model: 模型名称
            
        Returns:
            str: 提取出的纯代码字符串
        """
        print(f"  [LLM-Code] Calling Qwen ({model})...")
        text = self.generate_text(prompt, model)
        return self._extract_code(text)

    def _extract_code(self, text: str) -> str:
        """
        辅助函数：从 LLM 返回的 Markdown 文本中提取代码块。
        支持 ```python ... ``` 或 ``` ... ``` 格式。
        """
        import re
        match = re.search(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
        code = match.group(1).strip() if match else text.strip()
        
        if 'if __name__ == "__main__":' in code:
            code = code.split('if __name__ == "__main__":')[0]
        elif "if __name__ == '__main__':" in code:
            code = code.split("if __name__ == '__main__':")[0]
            
        return code

    def get_embedding(self, text: str) -> List[float]:
        """
        获取文本的向量表示 (Embedding)，用于后续的相似度计算或新颖性检测。
        """
        try:
            response = self.client.embeddings.create(
                input=text,
                model="text-embedding-v1" 
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Embedding API Error: {e}")
            return [0.0] * 10 


class CodeRunner:
    """
    代码执行沙箱。
    负责在子进程中安全运行 Python 代码，捕获标准输出、标准错误和运行状态。
    """
    @staticmethod
    def run(code: str, input_data: str, timeout: float = 2.0) -> Tuple[str, str, str]:
        """
        运行 Python 代码片段。
        会自动包装代码，使其能够读取 stdin 并调用 solve() 函数。
        
        Args:
            code: 待运行的 Python 代码字符串
            input_data: 输入到 stdin 的数据
            timeout: 超时时间 (秒)
            
        Returns:
            Tuple[str, str, str]: (stdout, stderr, status)
            status 可能为 "OK", "RE" (Runtime Error), "TLE" (Time Limit Exceeded), "SysError"
        """
        
        wrapper = f"""
import sys
import traceback

# User Code Start
{code}
# User Code End

if __name__ == "__main__":
    try:
        input_str = sys.stdin.read().strip()
        if 'solve' in globals():
            result = solve(input_str)
            print(result)
        else:
            print("Error: No solve function found")
    except Exception:
        traceback.print_exc()
"""
        try:
            process = subprocess.Popen(
                [sys.executable, "-c", wrapper],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=input_data, timeout=timeout)
            
            if process.returncode != 0:
                return stdout.strip(), stderr.strip(), "RE" 
            return stdout.strip(), stderr.strip(), "OK"
            
        except subprocess.TimeoutExpired:
            process.kill()
            return "", "Timeout", "TLE"
        except Exception as e:
            return "", str(e), "SysError"

    @staticmethod
    def run_validator(code: str, input_data: str) -> bool:
        """
        运行验证器代码。
        验证器代码应包含 validate(input_str) -> bool 函数。
        
        Returns:
            bool: 数据是否合法 (True/False)
        """
        wrapper = f"""
import sys
# User Code
{code}
# End User Code

if __name__ == "__main__":
    try:
        input_str = sys.stdin.read().strip()
        if validate(input_str):
            print("VALID")
        else:
            print("INVALID")
    except:
        print("INVALID")
"""
        try:
            process = subprocess.Popen(
                [sys.executable, "-c", wrapper],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, _ = process.communicate(input=input_data, timeout=2.0)
            return stdout.strip() == "VALID"
        except:
            return False


class APESystem:
    """
    APE-System (Automated Problem Evaluation System) - Schema 增强版
    
    基于 Problem Schema 五元组 (I, C, O, V, T) 对编程题目进行多维度的自动化评估。
    包含四个核心评价步骤：
    1. 深度自洽性验证 (Schema-Constraint Validity)
    2. 鲁棒性测试 (Invariant-Based Hacker)
    3. 可解性与对齐度 (Solvability & Alignment)
    4. 结构新颖性 (Structural Novelty)
    """
    def __init__(self):
        self.llm = LLMClient()
        self.runner = CodeRunner()

    def evaluate(self, problem_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        主入口函数：对单个题目进行完整评估。
        
        Args:
            problem_json: 包含题目信息的字典，需包含 problem_text, std_code, test_cases, schema 等字段。
            
        Returns:
            Dict: 包含总分、各项指标得分、详细反馈和生成产物的评估报告。
        """
        print(f" Starting APE-System (Schema-Enhanced) Evaluation...")
        
        problem_text = problem_json.get("problem_text", "")
        # 兼容不同来源的字段名
        std_code = problem_json.get("std_code") or problem_json.get("standard_code") or ""
        test_cases = problem_json.get("test_cases", [])
        
        # 自动适配 Schema 格式
        raw_schema = problem_json.get("schema", {})
        schema = self._normalize_schema(raw_schema)
        
        if not schema:
            print("[Warning] No Schema found. Falling back to basic evaluation or failing.")
            return {"error": "Missing Schema definition in problem.json. Please add 'schema' field."}

        artifacts = {}

        # --- Step 1: Schema-Constraint Validity (Deep Self-Consistency) ---
        print("\n[Step 1] Schema-Constraint Validity...")
        data_compliance_score, step1_artifacts = self._step1_validity(schema, std_code, test_cases)
        artifacts.update(step1_artifacts)
        
        if data_compliance_score < 1.0:
             print(f"[Warning] Data Compliance is {data_compliance_score*100}%. Critical Failure.")

        # --- Step 2: Invariant-Based Hacker (Robustness) ---
        print("\n[Step 2] Invariant-Based Hacker (Robustness)...")
        logic_kill_rate, step2_artifacts = self._step2_robustness(schema, std_code, test_cases, problem_text)
        artifacts.update(step2_artifacts)

        # --- Step 3: Solvability & Alignment ---
        print("\n[Step 3] Solvability & Alignment...")
        solvability, alignment_score, step3_artifacts = self._step3_alignment(problem_text, schema, test_cases)
        artifacts.update(step3_artifacts)

        # --- Step 4: Structural Novelty ---
        print("\n[Step 4] Structural Novelty...")
        novelty_score, step4_artifacts = self._step4_novelty(schema)
        artifacts.update(step4_artifacts)

        # --- Final Score Calculation ---
        # Weights: Logic Kill Rate (40%), Solvability (20%), Alignment (20%), Novelty (20%)
        # Precondition: Data Compliance MUST be 100%
        
        if data_compliance_score < 1.0:
            total_score = 0.0
            is_qualified = False
            feedback = "Critical Error: Test data does not comply with Schema constraints."
        else:
            total_score = (
                logic_kill_rate * 40 +
                solvability * 20 +
                alignment_score * 20 +
                novelty_score * 20
            )
            is_qualified = (total_score >= 80)
            feedback = self._generate_feedback(data_compliance_score, logic_kill_rate, solvability, alignment_score, novelty_score)

        return {
            "total_score": round(total_score, 1),
            "is_qualified": is_qualified,
            "metrics": {
                "data_compliance": data_compliance_score,
                "logic_kill_rate": logic_kill_rate,
                "solvability": solvability,
                "alignment_score": alignment_score,
                "structural_novelty": novelty_score
            },
            "feedback": feedback,
            "generated_artifacts": artifacts
        }

    def _normalize_schema(self, raw_schema: Dict) -> Dict:
        """
        Schema 格式标准化适配器。
        将不同来源 (如 Gemini 母题库、Qwen ICPC 提取器) 的 Schema 键名统一转换为标准五元组 (I, C, O, V, T)。
        """
        # 自动处理字符串类型的 Schema (可能是 JSON 字符串)
        if isinstance(raw_schema, str):
            try:
                # 去除可能的 Markdown 标记
                clean_json = raw_schema.replace("```json", "").replace("```", "").strip()
                raw_schema = json.loads(clean_json)
            except Exception as e:
                # 打印前 50 个字符用于调试
                # print(f"[Warning] Failed to parse schema string: {str(e)}. Content: {raw_schema[:50]}...")
                return {}

        normalized = {}
        
        # 映射表：标准键 -> 可能的别名列表
        key_mapping = {
            "I": ["I", "Input Structure", "input_structure", "input"],
            "C": ["C", "Core Constraint", "Core Constraints", "core_constraints", "constraints"],
            "O": ["O", "Objective Function", "Objective", "objective"],
            "V": ["V", "Algorithmic Invariant", "Invariant", "invariant"],
            "T": ["T", "Transformable Parameters", "Transform Space", "transform_params"]
        }
        
        for std_key, aliases in key_mapping.items():
            for alias in aliases:
                if alias in raw_schema:
                    normalized[std_key] = raw_schema[alias]
                    break
            # 如果没找到，尝试保留空值或默认值
            if std_key not in normalized:
                normalized[std_key] = None
                
        # 简单校验：如果 I 和 C 都是空的，说明可能转换失败
        if not normalized["I"] and not normalized["C"]:
            return {}
            
        return normalized

    def _step1_validity(self, schema: Dict, std_code: str, test_cases: List[Dict]) -> Tuple[float, Dict]:
        """
        Step 1: 深度自洽性验证 (Schema-Constraint Validity)。
        利用 LLM 根据 Schema 中的 I (Input) 和 C (Constraints) 自动生成数据校验器，
        检查所有测试用例是否符合定义的约束。
        """
        input_struct = schema.get("I", {})
        constraints = schema.get("C", [])
        
        # 1. Generate Auto-Validator
        prompt = f"""
        Please generate a Python function `validate(input_str) -> bool` based on the following Input Structure and Constraints.
        The function should return True if the input strictly follows the format and constraints, False otherwise.
        
        Input Structure (I): {json.dumps(input_struct)}
        Constraints (C): {json.dumps(constraints)}
        
        The input `input_str` is the raw stdin string.
        """
        validator_code = self.llm.generate_code(prompt)
        
        # 2. Validate Data
        valid_count = 0
        total_cases = len(test_cases)
        
        for tc in test_cases:
            inp = tc["input"]
            is_valid = self.runner.run_validator(validator_code, inp)
            
            if is_valid:
                # 3. Run Standard Code on valid data
                std_out, _, status = self.runner.run(std_code, inp)
                if status == "OK":
                    valid_count += 1
                else:
                    print(f"  [Fail] Std code failed on valid input: {inp[:20]}...")
            else:
                print(f"  [Fail] Data Invalid: {inp[:20]}...")

        score = valid_count / total_cases if total_cases > 0 else 0.0
        return score, {"validator_code": validator_code}

    def _step2_robustness(self, schema: Dict, std_code: str, test_cases: List[Dict], problem_text: str) -> Tuple[float, Dict]:
        """
        Step 2: 鲁棒性测试 (Invariant-Based Hacker)。
        基于 Schema 中的 V (Invariant) 生成针对性的错误解法 (Logic Mutation)，
        以及随机的语法变异 (Syntax Mutation)，检测测试用例是否能有效拦截这些错误代码。
        """
        invariant = schema.get("V", "Unknown")
        mutants = []
        failed_mutants = []
        killed_count = 0
        
        # 1. Logic Mutation (Based on V)
        logic_prompt = f"""
        The intended algorithm for this problem is: {invariant}.
        Please generate a Python solution that uses a DIFFERENT, INCORRECT algorithm (e.g., Greedy instead of DP, or BFS instead of Dijkstra) that might pass weak test cases.
        The code must have a `solve(input_str)` function.
        Problem: {problem_text}
        """
        logic_mutant = self.llm.generate_code(logic_prompt)
        mutants.append(("Logic_Mutant", logic_mutant))
        
        # 2. Syntax Mutation (Random bugs)
        syntax_prompt = f"""
        Please take the following correct code and introduce a subtle bug (e.g., off-by-one, > instead of >=, int overflow).
        Correct Code:
        {std_code}
        """
        syntax_mutant = self.llm.generate_code(syntax_prompt)
        mutants.append(("Syntax_Mutant", syntax_mutant))
        
        # 3. Attack
        for name, code in mutants:
            is_killed = False
            for tc in test_cases:
                inp = tc["input"]
                exp = tc["output"]
                
                out, _, status = self.runner.run(code, inp)
                
                # Killed if: Crashes OR Output is different from Expected
                if status != "OK" or out != exp:
                    is_killed = True
                    break
            
            if is_killed:
                killed_count += 1
            else:
                failed_mutants.append(name)
                print(f"  [Alert] {name} survived all test cases!")

        score = killed_count / len(mutants) if mutants else 0.0
        return score, {"failed_mutants": failed_mutants}

    def _step3_alignment(self, problem_text: str, schema: Dict, test_cases: List[Dict]) -> Tuple[float, float, Dict]:
        """
        Step 3: 可解性与对齐度 (Solvability & Alignment)。
        模拟学生 (SimStudent) 仅根据题面解题，验证题目是否可解，
        并检查 AI 生成的解法是否符合 Schema 中预期的算法不变量 (V)。
        """

        invariant = schema.get("V", "Unknown")
        
        # 1. SimStudent Solve
        student_prompt = f"""You are a student. Solve this problem in Python.
        Please wrap your solution in a function `def solve(input_str: str) -> str:` that takes the input string and returns the output string.
        Problem: {problem_text}"""
        student_code = self.llm.generate_code(student_prompt)
        
        # Check Solvability
        passed = True
        for tc in test_cases:
            out, _, status = self.runner.run(student_code, tc["input"])
            if status != "OK" or out != tc["output"]:
                passed = False
                break
        solvability = 1.0 if passed else 0.0
        
        # 2. Alignment Check
        alignment_prompt = f"""
        The intended algorithm (Invariant) is: {invariant}.
        Here is a student's solution:
        {student_code}
        
        Does the student's solution use the intended algorithm? 
        Return a score from 0.0 to 1.0. Only return the number.
        """
        align_resp = self.llm.generate_text(alignment_prompt)
        try:
            import re
            match = re.search(r"(\d+(\.\d+)?)", align_resp)
            alignment_score = float(match.group(1)) if match else 0.5
        except:
            alignment_score = 0.5
            
        return solvability, alignment_score, {"sim_student_code": student_code}

    def _step4_novelty(self, schema: Dict) -> Tuple[float, Dict]:
        """
        Step 4: 结构新颖性 (Structural Novelty)。
        尝试加载母题库 (schemas_readable.json)，计算当前 Schema 与母题库中最近邻的距离。
        如果找不到母题库，回退到基于复杂度的启发式评分。
        """
        import os
        import json
        
        # 1. 尝试定位母题库文件
        # 假设相对路径: ../母题代码/output/schemas_readable.json
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(base_dir, "母题代码", "output", "schemas_readable.json")
        
        mother_db = []
        if os.path.exists(db_path):
            try:
                with open(db_path, "r", encoding="utf-8") as f:
                    mother_db = json.load(f)
            except Exception as e:
                print(f"  [Warning] Failed to load Mother DB: {e}")
        else:
            print(f"  [Warning] Mother DB not found at {db_path}. Using heuristic mode.")

        # 2. 如果没有母题库，使用启发式算法 (Heuristic Fallback)
        if not mother_db:
            constraints = schema.get("C", [])
            input_struct = schema.get("I", {})
            complexity = len(constraints) * 0.1
            if isinstance(input_struct, dict) and input_struct.get("type") in ["graph", "tree"]:
                complexity += 0.3
            return min(0.9, 0.2 + complexity), {"mode": "heuristic"}

        # 3. 基于母题库的相似度计算 (Simple Text Similarity)
        # 比较当前题目的 Invariant (V) 与母题库中所有题目的 Invariant
        curr_v = str(schema.get("V", "")).lower()
        max_sim = 0.0
        most_similar_title = ""
        
        for item in mother_db:
            # 适配母题库的结构 (item["schema"]["Algorithmic Invariant"])
            db_schema = self._normalize_schema(item.get("schema", {}))
            db_v = str(db_schema.get("V", "")).lower()
            
            if not curr_v or not db_v:
                continue
                
            # 简单的 Jaccard 相似度 (基于单词集合)
            set1 = set(curr_v.split())
            set2 = set(db_v.split())
            intersection = len(set1 & set2)
            union = len(set1 | set2)
            sim = intersection / union if union > 0 else 0.0
            
            if sim > max_sim:
                max_sim = sim
                most_similar_title = item.get("title", "Unknown")

        # 新颖性 = 1 - 最大相似度
        # 如果相似度很高 (max_sim -> 1.0)，说明是换皮题，新颖性低
        novelty_score = 1.0 - max_sim
        
        # 修正分数范围，避免极端
        novelty_score = max(0.1, min(0.95, novelty_score))

        return novelty_score, {
            "mode": "db_match", 
            "most_similar_problem": most_similar_title, 
            "max_similarity": round(max_sim, 2)
        }

    def _generate_feedback(self, compliance, kill_rate, solvability, alignment, novelty) -> str:
        """
        根据各项指标生成最终的文字反馈报告。
        """
        msgs = []
        if compliance < 1.0:
            return "REJECT: Data does not match Schema."
        if kill_rate < 0.5:
            msgs.append("Weak Data: Failed to kill wrong solutions.")
        if solvability < 1.0:
            msgs.append("Unsolvable: AI could not solve it.")
        if alignment < 0.7:
            msgs.append("Misaligned: AI solved it but used a different algorithm (Constraints too loose?).")
        if novelty < 0.3:
            msgs.append("Low Novelty: Looks like a standard template problem.")
            
        if not msgs:
            return "Excellent Problem! High quality and structurally sound."
        return " | ".join(msgs)

# ==========================================
# Example Usage
# ==========================================
if __name__ == "__main__":
    import argparse
    import os

    # 默认读取当前目录下的 problem.json
    default_input_file = os.path.join(os.path.dirname(__file__), "problem.json")

    parser = argparse.ArgumentParser(description="APE System (Schema-Enhanced)")
    parser.add_argument("input_file", nargs="?", default=default_input_file, help="Path to the problem JSON file")
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found.")
        sys.exit(1)

    try:
        with open(args.input_file, "r", encoding="utf-8") as f:
            input_json = json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        sys.exit(1)
    
    evaluator = APESystem()
    report = evaluator.evaluate(input_json)
    
    # Generate output filename
    # Identify the directory of the input file to save the report in the same location
    input_dir = os.path.dirname(os.path.abspath(args.input_file))
    base_name = os.path.splitext(os.path.basename(args.input_file))[0]
    output_file = os.path.join(input_dir, f"{base_name}_report.json")
    
    # Save report to JSON file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    print(f"\n[Success] Report saved to: {os.path.abspath(output_file)}")
