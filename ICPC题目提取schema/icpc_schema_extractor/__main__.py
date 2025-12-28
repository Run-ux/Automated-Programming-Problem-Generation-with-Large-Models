from __future__ import annotations

from pathlib import Path

from .pipeline import PipelineConfig, run_pipeline


def main() -> int:
    # 直接在这里配置运行参数（不通过命令行传参）
    workspace_root = Path(__file__).resolve().parents[1]

    cfg = PipelineConfig(
        pdf_path=workspace_root / "problemset-2025.pdf",
        out_root=workspace_root / "out",
        schema_def_path=workspace_root / "schema五元组定义.md",
        # 如需根据题集格式调整分题正则，可在这里填：
        # problem_regexes=[r"^\\s*Problem\\s+([A-Z])\\s*[:\\-]\\s*(.+?)\\s*$"],
        model="qwen3-max",
        base_url=None,
        api_key=None,
        run_extract=True,
        run_schema=True,
    )

    run_pipeline(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
