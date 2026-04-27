def solve(input_str: str) -> str:
    data = input_str.split()
    it = iter(data)
    x = int(next(it))
    q = int(next(it))
    teams = []
    out = []
    for _ in range(q):
        t = int(next(it))
        val = int(next(it))
        if t == 1:
            teams.append(val)
        else:
            K = val
            n = len(teams)
            conflict = None
            for L in range(K):
                for R in range(L, K):
                    cnt = 0
                    for a in teams:
                        r1, r2 = a % x, (a + 1) % x
                        for s in range(L, R + 1):
                            if s % x == r1 or s % x == r2:
                                cnt += 1
                                break
                    if cnt < (R - L + 1):
                        conflict = (L, R)
                        break
                if conflict:
                    break
            if conflict:
                out.append("NO\n{} {}".format(conflict[0], conflict[1]))
            else:
                out.append("YES")
                used = set()
                for i, a in enumerate(teams[:K]):
                    r1, r2 = a % x, (a + 1) % x
                    for s in range(K):
                        if (s % x == r1 or s % x == r2) and s not in used:
                            out.append("{} {}".format(i + 1, s))
                            used.add(s)
                            break
    return "\n".join(out)