from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


DATA_DIR = Path(r"D:\AutoProblemGen\爬取题目\datasets\Imandra_code_contests\data")
OUTPUT_DIR = Path(r"D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs")
MAX_SELECTED = 24
MIN_SELECTED = 18
ENGLISH_STOPWORDS = {
    "the",
    "and",
    "you",
    "are",
    "given",
    "input",
    "output",
    "print",
    "find",
    "number",
    "integer",
    "integers",
    "array",
    "string",
    "graph",
    "tree",
    "minimum",
    "maximum",
    "possible",
    "each",
}

SOURCE_MAP = {
    0: "UNKNOWN_SOURCE",
    1: "CODECHEF",
    2: "CODEFORCES",
    3: "HACKEREARTH",
    4: "CODEJAM",
    5: "ATCODER",
    6: "AIZU",
}

DIFFICULTY_MAP = {
    0: "UNKNOWN_DIFFICULTY",
    1: "EASY",
    2: "MEDIUM",
    3: "HARD",
    4: "HARDER",
    5: "HARDEST",
    6: "EXTERNAL",
    7: "A",
    8: "B",
    9: "C",
    10: "D",
    11: "E",
    12: "F",
    13: "G",
    14: "H",
    15: "I",
    16: "J",
    17: "K",
    18: "L",
    19: "M",
    20: "N",
    21: "O",
    22: "P",
    23: "Q",
    24: "R",
    25: "S",
    26: "T",
    27: "U",
    28: "V",
}

TARGET_FEATURES = {
    "source:CODEFORCES",
    "source:ATCODER",
    "source:AIZU",
    "source:CODECHEF",
    "source:HACKEREARTH",
    "difficulty:unknown",
    "difficulty:easy",
    "difficulty:medium",
    "difficulty:hard_plus",
    "difficulty:external",
    "difficulty:atcoder_low",
    "difficulty:atcoder_mid",
    "difficulty:atcoder_high",
    "rating:cf_low",
    "rating:cf_mid",
    "rating:cf_high",
    "tag:implementation",
    "tag:math",
    "tag:greedy",
    "tag:dp",
    "tag:data_structures",
    "tag:constructive",
    "tag:graphs",
    "tag:trees",
    "tag:strings",
    "tag:geometry",
    "tag:binary_search",
    "tag:number_theory",
    "objective:count",
    "objective:decision",
    "objective:optimize",
    "objective:construct",
    "structure:array",
    "structure:graph",
    "structure:tree",
    "structure:string",
    "structure:grid",
    "structure:geometry",
    "special:translated",
    "special:non_stdio",
    "special:untagged",
}

TAG_RULES = {
    "implementation": {"implementation"},
    "math": {"math"},
    "greedy": {"greedy"},
    "dp": {"dp"},
    "data_structures": {"data structures"},
    "constructive": {"constructive algorithms"},
    "graphs": {"graphs", "dfs and similar", "shortest paths", "dsu", "flows", "graph matchings"},
    "trees": {"trees"},
    "strings": {"strings", "hashing", "suffix array", "expression parsing"},
    "geometry": {"geometry"},
    "binary_search": {"binary search", "ternary search"},
    "number_theory": {"number theory"},
}

READ_COLUMNS = [
    "name",
    "description",
    "public_tests",
    "private_tests",
    "generated_tests",
    "source",
    "difficulty",
    "cf_contest_id",
    "cf_index",
    "cf_points",
    "cf_rating",
    "cf_tags",
    "is_description_translated",
    "untranslated_description",
    "time_limit",
    "memory_limit_bytes",
    "input_file",
    "output_file",
    "solutions",
    "incorrect_solutions",
]


def infer_split(file_name: str) -> str:
    if file_name.startswith("train-"):
        return "train"
    if file_name.startswith("test-"):
        return "test"
    if file_name.startswith("valid-"):
        return "valid"
    return "unknown"


def slugify(text: str, *, max_length: int = 48) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    if not slug:
        slug = "sample"
    return slug[:max_length].strip("_") or "sample"


