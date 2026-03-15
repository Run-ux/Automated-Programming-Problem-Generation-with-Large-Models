# 生成题面 Codex

该目录实现了“基于 Problem Schema 生成题面”的完整流程，输入为 `finiteness_verification/output/pilot/voted/*.json`，输出为：

- `output/*.md`：最终 Markdown 题面
- `artifacts/*.json`：中间结构化产物，包含变体规划和模型返回结果

## 流程

1. 读取上游 Schema 五元组与 `transform_space`
2. 通过 `VariantPlanner` 实例化题目变体
3. 生成结构化 Prompt，请模型返回严格 JSON 题面
4. 将 JSON 渲染为标准 OJ 风格 Markdown
5. 保存 Markdown 和中间产物

## 运行

安装依赖：

```bash
pip install -r requirements.txt
```

配置环境变量：

```bash
set DASHSCOPE_API_KEY=your_key
```

真实生成：

```bash
python main.py --problem-ids CF25E CF360C --variants 2
```

如果输入 schema 只有前四维，`main.py` 会先自动调用 `finiteness_verification` 的 transform 抽取第五维 `transform_space`，把补全后的文件缓存到 `prepared_schemas/`，再继续生成题面。

可选参数：

- `--theme cyber_city|arcane_lab|interstellar_logistics|campus_ops`
- `--source-dir <schema目录>`
- `--output-dir <md输出目录>`
- `--artifact-dir <json输出目录>`
- `--model <模型名>`
- `--seed <随机种子>`
- `--skip-transform-enrich`

## 说明

- 生成时要求模型输出 JSON，对题面结构更稳定，便于后续接测试数据和评测模块。
