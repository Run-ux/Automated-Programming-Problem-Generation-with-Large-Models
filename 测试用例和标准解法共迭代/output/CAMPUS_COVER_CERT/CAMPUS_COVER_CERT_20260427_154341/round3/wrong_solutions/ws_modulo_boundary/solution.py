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
            if K > x:
                out.append("NO\n0 {}".format(K - 1))
                continue
            cnt = 0
            for a in teams:
                r1, r2 = a % x, (a + 1) % x
                if r1 < K or r2 < K:
                    cnt += 1
            if cnt < K:
                out.append("NO\n0 {}".format(K - 1))
            else:
                out.append("YES")
                used = [False] * K
                for i, a in enumerate(teams):
                    if i >= K:
                        break
                    r1, r2 = a % x, (a + 1) % x
                    for s in (r1, r2):
                        if s < K and not used[s]:
                            out.append("{} {}".format(i + 1, s))
                            used[s] = True
                            break
                for idx in range(K):
                    if not used[idx]:
                        out.append("{} {}".format(len(teams), idx))
                        used[idx] = True
    return "\n".join(out)