def normalize_tags(tags: Any) -> list[str]:
    if not tags:
        return []
    normalized = []
    for tag in tags:
        if tag is None:
            continue
        value = str(tag).strip()
        if value:
            normalized.append(value)
    return normalized


def infer_tag_families(tags: list[str]) -> list[str]:
    tag_set = {tag.lower() for tag in tags}
    families = []
    for family, members in TAG_RULES.items():
        if tag_set & members:
            families.append(family)
    return families


def infer_difficulty_bucket(source_name: str, difficulty_name: str) -> str | None:
    if difficulty_name == "UNKNOWN_DIFFICULTY":
        return "unknown"
    if difficulty_name == "EASY":
        return "easy"
    if difficulty_name == "MEDIUM":
        return "medium"
    if difficulty_name in {"HARD", "HARDER", "HARDEST"}:
        return "hard_plus"
    if difficulty_name == "EXTERNAL":
        return "external"
    if source_name == "ATCODER" and difficulty_name in {"A", "B", "C"}:
        return "atcoder_low"
    if source_name == "ATCODER" and difficulty_name in {"D", "E", "F"}:
        return "atcoder_mid"
    if source_name == "ATCODER" and difficulty_name in {
        "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V"
    }:
        return "atcoder_high"
    return None


def infer_rating_bucket(source_name: str, cf_rating: Any) -> str | None:
    if source_name != "CODEFORCES":
        return None
    if cf_rating in (None, 0):
        return None
    try:
        rating = int(cf_rating)
    except (TypeError, ValueError):
        return None
    if rating <= 1200:
        return "cf_low"
    if rating <= 1800:
        return "cf_mid"
    return "cf_high"


def infer_structure_candidates(description: str, tags: list[str]) -> list[str]:
    text = description.lower()
    structures = []

    if re.search(r"\btree\b", text):
        structures.append("tree")
    if (
        re.search(r"\bgraph\b|\bvertex\b|\bedge\b|\bnodes?\b", text)
    ):
        structures.append("graph")
    if re.search(
        r"\bstring\b|\bsubstring\b|\bprefix\b|\bsuffix\b|\bpalindrome\b", text
    ):
        structures.append("string")
    if re.search(r"\bmatrix\b|\bgrid\b|\btable\b|\bcell\b", text):
        structures.append("grid")
    if re.search(
        r"\bpoint\b|\bcircle\b|\bpolygon\b|\bcoordinate\b|\bplane\b|\brectangle\b|\btriangle\b", text
    ):
        structures.append("geometry")
    if re.search(r"\barray\b|\bsequence\b|\bpermutation\b|\binteger\b|\bintegers\b|\bnumbers?\b", text):
        structures.append("array")

    deduped = []
    seen = set()
    for item in structures:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped


def infer_objective(description: str, tags: list[str]) -> str:
    text = description.lower()
    tag_set = {tag.lower() for tag in tags}
    if "constructive algorithms" in tag_set or re.search(r"\bconstruct\b|\boutput any\b|\bfind any\b|\bprint any\b", text):
        return "construct"
    if re.search(r"\bis it possible\b|\bwhether\b|\bdetermine if\b|\bpossible to\b", text):
        return "decision"
    if re.search(r"\bminimum\b|\bmaximum\b|\bminimize\b|\bmaximize\b|\bsmallest\b|\blargest\b|\bshortest\b|\blongest\b", text):
        return "optimize"
    if re.search(
        r"\bhow many\b|\bcount\b|\bfind the number of\b|\bdetermine the number of\b|\bnumber of ways\b|\bnumber of pairs\b|\bnumber of subsequences\b|\bnumber of permutations\b",
        text,
    ):
        return "count"
    return "unknown"


def derive_problem_id(source_name: str, row: dict[str, Any], row_uid: str) -> str:
    contest_id = row.get("cf_contest_id")
    index = row.get("cf_index")
    if source_name == "CODEFORCES" and contest_id and index:
        return f"CF{contest_id}{index}"
    return f"{source_name.lower()}_{row_uid}"


