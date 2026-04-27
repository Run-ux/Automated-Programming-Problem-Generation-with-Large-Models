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
                r1 = a % x
                r2 = (a + 1) % x
                chosen = -1
                for s in range(r1, K, x):
                    if s not in used:
                        chosen = s
                        break
                if chosen == -1:
                    for s in range(r2, K, x):
                        if s not in used:
                            chosen = s
                            break
                if chosen != -1:
                    used.add(chosen)
                    assign.append((tid, chosen))
            if len(assign) == K:
                out.append('YES')
                out.extend(f'{t} {s}' for t, s in assign)
            else:
                out.append('NO')
                out.append(f'0 {K-1}')
    return '\n'.join(out)