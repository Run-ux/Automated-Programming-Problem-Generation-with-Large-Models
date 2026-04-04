# 四元组抽取 - 运行说明

## 前置条件

```powershell
$env:DASHSCOPE_API_KEY = "your-api-key-here"
$env:QWEN_EXTRACT_MODEL = "qwen-max"
$env:QWEN_NORMALIZE_MODEL = "qwen-flash"
$env:QWEN_EMBEDDING_MODEL = "text-embedding-v3"
```

也可以直接执行 [scripts/set_qwen_env.ps1](/D:/AutoProblemGen/四元组抽取/scripts/set_qwen_env.ps1)：

```powershell
.\scripts\set_qwen_env.ps1 -ApiKey "your-api-key-here"
.\scripts\set_qwen_env.ps1 -ApiKey "your-api-key-here" -PersistUser
```

## 输入格式

`extract.py` 只接受新的单题 schema JSON，或包含多个这类 JSON 的目录。推荐输入目录：

`D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs`

单题样例：

`D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs\16_codeforces_1399_e1_weights_division_easy_version.json`

## 抽取

单题：

```powershell
cd D:\AutoProblemGen\四元组抽取
python extract.py --input D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs\16_codeforces_1399_e1_weights_division_easy_version.json --output output\single\ --resume
```

目录批量：

```powershell
python extract.py --input D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs --output output\batch\ --resume
```

## 归一化

```powershell
python normalize.py --input output\batch\raw\ --output output\batch\normalized\ --embedding-threshold 0.85
```

`normalized\` 目录中的文件就是最终结果。

## 验证

```powershell
python verify_prompts_structure.py
```

## 输出目录

```text
output/
├── single/
│   ├── raw/
│   └── logs/
└── batch/
    ├── raw/
    ├── normalized/
    ├── label_registry/
    └── logs/
```
