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
            if n < K:
                out.append("NO\n0 {}".format(K - 1))
                continue
            out.append("YES")
            used = set()
            for i, a in enumerate(teams[:K]):
                r1, r2 = a % x, (a + 1) % x
                s = r1 if r1 < K else r2
                if s not in used:
                    out.append("{} {}".format(i + 1, s))
                    used.add(s)
                else:
                    out.append("{} {}".format(i + 1, a % K))
                    used.add(a % K)
    return "\n".join(out)