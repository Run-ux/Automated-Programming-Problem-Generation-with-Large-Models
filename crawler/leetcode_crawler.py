import requests
from bs4 import BeautifulSoup
from leetcode_schema_extractor.Gemini.config import LEETCODE_URL, HEADERS

def get_problem_list():
    url = f"{LEETCODE_URL}/api/problems/all/"
    resp = requests.get(url, headers=HEADERS, verify=False)
    resp.raise_for_status()
    return resp.json()["stat_status_pairs"]

def get_problem_detail(slug):
    url = f"https://leetcode.cn/graphql/"
    headers = {
        "Content-Type": "application/json",
        "Referer": f"https://leetcode.cn/problems/{slug}/",
        "User-Agent": HEADERS.get("User-Agent", "Mozilla/5.0")
    }
    data = {
        "operationName": "questionData",
        "variables": {"titleSlug": slug},
        "query": """
        query questionData($titleSlug: String!) {
          question(titleSlug: $titleSlug) {
            translatedTitle
            translatedContent
            difficulty
            questionFrontendId
          }
        }
        """
    }
    resp = requests.post(url, json=data, headers=headers, verify=False)
    if resp.status_code == 200:
        content = resp.json()["data"]["question"]["translatedContent"]
        if content:
            soup = BeautifulSoup(content, "html.parser")
            return soup.get_text("\n", strip=True)
    return ""