def derive_url(source_name: str, row: dict[str, Any]) -> str | None:
    contest_id = row.get("cf_contest_id")
    index = row.get("cf_index")
    if source_name == "CODEFORCES" and contest_id and index:
        return f"https://codeforces.com/contest/{contest_id}/problem/{index}"
    return None


def count_cases(test_block: Any) -> int:
    if not isinstance(test_block, dict):
        return 0
    inputs = test_block.get("input") or []
    outputs = test_block.get("output") or []
    return max(len(inputs), len(outputs))


def count_solutions(sol_block: Any) -> int:
    if not isinstance(sol_block, dict):
        return 0
    languages = sol_block.get("language") or []
    solutions = sol_block.get("solution") or []
    return max(len(languages), len(solutions))


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", text))


def english_score(text: str) -> int:
    lowered = text.lower()
    tokens = re.findall(r"[a-z]+", lowered)
    unique_tokens = set(tokens)
    score = sum(1 for word in ENGLISH_STOPWORDS if word in unique_tokens)
    if len(tokens) >= 80:
        score += 2
    elif len(tokens) >= 30:
        score += 1
    return score


def looks_english(title: str, description: str) -> tuple[bool, int]:
    merged = f"{title}\n{description}"
    if contains_cjk(merged):
        return False, 0
    score = english_score(merged)
    return score >= 6, score


def guess_language_name(code: str) -> str:
    stripped = code.lstrip()
    if "#include" in code or "using namespace std" in code or "std::" in code:
        return "cpp"
    if re.search(r"\bpublic class\b|\bstatic void main\b|\bSystem\.out\b", code):
        return "java"
    if re.search(r"^\s*def\s+\w+\(", code, re.MULTILINE) or "print(" in code:
        return "python"
    if re.search(r"\bfn main\(", code):
        return "rust"
    if re.search(r"\bpackage main\b|\bfmt\.", code):
        return "go"
    if re.search(r"\busing System\b|\bConsole\.Write", code):
        return "csharp"
    if re.search(r"\bscanf\(|\bprintf\(", code):
        return "c"
    if stripped.startswith("<?php") or "$" in code[:120]:
        return "php"
    return "unknown"


def pick_reference_solution(sol_block: Any) -> dict[str, Any] | None:
    if not isinstance(sol_block, dict):
        return None
    languages = sol_block.get("language") or []
    solutions = sol_block.get("solution") or []
    best = None
    for idx, code in enumerate(solutions):
        if not isinstance(code, str):
            continue
        normalized = code.strip()
        if len(normalized) < 40:
            continue
        line_count = normalized.count("\n") + 1
        candidate = {
            "language_id": languages[idx] if idx < len(languages) else None,
            "language_guess": guess_language_name(normalized),
            "code": normalized,
            "char_count": len(normalized),
            "line_count": line_count,
        }
        key = (candidate["line_count"], candidate["char_count"])
        if best is None or key < (best["line_count"], best["char_count"]):
            best = candidate
    return best


def load_previous_problem_ids() -> set[str]:
    manifest_path = OUTPUT_DIR / "manifest.json"
    if not manifest_path.exists():
        return set()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    return {
        str(item["problem_id"])
        for item in manifest.get("files", [])
        if isinstance(item, dict) and item.get("problem_id")
    }


