from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable


DASH_RE = re.compile(r"^-\s+([a-z_]+)\b")
ORDERED_RE = re.compile(r"^\d+\.\s+([a-z_]+)\b")


def extract_closed_labels(prompt_file: Path) -> list[str]:
	"""Extract label names from the recommended list in prompt_invariant.py."""
	lines = prompt_file.read_text(encoding="utf-8").splitlines()
	labels: list[str] = []
	for line in lines:
		stripped = line.strip()
		match = DASH_RE.match(stripped) or ORDERED_RE.match(stripped)
		if match:
			labels.append(match.group(1))
	# Remove duplicates while preserving order
	seen = set()
	ordered = []
	for label in labels:
		if label not in seen:
			ordered.append(label)
			seen.add(label)
	return ordered


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
			"Count invariant labels and compare against the closed label set "
			"from prompt_invariant.py."
		)
	)
	parser.add_argument(
		"--registry",
		default="finiteness_verification/output/pilot/label_registry/invariant.json",
		help="Path to invariant.json",
	)
	parser.add_argument(
		"--prompt",
		default="finiteness_verification/prompts/prompt_invariant.py",
		help="Path to prompt_invariant.py (closed label set source)",
	)
	args = parser.parse_args()

	registry_path = Path(args.registry)
	prompt_path = Path(args.prompt)

	closed_labels = extract_closed_labels(prompt_path)
	registry_labels = load_registry_labels(registry_path)

	closed_set = set(closed_labels)
	registry_set = set(registry_labels)

	in_closed = sorted(registry_set & closed_set)
	new_labels = sorted(registry_set - closed_set)

	print(f"Total invariants in registry: {len(registry_labels)}")
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

