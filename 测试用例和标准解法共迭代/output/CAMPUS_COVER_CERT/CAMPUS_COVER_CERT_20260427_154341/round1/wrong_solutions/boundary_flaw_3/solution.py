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
            for L in range(K):
                for R in range(L, min(L + x, K)):
                    cnt = 0
                    length = R - L + 1
                    for a in teams:
                        r = a % x
                        if L <= r <= R:
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
                        r = a % x
                        if i not in used and s % x == r:
                            out.append(f"{i+1} {s}")
                            used.add(i)
                            break
            else:
                out.append("NO")
                out.append(f"{conflict[0]} {conflict[1]}")
    return "\n".join(out)