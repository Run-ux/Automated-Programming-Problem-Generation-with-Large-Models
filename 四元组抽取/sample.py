"""
新 schema 采样脚本：从 imandra_curated_schema_inputs 中复制样本文件。

输出：
- data/sample_phase1/
- data/sample_pilot/
"""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path


RANDOM_SEED = 42
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "爬取题目" / "output" / "imandra_curated_schema_inputs"
DEFAULT_DATA_DIR = CURRENT_DIR / "data"


def list_problem_files(source_dir: Path) -> list[Path]:
    return [
        path
        for path in sorted(source_dir.glob("*.json"))
        if path.name.lower() != "manifest.json"
    ]


def choose_sample(files: list[Path], sample_size: int, rng: random.Random) -> list[Path]:
    if sample_size <= 0 or sample_size >= len(files):
        return list(files)
    return sorted(rng.sample(files, sample_size))


def copy_sample(files: list[Path], output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for source_file in files:
        shutil.copy2(source_file, output_dir / source_file.name)


def main() -> None:
    parser = argparse.ArgumentParser(description="复制新 schema 样本目录")
    parser.add_argument(
        "--source-dir",
        type=str,
        default=str(DEFAULT_SOURCE_DIR),
        help="源 schema 目录",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=str(DEFAULT_DATA_DIR),
        help="输出 data 目录",
    )
    parser.add_argument(
        "--phase1-size",
        type=int,
        default=300,
        help="phase1 样本量，默认 300；若不足则全部复制",
    )
    parser.add_argument(
        "--pilot-size",
        type=int,
        default=50,
        help="pilot 样本量，默认 50；若不足则全部复制",
    )
    args = parser.parse_args()

    rng = random.Random(RANDOM_SEED)
    source_dir = Path(args.source_dir)
    data_dir = Path(args.data_dir)
    phase1_dir = data_dir / "sample_phase1"
    pilot_dir = data_dir / "sample_pilot"

    files = list_problem_files(source_dir)
    if not files:
        raise FileNotFoundError(f"未找到可用 schema 文件：{source_dir}")

    phase1_files = choose_sample(files, args.phase1_size, rng)
    pilot_files = choose_sample(phase1_files, args.pilot_size, rng)

    copy_sample(phase1_files, phase1_dir)
    copy_sample(pilot_files, pilot_dir)

    print(f"总文件数: {len(files)}")
    print(f"phase1 样本: {len(phase1_files)} -> {phase1_dir}")
    print(f"pilot 样本: {len(pilot_files)} -> {pilot_dir}")


if __name__ == "__main__":
    main()
