def solve(input_str: str) -> str:
    import sys
    data = input_str.split()
    it = iter(data)
    x = int(next(it))
    q = int(next(it))
    ops = []
    for _ in range(q):
        ops.append((int(next(it)), int(next(it))))
    
    teams = []
    team_id = 0
    out = []
    
    for t, v in ops:
        if t == 1:
            team_id += 1
            teams.append((team_id, v))
        else:
            K = v
            # 错误理解：认为周期性质意味着只需检查前 x 个时段，忽略 K >> x 时的累积赤字
            limit = min(K, x)
            conflict = None
            for L in range(limit):
                if conflict: break
                for R in range(L, limit):
                    cnt = 0
                    for tid, a in teams:
                        r1 = a % x
                        r2 = (a + 1) % x
                        if (r1 >= L and r1 <= R) or (r2 >= L and r2 <= R):
                            cnt += 1
                    if cnt < R - L + 1:
                        conflict = (L, R)
                        break
            
            if conflict:
                out.append('NO')
                out.append(f'{conflict[0]} {conflict[1]}')
            else:
                out.append('YES')
                # 简单构造输出，可能因未考虑全局而失败，但主要错误在 NO 分支误判为 YES
                used_slots = set()
                for s in range(K):
                    for tid, a in teams:
                        r1 = a % x
                        r2 = (a + 1) % x
                        if s == r1 or s == r2:
                            if s not in used_slots:
                                out.append(f'{tid} {s}')
                                used_slots.add(s)
                                break
    return '\n'.join(out)