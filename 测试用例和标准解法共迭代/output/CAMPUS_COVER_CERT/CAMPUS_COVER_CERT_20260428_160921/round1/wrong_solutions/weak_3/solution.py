def solve(input_str):
    import sys
    data = input_str.strip().split()
    if not data:
        return ''
    it = iter(data)
    x = int(next(it))
    q = int(next(it))
    teams = []
    out = []
    for _ in range(q):
        typ = int(next(it))
        if typ == 1:
            a = int(next(it))
            teams.append((len(teams) + 1, a))
        else:
            K = int(next(it))
            if K > 100:
                if len(teams) < K:
                    out.append('NO')
                    out.append(f'0 {K - 1}')
                else:
                    out.append('YES')
                    for s in range(K):
                        out.append(f'{teams[s % len(teams)][0]} {s}')
                continue
            def can_cover_buggy(tid, a, s):
                r = s % x
                return r == a % x or r == (a % x) + 1
            def count_cover(L, R):
                cnt = 0
                for tid, a_i in teams:
                    rems = {a_i % x, (a_i % x) + 1}
                    ok = False
                    for r in rems:
                        s0 = L + ((r - L) % x + x) % x
                        if s0 <= R:
                            ok = True
                            break
                    if ok:
                        cnt += 1
                return cnt
            conflict = None
            for L in range(K):
                for R in range(L, K):
                    cnt = count_cover(L, R)
                    if cnt < R - L + 1:
                        if conflict is None or (L < conflict[0]) or (L == conflict[0] and R < conflict[1]):
                            conflict = (L, R)
            if conflict is not None:
                out.append('NO')
                out.append(f'{conflict[0]} {conflict[1]}')
            else:
                used = [False] * len(teams)
                assign = []
                for s in range(K):
                    found = -1
                    for i, (tid, a_i) in enumerate(teams):
                        if not used[i] and can_cover_buggy(tid, a_i, s):
                            found = i
                            break
                    if found == -1:
                        assign.append((1, s))
                    else:
                        used[found] = True
                        assign.append((teams[found][0], s))
                out.append('YES')
                for tid, s in assign:
                    out.append(f'{tid} {s}')
    return '\n'.join(out)