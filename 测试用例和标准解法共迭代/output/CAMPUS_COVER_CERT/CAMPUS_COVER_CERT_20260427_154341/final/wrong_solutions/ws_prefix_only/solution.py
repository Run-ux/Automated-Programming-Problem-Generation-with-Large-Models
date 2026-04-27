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
            violation_R = -1
            for R in range(K):
                cnt = 0
                for a in teams:
                    r1, r2 = a % x, (a + 1) % x
                    if r1 <= R or r2 <= R:
                        cnt += 1
                if cnt < (R + 1):
                    violation_R = R
                    break
            if violation_R != -1:
                out.append("NO\n0 {}".format(violation_R))
            else:
                out.append("YES")
                used = set()
                for i, a in enumerate(teams[:K]):
                    r1, r2 = a % x, (a + 1) % x
                    for s in (r1, r2, r1 + x, r2 + x):
                        if 0 <= s < K and s not in used:
                            out.append("{} {}".format(i + 1, s))
                            used.add(s)
                            break
    return "\n".join(out)