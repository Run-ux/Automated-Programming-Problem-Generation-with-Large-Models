def solve(input_str: str) -> str:
    tokens = input_str.split()
    it = iter(tokens)
    x = int(next(it))
    q = int(next(it))
    teams = []
    out = []
    for _ in range(q):
        typ = int(next(it))
        val = int(next(it))
        if typ == 1:
            teams.append((len(teams)+1, val))
        else:
            K = val
            used = set()
            assign = []
            for tid, a in teams:
                r1, r2 = a % x, (a + 1) % x
                for s in range(K):
                    if s not in used and (s % x == r1 or s % x == r2):
                        used.add(s)
                        assign.append((tid, s))
                        break
            if len(assign) == K:
                out.append('YES')
                out.extend(f'{t} {s}' for t, s in assign)
            else:
                out.append('NO')
                check_K = min(K, 1000)
                best = None
                for length in range(1, check_K + 1):
                    for L in range(check_K - length + 1):
                        R = L + length - 1
                        cnt = 0
                        for tid2, a2 in teams:
                            r1, r2 = a2 % x, (a2 + 1) % x
                            for s in range(L, R + 1):
                                if s % x == r1 or s % x == r2:
                                    cnt += 1
                                    break
                        if cnt < length:
                            best = (L, R)
                            break
                    if best:
                        break
                if not best:
                    best = (0, K-1)
                out.append(f'{best[0]} {best[1]}')
    return '\n'.join(out)