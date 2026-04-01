from __future__ import annotations

import json
from pathlib import Path


SOURCE_PATH = Path(r"D:\AutoProblemGen\爬取题目\datasets\Imandra_code_contests\code_contests_merged.jsonl")
OUTPUT_DIR = Path(r"D:\AutoProblemGen\爬取题目\datasets\Imandra_code_contests\code_contests_merged_chunks_128mb")
TARGET_CHUNK_SIZE_BYTES = 128 * 1024 * 1024


def main() -> None:
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(f"Source file not found: {SOURCE_PATH}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total_lines = 0
    chunk_index = 0
    chunk_lines = 0
    chunk_bytes = 0
    current_handle = None
    manifest: list[dict[str, int | str]] = []

    def open_new_chunk() -> tuple[object, Path]:
        nonlocal chunk_index, chunk_lines, chunk_bytes
        chunk_index += 1
        chunk_lines = 0
        chunk_bytes = 0
        chunk_path = OUTPUT_DIR / f"code_contests_merged_part_{chunk_index:04d}.jsonl"
        handle = chunk_path.open("wb")
        print(f"opened chunk {chunk_index:04d}: {chunk_path.name}", flush=True)
        return handle, chunk_path

    current_handle, current_path = open_new_chunk()

    with SOURCE_PATH.open("rb") as source:
        for line in source:
            if chunk_lines > 0 and chunk_bytes + len(line) > TARGET_CHUNK_SIZE_BYTES:
                current_handle.close()
                manifest.append(
                    {
                        "file": current_path.name,
                        "lines": chunk_lines,
                        "bytes": chunk_bytes,
                    }
                )
                current_handle, current_path = open_new_chunk()

            current_handle.write(line)
            chunk_lines += 1
            chunk_bytes += len(line)
            total_lines += 1

    if current_handle is not None:
        current_handle.close()
        manifest.append(
            {
                "file": current_path.name,
                "lines": chunk_lines,
                "bytes": chunk_bytes,
            }
        )

    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "source_file": str(SOURCE_PATH),
                "target_chunk_size_bytes": TARGET_CHUNK_SIZE_BYTES,
                "total_chunks": len(manifest),
                "total_lines": total_lines,
                "chunks": manifest,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"done total_lines={total_lines} total_chunks={len(manifest)} "
        f"output_dir={OUTPUT_DIR}",
        flush=True,
    )


if __name__ == "__main__":
    main()
