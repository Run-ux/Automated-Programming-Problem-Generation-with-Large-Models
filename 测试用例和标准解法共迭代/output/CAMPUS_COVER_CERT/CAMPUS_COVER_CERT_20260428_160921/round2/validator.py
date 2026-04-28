def validate(input_str: str) -> bool:
    parts = input_str.split()
    if not parts:
        return False
    try:
        idx = 0
        x = int(parts[idx]); idx += 1
        q = int(parts[idx]); idx += 1
        if not (1 <= x <= 400000) or not (1 <= q <= 400000):
            return False
        for _ in range(q):
            if idx >= len(parts):
                return False
            op = int(parts[idx]); idx += 1
            if op == 1:
                if idx >= len(parts):
                    return False
                a = int(parts[idx]); idx += 1
                if a < 0 or a > 1000000000:
                    return False
            elif op == 2:
                if idx >= len(parts):
                    return False
                K = int(parts[idx]); idx += 1
                if K < 1 or K > 1000000000:
                    return False
            else:
                return False
        if idx != len(parts):
            return False
        return True
    except (ValueError, IndexError):
        return False