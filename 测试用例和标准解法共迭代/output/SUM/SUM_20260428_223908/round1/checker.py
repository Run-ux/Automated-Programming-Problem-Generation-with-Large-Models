def check(input_str: str, output_str: str, expected_str: str | None) -> bool:
    del input_str
    if expected_str is None:
        return bool(output_str.strip())
    return output_str.strip() == expected_str.strip()
