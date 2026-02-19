# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This project verifies whether programming problem tags are "finite and enumerable" through a four-dimensional extraction pipeline. It extracts and analyzes I/C/O/V tags (Input Structure, Core Constraints, Objective, Invariant) from competitive programming problems.

## Running Commands

### Prerequisites

```bash
# Set API key (required)
export DASHSCOPE_API_KEY="your-api-key"  # Linux/Mac
$env:DASHSCOPE_API_KEY="your-api-key"   # Windows PowerShell

# Install dependencies
pip install requests numpy scipy matplotlib
```

### Module Execution

All modules must run with `python -m` from the project root:

```bash
cd D:\Automated-Programming-Problem-Generation-with-Large-Models

# Extract tags (multi-round)
python -m finiteness_verification.extract --input finiteness_verification/data/sample_pilot.json --output finiteness_verification/output/pilot/ --rounds 3 --resume

# Normalize with embedding + LLM fallback
python -m finiteness_verification.normalize --input finiteness_verification/output/pilot/raw/ --output finiteness_verification/output/pilot/normalized/ --embedding-threshold 0.85

# Majority voting
python -m finiteness_verification.vote --input finiteness_verification/output/pilot/normalized/ --output finiteness_verification/output/pilot/voted/

# Saturation curve analysis
python -m finiteness_verification.analyze --input finiteness_verification/output/phase1/voted/ --output finiteness_verification/output/phase1/saturation_curves/

# View help
python -m finiteness_verification.extract --help
python -m finiteness_verification.normalize --help
python -m finiteness_verification.vote --help
python -m finiteness_verification.analyze --help
```

## Architecture

### Four-Dimensional Tag System
- **Input Structure (I)**: Data organization format (array, graph, tree, string, matrix)
- **Core Constraints (C)**: Problem constraints (connectivity, ordering, distinctness)
- **Objective (O)**: Optimization goals (maximize_value, minimize_count, feasibility)
- **Invariant (V)**: Algorithmic invariants (monotonicity, optimal_substructure, greedy_choice)

### Core Pipeline
```
sample.json → extract (raw/) → normalize (normalized/ + label_registry/) → vote (voted/) → analyze (saturation_curves/)
```

### Key Modules
- `extract.py`: Multi-round tag extraction using LLM (qwen-turbo)
- `normalize.py`: Embedding similarity + LLM fallback for tag normalization
- `vote.py`: Majority voting for stable results
- `analyze.py`: Saturation curve fitting and finiteness judgment
- `classify.py`: Phase 2 closed classification using extracted labels
- `qwen_client.py`: Wrapper for DashScope API calls
- `prompts/`: Prompt templates for each dimension

### Output Structure
```
output/
├── pilot/           # Pilot run (50 problems)
│   ├── raw/        # Raw extraction results
│   ├── normalized/ # Normalized results
│   ├── label_registry/ # Dynamic tag registry
│   ├── voted/      # Voting results
│   └── logs/
└── phase1/         # Phase 1 (1500 problems)
    ├── raw/
    ├── normalized/
    ├── label_registry/
    ├── voted/
    ├── labels_per_dimension.json
    └── saturation_curves/
```

## Code Conventions

- Use `pathlib.Path` for all file paths
- JSON output must use `ensure_ascii=False, indent=2, encoding="utf-8"`
- Tag names: `lower_snake_case`
- Logging via `logging` module, not `print`
- `--resume` flag for checkpoint continuation
- Rate limiting: 1 request/second via `RateLimiter` class
