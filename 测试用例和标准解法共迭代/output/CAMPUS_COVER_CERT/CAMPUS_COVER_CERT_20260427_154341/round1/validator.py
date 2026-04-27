def validate(input_str: str) -> bool:
    try:
        tokens = input_str.strip().split()
        if not tokens:
            return False
        it = iter(tokens)
        x = int(next(it))
        q = int(next(it))
        if not (1 <= x <= 400000 and 1 <= q <= 400000):
            return False
        for _ in range(q):
            op = int(next(it))
            if op == 1:
                a = int(next(it))
                if not (0 <= a <= 10**9):
                    return False
            elif op == 2:
                K = int(next(it))
                if not (1 <= K <= 10**9):
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