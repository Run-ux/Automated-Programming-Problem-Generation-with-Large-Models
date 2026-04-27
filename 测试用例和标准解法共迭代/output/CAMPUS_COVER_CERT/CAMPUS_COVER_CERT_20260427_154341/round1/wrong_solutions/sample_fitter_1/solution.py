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
            else:
                out.append("YES")
                assigned = []
                used = set()
                for s in range(K):
                    found = False
                    for i, a in enumerate(teams):
                        r1, r2 = a % x, (a + 1) % x
                        if i not in used and (s % x == r1 or s % x == r2):
                            assigned.append(f"{i+1} {s}")
                            used.add(i)
                            found = True
                            break
                    if not found:
                        for i in range(len(teams)):
                            if i not in used:
                                assigned.append(f"{i+1} {s}")
                                used.add(i)
                                break
                out.extend(assigned)
    return "\n".join(out)