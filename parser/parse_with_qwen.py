import os
import time
import json
import requests

# Qwen API 配置
QWEN_API_KEY = "sk-ac54a665d5ed43b48a5f1a414d88245a"
QWEN_MODEL = "qwen-plus"  # 可选 qwen-turbo, qwen-plus, qwen-max, qwen-max-longcontext
QWEN_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

def parse_to_schema_qwen(problem_text):
    prompt = f"""
你是算法题目结构化专家。阅读解析要求## 母题：Problem Schema / Problem Template

一个合格的母题，至少应包含：

1. **问题核心结构**
   - 输入对象类型（数组 / 图 / 字符串 / 区间）
   - 目标函数（最小化 / 计数 / 判定）
2. **解法不变量**
   - 双指针推进规则
   - 状态单调性
   - 可证明的贪心条件
3. **可变参数位（Slots）**
   
   - 约束条件
   - 数据规模
   - 输入输出形式
   - 是否多组数据
   - 是否在线 / 离线
   
4. **一个最细条目，对应的最优解法是否在竞赛语境下是“几乎唯一的”**
- 如果存在 3–4 种完全不同的主流最优解
   
- 那它更适合作为「中间层母题」
   
- 而不是“叶子节点母题”


## 改编：规则化变换

显式设计一组 **题目变换算子**，例如：

- 输入维度变换：1D → 2D → 环形
- 目标变换：最大 → 最小 → 计数
- 约束反转：≤K → ≥K
- 数据流化：一次性输入 → 在线查询
- 隐藏条件：显性单调 → 隐式单调

然后：

> LLM 的角色是「在算子约束下生成自然语言和细节」

而不是自由发挥。

------

## 考纲

1. 叶子节点必须能 **直接生成题目**
2. 中间节点只是 **分类与约束**
3. 算法在这里的作用是：限定可行解空间、限定问题不变量、限定复杂度边界
4. 第一层：问题结构维度。例如：顺序结构问题（Sequence）、区间结构问题（Interval）、图结构问题（Graph）、状态演化问题（State Transition）、几何与空间问题（Geometry / Spatial）。**原因：**同一算法在不同结构下完全不同，这层决定输入、约束和题面形式。
5. 第二层：核心约束/不变量。这一层开始体现“算法本质”。例如在 Sequence 下：单调性约束、局部最优可合并、双端可推进、前后依赖分离
6. 第三层：经典解法范式（算法标签）。如：双指针、单调栈、滑动窗口、前缀和、贪心、DP。**注意：**一个节点可以有多个算法标签、需要区分「主解法 / 辅助解法」。
7. 第四层：Problem Schema（叶子节点）。真正的母题。

------

## Problem Schema = 五元组

```
Schema = {
  'Input Structure',
  'Core Constraint',
  'Objective Function',
  'Algorithmic Invariant',
  'Transformable Parameters'
}
```

### 1.Input Structure（输入结构）

**必须形式化，而不是自然语言。**

示例：

- 一维数组 A[1..n]
- 有序数组 / 可重复
- 非负整数

### 2.Core Constraint（核心约束）

这是决定“为什么需要这个算法”的部分。

例如：

- 区间可通过左右边界唯一确定
- 局部信息不足，需要全局约束
- 状态单调演化

### 3. Objective Function（目标函数）

明确在求什么：

- 最大 / 最小
- 是否存在
- 计数
- 构造方案

**非常重要：**

> 同一个 Input + Constraint，不同 Objective 就是不同题型。

### 4.Algorithmic Invariant（算法不变量）

例如双指针：

- 左指针左侧状态已确定
- 右指针右侧状态已确定
- 指针移动不会破坏最优性

### 5. Transformable Parameters（可变参数）

这是后续“生成新题”的抓手。

至少包含：

- n 的数量级
- 值域
- 是否有序
- 是否循环
- 是否多组输入
- 是否在线

## 一个完整示例：双指针·接雨水 Schema

------

Schema 名称

**双端边界约束下的区间容量计算**

------

### 1. Input Structure

- 给定长度为 n 的数组 H[1..n]
- H[i] ≥ 0
- 表示柱状高度

------

### 2.Core Constraint

- 每个位置的可贡献值由其左右最大值的最小者决定
- 左右约束相互独立，但需全局一致

------

### 3. Objective Function

- 计算所有位置可累计的容量总和

------

### 4. Algorithmic Invariant

- 维护左右指针 L, R
- 若 maxLeft ≤ maxRight，则 L 的贡献可确定
- 每次移动一个指针，不影响已确定区域的正确性

------

### 5.Transformable Parameters

- H 是否允许负值（变形题）
- 是否二维（2D 接雨水）
- 是否在线输入
- 是否要求输出每个位置的容量
- 是否加入删除 / 修改操作

------

### 6.可衍生题型

- 接雨水
- 最大盛水容器（目标函数变化）
- 有约束的容量分配问题
- 区间最小瓶颈累积
请将以下力扣题目内容，按照如下五元组结构输出（用JSON格式）：\nSchema = {{\n  Input Structure,\n  Core Constraint,\n  Objective Function,\n  Algorithmic Invariant,\n  Transformable Parameters\n}}\n题目内容如下：\n{problem_text}\n"""
    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": QWEN_MODEL,
        "input": {
            "prompt": prompt
        }
    }
    max_retries = 3
    for i in range(max_retries):
        try:
            resp = requests.post(QWEN_API_URL, headers=headers, json=data, timeout=60)
            if resp.status_code == 200:
                result = resp.json()
                if "output" in result:
                    return result["output"]["text"]
                elif "choices" in result and result["choices"]:
                    return result["choices"][0]["message"]["content"]
                else:
                    return str(result)
            else:
                print(f"  ❌ Qwen API 错误: {resp.status_code} {resp.text[:100]}")
                if resp.status_code == 429:
                    print("  ⏳ 触发限流，强制休眠 10 秒...")
                    time.sleep(10)
                else:
                    time.sleep(3)
        except Exception as e:
            print(f"  ⚠️ 网络/未知错误: {e}")
            time.sleep(5)
    return None

def main():
    try:
        with open("problems_raw.json", "r", encoding="utf-8") as f:
            problems = json.load(f)
    except Exception:
        print("找不到 problems_raw.json")
        return

    total = len(problems)
    print(f"🚀 Qwen 开始处理，共 {total} 题")
    print(f"🤖 使用模型: {QWEN_MODEL}")

    # 边解析边写入
    with open("schemas.json", "w", encoding="utf-8") as f:
        f.write('[\n')
        first = True
        for i, p in enumerate(problems):
            print(f"解析 ({i+1}/{total}): {p['title']}")
            result = parse_to_schema_qwen(p["content"])
            item = {"slug": p["slug"], "title": p["title"], "schema": result}
            if not first:
                f.write(',\n')
            else:
                first = False
            json.dump(item, f, ensure_ascii=False, indent=2)
            f.flush()
            if result:
                print("  ✅ 成功")
                time.sleep(2)
            else:
                print("  ❌ 失败，跳过")
        f.write('\n]')
    print(f"💾 已边解析边保存所有数据到 schemas.json")

if __name__ == "__main__":
    main()
