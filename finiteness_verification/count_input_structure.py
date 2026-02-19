from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable


CANDIDATE_TYPES = [
    "array",
    "graph",
    "tree",
    "string",
    "matrix",
]


def extract_closed_types(prompt_file: Path) -> list[str]:
    """Extract type names from prompt_input_structure.py examples."""
    content = prompt_file.read_text(encoding="utf-8")
    labels = [t for t in CANDIDATE_TYPES if re.search(rf"\b{re.escape(t)}\b", content)]
    return labels


def load_registry_labels(registry_file: Path) -> list[str]:
    data = json.loads(registry_file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Registry JSON must be an object with label keys")
    return list(data.keys())


def format_list(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Count input_structure labels and compare against the closed label set "
            "from prompt_input_structure.py."
        )
    )
    parser.add_argument(
        "--registry",
        default="finiteness_verification/output/pilot/label_registry/input_structure.json",
        help="Path to input_structure.json",
    )
    parser.add_argument(
        "--prompt",
        default="finiteness_verification/prompts/prompt_input_structure.py",
        help="Path to prompt_input_structure.py (closed label set source)",
    )
    args = parser.parse_args()

    registry_path = Path(args.registry)
    prompt_path = Path(args.prompt)

    closed_labels = extract_closed_types(prompt_path)
    registry_labels = load_registry_labels(registry_path)

    closed_set = set(closed_labels)
    registry_set = set(registry_labels)

    in_closed = sorted(registry_set & closed_set)
    new_labels = sorted(registry_set - closed_set)

    print(f"Total input structures in registry: {len(registry_labels)}")
    print(f"Closed label set size: {len(closed_labels)}")
    print(f"Registry labels in closed set: {len(in_closed)}")
    print(f"Registry labels not in closed set (LLM新增): {len(new_labels)}")
    print()
    print("[In closed set]")
    print(format_list(in_closed) if in_closed else "- (none)")
    print()
    print("[LLM新增]")
    print(format_list(new_labels) if new_labels else "- (none)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())