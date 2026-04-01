from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


DATA_DIR = Path(r"D:\AutoProblemGen\爬取题目\datasets\Imandra_code_contests\data")
OUTPUT_PATH = Path(r"D:\AutoProblemGen\爬取题目\datasets\Imandra_code_contests\code_contests_merged.jsonl")
TEMP_OUTPUT_PATH = OUTPUT_PATH.with_suffix(".jsonl.tmp")
BATCH_SIZE = 8


def infer_split(file_name: str) -> str:
    if file_name.startswith("train-"):
        return "train"
    if file_name.startswith("test-"):
        return "test"
    if file_name.startswith("valid-"):
        return "valid"
    return "unknown"


def json_default(value: Any) -> Any:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.hex()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def main() -> None:
    parquet_files = sorted(DATA_DIR.glob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No parquet files found under {DATA_DIR}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if TEMP_OUTPUT_PATH.exists():
        TEMP_OUTPUT_PATH.unlink()

    total_rows = 0
    total_files = len(parquet_files)

    with TEMP_OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as out:
        for index, parquet_path in enumerate(parquet_files, start=1):
            split = infer_split(parquet_path.name)
            parquet_file = pq.ParquetFile(parquet_path)
            file_rows = parquet_file.metadata.num_rows
            print(
                f"[{index}/{total_files}] converting {parquet_path.name} "
                f"rows={file_rows} split={split}",
                flush=True,
            )

            written_in_file = 0
            for batch in parquet_file.iter_batches(batch_size=BATCH_SIZE):
                for record in batch.to_pylist():
                    record["split"] = split
                    out.write(json.dumps(record, ensure_ascii=False, default=json_default))
                    out.write("\n")
                    total_rows += 1
                    written_in_file += 1

            print(
                f"[{index}/{total_files}] finished {parquet_path.name} "
                f"written_rows={written_in_file}",
                flush=True,
            )

    os.replace(TEMP_OUTPUT_PATH, OUTPUT_PATH)
    output_size_gb = OUTPUT_PATH.stat().st_size / (1024 ** 3)
    print(f"done rows={total_rows} output={OUTPUT_PATH} size_gb={output_size_gb:.2f}", flush=True)


if __name__ == "__main__":
    main()
