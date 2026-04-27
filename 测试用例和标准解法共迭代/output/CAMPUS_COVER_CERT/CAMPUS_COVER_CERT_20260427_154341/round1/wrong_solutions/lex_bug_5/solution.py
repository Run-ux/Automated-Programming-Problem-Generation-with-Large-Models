def solve(input_str: str) -> str:
    import sys
    data = list(map(int, input_str.split()))
    it = iter(data)
    x = next(it)
    q = next(it)
    teams = []
    out = []
    for _ in range(q):
        t = next(it)
        v = next(it)
        if t == 1:
            teams.append(v)
        else:
            K = v
            if len(teams) < K:
                out.append("NO")
                out.append(f"0 {K-1}")
                continue
            conflict = None
            for R in range(K):
                for L in range(R + 1):
                    cnt = 0
                    length = R - L + 1
                    for a in teams:
                        r1, r2 = a % x, (a + 1) % x
                        if (L % x <= r1 <= R % x) or (L % x <= r2 <= R % x):
                            cnt += 1
                    if cnt < length:
                        conflict = (L, R)
                        break
                if conflict:
                    break
            if conflict is None:
                out.append("YES")
                used = set()
                for s in range(K):
                    for i, a in enumerate(teams):
                        r1, r2 = a % x, (a + 1) % x
                        if i not in used and (s % x == r1 or s % x == r2):
                            out.append(f"{i+1} {s}")
                            used.add(i)
                            break
            else:
                out.append("NO")
                out.append(f"{conflict[0]} {conflict[1]}")
    return "\n".join(out)