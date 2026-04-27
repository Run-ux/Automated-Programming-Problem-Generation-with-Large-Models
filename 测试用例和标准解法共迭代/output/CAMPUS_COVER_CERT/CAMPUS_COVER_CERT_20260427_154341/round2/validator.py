def validate(input_str: str) -> bool:
    try:
        tokens = input_str.split()
        if not tokens:
            return False
        it = iter(tokens)
        x = int(next(it))
        q = int(next(it))
        if not (1 <= x <= 400000 and 1 <= q <= 400000):
            return False
        for _ in range(q):
            t = int(next(it))
            val = int(next(it))
            if t == 1:
                if not (0 <= val <= 1000000000):
                    return False
            elif t == 2:
                if not (1 <= val <= 1000000000):
                    return False
            else:
                return False
        try:
            next(it)
            return False
        except StopIteration:
            return True
    except Exception:
        return False