# LeetCode Problem Schema Extractor

本项目用于自动爬取力扣（LeetCode）题目，并将每道题目结构化为“Problem Schema 五元组”并存储。

## 目录结构

- main.py                # 主入口，控制流程
- leetcode_crawler.py    # 爬取力扣题目
- schema_parser.py       # 解析题目为五元组（支持 Gemini）
- storage.py             # 存储五元组（如JSON）
- config.py              # 配置文件（如cookies、headers、API Key等）
- requirements.txt       # 依赖库

## 使用方法

1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
2. 配置 `config.py`，填写你的 Gemini API Key。
3. 运行主程序：
   ```bash
   python main.py
   ```

## 五元组结构示例

```json
Schema = {
  Input Structure,
  Core Constraint,
  Objective Function,
  Algorithmic Invariant,
  Transformable Parameters
}
```

## 注意事项
- 若需大规模爬取，建议做好反爬措施。
- LLM解析部分需消耗 Gemini API 额度。
