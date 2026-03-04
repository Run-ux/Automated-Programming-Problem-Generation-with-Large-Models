# 自动生成题目 (Automatic Problem Generation)

本模块实现了基于 **Schema 五元组 (I, C, O, V, T)** 的题目自动生成流程。

## 文件结构

- `config.py`: 配置文件，包括 API Key (请填入您的 DashScope Key) 和路径配置。
- `logic_mutator.py`: **逻辑变异器**，负责根据 `Transform Space` 生成新的数学骨架。
- `story_engine.py`: **故事引擎**，负责选择主题（魔法/科幻/日常等）并生成 Prompt。
- `llm_client.py`: 使用阿里云 Qwen API 生成最终的题面 Markdown。
- `main.py`: 主程序，串联上述模块。

## 运行方法

1.  **安装依赖**:
    ```bash
    pip install -r requirements.txt
    ```

    (注：如果您没有安装 `dashscope`，请先安装: `pip install dashscope`)

2.  **配置 API Key**:
    - 在 `config.py` 中填入您的阿里云 API Key。
    - 或者设置环境变量 `DASHSCOPE_API_KEY`。

3.  **运行**:
    ```bash
    python main.py
    ```

## 生成流程

1.  **加载**: 读取 `../finiteness_verification/output/pilot/voted` 目录下的 JSON Schema。
2.  **变异**: `LogicMutator` 随机选择新的参数、目标函数和约束条件。
3.  **包装**: `StoryEngine` 随机选择一个故事背景，将数学概念映射为故事元素。
4.  **生成**: 调用大模型生成 Markdown 格式的题目。
5.  **保存**: 结果保存在 `output` 文件夹中。

## 示例输出

生成的文件名格式为 `{ProblemID}_generated_{Timestamp}_v{Variant}_{Theme}.md`。