def build_metadata() -> list[dict[str, Any]]:
    records = []
    for parquet_path in sorted(DATA_DIR.glob("*.parquet")):
        split = infer_split(parquet_path.name)
        parquet_file = pq.ParquetFile(parquet_path)
        row_index_in_file = 0
        for batch in parquet_file.iter_batches(columns=READ_COLUMNS, batch_size=32):
            for row in batch.to_pylist():
                source_name = SOURCE_MAP.get(row.get("source"), str(row.get("source")))
                difficulty_name = DIFFICULTY_MAP.get(row.get("difficulty"), str(row.get("difficulty")))
                tags = normalize_tags(row.get("cf_tags"))
                tag_families = infer_tag_families(tags)
                structures = infer_structure_candidates(row.get("description") or "", tags)
                objective = infer_objective(row.get("description") or "", tags)
                difficulty_bucket = infer_difficulty_bucket(source_name, difficulty_name)
                rating_bucket = infer_rating_bucket(source_name, row.get("cf_rating"))
                non_stdio = (
                    (row.get("input_file") not in (None, "", "stdin"))
                    or (row.get("output_file") not in (None, "", "stdout"))
                )
                translated = bool(row.get("is_description_translated"))
                english_ok, english_score_value = looks_english(row.get("name") or "", row.get("description") or "")
                reference_solution = pick_reference_solution(row.get("solutions"))
                row_uid = f"{parquet_path.stem}__row_{row_index_in_file:04d}"
                problem_id = derive_problem_id(source_name, row, row_uid)

                features = {f"source:{source_name}"}
                if difficulty_bucket:
                    features.add(f"difficulty:{difficulty_bucket}")
                if rating_bucket:
                    features.add(f"rating:{rating_bucket}")
                for family in tag_families:
                    features.add(f"tag:{family}")
                for structure in structures:
                    features.add(f"structure:{structure}")
                if objective != "unknown":
                    features.add(f"objective:{objective}")
                if translated:
                    features.add("special:translated")
                if non_stdio:
                    features.add("special:non_stdio")
                if not tags:
                    features.add("special:untagged")

                public_tests = row.get("public_tests") or {}
                quality = 0
                if row.get("name"):
                    quality += 3
                if len(row.get("description") or "") >= 400:
                    quality += 2
                if count_cases(public_tests) > 0:
                    quality += 2
                quality += min(len(tag_families), 4)
                if row.get("cf_rating") not in (None, 0):
                    quality += 1
                if difficulty_name != "UNKNOWN_DIFFICULTY":
                    quality += 1
                if objective != "unknown":
                    quality += 1
                if structures:
                    quality += 1
                if english_ok:
                    quality += 2
                if reference_solution:
                    quality += 2

                records.append(
                    {
                        "problem_id": problem_id,
                        "row_uid": row_uid,
                        "parquet_file": parquet_path.name,
                        "row_index_in_file": row_index_in_file,
                        "split": split,
                        "title": row.get("name") or "",
                        "source_name": source_name,
                        "difficulty_name": difficulty_name,
                        "difficulty_bucket": difficulty_bucket,
                        "rating_bucket": rating_bucket,
                        "cf_rating": row.get("cf_rating"),
                        "cf_tags": tags,
                        "tag_families": tag_families,
                        "structures": structures,
                        "objective": objective,
                        "translated": translated,
                        "non_stdio": non_stdio,
                        "english_ok": english_ok,
                        "english_score": english_score_value,
                        "has_reference_solution": reference_solution is not None,
                        "reference_solution_meta": {
                            "language_id": None if reference_solution is None else reference_solution["language_id"],
                            "language_guess": None if reference_solution is None else reference_solution["language_guess"],
                            "line_count": None if reference_solution is None else reference_solution["line_count"],
                        },
                        "features": sorted(features),
                        "quality": quality,
                        "public_test_count": count_cases(public_tests),
                    }
                )
                row_index_in_file += 1
    return records


