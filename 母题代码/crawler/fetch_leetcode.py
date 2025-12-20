from crawler.leetcode_crawler import get_problem_list, get_problem_detail
import json

def main():
    problems = get_problem_list()
    result = []
    for p in problems[:1000]:  # 可调整数量
        slug = p["stat"]["question__title_slug"]
        title = p["stat"]["question__title"]
        print(f"抓取：{title}")
        text = get_problem_detail(slug)
        result.append({"slug": slug, "title": title, "content": text})
    with open("problems_raw.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
