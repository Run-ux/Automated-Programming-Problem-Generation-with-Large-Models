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
            used_ids = set()
            assign = []
            for tid, a in teams:
                if tid in used_ids:
                    continue
                r1, r2 = a % x, (a + 1) % x
                for s in range(K):
                    if s % x == r1 or s % x == r2:
                        assign.append((tid, s))
                        used_ids.add(tid)
                        break
            if len(assign) == K:
                out.append('YES')
                out.extend(f'{t} {s}' for t, s in assign)
                teams = [t for t in teams if t[0] not in used_ids]
            else:
                out.append('NO')
                limit = min(K, 500)
                found_v = False
                for L in range(limit):
                    for R in range(L, limit):
                        cnt = 0
                        for tid2, a2 in teams:
                            r1, r2 = a2 % x, (a2 + 1) % x
                            for s in range(L, R + 1):
                                if s % x == r1 or s % x == r2:
                                    cnt += 1
                                    break
                        if cnt < (R - L + 1):
                            out.append(f'{L} {R}')
                            found_v = True
                            break
                    if found_v:
                        break
                if not found_v:
                    out.append(f'0 {K-1}')
    return '\n'.join(out)