def select_records(records: list[dict[str, Any]], target_features: set[str]) -> list[dict[str, Any]]:
    previous_problem_ids = load_previous_problem_ids()
    eligible_records = [
        record
        for record in records
        if record["english_ok"] and record["has_reference_solution"] and record["problem_id"] not in previous_problem_ids
    ]
    if len(eligible_records) < MIN_SELECTED:
        eligible_records = [record for record in records if record["english_ok"] and record["has_reference_solution"]]

    uncovered = set(target_features)
    selected = []
    selected_ids = set()
    covered_features = set()

    while uncovered and len(selected) < MAX_SELECTED:
        best = None
        best_gain = set()
        best_key = None
        for record in eligible_records:
            if record["row_uid"] in selected_ids:
                continue
            gain = set(record["features"]) & uncovered
            if not gain:
                continue
            rarity_bonus = sum(1 for feature in gain if feature.startswith("special:") or feature.startswith("source:"))
            key = (
                len(gain),
                rarity_bonus,
                record["quality"],
                record["english_score"],
                len(record["tag_families"]),
                record["public_test_count"],
            )
            if best_key is None or key > best_key:
                best = record
                best_gain = gain
                best_key = key
        if best is None:
            break
        selected.append(best)
        selected_ids.add(best["row_uid"])
        uncovered -= best_gain
        covered_features.update(best["features"])

    while len(selected) < MIN_SELECTED:
        best = None
        best_key = None
        for record in eligible_records:
            if record["row_uid"] in selected_ids:
                continue
            novelty = len(set(record["features"]) - covered_features)
            key = (
                novelty,
                record["quality"],
                record["english_score"],
                len(record["tag_families"]),
                1 if record["translated"] else 0,
                1 if record["non_stdio"] else 0,
            )
            if best_key is None or key > best_key:
                best = record
                best_key = key
        if best is None:
            break
        selected.append(best)
        selected_ids.add(best["row_uid"])
        covered_features.update(best["features"])

    return selected


