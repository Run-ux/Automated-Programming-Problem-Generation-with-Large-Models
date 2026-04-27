def check(input_str: str, output_str: str, expected_str: str | None = None) -> bool:
    import sys
    try:
        in_tokens = input_str.strip().split()
        out_tokens = output_str.strip().split()
        if not in_tokens or not out_tokens:
            return False
        it_in = iter(in_tokens)
        x = int(next(it_in))
        q = int(next(it_in))
        teams = []
        queries = []
        for _ in range(q):
            op = int(next(it_in))
            if op == 1:
                a = int(next(it_in))
                teams.append(a)
            else:
                K = int(next(it_in))
                queries.append(K)
        
        it_out = iter(out_tokens)
        team_used = [False] * len(teams)
        
        def covers(L, R, a_val):
            r1 = a_val % x
            r2 = (a_val + 1) % x
            return (L <= r1 <= R) or (L <= r2 <= R)
        
        def count_cover(L, R):
            cnt = 0
            for a_val in teams:
                if covers(L, R, a_val):
                    cnt += 1
            return cnt
        
        for K in queries:
            try:
                res = next(it_out)
            except StopIteration:
                return False
            if res == 'YES':
                used_slots = set()
                for _ in range(K):
                    tid = int(next(it_out))
                    s = int(next(it_out))
                    if not (1 <= tid <= len(teams)):
                        return False
                    if team_used[tid - 1]:
                        return False
                    team_used[tid - 1] = True
                    if not (0 <= s < K):
                        return False
                    if s in used_slots:
                        return False
                    used_slots.add(s)
                    a_val = teams[tid - 1]
                    if not covers(s, s, a_val):
                        return False
                if len(used_slots) != K:
                    return False
            elif res == 'NO':
                L = int(next(it_out))
                R = int(next(it_out))
                if not (0 <= L <= R < K):
                    return False
                if count_cover(L, R) >= (R - L + 1):
                    return False
                if K <= 2000:
                    for l in range(L + 1):
                        r_start = l if l < L else L
                        r_end = R if l < L else R - 1
                        for r in range(r_start, r_end + 1):
                            if count_cover(l, r) < (r - l + 1):
                                return False
            else:
                return False
        return True
    except Exception:
        return False