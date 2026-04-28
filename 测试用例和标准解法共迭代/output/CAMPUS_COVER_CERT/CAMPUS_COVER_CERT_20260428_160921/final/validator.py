def validate(input_str: str) -> bool:
    lines = input_str.strip().splitlines()
    if not lines:
        return False
    first = lines[0].split()
    if len(first) != 2:
        return False
    try:
        x = int(first[0])
        q = int(first[1])
    except (ValueError, IndexError):
        return False
    if not (1 <= x <= 400000) or not (1 <= q <= 400000):
        return False
    if len(lines) - 1 != q:
        return False
    for i in range(1, len(lines)):
        parts = lines[i].split()
        if len(parts) != 2:
            return False
        try:
            op = int(parts[0])
            val = int(parts[1])
        except (ValueError, IndexError):
            return False
        if op == 1:
            if not (0 <= val <= 1000000000):
                return False
        elif op == 2:
            if not (1 <= val <= 1000000000):
                return False
        else:
            return False
    return True