def load_selected_rows(selected_records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    target_map = defaultdict(dict)
    for record in selected_records:
        target_map[record["parquet_file"]][record["row_index_in_file"]] = record["row_uid"]

    loaded = {}
    for parquet_path in sorted(DATA_DIR.glob("*.parquet")):
        if parquet_path.name not in target_map:
            continue
        wanted = target_map[parquet_path.name]
        parquet_file = pq.ParquetFile(parquet_path)
        row_index_in_file = 0
        for batch in parquet_file.iter_batches(columns=READ_COLUMNS, batch_size=32):
            for row in batch.to_pylist():
                if row_index_in_file in wanted:
                    loaded[wanted[row_index_in_file]] = row
                row_index_in_file += 1
    return loaded


def json_default(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def build_output_record(record: dict[str, Any], row: dict[str, Any], selection_id: int) -> dict[str, Any]:
    source_name = record["source_name"]
    difficulty_name = record["difficulty_name"]
    public_tests = row.get("public_tests") or {}
    problem_id = record["problem_id"]
    reference_solution = pick_reference_solution(row.get("solutions"))

    output_record = {
        "selection_id": f"sample_{selection_id:02d}",
        "problem_id": problem_id,
        "record_uid": record["row_uid"],
        "statement_language": "english",
        "title": row.get("name") or "",
        "description": row.get("description") or "",
        "public_tests": {
            "input": public_tests.get("input") or [],
            "output": public_tests.get("output") or [],
        },
        "source": {
            "split": record["split"],
            "source_id": row.get("source"),
            "source_name": source_name,
            "url": derive_url(source_name, row),
        },
        "difficulty": {
            "difficulty_id": row.get("difficulty"),
            "difficulty_name": difficulty_name,
            "difficulty_bucket": record["difficulty_bucket"],
            "cf_rating": row.get("cf_rating"),
            "cf_points": row.get("cf_points"),
            "cf_contest_id": row.get("cf_contest_id"),
            "cf_index": row.get("cf_index"),
            "rating_bucket": record["rating_bucket"],
        },
        "tags": record["cf_tags"],
        "limits": {
            "time_limit": row.get("time_limit"),
            "memory_limit_bytes": row.get("memory_limit_bytes"),
        },
        "io_mode": {
            "input_file": row.get("input_file"),
            "output_file": row.get("output_file"),
            "non_stdio": record["non_stdio"],
        },
        "translation": {
            "is_description_translated": record["translated"],
            "untranslated_description": row.get("untranslated_description") or "",
        },
        "reference_solution": reference_solution,
        "artifact_counts": {
            "public_tests": count_cases(row.get("public_tests")),
            "private_tests": count_cases(row.get("private_tests")),
            "generated_tests": count_cases(row.get("generated_tests")),
            "solutions": count_solutions(row.get("solutions")),
            "incorrect_solutions": count_solutions(row.get("incorrect_solutions")),
        },
        "heuristic_profile": {
            "tag_families": record["tag_families"],
            "structure_candidates": record["structures"],
            "objective_type": record["objective"],
            "coverage_features": record["features"],
            "english_filter": {
                "passed": record["english_ok"],
                "score": record["english_score"],
            },
            "notes": [
                "selection favors source, difficulty, tag and structure coverage over sample count",
                "heuristic_profile fields are inferred from metadata and statement text",
            ],
        },
    }
    return output_record


def write_outputs(
    selected_records: list[dict[str, Any]],
    loaded_rows: dict[str, dict[str, Any]],
    target_features: set[str],
) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old_file in OUTPUT_DIR.glob("*.json"):
        old_file.unlink()

    manifest_entries = []
    source_counter = Counter()
    difficulty_counter = Counter()
    feature_counter = Counter()

    for idx, record in enumerate(selected_records, start=1):
        row = loaded_rows[record["row_uid"]]
        output_record = build_output_record(record, row, idx)
        title_slug = slugify(output_record["title"])
        file_name = f"{idx:02d}_{record['source_name'].lower()}_{title_slug}.json"
        file_path = OUTPUT_DIR / file_name
        file_path.write_text(
            json.dumps(output_record, ensure_ascii=False, indent=2, default=json_default),
            encoding="utf-8",
        )

        source_counter[record["source_name"]] += 1
        difficulty_counter[record["difficulty_name"]] += 1
        feature_counter.update(record["features"])
        manifest_entries.append(
            {
                "file_name": file_name,
                "selection_id": output_record["selection_id"],
                "problem_id": output_record["problem_id"],
                "record_uid": record["row_uid"],
                "title": output_record["title"],
                "source_name": record["source_name"],
                "difficulty_name": record["difficulty_name"],
                "statement_language": "english",
                "reference_solution_language_id": None if output_record["reference_solution"] is None else output_record["reference_solution"]["language_id"],
                "reference_solution_language_guess": None if output_record["reference_solution"] is None else output_record["reference_solution"]["language_guess"],
                "tag_families": record["tag_families"],
                "coverage_features": record["features"],
            }
        )

    manifest = {
        "selection_strategy": {
            "type": "greedy_set_cover_plus_diversity_fill",
            "target_features": sorted(target_features),
            "max_selected": MAX_SELECTED,
            "min_selected": MIN_SELECTED,
            "hard_filters": [
                "statement must be english by heuristic filter",
                "must contain at least one correct solution code",
                "prefer not to reuse the immediately previous batch when possible",
            ],
        },
        "summary": {
            "total_selected": len(manifest_entries),
            "source_distribution": dict(source_counter),
            "difficulty_distribution": dict(difficulty_counter),
            "covered_target_features": sorted(set(feature_counter) & target_features),
            "uncovered_target_features": sorted(target_features - set(feature_counter)),
        },
        "files": manifest_entries,
    }
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    records = build_metadata()
    previous_problem_ids = load_previous_problem_ids()
    eligible_records = [
        record
        for record in records
        if record["english_ok"] and record["has_reference_solution"] and record["problem_id"] not in previous_problem_ids
    ]
    if len(eligible_records) < MIN_SELECTED:
        eligible_records = [record for record in records if record["english_ok"] and record["has_reference_solution"]]
    available_target_features = {
        feature
        for record in eligible_records
        for feature in record["features"]
        if feature in TARGET_FEATURES
    }
    selected_records = select_records(records, available_target_features)
    loaded_rows = load_selected_rows(selected_records)
    manifest = write_outputs(selected_records, loaded_rows, available_target_features)
    print(
        f"done total_candidates={len(records)} selected={manifest['summary']['total_selected']} "
        f"output_dir={OUTPUT_DIR}",
        flush=True,
    )
    print(
        f"uncovered_target_features={len(manifest['summary']['uncovered_target_features'])}",
        flush=True,
    )


if __name__ == "__main__":
    main()
