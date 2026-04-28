def validate(input_str: str) -> bool:
    try:
        [int(x) for x in input_str.split()]
        return bool(input_str.strip())
    except Exception:
        return False
