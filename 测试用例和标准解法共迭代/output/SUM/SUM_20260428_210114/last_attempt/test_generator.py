def generate_tests() -> list[dict]:
    return [
        {"input": "0 0", "source": "zero", "purpose": "零值边界"},
        {"input": "1 2", "source": "basic", "purpose": "基础求和"}
    ]
