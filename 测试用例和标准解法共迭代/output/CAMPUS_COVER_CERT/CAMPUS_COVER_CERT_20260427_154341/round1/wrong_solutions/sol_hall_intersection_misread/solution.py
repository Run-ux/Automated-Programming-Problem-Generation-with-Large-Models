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
            # 简化处理：仅当 K 较小时进行区间检查，否则默认 YES（模拟选手对大数据范围的妥协）
            limit = min(K, 500)
            conflict = None
            for L in range(limit):
                if conflict: break
                for R in range(L, limit):
                    cnt = 0
                    for tid, a in teams:
                        r1 = a % x
                        r2 = (a + 1) % x
                        # 错误理解：要求队伍的两个合法时段都必须完全落在 [L, R] 内
                        if r1 >= L and r1 <= R and r2 >= L and r2 <= R:
                            cnt += 1
                    if cnt < R - L + 1:
                        conflict = (L, R)
                        break
            
            if conflict:
                out.append('NO')
                out.append(f'{conflict[0]} {conflict[1]}')
            else:
                out.append('YES')
                used_slots = set()
                assigned_count = 0
                for tid, a in teams:
                    if assigned_count == K: break
                    r1 = a % x
                    r2 = (a + 1) % x
                    for s in [r1, r2]:
                        if s < K and s not in used_slots:
                            out.append(f'{tid} {s}')
                            used_slots.add(s)
                            assigned_count += 1
                            break
    return '\n'.join(out)