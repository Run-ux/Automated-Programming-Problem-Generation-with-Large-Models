import random

def generate_tests() -> list[dict]:
    tests = []
    random.seed(42)
    
    # 1. basic_small
    tests.append({
        "input": "3 4\n1 0\n1 1\n2 2\n2 3",
        "source": "problem_statement",
        "purpose": "Verify fundamental YES/NO branching, output formatting, and basic modulo constraints",
        "expect_oracle": True,
        "is_sample": True,
        "is_large": False,
        "metadata": {"bucket": "basic_small", "x": 3, "q": 4}
    })
    tests.append({
        "input": "5 4\n1 0\n1 3\n1 3\n2 4",
        "source": "problem_statement",
        "purpose": "Demonstrate lexicographically minimal conflict interval selection",
        "expect_oracle": True,
        "is_sample": True,
        "is_large": False,
        "metadata": {"bucket": "basic_small", "x": 5, "q": 4}
    })
    
    # 2. boundary_values
    tests.append({
        "input": "1 3\n1 0\n2 1\n2 2",
        "source": "custom",
        "purpose": "Test x=1, K=1, K=2 edge cases",
        "expect_oracle": True,
        "is_sample": False,
        "is_large": False,
        "metadata": {"bucket": "boundary_values", "x": 1, "q": 3}
    })
    tests.append({
        "input": "2 5\n1 1000000000\n1 0\n2 2\n2 3\n2 1",
        "source": "custom",
        "purpose": "Test large a_i, K=x, exact capacity boundaries",
        "expect_oracle": True,
        "is_sample": False,
        "is_large": False,
        "metadata": {"bucket": "boundary_values", "x": 2, "q": 5}
    })
    
    # 3. random_moderate
    lines = ["100 20"]
    for _ in range(20):
        if random.random() < 0.6:
            lines.append(f"1 {random.randint(0, 1000)}")
        else:
            lines.append(f"2 {random.randint(1, 50)}")
    tests.append({
        "input": "\n".join(lines),
        "source": "random",
        "purpose": "Stress test correctness under varied random distributions of a_i and K",
        "expect_oracle": False,
        "is_sample": False,
        "is_large": False,
        "metadata": {"bucket": "random_moderate", "x": 100, "q": 20}
    })
    
    # 4. adversarial_hall
    # Crafted to force tight Hall violations
    tests.append({
        "input": "4 6\n1 0\n1 0\n1 2\n1 2\n2 4\n2 3",
        "source": "custom",
        "purpose": "Force tight Hall violations, test lexicographical minimality extraction",
        "expect_oracle": True,
        "is_sample": False,
        "is_large": False,
        "metadata": {"bucket": "adversarial_hall", "x": 4, "q": 6}
    })
    
    # 5. performance_max (scaled down for generator safety, but marked large)
    lines_perf = ["400000 10"]
    for i in range(1, 6):
        lines_perf.append(f"1 {i * 1000}")
    lines_perf.append("2 1000000000")
    for i in range(6, 10):
        lines_perf.append(f"1 {i * 1000}")
    lines_perf.append("2 5")
    tests.append({
        "input": "\n".join(lines_perf),
        "source": "custom",
        "purpose": "Validate O(log x) or O(1) per operation complexity under full constraints and large K",
        "expect_oracle": False,
        "is_sample": False,
        "is_large": True,
        "metadata": {"bucket": "performance_max", "x": 400000, "q": 10}
    })
    
    return tests