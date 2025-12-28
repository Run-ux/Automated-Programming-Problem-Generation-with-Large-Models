# ICPC PDF 题面提取 + Schema 五元组提取

本工具完成两步：
1) 从 ICPC 世界赛 PDF 题集提取每道题文字，并标准化为 `Title/Description/Input/Output/Constraints`。
2) 调用阿里千问（Qwen/DashScope）API，对每题提取 Problem Schema 五元组，并保存 JSON。

## 安装

在本工作区：

```powershell
D:/ICPC题目提取schema/.venv/Scripts/python.exe -m pip install -r requirements.txt
```

## 运行

### 推荐：直接运行（不使用命令行参数）

项目默认入口会从主函数读取配置并执行：PDF 提取 → 标准化 → schema 提取。

```powershell
D:/ICPC题目提取schema/.venv/Scripts/python.exe -m icpc_schema_extractor
```

你可以在 [icpc_schema_extractor/__main__.py](icpc_schema_extractor/__main__.py) 中修改：
- `pdf_path`（PDF 路径）
- `out_root`（输出目录）
- `schema_def_path`（五元组定义文件）
- `model`（千问模型名）

baseurl 与 key 建议写在 `.env`（见下文）。

### （可选）仍然使用子命令

```powershell
D:/ICPC题目提取schema/.venv/Scripts/python.exe -m icpc_schema_extractor \
  extract \
  --pdf "path/to/icpc.pdf" \
  --out "out"
```

输出：
- `out/problems/A.md`、`out/problems/B.md` ...
- `out/problems/index.json`

### 2) 在(1)基础上做 schema 提取

推荐方式：使用 `.env`（项目已自动加载）。

1) 复制 [.env.example](.env.example) 为 `.env`
2) 填写：
- `QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`
- `DASHSCOPE_API_KEY=你的key`

也可用环境变量方式设置（PowerShell）：

```powershell
$env:QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:DASHSCOPE_API_KEY = "你的key"
```

```powershell
D:/ICPC题目提取schema/.venv/Scripts/python.exe -m icpc_schema_extractor \
  schema \
  --problems "out/problems" \
  --schema-def "schema五元组定义.md" \
  --out "out"
```

输出：
- `out/schemas/A.json`、`out/schemas/B.json` ...
- `out/schemas/index.json`

## 注意

- PDF 分题依赖标题识别正则，可能需要根据具体题集格式调整（见 CLI 参数 `--problem-regex`）。
- schema 提取需要模型输出 JSON，本工具会做 JSON 校验与失败重试。
