import json
import re

def parse_schema(schema_str):
    if not schema_str:
        return ""
    # 去除包裹的 ```json ... ``` 标记
    schema_str = schema_str.strip()
    if schema_str.startswith("```json"):
        schema_str = schema_str[7:]
    if schema_str.endswith("```"):
        schema_str = schema_str[:-3]
    schema_str = schema_str.strip()
    # 尝试解析为 dict，否则原样返回
    try:
        schema = json.loads(schema_str)
        return schema
    except Exception:
        # 兼容部分schema为字符串的情况
        return schema_str

def main():
    with open("schemas.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    output = []
    for item in data:
        title = item.get("title", "")
        slug = item.get("slug", "")
        schema_raw = item.get("schema", "")
        schema = parse_schema(schema_raw)
        output.append({
            "title": title,
            "slug": slug,
            "schema": schema
        })

    with open("schemas_readable.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()