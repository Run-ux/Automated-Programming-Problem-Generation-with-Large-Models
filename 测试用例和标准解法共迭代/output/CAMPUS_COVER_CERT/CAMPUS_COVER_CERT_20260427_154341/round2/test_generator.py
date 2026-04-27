def generate_tests() -> list[dict]:
    tests = []
    tests.append({
        "input": "3 4\n1 0\n1 1\n2 2\n2 3",
        "output": "YES\n1 0\n2 1\nNO\n0 2",
        "source": "problem_statement",
        "purpose": "Basic YES/NO branching and formatting.",
        "expect_oracle": True,
        "is_sample": True,
        "is_large": False,
        "metadata": {"bucket": "basic_small"}
    })
    tests.append({
        "input": "5 4\n1 0\n1 3\n1 3\n2 4",
        "output": "NO\n0 1",
        "source": "problem_statement",
        "purpose": "Lexicographically smallest conflict interval.",
        "expect_oracle": True,
        "is_sample": True,
        "is_large": False,
        "metadata": {"bucket": "basic_small"}
    })
    tests.append({
        "input": "1 3\n1 0\n2 1\n2 2",
        "output": "YES\n1 0\nNO\n0 1",
        "source": "generated",
        "purpose": "x=1 edge case, K=1 and K=total_teams+1.",
        "expect_oracle": True,
        "is_sample": False,
        "is_large": False,
        "metadata": {"bucket": "boundary_values"}
    })
    tests.append({
        "input": "5 10\n1 0\n1 2\n2 2\n1 4\n2 3\n1 1\n2 4\n1 3\n2 5\n2 6",
        "output": "",
        "source": "generated",
        "purpose": "Interleaved adds and queries, mixed YES/NO outcomes.",
        "expect_oracle": True,
        "is_sample": False,
        "is_large": False,
        "metadata": {"bucket": "random_mixed"}
    })
    tests.append({
        "input": "4 5\n1 0\n1 2\n1 2\n2 3\n2 4",
        "output": "NO\n0 0\nNO\n0 3",
        "source": "generated",
        "purpose": "Force tight Hall violations at specific L, R.",
        "expect_oracle": True,
        "is_sample": False,
        "is_large": False,
        "metadata": {"bucket": "adversarial_hall"}
    })
    lines_perf = ["400000 1000"]
    for i in range(500):
        lines_perf.append(f"1 {i * 1000}")
    for i in range(500):
        lines_perf.append(f"2 {i + 1}")
    tests.append({
        "input": "\n".join(lines_perf),
        "output": "",
        "source": "generated",
        "purpose": "Large x, q, and K to test efficiency.",
        "expect_oracle": False,
        "is_sample": False,
        "is_large": True,
        "metadata": {"bucket": "performance_large"}
    })
    return tests