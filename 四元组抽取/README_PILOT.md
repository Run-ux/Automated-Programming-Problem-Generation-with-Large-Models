# 四元组抽取 - 运行说明

## 前置条件

```powershell
$env:DASHSCOPE_API_KEY = "your-api-key-here"
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
python extract.py --input D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs\16_codeforces_1399_e1_weights_division_easy_version.json --output output\single\ --rounds 3 --resume
```

目录批量：

```powershell
python extract.py --input D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs --output output\batch\ --rounds 3 --resume
```

## 归一化与投票

```powershell
python normalize.py --input output\batch\raw\ --output output\batch\normalized\ --embedding-threshold 0.85
python vote.py --input output\batch\normalized\ --output output\batch\voted\
```

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
    ├── voted/
    └── logs/
```
